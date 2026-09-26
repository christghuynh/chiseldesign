"""Build-time smoke test for the backend image (INF-2).

Runs as the image's non-root user during `docker build`. Fails the build unless CadQuery imports,
exports a box to STEP and STL (and reads the STEP back), and the app answers GET /api/health.
"""

import asyncio
import json
import sys
import tempfile
from pathlib import Path


def main() -> None:
    import cadquery as cq

    box = cq.Workplane("XY").box(10, 20, 30)
    with tempfile.TemporaryDirectory() as tmp:
        step = Path(tmp) / "box.step"
        stl = Path(tmp) / "box.stl"
        cq.exporters.export(box, str(step))
        cq.exporters.export(box, str(stl))

        head = step.read_text(errors="replace")[:64]
        if not head.startswith("ISO-10303-21"):
            sys.exit(f"STEP export has no ISO-10303-21 header: {head!r}")
        if stl.stat().st_size == 0:
            sys.exit("STL export is empty")

        # Read the STEP back and check the volume survived the round trip.
        volume = cq.importers.importStep(str(step)).val().Volume()
        if abs(volume - 10 * 20 * 30) > 1e-3:
            sys.exit(f"STEP round trip changed the volume: {volume}")

    status, body = asyncio.run(_get("/api/health"))
    if status != 200 or not json.loads(body).get("ok"):
        sys.exit(f"/api/health returned {status}: {body!r}")

    print(f"smoke ok: cadquery {cq.__version__}, STEP + STL export, /api/health 200")


async def _get(path: str) -> tuple[int, bytes]:
    """One GET straight through the ASGI app (no server, no httpx in the runtime image)."""
    from app.main import app

    scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": "GET",
             "scheme": "http", "path": path, "raw_path": path.encode(), "root_path": "",
             "query_string": b"", "headers": [(b"host", b"localhost")],
             "client": ("127.0.0.1", 0), "server": ("localhost", 80)}
    sent: list[dict] = []

    async def receive() -> dict:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: dict) -> None:
        sent.append(message)

    await app(scope, receive, send)
    status = next(m["status"] for m in sent if m["type"] == "http.response.start")
    return status, b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body")


if __name__ == "__main__":
    main()
