from types import SimpleNamespace

import numpy as np

from flightlabfoam import postprocess, toolpath
from flightlabfoam.model import Design
from flightlabfoam.settings import Settings


def _tiny_toolpath():
    xy = np.array([[0.0, 18.7541], [10.0041, 18.7541], [10.0, 19.5116], [0.0, 18.7541]])
    feed = np.array([120.0, 120.0, 120.0, 240.0])
    return SimpleNamespace(xy=xy, az=xy.copy(), feed=feed)


EXPECTED_HEAT_ON = (
    "G21\r\n"
    "G17\r\n"
    "G90\r\n"
    "M3\r\n"
    "G1X0.0000Y18.7541A0.0000Z18.7541F120.0000\r\n"
    "G1X10.0041Y18.7541A10.0041Z18.7541\r\n"
    "G1X10.0000Y19.5116A10.0000Z19.5116\r\n"
    "G1X0.0000Y18.7541A0.0000Z18.7541F240.0000\r\n"
    "M5\r\n"
)


def test_mach3_format_byte_for_byte():
    d = Design()
    d.cut.heat_control = True
    assert postprocess.gcode(_tiny_toolpath(), d, Settings()) == EXPECTED_HEAT_ON


def test_heat_off_by_default_writes_no_heat_codes():
    text = postprocess.gcode(_tiny_toolpath(), Design(), Settings())
    assert "M3" not in text and "M5" not in text
    assert text == EXPECTED_HEAT_ON.replace("M3\r\n", "").replace("M5\r\n", "")


def test_heat_dwell_and_custom_codes():
    d = Design()
    d.cut.heat_control = True
    d.cut.heat_dwell_s = 2.5
    s = Settings()
    s.machine.heat_on_code, s.machine.heat_off_code = "M7", "M9"
    lines = postprocess.gcode(_tiny_toolpath(), d, s).split("\r\n")
    assert lines[3:5] == ["M7", "G4 P2.5"]
    assert lines[-2] == "M9" and lines[-1] == ""


def test_real_panel_file_is_well_formed(design, settings):
    design.cut.comment_header = True
    tp = toolpath.build(design, settings, 0)
    text = postprocess.gcode(tp, design, settings)
    assert text.endswith("\r\n") and "\n" not in text.replace("\r\n", "")
    lines = text.split("\r\n")[:-1]
    comments = [l for l in lines if l.startswith("(")]
    assert comments and all(l.count("(") == 1 and l.endswith(")") for l in comments)
    moves = [l for l in lines if l.startswith("G1X")]
    assert len(moves) == len(tp.xy)
    assert all(" " not in m for m in moves)
    # straight panel with the xy feed model: F on the first move and on the exit only
    assert [m for m in moves if "F" in m] == [moves[0], moves[-1]]
    assert "G0" not in text.replace("G01", "") and "%" not in text and "M30" not in text


def test_filename(design, settings):
    design.name = "My wing/v2"
    tp = toolpath.build(design, settings, 0, "left")
    assert postprocess.filename(design, tp) == "My-wing-v2-panel1-left.nc"
