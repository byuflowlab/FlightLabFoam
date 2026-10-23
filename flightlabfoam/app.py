"""Flask app: one page plus a JSON API over the geometry library.

The browser keeps the design and sends it whole with each request, so the server holds
no state apart from ``settings.yaml``. Errors come back as ``{"error": message}`` with
a 4xx status; the page shows the message.
"""

from __future__ import annotations

import io
import json
import zipfile
from dataclasses import asdict
from pathlib import Path

import numpy as np
from flask import Flask, Response, jsonify, render_template, request

from . import __version__, airfoil, checks, flightlab_import, postprocess, toolpath
from . import settings as settings_mod
from .model import Block, ControlCut, Design, Hole, Section, Spar


def create_app(settings_path: Path | None = None) -> Flask:
    app = Flask(__name__)
    app.config["SETTINGS_PATH"] = Path(settings_path or settings_mod.settings_path())

    def load_settings():
        return settings_mod.load(app.config["SETTINGS_PATH"])

    def body() -> dict:
        data = request.get_json(force=True, silent=True)
        if not isinstance(data, dict):
            raise ValueError("expected a JSON object")
        return data

    @app.errorhandler(ValueError)
    def bad_request(e):
        return jsonify({"error": str(e)}), 400

    @app.get("/")
    def index():
        return render_template("index.html", version=__version__)

    @app.get("/api/settings")
    def get_settings():
        return jsonify(load_settings().to_dict())

    @app.put("/api/settings")
    def put_settings():
        s = settings_mod.Settings.from_dict(body())
        settings_mod.save(s, app.config["SETTINGS_PATH"])
        return jsonify(s.to_dict())

    @app.get("/api/defaults")
    def defaults():
        """Default design and list items, so the page never duplicates them."""
        return jsonify(
            {
                "design": Design().to_dict(),
                "section": asdict(Section()),
                "block": asdict(Block()),
                "spar": asdict(Spar()),
                "hole": asdict(Hole()),
                "control_cut": asdict(ControlCut(enabled=True)),
                "dialects": {k: d.label for k, d in postprocess.DIALECTS.items()},
            }
        )

    @app.get("/api/airfoils")
    def list_airfoils():
        return jsonify({"bundled": airfoil.available()})

    @app.post("/api/airfoil")
    def get_airfoil():
        """Coordinates for a bundled or NACA airfoil name, or for uploaded .dat text."""
        data = body()
        if data.get("dat"):
            title, coords = airfoil.parse_dat(data["dat"])
            stem = Path(data.get("filename") or title or "custom").stem
            name = airfoil.key(stem) or "custom"
        else:
            name = str(data.get("name", "")).strip()
            if not name:
                raise ValueError("give an airfoil name or a .dat file")
            coords = airfoil.load(name, data.get("embedded"))
            title = name
        surf = airfoil.Surfaces.from_coords(coords)
        return jsonify(
            {
                "name": name,
                "title": title,
                "coordinates": np.round(coords, 6).tolist(),
                "max_thickness": surf.max_thickness(),
            }
        )

    @app.post("/api/import/flightlab")
    def import_flightlab():
        data = body()
        text = data.get("text", "")
        base = Design.from_dict(data["design"]) if data.get("design") else None
        design, notes = flightlab_import.load_surface(text, data.get("surface"), base)
        return jsonify(
            {
                "surfaces": flightlab_import.surfaces(json.loads(text)),
                "design": design.to_dict(),
                "notes": notes,
            }
        )

    @app.post("/api/preview")
    def preview():
        """Section outlines for every section plus the full cut of one panel."""
        data = body()
        design = Design.from_dict(data.get("design"))
        design.validate()
        s = load_settings()
        sections = []
        for i, sec in enumerate(design.sections):
            coords = airfoil.load(sec.airfoil, design.airfoils) * sec.chord
            a = np.radians(sec.twist)
            rot = np.array([[np.cos(a), np.sin(a)], [-np.sin(a), np.cos(a)]])
            pts = coords @ rot.T
            pts[:, 0] += sec.x_le
            sections.append({"index": i, "outline": _round(pts)})
        panel = int(data.get("panel", 0))
        side = data.get("side", "right")
        out = {"sections": sections, "panel": None}
        if 0 <= panel < design.n_panels:
            out["panel"] = _panel_json(design, s, panel, side)
        return jsonify(out)

    @app.post("/api/toolpath")
    def get_toolpath():
        data = body()
        design = Design.from_dict(data.get("design"))
        return jsonify(_panel_json(design, load_settings(), int(data.get("panel", 0)), data.get("side", "right")))

    @app.post("/api/gcode")
    def get_gcode():
        """G-code for one panel (``panel`` an index) or every panel (``panel`` = ``"all"``)."""
        data = body()
        design = Design.from_dict(data.get("design"))
        files = _gcode_files(design, load_settings(), data.get("panel", 0), data.get("side", "all"))
        problems = [c for f in files for c in f["checks"] if c["level"] == "error"]
        if problems:
            return jsonify({"error": "fix the errors before generating G-code", "files": files}), 400
        return jsonify({"files": files})

    @app.post("/api/gcode.zip")
    def get_gcode_zip():
        data = body()
        design = Design.from_dict(data.get("design"))
        files = _gcode_files(design, load_settings(), data.get("panel", "all"), data.get("side", "all"))
        if any(c["level"] == "error" for f in files for c in f["checks"]):
            return jsonify({"error": "fix the errors before generating G-code"}), 400
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for f in files:
                z.writestr(f["filename"], f["text"])
        return Response(
            buf.getvalue(),
            mimetype="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{postprocess.stem(design)}-gcode.zip"'},
        )

    return app


def _round(a: np.ndarray, digits: int = 4) -> list:
    return np.round(np.asarray(a, dtype=float), digits).tolist()


def _panel_json(design: Design, settings, panel: int, side: str) -> dict:
    tp = toolpath.build(design, settings, panel, side)
    pl = tp.placement
    b = pl.block
    return {
        "index": panel,
        "side": side,
        "root_on": pl.root_on,
        "xy": _round(tp.xy),
        "az": _round(tp.az),
        "root": _round(tp.root),
        "tip": _round(tp.tip),
        "kind": tp.kind,
        "feed": _round(tp.feed, 2),
        "seconds": _round(tp.seconds, 3),
        "total_seconds": tp.total_seconds,
        "face_root": _round(tp.face_root),
        "face_tip": _round(tp.face_tip),
        "nominal_root": _round(pl.to_machine(tp.ends.nominal_root)),
        "nominal_tip": _round(pl.to_machine(tp.ends.nominal_tip)),
        "block": {"span": b.span, "chord": b.chord, "thickness": b.thickness, "cut_in": b.cut_in},
        "w_root": pl.w_root,
        "w_tip": pl.w_tip,
        "w_block": list(pl.w_block),
        "span": tp.ends.span,
        "checks": checks.check(tp, design, settings),
    }


def _gcode_files(design: Design, settings, panel, side) -> list[dict]:
    design.validate()
    panels = range(design.n_panels) if panel == "all" else [int(panel)]
    wanted = toolpath.sides(design) if side in ("all", None) else [side]
    files = []
    for p in panels:
        for sd in wanted:
            tp = toolpath.build(design, settings, p, sd)
            files.append(
                {
                    "panel": p,
                    "side": sd,
                    "filename": postprocess.filename(design, tp),
                    "text": postprocess.gcode(tp, design, settings),
                    "checks": checks.check(tp, design, settings),
                    "minutes": tp.total_seconds / 60,
                }
            )
    return files
