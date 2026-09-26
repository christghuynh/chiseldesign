from fastapi import APIRouter, File, Form, UploadFile

from app import fixtures
from app.models import ParseResponse

router = APIRouter()


@router.post("/parse", response_model=ParseResponse)
async def parse(
    image: UploadFile = File(...),
    measurements: str | None = Form(None),  # JSON string; its shape is defined by AI-3
    note: str | None = Form(None),
) -> ParseResponse:
    # STUB (F-4): the image is NOT analyzed. Returns the straight-ramp fixture's params with no
    # parts or rule checks (a parse result has params + assumed only). AI-3 replaces this.
    spec = fixtures.ramp_plan("straight").spec
    spec.parts = []
    spec.rule_checks = []
    return ParseResponse(
        spec=spec,
        template_confidence=None,
        questions=[],
        raw_notes="Fixture response: the image was not analyzed.",
    )
