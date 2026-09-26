from fastapi import APIRouter

from app.api.errors import not_implemented
from app.models import ErrorResponse, ExportRequest

router = APIRouter(prefix="/export")
NOT_IMPLEMENTED = {501: {"model": ErrorResponse}}

# STUBS (F-4): the CadQuery exporter is GEO-17, the CSV export is GEO-18.


@router.post("/step", responses={200: {"content": {"application/step": {}}}, **NOT_IMPLEMENTED})
def export_step(req: ExportRequest):
    raise not_implemented("GEO-17")


@router.post("/stl", responses={200: {"content": {"model/stl": {}}}, **NOT_IMPLEMENTED})
def export_stl(req: ExportRequest):
    raise not_implemented("GEO-17")


@router.post("/cutlist.csv", responses={200: {"content": {"text/csv": {}}}, **NOT_IMPLEMENTED})
def export_cutlist_csv(req: ExportRequest):
    raise not_implemented("GEO-18")
