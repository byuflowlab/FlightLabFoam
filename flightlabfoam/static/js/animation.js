'use strict';
// Cutting animation: an oblique view of the machine with the wire moving through the
// toolpath of the selected panel, timed by the programmed feeds.
//
// A machine point is (X, Y, w): X into the block, Y up, w from the X/Y carriage to the
// A/Z carriage. The airfoil plane (X, Y) is drawn face on, and the span w recedes up and
// to the right, so the X/Y carriage is at the front and the A/Z carriage at the back.

const anim = { t: 0, playing: false, last: null, cum: null, total: 0, path: null };
const OBLIQUE = { cos: Math.cos(Math.PI / 5) * 0.4, sin: Math.sin(Math.PI / 5) * 0.4 };

function project(X, Y, w) {
  return [X + w * OBLIQUE.cos, Y + w * OBLIQUE.sin];
}

function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function setAnimPath() {
  const pv = state.preview && state.preview.panel;
  if (!pv) { anim.path = null; anim.cum = null; anim.total = 0; drawAnim(); return; }
  // start from program zero, where the wire is zeroed, so the clock matches the G-code
  anim.path = Object.assign({}, pv, { xy: [[0, 0], ...pv.xy], az: [[0, 0], ...pv.az], seconds: [0, ...pv.seconds] });
  anim.cum = [0];
  for (let i = 1; i < anim.path.seconds.length; i++) anim.cum.push(anim.cum[i - 1] + anim.path.seconds[i]);
  anim.total = anim.cum[anim.cum.length - 1];
  anim.t = Math.min(anim.t, anim.total);
  drawAnim();
}

// Carriage positions at time t, and the index of the move in progress.
function positionAt(t) {
  const pv = anim.path, cum = anim.cum;
  let i = 1;
  while (i < cum.length - 1 && cum[i] < t) i++;
  const span = cum[i] - cum[i - 1];
  const f = span > 0 ? Math.max(0, Math.min(1, (t - cum[i - 1]) / span)) : 1;
  const lerp = (a, b) => [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f];
  return { i, xy: lerp(pv.xy[i - 1], pv.xy[i]), az: lerp(pv.az[i - 1], pv.az[i]) };
}

