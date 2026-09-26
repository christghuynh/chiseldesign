"""The engine: turns template parameters into parts, rule checks and a priced plan.

This is the entry point other areas call (the `/edit`, `/instructions` and export routes, all
owned by other people). **The signatures below are a contract**: the geometry-engine owner
replaces the bodies, and any change to a signature or to these exceptions must be announced.

STUB: the bodies return fixtures until the real engine lands (tasks GEO-2, GEO-7 and GEO-14).
"""

from typing import Any

from app import fixtures
from app.models import ParamValue, Plan, SkeletonStep, Spec, TemplateInfo


class TemplateError(Exception):
    """The template is unknown or cannot be built."""


class ParamValidationError(Exception):
    """A parameter is missing, has the wrong type, or is outside its bounds."""


def generate(template: str, params: dict[str, ParamValue], meta: dict[str, Any] | None = None) -> tuple[Spec, Plan]:
    """Validate params, compute parts + rule_checks + plan.

    Raises TemplateError / ParamValidationError.

    STUB: only the "ramp" template exists, and the fixture is picked by the `layout` param alone
    (`switchback`, otherwise straight). Every other param, and `meta`, is ignored.
    """
    if template != "ramp":
        raise TemplateError(f"Unknown template: {template!r}")
    layout = params.get("layout")
    result = fixtures.ramp_plan("switchback" if layout is not None and layout.value == "switchback" else "straight")
    return result.spec, result.plan


def get_skeleton(spec: Spec) -> list[SkeletonStep]:
    """Deterministic build-step outline from the template (input to /instructions).

    STUB: always returns the straight-ramp outline, whatever the spec.
    """
    return fixtures.ramp_skeleton()


def list_templates() -> list[TemplateInfo]:
    """Every template the engine can build: key, name, description, params JSON Schema and defaults.

    The parameter panel, the parse prompt and the edit tools all read template schemas, defaults
    and bounds from here rather than importing template modules.

    STUB: returns the ramp entry from fixtures/templates.json.
    """
    return fixtures.templates()
