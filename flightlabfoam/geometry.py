"""Matched root and tip outlines for one panel.

A hot wire cuts a ruled surface: point *i* of the root outline and point *i* of the tip
outline lie on the same wire line. :func:`panel_ends` builds the two outlines with
the same number of points, in the same order, at the same fraction of the chord.

The steps, all at the panel ends (not at the carriages):

1. Sample both airfoils at shared cosine-spaced chord stations, separately for the
   upper and lower surfaces. Feature boundaries (spar slots, holes, hinge cuts) become
   stations at both ends; the stations between them are warped piecewise-linearly so
   a slot that is 6 mm wide at both ends lands exactly even though the chords differ.
2. Scale by chord and thicken the trailing edge to the minimum thickness.
3. Offset the outline outward by the kerf so the finished part keeps its size.
4. Insert the feature cuts, already kerf-compensated.
5. Rotate by twist about the leading edge and shift by the sweep offset.

Projection to the carriages is linear along each wire line and happens later, in
:mod:`flightlabfoam.toolpath`.

Each outline runs in Selig order: trailing edge (upper), over the upper surface to
the leading edge, then along the lower surface to the trailing edge (lower).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from . import airfoil
from .model import ControlCut, Design, Hole, Spar

ARC_POINTS = 24  # segments in a full circle; half that for a U slot bottom
_EDGE_CLEARANCE = 0.01  # feature boundaries must stay this far (x/c) from the LE and TE


@dataclass
class PanelEnds:
    root: np.ndarray  # (m, 2) cut outline at the wing root, panel frame, mm
    tip: np.ndarray  # (m, 2) cut outline at the wing tip
    le_index: int
    span: float
    nominal_root: np.ndarray  # airfoil outline without kerf or features, for drawing
    nominal_tip: np.ndarray
    warnings: list[str] = field(default_factory=list)

    def at(self, t: float) -> np.ndarray:
        """Outline on the wire lines at fraction ``t`` of the span (0 root, 1 tip; may extrapolate)."""
        return self.root + (self.tip - self.root) * t


@dataclass
class _End:
    surf: airfoil.Surfaces
    chord: float
    kerf: float
    x_le: float
    twist: float
    te_min: float


@dataclass
class _Event:
    """A feature on one surface, with its chord-fraction boundaries at each end."""

    a: tuple[float, float]  # (root, tip) start, x/c
    b: tuple[float, float]  # (root, tip) end, x/c; equal to a for a slit
    feature: object

    @property
    def slit(self) -> bool:
        return self.a == self.b


def panel_ends(design: Design, panel: int) -> PanelEnds:
    if not 0 <= panel < design.n_panels:
        raise ValueError(f"there is no panel {panel + 1}")
    s_root, s_tip = design.sections[panel], design.sections[panel + 1]
    cut = design.cut
    ends = [
        _End(
            airfoil.Surfaces.from_coords(airfoil.load(s.airfoil, design.airfoils)),
            s.chord,
            kerf,
            s.x_le,
            s.twist,
            cut.te_min_thickness,
        )
        for s, kerf in ((s_root, cut.kerf_root), (s_tip, cut.kerf_tip))
    ]
    warnings: list[str] = []
    features = design.features_for(panel)
    events = {"upper": [], "lower": []}
    for f in features:
        events[f.surface].append(_event(f, ends))
    for side in events:
        events[side].sort(key=lambda e: e.a[0])

    n = cut.points_per_surface
    loops, nominals = [], []
    for k, end in enumerate(ends):
        upper, up_marks = _sample(end, "upper", events["upper"], k, n)
        lower, lo_marks = _sample(end, "lower", events["lower"], k, n)
        base = np.vstack([upper[::-1], lower[1:]])
        nominals.append(_place(base, end))
        off = _offset(base, end.kerf)
        m_u = len(upper)
        up_off = off[:m_u][::-1]
        lo_off = off[m_u - 1 :]
        up_final = _insert(up_off, up_marks, events["upper"], end, k, "upper", warnings)
        lo_final = _insert(lo_off, lo_marks, events["lower"], end, k, "lower", warnings)
        loop = np.vstack([up_final[::-1], lo_final[1:]])
        loops.append((_place(loop, end), len(up_final) - 1))

    (root, le_r), (tip, le_t) = loops
    assert root.shape == tip.shape and le_r == le_t, "root and tip outlines must match point for point"
    return PanelEnds(
        root=root,
        tip=tip,
        le_index=le_r,
        span=s_tip.span_pos - s_root.span_pos,
        nominal_root=nominals[0],
        nominal_tip=nominals[1],
        warnings=list(dict.fromkeys(warnings)),
    )


def _place(loop: np.ndarray, end: _End) -> np.ndarray:
    """Twist about the leading edge (positive nose up), then shift by the sweep offset."""
    a = np.radians(end.twist)
    rot = np.array([[np.cos(a), np.sin(a)], [-np.sin(a), np.cos(a)]])  # clockwise = nose up
    out = loop @ rot.T
    out[:, 0] += end.x_le
    return out


def _event(f, ends: list[_End]) -> _Event:
    """Chord-fraction boundaries of a feature at the root and the tip."""
    a, b = [], []
    for end in ends:
        c = end.chord
        if isinstance(f, Spar) and f.kind in ("rect", "u"):
            lo, hi = f.x_c - f.width / (2 * c), f.x_c + f.width / (2 * c)
        elif isinstance(f, ControlCut):
            lo, hi = f.hinge_x_c - f.gap / (2 * c), f.hinge_x_c + f.gap / (2 * c)
        else:  # round spar or hole: a slit at the centre
            lo = hi = f.x_c
        if lo < _EDGE_CLEARANCE or hi > 1 - _EDGE_CLEARANCE:
            raise ValueError(f"{_label(f)} at x/c = {f.x_c if not isinstance(f, ControlCut) else f.hinge_x_c:g} runs off the airfoil")
        a.append(lo)
        b.append(hi)
    return _Event(tuple(a), tuple(b), f)


def _label(f) -> str:
    if isinstance(f, Spar):
        return {"rect": "square spar", "u": "U spar", "round": "round spar"}.get(f.kind, "spar")
    if isinstance(f, Hole):
        return "lightening hole"
    return f"{f.kind} cut"


def _sample(end: _End, side: str, events: list[_Event], k: int, n: int):
    """Points along one surface, LE -> TE, in mm; plus the station index of each event start.

    Reference stations are cosine spaced. Event boundaries are added at the mean of
    their root and tip positions, stations inside an event are dropped, and the
    stations are then warped so each boundary lands at this end's own position.
    """
    s = airfoil.cosine_stations(n)
    ref_knots, end_knots = [0.0], [0.0]
    extra = []
    for e in events:
        a_ref = 0.5 * (e.a[0] + e.a[1])
        b_ref = 0.5 * (e.b[0] + e.b[1])
        gap = 0.5 / n
        s = s[(s < a_ref - gap) | (s > b_ref + gap)]
        extra.append(a_ref)
        ref_knots.append(a_ref)
        end_knots.append(e.a[k])
        if not e.slit:
            extra.append(b_ref)
            ref_knots.append(b_ref)
            end_knots.append(e.b[k])
    ref_knots.append(1.0)
    end_knots.append(1.0)
    if np.any(np.diff(ref_knots) <= 0) or np.any(np.diff(end_knots) <= 0):
        raise ValueError(f"features on the {side} surface overlap; move them apart")

    s = np.sort(np.concatenate([s, extra]))
    x = np.interp(s, ref_knots, end_knots)
    surf = end.surf
    y = surf.upper(x) if side == "upper" else surf.lower(x)
    if side == "upper" and end.te_min > 0:
        aft = x >= 0.5
        y = np.where(aft, np.maximum(y, surf.lower(x) + end.te_min / end.chord), y)
    marks = [int(np.searchsorted(s, 0.5 * (e.a[0] + e.a[1]))) for e in events]
    return np.column_stack([x, y]) * end.chord, marks


def _offset(loop: np.ndarray, d: float) -> np.ndarray:
    """Offset a closed outline outward by ``d`` with mitred corners (miter capped at 3d)."""
    if d == 0:
        return loop.copy()
    seg = np.roll(loop, -1, axis=0) - loop  # segment i runs from point i to i + 1 (closing at the TE)
    length = np.linalg.norm(seg, axis=1)
    normal = np.column_stack([seg[:, 1], -seg[:, 0]]) / np.maximum(length, 1e-12)[:, None]
    # a zero-length segment (a closed trailing edge) borrows its neighbour's normal
    for i in np.flatnonzero(length < 1e-9):
        normal[i] = normal[i - 1]
    area = 0.5 * np.sum(loop[:, 0] * np.roll(loop[:, 1], -1) - np.roll(loop[:, 0], -1) * loop[:, 1])
    if area < 0:
        normal = -normal
    n_in, n_out = np.roll(normal, 1, axis=0), normal
    bis = n_in + n_out
    norm = np.linalg.norm(bis, axis=1)
    bis = np.where((norm < 1e-9)[:, None], n_out, bis / np.maximum(norm, 1e-12)[:, None])
    cos = np.maximum(np.sum(bis * n_out, axis=1), 1 / 3)
    return loop + d * bis / cos[:, None]


def _insert(surface, marks, events, end: _End, k: int, side: str, warnings: list[str]) -> np.ndarray:
    """Insert each event's cut after its start station on a LE -> TE surface."""
    pieces, last = [], 0
    for mark, e in zip(marks, events):
        pieces.append(surface[last : mark + 1])
        anchor = surface[mark]
        pieces.append(np.asarray(_excursion(e, anchor, end, k, side, warnings), dtype=float).reshape(-1, 2))
        last = mark + 1
    pieces.append(surface[last:])
    return np.vstack(pieces)


