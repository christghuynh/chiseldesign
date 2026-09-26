"""AI-9: a demo cache for parse results, keyed by the sha256 of the raw uploaded bytes.

Files live at `fixtures/demo/<sha256>.json` and hold a serialized `ParseResponse`. The route
checks the cache before any AI call, so the demo sketch parses instantly and identically every
time (and without spending quota). `evals/cache_demo.py <image>` runs one real parse and writes
the file.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path

from app.config import settings
from app.models import ParseResponse

log = logging.getLogger("app.ai")


def demo_dir() -> Path:
    override = os.environ.get("DEMO_CACHE_DIR", "").strip()
    base = Path(override) if override else settings.fixtures_dir / "demo"
    return base


def sha256_hex(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def cache_path(raw: bytes) -> Path:
    return demo_dir() / f"{sha256_hex(raw)}.json"


def lookup(raw: bytes) -> ParseResponse | None:
    """Return the cached ParseResponse for these exact bytes, or None."""
    path = cache_path(raw)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        response = ParseResponse.model_validate(data)
        log.info("parse: demo cache hit %s", path.name)
        return response
    except (OSError, ValueError) as exc:
        log.info("parse: demo cache file %s is unusable (%s)", path.name, exc)
        return None


def store(raw: bytes, response: ParseResponse) -> Path:
    """Write a ParseResponse to the demo cache for these bytes and return the path."""
    path = cache_path(raw)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(response.model_dump(mode="json"), indent=2), encoding="utf-8")
    return path
