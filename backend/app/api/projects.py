"""Projects API (INF-6). Auth via current_user (INF-5); persistence via the store repo.

Owners only see their own projects; another user's project id returns 404.
"""

from fastapi import APIRouter, Depends

from app.auth.verify import AuthUser, current_user
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
from app.store import repo

router = APIRouter(prefix="/projects")
ERRORS = {401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 503: {"model": ErrorResponse}}


@router.get("", response_model=list[ProjectSummary], responses=ERRORS)
def list_projects(user: AuthUser = Depends(current_user)):
    owner_id = repo.upsert_user(user.sub)
    return repo.list_projects(owner_id)


@router.post("", response_model=ProjectCreateResponse, responses=ERRORS)
def create_project(req: ProjectCreateRequest, user: AuthUser = Depends(current_user)):
    owner_id = repo.upsert_user(user.sub)
    return repo.create_project(owner_id, req.name, req.spec)


@router.get("/{project_id}", response_model=ProjectDetail, responses=ERRORS)
def get_project(project_id: int, user: AuthUser = Depends(current_user)):
    owner_id = repo.upsert_user(user.sub)
    return repo.get_project(owner_id, project_id)


@router.post("/{project_id}/versions", response_model=VersionCreateResponse, responses=ERRORS)
def create_version(project_id: int, req: VersionCreateRequest, user: AuthUser = Depends(current_user)):
    owner_id = repo.upsert_user(user.sub)
    return repo.create_version(owner_id, project_id, req.spec, req.source)


@router.get("/{project_id}/versions/{n}", response_model=VersionResponse, responses=ERRORS)
def get_version(project_id: int, n: int, user: AuthUser = Depends(current_user)):
    owner_id = repo.upsert_user(user.sub)
    return repo.get_version(owner_id, project_id, n)
