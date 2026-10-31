import json
from pathlib import Path

import pytest

from flightlabfoam import toolpath
from flightlabfoam.flightlab_import import load_surface, surfaces
from flightlabfoam.settings import Settings

FIXTURES = Path(__file__).parent / "fixtures"


def read(name):
    return (FIXTURES / name).read_text()


def test_rc1_main_wing():
    d, notes = load_surface(read("rc1-hw1.flightlab.json"))
    assert d.symmetric and d.n_panels == 1
    assert d.sections[0].chord == pytest.approx(160.0)
    assert d.sections[1].span_pos == pytest.approx(600.0)
    assert d.sections[1].airfoil == "naca2412"
    assert d.control_cuts == []


def test_elevator_hinge_loads_switched_off():
    d, notes = load_surface(read("rc1-hw1.flightlab.json"), "Horizontal tail")
    assert len(d.control_cuts) == 1
    cut = d.control_cuts[0]
    assert not cut.enabled and cut.kind == "elevator" and cut.hinge_x_c == pytest.approx(0.75)
    assert any("cutting off" in n for n in notes)


def test_multi_panel_wing_with_sweep_twist_and_dihedral():
    d, notes = load_surface(read("motorcomp.flightlab.json"))
    assert d.n_panels == 3
    assert d.sections[2].x_le == pytest.approx(70.0)
    assert d.sections[3].twist == pytest.approx(-1.5)
    assert d.sections[3].airfoil == "sd7037"
    # true panel length in the y-z plane
    assert d.sections[2].span_pos - d.sections[1].span_pos == pytest.approx(((0.36**2 + 0.03**2) ** 0.5) * 1000)
    assert any("dihedral" in n for n in notes)


def test_embedded_airfoil_is_copied_and_every_panel_builds():
    d, _ = load_surface(read("milestone5-double-winglet.flightlab.json"))
    assert "mh45" in d.airfoils
    for p in range(d.n_panels):
        for side in toolpath.sides(d):
            toolpath.build(d, Settings(), p, side)


def test_vertical_surface_and_surface_list():
    text = read("rc1-hw1.flightlab.json")
    import json

    listed = surfaces(json.loads(text))
    assert [s["name"] for s in listed] == ["Main wing", "Horizontal tail", "Vertical tail"]
    assert listed[2]["vertical"] and not listed[2]["symmetric"]
    d, notes = load_surface(text, "Vertical tail")
    assert not d.symmetric and d.sections[1].span_pos == pytest.approx(150.0)


def test_bad_input():
    with pytest.raises(ValueError, match="JSON"):
        load_surface("not json")
    with pytest.raises(ValueError, match="no lifting surfaces"):
        load_surface("{}")
    with pytest.raises(ValueError, match="no surface named"):
        load_surface(read("rc1-hw1.flightlab.json"), "Canard")


DIHEDRAL = json.dumps(
    {
        "name": "Glider",
        "surfaces": [
            {
                "name": "Main Wing",
                "symmetric": True,
                "stations": [
                    {"x_le": 0.0, "y": 0.0, "z": 0.0, "chord": 0.2, "airfoil": "naca2412"},
                    {"x_le": 0.0, "y": 0.5, "z": 0.05, "chord": 0.2, "airfoil": "naca2412"},
                ],
            }
        ],
    }
)


def test_dihedral_is_reported_with_both_spans():
    (s,) = surfaces(json.loads(DIHEDRAL))
    assert s["dihedral"] == pytest.approx(5.71, abs=0.01)
    assert s["span_true"] == pytest.approx(502.49, abs=0.01)
    assert s["span_plan"] == pytest.approx(500.0)


def test_dihedral_panel_is_cut_at_its_true_length_by_default():
    d, notes = load_surface(DIHEDRAL)
    assert d.sections[1].span_pos == pytest.approx(502.49, abs=0.01)
    assert any("designed 500.0 mm" in n for n in notes)


def test_dihedral_panel_can_be_cut_at_its_plan_span():
    d, notes = load_surface(DIHEDRAL, span="plan")
    assert d.sections[1].span_pos == pytest.approx(500.0)
    assert any("2.5 mm short of the design" in n for n in notes)
    with pytest.raises(ValueError):
        load_surface(DIHEDRAL, span="projected")
