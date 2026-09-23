import io

from app import db
from app.models import Enterprise, MatchFeedback
from app.applications.enterprise.services.deepseek_service import DeepSeekProfileService


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


def test_clip_match_requires_login(client):
    resp = client.post(
        "/api/clip-match",
        data={"image": (io.BytesIO(b"not an image"), "sample.jpg")},
        content_type="multipart/form-data",
    )

    assert resp.status_code == 401


def test_assets_endpoint_does_not_invent_enterprise_facts(client, test_enterprise):
    _login(client, test_enterprise)
    test_enterprise.business_scope = None
    test_enterprise.credit_score = None
    db.session.commit()

    resp = client.get("/api/user/assets")

    assert resp.status_code == 200
    assets = resp.get_json()["assets"]
    assert assets["is_certified"] is False
    assert assets["patent_count"] == 0
    assert assets["qualifications"] == []
    assert assets["data_auth"] == []
    assert assets["team_members"] == []
    assert assets["credit_breakdown"] == []
    assert assets["credit_score"] is None
    assert assets["industry_tag"] == "未登记"


def test_profile_card_does_not_invent_credit_score(client, test_enterprise):
    test_enterprise.credit_score = None
    db.session.commit()
    _login(client, test_enterprise)

    response = client.get(f"/api/enterprise/{test_enterprise.id}/profile-mini")
    assert response.status_code == 200
    assert response.get_json()["enterprise"]["credit_score"] is None


def test_new_enterprise_has_no_unverified_credit_or_capacity_defaults(_db):
    enterprise = Enterprise(name="未评级企业", role="enterprise")
    db.session.add(enterprise)
    db.session.flush()

    assert enterprise.credit_score is None
    assert enterprise.capacity is None


def test_credit_and_fulfillment_views_keep_missing_score_unknown(client, test_enterprise):
    test_enterprise.credit_score = None
    db.session.commit()
    _login(client, test_enterprise)

    credit_response = client.get(f"/api/credit/score/{test_enterprise.id}")
    assert credit_response.status_code == 200
    credit_body = credit_response.get_json()
    assert credit_body["credit_score"] is None
    assert credit_body["level"] == "未公开"

    fulfillment_response = client.get("/fulfillment/api/dashboard-data")
    assert fulfillment_response.status_code == 200
    assert fulfillment_response.get_json()["current_score"] is None


def test_fulfillment_backflow_is_not_available_to_enterprise_sessions(client, test_enterprise):
    _login(client, test_enterprise)
    response = client.post(
        "/fulfillment/api/backflow",
        json={
            "collaboration_code": "unauthorized",
            "invoice_info": {"verified": True},
            "buyer_id": test_enterprise.id,
            "seller_id": test_enterprise.id + 1,
        },
    )
    assert response.status_code == 403


def test_favorites_do_not_label_credit_score_as_match_score(client, test_enterprise, test_supplier):
    test_enterprise.extras = {"favorites": [test_supplier.id]}
    db.session.commit()
    _login(client, test_enterprise)

    resp = client.get("/api/favorites")

    assert resp.status_code == 200
    favorite = resp.get_json()["favorites"][0]
    assert favorite["match"] is None
    assert favorite["match_score"] is None

    db.session.add(
        MatchFeedback(
            buyer_id=test_enterprise.id,
            supplier_id=test_supplier.id,
            match_score=87.5,
        )
    )
    db.session.commit()
    resp = client.get("/api/favorites")
    favorite = resp.get_json()["favorites"][0]
    assert favorite["match"] == "88%"
    assert favorite["match_score"] == 87.5


def test_favorites_do_not_invent_missing_credit_score(client, test_enterprise, test_supplier):
    test_supplier.credit_score = None
    test_enterprise.extras = {"favorites": [test_supplier.id]}
    db.session.commit()
    _login(client, test_enterprise)

    response = client.get("/api/favorites")

    assert response.status_code == 200
    assert response.get_json()["favorites"][0]["credit_score"] is None


def test_enterprise_profile_uses_current_orders_for_capacity_truth(test_enterprise):
    test_enterprise.capacity = 200
    test_enterprise.current_orders = 50
    test_enterprise.max_capacity = 200

    profile = DeepSeekProfileService().generate_public_profile(test_enterprise.id)

    assert profile["capacity_usage"] == "25%"
    assert profile["capacity_status"] == "产能充裕"


def test_enterprise_profile_does_not_invent_live_capacity(test_enterprise):
    test_enterprise.current_orders = None
    test_enterprise.max_capacity = None

    profile = DeepSeekProfileService().generate_public_profile(test_enterprise.id)

    assert profile["capacity_usage"] == "未公开"
    assert profile["capacity_status"] == "未公开"


def test_assets_do_not_upgrade_incomplete_records_to_verified_facts(client, test_enterprise):
    _login(client, test_enterprise)
    test_enterprise.qualifications = [{"title": "某资质"}]
    test_enterprise.data_auth = [{"name": "外部系统"}]
    db.session.commit()

    response = client.get("/api/user/assets")
    assert response.status_code == 200
    assets = response.get_json()["assets"]
    assert assets["qualifications"] == [{"title": "某资质", "date": "日期未登记", "status": "未核验"}]
    assert assets["data_auth"] == [{"name": "外部系统", "status": "未连接", "data": "授权数据"}]


def test_rag_ingest_rejects_infected_pdf_before_parser(client, test_enterprise):
    _login(client, test_enterprise)

    resp = client.post(
        "/api/rag/ingest",
        data={
            "file": (
                io.BytesIO(b"%PDF-1.4\nEICAR-STANDARD-ANTIVIRUS-TEST-FILE"),
                "sample.pdf",
            )
        },
        content_type="multipart/form-data",
    )

    assert resp.status_code == 400
    assert "安全扫描" in resp.get_json()["error"]


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
