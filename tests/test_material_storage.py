"""Encrypted S3-compatible procurement material storage tests."""

from io import BytesIO
from unittest.mock import MagicMock, patch

from cryptography.fernet import Fernet

from app.services.material_storage import retrieve_material, store_material


def test_s3_material_storage_encrypts_before_upload_and_decrypts_on_read(app, monkeypatch):
    key = Fernet.generate_key().decode("ascii")
    monkeypatch.setitem(app.config, "MATERIAL_STORAGE_BACKEND", "s3")
    monkeypatch.setitem(app.config, "MATERIAL_ENCRYPTION_KEY", key)
    monkeypatch.setitem(app.config, "MATERIAL_S3_BUCKET", "private-materials")
    monkeypatch.setitem(app.config, "MATERIAL_S3_REGION", "cn-south-1")
    plaintext = b"confidential procurement specification"
    client = MagicMock()

    with patch("boto3.client", return_value=client):
        object_key = store_material(
            content=plaintext,
            sha256="a" * 64,
            owner_id=12,
            session_id=34,
        )
        uploaded = client.put_object.call_args.kwargs["Body"]
        client.get_object.return_value = {"Body": BytesIO(uploaded)}
        restored = retrieve_material(object_key)

    assert object_key == f"materials/12/34/{'a' * 64}.bin"
    assert plaintext not in uploaded
    assert restored == plaintext
    assert client.put_object.call_args.kwargs["ServerSideEncryption"] == "AES256"
    assert client.put_object.call_args.kwargs["Bucket"] == "private-materials"
