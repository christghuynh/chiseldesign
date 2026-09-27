"""AI-8: generate a synthetic eval set of hand-drawn-style sketches, photographed badly.

    cd backend && uv run python ../evals/make_synthetic_sketches.py --fonts /path/to/fonts

Draws porch/ramp side views, a garden bed, a workbench, a step platform, a note-style sketch and a
non-sketch, in handwriting fonts (OFL Google Fonts: Kalam, Patrick Hand, Caveat, Nothing You Could
Do), then applies phone-photo effects (tilt, perspective, blur, uneven light, paper texture, JPEG).
Writes fixtures/sketches/synthetic/*.jpg and evals/synthetic_cases.json. Deterministic (fixed seed).

These are a stand-in until real sketches exist (NC-5). They test reading handwriting-like numbers,
units and layout; they do not replace photos of real paper sketches and real porches.
"""

from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

REPO = Path(__file__).resolve().parents[1]
OUT_DIR = REPO / "fixtures" / "sketches" / "synthetic"
CASES = REPO / "evals" / "synthetic_cases.json"
W, H = 1600, 1200
INK = (25, 30, 60)


class Pen:
    def __init__(self, img: Image.Image, font_path: Path, rng: random.Random, width: int = 5):
        self.d = ImageDraw.Draw(img)
        self.font_path, self.rng, self.width = font_path, rng, width

    def line(self, a, b, width=None):
        """A slightly wobbly hand-drawn line."""
        (x0, y0), (x1, y1) = a, b
        n = max(4, int(math.hypot(x1 - x0, y1 - y0) / 40))
        pts = []
        for i in range(n + 1):
            t = i / n
            j = self.rng.uniform(-2.5, 2.5) if 0 < i < n else 0
            pts.append((x0 + (x1 - x0) * t + j, y0 + (y1 - y0) * t + j))
        self.d.line(pts, fill=INK, width=width or self.width, joint="curve")

    def poly(self, pts, width=None):
        for a, b in zip(pts, pts[1:]):
            self.line(a, b, width)

    def text(self, xy, s, size=64, angle=0):
        font = ImageFont.truetype(str(self.font_path), size)
        if angle == 0:
            self.d.text(xy, s, font=font, fill=INK)
            return
        box = self.d.textbbox((0, 0), s, font=font)
        tile = Image.new("RGBA", (box[2] + 20, box[3] + 20), (0, 0, 0, 0))
        ImageDraw.Draw(tile).text((10, 10), s, font=font, fill=INK + (255,))
        tile = tile.rotate(angle, expand=True)
        self.d._image.paste(tile, (int(xy[0]), int(xy[1])), tile)

    def dim(self, a, b, label, size=60, offset=(0, 0)):
        """Dimension line with arrow ticks and a label near its middle."""
        self.line(a, b, 3)
        for p in (a, b):
            self.line((p[0] - 12, p[1] - 12), (p[0] + 12, p[1] + 12), 3)
        mx, my = (a[0] + b[0]) / 2 + offset[0], (a[1] + b[1]) / 2 + offset[1]
        self.text((mx, my), label, size)


def porch(pen: Pen, steps: int, rise_label: str | None, yard_label: str | None, width_label: str | None = None, extra: str | None = None):
    ground = 900
    wall_x = 1250
    step_h, step_d = 70, 90
    top = ground - steps * step_h
    pen.line((80, ground), (1520, ground))  # ground
    pen.poly([(wall_x, top), (wall_x, 250), (1480, 250)])  # house wall
    pen.text((1290, 300), "HOUSE", 56)
    pen.text((1300, top - 70), "porch", 54)
    pen.line((wall_x, top), (1480, top))
    # steps going down to the left
    x, y = wall_x, top
    for _ in range(steps):
        pen.poly([(x, y), (x - step_d, y), (x - step_d, y + step_h)])
        x, y = x - step_d, y + step_h
    if rise_label:
        pen.dim((wall_x + 150, top), (wall_x + 150, ground), rise_label, offset=(20, -30))
    if yard_label:
        pen.dim((100, ground + 90), (wall_x, ground + 90), yard_label, offset=(-60, 10))
        pen.text((110, ground + 160), "yard / walkway", 46)
    if width_label:
        pen.text((200, 300), width_label, 58)
    if extra:
        pen.text((200, 400), extra, 58)
    pen.text((110, 120), "Ramp for Grandma", 72, angle=2)


def note(pen: Pen, lines: list[str]):
    y = 150
    for s in lines:
        pen.text((150, y), s, 76, angle=pen.rng.uniform(-2, 2))
        y += 150


