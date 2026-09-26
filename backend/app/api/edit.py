from fastapi import APIRouter, Depends

from app.ai.edit import EditError, handle_edit
from app.ai.ratelimit import edit_rate_limit
from app.api.errors import ApiError
from app.models import EditRequest, EditResponse, ErrorResponse

router = APIRouter()


@router.post(
    "/edit",
    response_model=EditResponse,
    responses={429: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
    dependencies=[Depends(edit_rate_limit)],
)
def edit(req: EditRequest) -> EditResponse:
    """AI-5: interpret a spoken/typed edit into a param change, a rule fix, or a clarification.

    On any AI failure the frontend falls back to its sliders and typed box, so we return
    503 AI_UNAVAILABLE rather than a 500.
    """
    try:
        return handle_edit(req.spec, req.utterance)
    except EditError as exc:
        raise ApiError(
            503,
            "AI_UNAVAILABLE",
            "The voice editor is unavailable right now — use the sliders or the typed box to make the change.",
        ) from exc
