"""Project/version repository (INF-6).

Owners only see their own projects: another user's project id resolves to 404 via
ApiError, so we never reveal whether a project exists. The returned shapes follow the
payload models in app.models.api exactly.
"""

from __future__ import annotations

from app.api.errors import ApiError
from app.models import (
    ProjectCreateResponse,
    ProjectDetail,
    ProjectSummary,
    Spec,
    VersionCreateResponse,
    VersionInfo,
    VersionResponse,
)
from app.store.db import connect, now_iso


def upsert_user(auth0_sub: str) -> int:
    """Return the user id for an auth0 sub, creating the row if needed."""
    with connect() as conn:
        conn.execute(
            "INSERT INTO users (auth0_sub, created_at) VALUES (?, ?) "
            "ON CONFLICT(auth0_sub) DO NOTHING",
            (auth0_sub, now_iso()),
        )
        row = conn.execute("SELECT id FROM users WHERE auth0_sub = ?", (auth0_sub,)).fetchone()
        conn.commit()
        return int(row["id"])


def _owned_project_row(conn, project_id: int, owner_id: int):
    """Fetch a project row scoped to its owner; 404 if missing or not owned."""
    row = conn.execute(
        "SELECT * FROM projects WHERE id = ? AND owner_id = ?",
        (project_id, owner_id),
    ).fetchone()
    if row is None:
        raise ApiError(404, "NOT_FOUND", f"Project {project_id} not found")
    return row


def list_projects(owner_id: int) -> list[ProjectSummary]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, name, template, updated_at, thumb_png FROM projects "
            "WHERE owner_id = ? ORDER BY updated_at DESC, id DESC",
            (owner_id,),
        ).fetchall()
    return [
        ProjectSummary(
            id=int(r["id"]),
            name=r["name"],
            template=r["template"],
            updated_at=r["updated_at"],
            thumb=r["thumb_png"],
        )
        for r in rows
    ]


def create_project(owner_id: int, name: str, spec: Spec) -> ProjectCreateResponse:
    """Create a project and store the initial spec as version 1 (source 'manual')."""
    ts = now_iso()
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO projects (owner_id, name, template, created_at, updated_at, thumb_png) "
            "VALUES (?, ?, ?, ?, ?, NULL)",
            (owner_id, name, spec.template, ts, ts),
        )
        project_id = int(cur.lastrowid)
        conn.execute(
            "INSERT INTO versions (project_id, n, spec_json, source, created_at) VALUES (?, 1, ?, 'manual', ?)",
            (project_id, spec.model_dump_json(), ts),
        )
        conn.commit()
    return ProjectCreateResponse(id=project_id)


def get_project(owner_id: int, project_id: int) -> ProjectDetail:
    with connect() as conn:
        _owned_project_row(conn, project_id, owner_id)
        vrows = conn.execute(
            "SELECT n, source, created_at FROM versions WHERE project_id = ? ORDER BY n ASC",
            (project_id,),
        ).fetchall()
        prow = conn.execute("SELECT name FROM projects WHERE id = ?", (project_id,)).fetchone()
        latest_row = conn.execute(
            "SELECT spec_json FROM versions WHERE project_id = ? ORDER BY n DESC LIMIT 1",
            (project_id,),
        ).fetchone()
    versions = [
        VersionInfo(n=int(v["n"]), created_at=v["created_at"], source=v["source"]) for v in vrows
    ]
    latest = Spec.model_validate_json(latest_row["spec_json"])
    return ProjectDetail(id=project_id, name=prow["name"], versions=versions, latest=latest)


def create_version(owner_id: int, project_id: int, spec: Spec, source: str) -> VersionCreateResponse:
    ts = now_iso()
    with connect() as conn:
        _owned_project_row(conn, project_id, owner_id)
        row = conn.execute(
            "SELECT COALESCE(MAX(n), 0) AS max_n FROM versions WHERE project_id = ?",
            (project_id,),
        ).fetchone()
        n = int(row["max_n"]) + 1
        conn.execute(
            "INSERT INTO versions (project_id, n, spec_json, source, created_at) VALUES (?, ?, ?, ?, ?)",
            (project_id, n, spec.model_dump_json(), source, ts),
        )
        conn.execute("UPDATE projects SET updated_at = ? WHERE id = ?", (ts, project_id))
        conn.commit()
    return VersionCreateResponse(n=n)


def get_version(owner_id: int, project_id: int, n: int) -> VersionResponse:
    with connect() as conn:
        _owned_project_row(conn, project_id, owner_id)
        row = conn.execute(
            "SELECT spec_json FROM versions WHERE project_id = ? AND n = ?",
            (project_id, n),
        ).fetchone()
    if row is None:
        raise ApiError(404, "NOT_FOUND", f"Version {n} not found")
    return VersionResponse(spec=Spec.model_validate_json(row["spec_json"]))
