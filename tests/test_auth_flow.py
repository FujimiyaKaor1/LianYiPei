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


def test_spa_login_switches_to_the_enterprise_named_in_new_credentials(client, _db):
    first = _enterprise("原采购企业")
    second = _enterprise("湖南星瀚精密制造有限公司")

    assert client.post(
        "/auth/login",
        data={"name": first.name, "password": "test123456"},
        headers={"X-Login-Modal": "1"},
    ).status_code == 200

    switched = client.post(
        "/auth/login",
        data={"name": second.name, "password": "test123456"},
        headers={"X-Login-Modal": "1"},
    )

    assert switched.status_code == 200
    assert client.get("/api/session").get_json()["user"]["id"] == second.id


def test_government_account_is_retired(client, _db):
    government = Enterprise(name="历史政府账号", role="government", verification_status="approved")
    government.set_password("gov123456")
    db.session.add(government)
    db.session.commit()

    response = client.post(
        "/auth/login",
        data={"name": government.name, "password": "gov123456"},
        headers={"X-Login-Modal": "1"},
    )

    assert response.status_code == 403
    assert response.get_json()["code"] == "government_portal_removed"
    assert client.get("/api/session").get_json()["authenticated"] is False


def test_admin_and_enterprise_share_the_enterprise_management_flow(client, test_admin, test_enterprise):
    test_enterprise.verification_status = "approved"
    test_enterprise.is_verified = True
    test_admin.verification_status = "approved"
    test_admin.is_verified = True
    db.session.commit()
    enterprise_client = client
    enterprise_login = enterprise_client.post(
        "/auth/login",
        data={"name": test_enterprise.name, "password": "test123456"},
        headers={"X-Login-Modal": "1"},
    )
    assert enterprise_login.status_code == 200
    assert enterprise_client.get("/api/user/me").get_json()["id"] == test_enterprise.id
    assert enterprise_client.get("/admin/api/verifications").status_code == 403

    enterprise_client.post("/auth/logout", headers={"X-Login-Modal": "1"})
    admin_client = enterprise_client
    admin_login = admin_client.post(
        "/auth/login",
        data={"name": test_admin.name, "password": "admin123456"},
        headers={"X-Login-Modal": "1"},
    )
    assert admin_login.status_code == 200
    assert admin_login.get_json()["redirect"] == "/admin/dashboard"
    verification_data = admin_client.get("/admin/api/verifications?status=all").get_json()
    assert any(item["id"] == test_enterprise.id for item in verification_data["items"])
    assert admin_client.get("/gov").status_code == 404