def garden_bed(pen: Pen):
    # oblique box
    f = [(300, 500), (1100, 500), (1100, 800), (300, 800)]
    b = [(p[0] + 220, p[1] - 160) for p in f]
    pen.poly(f + [f[0]])
    pen.poly([b[0], b[1], b[2]])
    for i in (0, 1, 2):
        pen.line(f[i], b[i])
    pen.dim((300, 870), (1100, 870), "6 ft long", offset=(-80, 10))
    pen.text((1150, 700), "2 ft", 64)
    pen.text((150, 620), '30" tall', 64)
    pen.text((300, 150), "raised garden bed", 80)
    pen.text((300, 250), "(wheelchair height)", 56)


def workbench(pen: Pen):
    pen.poly([(300, 450), (1200, 450), (1300, 380), (400, 380), (300, 450)])
    for x in (330, 1170):
        pen.line((x, 450), (x, 950))
    pen.line((1270, 400), (1270, 880))
    pen.line((330, 800), (1170, 800), 4)
    pen.text((500, 200), "workbench", 84)
    pen.dim((300, 1030), (1200, 1030), "48 in", offset=(-40, 5))
    pen.text((1320, 320), "24 deep", 58)
    pen.text((100, 650), "34 high", 58)
    pen.text((520, 830), "shelf", 50)


def step_platform(pen: Pen):
    ground = 900
    pen.line((100, ground), (1500, ground))
    pen.poly([(700, ground), (700, ground - 100), (820, ground - 100), (820, ground - 200), (1300, ground - 200), (1300, ground)])
    pen.dim((1380, ground - 200), (1380, ground), '14"', offset=(15, -30))
    pen.text((150, 200), "STEP PLATFORM", 84)
    pen.text((150, 320), "2 steps up to the back door, 36 in wide", 56)


def not_a_sketch(pen: Pen):
    note(pen, ["Groceries:", "- milk", "- eggs x12", "- bread", "- apples"])


def porch_cluttered(pen: Pen):
    porch(pen, 3, '21"', "12 ft")
    pen.text((1300, 480), 'door 80"', 50)
    pen.text((150, 300), "budget $4000?", 58)
    pen.text((150, 400), "call Dave 613-555-0142", 50)


def porch_corrected(pen: Pen):
    porch(pen, 3, None, "12 ft")
    pen.text((1410, 720), '18"', 60)
    pen.line((1400, 760), (1510, 730), 5)  # crossed out
    pen.text((1410, 800), '21"', 64)


def porch_no_units(pen: Pen):
    porch(pen, 3, "21", "12 ft")


def photo(img: Image.Image, rng: random.Random, harsh: bool) -> Image.Image:
    """Make it look like a phone photo of paper."""
    w, h = img.size
    # uneven lighting / shadow across the page
    shade = Image.linear_gradient("L").resize((w, h)).rotate(rng.uniform(0, 360))
    shade = shade.point(lambda v: 170 + v * (85 / 255) if not harsh else 120 + v * (135 / 255))
    img = Image.composite(img, Image.new("RGB", (w, h), (90, 85, 80)), shade)
    # perspective: map the page to a slightly skewed quad
    d = 0.06 if harsh else 0.03
    jit = lambda: rng.uniform(-d, d)  # noqa: E731
    quad = [(jit() * w, jit() * h), (jit() * w, h + jit() * h), (w + jit() * w, h + jit() * h), (w + jit() * w, jit() * h)]
    img = img.transform((w, h), Image.QUAD, [c for p in quad for c in p], resample=Image.BICUBIC, fillcolor=(60, 55, 50))
    img = img.rotate(rng.uniform(-9, 9) if harsh else rng.uniform(-4, 4), resample=Image.BICUBIC, fillcolor=(60, 55, 50))
    img = img.filter(ImageFilter.GaussianBlur(2.2 if harsh else 1.0))
    # sensor noise
    noise = Image.effect_noise((w, h), 28 if harsh else 14).convert("RGB")
    img = Image.blend(img, noise, 0.10 if harsh else 0.05)
    return img


def paper(rng: random.Random) -> Image.Image:
    base = (rng.randint(236, 250), rng.randint(232, 246), rng.randint(215, 235))
    img = Image.new("RGB", (W, H), base)
    d = ImageDraw.Draw(img)
    if rng.random() < 0.5:  # ruled notebook paper
        for y in range(120, H, 60):
            d.line((0, y, W, y), fill=(170, 195, 225), width=2)
        d.line((110, 0, 110, H), fill=(230, 150, 150), width=2)
    return img


