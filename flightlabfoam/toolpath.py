"""Place a panel in its foam block and between the carriages, and build the wire path.

Machine frame
-------------
* The X/Y carriage carries one end of the wire and the A/Z carriage the other. X and
  A are horizontal (into the block); Y and Z are vertical.
* Program zero is where the wire is zeroed before running a file. By default it is
  the bottom edge of the block's entry face (the face the wire starts at): X = 0 (and
  A = 0) on that face, Y = 0 (and Z = 0) on the block bottom. The block's
  ``machine_x`` and ``machine_y`` move the block away from program zero, for zeroing
  at a fixed point on the machine instead.
* The entry edge (leading or trailing, from the cut settings) faces X = 0. Cutting
  trailing edge first therefore turns the airfoil around in the machine.
* Spanwise, ``w`` runs from the X/Y carriage (w = 0) to the A/Z carriage
  (w = carriage separation).

Which carriage carries the root follows from the wing half, the entry edge and the
side of the X/Y carriage. Looking along +X with the leading edge first, a right wing's
tip is on the left, so its root is on the right; turning it to cut trailing edge first
swaps that, and so does cutting the left wing.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

import numpy as np

from .geometry import PanelEnds, panel_ends
from .model import Block, Design
from .settings import Settings


@dataclass
class Placement:
    side: str  # right | left wing half
    root_on: str  # xy | az: the carriage nearest the wing root
    block: Block  # with auto-sized dimensions filled in
    w_root: float  # spanwise machine positions, from the X/Y carriage
    w_tip: float
    w_block: tuple[float, float]  # block faces, (root side, tip side)
    u_face: float  # entry face position along u (x, or -x when the trailing edge enters first)
    y_bottom: float  # block bottom in the panel frame
    flip: bool  # True when the trailing edge enters first

    def to_block(self, pts: np.ndarray) -> np.ndarray:
        """Panel frame to block frame: X from the entry face, Y from the block bottom."""
        u = -pts[:, 0] if self.flip else pts[:, 0]
        return np.column_stack([u - self.u_face, pts[:, 1] - self.y_bottom])

    def to_machine(self, pts: np.ndarray) -> np.ndarray:
        """Panel frame to machine coordinates, measured from program zero."""
        return self.to_block(pts) + [self.block.machine_x, self.block.machine_y]


@dataclass
class Toolpath:
    panel: int
    side: str
    xy: np.ndarray  # (k, 2) X, Y for each vertex
    az: np.ndarray  # (k, 2) A, Z
    root: np.ndarray  # (k, 2) the same vertices at the wing root, machine X/Y frame
    tip: np.ndarray  # (k, 2) at the wing tip
    feed: np.ndarray  # (k,) F for the move into each vertex
    seconds: np.ndarray  # (k,) estimated duration of the move into each vertex
    kind: list[str]  # start | lead_in | cut | exit
    placement: Placement
    ends: PanelEnds
    face_root: np.ndarray  # cut outline where it leaves the block on the root side, block frame
    face_tip: np.ndarray
    warnings: list[str] = field(default_factory=list)

    @property
    def total_seconds(self) -> float:
        return float(np.sum(self.seconds))


def sides(design: Design) -> list[str]:
    return ["right", "left"] if design.symmetric else ["right"]


def root_carriage(side: str, entry: str, xy_side: str) -> str:
    """``xy`` or ``az``: which carriage the wing root is nearest."""
    root_on_operator_right = (side == "right") == (entry == "leading")
    return "xy" if root_on_operator_right == (xy_side == "right") else "az"


def place(design: Design, settings: Settings, panel: int, side: str, ends: PanelEnds | None = None) -> Placement:
    ends = ends or panel_ends(design, panel)
    block = design.block(panel)
    m = settings.machine
    flip = design.cut.entry == "trailing"
    root_on = root_carriage(side, design.cut.entry, m.xy_carriage_side)
    toward_tip = 1.0 if root_on == "xy" else -1.0

    def u_of(pts):
        return -pts[:, 0] if flip else pts[:, 0]

    if block.auto:
        both = np.vstack([ends.root, ends.tip])
        u, y = u_of(both), both[:, 1]
        block = replace(
            block,
            span=ends.span,
            chord=float(u.max() - u.min()) + block.cut_in + block.margin,
            thickness=float(y.max() - y.min()) + 2 * block.margin,
        )

    w_mid = m.carriage_separation / 2 + block.machine_offset
    w_panel = w_mid + toward_tip * block.span_offset
    w_root = w_panel - toward_tip * ends.span / 2
    w_tip = w_panel + toward_tip * ends.span / 2
    w_block = (w_mid - toward_tip * block.span / 2, w_mid + toward_tip * block.span / 2)

    faces = [ends.at((w - w_root) / (w_tip - w_root)) for w in w_block]
    both = np.vstack(faces)
    u_face = float(u_of(both).min()) - block.cut_in
    y_mid = 0.5 * (both[:, 1].max() + both[:, 1].min())
    y_bottom = y_mid - block.thickness / 2 - block.vertical_offset
    return Placement(side, root_on, block, w_root, w_tip, w_block, u_face, y_bottom, flip)


def build(design: Design, settings: Settings, panel: int, side: str = "right") -> Toolpath:
    design.validate()
    ends = panel_ends(design, panel)
    pl = place(design, settings, panel, side, ends)
    cut = design.cut
    m = settings.machine

    # matched outlines plus the trailing-edge midpoint, which is where a trailing-edge-first cut enters
    root = np.vstack([ends.root, 0.5 * (ends.root[0] + ends.root[-1])])
    tip = np.vstack([ends.tip, 0.5 * (ends.tip[0] + ends.tip[-1])])
    n, le, te_mid = len(ends.root), ends.le_index, len(ends.root)
    if cut.entry == "trailing":
        order = [te_mid, *range(n), te_mid]
    else:
        order = [*range(le, -1, -1), *range(n - 1, le - 1, -1)]
    root, tip = root[order], tip[order]

    # entry and exit: up from program zero to the entry point's height, across to the
    # entry face, straight in, and back out the same way. With the block at program
    # zero the first two points coincide and the duplicate is dropped below.
    root, tip = pl.to_machine(root), pl.to_machine(tip)
    x_face = pl.block.machine_x

    def approach(y):
        return np.array([[0.0, y], [x_face, y]])

    root = np.vstack([approach(root[0, 1]), root, approach(root[0, 1])[::-1]])
    tip = np.vstack([approach(tip[0, 1]), tip, approach(tip[0, 1])[::-1]])
    kind = ["start", "start", "lead_in", *["cut"] * (len(order) - 1), "exit", "exit"]

    span = pl.w_tip - pl.w_root
    w_xy, w_az = 0.0, m.carriage_separation
    xy = root + (tip - root) * ((w_xy - pl.w_root) / span)
    az = root + (tip - root) * ((w_az - pl.w_root) / span)

    keep = _drop_duplicates(xy, az)
    xy, az, root, tip = xy[keep], az[keep], root[keep], tip[keep]
    kind = [k for k, ok in zip(kind, keep) if ok]

    feed, seconds = _feeds(xy, az, root, tip, kind, cut, m)
    faces = [pl.to_block(ends.at((w - pl.w_root) / span)) for w in pl.w_block]
    return Toolpath(
        panel=panel,
        side=side,
        xy=xy,
        az=az,
        root=root,
        tip=tip,
        feed=feed,
        seconds=seconds,
        kind=kind,
        placement=pl,
        ends=ends,
        face_root=faces[0],
        face_tip=faces[1],
        warnings=list(ends.warnings),
    )


def _drop_duplicates(xy: np.ndarray, az: np.ndarray, tol: float = 5e-5) -> np.ndarray:
    """Keep a vertex only if either carriage moves from the previous kept vertex."""
    keep = np.ones(len(xy), dtype=bool)
    last = 0
    for i in range(1, len(xy)):
        if np.all(np.abs(xy[i] - xy[last]) < tol) and np.all(np.abs(az[i] - az[last]) < tol):
            keep[i] = False
        else:
            last = i
    return keep


def _feeds(xy, az, root, tip, kind, cut, machine):
    """F word and duration for every move.

    The cutting speed is held on the chosen reference (wing root, wing tip, or the
    faster or slower carriage). F is then the speed the controller must be told so
    that move takes that long, measured the way the machine profile says the
    controller measures it: along the X/Y carriage's path, over the X, Y and Z axes
    with A following, or over all four axes.
    """
    k = len(xy)
    feed = np.zeros(k)
    seconds = np.zeros(k)
    prev_xy, prev_az = np.zeros(2), np.zeros(2)  # the wire is zeroed at the origin
    prev_r, prev_t = np.zeros(2), np.zeros(2)
    for i in range(k):
        d_xy, d_az = xy[i] - prev_xy, az[i] - prev_az
        if machine.feed_model == "all":
            ctrl = float(np.linalg.norm([*d_xy, *d_az]))
        elif machine.feed_model == "xy":
            ctrl = float(np.linalg.norm(d_xy))
            if ctrl < 1e-12:
                ctrl = float(np.linalg.norm(d_az))
        else:
            ctrl = float(np.hypot(np.hypot(d_xy[0], d_xy[1]), d_az[1]))
            if ctrl < 1e-12:
                ctrl = abs(float(d_az[0]))
        if kind[i] == "exit":
            f = cut.exit_feed
            minutes = ctrl / f
        else:
            l_xy, l_az = float(np.linalg.norm(d_xy)), float(np.linalg.norm(d_az))
            ref = {
                "root": float(np.linalg.norm(root[i] - prev_r)),
                "tip": float(np.linalg.norm(tip[i] - prev_t)),
                "faster_carriage": max(l_xy, l_az),
                "slower_carriage": min(l_xy, l_az),
            }.get(cut.feed_basis, max(l_xy, l_az))
            if ref < 1e-9:
                ref = max(l_xy, l_az)
            minutes = ref / cut.feed
            f = ctrl / minutes if minutes > 0 else cut.feed
        feed[i] = f
        seconds[i] = 60.0 * minutes
        prev_xy, prev_az, prev_r, prev_t = xy[i], az[i], root[i], tip[i]
    return feed, seconds
