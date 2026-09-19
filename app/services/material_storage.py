"""Encrypted material storage with local and S3-compatible backends."""

from __future__ import annotations

from pathlib import Path
import os
import tempfile

from cryptography.fernet import Fernet, InvalidToken
from flask import current_app


class MaterialStorageUnavailable(RuntimeError):
    pass


def store_material(*, content: bytes, sha256: str, owner_id: int, session_id: int) -> str | None:
    backend = str(current_app.config.get("MATERIAL_STORAGE_BACKEND") or "none").strip().lower()
    if backend == "none":
        return None
    encrypted = _fernet().encrypt(content)
    object_key = f"materials/{int(owner_id)}/{int(session_id)}/{sha256}.bin"
    if backend == "filesystem":
        root = _storage_root()
        target = (root / object_key).resolve()
        if root not in target.parents:
            raise MaterialStorageUnavailable("材料存储路径无效")
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        temporary_path = ""
        try:
            with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".material-", delete=False) as handle:
                temporary_path = handle.name
                handle.write(encrypted)
            os.chmod(temporary_path, 0o600)
            os.replace(temporary_path, target)
        finally:
            if temporary_path:
                try:
                    os.unlink(temporary_path)
                except FileNotFoundError:
                    pass
        return object_key
    if backend == "s3":
        bucket = str(current_app.config.get("MATERIAL_S3_BUCKET") or "").strip()
        if not bucket:
            raise MaterialStorageUnavailable("材料对象存储桶未配置")
        client = _s3_client()
        try:
            client.put_object(
                Bucket=bucket,
                Key=object_key,
                Body=encrypted,
                ContentType="application/octet-stream",
                ServerSideEncryption="AES256",
                Metadata={"sha256": sha256, "encrypted": "fernet"},
            )
        except Exception as exc:
            raise MaterialStorageUnavailable("材料对象存储写入失败") from exc
        return object_key
    raise MaterialStorageUnavailable("材料存储后端配置错误")


def retrieve_material(object_key: str) -> bytes:
    backend = str(current_app.config.get("MATERIAL_STORAGE_BACKEND") or "none").strip().lower()
    if backend == "filesystem":
        root = _storage_root()
        target = (root / str(object_key)).resolve()
        if root not in target.parents or not target.is_file():
            raise MaterialStorageUnavailable("材料对象不存在")
        encrypted = target.read_bytes()
    elif backend == "s3":
        bucket = str(current_app.config.get("MATERIAL_S3_BUCKET") or "").strip()
        if not bucket:
            raise MaterialStorageUnavailable("材料对象存储桶未配置")
        try:
            encrypted = _s3_client().get_object(Bucket=bucket, Key=object_key)["Body"].read()
        except Exception as exc:
            raise MaterialStorageUnavailable("材料对象读取失败") from exc
    else:
        raise MaterialStorageUnavailable("材料未配置持久化存储")
    try:
        return _fernet().decrypt(encrypted)
    except InvalidToken as exc:
        raise MaterialStorageUnavailable("材料解密失败或完整性校验不通过") from exc


def _fernet() -> Fernet:
    key = str(current_app.config.get("MATERIAL_ENCRYPTION_KEY") or "").strip().encode("ascii")
    try:
        return Fernet(key)
    except (ValueError, TypeError) as exc:
        raise MaterialStorageUnavailable("材料加密密钥未正确配置") from exc


def _storage_root() -> Path:
    configured = str(current_app.config.get("MATERIAL_STORAGE_ROOT") or "").strip()
    if not configured:
        raise MaterialStorageUnavailable("材料私有存储目录未配置")
    root = Path(configured).resolve()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    return root


def _s3_client():
    try:
        import boto3
    except ImportError as exc:
        raise MaterialStorageUnavailable("S3客户端依赖未安装") from exc
    kwargs = {
        "region_name": current_app.config.get("MATERIAL_S3_REGION") or None,
        "endpoint_url": current_app.config.get("MATERIAL_S3_ENDPOINT_URL") or None,
    }
    return boto3.client("s3", **{key: value for key, value in kwargs.items() if value})
