'use strict';
// Spars, holes & control surfaces tab: three editable lists and a side view of the cut.

// A dropdown of tick boxes: "All panels", or any set of panels. [] means every panel.
function panelsInput(item) {
  const n = nPanels();
  const summary = h('summary', {});
  const label = () => {
    summary.textContent = !item.panels.length ? 'All panels'
      : item.panels.length === 1 ? `Panel ${item.panels[0] + 1}`
        : `Panels ${item.panels.map(p => p + 1).join(', ')}`;
  };
  const all = h('input', { type: 'checkbox' });
  const boxes = Array.from({ length: n }, () => h('input', { type: 'checkbox' }));
  const sync = () => {
    all.checked = !item.panels.length;
    boxes.forEach((b, i) => { b.checked = !item.panels.length || item.panels.includes(i); });
    label();
  };
  const set = panels => {
    // every panel ticked, or none left, both mean all of them
    item.panels = panels.length === n ? [] : panels;
    sync();
    changed();
  };
  all.addEventListener('change', () => set(all.checked ? [] : [0]));
  boxes.forEach(b => b.addEventListener('change', () => set(boxes.flatMap((x, i) => (x.checked ? [i] : [])))));
  sync();
  const menu = h('div', { class: 'multi-menu' },
    h('label', {}, all, 'All panels'),
    boxes.map((b, i) => h('label', {}, b, `Panel ${i + 1}`)));
  const box = h('details', { class: 'multi-select' }, summary, menu);
  // the table scrolls sideways and would clip the menu, so it is placed against the window
  box.addEventListener('toggle', () => {
    if (!box.open) return;
    const r = summary.getBoundingClientRect();
    Object.assign(menu.style, { left: `${r.left}px`, top: `${r.bottom + 2}px`, minWidth: `${r.width}px` });
  });
  return box;
}

// a click outside an open panel dropdown, or a scroll, closes it
const closePanelMenus = e => {
  document.querySelectorAll('details.multi-select[open]').forEach(d => { if (!e || !d.contains(e.target)) d.open = false; });
};
document.addEventListener('click', closePanelMenus);
window.addEventListener('scroll', () => closePanelMenus(), true);

const SURFACES = [['lower', 'Bottom'], ['upper', 'Top']];

function removeButton(list, i) {
  return h('button', { class: 'btn small danger', type: 'button', title: 'Remove', onclick: () => { list.splice(i, 1); changed(true); } }, '✕');
}

// `advanced`, if given, adds an Advanced tick box to each row; ticked, a second row below sets
// the item at the panel tip, and the main row sets it at the root. advanced = { lead, columns,
// start(item) }: `lead` columns come before the per-end ones, and start() runs when the box is ticked.
function featureTable(table, list, columns, emptyText, advanced) {
  const head = ['On', ...columns.map(c => c[0]), 'Panels', ...(advanced ? ['Advanced'] : []), ''];
  const rows = (item, i) => {
    const main = h('tr', {},
      h('td', {}, checkInput(() => item.enabled, v => { item.enabled = v; }, () => changed())),
      columns.map(c => h('td', {}, c[1](item))),
      h('td', {}, panelsInput(item)),
      advanced ? h('td', {}, checkInput(() => item.advanced, v => { if (v) advanced.start(item); item.advanced = v; }, () => changed(true))) : null,
      h('td', {}, removeButton(list, i)));
    if (!(advanced && item.advanced)) return main;
    const tip = h('tr', { class: 'advanced-row' },
      h('td', { colspan: advanced.lead + 1, class: 'end-label' }, 'At the tip end (the row above is the root end)'),
      advanced.columns.map(c => h('td', {}, c(item))),
      h('td', { colspan: columns.length - advanced.lead - advanced.columns.length + 3 }, advanced.extra ? advanced.extra(item) : null));
    return [main, tip];
  };
  fill(table,
    h('tr', {}, head.map(t => h('th', {}, t))),
    list.length ? list.flatMap(rows) : h('tr', { class: 'empty' }, h('td', { colspan: head.length }, emptyText)),
  );
}

// the arrow buttons step by 0.05, which suits both chord fractions and millimetres
const num = (key, kind) => item => numInput(() => item[key], v => { item[key] = v; }, kind, () => changed(), { step: 0.05 });
const sel = (key, options) => item => selectInput(options, () => item[key], v => { item[key] = v; }, () => changed(true));

// ticking Advanced starts the tip out the same as the root, so nothing changes until edited
const copyToTip = keys => item => { for (const k of keys) item['tip_' + k] = item[k]; };

// the switch for evening out the entry slit when it is longer at one end (see the hint)
const matchEntry = item => h('label', { class: 'inline-check', title: 'When the slit to the hole is longer at one end, the other end first runs out into the scrap and back, so both ends cut the slit at the same speed' },
  checkInput(() => item.match_entry, v => { item.match_entry = v; }, () => changed()), 'Even out the entry slit');

