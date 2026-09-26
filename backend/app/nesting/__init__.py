"""Stock nesting: 1D boards (GEO-11) and 2D sheets (GEO-12)."""

from app.nesting.boards import KERF_IN, BoardPiece, nest_boards
from app.nesting.errors import PieceTooLongError

__all__ = ["KERF_IN", "BoardPiece", "PieceTooLongError", "nest_boards"]
