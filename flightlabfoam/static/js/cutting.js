'use strict';
// Cutting settings tab.

function renderCutting() {
  const c = state.design.cut, m = state.settings.machine;
  const ch = () => changed();
  const n = (key, kind, extra) => numInput(() => c[key], v => { c[key] = kind === 'int' ? Math.round(v) : v; }, kind === 'int' ? null : kind, ch, extra);
  fill($('#cutting-form'),
    h('h3', {}, 'Wire heat'),
    checkField(`Turn the wire on and off in the file (${m.heat_on_code} / ${m.heat_off_code})`,
      checkInput(() => c.heat_control, v => { c.heat_control = v; }, () => changed(true))),
    c.heat_control ? field('Warm-up pause after heat on', n('heat_dwell_s', 's', { min: 0 }), 's') : null,

    h('h3', {}, 'Speed'),
    field('Cutting speed', n('feed', 'feed', { min: 0 }), 'feed'),
    field('Cutting speed is held on', selectInput([
      ['faster_carriage', 'the faster carriage'],
      ['slower_carriage', 'the slower carriage'],
      ['root', 'the wing root'],
      ['tip', 'the wing tip'],
    ], () => c.feed_basis, v => { c.feed_basis = v; }, ch)),
    field('Exit speed (leaving the block)', n('exit_feed', 'feed', { min: 0 }), 'feed'),

    h('h3', {}, 'Path'),
    field('Edge cut first', selectInput([
      ['trailing', 'Trailing edge first'],
      ['leading', 'Leading edge first'],
    ], () => c.entry, v => { c.entry = v; }, ch)),
    field('Kerf offset at the root', n('kerf_root', 'len', { min: 0 }), 'len'),
    field('Kerf offset at the tip', n('kerf_tip', 'len', { min: 0 }), 'len'),
    field('Minimum trailing-edge thickness', n('te_min_thickness', 'len', { min: 0 }), 'len'),
    field('Points per surface', n('points_per_surface', 'int', { min: 10, max: 400, step: 1 })),
    checkField('Write a comment header describing the cut', checkInput(() => c.comment_header, v => { c.comment_header = v; }, ch)),
  );
}

function initCutting() {
  on('structure', renderCutting);
}
