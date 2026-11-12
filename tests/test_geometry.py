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
        Spar(kind="round", x_c=0.3, diameter=6),
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


def test_clustering_tightens_the_nose_and_point_count_is_respected(design):
    design.cut.le_clustering = 1.0
    light = panel_ends(design, 0)
    design.cut.le_clustering = 1.5
    strong = panel_ends(design, 0)
    assert strong.spacing()["nose"] < light.spacing()["nose"] / 3
    assert light.spacing()["nose"] < light.spacing()["max"]
    design.cut.points_per_surface = 120
    assert len(panel_ends(design, 0).root) == 2 * 120 - 1


def test_point_settings_are_validated(design):
    design.cut.le_clustering = 3.0
    with pytest.raises(ValueError, match="clustering"):
        design.validate()
    design.cut.le_clustering = 1.25
    design.cut.points_per_surface = 5
    with pytest.raises(ValueError, match="points per surface"):
        design.validate()


def test_features_enter_from_the_bottom_by_default(design):
    plain = panel_ends(design, 0)
    design.spars = [Spar(kind="rect")]
    design.holes = [Hole(x_c=0.55)]
    design.control_cuts = [ControlCut(enabled=True)]
    cut = panel_ends(design, 0)
    # the upper surface, trailing edge to leading edge, is untouched
    assert np.allclose(cut.root[: cut.le_index + 1], plain.root[: plain.le_index + 1])
    assert len(cut.root) > len(plain.root)


def _end(airfoil_name: str, chord: float, min_thick: float, te_min: float):
    from flightlabfoam import airfoil
    from flightlabfoam.geometry import _End

    surf = airfoil.Surfaces.from_coords(airfoil.load(airfoil_name))
    return _End(surf, chord, 0.0, 0.0, 0.0, te_min, min_thick, add_to="lower"), surf


def test_minimum_thickness_moves_the_lower_surface_aft_of_the_thickest_point():
    end, surf = _end("naca0012", 80.0, 3.0, 0.0)
    x = np.linspace(0.0, 1.0, 801)
    upper, lower = end.skin("upper", x), end.skin("lower", x)
    np.testing.assert_allclose(upper, surf.upper(x) * 80.0)  # the upper surface is untouched
    aft = x >= end.x_thick
    assert np.all(upper[aft] - lower[aft] >= 3.0 - 1e-9)
    assert np.all(lower <= surf.lower(x) * 80.0 + 1e-9)  # only ever moved down
    # the leading edge, thinner than 3 mm near its tip, keeps its shape
    np.testing.assert_allclose(lower[~aft], surf.lower(x[~aft]) * 80.0)


def test_trailing_edge_is_flat_from_the_last_station_that_thick():
    end, surf = _end("naca0012", 80.0, 1.0, 2.0)
    t_raw = surf.thickness(end.x_te) * 80.0
    assert t_raw == pytest.approx(2.0, abs=0.01)  # x_te is where the airfoil thins to 2 mm
    x = np.linspace(end.x_te + 1e-6, 1.0, 200)
    np.testing.assert_allclose(end.skin("upper", x) - end.skin("lower", x), 2.0)
    ahead = np.linspace(end.x_thick, end.x_te - 1e-6, 200)
    assert np.all(end.skin("upper", ahead) - end.skin("lower", ahead) >= 2.0 - 1e-6)


def test_minimum_thickness_acts_before_the_trailing_edge():
    # with the minimum above the trailing-edge thickness, nothing is left for the tail step
    end, surf = _end("naca0012", 80.0, 2.0, 1.0)
    assert end.x_te == 1.0
    x = np.linspace(end.x_thick, 1.0, 400)
    np.testing.assert_allclose(end.skin("upper", x), surf.upper(x) * 80.0)
    assert end.skin("upper", 1.0) - end.skin("lower", 1.0) == pytest.approx(2.0)


def test_trailing_edge_thickness_is_limited_to_the_last_part_of_the_chord():
    from flightlabfoam import airfoil
    from flightlabfoam.geometry import _End

    surf = airfoil.Surfaces.from_coords(airfoil.load("naca0012"))
    free = _End(surf, 80.0, 0.0, 0.0, 0.0, 2.0, 1.0)
    assert free.x_te < 0.95  # unlimited, the 2 mm tail starts more than 5% from the end
    end = _End(surf, 80.0, 0.0, 0.0, 0.0, 2.0, 1.0, te_extent=0.02)
    assert end.x_te == pytest.approx(0.98)
    x = np.linspace(0.981, 1.0, 50)
    np.testing.assert_allclose(end.skin("upper", x) - end.skin("lower", x), 2.0)
    ahead = np.linspace(free.x_te + 0.005, 0.975, 50)  # thinner than 2 mm but outside the limit
    t = end.skin("upper", ahead) - end.skin("lower", ahead)
    assert np.all(t < 2.0) and np.all(t >= 1.0 - 1e-9)


@pytest.mark.parametrize("add_to, up_share", [("lower", 0.0), ("upper", 1.0), ("both", 0.5)])
def test_added_thickness_goes_on_the_chosen_surface(add_to, up_share):
    from flightlabfoam import airfoil
    from flightlabfoam.geometry import _End

    surf = airfoil.Surfaces.from_coords(airfoil.load("naca2412"))
    end = _End(surf, 100.0, 0.0, 0.0, 0.0, 2.0, 1.0, te_extent=1.0, add_to=add_to)
    x = np.linspace(0.0, 1.0, 801)
    up0, lo0 = surf.upper(x) * 100.0, surf.lower(x) * 100.0
    added = (end.skin("upper", x) - end.skin("lower", x)) - (up0 - lo0)
    assert added.max() > 1.0  # the tail was thickened
    np.testing.assert_allclose(end.skin("upper", x) - up0, up_share * added, atol=1e-9)
    np.testing.assert_allclose(lo0 - end.skin("lower", x), (1 - up_share) * added, atol=1e-9)
    tail = x > end.x_te
    np.testing.assert_allclose((end.skin("upper", x) - end.skin("lower", x))[tail], 2.0)
