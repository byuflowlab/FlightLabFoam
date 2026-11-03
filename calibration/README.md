# Calibration cuts

The same three test panels are cut in each of two foam blocks. Each set measures the kerf and the true carriage separation, all at F120 (about 85 mm/min per carriage), and two blocks show whether the results repeat. `make_tests.py` builds them (`uv run python calibration/make_tests.py`), writing a G-code file per test and a `.foam.json` that opens it in the app. Rebuild them after changing the settings, since the swept panels depend on the carriage separation.

| Block | Size: front to back × along the wire × tall | Files |
|---|---|---|
| 1 | 205 × 445 × 50.8 mm | `block1-test-*.nc` |
| 2 | 200 × 457 × 50.8 mm | `block2-test-*.nc` |
| 3 | 165 × 305 × 50.8 mm | kept for a validation cut, designed once the results are in |

In each block:

| Test | Panel | Height in the block | Leading edge from the entry face, X/Y end → A/Z end |
|---|---|---|---|
| A | straight | top, Y 36.6–44.2 mm | 95 → 95 mm |
| B | swept 100 mm | middle, Y 21.6–29.2 mm | 195 → 95 mm |
| C | swept 100 mm the other way | bottom, Y 6.6–14.2 mm | 95 → 195 mm |

All of them are NACA 0015 sections, 50 mm chord and 7.5 mm thick, running the block's full length along the wire. The two blocks differ in how they're cut:

| Block | Kerf compensation | Trailing edge, tests A / B / C | Measures |
|---|---|---|---|
| 1 | off | 0.5 / 0.5 / 0.5 mm | raw kerf, separation |
| 2 | 0.9 mm | 1 / 2 / 3 mm | the thinnest trailing edge that survives, separation again |

Block 1's parts came out 6–9 mm short in chord: the tail melted away back to where the part was under about 1 mm thick. Block 2 compensates for the kerf block 1 measured, so each part should come out at its drawn size, and thickens the trailing edge to a different value on each panel. With compensation on, the leading edges sit about 2 mm further in than the table above (96.8 and 196.8 mm), and block 2 is only 200 mm deep, so just 2 mm of foam is left behind the deepest one; handle it gently.

## Setting up

1. Lay the block with its long side along the wire (445 or 457 mm), its shorter side front to back (205 or 200 mm) and 50.8 mm vertical, centred between the carriages.
2. These cuts go trailing edge first, so the wire enters the face nearest the trailing edges. Zero the wire at the bottom edge of that face.
3. Run the block's three files in any order, with the same wire heat for both blocks. Note the heat setting for the record.
4. Mark each end of the block with the carriage it faced (X/Y or A/Z) before taking it off the machine.

## Measuring

Measure with a ruler, reading to the nearest millimetre, at both ends of the block. Note which end faced which carriage. Repeat readings, by you or someone else, are worth recording: each one goes in the record as another entry in the list.

**Kerf, from thickness.** For each test, measure the maximum thickness of the part, *T*, about 30% back from its leading edge (drawn 7.5 mm), and of the void it left in the block, *T*<sub>void</sub>. Then:

- kerf ≈ (7.5 − *T*) / 2
- kerf ≈ (*T*<sub>void</sub> − 7.5) / 2

With kerf compensation *c* on, add it: kerf ≈ *c* + (7.5 − *T*) / 2 from the part, and (*T*<sub>void</sub> − 7.5) / 2 − *c* from the void. Squeezing the foam reads the part thin and the void thin, so the first estimate runs high and the second low. Their mean is the kerf offset for Cutting settings.

**Trailing edge, from the part.** Measure the part's chord *L* (drawn 50.0 mm) and the thickness of its trailing edge where it ends. Chord isn't a kerf measurement: a thin tail melts away, which shortens the chord whatever the kerf. In block 2, the thinnest trailing edge whose part keeps its full 50 mm chord is the minimum to recommend, and goes into the settings as the minimum trailing edge.

**Separation, from the swept voids.** At each end, measure the distance *d* from the entry face to the leading-edge tip of each void, using the same face for every reading. For each test, Δ = *d*<sub>X/Y end</sub> − *d*<sub>A/Z end</sub>, which should be about 0 for A, +100 for B and −100 for C.

- Δ<sub>A</sub> shows any skew between the entry face and the wire. B and C cancel it, so it's only a check.
- The measured sweep is *S* = (Δ<sub>B</sub> − Δ<sub>C</sub>) / 2.
- The true separation is *D*<sub>true</sub> = *D* · 100 / *S*, where *D* is the separation the G-code was made with.

A larger true separation makes the cut sweep smaller. Kerf doesn't enter: both ends of each swept panel move at the same speed, so the kerf is the same at both ends and cancels in Δ. Each millimetre of separation error changes *S* by only about 0.13 mm, so with ruler readings good to about ±0.5 mm one block pins the separation to about ±4 mm; more blocks narrow it.

## Recording a run

Each block that is cut is a run, kept in its own folder under `runs/`, named by date and block (`runs/2026-10-31-block1/`). The folder holds:

- a copy of every `.foam.json` design and `.nc` file that was cut, so the record still describes what was cut after the generator or the settings change;
- `record.yaml`: the date, the block, the cutting conditions (heat setting, wire, foam), the measuring tool, the machine settings the G-code was made with, the app commit, and every reading, test by test and end by end.

Copy an existing `record.yaml` to start a new one. `analyze.py` reads every run, rebuilds each design to get the drawn sizes, and prints the kerf, the leading-edge positions, and the carriage separation for each run and for all of them together:

