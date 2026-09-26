"""AI-3 / AI-4 / AI-9 / AI-10 / INF-8: POST /parse.

Multipart: `image` (required), `measurements` (optional JSON string), `note` (optional).

Flow: rate limit (per IP) -> read bytes -> demo-cache lookup on the *raw* bytes (before any AI
call) -> validate + resize the image (INF-8) -> Gemini parse (AI-3) -> ParseResponse. Failures:
Gemini invalid output (after one retry) -> 502 PARSE_FAILED (tell the UI to pick a template);
Gemini unavailable/timeout -> 503 AI_UNAVAILABLE.

The AI never computes dimensions, quantities or prices.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.ai import parse as parse_pipeline
from app.ai import parsecache
from app.ai.client import AIUnavailable
from app.ai.imageprep import ImageTooLarge, UnsupportedImage, prepare_image
from app.ai.parse import ParseError
from app.ai.ratelimit import rate_limit
from app.api.errors import ApiError
from app.models import ParseResponse

router = APIRouter()


def _parse_measurements_json(raw: str | None) -> dict | None:
    if raw is None or not raw.strip():
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ApiError(400, "BAD_REQUEST", f"measurements is not valid JSON: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise ApiError(400, "BAD_REQUEST", "measurements must be a JSON object.")
    return data


@router.post("/parse", response_model=ParseResponse, dependencies=[Depends(rate_limit)])
async def parse(
    image: UploadFile = File(...),
    measurements: str | None = Form(None),
    note: str | None = Form(None),
) -> ParseResponse:
    measurements_obj = _parse_measurements_json(measurements)
    raw = await image.read()

    # Demo cache: keyed by the raw uploaded bytes, checked before any AI call.
    cached = parsecache.lookup(raw)
    if cached is not None:
        return cached

    # INF-8: validate the real bytes (not just content-type), cap size, apply EXIF, resize to JPEG.
    try:
        prepared = prepare_image(raw, image.content_type)
    except ImageTooLarge as exc:
        raise ApiError(413, "PAYLOAD_TOO_LARGE", str(exc)) from exc
    except UnsupportedImage as exc:
        raise ApiError(415, "UNSUPPORTED_MEDIA_TYPE", str(exc)) from exc

    try:
        return parse_pipeline.parse_image(prepared, "image/jpeg", measurements_obj, note)
    except ParseError as exc:
        raise ApiError(
            502,
            "PARSE_FAILED",
            "Could not read the image automatically. Please pick a template and enter the measurements manually.",
        ) from exc
    except AIUnavailable as exc:
        raise ApiError(
            503,
            "AI_UNAVAILABLE",
            "The parsing service is temporarily unavailable. Please try again in a moment.",
        ) from exc
