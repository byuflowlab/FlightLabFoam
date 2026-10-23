'use strict';
// Start-up, tabs, the context bar (panel, wing half, check status) and project files.

function showTab(name) {
  $$('.tabs button').forEach(b => b.classList.toggle('on', b.dataset.tab === name));
  $$('.pane').forEach(p => { p.hidden = p.dataset.pane !== name; });
  $('#contextbar').classList.toggle('hidden', name === 'load');
  if (name === 'load') $('#checks-list').classList.add('hidden');
  try { localStorage.setItem('flightlabfoam.tab', name); } catch (e) { /* storage unavailable */ }
}

function renderContext() {
  const d = state.design;
  $('#design-name').textContent = d.name;
  const panelSel = $('#panel-select');
  panelSel.replaceChildren(...d.sections.slice(1).map((_, i) => h('option', { value: i }, `${i + 1} of ${nPanels()}`)));
  panelSel.value = state.panel;
  const sideSel = $('#side-select');
  sideSel.replaceChildren(h('option', { value: 'right' }, 'Right'), h('option', { value: 'left' }, 'Left'));
  sideSel.value = state.side;
  $('#side-label').classList.toggle('hidden', !d.symmetric);

  const a = d.sections[state.panel], b = d.sections[state.panel + 1];
  const span = b.span_pos - a.span_pos;
  const sweep = Math.atan2(b.x_le - a.x_le, span) * 180 / Math.PI;
  $('#panel-facts').textContent =
    `span ${Units.fmt(span, 'len')} · taper ${(b.chord / a.chord).toFixed(2)} · LE sweep ${sweep.toFixed(1)}° · ` +
    `${a.airfoil} → ${b.airfoil}`;
}

function renderStatus() {
  const btn = $('#status-btn');
  const list = $('#checks-list');
  if (state.previewError) {
    btn.className = 'status error';
    btn.textContent = 'Cannot build this panel';
    list.replaceChildren(h('li', { class: 'error' }, state.previewError));
    return;
  }
  const checks = panelChecks();
  const errors = checks.filter(c => c.level === 'error').length;
  const warnings = checks.filter(c => c.level === 'warning').length;
  const pv = state.preview && state.preview.panel;
  const time = pv ? ` · ${minutesText(pv.total_seconds)} cut` : '';
  if (errors) { btn.className = 'status error'; btn.textContent = `${errors} error${errors > 1 ? 's' : ''}${warnings ? `, ${warnings} warning${warnings > 1 ? 's' : ''}` : ''}`; }
  else if (warnings) { btn.className = 'status warning'; btn.textContent = `${warnings} warning${warnings > 1 ? 's' : ''}${time}`; }
  else { btn.className = 'status ok'; btn.textContent = `Ready${time}`; }
  list.replaceChildren(...(checks.length ? checks : [{ level: 'info', message: 'No problems found for this panel.' }])
    .map(c => h('li', { class: c.level }, c.message)));
  if (errors) list.classList.remove('hidden');
}

function saveProject() {
  const stem = (state.design.name || 'wing').replace(/[^A-Za-z0-9_-]+/g, '-');
  downloadText(`${stem}.foam.json`, JSON.stringify(state.design, null, 2), 'application/json');
}

async function openProject(file) {
  try {
    const d = JSON.parse(await readFile(file));
    if (!d || !Array.isArray(d.sections)) throw new Error('this is not a FlightLabFoam project file');
    // ask the server to check it before replacing the current design
    await api('/api/preview', { design: d, panel: 0 });
    state.panel = 0;
    setDesign(d);
    toast(`Opened ${d.name || file.name}`);
  } catch (e) { toast(e.message, true); }
}

// Stop the server. The design is already autosaved in this browser, so nothing is lost.
async function exitApp() {
  if (!confirm('Stop FlightLabFoam? Your design stays saved in this browser for next time.')) return;
  try {
    await api('/api/shutdown', {});
  } catch (e) {
    toast(e.message, true);
    return;
  }
  document.body.replaceChildren(h('div', { class: 'stopped' }, h('div', {},
    h('h1', {}, 'FlightLabFoam has stopped'),
    h('p', {}, 'You can close this tab. Run uv run flightlabfoam to start it again.'))));
}

async function init() {
  try {
    const [defaults, settings, airfoils] = await Promise.all([api('/api/defaults'), api('/api/settings'), api('/api/airfoils')]);
    state.defaults = defaults;
    state.settings = settings;
    state.bundled = airfoils.bundled;
  } catch (e) {
    toast(e.message, true);
    return;
  }

  $$('.tabs button').forEach(b => b.addEventListener('click', () => showTab(b.dataset.tab)));
  $('#panel-select').addEventListener('change', e => selectPanel(+e.target.value));
  $('#side-select').addEventListener('change', e => selectPanel(state.panel, e.target.value));
  $('#status-btn').addEventListener('click', () => $('#checks-list').classList.toggle('hidden'));
  $('#save-btn').addEventListener('click', saveProject);
  $('#exit-btn').addEventListener('click', exitApp);
  $('#open-input').addEventListener('change', e => { const f = e.target.files[0]; e.target.value = ''; if (f) openProject(f); });
  $('#new-btn').addEventListener('click', () => {
    if (confirm('Start a new design? Save the current one first if you want to keep it.')) {
      state.panel = 0;
      setDesign(clone(state.defaults.design));
    }
  });

  on('structure', renderContext);
  on('preview', () => { renderContext(); renderStatus(); });
  initLoad(); initWing(); initFeatures(); initBlock(); initCutting(); initAnimation(); initGenerate(); initSettings();

  let tab = 'wing';
  try { tab = localStorage.getItem('flightlabfoam.tab') || 'wing'; } catch (e) { /* storage unavailable */ }
  showTab($(`.tabs button[data-tab="${tab}"]`) ? tab : 'wing');

  try {
    setDesign(savedDesign() || clone(state.defaults.design));
  } catch (e) {
    setDesign(clone(state.defaults.design));
  }
}

init();
