"""Work out the kerf and the carriage separation from the recorded calibration runs.

Each run is a folder in calibration/runs/ holding the designs and G-code that were cut and
a record.yaml of the measurements (see the README). The drawn sizes come from rebuilding
each design with the settings it was generated with, so they never have to be copied by hand.

Run from the repository root:  uv run python calibration/analyze.py
"""

import json
from pathlib import Path

import numpy as np
import yaml

from flightlabfoam import settings, toolpath
from flightlabfoam.model import Design

RUNS = Path(__file__).parent / "runs"


def drawn(run: Path, test: dict, s: settings.Settings) -> dict:
    """What was designed, at each carriage end (xy, az).

    chord, thickness: the airfoil as drawn, measured along and across its own chord line.
    comp: the kerf compensation the G-code was made with.
    te: the trailing-edge thickness the design asked for.
    le_depth: the leading edge of the cut path, from the entry face.
    outward: +1 if the void's leading edge lies deeper than the path's, -1 if shallower.
    """
    d = Design.from_dict(json.loads((run / test["design"]).read_text()))
    tp = toolpath.build(d, s, 0, test.get("side", "right"))
    root, tip = tp.placement.root_on, ("az" if tp.placement.root_on == "xy" else "xy")
    trailing_first = d.cut.entry == "trailing"
    out = {"chord": {}, "thickness": {}, "comp": {}, "le_depth": {}, "outward": 1 if trailing_first else -1}
    out["te"] = d.cut.te_min_thickness
    for e, outline, face, comp in (
        (root, tp.ends.nominal_root, tp.face_root, d.cut.kerf_root),
        (tip, tp.ends.nominal_tip, tp.face_tip, d.cut.kerf_tip),
    ):
        out["chord"][e], out["thickness"][e] = _size(outline, tp.ends.nominal_le)
        out["comp"][e] = comp
        out["le_depth"][e] = float(face[:, 0].max() if trailing_first else face[:, 0].min())
    return out


def _size(outline: np.ndarray, le: int) -> tuple[float, float]:
    """Chord and maximum thickness of an outline running trailing edge, upper, leading edge, lower."""
    te = 0.5 * (outline[0] + outline[-1])
    axis = (te - outline[le]) / np.linalg.norm(te - outline[le])
    local = (outline - outline[le]) @ np.array([axis, [-axis[1], axis[0]]]).T
    upper, lower = local[le::-1], local[le:]
    x = np.linspace(0.0, min(upper[-1, 0], lower[-1, 0]), 400)
    return float(np.linalg.norm(te - outline[le])), float(np.max(np.interp(x, *upper.T) - np.interp(x, *lower.T)))


def readings(test: dict, quantity: str, ends: dict) -> dict:
    """Mean of the readings at each end, keyed by carriage (xy, az) instead of the record's labels."""
    return {ends[label]: float(np.mean(v)) for label, v in (test.get(quantity) or {}).items() if v}


def analyze(run: Path) -> dict:
    rec = yaml.safe_load((run / "record.yaml").read_text())
    s = settings.Settings.from_dict(rec["settings"])
    sigma_d = rec["measured_with"]["resolution"] / 2  # one reading, read to the nearest mark
    weight = rec.get("weight", 1.0)

    print(f"\n{run.name}  ({rec['date']}, {rec['measured_with']['tool']}, measured by {rec.get('measured_by') or 'unrecorded'}, weight {weight:g})")
    kerfs, sweeps, depths = [], [], []
    for name, test in rec["tests"].items():
        nom = drawn(run, test, s)
        ends = test.get("ends", rec["block"].get("ends"))
        excluded = test.get("exclude") or {}
        for quantity, why in excluded.items():
            print(f"  {name}: {quantity} left out: {why}")
        get = lambda q: {} if q in excluded else readings(test, q, ends)
        # part = path offset in by the kerf; void = path offset out by it; path = drawn offset out by comp
        k_part = [nom["comp"][e] + (nom["thickness"][e] - t) / 2 for e, t in get("part_thickness").items()]
        k_void = [(t - nom["thickness"][e]) / 2 - nom["comp"][e] for e, t in get("void_thickness").items()]
        kerfs += k_part + k_void
        chord_loss = [nom["chord"][e] - c for e, c in get("part_chord").items()]
        print(
            f"  {name}: drawn {_list(nom['chord'].values())} x {_list(nom['thickness'].values())} mm, trailing edge "
            f"{nom['te']:g} mm, kerf compensation {_list(nom['comp'].values())}; kerf from part thickness "
            f"{_list(k_part)}, from void thickness {_list(k_void)}; part chord short by {_list(chord_loss)} mm, "
            f"trailing edge {_list(get('part_te_thickness').values())} mm"
        )
        d = get("le_depth")
        if test.get("le_depth_from") == "back":  # measured from the face opposite the entry
            d = {e: rec["block"]["size"]["front_to_back"] - v for e, v in d.items()}
        if len(d) == 2:
            sweeps.append((nom["le_depth"]["xy"] - nom["le_depth"]["az"], d["xy"] - d["az"]))
        depths += [(name, e, v, nom["le_depth"][e], nom["outward"]) for e, v in d.items()]

    out = {"run": run.name, "weight": weight}
    if kerfs:
        out["kerf"] = float(np.mean(kerfs))
        print(f"  kerf: {out['kerf']:.2f} mm (mean of {len(kerfs)}; range {min(kerfs):.2f} to {max(kerfs):.2f})")
    for name, e, got, path, outward in depths:
        want = path + outward * out.get("kerf", 0.0)
        print(f"  {name} leading edge at the {e.upper()} end: {got:.1f} mm from the entry face, expected {want:.1f} (shallower by {want - got:.1f})")

    x = np.array([p[0] for p in sweeps])
    if len(x) >= 2 and np.ptp(x) > 1.0:
        # measured difference = scale * drawn difference + skew; the scale is D_set / D_true
        y = np.array([p[1] for p in sweeps])
        xc = x - x.mean()
        scale = float(xc @ (y - y.mean()) / (xc @ xc))
        skew = float(y.mean() - scale * x.mean())
        sigma = np.sqrt(2) * sigma_d / np.sqrt(xc @ xc)  # each difference is two readings
        D = s.machine.carriage_separation
        out["separation"], out["separation_sigma"] = D / scale, D * sigma / scale**2
        print(
            f"  sweep scale {scale:.4f} +/- {sigma:.4f}, skew {skew:+.1f} mm; carriage separation "
            f"{out['separation']:.1f} +/- {out['separation_sigma']:.1f} mm (set to {D:.1f})"
        )
    return out


def _list(values) -> str:
    return ", ".join(f"{v:.2f}" for v in values) or "-"


def main() -> None:
    results = [analyze(run) for run in sorted(p for p in RUNS.iterdir() if (p / "record.yaml").exists())]
    used = [r for r in results if r["weight"] > 0]
    kerf = [(r["kerf"], r["weight"]) for r in used if "kerf" in r]
    sep = [(r["separation"], r["separation_sigma"] / np.sqrt(r["weight"])) for r in used if "separation" in r]
    print(f"\nAll runs ({len(used)} of {len(results)} used, weighted):")
    if kerf:
        v, w = np.array(kerf).T
        print(f"  kerf {w @ v / w.sum():.2f} mm")
    if sep:
        v, sd = np.array(sep).T
        w = 1 / sd**2
        print(f"  carriage separation {w @ v / w.sum():.1f} +/- {1 / np.sqrt(w.sum()):.1f} mm")


if __name__ == "__main__":
    main()
