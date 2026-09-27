"""Lane A tests for POST /parse and its helpers: image prep, rate limit, demo cache, failures.

FAKE_AI=1; no network. Real Gemini client is blocked. The rate limiter is reset per test.
"""

from __future__ import annotations

import io
import json

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.ai import client, ratelimit
from app.ai.client import AIUnavailable, fake_responses
from app.ai.imageprep import (
    ImageTooLarge,
    UnsupportedImage,
    prepare_image,
)
from app.main import create_app


@pytest.fixture(autouse=True)
def _fake_ai(monkeypatch):
    monkeypatch.setenv("FAKE_AI", "1")
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.delenv("RATE_LIMIT_PER_MIN", raising=False)
    monkeypatch.delenv("DEMO_CACHE_DIR", raising=False)

    def _refuse(*_a, **_k):
        raise AssertionError("a parse-route test tried to create a real Gemini client")

    monkeypatch.setattr(client, "_client_for", _refuse)
    ratelimit.reset()
    yield
    ratelimit.reset()


@pytest.fixture
def app_client():
    return TestClient(create_app())


def _png(size=(200, 150), color=(120, 130, 140)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


def _jpeg(size=(200, 150)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, (10, 20, 30)).save(buf, format="JPEG")
    return buf.getvalue()


def _webp(size=(200, 150)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, (200, 100, 50)).save(buf, format="WEBP")
    return buf.getvalue()


def _upload(img_bytes, filename="sketch.png", content_type="image/png", **form):
    files = {"image": (filename, img_bytes, content_type)}
    return files, form


# ---------------------------------------------------------------------------------------------
# INF-8 image prep (unit)


def test_prepare_accepts_png_jpeg_webp_and_returns_jpeg():
    for raw in (_png(), _jpeg(), _webp()):
        out = prepare_image(raw)
        assert Image.open(io.BytesIO(out)).format == "JPEG"


def test_prepare_downscales_long_side_to_1600():
    out = prepare_image(_png(size=(4000, 2000)))
    img = Image.open(io.BytesIO(out))
    assert max(img.size) == 1600


def test_prepare_rejects_oversize():
    with pytest.raises(ImageTooLarge):
        prepare_image(b"x" * (10 * 1024 * 1024 + 1))


def test_prepare_rejects_non_image_bytes():
    with pytest.raises(UnsupportedImage):
        prepare_image(b"this is not an image at all")


def _encode(fmt: str, img: Image.Image | None = None, **kw) -> bytes:
    buf = io.BytesIO()
    (img or Image.new("RGB", (320, 240), (200, 100, 50))).save(buf, format=fmt, **kw)
    return buf.getvalue()


@pytest.mark.parametrize("fmt", ["HEIF", "AVIF", "GIF", "BMP", "TIFF"])
def test_prepare_accepts_other_common_formats(fmt):
    # HEIF = the iPhone's HEIC photos (via pillow-heif).
    out = prepare_image(_encode(fmt))
    with Image.open(io.BytesIO(out)) as img:
        assert img.format == "JPEG" and img.size == (320, 240)


def test_transparent_images_go_on_white_not_black():
    sketch = Image.new("RGBA", (100, 100), (0, 0, 0, 0))  # transparent page ...
    sketch.putpixel((50, 50), (0, 0, 0, 255))  # ... with one black ink dot
    with Image.open(io.BytesIO(prepare_image(_encode("PNG", sketch)))) as img:
        assert min(img.getpixel((5, 5))) > 240  # background is white
        assert max(img.getpixel((50, 50))) < 80  # ink stays dark


def test_animated_gif_uses_the_first_frame():
    frames = [Image.new("RGB", (60, 60), c) for c in ((250, 250, 250), (0, 0, 0))]
    raw = _encode("GIF", frames[0], save_all=True, append_images=frames[1:])
    with Image.open(io.BytesIO(prepare_image(raw))) as img:
        assert min(img.getpixel((30, 30))) > 200


def test_prepare_rejects_decodable_but_unsupported_formats():
    with pytest.raises(UnsupportedImage, match="HEIC"):
        prepare_image(_encode("ICO"))


def test_prepare_rejects_non_images():
    with pytest.raises(UnsupportedImage):
        prepare_image(b"%PDF-1.7 not an image")


def test_route_accepts_an_iphone_heic_photo(app_client):
    files, form = _upload(_encode("HEIF"), filename="IMG_0042.HEIC", content_type="image/heic")
    res = app_client.post("/api/parse", files=files, data=form)
    assert res.status_code == 200, res.text


# ---------------------------------------------------------------------------------------------
# AI-3 route happy paths


def test_parse_returns_spec_from_shipped_fake(app_client):
    files, form = _upload(_png())
    res = app_client.post("/api/parse", files=files, data=form)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["spec"]["template"] == "ramp"
    assert body["spec"]["params"]["total_rise_in"]["value"] == 21
    assert body["template_confidence"] == 0.92


def test_parse_user_measurement_overrides_and_quote_in_meta(app_client):
    files, form = _upload(_png())
    form["measurements"] = json.dumps({"total_rise": 15, "contractor_quote": 3500})
    res = app_client.post("/api/parse", files=files, data=form)
    assert res.status_code == 200, res.text
    spec = res.json()["spec"]
    assert spec["params"]["total_rise_in"]["value"] == 15
    assert spec["params"]["total_rise_in"]["source"] == "user"
    assert spec["meta"]["contractor_quote_cad"] == 3500


def test_parse_unknown_object_returns_null_spec(app_client):
    files, form = _upload(_png())
    with fake_responses(
        "parse",
        {"template": None, "template_confidence": 0.1, "params": [], "questions": [], "notes": "A cat."},
    ):
        res = app_client.post("/api/parse", files=files, data=form)
    assert res.status_code == 200
    body = res.json()
    assert body["spec"] is None
    assert "cat" in body["raw_notes"].lower()


def test_parse_rejects_non_image(app_client):
    files, form = _upload(b"not an image", filename="x.png")
    res = app_client.post("/api/parse", files=files, data=form)
    assert res.status_code == 415
    assert res.json()["error"]["code"] == "UNSUPPORTED_MEDIA_TYPE"


def test_parse_rejects_bad_measurements_json(app_client):
    files, form = _upload(_png())
    form["measurements"] = "{not json"
    res = app_client.post("/api/parse", files=files, data=form)
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "BAD_REQUEST"


# ---------------------------------------------------------------------------------------------
# AI-4 failure handling


def test_parse_invalid_output_after_retry_is_502_parse_failed(app_client):
    files, form = _upload(_png())
    bad = {"template": "ramp"}  # missing required fields
    with fake_responses("parse", bad, bad):
        res = app_client.post("/api/parse", files=files, data=form)
    assert res.status_code == 502
    body = res.json()
    assert body["error"]["code"] == "PARSE_FAILED"
    assert "manual" in body["error"]["message"].lower() or "template" in body["error"]["message"].lower()


def test_parse_ai_unavailable_is_503(app_client):
    files, form = _upload(_png())
    with fake_responses("parse", AIUnavailable("down")):
        res = app_client.post("/api/parse", files=files, data=form)
    assert res.status_code == 503
    assert res.json()["error"]["code"] == "AI_UNAVAILABLE"


# ---------------------------------------------------------------------------------------------
# AI-10 rate limit


def test_rate_limit_returns_429_over_the_limit(app_client, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PER_MIN", "2")
    files, form = _upload(_png())
    codes = []
    for _ in range(3):
        f2, d2 = _upload(_png())
        codes.append(app_client.post("/api/parse", files=f2, data=d2).status_code)
    assert codes[:2] == [200, 200]
    assert codes[2] == 429


def test_rate_limit_429_has_the_right_code(app_client, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PER_MIN", "1")
    f1, d1 = _upload(_png())
    app_client.post("/api/parse", files=f1, data=d1)
    f2, d2 = _upload(_png())
    res = app_client.post("/api/parse", files=f2, data=d2)
    assert res.status_code == 429
    assert res.json()["error"]["code"] == "RATE_LIMITED"


# ---------------------------------------------------------------------------------------------
# AI-9 demo cache


def test_demo_cache_is_used_before_any_ai_call(app_client, monkeypatch, tmp_path):
    from app.ai import parsecache
    from app.models import ParseResponse, Spec

    raw = _png(color=(1, 2, 3))
    monkeypatch.setenv("DEMO_CACHE_DIR", str(tmp_path))
    cached = ParseResponse(
        spec=Spec(template="ramp", params={}, assumed=[], meta={}),
        template_confidence=0.5,
        questions=["cached question"],
        raw_notes="from cache",
    )
    parsecache.store(raw, cached)

    # If the cache is used, the AI is never consulted, so a queued outage must not matter.
    with fake_responses("parse", AIUnavailable("should not be called")):
        files = {"image": ("demo.png", raw, "image/png")}
        res = app_client.post("/api/parse", files=files, data={})
    assert res.status_code == 200
    assert res.json()["raw_notes"] == "from cache"


def test_demo_cache_roundtrip(monkeypatch, tmp_path):
    from app.ai import parsecache
    from app.models import ParseResponse

    monkeypatch.setenv("DEMO_CACHE_DIR", str(tmp_path))
    raw = b"\x89PNG-ish-bytes"
    assert parsecache.lookup(raw) is None
    resp = ParseResponse(spec=None, template_confidence=None, questions=[], raw_notes="x")
    path = parsecache.store(raw, resp)
    assert path.exists()
    got = parsecache.lookup(raw)
    assert got is not None and got.raw_notes == "x"
