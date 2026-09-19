"""Enterprise WeChat callback signature and AES-CBC envelope handling."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import struct
import time

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


class WorkWeChatCryptoError(ValueError):
    """Raised for an invalid or unauthenticated Enterprise WeChat envelope."""


class WorkWeChatCrypto:
    def __init__(self, *, token: str, encoding_aes_key: str, corp_id: str):
        self.token = str(token or "").strip()
        self.corp_id = str(corp_id or "").strip()
        try:
            self.key = base64.b64decode(str(encoding_aes_key or "").strip() + "=", validate=True)
        except Exception as exc:
            raise WorkWeChatCryptoError("invalid_encoding_aes_key") from exc
        if not self.token or not self.corp_id or len(self.key) != 32:
            raise WorkWeChatCryptoError("incomplete_work_wechat_config")

    def signature(self, encrypted: str, timestamp: str, nonce: str) -> str:
        raw = "".join(sorted([self.token, str(timestamp), str(nonce), str(encrypted)]))
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()

    def decrypt(self, encrypted: str, signature: str, timestamp: str, nonce: str) -> str:
        expected = self.signature(encrypted, timestamp, nonce)
        if not hmac.compare_digest(expected, str(signature or "")):
            raise WorkWeChatCryptoError("invalid_signature")
        try:
            ciphertext = base64.b64decode(str(encrypted).encode("ascii"), validate=True)
            decryptor = Cipher(algorithms.AES(self.key), modes.CBC(self.key[:16])).decryptor()
            padded = decryptor.update(ciphertext) + decryptor.finalize()
            raw = self._unpad(padded)
            if len(raw) < 20:
                raise WorkWeChatCryptoError("invalid_plaintext")
            message_length = struct.unpack(">I", raw[16:20])[0]
            message_end = 20 + message_length
            if message_end > len(raw):
                raise WorkWeChatCryptoError("invalid_message_length")
            message = raw[20:message_end]
            receiver = raw[message_end:].decode("utf-8")
            if not hmac.compare_digest(receiver, self.corp_id):
                raise WorkWeChatCryptoError("receiver_mismatch")
            return message.decode("utf-8")
        except WorkWeChatCryptoError:
            raise
        except Exception as exc:
            raise WorkWeChatCryptoError("decrypt_failed") from exc

    def encrypt(
        self,
        plaintext: str,
        *,
        timestamp: str | None = None,
        nonce: str | None = None,
    ) -> dict[str, str]:
        timestamp = str(timestamp or int(time.time()))
        nonce = str(nonce or secrets.token_hex(8))
        message = str(plaintext or "").encode("utf-8")
        raw = os.urandom(16) + struct.pack(">I", len(message)) + message + self.corp_id.encode("utf-8")
        encryptor = Cipher(algorithms.AES(self.key), modes.CBC(self.key[:16])).encryptor()
        encrypted = base64.b64encode(encryptor.update(self._pad(raw)) + encryptor.finalize()).decode("ascii")
        return {
            "encrypted": encrypted,
            "signature": self.signature(encrypted, timestamp, nonce),
            "timestamp": timestamp,
            "nonce": nonce,
        }

    @staticmethod
    def _pad(raw: bytes) -> bytes:
        padding_length = 32 - (len(raw) % 32)
        return raw + bytes([padding_length]) * padding_length

    @staticmethod
    def _unpad(raw: bytes) -> bytes:
        if not raw:
            raise WorkWeChatCryptoError("invalid_padding")
        padding_length = raw[-1]
        if padding_length < 1 or padding_length > 32:
            raise WorkWeChatCryptoError("invalid_padding")
        if raw[-padding_length:] != bytes([padding_length]) * padding_length:
            raise WorkWeChatCryptoError("invalid_padding")
        return raw[:-padding_length]
