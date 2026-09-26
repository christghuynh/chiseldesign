"""INF-8: validate and prepare an uploaded image for parsing.

`prepare_image(raw, content_type)` verifies the bytes really are a JPEG/PNG/WebP (by decoding,
not by trusting the content-type), rejects anything over 10 MB, applies EXIF orientation,
downscales so the long side is <= 1600 px, and returns re-encoded JPEG bytes ready for Gemini.

Raises `ImageTooLarge` (413) or `UnsupportedImage` (415); the route maps these to ApiError.
Raw bytes are never logged.
"""

from __future__ import annotations

import io

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_LONG_SIDE = 1600
JPEG_QUALITY = 85

# Pillow format -> what we accept. content-type is advisory only; the decoded format decides.
_ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}


class ImageError(Exception):
    """Base for upload problems."""


class ImageTooLarge(ImageError):
    """The upload exceeds MAX_BYTES (HTTP 413)."""


class UnsupportedImage(ImageError):
    """Not a decodable JPEG/PNG/WebP (HTTP 415)."""


def prepare_image(raw: bytes, content_type: str | None = None) -> bytes:
    """Return JPEG bytes (<= 1600 px long side, EXIF applied). See module docstring for errors."""
    if len(raw) > MAX_BYTES:
        raise ImageTooLarge(f"Image is {len(raw) // (1024 * 1024)} MB; the limit is 10 MB.")
    if not raw:
        raise UnsupportedImage("The uploaded file is empty.")

    try:
        with Image.open(io.BytesIO(raw)) as img:
            fmt = (img.format or "").upper()
            if fmt not in _ALLOWED_FORMATS:
                raise UnsupportedImage(f"Unsupported image format {fmt or 'unknown'}; use JPEG, PNG or WebP.")
            img = ImageOps.exif_transpose(img)  # honour camera rotation
            img = img.convert("RGB")
            img.thumbnail((MAX_LONG_SIDE, MAX_LONG_SIDE), Image.LANCZOS)
            out = io.BytesIO()
            img.save(out, format="JPEG", quality=JPEG_QUALITY)
            return out.getvalue()
    except UnsupportedImage:
        raise
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise UnsupportedImage("The uploaded file is not a readable image.") from exc
