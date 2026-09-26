from fastapi import APIRouter, Depends

from app.ai.instructions import handle_instructions
from app.ai.ratelimit import instructions_rate_limit
from app.models import InstructionsRequest, InstructionsResponse

router = APIRouter()


@router.post("/instructions", response_model=InstructionsResponse, dependencies=[Depends(instructions_rate_limit)])
def instructions(req: InstructionsRequest) -> InstructionsResponse:
    """AI-6: friendly spoken build steps. AI failures fall back to skeleton steps (still 200)."""
    return handle_instructions(req.spec)
