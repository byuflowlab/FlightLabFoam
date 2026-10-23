'use strict';
// SVG views. Each draws into a container at its current pixel size, with equal x and y
// scales, and redraws when the container is resized.
//
//   wingView:  whole wing seen from above, from the design alone
//   topView:   the machine from above: carriages, block and panel
//   sideView:  the machine from the side: block, the cut at each wing end and each carriage

const SVGNS = 'http://www.w3.org/2000/svg';

function svg(tag, attrs, ...kids) {
  const el = document.createElementNS(SVGNS, tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === undefined || v === null) continue;
    if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v);
  }
  for (const kid of kids.flat()) if (kid) el.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
  return el;
}

// Map world coordinates into a w x h pixel box. flipY puts +y up.
function mapper(b, w, h, flipY, pad) {
  pad = pad === undefined ? 28 : pad;
  const dx = Math.max(b.x1 - b.x0, 1e-9), dy = Math.max(b.y1 - b.y0, 1e-9);
  const k = Math.min((w - 2 * pad) / dx, (h - 2 * pad) / dy);
  const ox = (w - k * dx) / 2, oy = (h - k * dy) / 2;
  const m = {
    k,
    x: x => ox + (x - b.x0) * k,
    y: y => flipY ? h - oy - (y - b.y0) * k : oy + (y - b.y0) * k,
  };
  m.pts = arr => arr.map(p => `${m.x(p[0]).toFixed(1)},${m.y(p[1]).toFixed(1)}`).join(' ');
  return m;
}

function bounds(arrays, margin) {
  let x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity;
  for (const arr of arrays) for (const [x, y] of arr) {
    x0 = Math.min(x0, x); x1 = Math.max(x1, x); y0 = Math.min(y0, y); y1 = Math.max(y1, y);
  }
  const mx = (x1 - x0) * (margin || 0), my = (y1 - y0) * (margin || 0);
  return { x0: x0 - mx, x1: x1 + mx, y0: y0 - my, y1: y1 + my };
}

const line = (m, pts, style, extra) => svg('polyline', Object.assign({ points: m.pts(pts), fill: 'none', style }, extra || {}));
const polygon = (m, pts, style, extra) => svg('polygon', Object.assign({ points: m.pts(pts), style }, extra || {}));
const label = (m, x, y, text, anchor, dy) => svg('text', { x: m.x(x), y: m.y(y) + (dy || 0), 'text-anchor': anchor || 'middle', 'font-size': 12 }, text);

function legend(items) {
  return h('div', { class: 'legend' }, items.map(([color, text, dashed]) =>
    h('span', {}, h('i', { style: `background:${dashed ? 'transparent' : color};border-top:${dashed ? `2px dashed ${color}` : '0'}` }), text)));
}

function emptyMessage(container, text) {
  container.replaceChildren(h('div', { class: 'empty-msg' }, text));
}

// Re-run the last draw call for a container whenever it changes size.
const viewDraws = new Map();
const resizer = new ResizeObserver(entries => {
  for (const e of entries) {
    const fn = viewDraws.get(e.target);
    if (fn && e.contentRect.width > 0) fn();
  }
});
function drawInto(container, fn) {
  if (!viewDraws.has(container)) resizer.observe(container);
  viewDraws.set(container, fn);
  if (container.clientWidth > 0) fn();
}

function cutOnly(panel, key) {
  return panel[key].filter((_, i) => panel.kind[i] === 'cut' || panel.kind[i] === 'lead_in');
}

// ---------------------------------------------------------------- whole wing

function wingView(container) {
  drawInto(container, () => {
    const d = state.design;
    const W = container.clientWidth, H = container.clientHeight;
    const secs = d.sections;
    const halves = d.symmetric ? [1, -1] : [1];
    const pts = [];
    for (const s of secs) for (const sg of halves) pts.push([sg * s.span_pos, s.x_le], [sg * s.span_pos, s.x_le + s.chord]);
    const m = mapper(bounds([pts], 0.04), W, H, false);
    const root = svg('svg', { viewBox: `0 0 ${W} ${H}` });
    root.append(line(m, [[0, bounds([pts]).y0 - 10], [0, bounds([pts]).y1 + 10]], 'stroke:var(--line);stroke-dasharray:4 4'));
    for (let p = 0; p < secs.length - 1; p++) {
      const a = secs[p], b = secs[p + 1];
      for (const sg of halves) {
        const side = sg > 0 ? 'right' : 'left';
        const quad = [[sg * a.span_pos, a.x_le], [sg * b.span_pos, b.x_le], [sg * b.span_pos, b.x_le + b.chord], [sg * a.span_pos, a.x_le + a.chord]];
        const sel = p === state.panel && (side === state.side || !d.symmetric);
        root.append(polygon(m, quad, 'stroke-width:1.5', { class: 'panel-shape' + (sel ? '' : ' dim'), onclick: () => selectPanel(p, side) }));
        const cx = sg * (a.span_pos + b.span_pos) / 2, cy = (a.x_le + b.x_le + (a.chord + b.chord) / 2) / 2;
        root.append(label(m, cx, cy, `${p + 1}`, 'middle', 4));
      }
    }
    root.append(label(m, 0, bounds([pts]).y0, 'leading edge', 'middle', -8));
    if (d.symmetric) {
      root.append(label(m, bounds([pts]).x1, bounds([pts]).y1, 'right', 'end', 18));
      root.append(label(m, bounds([pts]).x0, bounds([pts]).y1, 'left', 'start', 18));
    }
    container.replaceChildren(root, h('div', { class: 'legend' }, 'Click a panel to select it. Seen from above, nose up.'));
  });
}

