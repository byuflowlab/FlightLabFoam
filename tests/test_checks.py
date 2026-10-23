import numpy as np
import pytest

from flightlabfoam import toolpath
from flightlabfoam.checks import check, feature_checks
from flightlabfoam.geometry import panel_ends
from flightlabfoam.model import ControlCut, Hole, Spar


def messages(design, settings):
    tp = toolpath.build(design, settings, 0)
    return [c["message"] for c in check(tp, design, settings)]


def test_default_features_on_a_normal_wing_raise_nothing(design):
    design.spars = [Spar()]
    design.holes = [Hole()]
    design.control_cuts = [ControlCut(enabled=True)]
    assert feature_checks(panel_ends(design, 0), 2.0) == []


def test_a_hole_that_only_breaks_through_at_the_thin_tip(tapered):
    # 10 mm hole at mid-chord: fits the 200 mm root, not the 120 mm SD7037 tip
    tapered.holes = [Hole()]
    found = feature_checks(panel_ends(tapered, 0), 2.0)
    assert "the lightening hole breaks through the top surface at the tip" in found
    assert not any("at the root" in m or "at both ends" in m for m in found)


def test_slot_deeper_than_the_wing_breaks_through_the_top(design, settings):
    design.spars = [Spar(x_c=0.3, depth=40.0)]
    assert any("square spar breaks through the top surface at both ends" in m for m in messages(design, settings))


def test_hole_too_big_breaks_through_both_skins(design, settings):
    design.holes = [Hole(x_c=0.5, diameter=30.0)]
    msgs = messages(design, settings)
    assert any("breaks through the top surface" in m for m in msgs)
    assert any("breaks through the bottom surface" in m for m in msgs)


def test_thin_wall_to_the_skin_uses_the_setting(design, settings):
    ends = panel_ends(design, 0)
    up = np.interp(100.0, *ends.skins[0][0].T)
    lo = np.interp(100.0, *ends.skins[0][1].T)
    # put a 10 mm hole 1 mm under the top skin
    design.holes = [Hole(x_c=0.5, diameter=10.0, y_offset=(up - 6.0) - 0.5 * (up + lo))]
    found = feature_checks(panel_ends(design, 0), 2.0)
    assert len(found) == 1 and found[0].startswith("only 1.0 mm of foam between the lightening hole and the top surface")
    assert feature_checks(panel_ends(design, 0), 0.5) == []


def test_two_holes_close_together_and_overlapping(design):
    design.holes = [Hole(x_c=0.45, diameter=8.0), Hole(x_c=0.5 + 0.5 / 200, diameter=8.0)]
    # centres 10.5 mm apart: 2.5 mm of foam between 8 mm holes
    found = feature_checks(panel_ends(design, 0), 3.0)
    assert any(m.startswith("only 2.5 mm of foam between the lightening hole 1 and the lightening hole 2") for m in found)
    design.holes[1].x_c = 0.47
    found = feature_checks(panel_ends(design, 0), 3.0)
    assert any("lightening hole 1 and the lightening hole 2 intersect at both ends" in m for m in found)


@pytest.mark.parametrize("kind", ["rect", "u"])
def test_hole_entering_through_a_slot_is_cut_from_the_slot_floor(tapered, settings, kind):
    tapered.spars = [Spar(kind=kind, x_c=0.3, width=12.0, depth=5.0)]
    tapered.holes = [Hole(x_c=0.31, diameter=12.0)]
    ends = panel_ends(tapered, 0)
    assert ends.root.shape == ends.tip.shape
    found = feature_checks(ends, 2.0)
    assert any("intersect" in m for m in found)
    tp = toolpath.build(tapered, settings, 0)
    assert len(tp.xy) > 0


def test_hinge_cut_inside_a_slot_is_allowed(design):
    design.spars = [Spar(x_c=0.75, width=10.0, depth=4.0)]
    design.control_cuts = [ControlCut(enabled=True, hinge_x_c=0.75)]
    ends = panel_ends(design, 0)
    assert ends.root.shape == ends.tip.shape


def test_cuts_that_cannot_be_built_are_still_errors(design):
    design.spars = [Spar(x_c=0.3, width=10.0), Spar(x_c=0.32, width=10.0)]
    with pytest.raises(ValueError, match="slots overlap on the bottom surface"):
        panel_ends(design, 0)
    design.spars = [Spar(x_c=0.3, width=10.0)]
    design.holes = [Hole(x_c=0.3 + 5.0 / 200)]  # the slit lands on the slot wall
    with pytest.raises(ValueError, match="at the edge of the square spar slot"):
        panel_ends(design, 0)