function renderFeatures() {
  const d = state.design, L = Units.label('len');
  // the size and place of a spar; the tip versions read the tip_ fields
  const sparCols = pre => [
    num(pre + 'x_c', 'frac'),
    item => item.kind === 'round' ? '—' : num(pre + 'width', 'len')(item),
    item => item.kind === 'round' ? '—' : num(pre + 'depth', 'len')(item),
    item => item.kind === 'round' ? num(pre + 'diameter', 'len')(item) : '—',
    item => item.kind === 'round' ? num(pre + 'y_offset', 'len')(item) : '—',
  ];
  const [cx, cw, cd, cdia, cy] = sparCols('');
  featureTable($('#spars-table'), d.spars, [
    ['Type', sel('kind', [['rect', 'Square slot'], ['u', 'U slot'], ['round', 'Round tube']])],
    ['From', sel('surface', SURFACES)],
    ['Centre (x/c)', cx],
    [`Width (${L})`, cw],
    [`Depth (${L})`, cd],
    [`Diameter (${L})`, cdia],
    [`Above camber (${L})`, cy],
  ], 'No spars', {
    lead: 2,
    columns: sparCols('tip_'),
    start: copyToTip(['x_c', 'width', 'depth', 'diameter', 'y_offset']),
    extra: item => item.kind === 'round' ? matchEntry(item) : null,
  });
  // the per-end columns come right after the lead ones, so the tip row lines up under them
  featureTable($('#holes-table'), d.holes, [
    ['Slit from', sel('surface', SURFACES)],
    ['Centre (x/c)', num('x_c', 'frac')],
    [`Diameter (${L})`, num('diameter', 'len')],
    [`Above camber (${L})`, num('y_offset', 'len')],
  ], 'No lightening holes', {
    lead: 1,
    columns: [num('tip_x_c', 'frac'), num('tip_diameter', 'len'), num('tip_y_offset', 'len')],
    start: copyToTip(['x_c', 'diameter', 'y_offset']),
    extra: matchEntry,
  });
  featureTable($('#controls-table'), d.control_cuts, [
    ['Surface', sel('kind', [['aileron', 'Aileron'], ['elevator', 'Elevator'], ['flap', 'Flap']])],
    ['Cut from', sel('surface', SURFACES)],
    ['Hinge (x/c)', num('hinge_x_c', 'frac')],
    [`Gap (${L})`, num('gap', 'len')],
  ], 'No control-surface cuts', {
    lead: 2,
    columns: [num('tip_hinge_x_c', 'frac'), num('tip_gap', 'len')],
    start: copyToTip(['hinge_x_c', 'gap']),
  });
  featuresView();
}

// The finished part at each end (the airfoil with every spar, hole and control cut at its own
// size) and the wire path, which runs the kerf outside the part: outside the airfoil, inside
// each hole and slot. 'both', 'root' or 'tip'.
let featuresViewEnds = 'both';

function featuresView() {
  const container = $('#features-view');
  drawInto(container, () => {
    const pv = state.preview && state.preview.panel;
    if (!pv) return emptyMessage(container, state.previewError || 'No panel to show');
    const W = container.clientWidth, H = container.clientHeight;
    const ends = [['root', pv.part_root, pv.root], ['tip', pv.part_tip, pv.tip]]
      .filter(([end]) => featuresViewEnds === 'both' || featuresViewEnds === end);
    // frame the airfoils, not the whole block or the run-in from program zero
    const cutOnly = path => path.filter((p, i) => pv.kind[i] === 'cut');
    const m = mapper(bounds(ends.flatMap(([, part, path]) => [part, cutOnly(path)]), 0.06), W, H, true, 24);
    const root = svg('svg', { viewBox: `0 0 ${W} ${H}` });
    for (const [end, part] of ends) {
      root.append(polygon(m, part, `fill:var(--${end});fill-opacity:.15;stroke:var(--${end});stroke-width:1;stroke-dasharray:4 3`));
    }
    for (const [end, , path] of ends) root.append(line(m, path, `stroke:var(--${end});stroke-width:1.6`));
    const items = ends.flatMap(([end]) => [
      [`var(--${end})`, `${end}: finished part`, 'area'],
      [`var(--${end})`, `${end}: wire path (kerf ${Units.fmt(state.design.cut['kerf_' + end], 'len', 2)} outside the part)`],
    ]);
    container.replaceChildren(root, legend(items));
  });
}

function initFeatures() {
  const add = (key, list) => () => { state.design[list].push(clone(state.defaults[key])); changed(true); };
  $('#add-spar').addEventListener('click', add('spar', 'spars'));
  $('#add-hole').addEventListener('click', add('hole', 'holes'));
  $('#add-control').addEventListener('click', add('control_cut', 'control_cuts'));
  on('structure', renderFeatures);
  document.querySelectorAll('#features-view-tabs button').forEach(btn => btn.addEventListener('click', () => {
    featuresViewEnds = btn.dataset.view;
    document.querySelectorAll('#features-view-tabs button').forEach(x => x.classList.toggle('on', x === btn));
    featuresView();
  }));
  on('preview', featuresView);
}
