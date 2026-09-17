"""Deterministic intent and file helpers used before model providers are enabled."""
from __future__ import annotations

import re
from pathlib import Path


def parse_procurement_intent(text: str) -> dict:
    value = (text or "").strip()[:500]
    intent: dict = {"raw_text": value, "confidence": "rule"}
    regions = ("华东", "华南", "华北", "华中", "西南", "西北", "东北", "广东", "浙江", "江苏", "山东", "四川", "湖南")
    region = next((item for item in regions if item in value), None)
    if region:
        intent["region"] = region
    quantity_match = re.search(r"(\d+(?:\.\d+)?)\s*(万|千)?\s*(件|台|套|吨|公斤|个|pcs)", value, re.I)
    if quantity_match:
        amount = float(quantity_match.group(1)) * {"万": 10000, "千": 1000}.get(quantity_match.group(2) or "", 1)
        intent["quantity"] = int(amount) if amount.is_integer() else amount
        intent["unit"] = quantity_match.group(3)
    delivery_match = re.search(r"(?:交期|交付|交货|周期)[^\d]{0,8}(\d+)\s*(?:天|日)?|(\d+)\s*(?:天|日)\s*(?:内|交付|交货|交期)?", value)
    if delivery_match:
        intent["delivery_days"] = int(delivery_match.group(1) or delivery_match.group(2))
    processes = [item for item in ("注塑", "冲压", "铸造", "锻造", "CNC", "机加工", "表面处理", "焊接", "装配") if item.lower() in value.lower()]
    if processes:
        intent["processes"] = processes
    certifications = [item for item in ("ISO 9001", "ISO9001", "IATF16949", "ISO", "3C", "CE", "FDA", "专精特新", "绿色工厂") if item.lower() in value.lower()]
    if certifications:
        intent["certifications"] = certifications
    if "专精特新" in value or "小巨人" in value:
        intent["is_little_giant"] = True
    if "绿色工厂" in value:
        intent["is_green_factory"] = True
    if any(item in value for item in ("出口", "外贸", "跨境", "国际贸易")):
        intent["is_export"] = True
    numeric_patterns = {
        "min_credit": r"(?:信用分|信用)[^\d]{0,8}(?:至少|不低于|最低|超过)?\s*(\d+(?:\.\d+)?)",
        "min_registered_capital": r"(?:注册资本)[^\d]{0,8}(?:至少|不低于|最低|超过)?\s*(\d+(?:\.\d+)?)",
        "min_capacity": r"(?:产能)[^\d]{0,8}(?:至少|不低于|最低|超过)?\s*(\d+(?:\.\d+)?)",
        "max_distance": r"(?:距离|半径)[^\d]{0,8}(?:不超过|以内|最大)?\s*(\d+(?:\.\d+)?)\s*(?:公里|km)",
    }
    for key, pattern in numeric_patterns.items():
        match = re.search(pattern, value, re.I)
        if match:
            number = float(match.group(1))
            intent[key] = int(number) if number.is_integer() else number
    preference_map = {"green": ("绿色优先", "低碳优先"), "distance": ("距离优先", "就近优先"), "credit": ("信用优先",), "capacity": ("产能优先",), "tech": ("技术优先", "工艺优先")}
    preferences = {key: 1.8 for key, phrases in preference_map.items() if any(phrase in value for phrase in phrases)}
    if preferences:
        intent["preferences"] = preferences
    product = re.sub(r"^(我想|我要|帮我|请帮我|找|需要|采购|采购一批)", "", value).strip(" ，,。")
    product = re.sub(r"^(?:能做|可以做|可做|生产|制造)", "", product).strip()
    product = re.split(r"(?:，|,|；|;|数量|交期|交付|支持出口|需要|供应商|厂家|工厂)", product, maxsplit=1)[0].strip()
    intent["product"] = product[:120] if product else value[:120]
    return intent


def merge_procurement_intent(previous: dict | None, incoming: dict, text: str) -> dict:
    """Incrementally merge intent; explicit natural-language relaxations clear constraints."""
    merged = dict(previous or {})
    clear_map = {
        "region": ("不限地区", "地区不限", "取消地区限制", "全国都可以", "全国均可"),
        "certifications": ("不限资质", "取消资质限制", "资质不限"),
        "delivery_days": ("不限交期", "取消交期限制", "交期不限"),
        "max_distance": ("不限距离", "取消距离限制", "距离不限"),
    }
    for key, phrases in clear_map.items():
        if any(phrase in text for phrase in phrases):
            merged.pop(key, None)
    for key, value in incoming.items():
        if key not in {"raw_text", "confidence"} and value not in (None, "", []):
            merged[key] = value
    merged["raw_text"] = text[:500]
    merged["confidence"] = incoming.get("confidence", "rule")
    return merged


def preview_tabular_file(filename: str, content: bytes) -> dict:
    """Return a bounded, non-persistent preview; callers decide what to import."""
    suffix = Path(filename or "").suffix.lower()
    if suffix not in {".csv", ".xlsx", ".xls"}:
        return {"kind": "document", "sheets": [], "rows": [], "errors": ["当前首版只预览 CSV/XLSX 表格，文档已安全接收"]}
    try:
        import pandas as pd
        from io import BytesIO

        if suffix == ".csv":
            frame = pd.read_csv(BytesIO(content), nrows=20)
            sheets = {"Sheet1": frame}
        else:
            sheets = pd.read_excel(BytesIO(content), sheet_name=None, nrows=20)
        preview = []
        for name, frame in list(sheets.items())[:10]:
            columns = [str(column)[:80] for column in frame.columns.tolist()[:50]]
            rows = [{str(key): (None if value != value else str(value)[:300]) for key, value in row.items()} for row in frame.to_dict(orient="records")[:20]]
            preview.append({"name": str(name)[:80], "columns": columns, "rows": rows})
        return {"kind": "table", "sheets": preview, "rows": sum(len(item["rows"]) for item in preview), "errors": []}
    except Exception:
        return {"kind": "table", "sheets": [], "rows": 0, "errors": ["文件格式或编码无法解析，请下载模板后重试"]}
