"""Static checks for the no-install student launch path."""

from pathlib import Path
import re
import tomllib

ROOT = Path(__file__).parents[1]
SETUP = ROOT / "student_setup"
LAUNCHERS = (
    Path("macos") / "Start FlightLabFoam.command",
    Path("windows") / "Start FlightLabFoam.cmd",
    Path("linux") / "Start FlightLabFoam.sh",
)


def test_release_and_launcher_fallbacks_are_exact_git_commits():
    release = (SETUP / "release.txt").read_text().strip()
    assert re.fullmatch(r"[0-9a-f]{40}", release)
    fallbacks = {
        re.search(r'FLIGHTLABFOAM_DEFAULT_COMMIT="?([0-9a-f]{40})"?', (SETUP / path).read_text()).group(1)
        for path in LAUNCHERS
    }
    assert len(fallbacks) == 1


def test_launchers_use_managed_python_and_the_controlled_release_channel():
    for relative_path in LAUNCHERS:
        source = (SETUP / relative_path).read_text()
        assert "student_setup/release.txt" in source
        assert "--python 3.12" in source
        assert "flightlabfoam[pinned]" in source
        # The installed environment is replaced on every update, so the machine
        # settings must be kept outside it.
        assert "-m flightlabfoam --settings" in source
        assert "settings.yaml" in source
        assert "FLIGHTLABFOAM_TEST_ONLY" in source
        # Installed once per promoted commit and then started directly; nothing
        # is re-resolved against PyPI on an ordinary launch.
        assert "installed.txt" in source
        assert "tool run" not in source
        # A failed update keeps the previously installed build usable.
        assert "previously installed build" in source


def test_pinned_extra_is_a_complete_set_of_exact_pins():
    """The launchers install flightlabfoam[pinned]; every library must be frozen."""
    pyproject = (ROOT / "pyproject.toml").read_text()
    assert "# BEGIN PINS" in pyproject and "# END PINS" in pyproject
    project = tomllib.loads(pyproject)["project"]
    pins = project["optional-dependencies"]["pinned"]
    for pin in pins:
        assert re.match(r"[A-Za-z0-9_.-]+==\S+", pin), pin
    names = {re.match(r"[A-Za-z0-9_.-]+", pin).group(0).lower() for pin in pins}
    for requirement in project["dependencies"]:
        assert re.match(r"[A-Za-z0-9_.-]+", requirement).group(0).lower() in names, requirement
    assert "werkzeug" in names  # a transitive dependency, so the set is complete


def test_every_launcher_ships_with_start_here_notes_and_a_download_build():
    for relative_path in LAUNCHERS:
        assert (SETUP / relative_path.parent / "START HERE.txt").exists()
    build = (SETUP / "build_downloads.sh").read_text()
    for name in ("macOS", "Windows", "Linux"):
        assert f"FlightLabFoam-{name}.zip" in build
    workflow = (ROOT / ".github" / "workflows" / "student-launchers.yml").read_text()
    for runner in ("macos-latest", "windows-latest", "ubuntu-latest"):
        assert runner in workflow
