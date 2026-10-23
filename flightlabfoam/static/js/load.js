'use strict';
// Load airplane tab: import one lifting surface from a FlightLab project.

let flightlabText = null;

async function importSurface(name) {
  try {
    const r = await api('/api/import/flightlab', { text: flightlabText, surface: name, design: state.design });
    setDesign(r.design);
    $('#flightlab-notes').replaceChildren(...r.notes.map(n => h('li', {}, n)));
    toast(`Loaded ${r.design.name}: ${r.design.sections.length - 1} panel(s)`);
  } catch (e) { toast(e.message, true); }
}

function showSurfaces(surfaces) {
  const box = $('#flightlab-surfaces');
  fill(box,
    h('p', {}, 'Pick the surface to cut. This replaces the current wing design.'),
    h('div', { class: 'surfaces' }, surfaces.map(s => h('button', {
      class: 'surface-option', type: 'button', onclick: () => importSurface(s.name),
    },
    h('strong', {}, s.name),
    h('small', {}, `${s.panels} panel${s.panels === 1 ? '' : 's'} · ${s.symmetric ? 'symmetric' : 'one side'}${s.vertical ? ' · vertical' : ''}`)))));
}

function initLoad() {
  $('#flightlab-input').addEventListener('change', async e => {
    const file = e.target.files[0];
    e.target.value = '';
    if (!file) return;
    try {
      flightlabText = await readFile(file);
      // a preview import lists the surfaces without changing the design
      const r = await api('/api/import/flightlab', { text: flightlabText, design: state.design });
      showSurfaces(r.surfaces);
      $('#flightlab-notes').replaceChildren();
    } catch (err) { toast(err.message, true); }
  });
}
