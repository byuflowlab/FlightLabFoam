"""Matched root and tip outlines for one panel.

A hot wire cuts a ruled surface: point *i* of the root outline and point *i* of the tip
outline lie on the same wire line. :func:`panel_ends` builds the two outlines with
the same number of points, in the same order, at the same fraction of the chord.

The steps, all at the panel ends (not at the carriages):

1. Sample both airfoils at shared chord stations clustered at the leading edge,
   separately for the upper and lower surfaces. Feature boundaries (spar slots, holes,
   hinge cuts) become stations at both ends; the stations between them are warped
   piecewise-linearly so a slot that is 6 mm wide at both ends lands exactly even
   though the chords differ.
2. Scale by chord and thicken the trailing edge to the minimum thickness.
3. Offset the outline outward by the kerf so the finished part keeps its size.
4. Insert the feature cuts, already kerf-compensated. A hole or hinge cut whose entry
   falls inside a spar slot on the same surface starts from the slot's floor instead.
5. Rotate by twist about the leading edge and shift by the sweep offset.

Projection to the carriages is linear along each wire line and happens later, in
:mod:`flightlabfoam.toolpath`. The nominal shape of every feature (no kerf, before
twist) is kept in :attr:`PanelEnds.shapes` for the fit checks in
:mod:`flightlabfoam.checks`.

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
SIDE_NAME = {"upper": "top", "lower": "bottom"}


@dataclass
class Shape:
    """The nominal outline of one feature at one panel end: section frame, mm, no kerf.

    ``kind`` is ``slot`` (closed, open to the entry surface), ``hole`` (closed circle)
    or ``cut`` (an open hinge-line polyline that runs through the wing on purpose).
    """

    label: str
    kind: str
    surface: str
    points: np.ndarray


@dataclass
class PanelEnds:
    root: np.ndarray  # (m, 2) cut outline at the wing root, panel frame, mm
    tip: np.ndarray  # (m, 2) cut outline at the wing tip
    le_index: int
    span: float
    nominal_root: np.ndarray  # airfoil outline without kerf or features, for drawing
    nominal_tip: np.ndarray
    nominal_le: int  # leading-edge index of the nominal outlines
    skins: list[tuple[np.ndarray, np.ndarray]] = field(default_factory=list)  # per end: (upper, lower), section frame
    shapes: list[list[Shape]] = field(default_factory=list)  # per end: every feature's nominal outline
    warnings: list[str] = field(default_factory=list)

    def spacing(self) -> dict:
        """Distance between neighbouring points: at the nose, and the largest anywhere (mm)."""
        nose, widest = 0.0, 0.0
        for loop in (self.nominal_root, self.nominal_tip):
            gaps = np.linalg.norm(np.diff(loop, axis=0), axis=1)
            le = self.nominal_le
            nose = max(nose, gaps[le - 1], gaps[le])
            widest = max(widest, float(gaps.max()))
        return {"nose": float(nose), "max": widest}

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

    def skin(self, side: str, x):
        """Surface height in mm at chord fraction ``x``, with the trailing edge thickened."""
        lower = self.surf.lower(x) * self.chord
        if side == "lower":
            return lower
        upper = self.surf.upper(x) * self.chord
        if self.te_min > 0:
            upper = np.where(np.asarray(x) >= 0.5, np.maximum(upper, lower + self.te_min), upper)
        return upper


@dataclass
class _Event:
    """A feature on one surface, with its chord-fraction boundaries at each end."""

    a: tuple[float, float]  # (root, tip) start, x/c
    b: tuple[float, float]  # (root, tip) end, x/c; equal to a for a slit
    feature: object
    label: str
    children: list["_Event"] = field(default_factory=list)  # cuts that start from this slot's floor

    @property
    def slit(self) -> bool:
        return self.a == self.b

    @property
    def is_slot(self) -> bool:
        return isinstance(self.feature, Spar) and self.feature.kind in ("rect", "u")


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
    labels = _labels(design)
    events = {"upper": [], "lower": []}
    for f in design.features_for(panel):
        events[f.surface].append(_event(f, ends, labels[id(f)]))
    for side in events:
        events[side] = _nest(sorted(events[side], key=lambda e: e.a[0]), side)

    n = cut.points_per_surface
    loops, nominals, skins, shapes = [], [], [], []
    for k, end in enumerate(ends):
        upper, up_marks = _sample(end, "upper", events["upper"], k, n, cut.le_clustering)
        lower, lo_marks = _sample(end, "lower", events["lower"], k, n, cut.le_clustering)
        base = np.vstack([upper[::-1], lower[1:]])
        nominals.append(_place(base, end))
        off = _offset(base, end.kerf)
        m_u = len(upper)
        n_le = m_u - 1
        up_off = off[:m_u][::-1]
        lo_off = off[m_u - 1 :]
        up_final = _insert(up_off, up_marks, events["upper"], end, k, "upper")
        lo_final = _insert(lo_off, lo_marks, events["lower"], end, k, "lower")
        loop = np.vstack([up_final[::-1], lo_final[1:]])
        loops.append((_place(loop, end), len(up_final) - 1))

        x = airfoil.stations(300, 1.0)
        skins.append(tuple(np.column_stack([x * end.chord, end.skin(side, x)]) for side in ("upper", "lower")))
        shapes.append([_shape(e, end, k, side) for side in events for e in _walk(events[side])])

    (root, le_r), (tip, le_t) = loops
    assert root.shape == tip.shape and le_r == le_t, "root and tip outlines must match point for point"
    return PanelEnds(
        root=root,
        tip=tip,
        le_index=le_r,
        span=s_tip.span_pos - s_root.span_pos,
        nominal_root=nominals[0],
        nominal_tip=nominals[1],
        nominal_le=n_le,
        skins=skins,
        shapes=shapes,
    )


def _place(loop: np.ndarray, end: _End) -> np.ndarray:
    """Twist about the leading edge (positive nose up), then shift by the sweep offset."""
    a = np.radians(end.twist)
    rot = np.array([[np.cos(a), np.sin(a)], [-np.sin(a), np.cos(a)]])  # clockwise = nose up
    out = loop @ rot.T
    out[:, 0] += end.x_le
    return out


def _labels(design: Design) -> dict:
    """A short name for every feature, numbered when there is more than one of a kind."""
    out = {}
    kinds = {"rect": "square", "u": "U", "round": "round"}
    for i, f in enumerate(design.spars):
        kind = kinds.get(f.kind, f.kind)
        out[id(f)] = f"spar {i + 1} ({kind})" if len(design.spars) > 1 else f"{kind} spar"
    for i, f in enumerate(design.holes):
        out[id(f)] = f"lightening hole {i + 1}" if len(design.holes) > 1 else "lightening hole"
    for i, f in enumerate(design.control_cuts):
        out[id(f)] = f"{f.kind} cut {i + 1}" if len(design.control_cuts) > 1 else f"{f.kind} cut"
    return out


def _event(f, ends: list[_End], label: str) -> _Event:
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
            raise ValueError(f"the {label} at x/c = {f.x_c if not isinstance(f, ControlCut) else f.hinge_x_c:g} runs off the airfoil")
        a.append(lo)
        b.append(hi)
    return _Event(tuple(a), tuple(b), f, label)


def _nest(events: list[_Event], side: str) -> list[_Event]:
    """Attach cuts whose entry lies inside a slot to that slot; reject overlaps that can't be cut.

    Returns the top-level events. A hole, round spar or hinge cut entirely inside a
    slot at both ends becomes one of the slot's children and is cut from its floor.
    """
    where = SIDE_NAME[side]
    slots = [e for e in events if e.is_slot]
    top = list(slots)
    for e in events:
        if e.is_slot:
            continue
        inside = [s for s in slots if all(s.a[k] < e.a[k] and e.b[k] < s.b[k] for k in (0, 1))]
        if inside:
            inside[0].children.append(e)
        else:
            top.append(e)

    def overlap(p, q):
        return any(p.a[k] <= q.b[k] and q.a[k] <= p.b[k] for k in (0, 1))

    def check(group):
        for i, p in enumerate(group):
            for q in group[i + 1 :]:
                if not overlap(p, q):
                    continue
                if p.is_slot and q.is_slot:
                    raise ValueError(f"the {p.label} and {q.label} slots overlap on the {where} surface; use one wider slot")
                if p.is_slot or q.is_slot:
                    slot, other = (p, q) if p.is_slot else (q, p)
                    raise ValueError(
                        f"the {other.label} enters the {where} surface at the edge of the {slot.label} slot; "
                        "move it inside the slot or clear of it"
                    )
                raise ValueError(f"the {p.label} and {q.label} enter the {where} surface at the same place; move one")

    top.sort(key=lambda e: e.a[0])
    check(top)
    for s in slots:
        s.children.sort(key=lambda e: e.a[0])
        check(s.children)
    return top


def _walk(events: list[_Event]):
    for e in events:
        yield e
        yield from e.children


def _sample(end: _End, side: str, events: list[_Event], k: int, n: int, clustering: float):
    """Points along one surface, LE -> TE, in mm; plus the station index of each event start.

    Reference stations are clustered at the leading edge (:func:`airfoil.stations`).
    Event boundaries are added at the mean of their root and tip positions, stations
    inside an event are dropped, and the stations are then warped so each boundary
    lands at this end's own position.
    """
    s = airfoil.stations(n, clustering)
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
        raise ValueError(f"features on the {SIDE_NAME[side]} surface cross between the root and the tip; move them apart")

    s = np.sort(np.concatenate([s, extra]))
    x = np.interp(s, ref_knots, end_knots)
    marks = [int(np.searchsorted(s, 0.5 * (e.a[0] + e.a[1]))) for e in events]
    return np.column_stack([x * end.chord, end.skin(side, x)]), marks


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


def _insert(surface, marks, events, end: _End, k: int, side: str) -> np.ndarray:
    """Insert each event's cut after its start station on a LE -> TE surface."""
    pieces, last = [], 0
    for mark, e in zip(marks, events):
        pieces.append(surface[last : mark + 1])
        anchor = surface[mark]
        pieces.append(np.asarray(_excursion(e, anchor, end, k, side), dtype=float).reshape(-1, 2))
        last = mark + 1
    pieces.append(surface[last:])
    return np.vstack(pieces)