CASE_DEFS = [
    # name, drawer, expected template, expected params {name: (value, tol)}, harsh photo
    ("porch_3steps_21in_12ft", lambda p: porch(p, 3, '21"', "12 ft"), "ramp",
     {"total_rise_in": (21, 1), "available_length_in": (144, 3)}, False),
    ("porch_ftin_labels", lambda p: porch(p, 2, "1'2\"", "12'", 'want it 36" wide'), "ramp",
     {"total_rise_in": (14, 1), "available_length_in": (144, 3), "clear_width_in": (36, 1)}, False),
    ("porch_metric", lambda p: porch(p, 3, "53 cm", "3.6 m"), "ramp",
     {"total_rise_in": (20.9, 1), "available_length_in": (141.7, 4)}, False),
    ("porch_steps_no_numbers", lambda p: porch(p, 3, None, None), "ramp",
     {"total_rise_in": (21, 4)}, False),
    ("porch_harsh_photo", lambda p: porch(p, 3, "24 in", "20 ft"), "ramp",
     {"total_rise_in": (24, 1), "available_length_in": (240, 4)}, True),
    ("ramp_note_list", lambda p: note(p, ["Ramp notes", "porch height 18 in", "yard is 15 ft deep",
                                          "make it 42 in wide", "switchback please"]), "ramp",
     {"total_rise_in": (18, 1), "available_length_in": (180, 3), "clear_width_in": (42, 1), "layout": ("switchback", None)}, False),
    ("porch_width_and_handrails", lambda p: porch(p, 2, "14 in", "12 ft", "36 in wide", "no handrails"), "ramp",
     {"total_rise_in": (14, 1), "available_length_in": (144, 3), "clear_width_in": (36, 1)}, True),
    ("garden_bed", garden_bed, "garden_bed",
     {"length_in": (72, 2), "width_in": (24, 2), "height_in": (30, 1)}, False),
    ("workbench", workbench, "workbench",
     {"width_in": (48, 1), "depth_in": (24, 1), "height_in": (34, 1)}, False),
    ("step_platform", step_platform, "step_platform",
     {"total_rise_in": (14, 1), "width_in": (36, 1)}, False),
    ("not_a_sketch", not_a_sketch, None, {}, False),
    # Harder: stray numbers, a crossed-out correction, a number with no unit, tiny/far, sideways, dark.
    ("porch_cluttered", porch_cluttered, "ramp", {"total_rise_in": (21, 1), "available_length_in": (144, 3)}, False),
    ("porch_crossed_out", porch_corrected, "ramp", {"total_rise_in": (21, 1), "available_length_in": (144, 3)}, False),
    ("porch_rise_no_unit", porch_no_units, "ramp", {"total_rise_in": (21, 1), "available_length_in": (144, 3)}, False),
    ("porch_far_away", lambda p: porch(p, 3, '21"', "12 ft"), "ramp", {"total_rise_in": (21, 1), "available_length_in": (144, 3)}, "far"),
    ("porch_sideways", lambda p: porch(p, 3, '21"', "12 ft"), "ramp", {"total_rise_in": (21, 1), "available_length_in": (144, 3)}, "sideways"),
    ("porch_dark", lambda p: porch(p, 3, '21"', "12 ft"), "ramp", {"total_rise_in": (21, 1), "available_length_in": (144, 3)}, "dark"),
]


def finish(img: Image.Image, mode, rng: random.Random) -> Image.Image:
    """Extra capture problems on top of photo(): far away on a table, rotated 90 degrees, very dark."""
    if mode == "far":
        small = img.resize((W // 3, H // 3), Image.BICUBIC)
        table = Image.new("RGB", (W, H), (120, 90, 60))
        table.paste(small, (rng.randint(200, 800), rng.randint(200, 600)))
        return table
    if mode == "sideways":
        return img.rotate(90, expand=True)
    if mode == "dark":
        return img.point(lambda v: int(v * 0.35))
    return img


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fonts", type=Path, required=True, help="directory with the handwriting .ttf files")
    args = ap.parse_args()
    fonts = sorted(args.fonts.glob("*.ttf"))
    if not fonts:
        raise SystemExit(f"no .ttf fonts in {args.fonts}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rng = random.Random(20260926)
    cases = []
    for i, (name, draw, template, params, harsh) in enumerate(CASE_DEFS):
        font = fonts[i % len(fonts)]
        img = paper(rng)
        draw(Pen(img, font, rng, width=7 if harsh is True else 5))
        img = finish(photo(img, rng, harsh is True), harsh if isinstance(harsh, str) else None, rng)
        rel = f"fixtures/sketches/synthetic/{name}.jpg"
        img.save(REPO / rel, format="JPEG", quality=72 if harsh is True else 85)
        expect_params = {k: ({"value": v} if tol is None else {"value": v, "tol": tol}) for k, (v, tol) in params.items()}
        cases.append({"name": name, "image": rel, "font": font.stem, "expect": {"template": template, "params": expect_params}})
        print(f"wrote {rel} ({font.stem}{', harsh' if harsh else ''})")
    CASES.write_text(json.dumps({
        "description": "Synthetic hand-drawn-style sketches (evals/make_synthetic_sketches.py). A stand-in for real sketches (NC-5).",
        "tolerances_default_in": 1.0,
        "cases": cases,
    }, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {CASES.relative_to(REPO)} ({len(cases)} cases)")


if __name__ == "__main__":
    main()
