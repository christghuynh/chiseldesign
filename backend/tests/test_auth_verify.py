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
