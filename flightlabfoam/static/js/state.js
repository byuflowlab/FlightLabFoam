'use strict';
// The design lives here, in the browser. Every edit autosaves to localStorage and
// schedules a preview request; the server returns outlines, the toolpath and checks.
//
// Events on `bus`:
//   structure: the shape of the design changed (panel count, list lengths, a new design,
//              units); forms re-render
//   preview:   a new preview arrived (or failed); views and the check list redraw

const state = {
  design: null,
  settings: null,
  defaults: null,
  bundled: [],
  panel: 0,
  side: 'right',
  preview: null,
  previewError: null,
};

const bus = new EventTarget();
const on = (name, fn) => bus.addEventListener(name, fn);
const emit = name => bus.dispatchEvent(new Event(name));

const STORAGE_KEY = 'flightlabfoam.design';

function clone(o) { return JSON.parse(JSON.stringify(o)); }

function nPanels() { return state.design.sections.length - 1; }

// Make a design complete: one block per panel, every list present, selection in range.
function normalizeDesign(d) {
  const base = clone(state.defaults.design);
  d = Object.assign(base, d || {});
  d.cut = Object.assign(clone(state.defaults.design.cut), d.cut || {});
  for (const k of ['spars', 'holes', 'control_cuts']) d[k] = d[k] || [];
  d.airfoils = d.airfoils || {};
  d.blocks = d.blocks || [];
  const n = d.sections.length - 1;
  while (d.blocks.length < n) d.blocks.push(clone(state.defaults.block));
  d.blocks.length = n;
  return d;
}

function setDesign(d) {
  state.design = normalizeDesign(d);
  state.panel = Math.min(state.panel, nPanels() - 1);
  if (!state.design.symmetric) state.side = 'right';
  changed(true);
}

// Call after any edit. structure=true re-renders the forms as well.
function changed(structure) {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(state.design)); } catch (e) { /* storage unavailable */ }
  if (structure) emit('structure');
  schedulePreview();
}

let previewTimer, previewSeq = 0;
function schedulePreview() {
  clearTimeout(previewTimer);
  previewTimer = setTimeout(refreshPreview, 180);
}

async function refreshPreview() {
  const seq = ++previewSeq;
  try {
    const r = await api('/api/preview', { design: state.design, panel: state.panel, side: state.side });
    if (seq !== previewSeq) return;
    state.preview = r;
    state.previewError = null;
  } catch (e) {
    if (seq !== previewSeq) return;
    state.previewError = e.message;
  }
  emit('preview');
}

function savedDesign() {
  try {
    const text = localStorage.getItem(STORAGE_KEY);
    return text ? JSON.parse(text) : null;
  } catch (e) {
    return null;
  }
}

function selectPanel(panel, side) {
  state.panel = Math.max(0, Math.min(panel, nPanels() - 1));
  if (side) state.side = state.design.symmetric ? side : 'right';
  emit('structure');
  schedulePreview();
}

function panelChecks() {
  return (state.preview && state.preview.panel && state.preview.panel.checks) || [];
}
