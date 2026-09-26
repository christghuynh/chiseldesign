"""Builds the combined JSON Schema for every contract model.

Run via `make types` (which calls backend/scripts/generate_schema.py). The output in
shared/schema/ is generated: never hand-edit it.
"""

import json
from pathlib import Path

from pydantic.json_schema import models_json_schema

from app import models

REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_PATH = REPO_ROOT / "shared" / "schema" / "contracts.schema.json"


def contract_models() -> list[type[models.Contract]]:
    """Every exported model except the shared base class, in a stable order."""
    return [getattr(models, name) for name in sorted(models.__all__) if name != "Contract"]


def _strip_field_titles(node: object) -> None:
    """Drop the auto-generated "title" from every field schema.

    Pydantic titles every property ("Cut Notes", "Id"). json-schema-to-typescript turns each
    one into a named alias (`CutNotes1`, `Label2`), which makes the generated TS unreadable.
    A string-valued "title" is a schema keyword; a dict-valued one is a property called "title".
    """
    if isinstance(node, dict):
        if isinstance(node.get("title"), str):
            del node["title"]
        for value in node.values():
            _strip_field_titles(value)
    elif isinstance(node, list):
        for item in node:
            _strip_field_titles(item)


def build_schema() -> dict:
    _, schema = models_json_schema(
        [(m, "serialization") for m in contract_models()],
        title="SketchBuildContracts",
    )
    for name, definition in schema["$defs"].items():
        for prop in definition.get("properties", {}).values():
            _strip_field_titles(prop)
        # Keep each model's own title (the type name) but nothing below it.
        definition["title"] = name
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    return schema


def render_schema() -> str:
    """Deterministic text form (sorted keys, LF endings, trailing newline)."""
    return json.dumps(build_schema(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
