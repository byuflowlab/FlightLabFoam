"""Sanity checks on a toolpath before it reaches the machine.

Each check returns ``{"level": "error" | "warning" | "info", "message": ...}``. An
error stops G-code generation; a warning is shown but does not.
"""

from __future__ import annotations

import numpy as np

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
            warn(f"the {name} carriage goes to {h} = {pts[:, 0].min():.1f} mm, behind the entry face")
        if pts[:, 0].max() > m.travel_horizontal + _TOL:
            error(f"the {name} carriage needs {h} = {pts[:, 0].max():.1f} mm but travels only {m.travel_horizontal:g} mm")
        if pts[:, 1].min() < -_TOL:
            error(f"the {name} carriage goes to {v} = {pts[:, 1].min():.1f} mm, below the bottom of the block")
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
    if tp.feed.max() > m.max_feed:
        warn(f"F reaches {tp.feed.max():.0f} mm/min, above the machine limit of {m.max_feed:g} mm/min")
    if cut.kerf_root == 0 and cut.kerf_tip == 0:
        out.append({"level": "info", "message": "kerf is zero, so the part will come out slightly undersize"})

    for w in tp.warnings:
        warn(w)
    return out


def has_errors(results: list[dict]) -> bool:
    return any(r["level"] == "error" for r in results)
