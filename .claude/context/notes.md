# Notes

## Session — 2026-10-22

- Built the first working version from an empty repo: the geometry library, the Flask app, the seven-tab browser UI, and the tests (61 passing). The README's "GUI Design" notes became user and developer docs.
- **Stack.** Flask with plain HTML/CSS/JS and no build step. Launched with `uv run flightlabfoam`. The browser holds the design and sends it whole with each request, and the server's only state is `settings.yaml`. Panel was rejected because its plots are static images and the cutting animation would be clunky.
- **Airfoils are owned here**, not imported from flightlab, to avoid pulling in NeuralFoil and Panel. The 8 `.dat` files are the same ones flightlab bundles, and name lookup follows the same order (embedded, then bundled, then NACA 4-digit), so `.flightlab.json` airfoil names resolve identically.
- **Root/tip matching.** Both ends are sampled at shared cosine chord stations. Feature boundaries are added as warped knots, so a fixed-mm slot lands exactly at both ends even though the chords differ. Projection to the carriages is per point along each wire line, which keeps mixed airfoils and twist exact. Kerf is a mitred outline offset. Feature cuts are kerf-compensated analytically (slots narrower, holes smaller, slits unchanged).
- **Machine frame.** X = 0 is the block's entry face and Y = 0 the block bottom. The entry edge faces X = 0, so trailing edge first turns the airfoil around. Which carriage has the root is derived from the wing half, the entry edge and the `xy_carriage_side` setting (`toolpath.root_carriage`).
- **Feed model.** The first default was `xyz`, which made a straight wing's vertical moves F≈170 because Mach3 counts the other carriage's Z axis. The known-good course output uses a constant F120, so `xy` (F = X/Y carriage speed) is the default, and `xyz`/`all` are options. The 50 mm speed test will settle it.
- uv was not installed on the dev machine. A private copy in the session scratchpad created `pyproject.toml`/`uv.lock` (`uv add`). The user needs `brew install uv` to run it.
- Verified in headless Chrome (Playwright driving the installed Chrome): every tab, panel switching, feature editing, the animation, generate/zip, flightlab import, the settings dialog, and inch display. No console errors. Node on this machine is broken (missing llhttp dylib), so JS was not linted.
