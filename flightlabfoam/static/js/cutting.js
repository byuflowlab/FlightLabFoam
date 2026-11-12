'use strict';
// Cutting settings tab.

function renderCutting() {
  const c = state.design.cut, m = state.settings.machine;
  const ch = () => changed();
  const n = (key, kind, extra, after) => numInput(() => c[key], v => { c[key] = kind === 'int' ? Math.round(v) : v; },
    kind === 'int' ? null : kind, after ? () => { ch(); after(); } : ch, extra);
  fill($('#cutting-form'),
    h('h3', {}, 'Wire heat'),
    checkField(`Turn the wire on and off in the file (${m.heat_on_code} / ${m.heat_off_code})`,
      checkInput(() => c.heat_control, v => { c.heat_control = v; }, () => changed(true))),
    c.heat_control ? field('Warm-up pause after heat on', n('heat_dwell_s', 's', { min: 0 }), 's') : null,

    h('h3', {}, 'Speed'),
    field('Cutting speed', n('feed', 'feed', { min: 0 }), 'feed'),
    field('Cutting speed is held on', selectInput([
      ['faster_carriage', 'the faster carriage'],
      ['slower_carriage', 'the slower carriage'],
      ['root', 'the wing root'],
      ['tip', 'the wing tip'],
    ], () => c.feed_basis, v => { c.feed_basis = v; }, ch)),
    field('Exit speed (leaving the block)', n('exit_feed', 'feed', { min: 0 }), 'feed'),

    h('h3', {}, 'Path'),
    field('Edge cut first', selectInput([
      ['trailing', 'Trailing edge first'],
      ['leading', 'Leading edge first'],
    ], () => c.entry, v => { c.entry = v; }, ch)),
    checkField('Write a comment header describing the cut', checkInput(() => c.comment_header, v => { c.comment_header = v; }, ch)),

    h('h3', {}, 'Kerf'),
    field('Kerf offset at the root', n('kerf_root', 'len', { min: 0 }, kerfWarning), 'len'),
    field('Kerf offset at the tip', n('kerf_tip', 'len', { min: 0 }, kerfWarning), 'len'),
    h('div', { class: 'field-warn', id: 'kerf-warn' }),

    h('h3', {}, 'Minimum thickness'),
    field('Add thickness to', selectInput([
      ['lower', 'the lower surface'],
      ['upper', 'the upper surface'],
      ['both', 'both surfaces, half each'],
    ], () => c.thicken_surface, v => { c.thicken_surface = v; }, ch)),
    field('Minimum thickness', n('min_thickness', 'len', { min: 0 }), 'len'),
    field('Minimum trailing-edge thickness', n('te_min_thickness', 'len', { min: 0 }), 'len'),
    field('Trailing edge minimum thickness length', n('te_extent', 'pct', { min: 0, max: 100 }), 'pct'),
  );
  kerfWarning();
}

// On a tapered panel the wire moves slower at the end with the smaller chord and melts more
// there, so suggest a little more kerf at that end. The note stays up as long as the wing is
// tapered, whatever kerf has been entered.
const SLOW_END_KERF_EXTRA = 0.25;  // mm

function kerfWarning() {
  const el = $('#kerf-warn');
  if (!el) return;
  const c = state.design.cut, s = state.design.sections;
  const panels = s.slice(1).map((tip, i) => tip.chord - s[i].chord);
  const tipSmaller = panels.some(d => d < -1e-6), rootSmaller = panels.some(d => d > 1e-6);
  const extra = Units.fmt(SLOW_END_KERF_EXTRA, 'len', 2);
  let msg = '';
  if (tipSmaller && rootSmaller) {
    msg = `⚠ Some panels taper toward the tip and some toward the root. The end with the smaller chord moves slower and melts more; it needs about ${extra} more kerf than the other.`;
  } else if (tipSmaller || rootSmaller) {
    const [slow, fast] = tipSmaller ? ['tip', 'root'] : ['root', 'tip'];
    const want = c[`kerf_${fast}`] + SLOW_END_KERF_EXTRA;
    msg = `⚠ Tapered wing: the ${slow} has the smaller chord, so it moves slower and melts more. ` +
      `Try ${extra} more kerf at the ${slow} than at the ${fast} (${Units.fmt(want, 'len', 2)}).`;
  }
  el.textContent = msg;
}

