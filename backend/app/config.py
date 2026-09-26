"""Settings read from the environment, with a `.env` file at the repo root as a fallback.

The .env file is read as utf-8-sig because files written from PowerShell can start with a
byte-order mark, which would otherwise glue itself onto the first key name.
"""

import os
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        # Real environment variables win over the file.
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def _app_version() -> str:
    try:
        return version("sketchbuild-backend")
    except PackageNotFoundError:
        return "0.0.0"


@dataclass(frozen=True)
class Settings:
    version: str
    cors_origins: list[str]
    fixtures_dir: Path


def load_settings() -> Settings:
    _load_dotenv(REPO_ROOT / ".env")
    origins = os.environ.get("CORS_ORIGINS", "http://localhost:5173")
    return Settings(
        version=_app_version(),
        cors_origins=[o.strip() for o in origins.split(",") if o.strip()],
        fixtures_dir=Path(os.environ.get("FIXTURES_DIR", REPO_ROOT / "fixtures")),
    )


settings = load_settings()
