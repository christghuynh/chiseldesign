"""Manual smoke test of the real Gemini path (makes two small API calls; never run by pytest).

    cd backend && uv run python -m app.ai.smoke

Needs GEMINI_API_KEY in the repo-root .env. Prints outcomes and latency, never the key.
"""

import logging
import os
import sys
import time

from app.ai.client import AIError, Message, Tool, call_with_tools, generate_json, model_name


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    os.environ["FAKE_AI"] = "0"
    print(f"model: {model_name()}")
    ok = True

    schema = {
        "type": "object",
        "properties": {"object": {"type": "string"}, "steps": {"type": "integer"}},
        "required": ["object", "steps"],
    }
    start = time.perf_counter()
    try:
        out = generate_json(
            "A porch has three steps up to the front door. Reply with the object and the number of steps.",
            schema,
            call="smoke_json",
        )
        print(f"generate_json ok in {time.perf_counter() - start:.1f}s: {out}")
    except AIError as exc:
        ok = False
        print(f"generate_json FAILED: {type(exc).__name__}: {exc}")

    tool = Tool(
        name="set_params",
        description="Change ramp parameters. Widths are in inches.",
        parameters={
            "type": "object",
            "properties": {
                "patch": {
                    "type": "object",
                    "properties": {"clear_width_in": {"type": "number"}},
                    "required": ["clear_width_in"],
                }
            },
            "required": ["patch"],
        },
    )
    start = time.perf_counter()
    try:
        turn = call_with_tools(
            [Message("user", "The ramp is 36 inches wide. Make it 6 inches wider.")],
            [tool],
            call="smoke_tools",
            force_tool=True,
        )
        print(f"call_with_tools ok in {time.perf_counter() - start:.1f}s: {turn}")
    except AIError as exc:
        ok = False
        print(f"call_with_tools FAILED: {type(exc).__name__}: {exc}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
