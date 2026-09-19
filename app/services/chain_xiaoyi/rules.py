"""Deterministic intent and file helpers used before model providers are enabled."""
from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from io import BytesIO
from zipfile import BadZipFile, ZipFile
from xml.etree import ElementTree


def _ocr_pdf(content: bytes, max_pages: int = 10) -> tuple[str, str | None]:
    """OCR a bounded PDF using local binaries without invoking a shell."""
    pdftoppm = shutil.which("pdftoppm")
    tesseract = shutil.which("tesseract")
    if not pdftoppm or not tesseract:
        return "", "扫描件需要安装 pdftoppm 和 tesseract OCR 组件"
    try:
        with tempfile.TemporaryDirectory(prefix="chain-xiaoyi-ocr-") as directory:
            source = Path(directory) / "source.pdf"
            prefix = Path(directory) / "page"
            source.write_bytes(content)
            subprocess.run(
                [pdftoppm, "-f", "1", "-l", str(max_pages), "-r", "200", "-png", str(source), str(prefix)],
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=45,
            )
            parts = []
            for image in sorted(Path(directory).glob("page-*.png"))[:max_pages]:
                result = subprocess.run(
                    [tesseract, str(image), "stdout", "-l", "chi_sim+eng", "--psm", "6"],
                    check=True, capture_output=True, timeout=20,
                )
                text = result.stdout.decode("utf-8", errors="replace").strip()
                if text:
                    parts.append(text)
            return "\n".join(parts)[:50_000], None
    except (OSError, subprocess.SubprocessError):
        return "", "扫描件 OCR 失败，请上传更清晰的文件或文本型 PDF"


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
    """Return a bounded, non-persistent preview for procurement materials."""
    suffix = Path(filename or "").suffix.lower()
    if suffix == ".docx":
        try:
            with ZipFile(BytesIO(content)) as archive:
                names = set(archive.namelist())
                if "word/document.xml" not in names:
                    raise ValueError("缺少 Word 正文")
                if archive.getinfo("word/document.xml").file_size > 5 * 1024 * 1024:
                    raise ValueError("Word 正文解压后过大")
                root = ElementTree.fromstring(archive.read("word/document.xml"))
                text = "\n".join(
                    node.text.strip() for node in root.iter()
                    if node.tag.endswith("}t") and node.text and node.text.strip()
                )[:50_000]
            return {"kind": "document", "format": "docx", "text": text, "sheets": [], "rows": 0, "errors": [] if text else ["Word 文档没有可提取的文本"]}
        except (BadZipFile, ValueError, ElementTree.ParseError):
            return {"kind": "document", "format": "docx", "text": "", "sheets": [], "rows": 0, "errors": ["Word 文件损坏或格式无法解析"]}
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
            reader = PdfReader(BytesIO(content))
            text = "\n".join((page.extract_text() or "") for page in reader.pages[:50])[:50_000]
            ocr_used = False
            errors = []
            if not text.strip():
                text, ocr_error = _ocr_pdf(content)
                ocr_used = bool(text.strip())
                if ocr_error:
                    errors.append(ocr_error)
                elif not ocr_used:
                    errors.append("PDF 没有识别出可用文本")
            return {"kind": "document", "format": "pdf", "text": text, "pages": min(len(reader.pages), 50), "ocr_used": ocr_used, "sheets": [], "rows": 0, "errors": errors}
        except Exception:
            return {"kind": "document", "format": "pdf", "text": "", "sheets": [], "rows": 0, "errors": ["PDF 文件损坏或当前环境缺少 PDF 解析器"]}
    if suffix == ".doc":
        return {"kind": "document", "format": "doc", "text": "", "sheets": [], "rows": 0, "errors": ["旧版 DOC 暂不能安全解析，请另存为 DOCX 后上传"]}
    if suffix not in {".csv", ".xlsx", ".xls"}:
        return {"kind": "document", "sheets": [], "rows": 0, "errors": ["不支持的文件格式"]}
    try:
        import pandas as pd
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


