// The analyst layer: hairlines, brackets, labels, readouts, the map layer and the transcript strip.
// Everything that sits on the ground goes through project() from engine.js.
import { project } from './engine.js';

export const C = {
  ink: '#F2F5F6', inkDim: 'rgba(242,245,246,.55)', amber: '#FFBE55', halo: 'rgba(3,6,8,.82)',
  map: 'rgb(46,112,206)', mapLine: '#A9D2FF', mapInk: '#D6EAFF', plate: 'rgba(6,9,12,.62)',
};
export const F = {
  bc: w => `${w} BC`, pm: w => `${w} PM`,
};

let TS = 1;
export function setTextScale(s) {
  TS = s;
  if (s > 1) Object.assign(SUB, { x: 72, y: 1468, font: '400 46px PS', safe: 1080 - 72 - 150, maxLines: 2, lh: 60 });
}
let TX = null;                         // text registry for window.TEXTS
export function beginTexts() { TX = []; }
export function endTexts() { const r = TX; TX = null; return r; }

// rep: what readcheck should read for a counter that is still rolling (its landing value, per core/README: full text from the first frame)
export function text(ctx, s, x, y, { font = '500 30px BC', col = C.ink, align = 'left', track = 0, halo = 7, alpha = 1, id = null, base = 'alphabetic', rep = null, seen = null } = {}) {
  if (alpha <= 0.003 || !s) return 0;
  ctx.save();
  ctx.globalAlpha *= Math.min(1, alpha);
  ctx.font = font; ctx.textAlign = align; ctx.textBaseline = base; ctx.letterSpacing = track + 'px';
  const m = ctx.measureText(s), w = m.width;
  if (halo) { ctx.shadowColor = C.halo; ctx.shadowBlur = halo; }
  ctx.fillStyle = col; ctx.fillText(s, x, y);
  if (halo) { ctx.shadowBlur = halo * 0.35; ctx.fillText(s, x, y); }
  ctx.restore();
  if (id && TX && (seen ?? alpha) > 0.5) {
    const x0 = align === 'center' ? x - w / 2 : align === 'right' ? x - w : x;
    const asc = m.actualBoundingBoxAscent || 20, des = m.actualBoundingBoxDescent || 6;
    TX.push({ id, text: rep ?? s, x0, y0: y - asc, x1: x0 + w, y1: y + des });
  }
  return w;
}
export function measure(ctx, s, font, track = 0) {
  ctx.save(); ctx.font = font; ctx.letterSpacing = track + 'px'; const w = ctx.measureText(s).width; ctx.restore(); return w;
}
export function hair(ctx, path, { w = 1.4, col = C.ink, alpha = 1, halo = 3.2, haloCol = 'rgba(3,6,8,.45)', dash = null, off = 0, cap = 'butt' } = {}) {
  if (alpha <= 0.003) return;
  ctx.save(); ctx.globalAlpha *= Math.min(1, alpha); ctx.lineJoin = 'round'; ctx.lineCap = cap;
  if (dash) { ctx.setLineDash(dash); ctx.lineDashOffset = off; }
  if (halo) { ctx.beginPath(); path(); ctx.strokeStyle = haloCol; ctx.lineWidth = w + halo; ctx.stroke(); }
  ctx.beginPath(); path(); ctx.strokeStyle = col; ctx.lineWidth = w; ctx.stroke();
  ctx.restore();
}
// lon/lat polyline -> screen path. keep(lon, lat) can hide parts (scan printing). Returns screen pts.
export function pathLL(ctx, cam, line, { keep = null, frac = 1, close = false } = {}) {
  if (!line || line.length === 0) return;
  let pen = false; const n = line.length, lim = Math.max(1, Math.floor(n * frac));
  for (let i = 0; i < lim; i++) {
    const [lo, la] = line[i];
    if (keep && !keep(lo, la)) { pen = false; continue; }
    const [x, y, vis] = project(cam, la, lo);
    if (!vis) { pen = false; continue; }
    if (!pen) { ctx.moveTo(x, y); pen = true; } else ctx.lineTo(x, y);
  }
  if (close && frac >= 1 && !keep) ctx.closePath();
}
export function brackets(ctx, x0, y0, x1, y1, { len = 26, w = 1.6, alpha = 1, col = C.ink } = {}) {
  hair(ctx, () => {
    const L = Math.min(len, (x1 - x0) / 2, (y1 - y0) / 2);
    ctx.moveTo(x0, y0 + L); ctx.lineTo(x0, y0); ctx.lineTo(x0 + L, y0);
    ctx.moveTo(x1 - L, y0); ctx.lineTo(x1, y0); ctx.lineTo(x1, y0 + L);
    ctx.moveTo(x1, y1 - L); ctx.lineTo(x1, y1); ctx.lineTo(x1 - L, y1);
    ctx.moveTo(x0 + L, y1); ctx.lineTo(x0, y1); ctx.lineTo(x0, y1 - L);
  }, { w, alpha, col, halo: 2.4 });
}
export function tick(ctx, x, y, r, { alpha = 1, w = 1.4 } = {}) {
  hair(ctx, () => { ctx.moveTo(x - r, y); ctx.lineTo(x + r, y); ctx.moveTo(x, y - r); ctx.lineTo(x, y + r); }, { w, alpha });
}
// one reading: small label line, the big amber value, an optional unit, all left aligned at (x, y)
export function readout(ctx, x, y, { label = '', value = '', unit = '', note = '', alpha = 1, id = 'readout', size = 112, col = C.amber, rep = null, dim = 1 } = {}) {
  if (alpha <= 0.003) return;
  size = Math.round(size * (TS > 1 ? 1.15 : 1));
  text(ctx, label, x + 2, y - size * 0.86, { font: `500 ${Math.round(28 * TS)}px PS`, track: 0.5, alpha: alpha * 0.94, id: id + '-label' });
  const w = text(ctx, value, x, y, { font: `300 ${size}px BC`, col, track: -1, alpha: alpha * dim, halo: 12, id: id + '-value', rep, seen: alpha });
  if (unit) text(ctx, unit, x + w + 10, y, { font: `400 ${Math.round(size * 0.36)}px BC`, col, alpha, halo: 8, id: id + '-unit' });
  hair(ctx, () => { ctx.moveTo(x + 2, y + 22); ctx.lineTo(x + 2 + Math.max(220, w + 60), y + 22); }, { w: 1, alpha: alpha * 0.55, halo: 0 });
  if (note) text(ctx, note, x + 2, y + 22 + Math.round(34 * TS), { font: `400 ${Math.round(22 * TS)}px PM`, col: 'rgba(242,245,246,.82)', alpha, track: 0.5, id: id + '-note' });
}
// greedy word wrap to a pixel width
export function wrap(ctx, s, font, maxW, track = 0) {
  const words = s.split(' '), lines = []; let cur = '';
  for (const w of words) { const t = cur ? cur + ' ' + w : w; if (!cur || measure(ctx, t, font, track) <= maxW) cur = t; else { lines.push(cur); cur = w; } }
  if (cur) lines.push(cur);
  return lines;
}
// transcript strip: English, left aligned, bottom left; one line in landscape, up to two balanced lines in vertical
export const SUB = { x: 96, y: 1002, font: '400 34px PS', track: 0.2, safe: 1180, maxLines: 1, lh: 46 };
export function subtitle(ctx, en, alpha, id) {
  if (alpha <= 0.003) return;
  let lines = wrap(ctx, en, SUB.font, SUB.safe, SUB.track);
  if (lines.length === 2) {          // balance the two lines so the second is never one orphan word
    const ws = en.split(' '); let best = null;
    for (let k = 1; k < ws.length; k++) {
      const a = ws.slice(0, k).join(' '), b = ws.slice(k).join(' ');
      const wa = measure(ctx, a, SUB.font, SUB.track), wb = measure(ctx, b, SUB.font, SUB.track);
      if (wa <= SUB.safe && wb <= SUB.safe && (!best || Math.max(wa, wb) < best[0])) best = [Math.max(wa, wb), [a, b]];
    }
    if (best) lines = best[1];
  }
  const w = Math.max(...lines.map(l => measure(ctx, l, SUB.font, SUB.track)));
  const y0 = SUB.y - (lines.length - 1) * SUB.lh, top = y0 - SUB.lh + 4, hgt = lines.length * SUB.lh + 18;
  ctx.save(); ctx.globalAlpha = alpha;
  const g = ctx.createLinearGradient(SUB.x - 30, 0, SUB.x + w + 80, 0);
  g.addColorStop(0, 'rgba(5,8,11,.70)'); g.addColorStop(0.85, 'rgba(5,8,11,.56)'); g.addColorStop(1, 'rgba(5,8,11,0)');
  ctx.fillStyle = g; ctx.fillRect(SUB.x - 30, top, w + 110, hgt);
  ctx.fillStyle = C.ink; ctx.fillRect(SUB.x - 30, top, 2, hgt);
  ctx.restore();
  lines.forEach((l, i) => text(ctx, l, SUB.x, y0 + i * SUB.lh, { font: SUB.font, track: SUB.track, alpha, halo: 4 }));
}
