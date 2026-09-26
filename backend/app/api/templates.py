from fastapi import APIRouter

from app import engine
from app.models import TemplateInfo

router = APIRouter()


@router.get("/templates", response_model=list[TemplateInfo])
def list_templates() -> list[TemplateInfo]:
    # Thin handler over the engine (currently a fixture stub, see engine.py).
    return engine.list_templates()
