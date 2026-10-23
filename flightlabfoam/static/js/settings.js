'use strict';
// Settings dialog (the ☰ menu): display units and the machine profile, saved to settings.yaml.

let settingsDraft = null;

function renderSettings() {
  const s = settingsDraft, m = s.machine;
  // inputs in this dialog show the draft's units, not the saved ones
  const units = { get inch() { return s.units === 'in'; } };
  const conv = kind => ((kind === 'len' || kind === 'feed') && units.inch ? 25.4 : 1);
  const unitLabel = kind => (kind === 'len' ? (units.inch ? 'in' : 'mm') : kind === 'feed' ? (units.inch ? 'in/min' : 'mm/min') : '');
  const n = (key, label, kind) => {
    const el = h('input', { type: 'number', step: 'any', min: 0 });
    el.value = +(m[key] / conv(kind)).toFixed(4);
    el.addEventListener('change', () => { const v = parseFloat(el.value); if (Number.isFinite(v)) m[key] = v * conv(kind); });
    return h('label', { class: 'field' }, label, h('span', { class: 'with-unit' }, el, h('span', { class: 'unit' }, unitLabel(kind))));
  };
  const t = (key, label) => {
    const el = h('input', { type: 'text', value: m[key] });
    el.addEventListener('change', () => { m[key] = el.value.trim(); });
    return h('label', { class: 'field' }, label, el);
  };
  fill($('#settings-fields'),
    h('h3', {}, 'Display'),
    field('Units', selectInput([['mm', 'Millimetres'], ['in', 'Inches']], () => s.units, v => { s.units = v; }, renderSettings)),
    h('h3', {}, 'Foam cutter'),
    t('name', 'Machine name'),
    field('G-code style', selectInput(Object.entries(state.defaults.dialects), () => m.dialect, v => { m.dialect = v; })),
    n('carriage_separation', 'Carriage separation', 'len'),
    n('travel_horizontal', 'Horizontal travel (X, A)', 'len'),
    n('travel_vertical', 'Vertical travel (Y, Z)', 'len'),
    field('X/Y carriage is on the', selectInput([['left', 'left'], ['right', 'right']], () => m.xy_carriage_side, v => { m.xy_carriage_side = v; })),
    field('Controller applies F to', selectInput([
      ['xy', 'the X/Y carriage'],
      ['xyz', 'the X, Y and Z axes (A follows)'],
      ['all', 'all four axes together'],
    ], () => m.feed_model, v => { m.feed_model = v; })),
    n('max_feed', 'Maximum feed', 'feed'),
    n('min_wall_thickness', 'Minimum foam wall', 'len'),
    t('heat_on_code', 'Heat on code'),
    t('heat_off_code', 'Heat off code'),
    h('p', { class: 'hint', style: 'grid-column: 1 / -1' },
      'The minimum foam wall is the thinnest foam allowed between a spar or hole and the skin, or between two of them. The carriage side is seen standing at the entry side of the machine, looking along +X. Check how F is applied with a timed straight move: a 50 mm move at F120 should take 25 s if F is the carriage speed.'),
  );
}

function initSettings() {
  const dialog = $('#settings-dialog');
  $('#menu-btn').addEventListener('click', () => {
    settingsDraft = clone(state.settings);
    renderSettings();
    dialog.showModal();
  });
  $('#settings-save').addEventListener('click', async e => {
    e.preventDefault();
    try {
      state.settings = await api('/api/settings', settingsDraft, 'PUT');
      dialog.close();
      toast('Settings saved');
      emit('structure');
      schedulePreview();
    } catch (err) { toast(err.message, true); }
  });
}
