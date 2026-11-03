"""The design: wing sections, foam blocks, cut features, and cutting settings.

All lengths are millimetres and all angles are degrees. The browser holds a design as
JSON and sends the whole thing with every request; :meth:`Design.from_dict` fills in
defaults for anything missing so older project files keep loading.

Panel frame: x is chordwise aft from the wing-root leading edge, y is up, and the
spanwise position of a section is its distance from the wing root.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from typing import Any

FORMAT_VERSION = 1


def _build(cls, data: dict | None):
    """Construct a flat dataclass from a dict, ignoring unknown keys."""
    if data is None:
        return cls()
    names = {f.name for f in fields(cls)}
    return cls(**{k: v for k, v in data.items() if k in names})


@dataclass
class Section:
    """One wing section, at the start or end of a panel."""

    airfoil: str = "naca2412"
    chord: float = 200.0
    span_pos: float = 0.0  # distance from the wing root along the span
    x_le: float = 0.0  # leading-edge sweep offset, positive aft
    twist: float = 0.0  # positive nose up, about the leading edge


@dataclass
class Block:
    """The foam block for one panel.

    With ``auto`` on, span, chord and thickness are sized to the panel with ``margin``
    of foam around it. ``cut_in`` and the two panel offsets place the panel inside the
    block (centred by default). ``machine_x``, ``machine_y`` and ``machine_offset``
    place the block in the cutting area.
    """

    auto: bool = True
    span: float = 600.0
    chord: float = 250.0
    thickness: float = 50.0
    margin: float = 10.0  # foam left behind the panel and above/below it when auto-sized
    cut_in: float = 10.0  # foam the wire crosses before it reaches the airfoil
    vertical_offset: float = 0.0  # panel position above the block's centre
    span_offset: float = 0.0  # panel position along the block span, toward the tip
    machine_offset: float = 0.0  # block centre from the midpoint between the carriages, toward the A/Z carriage
    machine_x: float = 0.0  # entry face from program zero along X; 0 puts program zero on the entry face
    machine_y: float = 0.0  # block bottom above program zero along Y; 0 puts program zero on the bottom


@dataclass
class Spar:
    """A spar cut that runs the length of the panel.

    ``rect`` and ``u`` are open slots cut into the wing from ``surface``. ``round`` is
    a tube hole reached through a thin entry slit from that surface. Every feature
    enters from the lower surface by default, which keeps the top of the wing clean.
    """

    enabled: bool = True
    kind: str = "rect"  # rect | u | round
    surface: str = "lower"  # lower | upper: the surface the cut enters from
    x_c: float = 0.3  # centre as a fraction of the local chord
    width: float = 6.0  # slot width (rect, u)
    depth: float = 6.0  # slot depth into the wing from the entry surface, at the slot centre (rect, u)
    diameter: float = 6.0  # tube diameter (round)
    y_offset: float = 0.0  # tube centre above the camber line (round)
    panels: list[int] = field(default_factory=list)  # empty means every panel


@dataclass
class Hole:
    """A round lightening hole reached through a thin entry slit from ``surface``."""

    enabled: bool = True
    x_c: float = 0.5
    diameter: float = 10.0
    y_offset: float = 0.0  # centre above the camber line
    surface: str = "lower"
    panels: list[int] = field(default_factory=list)


@dataclass
class ControlCut:
    """Separates a control surface along its hinge line.

    The wire cuts from ``surface`` through to the opposite surface and back. A
    nonzero ``gap`` makes the cut a V that opens to ``gap`` at the entry surface, which
    leaves room for the surface to deflect.
    """

    enabled: bool = False
    kind: str = "aileron"  # aileron | elevator | flap (a label only)
    hinge_x_c: float = 0.75
    gap: float = 0.0
    surface: str = "lower"
    panels: list[int] = field(default_factory=list)


@dataclass
class CutSettings:
    heat_control: bool = False  # write heat on/off codes into the file
    heat_dwell_s: float = 0.0  # pause after heat-on so the wire reaches temperature
    # cutting speed, mm/min. 85 is what F120 gives each carriage on the ME 415 machine, which
    # applies F over all four axes; it is the speed the calibration blocks were cut at
    feed: float = 85.0
    feed_basis: str = "faster_carriage"  # root | tip | faster_carriage | slower_carriage
    exit_feed: float = 170.0  # mm/min, the move back out of the block (F240 on the ME 415 machine)
    entry: str = "trailing"  # trailing | leading: which edge the wire reaches first
    kerf_root: float = 0.0  # path offset outside the root section
    kerf_tip: float = 0.0  # path offset outside the tip section
    te_min_thickness: float = 1.0  # the trailing edge is thickened to at least this; thinner melts away
    points_per_surface: int = 80
    le_clustering: float = 1.25  # 1 = light, 1.25 = medium, 1.5 = strong; see airfoil.stations
    comment_header: bool = False


@dataclass
class Design:
    name: str = "wing"
    symmetric: bool = True
    sections: list[Section] = field(
        default_factory=lambda: [Section(chord=200.0), Section(chord=200.0, span_pos=500.0)]
    )
    airfoils: dict[str, list[list[float]]] = field(default_factory=dict)
    blocks: list[Block] = field(default_factory=list)
    spars: list[Spar] = field(default_factory=list)
    holes: list[Hole] = field(default_factory=list)
    control_cuts: list[ControlCut] = field(default_factory=list)
    cut: CutSettings = field(default_factory=CutSettings)
    notes: str = ""
    format_version: int = FORMAT_VERSION

    @property
    def n_panels(self) -> int:
        return len(self.sections) - 1

    def block(self, panel: int) -> Block:
        return self.blocks[panel] if panel < len(self.blocks) else Block()

    def features_for(self, panel: int) -> list:
        """Enabled spars, holes and control cuts that apply to ``panel``."""
        return [
            f
            for f in (*self.spars, *self.holes, *self.control_cuts)
            if f.enabled and (not f.panels or panel in f.panels)
        ]

    def validate(self) -> None:
        if len(self.sections) < 2:
            raise ValueError("a wing needs at least two sections (one panel)")
        for i, s in enumerate(self.sections):
            if s.chord <= 0:
                raise ValueError(f"section {i + 1}: chord must be positive")
        for i in range(self.n_panels):
            if self.sections[i + 1].span_pos <= self.sections[i].span_pos:
                raise ValueError(
                    f"panel {i + 1}: each section must be farther out along the span than the one before it"
                )
        if self.cut.feed <= 0 or self.cut.exit_feed <= 0:
            raise ValueError("feed rates must be positive")
        if not 10 <= self.cut.points_per_surface <= 400:
            raise ValueError("use between 10 and 400 points per surface")
        if not 1.0 <= self.cut.le_clustering <= 2.0:
            raise ValueError("leading-edge clustering must be between 1 and 2")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict | None) -> "Design":
        data = dict(data or {})
        version = data.get("format_version", FORMAT_VERSION)
        if version > FORMAT_VERSION:
            raise ValueError(
                f"this project file is format {version}; this version of FlightLabFoam reads up to {FORMAT_VERSION}"
            )
        d = cls()
        for name in ("name", "symmetric", "notes"):
            if name in data:
                setattr(d, name, data[name])
        if "sections" in data:
            d.sections = [_build(Section, s) for s in data["sections"]]
        d.airfoils = dict(data.get("airfoils") or {})
        d.blocks = [_build(Block, b) for b in data.get("blocks") or []]
        d.spars = [_build(Spar, s) for s in data.get("spars") or []]
        d.holes = [_build(Hole, h) for h in data.get("holes") or []]
        d.control_cuts = [_build(ControlCut, c) for c in data.get("control_cuts") or []]
        d.cut = _build(CutSettings, data.get("cut"))
        return d
