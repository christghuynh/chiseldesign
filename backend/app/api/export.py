"""Export API: STEP/STL (GEO-17) and cut-list CSV (GEO-18).

Request body and response headers match frontend/src/components/plan/exports.ts:
the body is {spec}; the response is the file with a Content-Disposition filename
`sketchbuild-<template>[-<layout>].step|stl` / `...-cut-list.csv`.
"""

from fastapi import APIRouter
from fastapi.responses import Response

from app import engine
from app.cad.cutlist_csv import cutlist_csv
from app.cad.exporter import export_parts
from app.cad.naming import export_filename
from app.models import ErrorResponse, ExportRequest

router = APIRouter(prefix="/export")
ERRORS = {422: {"model": ErrorResponse}}


def _content_disposition(filename: str) -> str:
    return f'attachment; filename="{filename}"'


def _parts_for(spec):
    """Use the spec's parts if present; otherwise recompute them via the engine."""
    if spec.parts:
        return spec.parts
    _spec, _plan = engine.generate(spec.template, spec.params, spec.meta)
    return _spec.parts


@router.post(
    "/step",
    responses={200: {"content": {"application/step": {}}}, **ERRORS},
)
def export_step(req: ExportRequest):
    data = export_parts(_parts_for(req.spec), "step")
    filename = export_filename(req.spec, "step")
    return Response(
        content=data,
        media_type="application/step",
        headers={"Content-Disposition": _content_disposition(filename)},
    )


@router.post(
    "/stl",
    responses={200: {"content": {"model/stl": {}}}, **ERRORS},
)
def export_stl(req: ExportRequest):
    data = export_parts(_parts_for(req.spec), "stl")
    filename = export_filename(req.spec, "stl")
    return Response(
        content=data,
        media_type="model/stl",
        headers={"Content-Disposition": _content_disposition(filename)},
    )


@router.post(
    "/cutlist.csv",
    responses={200: {"content": {"text/csv": {}}}, **ERRORS},
)
def export_cutlist_csv(req: ExportRequest):
    body = cutlist_csv(req.spec)
    filename = export_filename(req.spec, "csv")
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": _content_disposition(filename)},
    )
