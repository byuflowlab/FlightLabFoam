'use strict';
// Block placement tab: the foam block for the selected panel.

let blockViewMode = 'panel';
let blockSizeInputs = {};

function renderBlock() {
  const b = state.design.blocks[state.panel];
  const ch = structure => () => changed(structure);
  blockSizeInputs = {};
  const size = (key, label) => {
    const input = numInput(() => b[key], v => { b[key] = v; }, 'len', ch(), { min: 0 });
    input.disabled = b.auto;
    blockSizeInputs[key] = input;
    return field(label, input, 'len');
  };
  fill($('#block-form'),
    h('h3', {}, `Panel ${state.panel + 1}`),
    checkField('Size the block to the panel automatically', checkInput(() => b.auto, v => {
      b.auto = v;
      // start manual sizing from the automatic size
      const pb = state.preview && state.preview.panel && state.preview.panel.block;
      if (!v && pb) Object.assign(b, { span: pb.span, chord: pb.chord, thickness: pb.thickness });
    }, ch(true))),
    b.auto ? field('Margin around the panel', numInput(() => b.margin, v => { b.margin = v; }, 'len', ch(), { min: 0 }), 'len') : null,
    size('span', 'Span-wise length'),
    size('chord', 'Chord-wise length'),
    size('thickness', 'Thickness'),
    h('h3', {}, 'Placement'),
    field('Cut-in distance', numInput(() => b.cut_in, v => { b.cut_in = v; }, 'len', ch(), { min: 0 }), 'len'),
    field('Vertical offset (panel up)', numInput(() => b.vertical_offset, v => { b.vertical_offset = v; }, 'len', ch()), 'len'),
    field('Span-wise offset (panel toward tip)', numInput(() => b.span_offset, v => { b.span_offset = v; }, 'len', ch()), 'len'),
    field('Block offset between carriages (toward A/Z)', numInput(() => b.machine_offset, v => { b.machine_offset = v; }, 'len', ch()), 'len'),
    h('div', {}, h('button', {
      class: 'btn ghost', type: 'button', onclick: () => {
        state.design.blocks = state.design.blocks.map(() => clone(b));
        toast('Copied to every panel');
        changed(true);
      },
    }, 'Use these settings for every panel')),
  );
  showAutoSize();
  drawBlockViews();
}

// With auto sizing on, show the size the server computed.
function showAutoSize() {
  const b = state.design.blocks[state.panel];
  const pb = state.preview && state.preview.panel && state.preview.panel.block;
  if (!b.auto || !pb) return;
  for (const key of ['span', 'chord', 'thickness']) {
    if (blockSizeInputs[key]) blockSizeInputs[key].value = roundForInput(Units.toDisplay(pb[key], 'len'), 'len');
  }
}

function drawBlockViews() {
  const el = $('#block-view');
  if (blockViewMode === 'panel') topView(el);
  else sideView(el);
}

function initBlock() {
  $$('#block-view-tabs button').forEach(btn => btn.addEventListener('click', () => {
    blockViewMode = btn.dataset.view;
    $$('#block-view-tabs button').forEach(x => x.classList.toggle('on', x === btn));
    drawBlockViews();
  }));
  on('structure', renderBlock);
  on('preview', () => { showAutoSize(); drawBlockViews(); });
}
