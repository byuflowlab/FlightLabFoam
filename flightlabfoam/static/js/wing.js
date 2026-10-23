'use strict';
// Wing design tab: name, symmetry, panel count, the section table and the view pane.

let wingViewMode = 'wing';

const COMMON_NACA = ['naca0009', 'naca0012', 'naca2412', 'naca4412'];

function airfoilNames() {
  const names = new Set([...state.bundled, ...COMMON_NACA, ...Object.keys(state.design.airfoils)]);
  state.design.sections.forEach(s => names.add(s.airfoil));
  return [...names].sort();
}

// The airfoil picker: known names, plus entries that ask for a NACA code or a .dat file.
function airfoilSelect(sec) {
  const el = h('select', {},
    airfoilNames().map(n => h('option', { value: n }, n + (state.design.airfoils[n] ? ' (uploaded)' : ''))),
    h('option', { value: '__naca' }, 'NACA 4-digit…'),
    h('option', { value: '__upload' }, 'Upload .dat…'));
  el.value = sec.airfoil;
  el.addEventListener('change', async () => {
    const v = el.value;
    el.value = sec.airfoil;
    if (v === '__naca') {
      const code = (prompt('NACA 4-digit code, for example 2412') || '').replace(/\D/g, '');
      if (!code) return;
      try {
        const r = await api('/api/airfoil', { name: 'naca' + code });
        sec.airfoil = r.name;
        changed(true);
      } catch (e) { toast(e.message, true); }
    } else if (v === '__upload') {
      uploadAirfoil(sec);
    } else {
      sec.airfoil = v;
      changed();
    }
  });
  return el;
}

function uploadAirfoil(sec) {
  const input = h('input', { type: 'file', accept: '.dat,.txt' });
  input.addEventListener('change', async () => {
    const file = input.files[0];
    if (!file) return;
    try {
      const r = await api('/api/airfoil', { dat: await readFile(file), filename: file.name });
      state.design.airfoils[r.name] = r.coordinates;
      sec.airfoil = r.name;
      toast(`Loaded ${r.title || r.name} (${(r.max_thickness * 100).toFixed(1)}% thick)`);
      changed(true);
    } catch (e) { toast(e.message, true); }
  });
  input.click();
}

function setPanelCount(n) {
  const secs = state.design.sections;
  n = Math.max(1, Math.min(12, Math.round(n)));
  while (secs.length - 1 < n) {
    const last = secs[secs.length - 1], prev = secs[secs.length - 2];
    const step = last.span_pos - prev.span_pos || 300;
    secs.push(Object.assign(clone(last), { span_pos: last.span_pos + step }));
  }
  secs.length = n + 1;
  setDesign(state.design);
}

function renderWing() {
  const d = state.design;
  $('#name-input').value = d.name;
  $('#symmetric-select').value = String(d.symmetric);
  $('#panel-count').value = nPanels();

  const L = Units.label('len');
  const table = $('#sections-table');
  fill(table,
    h('tr', {}, ['Section', 'Airfoil', `Chord (${L})`, `Span position (${L})`, `Sweep, LE offset (${L})`, 'Twist (°)'].map(t => h('th', {}, t))),
    d.sections.map((s, i) => h('tr', {},
      h('td', { class: 'label' }, i === 0 ? 'Root' : i === d.sections.length - 1 ? `Tip (${i + 1})` : `${i + 1}`),
      h('td', {}, airfoilSelect(s)),
      h('td', {}, numInput(() => s.chord, v => { s.chord = v; }, 'len', () => changed(), { min: 0 })),
      h('td', {}, i === 0
        ? h('span', { class: 'unit' }, '0 (root)')
        : numInput(() => s.span_pos, v => { s.span_pos = v; }, 'len', () => changed())),
      h('td', {}, numInput(() => s.x_le, v => { s.x_le = v; }, 'len', () => changed())),
      h('td', {}, numInput(() => s.twist, v => { s.twist = v; }, 'deg', () => changed())),
    )),
  );
  renderPoints();
  drawWingViews();
}

const CLUSTERING = [['1', 'Light'], ['1.25', 'Medium'], ['1.5', 'Strong']];

// How many points describe each airfoil surface, and how tightly they gather at the nose.
function renderPoints() {
  const c = state.design.cut;
  const count = numInput(() => c.points_per_surface, v => { c.points_per_surface = Math.max(10, Math.min(400, Math.round(v))); },
    null, () => { count.value = c.points_per_surface; changed(); }, { min: 10, max: 400, step: 1 });
  const known = CLUSTERING.some(([v]) => +v === c.le_clustering);
  fill($('#points-form'),
    field('Points per surface', count),
    field('Leading-edge clustering', selectInput(
      known ? CLUSTERING : [...CLUSTERING, [String(c.le_clustering), `Custom (${c.le_clustering})`]],
      () => String(c.le_clustering), v => { c.le_clustering = +v; }, () => changed())),
    h('span', { class: 'readout', id: 'spacing-readout' }));
  showSpacing();
}

function showSpacing() {
  const el = $('#spacing-readout');
  const sp = state.preview && state.preview.panel && state.preview.panel.spacing;
  if (el) el.textContent = sp ? `Panel ${state.panel + 1}: points ${Units.fmt(sp.nose, 'len', 2)} apart at the nose, at most ${Units.fmt(sp.max, 'len', 1)} apart elsewhere` : '';
}

function drawWingViews() {
  const el = $('#wing-view');
  if (wingViewMode === 'wing') wingView(el);
  else if (wingViewMode === 'panel') topView(el);
  else sideView(el);
}

function initWing() {
  $('#name-input').addEventListener('change', e => { state.design.name = e.target.value.trim() || 'wing'; changed(true); });
  $('#symmetric-select').addEventListener('change', e => {
    state.design.symmetric = e.target.value === 'true';
    if (!state.design.symmetric) state.side = 'right';
    changed(true);
  });
  $('#panel-count').addEventListener('change', e => setPanelCount(+e.target.value || 1));
  $$('#wing-view-tabs button').forEach(b => b.addEventListener('click', () => {
    wingViewMode = b.dataset.view;
    $$('#wing-view-tabs button').forEach(x => x.classList.toggle('on', x === b));
    drawWingViews();
  }));
  on('structure', renderWing);
  on('preview', () => { showSpacing(); drawWingViews(); });
}
