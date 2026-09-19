"""Conservative business-license extraction for registration drafts."""
from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from io import BytesIO
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from app.services.chain_xiaoyi.rules import preview_tabular_file


ALLOWED_SUFFIXES = {".pdf", ".docx", ".png", ".jpg", ".jpeg"}


def _ocr_image(content: bytes, suffix: str) -> tuple[str, str | None]:
    tesseract = shutil.which("tesseract")
    if not tesseract:
        return "", "图片识别需要安装 tesseract OCR 组件"
    try:
        with Image.open(BytesIO(content)) as image:
            image.verify()
        with Image.open(BytesIO(content)) as image:
            if image.width * image.height > 25_000_000:
                return "", "图片像素过大"
        with tempfile.TemporaryDirectory(prefix="registration-ocr-") as directory:
            source = Path(directory) / f"license{suffix}"
            source.write_bytes(content)
            result = subprocess.run(
                [tesseract, str(source), "stdout", "-l", "chi_sim+eng", "--psm", "6"],
                check=True, capture_output=True, timeout=30,
            )
            return result.stdout.decode("utf-8", errors="replace")[:50_000], None
    except (UnidentifiedImageError, OSError, subprocess.SubprocessError):
        return "", "图片损坏或 OCR 识别失败"


def _match_field(text: str, pattern: str, confidence: float = 0.9):
    match = re.search(pattern, text, re.I)
    if not match:
        return None
    value = re.sub(r"\s+", " ", match.group(1)).strip(" ：:")
    if not value:
        return None
    line = text[:match.start()].count("\n") + 1
    return {"value": value[:1000], "confidence": confidence, "evidence": {"page_or_line": line, "quote": match.group(0)[:300]}}


def extract_registration_material(filename: str, content: bytes) -> dict:
    suffix = Path(filename or "").suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise ValueError("仅支持 PDF、DOCX、PNG、JPG 营业执照材料")
    if not content or len(content) > 10 * 1024 * 1024:
        raise ValueError("材料不能为空且不能超过 10MB")
    errors: list[str] = []
    ocr_used = False
    if suffix in {".png", ".jpg", ".jpeg"}:
        text, error = _ocr_image(content, suffix)
        ocr_used = bool(text.strip())
        if error:
            errors.append(error)
    else:
        preview = preview_tabular_file(filename, content)
        text = str(preview.get("text") or "")
        errors.extend(preview.get("errors") or [])
        ocr_used = bool(preview.get("ocr_used"))

    patterns = {
        "name": r"(?:名称|企业名称|公司名称)\s*[:：]?\s*([^\n]{2,120})",
        "unified_social_credit_code": r"(?:统一社会信用代码|社会信用代码)\s*[:：]?\s*([0-9A-Z]{18})",
        "legal_representative": r"(?:法定代表人|法人)\s*[:：]?\s*([^\n]{2,50})",
        "address": r"(?:住所|注册地址|地址)\s*[:：]?\s*([^\n]{4,300})",
        "registered_capital": r"(?:注册资本|注册资金)\s*[:：]?\s*([^\n]{1,80})",
        "business_scope": r"(?:经营范围)\s*[:：]?\s*([^\n]{4,1000})",
    }
    fields = {key: field for key, pattern in patterns.items() if (field := _match_field(text, pattern))}
    capital = fields.get("registered_capital")
    if capital:
        number = re.search(r"\d+(?:\.\d+)?", str(capital["value"]).replace(",", ""))
        if number:
            capital["raw_value"] = capital["value"]
            capital["value"] = float(number.group())
    required = ("name", "unified_social_credit_code")
    missing = [key for key in required if key not in fields]
    return {
        "fields": fields,
        "missing_required": missing,
        "clarifying_questions": (["请确认企业名称"] if "name" in missing else []) + (["请确认统一社会信用代码"] if "unified_social_credit_code" in missing else []),
        "ocr_used": ocr_used,
        "errors": errors,
        "status": "needs_clarification" if missing else "draft",
        "schema_version": "enterprise-registration.v1",
    }
