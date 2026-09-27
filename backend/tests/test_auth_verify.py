"""INF-5: Auth0 JWT verification. No network: a local RSA key and a stubbed JWKS cache.

Covers the four modes: disabled -> dev user; missing token -> 401; auth on but
AUTH0_* missing -> 503; a token signed with a local RSA key -> verifies.
"""

import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from app.auth import verify
from app.auth.verify import DEV_USER_SUB, current_user, verify_token
from app.main import app

client = TestClient(app)
SPEC = client.post("/api/generate", json={"template": "ramp", "params": {"total_rise_in": {"value": 15, "source": "user"}}}).json()["spec"]

DOMAIN = "test-tenant.auth0.com"
AUDIENCE = "https://api.sketchbuild.test"
KID = "test-key-1"

_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _make_token(claims_override=None):
    now = int(time.time())
    claims = {
        "sub": "auth0|abc123",
        "aud": AUDIENCE,
        "iss": f"https://{DOMAIN}/",
        "iat": now,
        "exp": now + 3600,
    }
    if claims_override:
        claims.update(claims_override)
    return jwt.encode(claims, _PRIVATE_KEY, algorithm="RS256", headers={"kid": KID})


@pytest.fixture
def _local_jwks(monkeypatch):
    """Serve the local public key from the JWKS cache without any network call."""
    pem = _PRIVATE_KEY.public_key()
    monkeypatch.setattr(verify._jwks, "get_key", lambda url, kid: pem)
    monkeypatch.setenv("AUTH0_DOMAIN", DOMAIN)
    monkeypatch.setenv("AUTH0_AUDIENCE", AUDIENCE)
    monkeypatch.delenv("AUTH_DISABLED", raising=False)
    yield


def test_disabled_mode_returns_the_dev_user(monkeypatch):
    monkeypatch.setenv("AUTH_DISABLED", "1")

    class _Req:
        headers: dict = {}

    assert current_user(_Req()).sub == DEV_USER_SUB


def test_missing_token_is_401(monkeypatch, tmp_path):
    monkeypatch.setenv("AUTH0_DOMAIN", DOMAIN)
    monkeypatch.setenv("AUTH0_AUDIENCE", AUDIENCE)
    monkeypatch.delenv("AUTH_DISABLED", raising=False)
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "t.db"))
    r = client.get("/api/projects")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "UNAUTHORIZED"


def test_auth_enabled_but_unconfigured_is_503(monkeypatch, tmp_path):
    monkeypatch.delenv("AUTH_DISABLED", raising=False)
    monkeypatch.delenv("AUTH0_DOMAIN", raising=False)
    monkeypatch.delenv("AUTH0_AUDIENCE", raising=False)
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "t.db"))
    r = client.get("/api/projects", headers={"Authorization": "Bearer anything"})
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "AUTH_NOT_CONFIGURED"


def test_valid_local_token_verifies(_local_jwks):
    user = verify_token(_make_token())
    assert user.sub == "auth0|abc123"


def test_wrong_audience_is_rejected(_local_jwks):
    from app.api.errors import ApiError

    with pytest.raises(ApiError) as exc:
        verify_token(_make_token({"aud": "https://someone-else"}))
    assert exc.value.status == 401


def test_valid_token_reaches_the_projects_route(_local_jwks, tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "t.db"))
    r = client.get("/api/projects", headers={"Authorization": f"Bearer {_make_token()}"})
    assert r.status_code == 200
    assert r.json() == []


def _bearer(sub="auth0|abc123", **claims):
    return {"Authorization": f"Bearer {_make_token({'sub': sub, **claims})}"}


def test_deleting_a_project_works_with_a_verified_login_token(_local_jwks, tmp_path, monkeypatch):
    """The whole delete path under real RS256 verification (not the AUTH_DISABLED dev user): the owner's token
    deletes; someone else's valid token gets a 404 and changes nothing; a bad or missing token is a 401."""
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "t.db"))
    mine, theirs = _bearer("auth0|abc123"), _bearer("auth0|someone-else")
    pid = client.post("/api/projects", json={"name": "Ramp", "spec": SPEC}, headers=mine).json()["id"]

    assert client.delete(f"/api/projects/{pid}", headers=theirs).status_code == 404  # another login cannot delete it
    assert client.delete(f"/api/projects/{pid}", headers=_bearer(aud="https://someone-else")).status_code == 401
    assert client.delete(f"/api/projects/{pid}", headers={"Authorization": "Bearer not-a-token"}).status_code == 401
    assert client.delete(f"/api/projects/{pid}").status_code == 401
    assert client.get(f"/api/projects/{pid}", headers=mine).status_code == 200  # all of that left it in place

    deleted = client.delete(f"/api/projects/{pid}", headers=mine)
    assert deleted.status_code == 204 and deleted.content == b""
    assert client.get(f"/api/projects/{pid}", headers=mine).status_code == 404
    assert client.get("/api/projects", headers=mine).json() == []


def test_an_expired_login_cannot_delete(_local_jwks, tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "t.db"))
    pid = client.post("/api/projects", json={"name": "Ramp", "spec": SPEC}, headers=_bearer()).json()["id"]
    now = int(time.time())
    expired = _bearer(iat=now - 7200, exp=now - 3600)
    assert client.delete(f"/api/projects/{pid}", headers=expired).status_code == 401
    assert client.get(f"/api/projects/{pid}", headers=_bearer()).status_code == 200


def test_verify_can_be_imported_before_anything_else():
    """`app.auth.verify` and `app.api` used to import each other, so importing verify first failed (only a full
    test run, which imported the API first, hid it). A fresh interpreter has no such help."""
    import subprocess
    import sys
    from pathlib import Path

    backend = Path(__file__).resolve().parents[1]
    for module in ("app.auth.verify", "app.store.repo", "app.api.errors"):
        done = subprocess.run([sys.executable, "-c", f"import {module}"], cwd=backend, capture_output=True, text=True)
        assert done.returncode == 0, f"import {module} failed:\n{done.stderr[-500:]}"

