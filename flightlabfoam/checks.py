"""Sanity checks on a toolpath before it reaches the machine.

Each check returns ``{"level": "error" | "warning" | "info", "message": ...}``. An
error stops G-code generation; a warning is shown but does not.
"""

from __future__ import annotations

import numpy as np

from .geometry import SIDE_NAME, PanelEnds
from .model import Design
from .settings import Settings
from .toolpath import Toolpath

_TOL = 1e-6


def check(tp: Toolpath, design: Design, settings: Settings) -> list[dict]:
    out: list[dict] = []

    def error(msg):
        out.append({"level": "error", "message": msg})

    def warn(msg):
        out.append({"level": "warning", "message": msg})

    m, pl, b = settings.machine, tp.placement, tp.placement.block
    span = tp.ends.span

    if span >= m.carriage_separation:
        error(f"the panel ({span:.1f} mm) is longer than the carriage separation ({m.carriage_separation:.1f} mm)")
    if b.span + _TOL < span:
        error(f"the block ({b.span:.1f} mm) is shorter than the panel span ({span:.1f} mm)")
    lo, hi = sorted(pl.w_block)
    if b.machine_x < 0:
        error("the block's entry face is behind program zero, so the wire would start inside the foam; use a distance of 0 or more")
    if lo < -_TOL or hi > m.carriage_separation + _TOL:
        error("the block does not fit between the carriages; reduce its span or its offset between the carriages")
    if b.span + _TOL >= span:
        p_lo, p_hi = sorted((pl.w_root, pl.w_tip))
        if p_lo < lo - _TOL or p_hi > hi + _TOL:
            error("the panel extends past the end of the block; check the span offset")

    faces = np.vstack([tp.face_root, tp.face_tip])
    if faces[:, 0].max() > b.chord + _TOL:
        error(f"the panel extends {faces[:, 0].max() - b.chord:.1f} mm past the back of the block; lengthen the block or reduce the cut-in")
    if faces[:, 1].min() < -_TOL:
        error(f"the panel extends {-faces[:, 1].min():.1f} mm below the block; raise it or use thicker foam")
    if faces[:, 1].max() > b.thickness + _TOL:
        error(f"the panel extends {faces[:, 1].max() - b.thickness:.1f} mm above the block; lower it or use thicker foam")

    for name, pts, h, v in (("X/Y", tp.xy, "X", "Y"), ("A/Z", tp.az, "A", "Z")):
        if pts[:, 0].min() < -_TOL:
            warn(f"the {name} carriage goes to {h} = {pts[:, 0].min():.1f} mm, behind program zero")
        if pts[:, 0].max() > m.travel_horizontal + _TOL:
            error(f"the {name} carriage needs {h} = {pts[:, 0].max():.1f} mm but travels only {m.travel_horizontal:g} mm")
        low = float(pts[:, 1].min())
        if low < -m.max_below_zero - _TOL:
            error(
                f"the {name} carriage goes to {v} = {low:.1f} mm, more than the {m.max_below_zero:g} mm "
                "allowed below program zero"
            )
        elif low < -_TOL:
            warn(f"the {name} carriage goes to {v} = {low:.1f} mm, below program zero; check it has room to go there")
        if pts[:, 1].max() > m.travel_vertical + _TOL:
            error(f"the {name} carriage needs {v} = {pts[:, 1].max():.1f} mm but travels only {m.travel_vertical:g} mm")

    cutting = np.array([k in ("lead_in", "cut") for k in tp.kind])
    for name, pts in (("X/Y", tp.xy), ("A/Z", tp.az)):
        extent = float(np.ptp(pts[cutting, 0]))
        smallest = min(design.sections[tp.panel].chord, design.sections[tp.panel + 1].chord)
        if extent < 0.25 * smallest:
            warn(
                f"at the {name} carriage the wire traces an outline only {extent:.0f} mm long; the panel is very "
                "tapered for this carriage separation, so check the cut carefully"
            )

    cut = design.cut
    # judge the carriages' real speeds, not F: how F maps to them depends on the feed model
    minutes = np.maximum(tp.seconds / 60.0, 1e-12)
    prev = lambda a: np.vstack([[0.0, 0.0], a[:-1]])
    speed = np.maximum(np.linalg.norm(tp.xy - prev(tp.xy), axis=1), np.linalg.norm(tp.az - prev(tp.az), axis=1)) / minutes
    if speed.max() > m.max_feed:
        warn(f"a carriage reaches {speed.max():.0f} mm/min, above the machine limit of {m.max_feed:g} mm/min")
    te = max(cut.te_min_thickness, cut.min_thickness)  # the minimum thickness also holds the tail up
    if te < m.min_te_thickness - _TOL:
        warn(
            f"the trailing edge is only {te:g} mm thick; on this machine an edge thinner than "
            f"{m.min_te_thickness:g} mm tends to melt away and shorten the chord (Cutting settings)"
        )
    elif te > m.max_te_thickness + _TOL:
        warn(
            f"the trailing edge is {te:g} mm thick; above {m.max_te_thickness:g} mm it starts "
            "to look blunt (Cutting settings)"
        )
    if cut.kerf_root == 0 and cut.kerf_tip == 0:
        out.append({"level": "info", "message": "kerf is zero, so the part will come out slightly undersize"})

    for w in feature_checks(tp.ends, m.min_wall_thickness):
        warn(w)
    for w in tp.warnings:
        warn(w)
    return out