def _slot_frame(e: _Event, end: _End, k: int, side: str, kerf: float):
    """Walls, floor height and U radius of a slot; kerf moves the walls and floor inward."""
    f, c = e.feature, end.chord
    s_in = -1.0 if side == "upper" else 1.0
    xa, xb = e.a[k] * c + kerf, e.b[k] * c - kerf
    floor = end.skin(side, f.x_c) + s_in * (f.depth - kerf)
    r = (xb - xa) / 2
    return xa, xb, floor, r, s_in


def _circle(f, end: _End, side: str, kerf: float, n: int = ARC_POINTS) -> np.ndarray:
    """A hole's outline, starting at the point nearest the entry surface.

    It runs counter-clockwise from the top for upper entry and clockwise from the bottom
    for lower entry, so material stays on the same side of the wire as on the outline.
    """
    s_in = -1.0 if side == "upper" else 1.0
    c = end.chord
    r = f.diameter / 2 - kerf
    xc = f.x_c * c
    yc = 0.5 * (end.surf.upper(f.x_c) + end.surf.lower(f.x_c)) * c + f.y_offset
    theta = -s_in * np.pi / 2 - s_in * 2 * np.pi * np.arange(0, n + 1) / n
    pts = np.column_stack([xc + r * np.cos(theta), yc + r * np.sin(theta)])
    pts[-1] = pts[0]
    return pts


