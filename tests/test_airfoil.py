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
