from fastapi import APIRouter

from app import engine
from app.models import EditRequest, EditResponse

router = APIRouter()


@router.post("/edit", response_model=EditResponse)
def edit(req: EditRequest) -> EditResponse:
    # STUB: ignores the utterance and just regenerates the posted spec through the engine.
    # The AI edit tools (set_params, apply_fix, ask_clarification) replace this.
    spec, plan = engine.generate(req.spec.template, req.spec.params, req.spec.meta)
    return EditResponse(
        spec=spec,
        plan=plan,
        patch={},
        message="Fixture mode: the edit was not applied.",
        needs_clarification=False,
    )