// ---------------------------------------------------------------- machine top view

function topView(container) {
  drawInto(container, () => {
    const pv = state.preview && state.preview.panel;
    if (!pv) return emptyMessage(container, state.previewError || 'No panel to show');
    const W = container.clientWidth, H = container.clientHeight;
    const D = state.settings.machine.carriage_separation;
    const b = pv.block;
    const xyCut = cutOnly(pv, 'xy'), azCut = cutOnly(pv, 'az'), rootCut = cutOnly(pv, 'root'), tipCut = cutOnly(pv, 'tip');
    const ext = arr => [Math.min(...arr.map(p => p[0])), Math.max(...arr.map(p => p[0]))];
    const [r0, r1] = ext(rootCut), [t0, t1] = ext(tipCut), [x0, x1] = ext(xyCut), [a0, a1] = ext(azCut);
    const world = [[0, 0], [D, 0], [0, Math.max(b.chord, x1, a1)], [D, Math.min(0, x0, a0)]];
    const m = mapper(bounds([world], 0.06), W, H, false, 34);
    const root = svg('svg', { viewBox: `0 0 ${W} ${H}` });
    const [wb0, wb1] = pv.w_block;
    root.append(polygon(m, [[wb0, 0], [wb1, 0], [wb1, b.chord], [wb0, b.chord]], 'fill:var(--block);stroke:var(--block-line)'));
    root.append(line(m, [[0, x0], [D, a0]], 'stroke:var(--wire);stroke-dasharray:5 4;opacity:.7'));
    root.append(line(m, [[0, x1], [D, a1]], 'stroke:var(--wire);stroke-dasharray:5 4;opacity:.7'));
    root.append(polygon(m, [[pv.w_root, r0], [pv.w_tip, t0], [pv.w_tip, t1], [pv.w_root, r1]], 'fill:var(--accent-soft);stroke:var(--accent);stroke-width:1.5'));
    root.append(line(m, [[pv.w_root, r0], [pv.w_root, r1]], 'stroke:var(--root);stroke-width:3'));
    root.append(line(m, [[pv.w_tip, t0], [pv.w_tip, t1]], 'stroke:var(--tip);stroke-width:3'));
    const yMax = Math.max(b.chord, x1, a1), yMin = Math.min(0, x0, a0);
    root.append(line(m, [[0, yMin], [0, yMax]], 'stroke:var(--xy);stroke-width:4'));
    root.append(line(m, [[D, yMin], [D, yMax]], 'stroke:var(--az);stroke-width:4'));
    root.append(label(m, 0, yMin, 'X/Y carriage', 'start', -10));
    root.append(label(m, D, yMin, 'A/Z carriage', 'end', -10));
    root.append(label(m, pv.w_root, Math.max(r1, t1), 'root', 'middle', 16));
    root.append(label(m, pv.w_tip, Math.max(r1, t1), 'tip', 'middle', 16));
    root.append(label(m, (wb0 + wb1) / 2, 0, 'entry face, X = 0', 'middle', -6));
    container.replaceChildren(root, legend([
      ['var(--root)', 'wing root'], ['var(--tip)', 'wing tip'], ['var(--wire)', 'wire at the entry and far edges', true],
    ]));
  });
}

// ---------------------------------------------------------------- machine side view

function sideView(container, opts) {
  opts = opts || {};
  drawInto(container, () => {
    const pv = state.preview && state.preview.panel;
    if (!pv) return emptyMessage(container, state.previewError || 'No panel to show');
    const W = container.clientWidth, H = container.clientHeight;
    const b = pv.block;
    const blockRect = [[0, 0], [b.chord, 0], [b.chord, b.thickness], [0, b.thickness]];
    const showCarriages = opts.carriages !== false;
    const all = [blockRect, pv.root, pv.tip].concat(showCarriages ? [pv.xy, pv.az] : []);
    const m = mapper(bounds(all, 0.03), W, H, true, 24);
    const root = svg('svg', { viewBox: `0 0 ${W} ${H}` });
    root.append(polygon(m, blockRect, 'fill:var(--block);stroke:var(--block-line);opacity:.8'));
    root.append(polygon(m, pv.nominal_root, 'fill:var(--root);opacity:.10;stroke:none'));
    root.append(polygon(m, pv.nominal_tip, 'fill:var(--tip);opacity:.10;stroke:none'));
    if (showCarriages) {
      root.append(line(m, pv.xy, 'stroke:var(--xy);stroke-dasharray:5 3;stroke-width:1.2'));
      root.append(line(m, pv.az, 'stroke:var(--az);stroke-dasharray:5 3;stroke-width:1.2'));
    }
    root.append(line(m, pv.root, 'stroke:var(--root);stroke-width:1.6'));
    root.append(line(m, pv.tip, 'stroke:var(--tip);stroke-width:1.6'));
    const s = pv.root[0];
    root.append(svg('circle', { cx: m.x(s[0]), cy: m.y(s[1]), r: 4, style: 'fill:var(--wire)' }));
    root.append(label(m, 0, 0, 'X = 0', 'start', 14));
    const items = [['var(--root)', 'cut at wing root'], ['var(--tip)', 'cut at wing tip']];
    if (showCarriages) items.push(['var(--xy)', 'X/Y carriage', true], ['var(--az)', 'A/Z carriage', true]);
    container.replaceChildren(root, legend(items));
  });
}
