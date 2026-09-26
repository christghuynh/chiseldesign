"""Reference data: lumber (actual dimensions, stock lengths) and prices.

The JSON files are edited by hand (prices come from a retailer, task NC-4). Everything here is
read-only and cached; callers get validated models, never raw dicts.
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, model_validator

DATA_DIR = Path(__file__).resolve().parent


class LumberSpec(BaseModel):
    """One material. All dimensions are ACTUAL inches, never nominal."""

    nominal: str
    description: str
    thickness_in: float
    width_in: float | None  # boards only
    kind: Literal["board", "sheet"]
    stock_lengths_in: list[float]  # boards only, ascending
    sheet_size_in: tuple[float, float] | None  # sheets only: (width, length)
    outdoor_rated: bool

    @model_validator(mode="after")
    def _check_kind(self) -> "LumberSpec":
        if self.kind == "board":
            if self.width_in is None or not self.stock_lengths_in:
                raise ValueError("a board needs width_in and stock_lengths_in")
            if self.stock_lengths_in != sorted(self.stock_lengths_in):
                raise ValueError("stock_lengths_in must be ascending")
        elif self.sheet_size_in is None:
            raise ValueError("a sheet needs sheet_size_in")
        return self

    @property
    def max_stock_length_in(self) -> float:
        """Longest board sold, or the long side of a sheet."""
        return self.stock_lengths_in[-1] if self.kind == "board" else max(self.sheet_size_in or (0, 0))


class PriceEntry(BaseModel):
    description: str
    unit: str
    price_cad: float
    units_per_pack: int | None  # fasteners: pieces per box
    source_url: str | None
    retrieved_at: str | None
    placeholder: bool


@lru_cache
def lumber() -> dict[str, LumberSpec]:
    raw = json.loads((DATA_DIR / "lumber.json").read_text("utf-8"))["materials"]
    return {key: LumberSpec.model_validate(value) for key, value in raw.items()}


@lru_cache
def prices() -> dict[str, PriceEntry]:
    raw = json.loads((DATA_DIR / "prices.json").read_text("utf-8"))["items"]
    return {key: PriceEntry.model_validate(value) for key, value in raw.items()}


def lumber_spec(material: str) -> LumberSpec:
    try:
        return lumber()[material]
    except KeyError:
        raise KeyError(f"Unknown material {material!r}; known: {sorted(lumber())}") from None
