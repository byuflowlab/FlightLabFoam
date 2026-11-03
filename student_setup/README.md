# FlightLabFoam student launchers

These launchers are the no-Git, no-Python-install route for students. Give each student the ZIP file for their operating system. The first launch downloads a private copy of Python and FlightLabFoam; later launches start that copy directly.

## Student directions

1. Download the launcher for your computer and unzip it.
2. Open it by double-clicking it (on Linux, run it from a terminal; see below).
3. Keep the small launcher window open while using FlightLabFoam in your browser.
4. Click **Exit** in the app, or close the launcher window, when you are finished.

The first launch needs an internet connection and takes a few minutes. Later launches take a few seconds: the launcher only checks a small release file and then starts the installed copy. This setup does not change the computer's normal Python installation and does not require Git or administrator access.

### macOS

Open **Start FlightLabFoam.command**. If macOS blocks it because it was downloaded, Control-click the file, choose **Open**, and then choose **Open** again. This is normally needed only once.

### Windows

Open **Start FlightLabFoam.cmd**. If Windows SmartScreen appears, choose **More info**, verify that the file came from the course, and choose **Run anyway**.

### Linux

Open a terminal in the unzipped folder and run `bash "Start FlightLabFoam.sh"`. Most desktop file managers can also run it directly (right-click, **Run as a Program**), or make it executable once with `chmod +x "Start FlightLabFoam.sh"`. The script needs `curl` or `wget`, which nearly every distribution includes.

## Updating FlightLabFoam

Keep using the same launcher. Each time it starts, it checks the small `student_setup/release.txt` file in this repository. If the instructor has promoted a new build, the launcher installs it into a fresh environment. If that install fails part-way (for example, the connection drops), the previously installed build starts instead. If the update check itself fails, the already-installed build starts without any network access.

## Settings survive updates

The app normally keeps its settings (display units and the foam cutter profile) in `settings.yaml` at the repository root. A launcher install has no repository, and its environment is deleted and rebuilt on every update, so the launchers pass `--settings` pointing at `settings.yaml` in the FlightLabFoam data folder (see [What the launchers do](#what-the-launchers-do)). The file is created from the defaults on first use and is never touched by an update or a reinstall of the environment. Saved `.foam.json` project files are wherever the student saved them and are also unaffected.

When a new build changes a default in the machine profile, students who already have a `settings.yaml` keep their old value; a missing key takes the new default. To push a changed value to everyone, have them delete `settings.yaml` (see [Resetting a student's installation](#resetting-a-students-installation)).

## Library versions are frozen

The `pinned` extra in `pyproject.toml` lists every third-party package at one exact version, resolved once for Windows, macOS, and Linux on Python 3.12. Because the launchers install `flightlabfoam[pinned]` from the promoted commit, every student receives the same libraries no matter when they first install or update. Only FlightLabFoam itself changes from one promoted build to the next.

The pins are generated, not hand-edited, from the core `dependencies` in `pyproject.toml`. Before a course starts, refresh them with `uv` on the PATH:

```bash
python student_setup/update_pins.py
uv lock
uv sync
uv run pytest
uv run flightlabfoam
```

Then commit and promote as usual. Do not edit the block between `BEGIN PINS` and `END PINS` by hand; rerun the script instead. To add or drop a dependency without moving any other pin, add it to `dependencies` and run `python student_setup/update_pins.py --keep`.

## Resetting a student's installation

A student whose installed environment is broken can force a clean reinstall of the current build. Re-downloading the launcher ZIP alone does **not** do this: the environment lives outside the ZIP and the launcher will keep starting it. Deleting `installed.txt` makes the next launch rebuild the environment; deleting the whole folder also re-downloads `uv` and Python and resets the settings.

**Windows.** Press the Windows key and R together, paste `%LOCALAPPDATA%\FlightLabFoam`, and press Enter. Delete `installed.txt` (or `settings.yaml` to reset the settings), or go up one level and delete the whole `FlightLabFoam` folder. Then open **Start FlightLabFoam.cmd** again.

**macOS.** Click the desktop so Finder is active, press Shift, Command, and G together, paste `~/.local/share/flightlabfoam`, and press Return. Drag `installed.txt` (or `settings.yaml`) to the Trash, or press Command and the up arrow and drag the whole `flightlabfoam` folder to the Trash. Then open **Start FlightLabFoam.command** again. From Terminal the equivalent is `rm ~/.local/share/flightlabfoam/installed.txt`.

**Linux.** Same folder as macOS: `rm ~/.local/share/flightlabfoam/installed.txt` (or `rm -rf ~/.local/share/flightlabfoam`), then run the launcher again. If `XDG_DATA_HOME` is set, the folder is under that directory instead.

## What the launchers do

They install `uv` into a FlightLabFoam-only folder in the student's user account (`~/.local/share/flightlabfoam` on macOS and Linux, `%LOCALAPPDATA%\FlightLabFoam` on Windows). The first time a build is seen, `uv` downloads Python 3.12, creates a virtual environment in that folder, and installs `flightlabfoam[pinned]` from the promoted Git commit's source archive on GitHub. The commit hash is recorded in `installed.txt` next to the environment. On every later launch the launcher compares that file with `release.txt` and, when they match, starts the environment's own Python directly with `python -m flightlabfoam --settings <data folder>/settings.yaml`.

Each launcher also carries a fallback commit (`FLIGHTLABFOAM_DEFAULT_COMMIT`), used only when the very first launch cannot reach `release.txt`. Update it when you rebuild the ZIP files.

Both `release.txt` and the source archives are fetched anonymously, so **the GitHub repository must be public** for the launchers to work.

For a release, first push and test the new code. Then put that tested 40-character commit hash in `student_setup/release.txt` and push that one-file change. Students receive the new build the next time they launch FlightLabFoam. Commits that have not been placed in `release.txt` are never sent to students.

The **Student launcher smoke tests** GitHub Actions workflow runs the real launcher twice (install, then reuse) on macOS, Windows, and Ubuntu, with `FLIGHTLABFOAM_TEST_ONLY=1` so the second run imports the app instead of starting the server. It runs automatically when launcher files change and can also be started manually from the repository's **Actions** tab. Changing only `release.txt` does not rerun it.

After editing any launcher or `START HERE.txt`, rebuild the student ZIP files:

```bash
./student_setup/build_downloads.sh
```

The files to post are then in `student_setup/downloads/`. The short [release checklist](RELEASE_CHECKLIST.md) covers the first launch, ordinary promotion, and rollback.
