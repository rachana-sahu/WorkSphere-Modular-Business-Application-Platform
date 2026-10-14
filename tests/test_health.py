import io
import json
import logging

from fastapi.testclient import TestClient

from app import main
from app.observability import JsonLogFormatter

client = TestClient(main.app)


def test_liveness_does_not_require_database() -> None:
    response = client.get(
        "/api/health/live",
        headers={"X-Request-ID": "health-check-17"},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["x-request-id"] == "health-check-17"


def test_invalid_request_id_is_replaced_with_safe_generated_id() -> None:
    response = client.get("/api/health/live", headers={"X-Request-ID": "bad id\n"})

    assert response.status_code == 200
    assert response.headers["x-request-id"]
    assert response.headers["x-request-id"] != "bad id\n"


def test_request_logs_are_structured_and_correlated() -> None:
    output = io.StringIO()
    handler = logging.StreamHandler(output)
    handler.setFormatter(JsonLogFormatter())
    logger = logging.getLogger("worksphere.http")
    previous_level = logger.level
    previous_disabled = logger.disabled
    logger.setLevel(logging.INFO)
    logger.disabled = False
    logger.addHandler(handler)
    try:
        response = client.get(
            "/api/health/live",
            headers={"X-Request-ID": "log-check-42"},
        )
    finally:
        logger.removeHandler(handler)
        handler.close()
        logger.setLevel(previous_level)
        logger.disabled = previous_disabled
    entries = [json.loads(line) for line in output.getvalue().splitlines()]
    entry = next(
        entry
        for entry in entries
        if entry.get("request_id") == "log-check-42"
        and entry.get("message") == "HTTP request completed"
    )

    assert response.status_code == 200
    assert entry["logger"] == "worksphere.http"
    assert entry["method"] == "GET"
    assert entry["path"] == "/api/health/live"
    assert entry["status_code"] == 200
    assert isinstance(entry["duration_ms"], float)


def test_unexpected_errors_return_safe_message_with_request_id(monkeypatch) -> None:
    def fail_readiness() -> bool:
        raise RuntimeError("private database connection detail")

    monkeypatch.setattr(main, "check_database", fail_readiness)
    test_client = TestClient(main.app, raise_server_exceptions=False)

    response = test_client.get(
        "/api/health/ready",
        headers={"X-Request-ID": "readiness-failure"},
    )

    assert response.status_code == 500
    assert response.headers["x-request-id"] == "readiness-failure"
    assert response.json() == {
        "detail": {
            "code": "internal_error",
            "message": "The request could not be completed due to an internal error.",
        }
    }
    assert "private database connection detail" not in response.text


def test_readiness_succeeds_when_database_is_available(
    monkeypatch,
) -> None:
    monkeypatch.setattr(main, "check_database", lambda: True)

    response = client.get("/api/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_readiness_returns_safe_error_when_database_is_unavailable(
    monkeypatch,
) -> None:
    monkeypatch.setattr(main, "check_database", lambda: False)

    response = client.get("/api/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "detail": {
            "code": "database_unavailable",
            "message": "The database is currently unavailable.",
        }
    }
