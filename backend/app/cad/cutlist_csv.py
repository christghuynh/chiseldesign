"""Cut-list CSV (GEO-18).

Columns match what P4's frontend already emits (QUESTIONS.md FE-10):
    label,name,material,actual_dims_in,length_in,length,qty,part_ids,cut_notes
CRLF line endings, RFC 4180 quoting via the stdlib csv module.
The plan comes from engine.generate (never by importing cutlist/pricing modules directly).
"""

from __future__ import annotations

import csv
import io

from app import engine
from app.models import Spec

HEADER = [
    "label",
    "name",
    "material",
    "actual_dims_in",
    "length_in",
    "length",
    "qty",
    "part_ids",
    "cut_notes",
]


def cutlist_csv(spec: Spec) -> str:
    """Return the cut list as an RFC 4180 CSV string (CRLF), computed via the engine."""
    _spec, plan = engine.generate(spec.template, spec.params, spec.meta)
    buf = io.StringIO(newline="")
    writer = csv.writer(buf, lineterminator="\r\n", quoting=csv.QUOTE_MINIMAL)
    writer.writerow(HEADER)
    for row in plan.cut_list:
        writer.writerow(
            [
                row.label,
                row.name,
                row.material,
                row.actual_dims,
                row.length_in,
                row.length_display,
                row.qty,
                " ".join(row.part_ids),
                "; ".join(row.cut_notes),
            ]
        )
    return buf.getvalue()
