"""Build the calibration cuts: three panels per foam block, for blocks 1 and 2.

In each block, three panels are stacked in its thickness, each running the block's full
length along the wire, all at F120 (85 mm/min per carriage on this machine):

* A, straight: measures kerf, and whether the entry face is square to the wire.
* B, swept aft by 100 mm, and C, swept forward by 100 mm: together they measure the
  carriage separation. Both are untapered, so the two ends of the wire move at the same
  speed and melt the same amount; comparing B with C also cancels any skew of the block.

Block 1 has kerf compensation off, to measure the raw kerf, and the default 0.5 mm
trailing edge. Its parts lost the tail back to where they were under about 1 mm thick,
so block 2 cuts with the measured kerf compensated and a thicker trailing edge on each
panel (1, 2 and 3 mm), to find the thinnest edge that survives. It also repeats the
separation measurement, which kerf does not affect.

Run from the repository root:  uv run python calibration/make_tests.py
It writes a project file (open it in the app) and a G-code file per test, prefixed with
the block's name.
"""

import json
from pathlib import Path

from flightlabfoam import checks, postprocess, settings, toolpath
from flightlabfoam.model import Block, Design, Section

HERE = Path(__file__).parent
BLOCKS = {  # mm: along the wire, front to back, tall
    "block1": dict(span=445.0, chord=205.0, thickness=50.8),
    "block2": dict(span=457.0, chord=200.0, thickness=50.8),
}
CUT = {  # per block: kerf compensation (mm), and trailing-edge thickness (mm) for tests A, B, C
    "block1": dict(kerf=0.0, te=(0.5, 0.5, 0.5)),
    "block2": dict(kerf=0.9, te=(1.0, 2.0, 3.0)),
}
AIRFOIL, CHORD = "naca0015", 50.0  # 7.5 mm thick
SWEEP = 100.0  # leading-edge offset of the tip end for tests B and C
CUT_IN = 45.0  # keeps both carriages ahead of program zero on the swept panels
FEED = 85.0  # mm/min per carriage: F120 with the controller applying F over all four axes
TESTS = [  # name, tip sweep (mm), panel centre above the block's centre (mm)
    ("test-A-straight", 0.0, 15.0),  # top
    ("test-B-sweep-aft", SWEEP, 0.0),  # middle
    ("test-C-sweep-forward", -SWEEP, -15.0),  # bottom
]


def design(name: str, block: dict, sweep: float, offset: float, kerf: float, te: float) -> Design:
    d = Design(name=name, symmetric=False)
    d.sections = [Section(AIRFOIL, CHORD, 0.0), Section(AIRFOIL, CHORD, block["span"], x_le=sweep)]
    d.blocks = [Block(auto=False, cut_in=CUT_IN, vertical_offset=offset, **block)]
    d.cut.feed = FEED
    d.cut.kerf_root = d.cut.kerf_tip = kerf
    d.cut.te_min_thickness = te
    d.cut.comment_header = True
    return d


def main() -> None:
    s = settings.load()
    for block_name, block in BLOCKS.items():
        cut = CUT[block_name]
        for (test, sweep, offset), te in zip(TESTS, cut["te"]):
            build(s, f"{block_name}-{test}", block, sweep, offset, cut["kerf"], te)


def build(s, name: str, block: dict, sweep: float, offset: float, kerf: float, te: float) -> None:
    d = design(name, block, sweep, offset, kerf, te)
    tp = toolpath.build(d, s, 0, "right")
    problems = [c["message"] for c in checks.check(tp, d, s) if c["level"] != "info" and "trailing edge" not in c["message"]]
    if problems:
        raise SystemExit(f"{name}: {problems}")
    (HERE / f"{name}.foam.json").write_text(json.dumps(d.to_dict(), indent=2))
    with open(HERE / f"{name}.nc", "w", newline="") as f:
        f.write(postprocess.gcode(tp, d, s))
    cut = [k == "cut" for k in tp.kind]
    root_far, tip_far = (face[:, 0].max() for face in (tp.face_root, tp.face_tip))
    y = tp.root[cut, 1]
    print(
        f"{name}: kerf {kerf:g}, trailing edge {te:g} mm; part Y {y.min():.1f}-{y.max():.1f} mm; leading edge {root_far:.1f} mm from the entry face "
        f"at the X/Y end, {tip_far:.1f} mm at the A/Z end; about {tp.total_seconds / 60:.1f} min"
    )


if __name__ == "__main__":
    main()
