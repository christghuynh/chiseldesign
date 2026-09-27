"""The engine: turns template parameters into parts, rule checks and a priced plan.

This is the entry point other areas call (the `/edit`, `/instructions` and export routes, all
owned by other people). **The signatures below are a contract**: any change to a signature or to these
exceptions must be announced.

Pipeline: validate params -> template `derive` -> template `generate_parts` -> cut-list labeling ->
rule checks -> priced plan. Everything is deterministic: the same params give byte-identical output.
"""

from typing import Any

from app import cutlist, plan as plan_builder, rules, templates
from app.engine_errors import ParamValidationError, TemplateError  # noqa: F401  (public: engine.TemplateError)
from app.models import ParamValue, Plan, SkeletonStep, Spec, TemplateInfo


def _plain(params: dict[str, ParamValue]) -> dict[str, Any]:
    return {name: value.value for name, value in params.items()}


def _spec_params(model: Any, provided: dict[str, ParamValue]) -> dict[str, ParamValue]:
    """Every parameter the template has, in the template's own order.

    A value the caller gave keeps its source and confidence; anything else is a `default`. Parameters
    whose value is null (for example no site length limit) are left out: a null cannot be a ParamValue,
    and leaving it out means "default" when the spec is regenerated.
    """
    result: dict[str, ParamValue] = {}
    for name in type(model).model_fields:
        value = getattr(model, name)
        if value is None:
            continue
        given = provided.get(name)
        if given is not None:
            result[name] = ParamValue(value=value, source=given.source, confidence=given.confidence)
        else:
            result[name] = ParamValue(value=value, source="default")
    return result


def generate(template: str, params: dict[str, ParamValue], meta: dict[str, Any] | None = None) -> tuple[Spec, Plan]:
    """Validate params, compute parts + rule_checks + plan.

    Raises TemplateError (unknown template) or ParamValidationError (a value is missing, unknown or out of
    bounds). `meta` is stored on the spec as given; `meta["contractor_quote_cad"]` feeds the plan's savings.
    """
    module = templates.get_template(template)
    model = templates.validate_params(template, _plain(params))
    derived = module.derive(model)
    parts = cutlist.label_parts(module.generate_parts(model))
    checks = rules.check_design(template, model, derived, parts)
    spec_meta = dict(meta or {})
    # Key numbers for the UI (optional template hook), recomputed on every call so a stale summary
    # posted back in `meta` never survives.
    spec_meta.pop("summary", None)
    if hasattr(module, "summarize"):
        spec_meta["summary"] = module.summarize(model, derived)
    plan = plan_builder.build_plan(parts, spec_meta)
    spec_params = _spec_params(model, params)
    assumed = [name for name, value in spec_params.items() if value.source in ("inferred", "default")]
    spec = Spec(template=template, params=spec_params, assumed=assumed, parts=parts, rule_checks=checks, meta=spec_meta)
    return spec, plan


def get_skeleton(spec: Spec) -> list[SkeletonStep]:
    """Deterministic build-step outline from the template (input to /instructions)."""
    module = templates.get_template(spec.template)
    model = templates.validate_params(spec.template, _plain(spec.params))
    return module.build_skeleton(model, spec.parts)


def list_templates() -> list[TemplateInfo]:
    """Every template the engine can build: key, name, description, params JSON Schema and defaults.

    The parameter panel, the parse prompt and the edit tools all read template schemas, defaults
    and bounds from here rather than importing template modules.
    """
    return templates.template_infos()
