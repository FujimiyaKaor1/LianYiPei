"""Deterministic natural-language intake for supplier quote replies.

The parser extracts only values explicitly present in the supplier's message.
It never asks an LLM to invent commercial terms. A message beginning with
``报价`` produces a preview; only ``确认报价`` is an executable commitment.
"""
from __future__ import annotations

from datetime import date, timedelta
import re
from typing import Any


class SupplierQuoteParseError(ValueError):
    """Raised when a supplier quote command is incomplete or malformed."""


_COMMAND = re.compile(r"^\s*(确认)?报价\s*#?\s*(\d+)\b", re.IGNORECASE)
_NUMBER = r"(\d+(?:\.\d+)?)"


def is_supplier_quote_command(text: str) -> bool:
    return bool(_COMMAND.search(str(text or "").strip()))


def parse_supplier_quote(text: str) -> dict[str, Any]:
    content = re.sub(r"\s+", " ", str(text or "").strip())
    command = _COMMAND.search(content)
    if not command:
        raise SupplierQuoteParseError("请使用“报价 询价ID 单价…”提交报价")

    price_match = re.search(rf"(?:单价|含税价|未税价)\s*[:：]?\s*[¥￥]?\s*{_NUMBER}", content, re.IGNORECASE)
    if not price_match:
        raise SupplierQuoteParseError("报价中缺少单价，例如：单价12.8元")

    details: dict[str, Any] = {}
    details["tax_included"] = "不含税" not in content if "含税" in content else False
    _copy_number(details, "tax_rate", content, rf"(?:税率|含税)\s*[:：]?\s*{_NUMBER}\s*%")
    _copy_number(details, "moq", content, rf"(?:MOQ|起订量|最小起订量)\s*[:：]?\s*{_NUMBER}")
    _copy_number(details, "delivery_days", content, rf"(?:交期|交货期)\s*[:：]?\s*{_NUMBER}\s*天")
    _copy_number(details, "mold_fee", content, rf"模具费\s*[:：]?\s*[¥￥]?\s*{_NUMBER}")
    _copy_number(details, "freight", content, rf"运费\s*[:：]?\s*[¥￥]?\s*{_NUMBER}")

    payment = re.search(
        r"付款(?:条件)?\s*[:：]?\s*(.+?)(?=\s+(?:有效期|币种|备注|交期|MOQ|起订量|模具费|运费|税率|含税|不含税)|$)",
        content,
        re.IGNORECASE,
    )
    if payment:
        details["payment_terms"] = payment.group(1).strip()[:200]

    valid_date = re.search(r"有效期(?:至)?\s*[:：]?\s*(\d{4})[-/.年](\d{1,2})[-/.月](\d{1,2})日?", content)
    valid_days = re.search(r"有效期\s*[:：]?\s*(\d{1,4})\s*天", content)
    if valid_date:
        try:
            details["valid_until"] = date(
                int(valid_date.group(1)),
                int(valid_date.group(2)),
                int(valid_date.group(3)),
            ).isoformat()
        except ValueError as exc:
            raise SupplierQuoteParseError("报价有效期日期无效") from exc
    elif valid_days:
        days = int(valid_days.group(1))
        if days < 1 or days > 3650:
            raise SupplierQuoteParseError("报价有效期必须在1至3650天之间")
        details["valid_until"] = (date.today() + timedelta(days=days)).isoformat()

    currency = "CNY"
    if re.search(r"(?:USD|美元|美金)", content, re.IGNORECASE):
        currency = "USD"
    elif re.search(r"(?:EUR|欧元)", content, re.IGNORECASE):
        currency = "EUR"
    details["currency"] = currency

    return {
        "quote_id": int(command.group(2)),
        "confirmed": bool(command.group(1)),
        "reply_price": float(price_match.group(1)),
        "reply_details": details,
    }


def format_quote_preview(parsed: dict[str, Any], product_name: str) -> str:
    details = parsed.get("reply_details") or {}
    lines = [
        f"报价预览 #{parsed['quote_id']}：{product_name}",
        f"单价：{parsed['reply_price']:g} {details.get('currency', 'CNY')}",
        f"含税：{'是' if details.get('tax_included') else '否'}",
    ]
    labels = (
        ("tax_rate", "税率", "%"),
        ("moq", "MOQ", ""),
        ("delivery_days", "交期", "天"),
        ("mold_fee", "模具费", ""),
        ("freight", "运费", ""),
        ("payment_terms", "付款条件", ""),
        ("valid_until", "有效期至", ""),
    )
    for key, label, suffix in labels:
        if details.get(key) is not None:
            lines.append(f"{label}：{details[key]}{suffix}")
    lines.append("确认无误后，请将开头“报价”改为“确认报价”并重新发送。")
    return "\n".join(lines)


def _copy_number(target: dict[str, Any], key: str, content: str, pattern: str) -> None:
    match = re.search(pattern, content, re.IGNORECASE)
    if not match:
        return
    value = float(match.group(1))
    target[key] = int(value) if value.is_integer() else value
