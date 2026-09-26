"""Write shared/schema/contracts.schema.json from the Pydantic models. Run via `make types`."""

from app.models.schema import SCHEMA_PATH, render_schema


def main() -> None:
    SCHEMA_PATH.parent.mkdir(parents=True, exist_ok=True)
    # Write bytes so Windows doesn't turn "\n" into CRLF.
    SCHEMA_PATH.write_bytes(render_schema().encode("utf-8"))
    print(f"wrote {SCHEMA_PATH}")


if __name__ == "__main__":
    main()