```
uv run python calibration/analyze.py
```

Other fields a record can carry, when a cut isn't a standard calibration cut:

- `measured_by`, and a `weight` for the run in the totals (default 1; 0 leaves it out).
- Per test: `side` (right or left wing), `ends` mapping the reading labels to carriages (`{root: az, tip: xy}`), `le_depth_from: back` when *d* was measured from the face opposite the entry, and `exclude`, which leaves out a measurement with the reason recorded.

The separation is a straight-line fit of measured against drawn Δ over all the tests in a run, so the skew drops out, and its ± assumes each reading is good to half the ruler's resolution.

## Results

| Run | Kerf offset | Carriage separation |
|---|---|---|
| 2026-10-30, student main wing (weight 0.5) | 0.76 mm (0.51–1.01) | – (no sweep) |
| 2026-10-31, block 1 | 0.92 mm (0.75–1.25) | 769.3 ± 3.8 mm (set to 773.1) |
| 2026-11-02, block 2 (to be remeasured) | 0.76 mm (0.35–1.15); parts 1.08, voids 0.44 | 797.0 ± 4.1 mm (set to 773.1) |
| All, weighted | 0.82 mm | 782.2 ± 2.8 mm |

Block 1 agrees with the measured 773.1 mm within its uncertainty. Every void's leading edge came out 1–4 mm (mostly 2 mm) shallower than drawn plus kerf, at both depths alike, so it is not the separation: either the block face sat a little past X0, or the wire lags and rounds the leading edge where it turns.

Block 2 disagrees with block 1 by about 5σ, almost all of it from one reading: test B's leading edge at the X/Y end, 193 mm, 4.6 mm shallower than drawn when every other block 2 depth is within 2.6 mm. The block is being remeasured before either separation is used, so the combined 782 mm means nothing yet. Where the block sat between the carriages can't cause this: sliding it along the wire moves both leading edges of a swept panel by the same amount (about 2.2 mm per 10 mm of shift), so Δ doesn't change. The pattern of B and C depths suggests each block sat 3–5 mm off-centre, which is within the reading error.

Block 2's kerf estimates split: the parts imply about 1.1 mm, the voids about 0.4 mm, and part plus void thickness comes to 17.1–17.6 mm where 18.6 is expected. Squeezing the foam would do that. All three parts kept their chord to within 1 mm, with 1, 2 and 3 mm trailing edges, so a 1 mm trailing edge is enough. That's now the minimum, and the app warns above 2 mm, where the tail starts to look blunt. The parts' trailing-edge thicknesses weren't measured.

The student wing was a real cut, not a test panel. An undergraduate measured it, so it counts half. Its void readings and leading-edge depths are left out: with a 2.9 mm cut-in, the foam above and below the wing is nearly cut free, so the void closes up and the depth is just the block's. Its part thicknesses agree with block 1, but only if they were read across the chord line. If they were read as the cambered section's height lying flat, its kerf is about 0.7 mm higher.

Block 1 and the student wing lost 6–9 mm of part chord, with kerf compensation (the wing) and without it (block 1), with 0.5 mm trailing edges. So the loss isn't kerf. It's the thin trailing edge melting away, which block 2's thicker trailing edges fixed.

If two blocks agree, set the kerf offset and the carriage separation to their means. If they disagree by more than the measurement error, something drifted between cuts, such as wire heat or tension, and is worth finding before going further.

## Feed model check

How the controller turns F into carriage speeds is the ☰ setting "Controller applies F to". It is set to `all` (F over all four axes). Blocks 1 and 2 were generated with `xy`, and test C's lead-in, written as F5.4, crawled; run by hand at F120 it cut well, which is what `all` predicts. Under `all`, F120 with both carriages moving equally gives each carriage about 85 mm/min, which is the speed blocks 1 and 2 were cut at and the app's default cutting speed.

The timing test below hasn't been run. It would confirm the setting:

To settle it, run this with the wire cold and no foam, and time each move:

```
G21
G17
G90
G1X50.0000Y0.0000A50.0000Z0.0000F120.0000
G1X50.0000Y50.0000A50.0000Z50.0000
G1X0.0000Y0.0000A0.0000Z0.0000F300.0000
```

| Setting | First move (X and A, 50 mm each) | Second move (Y and Z, 50 mm each) |
|---|---|---|
| `xy`: F is the X/Y carriage speed | 25 s | 25 s |
| `xyz`: F over X, Y and Z, A follows | 25 s | 35 s |
| `all`: F over all four axes | 35 s | 35 s |

Set the one that matches. Every file needs regenerating afterwards.

## Why it works

The wire is a straight line between the two carriages. The program places each carriage's path assuming the carriages are *D* apart. If they are really *D* + δ apart, the wire still passes through the programmed carriage positions. Each block face then sits at a slightly different fraction of the way between the carriages than intended, and the cut there is that blend of the two carriage paths. Anything that changes from one end of the block to the other, such as sweep or taper, comes out scaled by *D* / (*D* + δ). That's independent of where the block sits between the carriages.

A large, untapered sweep is the best thing to measure, for two reasons:

- **Size:** the effect is proportional to it.
- **No kerf bias:** without taper, both carriages trace the same shape, so kerf is identical at both ends.

A smaller block can't do this test. The panel's sweep is magnified by *D* / span at the carriages, and with a short span the carriages run out of room long before the sweep is big enough to measure.