def _excursion(e: _Event, anchor, end: _End, k: int, side: str):
    """Points of a feature cut, in LE -> TE order, between its start and end stations.

    ``s_in`` points into the wing from the entry surface. Every cut is drawn so that
    wing material stays on the same side of the wire as along the outline, so the
    kerf compensation shrinks slots and holes (the wire widens them back).
    """
    f, c, kerf = e.feature, end.chord, end.kerf
    other = "lower" if side == "upper" else "upper"
    s_in = -1.0 if side == "upper" else 1.0

    if e.is_slot:
        xa, xb, floor, r, s_in = _slot_frame(e, end, k, side, kerf)
        top = anchor[1]
        xc = f.x_c * c
        if f.kind == "rect":
            # the floor is a straight line; cuts that start from it are spliced in by x
            pts = [(xa, top), (xa, floor)]
            for ch in e.children:
                foot = (ch.a[k] * c, floor)
                pts += [foot, *_excursion(ch, foot, end, k, side)]
                if not ch.slit:
                    pts.append((ch.b[k] * c, floor))
            return pts + [(xb, floor), (xb, top)]
        # U slot: the floor is a half circle split at each child's entry, with a fixed
        # number of points per piece so the root and tip still match point for point
        yc = floor - s_in * r

        def arc_t(x):
            return float(np.arccos(np.clip((xc - x) / r, -1.0, 1.0)) / np.pi)

        def arc(t0, t1, include_end):
            m = max(2, (ARC_POINTS // 2) // (len(e.children) + 1))
            t = np.linspace(t0, t1, m + 1)[: None if include_end else -1]
            return list(zip(xc - r * np.cos(np.pi * t), yc + s_in * r * np.sin(np.pi * t)))

        pts, t_prev = [(xa, top)], 0.0
        for ch in e.children:
            t_a = arc_t(ch.a[k] * c)
            pts += arc(t_prev, t_a, True)
            foot = pts[-1]
            pts += _excursion(ch, foot, end, k, side)
            t_prev = t_a
            if not ch.slit:
                t_prev = arc_t(ch.b[k] * c)
                pts.append(arc(t_prev, t_prev, True)[0])
        return pts + arc(t_prev, 1.0, True) + [(xb, top)]

    if isinstance(f, ControlCut):
        xh = f.hinge_x_c * c
        apex = (xh, end.skin(other, f.hinge_x_c) + s_in * kerf)
        return [apex] if not e.slit else [apex, tuple(anchor)]

    # round spar or lightening hole: entry slit from the surface, then a full circle
    return [*map(tuple, _circle(f, end, side, kerf)), tuple(anchor)]


def _shape(e: _Event, end: _End, k: int, side: str) -> Shape:
    """The nominal (no kerf) outline of a feature at one end, for the fit checks."""
    f, c = e.feature, end.chord
    if e.is_slot:
        xa, xb, floor, r, s_in = _slot_frame(e, end, k, side, 0.0)
        mouth = np.linspace(xb, xa, 25)  # along the entry surface, closing the outline
        skin = np.column_stack([mouth, end.skin(side, mouth / c)])
        if f.kind == "rect":
            body = np.array([(xa, floor), (xb, floor)])
        else:
            t = np.linspace(0.0, 1.0, ARC_POINTS + 1)
            yc = floor - s_in * r
            body = np.column_stack([f.x_c * c - r * np.cos(np.pi * t), yc + s_in * r * np.sin(np.pi * t)])
        return Shape(e.label, "slot", side, np.vstack([body, skin, body[:1]]))
    if isinstance(f, ControlCut):
        other = "lower" if side == "upper" else "upper"
        xa, xb, xh = e.a[k] * c, e.b[k] * c, f.hinge_x_c * c
        pts = [(xa, end.skin(side, e.a[k])), (xh, end.skin(other, f.hinge_x_c)), (xb, end.skin(side, e.b[k]))]
        return Shape(e.label, "cut", side, np.array(pts, dtype=float))
    return Shape(e.label, "hole", side, _circle(f, end, side, 0.0, n=72))
