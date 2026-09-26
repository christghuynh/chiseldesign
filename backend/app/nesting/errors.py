"""Errors raised by the nesting functions."""


class PieceTooLongError(ValueError):
    """A piece cannot be cut from any stock the material is sold in (never silently truncated).

    `part_ids` lists every offending piece (nesting checks them all before raising, so a caller can drop
    exactly those pieces and nest the rest). The message names the first one, its size and the limit.
    """

    def __init__(self, message: str, part_ids: list[str]):
        super().__init__(message)
        self.part_ids = part_ids
