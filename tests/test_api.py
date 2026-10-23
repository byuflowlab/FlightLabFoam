import io
import zipfile

import yaml

from flightlabfoam.model import Design


def test_index_page(client):
    r = client.get("/")
    assert r.status_code == 200 and b"FlightLabFoam" in r.data


def test_settings_roundtrip_writes_yaml(client, settings_path):
    s = client.get("/api/settings").get_json()
    assert s["units"] == "mm" and settings_path.exists()
    s["units"] = "in"
    s["machine"]["carriage_separation"] = 800.0
    assert client.put("/api/settings", json=s).status_code == 200
    on_disk = yaml.safe_load(settings_path.read_text())
    assert on_disk["units"] == "in" and on_disk["machine"]["carriage_separation"] == 800.0


def test_bad_settings_are_rejected(client):
    r = client.put("/api/settings", json={"units": "furlongs"})
    assert r.status_code == 400 and "units" in r.get_json()["error"]


def test_airfoils(client):
    assert "clarky" in client.get("/api/airfoils").get_json()["bundled"]
    r = client.post("/api/airfoil", json={"name": "naca0012"}).get_json()
    assert abs(r["max_thickness"] - 0.12) < 2e-3
    dat = "MY FOIL\n" + "\n".join(f"{x} {y}" for x, y in r["coordinates"])
    up = client.post("/api/airfoil", json={"dat": dat, "filename": "My Foil.dat"}).get_json()
    assert up["name"] == "myfoil" and len(up["coordinates"]) == len(r["coordinates"])
    assert client.post("/api/airfoil", json={"name": "nope"}).status_code == 400


def test_preview_and_toolpath(client):
    d = Design().to_dict()
    r = client.post("/api/preview", json={"design": d, "panel": 0}).get_json()
    assert len(r["sections"]) == 2 and r["panel"]["root_on"] in ("xy", "az")
    assert len(r["panel"]["xy"]) == len(r["panel"]["kind"])
    tp = client.post("/api/toolpath", json={"design": d, "panel": 0, "side": "left"}).get_json()
    assert tp["side"] == "left" and tp["total_seconds"] > 0


def test_invalid_design_returns_error(client):
    d = Design().to_dict()
    d["sections"][1]["span_pos"] = 0.0
    r = client.post("/api/preview", json={"design": d})
    assert r.status_code == 400 and "span" in r.get_json()["error"]


def test_gcode_for_all_panels_and_zip(client):
    d = Design()
    d.sections.append(type(d.sections[0])(chord=150.0, span_pos=800.0, x_le=30.0))
    files = client.post("/api/gcode", json={"design": d.to_dict(), "panel": "all"}).get_json()["files"]
    assert sorted(f["filename"] for f in files) == [
        "wing-panel1-left.nc", "wing-panel1-right.nc", "wing-panel2-left.nc", "wing-panel2-right.nc"
    ]
    r = client.post("/api/gcode.zip", json={"design": d.to_dict(), "panel": "all"})
    assert r.status_code == 200 and r.mimetype == "application/zip"
    names = zipfile.ZipFile(io.BytesIO(r.data)).namelist()
    assert len(names) == 4


def test_gcode_refuses_a_panel_that_does_not_fit(client):
    d = Design()
    d.blocks = [type(d.block(0))(auto=False, span=500.0, chord=100.0, thickness=50.0)]
    r = client.post("/api/gcode", json={"design": d.to_dict(), "panel": 0, "side": "right"})
    assert r.status_code == 400
    msgs = [c["message"] for f in r.get_json()["files"] for c in f["checks"]]
    assert any("past the back of the block" in m for m in msgs)


def test_import_flightlab(client):
    from pathlib import Path

    text = (Path(__file__).parent / "fixtures" / "motorcomp.flightlab.json").read_text()
    base = Design()
    base.cut.feed = 99.0
    r = client.post("/api/import/flightlab", json={"text": text, "design": base.to_dict()}).get_json()
    assert len(r["surfaces"]) == 3 and r["design"]["cut"]["feed"] == 99.0
    assert len(r["design"]["sections"]) == 4
