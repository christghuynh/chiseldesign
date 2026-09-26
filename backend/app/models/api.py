"""Request/response payloads for the API.

These are additions to the core models in core.py so the frontend client can be
typed end to end. Multipart bodies (`/parse`, `/voice/stt`) have no JSON request model.
Field types that weren't specified up front (project ids, timestamps, thumbnails) are listed in
foundation.md under "Decisions to confirm".
"""

from typing import Any, Literal

from app.models.core import (
    BuildStep,
    Contract,
    ParamValue,
    Plan,
    Spec,
)


class HealthResponse(Contract):
    ok: bool
    version: str


class ErrorBody(Contract):
    code: str
    message: str


class ErrorResponse(Contract):
    error: ErrorBody


class TemplateInfo(Contract):
    key: str
    name: str
    description: str
    params_schema: dict[str, Any]  # JSON Schema of the template's Params
    defaults: dict[str, Any]


class ParseResponse(Contract):
    spec: Spec | None  # params + assumed, no parts yet; null when the image isn't a supported object
    # (the reason goes in raw_notes and the UI offers to pick a template manually)
    template_confidence: float | None
    questions: list[str]
    raw_notes: str


class GenerateRequest(Contract):
    template: str
    params: dict[str, ParamValue]
    meta: dict[str, Any] = {}


class GenerateResponse(Contract):
    spec: Spec
    plan: Plan


class EditRequest(Contract):
    spec: Spec
    utterance: str


class EditResponse(Contract):
    spec: Spec
    plan: Plan
    patch: dict[str, Any]
    message: str  # <= 1 sentence, spoken
    needs_clarification: bool


class InstructionsRequest(Contract):
    spec: Spec


class InstructionsResponse(Contract):
    steps: list[BuildStep]


class SttResponse(Contract):
    text: str


class TtsRequest(Contract):
    text: str


class ProjectSummary(Contract):
    id: int
    name: str
    template: str
    updated_at: str  # ISO 8601
    thumb: str | None  # PNG data URL


class ProjectCreateRequest(Contract):
    name: str
    spec: Spec


class ProjectCreateResponse(Contract):
    id: int


class VersionInfo(Contract):
    n: int
    created_at: str  # ISO 8601
    source: Literal["parse", "edit", "manual", "fix"]


class ProjectDetail(Contract):
    id: int
    name: str
    versions: list[VersionInfo]
    latest: Spec


class VersionCreateRequest(Contract):
    spec: Spec
    source: Literal["parse", "edit", "manual", "fix"]


class VersionCreateResponse(Contract):
    n: int


class VersionResponse(Contract):
    spec: Spec


class ExportRequest(Contract):
    spec: Spec
