from fastapi import APIRouter

from app.config import settings
from app.models import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(ok=True, version=settings.version)
