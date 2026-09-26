from fastapi import APIRouter

from app import engine
from app.models import GenerateRequest, GenerateResponse

router = APIRouter()


@router.post("/generate", response_model=GenerateResponse)
def generate(req: GenerateRequest) -> GenerateResponse:
    # Thin handler: everything happens in the engine (currently a fixture stub, see engine.py).
    # engine.TemplateError / ParamValidationError become 422 responses (api/errors.py).
    spec, plan = engine.generate(req.template, req.params, req.meta)
    return GenerateResponse(spec=spec, plan=plan)
