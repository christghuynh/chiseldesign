"""Export filenames, matching frontend/src/components/plan/exports.ts `exportFilename`.

`sketchbuild-<template>[-<layout>].step|stl` and `sketchbuild-<template>[-<layout>]-cut-list.csv`.
The layout segment is dropped when it is absent or "auto". Non [a-z0-9-] runs collapse to "_",
and the whole thing is lowercased.
"""

from __future__ import annotations

import re

from app.models import Spec


def export_filename(spec: Spec, kind: str) -> str:
    """kind is one of 'step', 'stl', 'csv'."""
    ext = {"step": "step", "stl": "stl", "csv": "csv"}[kind]
    layout_param = spec.params.get("layout")
    layout = layout_param.value if layout_param is not None else None
    segments = [
        "sketchbuild",
        spec.template,
        layout if isinstance(layout, str) and layout != "auto" else None,
        "cut-list" if kind == "csv" else None,
    ]
    stem = "-".join(s for s in segments if s)
    stem = re.sub(r"[^a-z0-9-]+", "_", stem, flags=re.IGNORECASE).lower()
    return f"{stem}.{ext}"
