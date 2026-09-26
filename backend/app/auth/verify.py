"""Auth0 JWT verification (INF-5, PRD §12).

RS256, verified against the tenant JWKS. Config is read at call time:
- AUTH_DISABLED=1  -> a fixed dev user (sub 'dev|local'); no token needed.
- AUTH_DISABLED unset/0 and AUTH0_DOMAIN / AUTH0_AUDIENCE missing -> 503 (clear message,
  not a crash), so the app boots even before P4 supplies the tenant values.
- otherwise: Bearer token required; RS256 signature, audience and issuer are all checked.

The JWKS is cached in-process and refetched once on an unknown kid (key rotation).
"""

from __future__ import annotations

import os
import threading
import urllib.request
from dataclasses import dataclass

import jwt
from fastapi import Request

from app.api.errors import ApiError

DEV_USER_SUB = "dev|local"
_JWKS_TIMEOUT = 5.0


@dataclass(frozen=True)
class AuthUser:
    sub: str


def _auth_disabled() -> bool:
    return os.environ.get("AUTH_DISABLED", "").strip() in {"1", "true", "True"}


def _domain() -> str | None:
    d = os.environ.get("AUTH0_DOMAIN", "").strip()
    return d or None


def _audience() -> str | None:
    a = os.environ.get("AUTH0_AUDIENCE", "").strip()
    return a or None


class _JwksCache:
    """Process-wide JWKS cache with a single refetch on an unknown kid."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._keys: dict[str, str] = {}  # kid -> PEM public key
        self._url: str | None = None

    def _fetch(self, url: str) -> dict[str, str]:
        with urllib.request.urlopen(url, timeout=_JWKS_TIMEOUT) as resp:  # noqa: S310 (trusted issuer URL)
            data = resp.read()
        jwks = jwt.PyJWKSet.from_json(data.decode("utf-8"))
        return {k.key_id: k.key for k in jwks.keys if k.key_id}

    def get_key(self, url: str, kid: str) -> str:
        with self._lock:
            if url != self._url:
                self._keys = {}
                self._url = url
            if kid in self._keys:
                return self._keys[kid]
            # Unknown kid: refetch once (handles rotation and a cold cache).
            self._keys = self._fetch(url)
            self._url = url
            key = self._keys.get(kid)
        if key is None:
            raise ApiError(401, "UNAUTHORIZED", "Unknown token signing key")
        return key


_jwks = _JwksCache()


def _bearer_token(request: Request) -> str:
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise ApiError(401, "UNAUTHORIZED", "Missing or malformed Authorization header")
    return token.strip()


def verify_token(token: str) -> AuthUser:
    """Verify an RS256 Auth0 token; raise ApiError on any failure."""
    domain, audience = _domain(), _audience()
    if not domain or not audience:
        raise ApiError(503, "AUTH_NOT_CONFIGURED", "Authentication is not configured on the server")
    issuer = f"https://{domain}/"
    jwks_url = f"https://{domain}/.well-known/jwks.json"
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError:
        raise ApiError(401, "UNAUTHORIZED", "Malformed token")
    kid = header.get("kid")
    if not kid:
        raise ApiError(401, "UNAUTHORIZED", "Token has no key id")
    public_key = _jwks.get_key(jwks_url, kid)
    try:
        claims = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience=audience,
            issuer=issuer,
        )
    except jwt.PyJWTError as exc:
        raise ApiError(401, "UNAUTHORIZED", f"Invalid token: {exc}")
    sub = claims.get("sub")
    if not sub:
        raise ApiError(401, "UNAUTHORIZED", "Token has no subject")
    return AuthUser(sub=sub)


def current_user(request: Request) -> AuthUser:
    """FastAPI dependency for project routes."""
    if _auth_disabled():
        return AuthUser(sub=DEV_USER_SUB)
    return verify_token(_bearer_token(request))