function drawAnim() {
  const canvas = $('#anim-canvas');
  const cw = canvas.clientWidth;
  if (!cw) return;
  const dpr = window.devicePixelRatio || 1;
  const ch = Math.round(cw * 0.5);
  canvas.width = cw * dpr;
  canvas.height = ch * dpr;
  canvas.style.height = ch + 'px';
  const g = canvas.getContext('2d');
  g.setTransform(dpr, 0, 0, dpr, 0, 0);
  g.clearRect(0, 0, cw, ch);
  const pv = anim.path;
  if (!pv) {
    g.fillStyle = cssVar('--muted');
    g.font = '14px sans-serif';
    g.fillText(state.previewError || 'No panel to animate', 20, 30);
    return;
  }

  const D = state.settings.machine.carriage_separation;
  const b = pv.block;
  const [wb0, wb1] = pv.w_block;
  const boxCorners = [];
  for (const w of [wb0, wb1]) for (const X of [0, b.chord]) for (const Y of [0, b.thickness]) boxCorners.push(project(X, Y, w));
  const pts = [...boxCorners, ...pv.xy.map(p => project(p[0], p[1], 0)), ...pv.az.map(p => project(p[0], p[1], D))];
  const xs = pts.map(p => p[0]), ys = pts.map(p => p[1]);
  const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
  const pad = 30;
  const k = Math.min((cw - 2 * pad) / (x1 - x0), (ch - 2 * pad) / (y1 - y0));
  const ox = (cw - k * (x1 - x0)) / 2, oy = (ch - k * (y1 - y0)) / 2;
  const S = p => [ox + (p[0] - x0) * k, ch - oy - (p[1] - y0) * k];
  const P = (X, Y, w) => S(project(X, Y, w));

  const stroke = (pts3, color, width, dash) => {
    g.beginPath();
    pts3.forEach((p, j) => { const [sx, sy] = P(...p); j ? g.lineTo(sx, sy) : g.moveTo(sx, sy); });
    g.strokeStyle = color; g.lineWidth = width; g.setLineDash(dash || []); g.stroke(); g.setLineDash([]);
  };

  // foam block: faces at each end and the long edges between them
  const face = w => [[0, 0, w], [b.chord, 0, w], [b.chord, b.thickness, w], [0, b.thickness, w], [0, 0, w]];
  g.fillStyle = cssVar('--block');
  g.beginPath();
  face(wb0).forEach((p, j) => { const [sx, sy] = P(...p); j ? g.lineTo(sx, sy) : g.moveTo(sx, sy); });
  g.fill();
  stroke(face(wb0), cssVar('--block-line'), 1);
  stroke(face(wb1), cssVar('--block-line'), 1);
  for (const [X, Y] of [[0, 0], [b.chord, 0], [b.chord, b.thickness], [0, b.thickness]]) stroke([[X, Y, wb0], [X, Y, wb1]], cssVar('--block-line'), 1);

  // the panel's cut at the wing root and tip
  stroke(pv.root.map(p => [p[0], p[1], pv.w_root]), cssVar('--root'), 1.2);
  stroke(pv.tip.map(p => [p[0], p[1], pv.w_tip]), cssVar('--tip'), 1.2);

  // carriage paths: faint in full, bold up to now
  const pos = positionAt(anim.t);
  const done = (arr, w) => [...arr.slice(0, pos.i).map(p => [p[0], p[1], w]), [...(w === 0 ? pos.xy : pos.az), w]];
  stroke(pv.xy.map(p => [p[0], p[1], 0]), cssVar('--xy'), 1, [4, 3]);
  stroke(pv.az.map(p => [p[0], p[1], D]), cssVar('--az'), 1, [4, 3]);
  stroke(done(pv.xy, 0), cssVar('--xy'), 2.2);
  stroke(done(pv.az, D), cssVar('--az'), 2.2);

  // the wire
  stroke([[pos.xy[0], pos.xy[1], 0], [pos.az[0], pos.az[1], D]], cssVar('--wire'), 2.5);
  for (const [p, w, c] of [[pos.xy, 0, '--xy'], [pos.az, D, '--az']]) {
    const [sx, sy] = P(p[0], p[1], w);
    g.beginPath(); g.arc(sx, sy, 5, 0, 2 * Math.PI); g.fillStyle = cssVar(c); g.fill();
  }

  g.fillStyle = cssVar('--muted');
  g.font = '12px sans-serif';
  const [lx, ly] = P(0, 0, 0); g.fillText('X/Y carriage', lx, ly + 18);
  const [rx, ry] = P(0, 0, D); g.fillText('A/Z carriage', rx, ry + 18);

  $('#anim-time').textContent = `${minutesText(anim.t)} / ${minutesText(anim.total)}`;
  $('#anim-scrub').value = anim.total ? Math.round(1000 * anim.t / anim.total) : 0;
}

function animFrame(now) {
  if (!anim.playing) return;
  if (anim.last !== null) anim.t += (now - anim.last) / 1000 * +$('#anim-speed').value;
  anim.last = now;
  if (anim.t >= anim.total) { anim.t = anim.total; setPlaying(false); }
  drawAnim();
  if (anim.playing) requestAnimationFrame(animFrame);
}

function setPlaying(p) {
  anim.playing = p && !!anim.path;
  anim.last = null;
  $('#anim-play').textContent = anim.playing ? 'Pause' : 'Play';
  if (anim.playing) {
    if (anim.t >= anim.total) anim.t = 0;
    requestAnimationFrame(animFrame);
  }
}

function initAnimation() {
  $('#anim-play').addEventListener('click', () => setPlaying(!anim.playing));
  $('#anim-scrub').addEventListener('input', e => {
    anim.t = anim.total * e.target.value / 1000;
    drawAnim();
  });
  on('preview', setAnimPath);
  new ResizeObserver(() => drawAnim()).observe($('#anim-canvas'));
}
