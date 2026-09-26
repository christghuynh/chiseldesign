"""Layout helpers for laying boards, panels and segments along a length (used by the ramp parts).

Pure functions on plain numbers: they return `(start, end)` intervals measured from 0 along the
length being covered, so the run decking (slope distance), the landing decking (across the landing)
and the curb/rail/panel segmenting can all share them.
"""

import math
from dataclasses import dataclass

from app.data import LumberSpec, lumber_spec
from app.rules.constants import EDGE_CURB_MIN_HEIGHT_IN

# A ripped (narrowed) board is only worth cutting when it ends up at least this wide.
MIN_RIPPED_WIDTH_IN = 2.0
_EPS = 1e-9
CURB_MATERIAL = "2x6_PT"  # on edge: 5.5 in tall, above the 4 in minimum that ADA 405.9.2 needs


def curb_spec() -> LumberSpec:
    """The curb board. A curb must stand at least EDGE_CURB_MIN_HEIGHT_IN tall (ADA 405.9.2): a 2x4 on edge (3.5 in) is too low."""
    spec = lumber_spec(CURB_MATERIAL)
    assert spec.width_in is not None and spec.width_in >= EDGE_CURB_MIN_HEIGHT_IN.value, "edge curbs must be at least 4 in tall"
    return spec


@dataclass(frozen=True)
class BoardSpan:
    """One deck board covering `[start, end]` along the length. `ripped` boards are narrower than stock."""

    start: float
    end: float
    ripped: bool

    @property
    def width(self) -> float:
        return self.end - self.start


def layout_boards(length: float, width: float, gap: float, min_width: float = MIN_RIPPED_WIDTH_IN) -> list[BoardSpan]:
    """Cover `length` with boards of stock `width` separated by `gap`, without leaving a sliver board.

    The rule (the last board always ends exactly at `length`):

    - n = floor((length + gap) / (width + gap)) full boards; the remainder is
      r = length - (n * width + (n - 1) * gap).
    - If r >= min_width + gap, add one more board of width r - gap after a gap (a RIPPED board).
    - Otherwise r is too small to be a board, so it is spread evenly over the gaps
      (gap' = gap + r / (n - 1)) and every board stays full width.

    Cases the rule does not cover, decided here so nothing is ever wider than the board that is sold:
    - n == 0 (the length is shorter than one board): one ripped board covering the whole length.
    - n == 1 and r < min_width + gap (there is no gap to spread r over): two equal ripped boards
      instead of stretching one board past its stock width.
    """
    n = math.floor((length + gap) / (width + gap) + _EPS)
    if n == 0:
        return [BoardSpan(0.0, length, True)]
    remainder = max(0.0, length - (n * width + (n - 1) * gap))
    if remainder >= min_width + gap - _EPS:
        spans = [BoardSpan(i * (width + gap), i * (width + gap) + width, False) for i in range(n)]
        spans.append(BoardSpan(n * (width + gap), length, True))
        return spans
    if n == 1:
        half = (length - gap) / 2
        return [BoardSpan(0.0, half, True), BoardSpan(half + gap, length, True)]
    gap_wide = gap + remainder / (n - 1)
    spans = [BoardSpan(i * (width + gap_wide), i * (width + gap_wide) + width, False) for i in range(n)]
    spans[-1] = BoardSpan(spans[-1].start, length, False)
    return spans


def equal_pieces(length: float, max_piece: float, gap: float = 0.0) -> list[tuple[float, float]]:
    """Split `length` into the fewest equal pieces no longer than `max_piece`, `gap` apart.

    Returns `(start, end)` intervals; the last one ends exactly at `length`.
    """
    n = max(1, math.ceil(length / max_piece - _EPS))
    piece = (length - (n - 1) * gap) / n
    pieces = [(i * (piece + gap), i * (piece + gap) + piece) for i in range(n)]
    pieces[-1] = (pieces[-1][0], length)
    return pieces
