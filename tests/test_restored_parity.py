import io

from app import db
from app.models import Enterprise


def _login(client, user):
    with client.session_transaction() as session:
        session["_user_id"] = str(user.id)
        session["_fresh"] = True


def _login_id(client, user_id):
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True


def test_rag_ingest_requires_login(client):
    resp = client.post(
        "/api/rag/ingest",
        data={"file": (io.BytesIO(b"%PDF-1.4\n"), "sample.pdf")},
        content_type="multipart/form-data",
    )

    assert resp.status_code == 401


def test_rag_ingest_rejects_non_pdf(client, test_enterprise):
    _login(client, test_enterprise)

    resp = client.post(
        "/api/rag/ingest",
        data={"file": (io.BytesIO(b"not a pdf"), "sample.txt")},
        content_type="multipart/form-data",
    )

    assert resp.status_code == 400
    assert "PDF" in resp.get_json()["error"]


def test_rag_ingest_calls_service_for_authenticated_pdf(client, test_enterprise, monkeypatch, tmp_path, app):
    app.config["UPLOAD_FOLDER"] = str(tmp_path / "uploads")
    _login(client, test_enterprise)

    calls = []

    def fake_ingest_pdf(file_path, persist_directory):
        calls.append((file_path, persist_directory))
        return {
            "file_path": file_path,
            "pages": 1,
            "chunks": 2,
            "inserted_ids": 2,
            "persist_directory": persist_directory,
            "collection_name": "pdf_knowledge",
            "embedding_model": "mock",
        }

    monkeypatch.setattr("app.routes.rag._import_rag_service", lambda: fake_ingest_pdf)

    resp = client.post(
        "/api/rag/ingest",
        data={"file": (io.BytesIO(b"%PDF-1.4\n"), "sample.pdf")},
        content_type="multipart/form-data",
    )

    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["ok"] is True
    assert payload["data"]["chunks"] == 2
    assert calls


def test_rag_clear_rejects_government_user(app, _db, tmp_path):
    app.config["RAG_CHROMA_DIR"] = str(tmp_path / "chroma")
    government = Enterprise(name="RAG测试政府", role="government")
    government.set_password("gov123456")
    db.session.add(government)
    db.session.commit()
    government_id = government.id

    gov_client = app.test_client()
    _login_id(gov_client, government_id)
    gov_resp = gov_client.post("/api/rag/clear")
    assert gov_resp.status_code == 403


def test_rag_clear_allows_admin_user(app, _db, tmp_path):
    app.config["RAG_CHROMA_DIR"] = str(tmp_path / "chroma")
    admin = Enterprise(name="RAG测试管理员", role="admin")
    admin.set_password("admin123456")
    db.session.add(admin)
    db.session.commit()
    admin_id = admin.id

    admin_client = app.test_client()
    _login_id(admin_client, admin_id)
    admin_resp = admin_client.post("/api/rag/clear")
    assert admin_resp.status_code == 200
    assert admin_resp.get_json()["ok"] is True


def test_wechat_test_email_requires_login(client):
    resp = client.post("/api/wechat/test-email")

    assert resp.status_code == 401


def test_wechat_test_email_requires_saved_email(client, test_enterprise):
    _login(client, test_enterprise)

    resp = client.post("/api/wechat/test-email")

    assert resp.status_code == 400
    assert "邮箱" in resp.get_json()["message"]


def test_wechat_test_email_sends_to_saved_email(client, test_enterprise, monkeypatch):
    _login(client, test_enterprise)
    test_enterprise.extras = {"email": "ops@example.com"}
    db.session.add(test_enterprise)
    db.session.commit()
    sent = []

    def fake_send_email(to_email, subject, body, html_body=None):
        sent.append((to_email, subject, body, html_body))
        return True, "ok"

    monkeypatch.setattr("app.services.email_service.send_email", fake_send_email)

    resp = client.post("/api/wechat/test-email")

    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["success"] is True
    assert "ops@example.com" in payload["message"]
    assert sent and sent[0][0] == "ops@example.com"