def has_errors(results: list[dict]) -> bool:
    return any(r["level"] == "error" for r in results)


def feature_checks(ends: PanelEnds, min_wall: float) -> list[str]:
    """Warnings for spars, holes and hinge cuts that break a skin, crowd it, or meet each other.

    Every feature's nominal outline is checked at the root and the tip; the panel is a
    straight-line blend of the two. Features may intersect each other, which is reported
    but allowed. Each finding is reported once, at whichever ends it occurs.
    """
    found: dict[tuple, dict] = {}

    def note(key, k, value, text):
        f = found.setdefault(key, {"ends": set(), "value": value, "text": text})
        f["ends"].add(k)
        if value is not None and value < f["value"]:
            f["value"] = value

    for k, (skins, shapes) in enumerate(zip(ends.skins, ends.shapes)):
        skin = dict(zip(("upper", "lower"), skins))
        dense = [_densify(sh.points, closed=sh.kind != "cut") for sh in shapes]

        for sh, pts in zip(shapes, dense):
            if sh.kind == "cut":
                continue  # a hinge cut goes through the wing on purpose
            if sh.kind == "slot":
                # a slot is open to its entry skin; only the far skin can be crowded or broken
                mouth = np.abs(pts[:, 1] - np.interp(pts[:, 0], *skin[sh.surface].T)) < 1e-6
                pts = pts[~mouth]
                sides = ["lower" if sh.surface == "upper" else "upper"]
            else:
                sides = ["upper", "lower"]
            for side in sides:
                s_y = np.interp(pts[:, 0], *skin[side].T)
                beyond = pts[:, 1] > s_y + 1e-6 if side == "upper" else pts[:, 1] < s_y - 1e-6
                if beyond.any():
                    note(("through", sh.label, side), k, None, f"the {sh.label} breaks through the {SIDE_NAME[side]} surface")
                else:
                    d = float(_distance(pts, skin[side]).min())
                    if d < min_wall:
                        note(("skin", sh.label, side), k, d, f"between the {sh.label} and the {SIDE_NAME[side]} surface")

        for i in range(len(shapes)):
            for j in range(i + 1, len(shapes)):
                a, b = shapes[i], shapes[j]
                if a.kind == "cut" and b.kind == "cut":
                    continue
                pa, pb = dense[i], dense[j]
                d = min(float(_distance(pa, pb).min()), float(_distance(pb, pa).min()))
                hit = d < 1e-6
                if b.kind != "cut":
                    hit = hit or bool(_inside(pa, pb).any())
                if a.kind != "cut":
                    hit = hit or bool(_inside(pb, pa).any())
                if hit:
                    note(("hit", a.label, b.label), k, None, f"the {a.label} and the {b.label} intersect")
                elif d < min_wall:
                    note(("pair", a.label, b.label), k, d, f"between the {a.label} and the {b.label}")

    out = []
    for key, f in found.items():
        where = "at both ends" if len(f["ends"]) == 2 else f"at the {('root', 'tip')[next(iter(f['ends']))]}"
        if key[0] == "through":
            out.append(f"{f['text']} {where}")
        elif key[0] == "hit":
            out.append(f"{f['text']} {where}; that is allowed, but check it is what you want")
        else:
            out.append(f"only {f['value']:.1f} mm of foam {f['text']} {where} (minimum {min_wall:g} mm)")
    return out


def _densify(pts: np.ndarray, closed: bool, step: float = 0.25) -> np.ndarray:
    """Add points along each segment so none is longer than ``step`` mm."""
    if closed and not np.allclose(pts[0], pts[-1]):
        pts = np.vstack([pts, pts[:1]])
    out = [pts[:1]]
    for p, q in zip(pts[:-1], pts[1:]):
        m = max(1, int(np.ceil(np.linalg.norm(q - p) / step)))
        t = np.linspace(0.0, 1.0, m + 1)[1:, None]
        out.append(p + (q - p) * t)
    return np.vstack(out)


def _distance(pts: np.ndarray, line: np.ndarray) -> np.ndarray:
    """Distance from each point to the nearest point of a polyline."""
    a, b = line[:-1], line[1:]
    ab = b - a
    t = np.einsum("psk,sk->ps", pts[:, None, :] - a[None], ab) / np.maximum(np.einsum("sk,sk->s", ab, ab), 1e-300)
    proj = a[None] + np.clip(t, 0.0, 1.0)[..., None] * ab[None]
    return np.linalg.norm(pts[:, None, :] - proj, axis=2).min(axis=1)


def _inside(pts: np.ndarray, poly: np.ndarray) -> np.ndarray:
    """Even-odd test: which points lie inside a closed polygon."""
    x, y = pts[:, :1], pts[:, 1:]
    x1, y1 = poly[:, 0], poly[:, 1]
    x2, y2 = np.roll(x1, -1), np.roll(y1, -1)
    crosses = ((y1 > y) != (y2 > y)) & (x < (x2 - x1) * (y - y1) / np.where(y2 == y1, 1e-300, y2 - y1) + x1)
    return crosses.sum(axis=1) % 2 == 1
