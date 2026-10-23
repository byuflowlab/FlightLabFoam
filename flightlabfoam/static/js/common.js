'use strict';
// Shared helpers: API calls, DOM building, unit conversion, toasts and downloads.

async function api(path, body, method) {
  const opts = { method: method || (body === undefined ? 'GET' : 'POST'), headers: { 'Content-Type': 'application/json' } };
  if (body !== undefined) opts.body = JSON.stringify(body);
  const res = await fetch(path, opts);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(data.error || 'Something went wrong. Check the terminal running FlightLabFoam.');
    err.data = data;
    throw err;
  }
  return data;
}

// h('div', {class: 'x', onclick: fn}, child, 'text', [more children])
function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === undefined || v === null || v === false) continue;
    if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
    else if (k === 'class') el.className = v;
    else if (k === 'text') el.textContent = v;
    else if (v === true) el.setAttribute(k, '');
    else el.setAttribute(k, v);
  }
  for (const kid of kids.flat()) {
    if (kid === undefined || kid === null || kid === false) continue;
    el.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
  }
  return el;
}

// Replace an element's children, flattening arrays and skipping null/false like h() does.
function fill(el, ...kids) {
  el.replaceChildren(...kids.flat(Infinity).filter(k => k !== undefined && k !== null && k !== false)
    .map(k => (k instanceof Node ? k : document.createTextNode(String(k)))));
  return el;
}

const $ = (sel, root) => (root || document).querySelector(sel);
const $$ = (sel, root) => [...(root || document).querySelectorAll(sel)];

let toastTimer;
function toast(msg, isError) {
  const el = $('#toast');
  el.textContent = msg;
  el.classList.toggle('error', !!isError);
  el.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('show'), isError ? 5000 : 2600);
}

// Everything is stored in mm and mm/min; these convert for display when units are inches.
const Units = {
  get inch() { return state.settings && state.settings.units === 'in'; },
  factor(kind) { return (kind === 'len' || kind === 'feed') && this.inch ? 25.4 : 1; },
  toDisplay(v, kind) { return v / this.factor(kind); },
  fromDisplay(v, kind) { return v * this.factor(kind); },
  label(kind) {
    if (kind === 'len') return this.inch ? 'in' : 'mm';
    if (kind === 'feed') return this.inch ? 'in/min' : 'mm/min';
    return { deg: '°', s: 's', frac: 'x/c' }[kind] || '';
  },
  fmt(v, kind, digits) {
    const d = digits !== undefined ? digits : (this.inch && (kind === 'len' || kind === 'feed') ? 3 : 1);
    return `${(+this.toDisplay(v, kind).toFixed(d))} ${this.label(kind)}`.trim();
  },
};

function roundForInput(v, kind) {
  const d = Units.inch && (kind === 'len' || kind === 'feed') ? 4 : 3;
  return +Number(v).toFixed(d);
}

// A number input bound to get/set in stored units. onChange fires after a valid edit.
function numInput(get, set, kind, onChange, extra) {
  const el = h('input', Object.assign({ type: 'number', step: 'any' }, extra || {}));
  el.value = roundForInput(Units.toDisplay(get(), kind), kind);
  el.addEventListener('change', () => {
    const v = parseFloat(el.value);
    if (!Number.isFinite(v)) { el.value = roundForInput(Units.toDisplay(get(), kind), kind); return; }
    set(Units.fromDisplay(v, kind));
    onChange && onChange();
  });
  return el;
}

function selectInput(options, get, set, onChange) {
  const el = h('select', {}, options.map(([value, label]) => h('option', { value: String(value) }, label)));
  el.value = String(get());
  el.addEventListener('change', () => { set(el.value); onChange && onChange(); });
  return el;
}

function checkInput(get, set, onChange) {
  const el = h('input', { type: 'checkbox' });
  el.checked = !!get();
  el.addEventListener('change', () => { set(el.checked); onChange && onChange(); });
  return el;
}

// A labelled field for a form grid.
function field(label, input, kind) {
  const unit = kind ? Units.label(kind) : '';
  return h('label', { class: 'field' }, label, unit ? h('span', { class: 'with-unit' }, input, h('span', { class: 'unit' }, unit)) : input);
}

function checkField(label, input) {
  return h('label', { class: 'field check' }, input, label);
}

function downloadBlob(filename, blob) {
  const url = URL.createObjectURL(blob);
  const a = h('a', { href: url, download: filename });
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function downloadText(filename, text, type) {
  downloadBlob(filename, new Blob([text], { type: type || 'text/plain' }));
}

function readFile(file) {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(r.result);
    r.onerror = () => reject(r.error);
    r.readAsText(file);
  });
}

function minutesText(seconds) {
  const m = Math.floor(seconds / 60), s = Math.round(seconds % 60);
  return `${m} min ${String(s).padStart(2, '0')} s`;
}
