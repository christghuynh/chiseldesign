"""Template registry (GEO-2).

Every module in this package that defines `KEY` and a `Params` model is a template and is found
automatically, so adding a template means adding a file, not editing this one. See `ramp.py` for the
interface a template module exposes.
"""

import importlib
import pkgutil
from functools import lru_cache
from types import ModuleType
from typing import Any

from pydantic import BaseModel, ValidationError

from app.engine_errors import ParamValidationError, TemplateError
from app.models import TemplateInfo


@lru_cache
def registry() -> dict[str, ModuleType]:
    found: dict[str, ModuleType] = {}
    for info in pkgutil.iter_modules(__path__):
        module = importlib.import_module(f"{__name__}.{info.name}")
        if hasattr(module, "KEY") and hasattr(module, "Params"):
            found[module.KEY] = module
    return dict(sorted(found.items()))


def get_template(key: str) -> ModuleType:
    try:
        return registry()[key]
    except KeyError:
        raise TemplateError(f"Unknown template: {key!r}") from None


def params_schema(model: type[BaseModel]) -> dict[str, Any]:
    """JSON Schema of a Params model, with nullable fields flattened.

    Pydantic writes `anyOf: [{type: number}, {type: null}]`; this rewrites it as `type: [number, null]`
    so every consumer (the parameter panel, the parse prompt) sees one simple shape per field.
    """
    schema = model.model_json_schema()
    for prop in schema.get("properties", {}).values():
        options = prop.get("anyOf")
        if options and len(options) == 2 and {"type": "null"} in options:
            other = next(o for o in options if o != {"type": "null"})
            del prop["anyOf"]
            prop.update(other)
            prop["type"] = [other["type"], "null"]
    return schema


def defaults_of(model: type[BaseModel]) -> dict[str, Any]:
    """Default value of every field that has one (required fields are left out)."""
    return {name: field.default for name, field in model.model_fields.items() if not field.is_required()}


def template_infos() -> list[TemplateInfo]:
    return [
        TemplateInfo(
            key=key,
            name=module.NAME,
            description=module.DESCRIPTION,
            params_schema=params_schema(module.Params),
            defaults=defaults_of(module.Params),
        )
        for key, module in registry().items()
    ]


def validate_params(key: str, values: dict[str, Any]) -> BaseModel:
    """Build a template's Params from plain values (defaults filled in).

    Raises ParamValidationError with a readable message when a value is missing, unknown, of the
    wrong type or out of bounds.
    """
    model = get_template(key).Params
    try:
        return model.model_validate(values)
    except ValidationError as exc:
        messages = []
        for error in exc.errors():
            name = ".".join(str(part) for part in error["loc"])
            if error["type"] == "missing":
                messages.append(f"{name} is required")
            elif error["type"] == "extra_forbidden":
                messages.append(f"Unknown parameter '{name}'")
            else:
                messages.append(f"{name}: {error['msg']}")
        raise ParamValidationError("; ".join(messages)) from None
