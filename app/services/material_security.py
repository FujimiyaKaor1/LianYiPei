"""Fail-closed validation and malware scanning for procurement materials."""

from __future__ import annotations

import hashlib
from io import BytesIO
import os
from pathlib import Path
import shutil
import socket
import struct
import subprocess
import tempfile
from zipfile import BadZipFile, ZipFile

from flask import current_app


class InvalidMaterial(ValueError):
    pass


class MaterialInfected(ValueError):
    pass


class MaterialScanUnavailable(RuntimeError):
    pass


EICAR_SIGNATURE = b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE"
MAX_ARCHIVE_ENTRIES = 1000
MAX_UNCOMPRESSED_BYTES = 50 * 1024 * 1024
MAX_COMPRESSION_RATIO = 100
MAX_MATERIAL_BYTES = 10 * 1024 * 1024


def scan_material(filename: str, content: bytes) -> dict:
    """Validate format, archive bounds and malware status before any parser runs."""
    suffix = Path(filename or "").suffix.lower()
    if not content:
        raise InvalidMaterial("文件内容为空")
    # Reject before storage or archive inspection. The upload route reads one
    # byte over the limit specifically so this check can prevent oversized
    # encrypted objects from being persisted.
    if len(content) > MAX_MATERIAL_BYTES:
        raise InvalidMaterial("文件大小不能超过10MB")
    if EICAR_SIGNATURE in content:
        raise MaterialInfected("文件未通过安全扫描")

    _validate_magic_and_archive(suffix, content)
    mode = str(current_app.config.get("MATERIAL_AV_MODE") or "basic").strip().lower()
    if mode not in {"basic", "clamav"}:
        raise MaterialScanUnavailable("材料安全扫描模式配置错误")
    engine = "signature-and-archive"
    if mode == "clamav":
        _scan_with_clamav(content)
        engine = "clamav"
    return {
        "status": "clean",
        "engine": engine,
        "sha256": hashlib.sha256(content).hexdigest(),
        "policy_version": "material-security.v1",
    }


def _validate_magic_and_archive(suffix: str, content: bytes) -> None:
    if suffix == ".pdf":
        if not content.startswith(b"%PDF-"):
            raise InvalidMaterial("文件扩展名与PDF内容不一致")
        return
    if suffix in {".doc", ".xls"}:
        raise InvalidMaterial("旧版 DOC/XLS 暂不支持安全解析，请另存为 DOCX/XLSX")
    if suffix in {".docx", ".xlsx"}:
        if not content.startswith(b"PK"):
            raise InvalidMaterial("文件扩展名与Office文档内容不一致")
        try:
            with ZipFile(BytesIO(content)) as archive:
                entries = archive.infolist()
                if len(entries) > MAX_ARCHIVE_ENTRIES:
                    raise InvalidMaterial("Office文档包含过多文件")
                total_size = sum(entry.file_size for entry in entries)
                compressed_size = max(1, sum(entry.compress_size for entry in entries))
                if total_size > MAX_UNCOMPRESSED_BYTES or (
                    total_size > 5 * 1024 * 1024
                    and total_size / compressed_size > MAX_COMPRESSION_RATIO
                ):
                    raise InvalidMaterial("Office文档解压规模异常")
                if any(entry.flag_bits & 0x1 for entry in entries):
                    raise InvalidMaterial("不支持加密的Office文档")
                names = {entry.filename for entry in entries}
                required = "word/document.xml" if suffix == ".docx" else "xl/workbook.xml"
                if required not in names:
                    raise InvalidMaterial("Office文档结构与扩展名不一致")
                if any(name.lower().endswith("vbaproject.bin") for name in names):
                    raise InvalidMaterial("采购材料不得包含宏代码")
        except BadZipFile as exc:
            raise InvalidMaterial("Office文档损坏或不是有效压缩包") from exc
        return
    if suffix in {".png", ".jpg", ".jpeg"}:
        try:
            from PIL import Image, UnidentifiedImageError

            with Image.open(BytesIO(content)) as image:
                image.verify()
            with Image.open(BytesIO(content)) as image:
                if image.width * image.height > 25_000_000:
                    raise InvalidMaterial("图片像素过大")
        except InvalidMaterial:
            raise
        except (UnidentifiedImageError, OSError) as exc:
            raise InvalidMaterial("图片损坏或格式与扩展名不一致") from exc
        return
    if suffix == ".csv":
        if b"\x00" in content or content.startswith((b"MZ", b"\x7fELF")):
            raise InvalidMaterial("CSV内容格式异常")
        return
    raise InvalidMaterial("不支持的采购材料格式")


