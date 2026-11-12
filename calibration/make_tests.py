"""Build the calibration cuts: three panels per foam block.

Blocks 1 and 2 stack the same three panels in their thickness, each running the block's
full length along the wire, all at F120 (85 mm/min per carriage on this machine):

* A, straight: measures kerf, and whether the entry face is square to the wire.
* B, swept aft by 100 mm, and C, swept forward by 100 mm: together they measure the
  carriage separation. Both are untapered, so the two ends of the wire move at the same
  speed and melt the same amount; comparing B with C also cancels any skew of the block.

Block 1 has kerf compensation off, to measure the raw kerf, and the default 0.5 mm
trailing edge. Its parts lost the tail back to where they were under about 1 mm thick,
so block 2 cuts with the measured kerf compensated and a thicker trailing edge on each
panel (1, 2 and 3 mm), to find the thinnest edge that survives. It also repeats the
separation measurement, which kerf does not affect.

Block 3 measures how kerf depends on wire speed, in two rounds:

* Round 1, A and B: straight panels at 50 and 140 mm/min. Untapered, so each is one clean
  kerf reading at one speed, to go with the 85 mm/min of blocks 1 and 2.
* Round 2, C: a tapered panel, whose two ends run at different speeds (about 36 and
  64 mm/min). It is built only once round 1 has been measured, with the root and tip kerf
  that the fit suggests, so it both validates the fit and adds two more points:
  uv run python calibration/make_tests.py --taper-kerf ROOT TIP

All of block 3 is NACA 0012 at 80 mm chord, with a long thin aft part like the student
tails, so the parts' thickness can also be read at several chord stations to see whether
thin foam melts more than thick foam at the same speed.

Run from the repository root:  uv run python calibration/make_tests.py
It writes a project file (open it in the app) and a G-code file per test, prefixed with
the block's name.
"""

import argparse
import json
from pathlib import Path

from flightlabfoam import checks, postprocess, settings, toolpath
from flightlabfoam.model import Block, Design, Section

HERE = Path(__file__).parent
FEED = 85.0  # mm/min per carriage: F120 with the controller applying F over all four axes

# Blocks 1 and 2: NACA 0015 at 50 mm chord (7.5 mm thick); a straight and two swept panels
BLOCKS = {  # mm: along the wire, front to back, tall
    "block1": dict(span=445.0, chord=205.0, thickness=50.8),
    "block2": dict(span=457.0, chord=200.0, thickness=50.8),
}
CUT = {  # per block: kerf compensation (mm), and trailing-edge thickness (mm) for tests A, B, C
    "block1": dict(kerf=0.0, te=(0.5, 0.5, 0.5)),
    "block2": dict(kerf=0.9, te=(1.0, 2.0, 3.0)),
}
AIRFOIL, CHORD = "naca0015", 50.0
SWEEP = 100.0  # leading-edge offset of the tip end for tests B and C
CUT_IN = 45.0  # keeps both carriages ahead of program zero on the swept panels
TESTS = [  # name, tip sweep (mm), panel centre above the block's centre (mm)
    ("test-A-straight", 0.0, 15.0),  # top
    ("test-B-sweep-aft", SWEEP, 0.0),  # middle
    ("test-C-sweep-forward", -SWEEP, -15.0),  # bottom
]

# Block 3: kerf against wire speed
BLOCK3 = dict(span=305.0, chord=165.0, thickness=50.8)
B3_AIRFOIL, B3_CHORD = "naca0012", 80.0  # 9.6 mm thick
B3_KERF, B3_TE, B3_CUT_IN = 0.9, 1.0, 20.0  # kerf compensation of the straight panels, as block 2
B3_SPEEDS = [  # round 1: name, mm/min per carriage, panel centre above the block's centre (mm)
    ("test-A-slow", 50.0, 15.0),  # top
    ("test-B-fast", 140.0, 0.0),  # middle
]
B3_TAPER = dict(name="test-C-taper", root=80.0, tip=45.0, offset=-15.0)  # round 2, bottom; faster carriage at FEED


def design(name: str, block: dict, sweep: float, offset: float, kerf: float, te: float) -> Design:
    d = Design(name=name, symmetric=False)
    d.sections = [Section(AIRFOIL, CHORD, 0.0), Section(AIRFOIL, CHORD, block["span"], x_le=sweep)]
    d.blocks = [Block(auto=False, cut_in=CUT_IN, vertical_offset=offset, **block)]
    d.cut.feed = FEED
    d.cut.kerf_root = d.cut.kerf_tip = kerf
    d.cut.te_min_thickness = te
    # cut before the minimum thickness existed, with the tail thickened upward over whatever length it needed
    d.cut.min_thickness = 0.0
    d.cut.thicken_surface = "upper"
    d.cut.te_extent = 1.0
    d.cut.comment_header = True
    return d


def block3_design(name: str, root: float, tip: float, offset: float, feed: float, kerf_root: float, kerf_tip: float) -> Design:
    """A block 3 panel, with the root at the X/Y end; the tip leading edge is set back to centre the taper."""
    d = Design(name=name, symmetric=False)
    span = BLOCK3["span"]
    d.sections = [Section(B3_AIRFOIL, root, 0.0), Section(B3_AIRFOIL, tip, span, x_le=(root - tip) / 2)]
    d.blocks = [Block(auto=False, cut_in=B3_CUT_IN, vertical_offset=offset, **BLOCK3)]
    d.cut.feed = feed
    d.cut.kerf_root, d.cut.kerf_tip = kerf_root, kerf_tip
    d.cut.te_min_thickness = B3_TE
    d.cut.comment_header = True
    return d


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--taper-kerf", nargs=2, type=float, metavar=("ROOT", "TIP"), help="build block 3's tapered panel with this kerf compensation (mm)")
    args = p.parse_args()
    s = settings.load()
    for block_name, block in BLOCKS.items():
        cut = CUT[block_name]
        for (test, sweep, offset), te in zip(TESTS, cut["te"]):
            write(s, design(f"{block_name}-{test}", block, sweep, offset, cut["kerf"], te))
    for test, feed, offset in B3_SPEEDS:
        write(s, block3_design(f"block3-{test}", B3_CHORD, B3_CHORD, offset, feed, B3_KERF, B3_KERF))
    if args.taper_kerf:
        t = B3_TAPER
        write(s, block3_design(f"block3-{t['name']}", t["root"], t["tip"], t["offset"], FEED, *args.taper_kerf))
    else:
        print("block3-test-C-taper: not built; measure round 1, then rerun with --taper-kerf ROOT TIP")


def write(s, d: Design) -> None:
    name = d.name
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
        f"{name}: {d.cut.feed:g} mm/min, kerf {d.cut.kerf_root:g}/{d.cut.kerf_tip:g}, trailing edge {d.cut.te_min_thickness:g} mm; "
        f"part Y {y.min():.1f}-{y.max():.1f} mm; leading edge {root_far:.1f} mm from the entry face at the X/Y end, "
        f"{tip_far:.1f} mm at the A/Z end; about {tp.total_seconds / 60:.1f} min"
    )


if __name__ == "__main__":
    main()
