from fastapi import APIRouter

from app.api.errors import not_implemented
from app.models import (
    ErrorResponse,
    ProjectCreateRequest,
    ProjectCreateResponse,
    ProjectDetail,
    ProjectSummary,
    VersionCreateRequest,
    VersionCreateResponse,
    VersionResponse,
)

router = APIRouter(prefix="/projects")
NOT_IMPLEMENTED = {501: {"model": ErrorResponse}}

# STUBS (F-4): auth (INF-5) and persistence (INF-6) are not built yet.


@router.get("", response_model=list[ProjectSummary], responses=NOT_IMPLEMENTED)
def list_projects():
    raise not_implemented("INF-6")


@router.post("", response_model=ProjectCreateResponse, responses=NOT_IMPLEMENTED)
def create_project(req: ProjectCreateRequest):
    raise not_implemented("INF-6")


@router.get("/{project_id}", response_model=ProjectDetail, responses=NOT_IMPLEMENTED)
def get_project(project_id: int):
    raise not_implemented("INF-6")


@router.post("/{project_id}/versions", response_model=VersionCreateResponse, responses=NOT_IMPLEMENTED)
def create_version(project_id: int, req: VersionCreateRequest):
    raise not_implemented("INF-6")


@router.get("/{project_id}/versions/{n}", response_model=VersionResponse, responses=NOT_IMPLEMENTED)
def get_version(project_id: int, n: int):
    raise not_implemented("INF-6")
