from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_request_id_is_returned_and_invalid_input_is_replaced():
    supplied = str(uuid4())
    response = client.get("/health", headers={"X-Request-ID": supplied})
    assert response.headers["x-request-id"] == supplied

    response = client.get("/health", headers={"X-Request-ID": "not-a-uuid"})
    assert response.headers["x-request-id"] != "not-a-uuid"
    assert len(response.headers["x-request-id"]) == 36


def test_request_log_is_correlated_and_omits_query_values(caplog):
    supplied = str(uuid4())
    with caplog.at_level("INFO", logger="app.http"):
        client.get("/health?private=value", headers={"X-Request-ID": supplied})

    record = next(record for record in caplog.records if record.name == "app.http")
    assert record.request_id == supplied
    assert record.path == "/health"
    assert record.duration_ms >= 0
    assert "private=value" not in record.getMessage()


def test_readiness_reports_database_health(monkeypatch):
    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, _query):
            return None

    monkeypatch.setattr("app.main.engine.connect", lambda: Connection())
    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["checks"]["database"] == "healthy"


def test_readiness_fails_without_exposing_dependency_error(monkeypatch):
    def fail_connect():
        raise RuntimeError("private database connection string")

    monkeypatch.setattr("app.main.engine.connect", fail_connect)
    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    assert response.json()["checks"]["database"] == "unavailable"
    assert "private" not in response.text


# FILE PURPOSE:
# Verifies request correlation headers and readiness responses without
# leaking internal dependency errors to callers.
