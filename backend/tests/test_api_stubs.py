"""F-4: the FastAPI skeleton. Real routes return fixtures; the rest return 501 in the standard error shape."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import EditResponse, GenerateResponse, InstructionsResponse, ParseResponse, TemplateInfo

client = TestClient(app)

SPEC = client.post("/api/generate", json={"template": "ramp", "params": {}}).json()["spec"]


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True and body["version"]


def test_templates_returns_the_ramp_schema():
    r = client.get("/api/templates")
    assert r.status_code == 200
    templates = [TemplateInfo.model_validate(t) for t in r.json()]
    assert [t.key for t in templates] == ["ramp"]
    assert "total_rise_in" in templates[0].params_schema["properties"]


def test_generate_defaults_to_the_straight_fixture():
    r = client.post("/api/generate", json={"template": "ramp", "params": {}})
    assert r.status_code == 200
    result = GenerateResponse.model_validate(r.json())
    assert result.spec.params["layout"].value == "straight"
    assert any(c.id == "RAMP-007" and c.status == "fail" for c in result.spec.rule_checks)


def test_generate_returns_the_switchback_fixture_when_asked():
    params = {"layout": {"value": "switchback", "source": "user"}}
    r = client.post("/api/generate", json={"template": "ramp", "params": params})
    result = GenerateResponse.model_validate(r.json())
    assert result.spec.params["layout"].value == "switchback"
    assert next(c for c in result.spec.rule_checks if c.id == "RAMP-007").status == "pass"


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
    assert len(steps) == 11 and steps[0].n == 1


@pytest.mark.parametrize(
    ("method", "path", "kwargs", "task"),
    [
        ("post", "/api/voice/stt", {"files": {"audio": ("a.webm", b"x", "audio/webm")}}, "VOX-1"),
        ("post", "/api/voice/tts", {"json": {"text": "hello"}}, "VOX-2"),
        ("get", "/api/projects", {}, "INF-6"),
        ("post", "/api/projects", {"json": {"name": "p", "spec": SPEC}}, "INF-6"),
        ("get", "/api/projects/1", {}, "INF-6"),
        ("post", "/api/projects/1/versions", {"json": {"spec": SPEC, "source": "edit"}}, "INF-6"),
        ("get", "/api/projects/1/versions/2", {}, "INF-6"),
        ("post", "/api/export/step", {"json": {"spec": SPEC}}, "GEO-17"),
        ("post", "/api/export/stl", {"json": {"spec": SPEC}}, "GEO-17"),
        ("post", "/api/export/cutlist.csv", {"json": {"spec": SPEC}}, "GEO-18"),
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
