'use strict';
// Spars, holes & control surfaces tab: three editable lists and a side view of the cut.

// "all" or "1, 3" <-> [] or [0, 2]
function panelsInput(item) {
  const el = h('input', { type: 'text', placeholder: 'all' });
  el.value = item.panels.length ? item.panels.map(p => p + 1).join(', ') : 'all';
  el.addEventListener('change', () => {
    const text = el.value.trim().toLowerCase();
    if (!text || text === 'all') item.panels = [];
    else {
      const nums = text.split(/[\s,]+/).map(Number).filter(n => Number.isInteger(n) && n >= 1 && n <= nPanels());
      item.panels = [...new Set(nums)].map(n => n - 1).sort((a, b) => a - b);
    }
    el.value = item.panels.length ? item.panels.map(p => p + 1).join(', ') : 'all';
    changed();
  });
  return el;
}

const SURFACES = [['lower', 'Bottom'], ['upper', 'Top']];

function removeButton(list, i) {
  return h('button', { class: 'btn small danger', type: 'button', title: 'Remove', onclick: () => { list.splice(i, 1); changed(true); } }, '✕');
}

function featureTable(table, list, columns, emptyText) {
  fill(table,
    h('tr', {}, ['On', ...columns.map(c => c[0]), 'Panels', ''].map(t => h('th', {}, t))),
    list.length
      ? list.map((item, i) => h('tr', {},
        h('td', {}, checkInput(() => item.enabled, v => { item.enabled = v; }, () => changed())),
        columns.map(c => h('td', {}, c[1](item))),
        h('td', {}, panelsInput(item)),
        h('td', {}, removeButton(list, i))))
      : h('tr', { class: 'empty' }, h('td', { colspan: columns.length + 3 }, emptyText)),
  );
}

// the arrow buttons step by 0.05, which suits both chord fractions and millimetres
const num = (key, kind) => item => numInput(() => item[key], v => { item[key] = v; }, kind, () => changed(), { step: 0.05 });
const sel = (key, options) => item => selectInput(options, () => item[key], v => { item[key] = v; }, () => changed(true));

function renderFeatures() {
  const d = state.design, L = Units.label('len');
  featureTable($('#spars-table'), d.spars, [
    ['Type', sel('kind', [['rect', 'Square slot'], ['u', 'U slot'], ['round', 'Round tube']])],
    ['From', sel('surface', SURFACES)],
    ['Centre (x/c)', num('x_c', 'frac')],
    [`Width (${L})`, item => item.kind === 'round' ? '—' : num('width', 'len')(item)],
    [`Depth (${L})`, item => item.kind === 'round' ? '—' : num('depth', 'len')(item)],
    [`Diameter (${L})`, item => item.kind === 'round' ? num('diameter', 'len')(item) : '—'],
    [`Above camber (${L})`, item => item.kind === 'round' ? num('y_offset', 'len')(item) : '—'],
  ], 'No spars');
  featureTable($('#holes-table'), d.holes, [
    ['Centre (x/c)', num('x_c', 'frac')],
    [`Diameter (${L})`, num('diameter', 'len')],
    [`Above camber (${L})`, num('y_offset', 'len')],
    ['Slit from', sel('surface', SURFACES)],
  ], 'No lightening holes');
  featureTable($('#controls-table'), d.control_cuts, [
    ['Surface', sel('kind', [['aileron', 'Aileron'], ['elevator', 'Elevator'], ['flap', 'Flap']])],
    ['Hinge (x/c)', num('hinge_x_c', 'frac')],
    [`Gap (${L})`, num('gap', 'len')],
    ['Cut from', sel('surface', SURFACES)],
  ], 'No control-surface cuts');
  sideView($('#features-view'), { carriages: false });
}

function initFeatures() {
  const add = (key, list) => () => { state.design[list].push(clone(state.defaults[key])); changed(true); };
  $('#add-spar').addEventListener('click', add('spar', 'spars'));
  $('#add-hole').addEventListener('click', add('hole', 'holes'));
  $('#add-control').addEventListener('click', add('control_cut', 'control_cuts'));
  on('structure', renderFeatures);
  on('preview', () => sideView($('#features-view'), { carriages: false }));
}
