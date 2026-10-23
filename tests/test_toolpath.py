import numpy as np
import pytest

from flightlabfoam import toolpath
from flightlabfoam.geometry import panel_ends


@pytest.mark.parametrize(
    "side, entry, xy_side, expected",
    [
        ("right", "leading", "left", "az"),
        ("right", "trailing", "left", "xy"),
        ("left", "leading", "left", "xy"),
        ("left", "trailing", "left", "az"),
        ("right", "leading", "right", "xy"),
    ],
)
def test_root_carriage(side, entry, xy_side, expected):
    assert toolpath.root_carriage(side, entry, xy_side) == expected


def test_straight_panel_carriages_match_and_lead_in(design, settings):
    design.cut.entry = "leading"
    tp = toolpath.build(design, settings, 0)
    assert np.allclose(tp.xy, tp.az)
    assert tp.kind[0] == "start" and tp.kind[-1] == "exit"
    assert tp.xy[0, 0] == 0.0 and tp.xy[-1, 0] == 0.0
    assert tp.xy[1, 0] == pytest.approx(design.block(0).cut_in)  # first contact
    assert tp.xy[1, 1] == pytest.approx(tp.xy[0, 1])  # horizontal lead-in
    assert tp.xy[2, 1] > tp.xy[1, 1]  # leading edge first, upper surface first
    # auto block: the margin sits below the panel
    assert tp.face_root[:, 1].min() == pytest.approx(design.block(0).margin)


def test_trailing_edge_first_enters_at_the_trailing_edge(design, settings):
    tp = toolpath.build(design, settings, 0)
    le_x = tp.root[np.argmax(tp.root[:, 0]), 0]
    assert le_x == pytest.approx(design.block(0).cut_in + design.sections[0].chord, abs=1e-6)


def test_carriage_paths_are_linear_extrapolations(tapered, settings):
    tp = toolpath.build(tapered, settings, 0)
    pl = tp.placement
    span = pl.w_tip - pl.w_root
    expect_xy = tp.root + (tp.tip - tp.root) * (0.0 - pl.w_root) / span
    expect_az = tp.root + (tp.tip - tp.root) * (settings.machine.carriage_separation - pl.w_root) / span
    assert np.allclose(tp.xy, expect_xy) and np.allclose(tp.az, expect_az)
    # every cut vertex at the wing root is a point of the root outline (or the trailing-edge midpoint)
    outline = pl.to_machine(panel_ends(tapered, 0).root)
    te_mid = 0.5 * (outline[0] + outline[-1])
    candidates = np.vstack([outline, te_mid])
    cut = np.array([k in ("lead_in", "cut") for k in tp.kind])
    dist = np.min(np.linalg.norm(tp.root[cut][:, None, :] - candidates[None, :, :], axis=2), axis=1)
    assert np.all(dist < 1e-9)


def test_no_consecutive_duplicate_vertices(design, settings):
    tp = toolpath.build(design, settings, 0)
    step = np.abs(np.diff(np.hstack([tp.xy, tp.az]), axis=0)).max(axis=1)
    assert np.all(step > 1e-5)


@pytest.mark.parametrize("basis", ["faster_carriage", "slower_carriage", "root", "tip"])
def test_feed_basis_holds_the_reference_speed(tapered, settings, basis):
    tapered.cut.feed_basis = basis
    tp = toolpath.build(tapered, settings, 0)
    cut = np.array([k in ("lead_in", "cut") for k in tp.kind])
    minutes = tp.seconds / 60
    prev = lambda a: np.vstack([[0, 0], a[:-1]])
    l_xy = np.linalg.norm(tp.xy - prev(tp.xy), axis=1)
    l_az = np.linalg.norm(tp.az - prev(tp.az), axis=1)
    ref = {
        "faster_carriage": np.maximum(l_xy, l_az),
        "slower_carriage": np.minimum(l_xy, l_az),
        "root": np.linalg.norm(tp.root - prev(tp.root), axis=1),
        "tip": np.linalg.norm(tp.tip - prev(tp.tip), axis=1),
    }[basis]
    ok = cut & (ref > 1e-6)
    assert np.allclose(ref[ok] / minutes[ok], tapered.cut.feed, rtol=1e-9)
    # with the xy feed model, F is the X/Y carriage speed
    assert np.allclose(tp.feed[ok], l_xy[ok] / minutes[ok], rtol=1e-9)


def test_tapered_panel_makes_the_tip_carriage_slower(tapered, settings):
    tp = toolpath.build(tapered, settings, 0)
    root_side = tp.xy if tp.placement.root_on == "xy" else tp.az
    tip_side = tp.az if tp.placement.root_on == "xy" else tp.xy
    assert np.ptp(root_side[:, 0]) > np.ptp(tip_side[:, 0])


def test_left_wing_swaps_carriages(tapered, settings):
    right = toolpath.build(tapered, settings, 0, "right")
    left = toolpath.build(tapered, settings, 0, "left")
    assert right.placement.root_on != left.placement.root_on
    assert np.allclose(right.xy, left.az) and np.allclose(right.az, left.xy)