def _excursion(e: _Event, anchor, end: _End, k: int, side: str, warnings: list[str]):
    """Points of a feature cut, in LE -> TE order, between its start and end stations.

    ``s_in`` points into the wing from the entry surface. Every cut is drawn so that
    wing material stays on the same side of the wire as along the outline, so the
    kerf compensation shrinks slots and holes (the wire widens them back).
    """
    f, c, kerf, surf = e.feature, end.chord, end.kerf, end.surf
    s_in = -1.0 if side == "upper" else 1.0
    entry = surf.upper if side == "upper" else surf.lower
    other = surf.lower if side == "upper" else surf.upper

    if isinstance(f, Spar) and f.kind in ("rect", "u"):
        xc = f.x_c * c
        xa, xb = e.a[k] * c + kerf, e.b[k] * c - kerf
        y_bottom = entry(f.x_c) * c + s_in * (f.depth - kerf)
        thick = surf.thickness(f.x_c) * c
        if f.depth >= thick:
            warnings.append(f"{_label(f)} is {f.depth:g} mm deep but the airfoil is only {thick:.1f} mm thick there")
        top = anchor[1]
        if f.kind == "rect":
            return [(xa, top), (xa, y_bottom), (xb, y_bottom), (xb, top)]
        r = (xb - xa) / 2
        yc = y_bottom - s_in * r
        theta = np.pi - s_in * np.pi * np.arange(0, ARC_POINTS // 2 + 1) / (ARC_POINTS // 2)
        arc = np.column_stack([xc + r * np.cos(theta), yc + r * np.sin(theta)])
        return [(xa, top), *map(tuple, arc), (xb, top)]

    if isinstance(f, ControlCut):
        xh = f.hinge_x_c * c
        apex = (xh, other(f.hinge_x_c) * c + s_in * kerf)
        return [apex] if not e.slit else [apex, tuple(anchor)]

    # round spar or lightening hole: entry slit from the surface, then a full circle
    r = f.diameter / 2 - kerf
    xc = f.x_c * c
    yc = 0.5 * (surf.upper(f.x_c) + surf.lower(f.x_c)) * c + f.y_offset
    up, lo = surf.upper(f.x_c) * c, surf.lower(f.x_c) * c
    if yc + f.diameter / 2 > up or yc - f.diameter / 2 < lo:
        warnings.append(f"{_label(f)} ({f.diameter:g} mm) does not fit inside the airfoil at x/c = {f.x_c:g}")
    start = -s_in * np.pi / 2
    theta = start - s_in * 2 * np.pi * np.arange(0, ARC_POINTS + 1) / ARC_POINTS
    circle = np.column_stack([xc + r * np.cos(theta), yc + r * np.sin(theta)])
    circle[-1] = circle[0]
    return [*map(tuple, circle), tuple(anchor)]
