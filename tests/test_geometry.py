import numpy as np
import pytest

from flightlabfoam import airfoil
from flightlabfoam.geometry import panel_ends
from flightlabfoam.model import ControlCut, Hole, Spar


def test_straight_panel_has_identical_ends(design):
    ends = panel_ends(design, 0)
    assert np.allclose(ends.root, ends.tip)
    assert ends.span == pytest.approx(500.0)


def test_mixed_airfoils_reproduce_each_end_exactly(tapered):
    ends = panel_ends(tapered, 0)
    assert ends.root.shape == ends.tip.shape
    for pts, sec in ((ends.root, tapered.sections[0]), (ends.tip, tapered.sections[1])):
        # undo twist and sweep, then compare with the airfoil itself
        a = np.radians(sec.twist)
        unrot = np.array([[np.cos(a), -np.sin(a)], [np.sin(a), np.cos(a)]])
        local = (pts - [sec.x_le, 0.0]) @ unrot.T / sec.chord
        surf = airfoil.Surfaces.from_coords(airfoil.load(sec.airfoil))
        le = ends.le_index
        upper, lower = local[: le + 1], local[le:]
        assert np.allclose(upper[:, 1], surf.upper(upper[:, 0]), atol=1e-9)
        assert np.allclose(lower[:, 1], surf.lower(lower[:, 0]), atol=1e-9)


def test_twist_is_nose_up_about_the_leading_edge(design):
    design.sections[0].twist = 5.0
    ends = panel_ends(design, 0)
    le = ends.root[ends.le_index]
    assert np.allclose(le, [0.0, 0.0], atol=1e-9)
    assert ends.root[0, 1] < -15.0  # trailing edge drops by about chord * sin(5 deg)


def test_kerf_offsets_the_outline_outward(design):
    plain = panel_ends(design, 0).root
    design.cut.kerf_root = design.cut.kerf_tip = 0.5
    kerfed = panel_ends(design, 0).root
    # every kerfed point is about 0.5 mm from the nominal outline, outside it
    d = np.min(np.linalg.norm(kerfed[:, None, :] - plain[None, :, :], axis=2), axis=1)
    assert np.all(d > 0.3) and np.all(d < 1.6)
    assert np.ptp(kerfed[:, 1]) > np.ptp(plain[:, 1])


def test_trailing_edge_is_thickened(design):
    design.cut.te_min_thickness = 1.0
    ends = panel_ends(design, 0)
    assert ends.root[0, 1] - ends.root[-1, 1] == pytest.approx(1.0, abs=1e-6)


def test_square_spar_slot_is_the_same_size_at_both_ends(tapered):
    tapered.spars = [Spar(kind="rect", x_c=0.3, width=8.0, depth=5.0)]
    ends = panel_ends(tapered, 0)
    assert ends.root.shape == ends.tip.shape
    for pts, sec in ((ends.root, tapered.sections[0]), (ends.tip, tapered.sections[1])):
        a = np.radians(sec.twist)
        unrot = np.array([[np.cos(a), -np.sin(a)], [np.sin(a), np.cos(a)]])
        local = (pts - [sec.x_le, 0.0]) @ unrot.T
        xc = 0.3 * sec.chord
        walls = np.unique(np.round(local[np.abs(local[:, 0] - xc) <= 4.0 + 1e-6, 0], 6))
        assert walls.min() == pytest.approx(xc - 4.0) and walls.max() == pytest.approx(xc + 4.0)


@pytest.mark.parametrize(
    "feature",
    [
        Spar(kind="u", x_c=0.25, width=6, depth=6),
        Spar(kind="round", x_c=0.3, diameter=6, surface="lower"),
        Hole(x_c=0.55, diameter=6),
        ControlCut(enabled=True, hinge_x_c=0.75),
        ControlCut(enabled=True, hinge_x_c=0.75, gap=4.0),
    ],
)
def test_features_keep_root_and_tip_matched(tapered, feature):
    tapered.cut.kerf_root, tapered.cut.kerf_tip = 0.4, 0.6
    tapered.spars, tapered.holes, tapered.control_cuts = [], [], []
    {Spar: tapered.spars, Hole: tapered.holes, ControlCut: tapered.control_cuts}[type(feature)].append(feature)
    ends = panel_ends(tapered, 0)
    assert ends.root.shape == ends.tip.shape
    assert len(ends.root) > 2 * tapered.cut.points_per_surface


def test_disabled_and_other_panel_features_are_ignored(design):
    base = panel_ends(design, 0).root.shape
    design.control_cuts = [ControlCut(enabled=False)]
    design.spars = [Spar(panels=[3])]
    assert panel_ends(design, 0).root.shape == base


def test_overlapping_features_are_rejected(design):
    design.spars = [Spar(x_c=0.3, width=10), Spar(x_c=0.32, width=10)]
    with pytest.raises(ValueError, match="overlap"):
        panel_ends(design, 0)
