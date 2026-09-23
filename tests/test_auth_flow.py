from app import db
from app.models import Enterprise


def _enterprise(name="已审核企业", password="test123456", status="approved"):
    item = Enterprise(
        name=name,
        role="enterprise",
        verification_status=status,
        is_verified=status == "approved",
    )
    item.set_password(password)
    db.session.add(item)
    db.session.commit()
    return item


def test_login_returns_session_contract_and_preserves_safe_next(client, _db):
    user = _enterprise()

    response = client.post(
        "/auth/login?next=/dashboard",
        data={"name": user.name, "password": "test123456"},
        headers={"X-Login-Modal": "1"},
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "redirect": "/dashboard",
        "role": "enterprise",
    }

    session = client.get("/api/session")
    assert session.status_code == 200
    assert session.get_json()["authenticated"] is True
    assert session.get_json()["user"]["id"] == user.id


def test_login_rejects_external_next(client, _db):
    user = _enterprise()

    response = client.post(
        "/auth/login?next=https://evil.example/steal",
        data={"name": user.name, "password": "test123456"},
        headers={"X-Login-Modal": "1"},
    )

    assert response.status_code == 200
    assert response.get_json()["redirect"] == "/"


def test_login_reports_pending_and_rejected_accounts_without_creating_session(client, _db):
    pending = _enterprise("待审核企业", status="pending")
    rejected = _enterprise("已驳回企业", status="rejected")
    rejected.rejection_reason = "材料不完整"
    db.session.commit()

    pending_response = client.post(
        "/auth/login",
        data={"name": pending.name, "password": "test123456"},
        headers={"X-Login-Modal": "1"},
    )
    assert pending_response.status_code == 403
    assert "等待管理员审核" in pending_response.get_json()["error"]
    assert client.get("/api/session").get_json()["authenticated"] is False

    rejected_response = client.post(
        "/auth/login",
        data={"name": rejected.name, "password": "test123456"},
        headers={"X-Login-Modal": "1"},
    )
    assert rejected_response.status_code == 403
    assert "材料不完整" in rejected_response.get_json()["error"]
    assert client.get("/api/session").get_json()["authenticated"] is False


def test_post_logout_is_available_on_auth_namespace_and_clears_session(client, _db):
    user = _enterprise()
    login = client.post(
        "/auth/login",
        data={"name": user.name, "password": "test123456"},
        headers={"X-Login-Modal": "1"},
    )
    assert login.status_code == 200
    assert client.get("/api/session").get_json()["authenticated"] is True

    response = client.post("/auth/logout", headers={"X-Login-Modal": "1"})

    assert response.status_code == 200
    assert response.get_json() == {"ok": True}
    assert client.get("/api/session").get_json()["authenticated"] is False


def test_login_rejects_blank_credentials_without_database_error(client, _db):
    response = client.post(
        "/auth/login",
        data={"name": "   ", "password": ""},
        headers={"X-Login-Modal": "1"},
    )

    assert response.status_code == 400
    assert response.get_json()["ok"] is False
