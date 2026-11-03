import pytest

from flightlabfoam.app import create_app
from flightlabfoam.model import Design
from flightlabfoam.settings import Settings


@pytest.fixture
def settings_path(tmp_path):
    return tmp_path / "settings.yaml"


@pytest.fixture
def client(settings_path):
    app = create_app(settings_path)
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture
def settings():
    s = Settings()
    s.machine.feed_model = "xy"  # the expected F values in the tests are written for this model
    return s


@pytest.fixture
def design():
    """A straight one-panel wing with no kerf and a sharp trailing edge allowed."""
    d = Design()
    d.cut.te_min_thickness = 0.0
    d.cut.points_per_surface = 40
    return d


@pytest.fixture
def tapered():
    """A tapered, swept, twisted panel with different root and tip airfoils."""
    d = Design()
    d.sections[0].airfoil = "naca2412"
    d.sections[1].airfoil = "sd7037"
    d.sections[1].chord = 120.0
    d.sections[1].x_le = 50.0
    d.sections[1].twist = -3.0
    d.cut.te_min_thickness = 0.0
    d.cut.points_per_surface = 40
    return d
