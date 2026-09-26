"""INF-8: one log line per request (method, path, status, latency), never bodies or keys."""

import logging

from fastapi.testclient import TestClient

from app.main import create_app

client = TestClient(create_app())


def test_each_request_logs_method_path_status_and_latency(caplog):
    with caplog.at_level(logging.INFO, logger="app.request"):
        client.get("/api/health")
        client.get("/api/nope")
    lines = [r.getMessage() for r in caplog.records if r.name == "app.request"]
    assert len(lines) == 2
    assert lines[0].startswith("GET /api/health status=200 latency_ms=")
    assert lines[1].startswith("GET /api/nope status=404 latency_ms=")


def test_request_bodies_are_never_logged(caplog):
    secret = "measurement-blob-that-must-not-appear"
    with caplog.at_level(logging.INFO, logger="app.request"):
        client.post("/api/generate", json={"template": "ramp", "params": {"total_rise_in": {"value": 15, "source": "user"}}, "meta": {"note": secret}})
    lines = [r.getMessage() for r in caplog.records if r.name == "app.request"]
    assert lines == [lines[0]] and lines[0].startswith("POST /api/generate status=200")
    assert all(secret not in r.getMessage() for r in caplog.records)


def test_app_loggers_emit_info_without_extra_configuration():
    # uvicorn doesn't configure `app.*`; the middleware setup must, or INFO lines vanish in prod.
    app_log = logging.getLogger("app")
    assert app_log.handlers
    assert logging.getLogger("app.ai").getEffectiveLevel() <= logging.INFO
    assert logging.getLogger("app.request").getEffectiveLevel() <= logging.INFO
