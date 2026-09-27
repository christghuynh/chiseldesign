"""INF-8: validate and prepare an uploaded image for parsing.

`prepare_image(raw, content_type)` verifies the bytes really are a supported image (by decoding,
not by trusting the content-type), rejects anything over 10 MB, applies EXIF orientation,
puts transparent images on white, keeps the first frame of animated or multi-page files,
downscales so the long side is <= 1600 px, and returns re-encoded JPEG bytes ready for Gemini.

Supported: JPEG, PNG, WebP, HEIC/HEIF (iPhone photos, via pillow-heif), AVIF, GIF, BMP, TIFF.

Raises `ImageTooLarge` (413) or `UnsupportedImage` (415); the route maps these to ApiError.
Raw bytes are never logged.
"""

from __future__ import annotations

import io

import pillow_heif
from PIL import Image, ImageOps, UnidentifiedImageError

pillow_heif.register_heif_opener()  # lets Image.open read HEIC/HEIF

MAX_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_LONG_SIDE = 1600
JPEG_QUALITY = 85

# Pillow format -> what we accept. content-type is advisory only; the decoded format decides.
_ALLOWED_FORMATS = {"JPEG", "MPO", "PNG", "WEBP", "HEIF", "AVIF", "GIF", "BMP", "TIFF"}
SUPPORTED_TEXT = "JPEG, PNG, HEIC, WebP, AVIF, GIF, BMP or TIFF"


class ImageError(Exception):
    """Base for upload problems."""


class ImageTooLarge(ImageError):
    """The upload exceeds MAX_BYTES (HTTP 413)."""


class UnsupportedImage(ImageError):
    """Not a decodable image in a supported format (HTTP 415)."""


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
                raise UnsupportedImage(f"Unsupported image format {fmt or 'unknown'}; use {SUPPORTED_TEXT}.")
            img.seek(0)  # first frame of an animated GIF / multi-page TIFF
            img = ImageOps.exif_transpose(img)  # honour camera rotation
            img = _on_white(img)
            img.thumbnail((MAX_LONG_SIDE, MAX_LONG_SIDE), Image.LANCZOS)
            out = io.BytesIO()
            img.save(out, format="JPEG", quality=JPEG_QUALITY)
            return out.getvalue()
    except UnsupportedImage:
        raise
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise UnsupportedImage(f"The uploaded file is not a readable image; use {SUPPORTED_TEXT}.") from exc


def _on_white(img: Image.Image) -> Image.Image:
    """RGB copy; transparency becomes white paper, not the black a plain convert() would give."""
    if img.mode in ("RGBA", "LA", "PA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.getchannel("A"))
        return background
    return img.convert("RGB")
