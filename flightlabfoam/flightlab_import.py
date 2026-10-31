"""Read a lifting surface from a FlightLab ``.flightlab.json`` project.

FlightLab stores each surface as a list of stations from root to tip, each with a
leading-edge point (metres, x aft, y right, z up), a chord, a twist and an airfoil
name. Here each pair of neighbouring stations becomes one panel:

* the panel span is the distance between the stations in the y-z plane, so a panel
  with dihedral is cut at its true length, flat; ``span="plan"`` cuts it at its plan
  span instead, which is shorter;
* the leading-edge x offset from the first station becomes sweep;
* airfoils embedded in the project are copied into the design; other names are
  bundled airfoils or NACA 4-digit codes and resolve the same way here;
* an elevator hinge is loaded as a control-surface cut that is switched off.

FlightLab files carry no spar positions, so spars, holes and blocks start empty.
"""

from __future__ import annotations

import json
import math

from . import airfoil
from .model import ControlCut, Design, Section


def surfaces(project: dict) -> list[dict]:
    """Name, symmetry, station count and dihedral of every lifting surface in a project.

    ``span_true`` and ``span_plan`` are the half-span in mm measured along the panels and
    in plan; they differ only when a panel has dihedral.
    """
    out = []
    for s in project.get("surfaces") or []:
        st = s.get("stations") or []
        dz = abs(st[-1]["z"] - st[0]["z"]) if st else 0.0
        dy = abs(st[-1]["y"] - st[0]["y"]) if st else 0.0
        vertical = dz > dy
        lengths = [_lengths(a, b, vertical) for a, b in zip(st, st[1:])]
        out.append(
            {
                "name": s.get("name", ""),
                "symmetric": bool(s.get("symmetric", True)),
                "panels": max(len(st) - 1, 0),
                "vertical": vertical,
                "dihedral": max((abs(_dihedral(a, b) or 0.0) for a, b in zip(st, st[1:])), default=0.0),
                "span_true": 1000.0 * sum(t for t, _ in lengths),
                "span_plan": 1000.0 * sum(p for _, p in lengths),
            }
        )
    return out


def _dihedral(a: dict, b: dict) -> float | None:
    """Dihedral of the panel between two stations in degrees, or None for a vertical panel."""
    dy, dz = b["y"] - a["y"], b["z"] - a["z"]
    return math.degrees(math.atan2(dz, dy)) if abs(dy) >= abs(dz) else None


def _lengths(a: dict, b: dict, vertical: bool) -> tuple[float, float]:
    """True length and plan length (projected onto y, or onto z for a vertical surface), in m."""
    dy, dz = b["y"] - a["y"], b["z"] - a["z"]
    return math.hypot(dy, dz), abs(dz if vertical else dy)


def load_surface(
    text: str, surface: str | None = None, base: Design | None = None, span: str = "true"
) -> tuple[Design, list[str]]:
    """Build a design from one lifting surface; return ``(design, notes)``.

    ``surface`` is a surface name; by default the first surface is used. Cutting
    settings are kept from ``base`` so importing does not reset the machine setup.
    ``span`` is "true" to cut panels with dihedral at their length along the panel, so
    the tilted wing has the designed plan span, or "plan" to cut them at the plan span.
    """
    if span not in ("true", "plan"):
        raise ValueError("span must be true or plan")
    try:
        project = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"not a JSON file: {e}") from None
    if not isinstance(project, dict) or "surfaces" not in project:
        raise ValueError("this file has no lifting surfaces; is it a .flightlab.json project?")
    all_surfaces = project["surfaces"]
    if not all_surfaces:
        raise ValueError("the project has no lifting surfaces")
    if surface is None:
        src = all_surfaces[0]
    else:
        matches = [s for s in all_surfaces if s.get("name") == surface]
        if not matches:
            raise ValueError(f"no surface named {surface!r}")
        src = matches[0]
    stations = src.get("stations") or []
    if len(stations) < 2:
        raise ValueError(f"surface {src.get('name')!r} needs at least two stations")

    notes: list[str] = []
    embedded_src = project.get("airfoils") or {}
    design = Design()
    if base is not None:
        design.cut = base.cut
    proj_name = project.get("name") or "airplane"
    design.name = f"{proj_name} {src.get('name', '')}".strip()
    design.symmetric = bool(src.get("symmetric", True))
    design.sections = []

    vertical = surfaces(project)[all_surfaces.index(src)]["vertical"]
    span_pos = 0.0
    x0 = stations[0]["x_le"]
    for i, st in enumerate(stations):
        if i > 0:
            prev = stations[i - 1]
            true, plan = _lengths(prev, st, vertical)
            if true <= 0:
                raise ValueError(f"surface {src.get('name')!r}: stations {i} and {i + 1} are at the same place")
            span_pos += (true if span == "true" else plan) * 1000.0
            angle = _dihedral(prev, st)
            if angle is not None and abs(angle) > 0.5:
                if span == "true":
                    notes.append(
                        f"panel {i} has {angle:.1f}° of dihedral; it is cut flat at its true length of {true * 1000:.1f} mm, "
                        f"so once tilted it spans the designed {plan * 1000:.1f} mm"
                    )
                else:
                    notes.append(
                        f"panel {i} has {angle:.1f}° of dihedral; it is cut at its plan span of {plan * 1000:.1f} mm, "
                        f"so once tilted it spans {plan * plan / true * 1000:.1f} mm, {(true - plan) * 1000:.1f} mm short of the design"
                    )
        name = _airfoil(st.get("airfoil", "naca0012"), embedded_src, design, notes)
        design.sections.append(
            Section(
                airfoil=name,
                chord=st["chord"] * 1000.0,
                span_pos=span_pos,
                x_le=(st["x_le"] - x0) * 1000.0,
                twist=float(st.get("twist_deg", 0.0)),
            )
        )

    control = src.get("trim_control", "fixed")
    if control == "elevator":
        design.control_cuts = [
            ControlCut(enabled=False, kind="elevator", hinge_x_c=float(src.get("control_hinge_fraction", 0.75)))
        ]
        notes.append(
            f"loaded the elevator hinge at {design.control_cuts[0].hinge_x_c:.0%} chord with cutting off; "
            "turn it on in Spars, holes & control surfaces"
        )
    elif control == "whole_surface":
        notes.append("this is an all-moving surface, so there is no hinge to cut")
    if vertical:
        notes.append("this is a vertical surface; its span runs up the stations, and it is cut as one half")
    notes.append("FlightLab files have no spar positions, so add spars and holes by hand")
    design.validate()
    return design, notes


def _airfoil(name: str, embedded: dict, design: Design, notes: list[str]) -> str:
    """Resolve a FlightLab airfoil name, copying embedded coordinates into the design."""
    if name in embedded:
        coords = embedded[name].get("coordinates") if isinstance(embedded[name], dict) else embedded[name]
        design.airfoils[name] = [list(map(float, p)) for p in coords]
        return name
    try:
        airfoil.load(name)
        return name
    except ValueError:
        notes.append(f"airfoil {name!r} is not available here; using naca0012 instead")
        return "naca0012"