_FIELD_ALIASES = {
    # Include the English headers commonly emitted by ERP exports in addition
    # to Chinese procurement templates.  Header matching is case-insensitive.
    "product": ("产品", "产品名称", "物料", "物料名称", "品名", "采购品", "名称", "name", "product", "product_name", "item", "item_name"),
    "specification": ("规格", "规格型号", "型号", "技术要求", "产品规格", "spec", "specification", "model"),
    "quantity": ("数量", "采购数量", "需求数量", "quantity", "qty", "amount"),
    "unit": ("单位", "计量单位", "unit", "uom"),
    "delivery_days": ("交期", "交货期", "交付周期", "交货天数", "delivery", "delivery_days", "lead_time"),
    "region": ("地区", "区域", "省份", "交货地区", "region", "province", "city"),
    "processes": ("工艺", "加工工艺", "制造工艺", "process", "processes"),
    "certifications": ("资质", "认证", "认证要求", "certification", "certifications"),
    "budget": ("预算", "目标价格", "预算范围", "含税预算", "budget", "target_price"),
}


def _field_value(key: str, raw):
    value = "" if raw is None else str(raw).strip()
    if not value:
        return None
    if key == "quantity":
        match = re.search(r"\d+(?:\.\d+)?", value.replace(",", ""))
        if not match:
            return None
        number = float(match.group())
        return int(number) if number.is_integer() else number
    if key == "delivery_days":
        match = re.search(r"\d+", value)
        return int(match.group()) if match else None
    if key in {"processes", "certifications"}:
        return [item.strip() for item in re.split(r"[,，、;/；]", value) if item.strip()][:20]
    return value[:500]


def extract_procurement_draft(preview: dict) -> dict:
    """Extract a conservative, evidenced procurement draft from a preview."""
    fields: dict = {}
    items: list[dict] = []
    if preview.get("kind") == "table":
        for sheet in preview.get("sheets") or []:
            rows = sheet.get("rows") or []
            if not rows:
                continue
            for row_index, row in enumerate(rows, start=2):
                normalized = {re.sub(r"\s+", "", str(column)).lower(): (column, value) for column, value in row.items()}
                item_fields: dict = {}
                for key, aliases in _FIELD_ALIASES.items():
                    for alias in aliases:
                        match = normalized.get(alias.lower())
                        if not match:
                            continue
                        column, raw = match
                        value = _field_value(key, raw)
                        if value is not None:
                            item_fields[key] = {"value": value, "confidence": 0.98, "evidence": {"sheet": sheet.get("name"), "row": row_index, "column": str(column)}}
                        break
                # A row without a product is generally a note/subtotal rather
                # than a purchasable line item and is kept out of automation.
                if "product" in item_fields:
                    item_missing = [key for key in ("product", "quantity") if key not in item_fields]
                    items.append({"index": len(items) + 1, "fields": item_fields, "missing_required": item_missing})
        if items:
            fields = dict(items[0]["fields"])
    else:
        text = str(preview.get("text") or "")
        patterns = {
            "product": r"(?:产品名称|产品|物料名称|品名)\s*[:：]\s*([^\n]{1,120})",
            "specification": r"(?:规格型号|规格|型号|技术要求)\s*[:：]\s*([^\n]{1,500})",
            "quantity": r"(?:采购数量|需求数量|数量)\s*[:：]\s*([^\n]{1,40})",
            "unit": r"(?:计量单位|单位)\s*[:：]\s*([^\n]{1,20})",
            "delivery_days": r"(?:交货期|交期|交付周期)\s*[:：]\s*([^\n]{1,40})",
            "region": r"(?:交货地区|地区|区域)\s*[:：]\s*([^\n]{1,80})",
            "processes": r"(?:加工工艺|制造工艺|工艺)\s*[:：]\s*([^\n]{1,200})",
            "certifications": r"(?:认证要求|资质|认证)\s*[:：]\s*([^\n]{1,200})",
            "budget": r"(?:预算范围|预算|目标价格)\s*[:：]\s*([^\n]{1,100})",
        }
        for key, pattern in patterns.items():
            match = re.search(pattern, text, re.I)
            if match:
                value = _field_value(key, match.group(1))
                if value is not None:
                    line = text[:match.start()].count("\n") + 1
                    fields[key] = {"value": value, "confidence": 0.86, "evidence": {"page_or_line": line, "quote": match.group(0)[:300]}}
        if fields:
            items.append({"index": 1, "fields": dict(fields), "missing_required": [key for key in ("product", "quantity") if key not in fields]})
    missing = sorted({key for item in items for key in item.get("missing_required", [])}) if items else [key for key in ("product", "quantity") if key not in fields]
    questions = {"product": "请确认需要采购的产品名称", "quantity": "请补充采购数量"}
    return {
        "fields": fields,
        "items": items,
        "missing_required": missing,
        "clarifying_questions": [questions[key] for key in missing],
        "schema_version": "procurement.v2",
    }
