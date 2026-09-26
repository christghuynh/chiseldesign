"""INF-6: SQLite store + projects API.

These tests never touch the network. AUTH_DISABLED=1 (autouse) uses the fixed dev user,
and DATABASE_PATH points at a per-test tmp file so nothing leaks between tests.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import ProjectDetail, ProjectSummary

client = TestClient(app)

SPEC = client.post("/api/generate", json={"template": "ramp", "params": {}}).json()["spec"]


@pytest.fixture(autouse=True)
def _isolated_env(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTH_DISABLED", "1")
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    yield


def test_create_add_versions_and_fetch_each():
    created = client.post("/api/projects", json={"name": "Grandma's ramp", "spec": SPEC})
    assert created.status_code == 200
    pid = created.json()["id"]

    # A fresh project has version 1 (the initial spec, source 'manual').
    detail = ProjectDetail.model_validate(client.get(f"/api/projects/{pid}").json())
    assert [v.n for v in detail.versions] == [1]
    assert detail.versions[0].source == "manual"
    assert detail.name == "Grandma's ramp"

    # Add two more versions.
    v2 = client.post(f"/api/projects/{pid}/versions", json={"spec": SPEC, "source": "edit"})
    v3 = client.post(f"/api/projects/{pid}/versions", json={"spec": SPEC, "source": "fix"})
    assert v2.json()["n"] == 2 and v3.json()["n"] == 3

    detail = ProjectDetail.model_validate(client.get(f"/api/projects/{pid}").json())
    assert [(v.n, v.source) for v in detail.versions] == [(1, "manual"), (2, "edit"), (3, "fix")]

    # Fetch a specific version n.
    r = client.get(f"/api/projects/{pid}/versions/2")
    assert r.status_code == 200
    assert r.json()["spec"]["template"] == "ramp"


def test_list_shows_created_projects():
    client.post("/api/projects", json={"name": "One", "spec": SPEC})
    client.post("/api/projects", json={"name": "Two", "spec": SPEC})
    summaries = [ProjectSummary.model_validate(s) for s in client.get("/api/projects").json()]
    assert {s.name for s in summaries} == {"One", "Two"}
    assert all(s.template == "ramp" for s in summaries)


def test_missing_version_is_404():
    pid = client.post("/api/projects", json={"name": "P", "spec": SPEC}).json()["id"]
    r = client.get(f"/api/projects/{pid}/versions/99")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


def test_owner_only_a_foreign_project_is_404():
    """A different user's project id resolves to 404 (existence is not revealed)."""
    # User A (the default dev user) creates a project.
    pid = client.post("/api/projects", json={"name": "Private", "spec": SPEC}).json()["id"]

    # Switch to a different auth0 sub via a dependency override (keyed by the real dependency object).
    from app.auth.verify import AuthUser, current_user

    app.dependency_overrides[current_user] = lambda: AuthUser(sub="auth0|other")
    try:
        r = client.get(f"/api/projects/{pid}")
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "NOT_FOUND"
        # And user B sees an empty project list, not user A's project.
        assert client.get("/api/projects").json() == []
    finally:
        app.dependency_overrides.clear()
