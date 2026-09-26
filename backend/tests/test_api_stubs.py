"""The API routes. /generate, /edit and /templates go through the real engine; /parse and /instructions are
still fixture stubs; the rest return 501 in the standard error shape."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import EditResponse, GenerateResponse, InstructionsResponse, ParseResponse, TemplateInfo

client = TestClient(app)


def user(value):
    return {"value": value, "source": "user"}


RAMP_PARAMS = {"total_rise_in": user(15), "available_length_in": user(160)}
SPEC = client.post("/api/generate", json={"template": "ramp", "params": {**RAMP_PARAMS, "layout": user("straight")}}).json()["spec"]


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True and body["version"]


def test_templates_returns_the_registered_templates_with_schemas():
    r = client.get("/api/templates")
    assert r.status_code == 200
    templates = {t["key"]: TemplateInfo.model_validate(t) for t in r.json()}
    assert "ramp" in templates
    assert "total_rise_in" in templates["ramp"].params_schema["properties"]
    assert all(t.params_schema["properties"] and t.defaults is not None for t in templates.values())


def test_generate_a_straight_ramp_that_is_too_long_fails_the_site_fit_rule_with_a_switchback_fix():
    r = client.post("/api/generate", json={"template": "ramp", "params": {**RAMP_PARAMS, "layout": user("straight")}})
    assert r.status_code == 200
    result = GenerateResponse.model_validate(r.json())
    assert result.spec.params["layout"].value == "straight" and result.spec.parts and result.plan.cut_list
    fail = next(c for c in result.spec.rule_checks if c.id == "RAMP-007")
    assert fail.status == "fail" and fail.fix is not None and fail.fix.params_patch == {"layout": "switchback"}


def test_generate_applying_the_fix_gives_a_switchback_that_fits():
    r = client.post("/api/generate", json={"template": "ramp", "params": {**RAMP_PARAMS, "layout": user("switchback")}})
    result = GenerateResponse.model_validate(r.json())
    assert result.spec.params["layout"].value == "switchback"
    assert next(c for c in result.spec.rule_checks if c.id == "RAMP-007").status == "pass"


def test_generate_fills_defaults_and_lists_assumptions():
    r = client.post("/api/generate", json={"template": "ramp", "params": {"total_rise_in": user(12)}})
    result = GenerateResponse.model_validate(r.json())
    assert result.spec.params["clear_width_in"].source == "default" and result.spec.params["total_rise_in"].source == "user"
    assert "clear_width_in" in result.spec.assumed and "total_rise_in" not in result.spec.assumed
    assert result.plan.has_placeholder_prices is True


def test_generate_missing_or_bad_params_are_a_readable_422():
    missing = client.post("/api/generate", json={"template": "ramp", "params": {}})
    assert missing.status_code == 422
    assert missing.json() == {"error": {"code": "INVALID_PARAMS", "message": "total_rise_in is required"}}
    bad = client.post("/api/generate", json={"template": "ramp", "params": {"total_rise_in": user(200)}})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "INVALID_PARAMS"
    assert "total_rise_in" in bad.json()["error"]["message"]


def test_generate_with_an_unknown_template_is_a_readable_422():
    r = client.post("/api/generate", json={"template": "nope", "params": {}})
    assert r.status_code == 422
    assert r.json() == {"error": {"code": "TEMPLATE_ERROR", "message": "Unknown template: 'nope'"}}


def test_parse_accepts_multipart_and_returns_params_without_parts(monkeypatch):
    # AI-3 (Lane A / p3-parse) replaced the F-4 stub: /parse validates the image and calls the
    # (fake) parser. A real PNG is required; the shipped fake returns the ramp reading.
    monkeypatch.setenv("FAKE_AI", "1")
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (120, 90), (40, 50, 60)).save(buf, format="PNG")
    r = client.post(
        "/api/parse",
        files={"image": ("sketch.png", buf.getvalue(), "image/png")},
        data={"measurements": '{"total_rise_in": 15}', "note": "porch"},
    )
    assert r.status_code == 200, r.text
    result = ParseResponse.model_validate(r.json())
    assert result.spec is not None
    assert result.spec.parts == [] and result.spec.rule_checks == []
    # The user measurement (15) overrides the fake reading, so its source is "user".
    assert result.spec.params["total_rise_in"].source == "user"
    assert result.template_confidence == 0.92


def test_parse_requires_an_image():
    r = client.post("/api/parse", data={"note": "no image"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_edit_returns_a_regenerated_spec_and_a_short_message():
    r = client.post("/api/edit", json={"spec": SPEC, "utterance": "make it wider"})
    assert r.status_code == 200
    result = EditResponse.model_validate(r.json())
    assert result.needs_clarification is False and result.message
    assert result.spec.parts and result.plan.cut_list
    # The stub regenerates the posted spec through the engine, so the layout is preserved.
    assert result.spec.params["layout"].value == SPEC["params"]["layout"]["value"]


def test_instructions():
    r = client.post("/api/instructions", json={"spec": SPEC})
    assert r.status_code == 200
    steps = InstructionsResponse.model_validate(r.json()).steps
    # AI-6 rewrites the engine skeleton (the stub skeleton has 10 steps); the shipped fake matches.
    assert len(steps) == 10 and steps[0].n == 1


@pytest.mark.parametrize(
    ("method", "path", "kwargs", "task"),
    [
        # Every route is implemented now: voice (VOX-1/2, test_voice.py), /projects (INF-6,
        # test_projects_api.py) and /export/* (GEO-17/18, test_cad_export.py, test_cutlist_csv.py).
    ],
)
def test_unbuilt_routes_return_501_in_the_standard_error_shape(method, path, kwargs, task):
    r = getattr(client, method)(path, **kwargs)
    assert r.status_code == 501
    assert r.json() == {"error": {"code": "NOT_IMPLEMENTED", "message": f"Not implemented yet (task {task})"}}


def test_unknown_route_uses_the_error_shape():
    r = client.get("/api/nope")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


def test_invalid_body_uses_the_error_shape():
    r = client.post("/api/generate", json={"template": "ramp"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "params" in r.json()["error"]["message"]


def test_cors_allows_the_vite_dev_origin():
    r = client.get("/api/health", headers={"Origin": "http://localhost:5173"})
    assert r.headers["access-control-allow-origin"] == "http://localhost:5173"
