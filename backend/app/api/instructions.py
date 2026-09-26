from fastapi import APIRouter

from app import fixtures
from app.models import InstructionsRequest, InstructionsResponse

router = APIRouter()


@router.post("/instructions", response_model=InstructionsResponse)
def instructions(req: InstructionsRequest) -> InstructionsResponse:
    # STUB (F-4): always returns the switchback ramp's steps. AI-6 replaces this.
    return fixtures.ramp_instructions()