// The selected panel's airfoil at one end, in its own frame: as designed, thickened, and the
// cut path. 'te' zooms in on the last part of the chord.
let cutViewEnd = 0, cutViewZoom = 'whole';

function drawCutView() {
  const container = $('#cut-view');
  drawInto(container, () => {
    const pv = state.preview && state.preview.panel;
    const e = pv && pv.sections_local && pv.sections_local[cutViewEnd];
    if (!e) return emptyMessage(container, state.previewError || 'No panel to show');
    const W = container.clientWidth, H = container.clientHeight;
    const c = e.chord;
    let x0 = -0.03 * c;
    if (cutViewZoom === 'te') x0 = Math.min(e.te_start === null ? c : e.te_start, 0.85 * c) - 0.05 * c;
    const inView = arr => arr.filter(p => p[0] >= x0);
    const b = bounds([inView(e.cut), inView(e.raw)], 0.04);
    b.x0 = Math.min(b.x0, x0);
    const m = mapper(b, W, H, true, 24);
    const root = svg('svg', { viewBox: `0 0 ${W} ${H}` });
    const clipId = 'cut-view-clip';
    root.append(svg('clipPath', { id: clipId }, svg('rect', { x: m.x(b.x0), y: 0, width: W - m.x(b.x0), height: H })));
    const g = svg('g', { 'clip-path': `url(#${clipId})` });
    g.append(polygon(m, e.nominal, 'fill:var(--root);fill-opacity:.15;stroke:var(--root);stroke-width:1.2'));
    g.append(polygon(m, e.raw, 'fill:none;stroke:var(--muted);stroke-width:1.2;stroke-dasharray:4 3'));
    g.append(polygon(m, e.cut, 'fill:none;stroke:var(--wire);stroke-width:1.6'));
    if (e.te_start !== null) {
      g.append(line(m, [[e.te_start, b.y0], [e.te_start, b.y1]], 'stroke:var(--ink);stroke-width:1;stroke-dasharray:6 3'));
      g.append(label(m, e.te_start, b.y1, `trailing-edge thickness over the last ${Units.fmt(c - e.te_start, 'len')}`, 'end', 12));
    }
    root.append(g);
    // the kerf, dimensioned when it is big enough to see: at the trailing edge when zoomed in,
    // otherwise above the thickest point
    if (e.kerf > 0 && e.kerf * m.k >= 18) {
      const text = `kerf ${Units.fmt(e.kerf, 'len', 2)}`;
      if (cutViewZoom === 'te') {
        // across the gap above the upper surface, partway along the flat tail
        const xd = e.te_start === null ? 0.97 * c : 0.5 * (e.te_start + c);
        const upper = e.nominal.slice(0, Math.ceil(e.nominal.length / 2));  // the outline runs TE, upper, LE, lower
        const top = upper.reduce((best, p) => (Math.abs(p[0] - xd) < Math.abs(best[0] - xd) ? p : best));
        root.append(dimension(m, top, [top[0], top[1] + e.kerf], text));
      } else {
        const xt = e.thick_at;
        const top = e.nominal.reduce((best, p) => (p[1] > 0 && Math.abs(p[0] - xt) < Math.abs(best[0] - xt) ? p : best), [Infinity, 0]);
        root.append(dimension(m, top, [top[0], top[1] + e.kerf], text));
      }
    }
    const end = cutViewEnd === 0 ? 'root' : 'tip';
    container.replaceChildren(root, legend([
      ['var(--muted)', `${end} airfoil as designed`, true],
      ['var(--root)', 'after the minimum thicknesses'],
      ['var(--wire)', `wire path, kerf ${Units.fmt(e.kerf, 'len', 2)} outside`],
    ]));
  });
}

function initCutting() {
  const tabs = (sel, setView) => {
    const buttons = Array.from(document.querySelectorAll(sel + ' button'));
    buttons.forEach(btn => btn.addEventListener('click', () => {
      setView(btn.dataset.view);
      buttons.forEach(x => x.classList.toggle('on', x === btn));
      drawCutView();
    }));
  };
  tabs('#cut-end-tabs', v => { cutViewEnd = +v; });
  tabs('#cut-zoom-tabs', v => { cutViewZoom = v; });
  on('structure', renderCutting);
  on('preview', () => { drawCutView(); kerfWarning(); });
}
