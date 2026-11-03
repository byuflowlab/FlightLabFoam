# To do

## Verify on the machine
- [ ] Measure axis travel; update the defaults in `settings.py` and `settings.yaml`.
- [ ] Time a 50 mm move at F120 with both carriages moving; set the default feed model to match.
- [ ] Cut an asymmetric test panel to confirm `xy_carriage_side` and left/right handedness.
- [x] Done 2026-10-27: Measure carriage separation. 30.4375 in = 773.1125 mm, now the default in `settings.py` and `settings.yaml`.
- [x] Done 2026-10-31: Cut block 1 (kerf off, 0.5 mm trailing edge). Kerf ≈ 0.9 mm, separation 769 ± 4 mm, and the tail melted where the part was under about 1 mm thick. Recorded in `calibration/runs/`, with a student's main wing at half weight.
- [x] Done 2026-11-02: Cut block 2 (kerf compensation 0.9 mm, trailing edges 1/2/3 mm) and record it in `calibration/runs/`. All three parts kept their chord, so the minimum trailing edge stays 1 mm (warning above 2 mm).
- [ ] Remeasure block 2 (2026-11-03), rerun `analyze.py`, then set the default kerf offset (block 2 parts suggest about 1.1 mm) and carriage separation (block 1 769 vs block 2 797 mm, unresolved).
- [ ] Design a validation cut for block 3 (165 × 305 × 50.8 mm) once the results are in: a tapered panel with kerf compensation on, measured against its design. If block 2 goes well, use block 3 to test a separate trailing-edge kerf as well (see Features).
- [ ] Measure the axis travel.
- [ ] Cut a tapered test panel to calibrate kerf at the slow and fast ends.

## Features
- [x] Done 2026-10-23: Add an exit button top right. It stops the server through `/api/shutdown`.
- [x] Done 2026-10-23: Checks to make sure that the spar slots and lightening holes don't intersect the surface opposite from entry (cutting the airfoil in half). `checks.feature_checks` warns on a breakthrough of either skin, on walls thinner than the minimum-wall setting, and on features intersecting each other.
- [ ] Double-click student launchers per OS, like flightlab's `student_setup/`.
- [ ] Two panels from one block, stacked or nested, with a collision check.
- [ ] Kerf that depends on the local wire speed, instead of one value per end.
- [ ] A separate kerf for the trailing edge, where the thin tail melts back more than the surfaces do. Build it after block 2 and test it on block 3.
- [ ] Spar slots perpendicular to the local surface rather than vertical; tapered spars (different size at root and tip).
- [ ] Partial-span features: a hot wire can't, but the UI could warn when a feature should stop short.
- [ ] Optional skin/sheeting allowance (shrink the outline by the sheet thickness).
- [ ] More G-code dialects (LinuxCNC XYUV, GRBL XYZA), and inverse-time feed (`G93`).


## Still open, deliberately
- Dihedral is not cut: each panel is cut flat, at its true length by default or at its plan span (chosen on the Load tab).
- G-code is always millimetres; inches are display only.
