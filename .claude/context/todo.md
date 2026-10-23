# To do

## Verify on the machine
- [ ] Measure carriage separation and axis travel; update the defaults in `settings.py` and `settings.yaml`.
- [ ] Time a 50 mm move at F120 with both carriages moving; set the default feed model to match.
- [ ] Cut an asymmetric test panel to confirm `xy_carriage_side` and left/right handedness.
- [ ] Cut a tapered test panel to calibrate kerf at the slow and fast ends.

## Features
- [ ] Add an exit button top right. 
- [ ] Checks to make sure that the spar slots and lightening holes don't intersect the surface opposite from entry (cutting the airfoil in half). 
- [ ] Double-click student launchers per OS, like flightlab's `student_setup/`.
- [ ] Two panels from one block, stacked or nested, with a collision check.
- [ ] Kerf that depends on the local wire speed, instead of one value per end.
- [ ] Spar slots perpendicular to the local surface rather than vertical; tapered spars (different size at root and tip).
- [ ] Partial-span features: a hot wire can't, but the UI could warn when a feature should stop short.
- [ ] Optional skin/sheeting allowance (shrink the outline by the sheet thickness).
- [ ] More G-code dialects (LinuxCNC XYUV, GRBL XYZA), and inverse-time feed (`G93`).


## Still open, deliberately
- Dihedral is reported but not cut: each panel is cut flat at its true length.
- G-code is always millimetres; inches are display only.
