from fastapi import APIRouter

from app.ai.instructions import handle_instructions
from app.models import InstructionsRequest, InstructionsResponse

router = APIRouter()


@router.post("/instructions", response_model=InstructionsResponse)
def instructions(req: InstructionsRequest) -> InstructionsResponse:
    """AI-6: friendly spoken build steps. AI failures fall back to skeleton steps (still 200)."""
    return handle_instructions(req.spec)
