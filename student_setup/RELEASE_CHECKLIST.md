# FlightLabFoam student release checklist

## One-time launch

1. Make the GitHub repository public. The launchers download `release.txt` and the source archive without logging in.
2. Commit and push `student_setup/`, the README changes, the setup tests, and the GitHub Actions workflow.
3. Put the pushed commit's hash in `student_setup/release.txt` and in `FLIGHTLABFOAM_DEFAULT_COMMIT` in all three launchers, rebuild the ZIP files with `./student_setup/build_downloads.sh`, and push again.
4. Open the repository's **Actions** tab and confirm that **Student launcher smoke tests** passes on macOS, Windows, and Linux.
5. Post these three files on the course site:
   - `student_setup/downloads/FlightLabFoam-macOS.zip`
   - `student_setup/downloads/FlightLabFoam-Windows.zip`
   - `student_setup/downloads/FlightLabFoam-Linux.zip`

## Ordinary code update

1. Finish and test the changes (`uv run pytest`, then open the app once).
2. Commit and push them to `master`.
3. Run `git rev-parse HEAD` and copy the full 40-character commit hash.
4. Replace the hash in `student_setup/release.txt` and push that one-file change.
5. Tell students to click **Exit** and reopen FlightLabFoam. Their existing launcher checks the release file and installs the promoted build into a fresh environment (under a minute; downloaded libraries are reused). Their settings are kept.

Do not rebuild or repost the ZIP files for an ordinary code update. Rebuild them only when a launcher or its `START HERE.txt` file changes.

## Library refresh

Do this before a course starts, not during it.

1. With `uv` on the PATH, run `python student_setup/update_pins.py`, then `uv lock`.
2. Run the tests and open the app once with the new pins.
3. Commit, push, and promote the commit exactly like an ordinary code update. No new ZIP files are needed.

## Rollback

Put the last known-good commit hash back in `student_setup/release.txt` and push the change. Students return to that build the next time they launch FlightLabFoam.
