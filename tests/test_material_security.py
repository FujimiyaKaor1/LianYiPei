"""Security tests for the private clamd material scanner."""

from __future__ import annotations

import socket

import pytest

from app.services.material_security import MaterialInfected, scan_material


class _FakeClamdSocket:
    def __init__(self, response: bytes):
        self.response = response
        self.sent: list[bytes] = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def settimeout(self, _timeout):
        return None

    def sendall(self, payload):
        self.sent.append(bytes(payload))

    def recv(self, _size):
        response, self.response = self.response, b""
        return response


def test_material_scan_supports_private_clamd_instream(app, monkeypatch):
    fake = _FakeClamdSocket(b"stream: OK\n")
    monkeypatch.setitem(app.config, "MATERIAL_AV_MODE", "clamav")
    monkeypatch.setitem(app.config, "CLAMAV_HOST", "clamav")
    monkeypatch.setitem(app.config, "CLAMAV_PORT", 3310)
    monkeypatch.setattr(socket, "create_connection", lambda *_args, **_kwargs: fake)

    with app.app_context():
        result = scan_material("purchase.pdf", b"%PDF-1.7\nprocurement")

    assert result["engine"] == "clamav"
    assert fake.sent[0] == b"zINSTREAM\0"
    assert fake.sent[-1] == b"\0\0\0\0"


def test_material_scan_rejects_content_marked_infected_by_clamd(app, monkeypatch):
    fake = _FakeClamdSocket(b"stream: Eicar-Test-Signature FOUND\n")
    monkeypatch.setitem(app.config, "MATERIAL_AV_MODE", "clamav")
    monkeypatch.setitem(app.config, "CLAMAV_HOST", "clamav")
    monkeypatch.setattr(socket, "create_connection", lambda *_args, **_kwargs: fake)

    with app.app_context(), pytest.raises(MaterialInfected):
        scan_material("purchase.pdf", b"%PDF-1.7\nprocurement")

