from app.services.production_readiness import _agent_schema_ready


def test_healthz_is_public_and_does_not_expose_configuration(client):
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_readyz_reports_database_and_agent_schema(client, app):
    response = client.get("/readyz")

    with app.app_context():
        expected_status = 200 if _agent_schema_ready() else 503
    assert response.status_code == expected_status
    payload = response.get_json()
    assert payload["status"] in {"ready", "not_ready"}
    assert payload["checks"]["database"] == "ok"
    assert payload["checks"]["agent_schema"] in {"ok", "missing"}
    assert "SECRET" not in str(payload).upper()
