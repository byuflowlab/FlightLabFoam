"""Turn a toolpath into G-code text for a particular controller.

A :class:`Dialect` holds everything that varies between controllers: axis letters,
number format, header, heat codes, dwell and comment syntax. The toolpath itself
never changes with the dialect.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import __version__
from .model import Design
from .settings import Settings
from .toolpath import Toolpath


@dataclass(frozen=True)
class Dialect:
    key: str
    label: str
    axes: tuple[str, str, str, str] = ("X", "Y", "A", "Z")  # X/Y carriage horizontal, vertical; A/Z carriage
    decimals: int = 4
    line_end: str = "\r\n"
    header: tuple[str, ...] = ("G21", "G17", "G90")
    move: str = "G1"
    dwell: str = "G4 P{seconds:g}"  # P in seconds
    comment: str = "({text})"


DIALECTS = {
    "mach3_xyaz": Dialect(key="mach3_xyaz", label="Mach3, X/Y + A/Z carriages (mm)"),
}


def dialect_for(settings: Settings) -> Dialect:
    try:
        return DIALECTS[settings.machine.dialect]
    except KeyError:
        raise ValueError(f"unknown G-code style {settings.machine.dialect!r}") from None


def gcode(tp: Toolpath, design: Design, settings: Settings) -> str:
    d = dialect_for(settings)
    cut, m = design.cut, settings.machine
    fmt = f"{{:.{d.decimals}f}}"
    lines: list[str] = []
    if cut.comment_header:
        lines += [d.comment.format(text=_clean(t)) for t in _header_comments(tp, design, settings)]
    lines += list(d.header)
    if cut.heat_control:
        lines.append(m.heat_on_code)
        if cut.heat_dwell_s > 0:
            lines.append(d.dwell.format(seconds=cut.heat_dwell_s))

    ax = d.axes
    last_f = None
    for (x, y), (a, z), f in zip(tp.xy, tp.az, tp.feed):
        words = f"{d.move}{ax[0]}{fmt.format(x)}{ax[1]}{fmt.format(y)}{ax[2]}{fmt.format(a)}{ax[3]}{fmt.format(z)}"
        f_text = fmt.format(f)
        if f_text != last_f:
            words += f"F{f_text}"
            last_f = f_text
        lines.append(_no_negative_zero(words))
    if cut.heat_control:
        lines.append(m.heat_off_code)
    return d.line_end.join(lines) + d.line_end


def stem(design: Design) -> str:
    """The design name, made safe for a filename."""
    return "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in design.name.strip()) or "wing"


def filename(design: Design, tp: Toolpath) -> str:
    return f"{stem(design)}-panel{tp.panel + 1}-{tp.side}.nc"


def _header_comments(tp: Toolpath, design: Design, settings: Settings) -> list[str]:
    cut, pl = design.cut, tp.placement
    r, t = design.sections[tp.panel], design.sections[tp.panel + 1]
    root_axes, tip_axes = ("X/Y", "A/Z") if pl.root_on == "xy" else ("A/Z", "X/Y")
    b = pl.block
    return [
        f"FlightLabFoam {__version__}",
        f"{design.name} panel {tp.panel + 1} {tp.side} wing",
        f"root {r.airfoil} chord {r.chord:g} twist {r.twist:g} at the {root_axes} carriage",
        f"tip {t.airfoil} chord {t.chord:g} twist {t.twist:g} sweep {t.x_le - r.x_le:g} at the {tip_axes} carriage",
        f"block span {b.span:.1f} chord {b.chord:.1f} thickness {b.thickness:.1f} cut-in {b.cut_in:g}",
        f"{cut.entry} edge first; feed {cut.feed:g} mm/min on the {cut.feed_basis.replace('_', ' ')}",
        f"kerf root {cut.kerf_root:g} tip {cut.kerf_tip:g}",
        "zero the wire at the bottom edge of the entry face",
    ]


def _clean(text: str) -> str:
    """Comments may not contain parentheses."""
    return text.replace("(", "[").replace(")", "]")


def _no_negative_zero(words: str) -> str:
    return words.replace("-0.0000", "0.0000") if "-0.0000" in words else words
