import numpy as np
import pytest

from flightlabfoam import airfoil


def test_naca0012_is_symmetric_and_normalized():
    c = airfoil.naca4("0012")
    surf = airfoil.Surfaces.from_coords(c)
    x = np.linspace(0, 1, 50)
    assert np.allclose(surf.upper(x), -surf.lower(x), atol=1e-9)
    assert surf.max_thickness() == pytest.approx(0.12, abs=2e-3)
    assert c[:, 0].min() == pytest.approx(0.0, abs=1e-12)
    assert c[:, 0].max() == pytest.approx(1.0, abs=1e-6)


@pytest.mark.parametrize("name", airfoil.available())
def test_bundled_airfoils_parse_upper_above_lower(name):
    surf = airfoil.Surfaces.from_coords(airfoil.load(name))
    x = np.linspace(0.05, 0.95, 30)
    assert np.all(surf.upper(x) > surf.lower(x))


def test_lednicer_and_selig_files_give_the_same_shape():
    # clarky.dat is in Lednicer layout; rewrite it in Selig order and compare
    lednicer = airfoil.load("clarky")
    selig_text = "CLARK Y\n" + "\n".join(f"{x:.6f} {y:.6f}" for x, y in lednicer)
    _, selig = airfoil.parse_dat(selig_text)
    assert np.allclose(selig, lednicer, atol=1e-6)


def test_normalize_handles_percent_scale_and_reversed_order():
    c = airfoil.naca4("2412")
    messy = (c * 100.0)[::-1]
    assert np.allclose(airfoil.normalize(messy), c, atol=1e-9)


def test_lookup_order_embedded_then_bundled_then_naca():
    custom = airfoil.naca4("0006").tolist()
    assert airfoil.Surfaces.from_coords(airfoil.load("clarky", {"clarky": custom})).max_thickness() == pytest.approx(0.06, abs=2e-3)
    assert airfoil.load("NACA 2412").shape[0] > 10  # bundled file, despite the space
    assert airfoil.load("naca0009").shape[0] == 241  # generated
    with pytest.raises(ValueError, match="unknown airfoil"):
        airfoil.load("not-an-airfoil")


def test_parse_dat_rejects_text_without_coordinates():
    with pytest.raises(ValueError):
        airfoil.parse_dat("just a title\nno numbers here\n")


def test_stations_run_from_le_to_te_and_cluster_at_the_nose():
    light, strong = airfoil.stations(80, 1.0), airfoil.stations(80, 1.5)
    for s in (light, strong):
        assert s[0] == 0.0 and s[-1] == pytest.approx(1.0) and np.all(np.diff(s) > 0)
    assert strong[1] < light[1] / 5
    # the trailing edge gets no extra points: the last gap is the widest
    assert np.argmax(np.diff(light)) == len(light) - 2


def test_spline_passes_through_the_data():
    for name in airfoil.available():
        s = airfoil.Surfaces.from_coords(airfoil.load(name))
        assert np.allclose(s.upper(s.x_upper), s.y_upper, atol=1e-12)
        assert np.allclose(s.lower(s.x_lower), s.y_lower, atol=1e-12)


def test_spline_keeps_a_sparse_leading_edge_round():
    # naca2412.dat has no points between x/c = 0 and 0.0125; straight lines there cut the nose off
    true = airfoil.Surfaces.from_coords(airfoil.naca4("2412", n=2001))
    coarse = airfoil.Surfaces.from_coords(airfoil.load("naca2412"))
    x = np.linspace(0.0, 0.0125, 200)
    linear = np.interp(x, coarse.x_upper, coarse.y_upper)
    assert np.abs(linear - true.upper(x)).max() > 0.004
    assert np.abs(coarse.upper(x) - true.upper(x)).max() < 0.002