def _scan_with_clamav(content: bytes) -> None:
    host = str(current_app.config.get("CLAMAV_HOST") or "").strip()
    if host:
        _scan_with_clamd(content, host=host)
        return
    command = str(current_app.config.get("CLAMAV_COMMAND") or "clamscan").strip()
    executable = shutil.which(command)
    if not executable:
        raise MaterialScanUnavailable("病毒扫描服务不可用，暂时不能接收材料")
    path = ""
    try:
        with tempfile.NamedTemporaryFile(prefix="chain-material-", delete=False) as handle:
            path = handle.name
            handle.write(content)
        os.chmod(path, 0o600)
        result = subprocess.run(
            [executable, "--no-summary", path],
            capture_output=True,
            timeout=30,
            check=False,
        )
        if result.returncode == 1:
            raise MaterialInfected("文件未通过病毒扫描")
        if result.returncode != 0:
            raise MaterialScanUnavailable("病毒扫描服务执行失败")
    except subprocess.TimeoutExpired as exc:
        raise MaterialScanUnavailable("病毒扫描服务超时") from exc
    finally:
        if path:
            try:
                os.unlink(path)
            except FileNotFoundError:
                pass


def _clamav_timeout() -> float:
    try:
        return max(1.0, min(float(current_app.config.get("CLAMAV_TIMEOUT_SECONDS") or 30), 120.0))
    except (TypeError, ValueError):
        return 30.0


def _scan_with_clamd(content: bytes, *, host: str) -> None:
    """Scan bytes through clamd's private INSTREAM protocol.

    The Web process never writes uploaded content to a shared scan directory
    and never exposes ClamAV publicly.  The protocol has a four-byte network
    order length before each chunk and a zero-length terminator.  A bounded
    response read prevents a misbehaving scanner from keeping an upload worker
    blocked indefinitely.
    """
    try:
        port = int(current_app.config.get("CLAMAV_PORT") or 3310)
    except (TypeError, ValueError):
        raise MaterialScanUnavailable("病毒扫描服务端口配置错误")
    timeout = _clamav_timeout()
    try:
        with socket.create_connection((host, port), timeout=timeout) as connection:
            connection.settimeout(timeout)
            connection.sendall(b"zINSTREAM\0")
            view = memoryview(content)
            chunk_size = 1024 * 1024
            for offset in range(0, len(view), chunk_size):
                chunk = view[offset : offset + chunk_size]
                connection.sendall(struct.pack("!I", len(chunk)))
                connection.sendall(chunk)
            connection.sendall(b"\x00\x00\x00\x00")
            response = bytearray()
            while len(response) < 8192:
                block = connection.recv(min(1024, 8192 - len(response)))
                if not block:
                    break
                response.extend(block)
                if b"\n" in block or b"\x00" in block:
                    break
    except (OSError, socket.timeout) as exc:
        raise MaterialScanUnavailable("病毒扫描服务不可用") from exc

    result = bytes(response).decode("utf-8", errors="replace").strip()
    if not result:
        raise MaterialScanUnavailable("病毒扫描服务未返回结果")
    normalized = result.upper()
    if "FOUND" in normalized:
        raise MaterialInfected("文件未通过病毒扫描")
    if " OK" in normalized or normalized.endswith("OK"):
        return
    raise MaterialScanUnavailable("病毒扫描服务返回了未知结果")


def ping_clamd(*, host: str, port: int, timeout: float = 3.0) -> bool:
    """Return whether a private clamd endpoint answers ``PING``."""
    try:
        with socket.create_connection((host, int(port)), timeout=max(0.5, float(timeout))) as connection:
            connection.settimeout(max(0.5, float(timeout)))
            connection.sendall(b"zPING\0")
            # clamd returns ``PONG\0`` for the NUL-terminated command form;
            # ``str.strip`` does not remove NUL bytes.
            response = connection.recv(64).decode("ascii", errors="ignore").strip("\x00\r\n \t").upper()
            return response == "PONG"
    except (OSError, ValueError, socket.timeout):
        return False
