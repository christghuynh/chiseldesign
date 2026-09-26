"""AI-9: run one REAL parse of an image and save the result to the demo cache.

    cd backend && uv run python ../evals/cache_demo.py <image> [--note "..."]

This makes one real Gemini call (needs GEMINI_API_KEY in the repo-root .env). It writes
fixtures/demo/<sha256>.json holding the ParseResponse, keyed by the sha256 of the RAW uploaded
bytes, so the demo sketch then parses instantly and offline via the /parse cache.

The key is never printed. Do not commit real API keys.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Allow `python ../evals/cache_demo.py` from backend/ to import the app package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.ai import parsecache  # noqa: E402
from app.ai.imageprep import prepare_image  # noqa: E402
from app.ai.parse import parse_image  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Run a real parse once and cache it for the demo.")
    ap.add_argument("image", type=Path, help="path to a JPEG/PNG/WebP sketch or site photo")
    ap.add_argument("--note", default=None, help="optional user note passed to the parser")
    args = ap.parse_args()

    if not args.image.is_file():
        print(f"no such file: {args.image}", file=sys.stderr)
        return 2

    os.environ["FAKE_AI"] = "0"  # this script is the sanctioned real call
    raw = args.image.read_bytes()
    prepared = prepare_image(raw, None)
    response = parse_image(prepared, "image/jpeg", note=args.note)

    # Cache is keyed by the RAW bytes the browser would upload, so /parse hits it before any AI.
    path = parsecache.store(raw, response)
    template = response.spec.template if response.spec else None
    print(f"cached parse for {args.image.name} -> {path} (template={template})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
