# To do

## Verify on the machine
- [ ] Measure axis travel; update the defaults in `settings.py` and `settings.yaml`.
- [ ] Time a 50 mm move at F120 with both carriages moving; set the default feed model to match.
- [ ] Cut an asymmetric test panel to confirm `xy_carriage_side` and left/right handedness.
- [x] Done 2026-10-27: Measure carriage separation. 30.4375 in = 773.1125 mm, now the default in `settings.py` and `settings.yaml`.
- [x] Done 2026-10-31: Cut block 1 (kerf off, 0.5 mm trailing edge). Kerf ≈ 0.9 mm, separation 769 ± 4 mm, and the tail melted where the part was under about 1 mm thick. Recorded in `calibration/runs/`, with a student's main wing at half weight.
- [x] Done 2026-11-02: Cut block 2 (kerf compensation 0.9 mm, trailing edges 1/2/3 mm) and record it in `calibration/runs/`. All three parts kept their chord, so the minimum trailing edge stays 1 mm (warning above 2 mm).
- [ ] Remeasure block 2 (2026-11-03), rerun `analyze.py`, then set the default kerf offset (block 2 parts suggest about 1.1 mm) and carriage separation (block 1 769 vs block 2 797 mm, unresolved).
- [ ] Cut block 3 round 1 (built 2026-11-11 in `make_tests.py`): straight NACA 0012 panels at 50 and 140 mm/min. Read thickness at several chord stations too (thin-foam check, see the calibration README).
- [ ] Fit kerf against speed, then build and cut block 3 round 2: the tapered panel (about 64 / 38 mm/min at its ends) with `--taper-kerf ROOT TIP` from the fit. It is also block 3's validation cut.
- [ ] Measure the axis travel.

## Features
- [x] Done 2026-10-23: Add an exit button top right. It stops the server through `/api/shutdown`.
- [x] Done 2026-10-23: Checks to make sure that the spar slots and lightening holes don't intersect the surface opposite from entry (cutting the airfoil in half). `checks.feature_checks` warns on a breakthrough of either skin, on walls thinner than the minimum-wall setting, and on features intersecting each other.
- [x] Done 2026-11-03: Double-click student launchers per OS, like flightlab's `student_setup/`. Built and tested locally; not live until the repo is public and a commit is promoted (see `student_setup/RELEASE_CHECKLIST.md`).
- [ ] Two panels from one block, stacked or nested, with a collision check.
- [ ] Kerf that depends on the local wire speed, instead of one value per end. Goal (2026-11-11): collect kerf-vs-speed data from every recorded cut, fit a low-order regression to it, and have the app suggest a root and tip kerf from the design and settings. The form of the fit isn't chosen in advance; let the data pick it. The user can always override the suggestion.
- [ ] A separate kerf for the trailing edge, where the thin tail melts back more than the surfaces do. Build it after block 2 and test it on block 3.
- [ ] Spar slots perpendicular to the local surface rather than vertical; tapered spars (different size at root and tip).
- [ ] Partial-span features: a hot wire can't, but the UI could warn when a feature should stop short.
- [ ] Optional skin/sheeting allowance (shrink the outline by the sheet thickness).
- [ ] More G-code dialects (LinuxCNC XYUV, GRBL XYZA), and inverse-time feed (`G93`).


## Still open, deliberately
- Dihedral is not cut: each panel is cut flat, at its true length by default or at its plan span (chosen on the Load tab).
- G-code is always millimetres; inches are display only.
