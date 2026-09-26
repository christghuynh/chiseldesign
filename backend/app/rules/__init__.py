"""Rule checks. One module per template: `app/rules/<template key>.py` exposes

    check(params, derived, parts) -> list[RuleCheck]

and is found automatically, so adding a template's rules never touches a shared file.
"""

import importlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.models import Part, RuleCheck

SOURCES_PATH = Path(__file__).resolve().parent / "sources.json"


@lru_cache
def sources() -> dict[str, dict[str, Any]]:
    """Citation key -> {title, publisher, url, notes} (placeholders until NC-3)."""
    raw = json.loads(SOURCES_PATH.read_text("utf-8"))
    return {key: value for key, value in raw.items() if not key.startswith("_")}


def check_design(template: str, params: Any, derived: Any, parts: list[Part]) -> list[RuleCheck]:
    """Run the rule checks for a template. A template without a rules module has no checks."""
    try:
        module = importlib.import_module(f"app.rules.{template}")
    except ModuleNotFoundError as exc:
        if exc.name == f"app.rules.{template}":
            return []
        raise
    return module.check(params, derived, parts)
