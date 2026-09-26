"""Part labelling (GEO-10) and cut-list rows.

`label_parts` groups identical parts and names the groups A, B, C ... `build_cut_list` turns labelled
parts into one CutListRow per label. Both are deterministic.
"""

from dataclasses import dataclass

from app.cutlist.geometry import part_extents, part_length, shape_signature
from app.data import lumber_spec
from app.models import CutListRow, Part
from app.util.units import format_fraction, format_ft_in

_GroupKey = tuple[str, str, tuple[tuple[float, float], ...], float, tuple[str, ...]]


def label_for_index(index: int) -> str:
    """0 -> A, 25 -> Z, 26 -> AA, 27 -> AB ... (bijective base 26, spreadsheet style)."""
    if index < 0:
        raise ValueError("index must be >= 0")
    chars: list[str] = []
    n = index + 1
    while n > 0:
        n, rem = divmod(n - 1, 26)
        chars.append(chr(ord("A") + rem))
    return "".join(reversed(chars))


def _group_key(part: Part) -> _GroupKey:
    return (part.material, part.name, shape_signature(part.profile), round(part.thickness, 3), tuple(part.cut_notes))


@dataclass
class _Group:
    key: _GroupKey
    length: float


def label_parts(parts: list[Part]) -> list[Part]:
    """Return NEW parts with `label` and `id` assigned; the inputs are not modified.

    Identical parts (same material, name, shape, extrusion depth and cut notes, wherever they sit) share
    a label. Labels are handed out by material key (alphabetical), then descending part length, then name,
    then cut notes (then shape, so the order is total). Part ids are "<label>-<n>", n counting from 1 in
    input order. Raises KeyError for a material that is not in lumber.json.
    """
    groups: dict[_GroupKey, _Group] = {}
    for part in parts:
        lumber_spec(part.material)  # fail early with a clear message
        key = _group_key(part)
        if key not in groups:
            groups[key] = _Group(key, part_length(part))

    def order(group: _Group):
        material, name, signature, thickness, notes = group.key
        return (material, -group.length, name, notes, signature, thickness)

    label_of = {g.key: label_for_index(i) for i, g in enumerate(sorted(groups.values(), key=order))}
    counters: dict[str, int] = {}
    labelled: list[Part] = []
    for part in parts:
        label = label_of[_group_key(part)]
        counters[label] = counters.get(label, 0) + 1
        labelled.append(part.model_copy(deep=True, update={"label": label, "id": f"{label}-{counters[label]}"}))
    return labelled


def sheet_piece_dims(part: Part) -> tuple[float, float]:
    """(larger, smaller) face dimensions of a sheet part.

    The part's three extents include the sheet thickness; the extent closest to the material's actual
    thickness is dropped and the other two are returned, larger first.
    """
    thickness = lumber_spec(part.material).thickness_in
    extents = list(part_extents(part))
    drop = min(range(3), key=lambda i: (abs(extents[i] - thickness), i))
    del extents[drop]
    return (max(extents), min(extents))


def actual_dims(part: Part) -> str:
    """Actual (never nominal) dimensions: "1-1/2 × 5-1/2" for boards, "11/16 × 48 × 96" for sheet pieces."""
    spec = lumber_spec(part.material)
    if spec.kind == "board":
        return f"{format_fraction(spec.thickness_in)} × {format_fraction(spec.width_in or 0)}"
    w, h = sheet_piece_dims(part)
    return f"{format_fraction(spec.thickness_in)} × {format_fraction(w)} × {format_fraction(h)}"


def build_cut_list(parts: list[Part]) -> list[CutListRow]:
    """One row per label, ordered A, B ... Z, AA ...; `parts` must already be labelled (label_parts).

    `length_in` is `part_length` (the same number the nesting uses). Name, material, dimensions, length
    and notes come from the first part carrying the label; parts sharing a label are identical by
    construction. For a sheet part `length_in` is its longest extent.
    """
    rows: dict[str, list[Part]] = {}
    for part in parts:
        rows.setdefault(part.label, []).append(part)
    result: list[CutListRow] = []
    for label in sorted(rows, key=lambda s: (len(s), s)):
        members = rows[label]
        first = members[0]
        length = part_length(first)
        result.append(
            CutListRow(
                label=label,
                name=first.name,
                material=first.material,
                actual_dims=actual_dims(first),
                length_in=length,
                length_display=format_ft_in(length),
                qty=len(members),
                part_ids=[p.id for p in members],
                cut_notes=list(first.cut_notes),
            )
        )
    return result
