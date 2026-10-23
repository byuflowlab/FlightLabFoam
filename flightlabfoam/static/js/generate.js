'use strict';
// Generate G-code tab.

function checksList(checks) {
  if (!checks.length) return null;
  return h('ul', { class: 'checks' }, checks.map(c => h('li', { class: c.level }, c.message)));
}

function fileCard(f, downloadable) {
  return h('div', { class: 'file' },
    h('header', {},
      h('strong', {}, f.filename),
      h('span', { class: 'unit' }, `about ${minutesText(f.minutes * 60)}`),
      downloadable ? h('button', { class: 'btn small', type: 'button', onclick: () => downloadText(f.filename, f.text) }, 'Download') : null),
    checksList(f.checks),
    h('details', {}, h('summary', {}, 'Show G-code'), h('pre', {}, f.text)));
}

function generateRequest() {
  return { design: state.design, panel: $('#gen-panel').value === 'all' ? 'all' : +$('#gen-panel').value, side: $('#gen-side').value };
}

async function generate() {
  const box = $('#gen-files');
  try {
    const r = await api('/api/gcode', generateRequest());
    box.replaceChildren(...r.files.map(f => fileCard(f, true)));
  } catch (e) {
    toast(e.message, true);
    const files = (e.data && e.data.files) || [];
    box.replaceChildren(...files.map(f => fileCard(f, false)));
  }
}

async function downloadZip() {
  try {
    const res = await fetch('/api/gcode.zip', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(generateRequest()),
    });
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).error || 'could not build the zip file');
    const name = (res.headers.get('Content-Disposition') || '').match(/filename="([^"]+)"/);
    downloadBlob(name ? name[1] : 'gcode.zip', await res.blob());
  } catch (e) { toast(e.message, true); }
}

function renderGenerate() {
  const panelSel = $('#gen-panel'), sideSel = $('#gen-side');
  const pv = panelSel.value, sv = sideSel.value;
  panelSel.replaceChildren(h('option', { value: 'all' }, 'Every panel'),
    ...state.design.sections.slice(1).map((_, i) => h('option', { value: i }, `Panel ${i + 1}`)));
  sideSel.replaceChildren(...(state.design.symmetric
    ? [['all', 'Left and right'], ['right', 'Right only'], ['left', 'Left only']]
    : [['right', 'The one half']]).map(([v, t]) => h('option', { value: v }, t)));
  if ([...panelSel.options].some(o => o.value === pv)) panelSel.value = pv;
  if ([...sideSel.options].some(o => o.value === sv)) sideSel.value = sv;
}

function initGenerate() {
  $('#gen-btn').addEventListener('click', generate);
  $('#gen-zip').addEventListener('click', downloadZip);
  on('structure', () => { renderGenerate(); $('#gen-files').replaceChildren(); });
}
