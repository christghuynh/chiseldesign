"""Ramp parts (tasks GEO-4, GEO-5, GEO-6). STUB: replaced by the parts implementation."""

from app.models import Part
from app.templates.ramp import Derived, Params


def build_parts(params: Params, derived: Derived) -> list[Part]:
    raise NotImplementedError("ramp parts are built by GEO-4, GEO-5 and GEO-6")
