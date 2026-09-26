"""AI-8: run the parse eval set and print per-parameter accuracy.

    cd backend && uv run python ../evals/run_parse_eval.py            # real parses (needs a key)
    cd backend && uv run python ../evals/run_parse_eval.py --fake     # network-free smoke run

Each case in evals/parse_cases.json names an image and the expected template + params (inches)
with tolerances. For every case we run the parse pipeline and compare:
- template: exact match;
- numeric params: within tolerance (case `tol`, else the file default, else 1.0 inch);
- string/enum/bool params: exact match.

Prints a per-param table and an overall accuracy. Exit code is non-zero if any case errored so
`make eval` fails loudly; accuracy below target is reported but not fatal (tuning is iterative).

`--fake` sets FAKE_AI=1 and skips missing image files, so it always runs the shipped fake reading
and never touches the network — used by the test and as a quick smoke check.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

CASES_PATH = Path(__file__).parent / "parse_cases.json"


def _load_pipeline():
    from app.ai.imageprep import prepare_image
    from app.ai.parse import parse_image

    return prepare_image, parse_image


def _tiny_png() -> bytes:
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (64, 48), (60, 70, 80)).save(buf, format="PNG")
    return buf.getvalue()


def _is_close(got, expected, tol) -> bool:
    try:
        return abs(float(got) - float(expected)) <= float(tol)
    except (TypeError, ValueError):
        return got == expected


def _compare(spec, expect, default_tol) -> list[tuple[str, bool, str]]:
    """Return (param, ok, detail) rows for one case."""
    rows: list[tuple[str, bool, str]] = []
    got_template = spec.template if spec else None
    rows.append(("template", got_template == expect["template"], f"{got_template!r} vs {expect['template']!r}"))
    params = spec.params if spec else {}
    for name, exp in expect.get("params", {}).items():
        pv = params.get(name)
        got = pv.value if pv is not None else None
        exp_val = exp["value"]
        if isinstance(exp_val, (int, float)) and not isinstance(exp_val, bool):
            tol = exp.get("tol", default_tol)
            ok = got is not None and _is_close(got, exp_val, tol)
            detail = f"{got} vs {exp_val} (±{tol})"
        else:
            ok = got == exp_val
            detail = f"{got!r} vs {exp_val!r}"
        rows.append((name, ok, detail))
    return rows


def run(fake: bool) -> int:
    if fake:
        os.environ["FAKE_AI"] = "1"
    prepare_image, parse_image = _load_pipeline()

    spec = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    default_tol = spec.get("tolerances_default_in", 1.0)
    cases = spec["cases"]

    total = correct = 0
    errored = 0
    print(f"parse eval: {len(cases)} case(s){' [FAKE]' if fake else ''}\n")

    for case in cases:
        name = case["name"]
        image_path = REPO_ROOT / case["image"]
        try:
            if image_path.is_file():
                raw = image_path.read_bytes()
            elif fake:
                raw = _tiny_png()  # fake mode ignores the pixels; use a placeholder
            else:
                print(f"  {name}: SKIP (missing image {case['image']})")
                continue
            prepared = prepare_image(raw, None)
            result = parse_image(prepared, "image/jpeg")
        except Exception as exc:  # noqa: BLE001 - report and keep going
            errored += 1
            print(f"  {name}: ERROR {type(exc).__name__}: {exc}")
            continue

        rows = _compare(result.spec, case["expect"], default_tol)
        case_ok = sum(1 for _, ok, _ in rows if ok)
        total += len(rows)
        correct += case_ok
        print(f"  {name}: {case_ok}/{len(rows)} params")
        for param, ok, detail in rows:
            print(f"      [{'PASS' if ok else 'FAIL'}] {param}: {detail}")

    pct = (100.0 * correct / total) if total else 0.0
    print(f"\noverall: {correct}/{total} params correct ({pct:.0f}%)")
    if errored:
        print(f"{errored} case(s) errored", file=sys.stderr)
        return 1
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Run the parse eval set and report per-param accuracy.")
    ap.add_argument("--fake", action="store_true", help="FAKE_AI mode: no network, skips missing images")
    args = ap.parse_args()
    return run(args.fake)


if __name__ == "__main__":
    sys.exit(main())
