# FlightLabFoam

A local web app that designs wing panels and writes G-code for a 4-axis hot-wire foam cutter. The designer runs in your browser; a small Python server on your own machine does the geometry and writes the files. Nothing leaves your computer.

Note: This build targets the yellow foam cutter at BYU. If you're using a different foam cutter make sure to change your cutter profile in settings. 

## Quick start

You need [uv](https://docs.astral.sh/uv/), which downloads the right Python and libraries by itself. Install it once:

- macOS and Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Windows (PowerShell): `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`

These download a ready-made uv in a few seconds. Open a new terminal afterwards so it can find `uv`. On an Apple-silicon Mac, `brew install uv` also works, but avoid it on an Intel Mac: Homebrew no longer has prebuilt packages for Intel and compiles uv from source, which can take half an hour.

Then, from this folder:

```bash
uv run flightlabfoam
```

The first run takes a minute to set up. A browser tab opens at `http://127.0.0.1:5150/`. Keep the terminal open while you work. To stop, click **Exit** at the top right of the app, or press `Ctrl-C` in the terminal. Use `--port 8000` for a different port and `--no-open` to skip opening the browser.

Your design autosaves in the browser. Use **Save project** to keep a `.foam.json` file, and **Open** to load one.

## Using the app

The tabs run left to right in the order you would use them. The bar under the tabs picks the panel and wing half that the views, checks and animation show, and the button at its right says whether that panel is ready to cut. Click the button to see the checks.

- **Load airplane** reads a `.flightlab.json` project saved from the FlightLab workbench. Pick a lifting surface and its stations become panels, with airfoils, chords, sweep and twist carried over. Each panel is cut flat, so a surface with dihedral gets a choice on this tab: cut each panel at its length along the panel (the default), so the wing has its designed span once tilted, or at the plan span, which is a little shorter and fits shorter foam. An elevator hinge is loaded with cutting switched off. FlightLab files carry no spar positions.
- **Wing design** (the default) sets symmetric or one-sided, the number of panels, and a table of sections from root to tip: airfoil (bundled, any NACA 4-digit, or an uploaded `.dat` in Selig or Lednicer format), chord, span position, sweep as a leading-edge offset, and twist. Under the table, set how many points describe each airfoil surface and how tightly they gather at the leading edge; a readout gives the resulting spacing in millimetres. The view underneath switches between the whole wing from above, the selected panel in the machine from above, and the airfoils from the side.
- **Spars, holes & control surfaces** adds square or U slots and round tubes for spars, round lightening holes, and hinge-line cuts for ailerons and elevators. Every cut enters from the bottom of the wing by default, keeping the top surface clean; each one can be switched to enter from the top. A hot wire cannot start inside the foam, so tubes and holes are reached through a thin slit. Positions are fractions of the local chord, so they follow the taper; sizes are the same at both ends. Every feature runs the full length of the panels it applies to. Features may overlap: a hole or hinge cut whose entry falls inside a spar slot is cut from the slot's floor. Each feature is checked at the root and the tip and gets a warning if it breaks through a skin, intersects another feature, or leaves less foam than the minimum wall thickness (set in the ☰ settings, 2 mm by default) between itself and a skin or another feature. Two overlapping slots, or an entry that lands exactly on a slot wall, can't be cut and are reported as errors.
- **Placement** has three boxes for the selected panel. The first sizes the foam block, automatically with a margin or by hand. **Block placement** sets where the block sits in the cutting area: its distance from program zero along X and Y, and its position between the carriages. **Panel placement** sets where the panel sits inside the block: the cut-in distance and the vertical and span-wise offsets. Everything is centred by default.
- **Cutting settings**: whether the file switches the wire heat (off by default), cutting speed and where it is held, exit speed, leading or trailing edge first (trailing by default), kerf offset at the root and tip, minimum trailing-edge thickness, and an optional comment header. A trailing edge thinner than the minimum in the ☰ settings (1 mm) gets a warning, since a thin edge melts away and shortens the chord, and so does one thicker than the maximum (2 mm), which looks blunt.
- **Cutting animation** plays the selected panel's cut: both carriages, the wire between them, the block and the panel, timed from the programmed feeds.
- **Generate G-code** builds one panel or all of them, left and right halves, shows the checks for each file, and downloads the files singly or as a zip. Files with errors are not offered for download.

The **☰ menu** opens the settings: display units (mm or inches) and the foam cutter profile. They are saved to [settings.yaml](settings.yaml) in this folder.

## Conventions

- **Units.** Everything is stored in millimetres and degrees. Inches are for display only, and G-code is always written in millimetres (`G21`).
- **Sections.** Span position is the distance from the wing root. Sweep is the leading-edge offset, positive aft. Twist is about the leading edge, positive nose up.
- **Machine axes.** One carriage is X (horizontal) and Y (vertical); the other is A (horizontal) and Z (vertical). Every move gives both, so the wire is a straight line between the carriages.
- **Program zero.** This is where you zero the wire before running the file. By default it is the bottom edge of the block's entry face (the face the wire enters): X = 0 on that face and Y = 0 on the block bottom. To zero at a fixed point on the machine instead, enter the block's distance from that point under Block placement. The wire rises from program zero to the entry height, moves across to the entry face, leads in horizontally across the cut-in distance, cuts the airfoil, and leaves the way it came in.
- **Which carriage has the root.** This follows from the wing half, the edge cut first and the side of the X/Y carriage. Looking along +X with the leading edge first, a right wing's tip is on your left. Cutting trailing edge first turns the panel around, and the left wing is the mirror image.
- **Feed.** The cutting speed is held on the reference you choose: the wing root, the wing tip, the faster carriage or the slower carriage. Each move's `F` is then set from how the controller measures speed, which is set in the machine profile.

## Before the first cut

The machine profile in the settings has defaults that need checking against the real machine:

- **Carriage separation** and **travel**, measured on the machine.
- **X/Y carriage side**, seen standing at the entry side looking along +X. Cut a small, clearly asymmetric test panel to confirm left and right come out the right way round.
- **How F is applied.** The ME 415 controller applies F over all four axes, so "Controller applies F to" is set to `all`. On another machine, time the moves in [calibration/README.md](calibration/README.md#feed-model-check) and set it to match.

Then preview the file in the controller's toolpath display before cutting foam.

## Development

```bash
uv sync               # create .venv with the locked versions
uv run pytest         # run the tests
uv run flightlabfoam  # start the app
```

The geometry is a plain Python library with no web code in it, so it can be used and tested on its own:

```python
from flightlabfoam.model import Design
from flightlabfoam.settings import Settings
from flightlabfoam import toolpath, postprocess, checks

design = Design()                      # a straight 500 mm NACA 2412 panel
tp = toolpath.build(design, Settings(), panel=0, side="right")
print(checks.check(tp, design, Settings()))
print(postprocess.gcode(tp, design, Settings()))
```

### How a panel becomes G-code

1. [airfoil.py](flightlabfoam/airfoil.py) loads coordinates (bundled file, NACA 4-digit, or uploaded `.dat`), normalizes them to unit chord with the leading edge at the origin, and splits them into upper and lower surfaces. Each surface is an Akima spline (translated from FLOWMath.jl) in √(x/c), which keeps the nose round even where the file has few points there.
2. [geometry.py](flightlabfoam/geometry.py) builds the root and tip outlines with the same number of points at the same chord fractions. The stations follow a half-cosine, x/c = 1 − cos(π/2 · t^p), which packs points at the leading edge and spends none extra at the trailing edge. It also places feature boundaries at both ends, thickens the trailing edge, offsets by the kerf, inserts the feature cuts, and applies twist and sweep. Point *i* of the root and point *i* of the tip lie on the same wire line.
3. [toolpath.py](flightlabfoam/toolpath.py) places the panel in its block and between the carriages. It orders the path for the entry edge, extends each wire line to the carriage planes, and computes each move's feed.
4. [checks.py](flightlabfoam/checks.py) checks the fit in the block and between the carriages, the axis travel, and the feeds.
5. [postprocess.py](flightlabfoam/postprocess.py) writes the text for a `Dialect`. The first dialect is Mach3 with X/Y and A/Z carriages: `G21 G17 G90`, `G1` moves with four decimals and no spaces, `F` only when it changes, CRLF line endings, and optional heat codes and comments.

[app.py](flightlabfoam/app.py) is a thin Flask layer over these modules. The browser keeps the design and sends it whole with every request, so the server's only state is `settings.yaml`. The front end is plain HTML, CSS and JavaScript in [flightlabfoam/static](flightlabfoam/static) with no build step. The server binds to `127.0.0.1` only and has no authentication, so don't expose it to a network.

| method | path | purpose |
|---|---|---|
| GET/PUT | `/api/settings` | units and machine profile, saved to `settings.yaml` |
| POST | `/api/shutdown` | stop the server (the Exit button) |
| GET | `/api/defaults` | default design and list items |
| GET | `/api/airfoils` | bundled airfoil names |
| POST | `/api/airfoil` | coordinates for a name, or for uploaded `.dat` text |
| POST | `/api/import/flightlab` | a lifting surface from a `.flightlab.json` project |
| POST | `/api/preview` | section outlines plus one panel's toolpath and checks |
| POST | `/api/toolpath` | one panel's toolpath |
| POST | `/api/gcode` | G-code text and checks for one panel or all |
| POST | `/api/gcode.zip` | the same files as a zip |

The bundled airfoils come from the UIUC Airfoil Coordinates Database and match the ones bundled with FlightLab, so airfoil names in FlightLab projects resolve the same way here.
