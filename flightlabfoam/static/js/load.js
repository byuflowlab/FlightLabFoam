'use strict';
// Load airplane tab: import one lifting surface from a FlightLab project.

let flightlabText = null;
let loadedSurface = null;  // the surface last imported, re-imported when the span choice changes

function spanChoice() {
  const picked = document.querySelector('input[name="dihedral-span"]:checked');
  return picked ? picked.value : 'true';
}

async function importSurface(name) {
  try {
    const r = await api('/api/import/flightlab', { text: flightlabText, surface: name, design: state.design, span: spanChoice() });
    loadedSurface = name;
    setDesign(r.design);
    $('#flightlab-notes').replaceChildren(...r.notes.map(n => h('li', {}, n)));
    toast(`Loaded ${r.design.name}: ${r.design.sections.length - 1} panel(s)`);
  } catch (e) { toast(e.message, true); }
}

// Panels with dihedral are cut flat; the student chooses whether at their length along
// the panel (the tilted wing then has the designed span) or at the plan span.
function spanOptions(surfaces) {
  const tilted = surfaces.filter(s => s.dihedral > 0.5);
  if (!tilted.length) return null;
  const mm = v => Units.fmt(v, 'len');
  const option = (value, title, detail, checked) => h('label', { class: 'span-option' },
    h('input', { type: 'radio', name: 'dihedral-span', value, checked }),
    h('span', {}, h('strong', {}, title), h('small', {}, detail)));
  const ex = tilted[0];
  return h('fieldset', { class: 'span-choice', onchange: () => loadedSurface && importSurface(loadedSurface) },
    h('legend', {}, 'Panels with dihedral'),
    h('p', { class: 'hint' }, `${tilted.map(s => `${s.name} has ${s.dihedral.toFixed(1)}° of dihedral`).join('; ')}. Each panel is cut flat, then tilted when the wing is assembled.`),
    option('true', 'Cut at the length along the panel (recommended)',
      `${ex.name}: ${mm(ex.span_true)} long, so once tilted it spans the designed ${mm(ex.span_plan)}.`, true),
    option('plan', 'Cut at the plan span',
      `${ex.name}: ${mm(ex.span_plan)} long, so once tilted it spans ${mm(ex.span_plan ** 2 / ex.span_true)}, a little short of the design. Use this only if the foam is too short.`, false));
}

function showSurfaces(surfaces) {
  const box = $('#flightlab-surfaces');
  fill(box,
    spanOptions(surfaces),
    h('p', {}, 'Pick the surface to cut. This replaces the current wing design.'),
    h('div', { class: 'surfaces' }, surfaces.map(s => h('button', {
      class: 'surface-option', type: 'button', onclick: () => importSurface(s.name),
    },
    h('strong', {}, s.name),
    h('small', {}, `${s.panels} panel${s.panels === 1 ? '' : 's'} · ${s.symmetric ? 'symmetric' : 'one side'}${s.vertical ? ' · vertical' : ''}${s.dihedral > 0.5 ? ` · ${s.dihedral.toFixed(1)}° dihedral` : ''}`)))));
}

function initLoad() {
  $('#flightlab-input').addEventListener('change', async e => {
    const file = e.target.files[0];
    e.target.value = '';
    if (!file) return;
    try {
      flightlabText = await readFile(file);
      loadedSurface = null;
      // a preview import lists the surfaces without changing the design
      const r = await api('/api/import/flightlab', { text: flightlabText, design: state.design });
      showSurfaces(r.surfaces);
      $('#flightlab-notes').replaceChildren();
    } catch (err) { toast(err.message, true); }
  });
}
