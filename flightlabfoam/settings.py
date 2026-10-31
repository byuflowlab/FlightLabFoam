"""User settings: display units and the foam cutter's machine profile.

Saved as ``settings.yaml`` at the repository root (override with the
``FLIGHTLABFOAM_SETTINGS`` environment variable or ``--settings``). A missing file is
created from the defaults; a missing key takes its default, so adding a setting never
breaks an existing file.
"""

from __future__ import annotations

import os
import threading
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PATH = REPO_ROOT / "settings.yaml"

_lock = threading.Lock()


@dataclass
class Machine:
    name: str = "ME 415 foam cutter"
    dialect: str = "mach3_xyaz"
    # mm between the last fixed points where the wire touches each carriage;
    # measured on the ME 415 cutter as 30.4375 in
    carriage_separation: float = 773.1125
    travel_horizontal: float = 600.0  # mm of X (and A) travel
    travel_vertical: float = 300.0  # mm of Y (and Z) travel
    xy_carriage_side: str = "left"  # side of the X/Y carriage, seen from the X0 end looking along +X
    # how the controller turns F into axis speeds. xy: F is the X/Y carriage speed; xyz: F is
    # the speed along X, Y and Z with A following; all: F is the speed of the 4-axis vector.
    # Confirm with a timed straight move on the real machine.
    feed_model: str = "xy"
    max_feed: float = 600.0  # mm/min; faster moves are flagged
    min_wall_thickness: float = 2.0  # mm; thinner foam between a feature and a skin or another feature is flagged
    # mm; a design whose trailing edge is thickened to less than this is flagged, since a thinner
    # edge melts away and shortens the chord. 1 mm from the first cuts; refine with block 2.
    min_te_thickness: float = 1.0
    heat_on_code: str = "M3"
    heat_off_code: str = "M5"


@dataclass
class Settings:
    units: str = "mm"  # mm | in, for display only; G-code is always written in mm
    machine: Machine = field(default_factory=Machine)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict | None) -> "Settings":
        data = data or {}
        names = {f.name for f in fields(Machine)}
        machine = Machine(**{k: v for k, v in (data.get("machine") or {}).items() if k in names})
        s = cls(units=data.get("units", "mm"), machine=machine)
        s.validate()
        return s

    def validate(self) -> None:
        if self.units not in ("mm", "in"):
            raise ValueError("units must be mm or in")
        m = self.machine
        if m.carriage_separation <= 0:
            raise ValueError("carriage separation must be positive")
        if m.xy_carriage_side not in ("left", "right"):
            raise ValueError("the X/Y carriage side must be left or right")
        if m.feed_model not in ("xy", "xyz", "all"):
            raise ValueError("feed model must be xy, xyz or all")
        if m.travel_horizontal <= 0 or m.travel_vertical <= 0 or m.max_feed <= 0:
            raise ValueError("travel limits and maximum feed must be positive")
        if m.min_wall_thickness < 0:
            raise ValueError("the minimum wall thickness cannot be negative")
        if m.min_te_thickness < 0:
            raise ValueError("the minimum trailing-edge thickness cannot be negative")


def settings_path() -> Path:
    return Path(os.environ.get("FLIGHTLABFOAM_SETTINGS", DEFAULT_PATH))


def load(path: Path | None = None) -> Settings:
    path = Path(path or settings_path())
    if not path.exists():
        settings = Settings()
        save(settings, path)
        return settings
    with open(path) as f:
        return Settings.from_dict(yaml.safe_load(f))


def save(settings: Settings, path: Path | None = None) -> None:
    """Write atomically: a crash mid-write leaves the old file intact."""
    path = Path(path or settings_path())
    settings.validate()
    text = (
        "# FlightLabFoam settings. Edit here or from the menu in the app.\n"
        "# Lengths are mm and feeds are mm/min, whatever the display units.\n"
        + yaml.safe_dump(settings.to_dict(), sort_keys=False)
    )
    with _lock:
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(text)
        os.replace(tmp, path)
