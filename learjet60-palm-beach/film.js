// "Four Minutes over Palm Beach" — the crash of Learjet 60 N722BD, 1 November 2026. Satellite Briefing.
// render(t) is a pure function of t: camera from keyframes, plates by altitude, every mark through engine.project.
import { clamp, lerp, seg, ss, eio, eo, ei } from '/core/lib.js';
import { Engine, makeCamera, project, unproject, ecef } from './engine.js';
import { C, text, measure, hair, pathLL, brackets, tick, readout, subtitle, SUB, beginTexts, endTexts, setTextScale, wrap } from './overlay.js';
import { T, VO, P, BEAT } from './timeline.js';

const W = innerWidth, H = innerHeight;
const V = H > W;                          // vertical (Shorts / Reels): 1080x1920
for (const id of ['gl', 'ov']) { const c = document.getElementById(id); c.width = W; c.height = H; }
const gl = new Engine(document.getElementById('gl'));
const cv = document.getElementById('ov'), ctx = cv.getContext('2d');
const TS = V ? 1.2 : 1;                   // text scale: a phone shows the frame small
const F = n => Math.round(n * TS);
setTextScale(TS);
// every position in one table: landscape keeps the original layout; vertical keeps clear of the Shorts UI
// (top ~230 px: search/camera; bottom ~360 px: title, channel; right ~150 px from mid-height: buttons)
const LY = V ? {
  fov: 50, sy: 210, date: [72, 262], clock: [72, 302], alt: [W - 72, 262], scale: [W - 72, 330],
  legend: 1140, logStorm: 800, logDive: 800, read: [84, 590], open: [84, 590], cruise: [84, 1250], routeNote: [72, 372],
  credit: [72, 1636], creditW: W - 72 - 72, endBox: [56, 330, W - 56, 980], title: [96, 470], titleSub: [100, 526],
  cause: [96, 720], memory: [100, 860], endCam: { sx: 0, sy: 560 },
} : {
  fov: 30, sy: 0, date: [96, 72], clock: [96, 108], alt: [W - 56, 72], scale: [W - 56, 988],
  legend: 180, logStorm: 360, logDive: 200, read: [1330, 470], open: [1330, 520], cruise: [250, 790], routeNote: [96, 140],
  credit: [W - 56, 1046], creditW: 0, endBox: [130, 250, 1000, 790], title: [200, 370], titleSub: [204, 424],
  cause: [200, 610], memory: [204, 740], endCam: { sx: 340, sy: 40 },
};

const load = src => new Promise((ok, no) => { const i = new Image(); i.onload = () => ok(i); i.onerror = () => no(new Error('image ' + src)); i.src = src; });
const json = src => fetch(src).then(r => { if (!r.ok) throw new Error(src); return r.json(); });
let PL, RADAR, CUES = [];
const BB = {};
const S = P.site;
const FT = 3280.84;                       // feet per km
const fmt = n => Math.round(n).toLocaleString('en-US');

// ------------------------------------------------------------------ the dive: the camera falls with the jet
// FAA (reported): 35,250 ft -> 8,750 ft in about one minute. The camera's altitude IS the reading in this window.
const ALT0 = 35250, ALT1 = 8750;
const diveU = t => { const u = seg(t, T.dive0, T.land8750); return u * (0.3 + 0.7 * u); };   // the fall accelerates
const jetFt = t => lerp(ALT0, ALT1, diveU(t));
const TILT0 = 28, HD0 = 84;

// ------------------------------------------------------------------ camera keyframes: t, target lon/lat, distance d (km, log), tilt, heading, lens shift
function camKeys() {
  const pre = ALT0 / FT / Math.cos(TILT0 * Math.PI / 180);
  const K = [
    { t: 0.0, ll: S, d: 1.95, tilt: 0, hd: 0 },
    { t: T.climb, ll: S, d: 1.72, tilt: 0, hd: -3, e: 'lin' },                                   // a slow creep while the voice speaks
    V ? { t: T.route0, ll: [-87.3, 27.6], d: 5000, tilt: 24, hd: 0, sy: 0, e: 'io' }                   // vertical: north up, pulled back so Austin and the Bahamas both fit the narrow frame
      : { t: T.route0, ll: [-86.2, 26.4], d: 3250, tilt: 30, hd: 6, sy: 30, e: 'io' },                 // the climb: one street to the whole trip               // the climb: one street to the whole trip
    V ? { t: T.storm0, ll: [-87.0, 27.6], d: 4800, tilt: 25, hd: 3, sy: 0, e: 'lin' }
      : { t: T.storm0, ll: [-85.9, 26.5], d: 3100, tilt: 31, hd: 10, sy: 30, e: 'lin' },             // orbit creep while the route grows
    { t: T.low, ll: [-80.5, 26.64], d: 150, tilt: 27, hd: 78, e: 'io' },                         // the dive into the storm
    { t: T.r1247, ll: [-80.45, 26.64], d: 120, tilt: 27, hd: 79, e: 'lin' },             // down to Palm Beach County, facing east with the jet
    { t: T.hush, ll: [-80.128, 26.633], d: pre * 1.02, tilt: TILT0, hd: HD0 - 2, e: 'io' },       // to cruise height above the site
    { t: T.dive0, ll: S, d: pre, tilt: TILT0, hd: HD0, e: 'lin' },                               // the held breath: barely moving
    { t: T.land8750, ll: S, d: 0, tilt: 0, hd: 0, e: 'dive' },                                   // d replaced by the jet's altitude (camAt)
    { t: T.impact, ll: S, d: 1.66, tilt: 0, hd: 0, e: 'o' },
    { t: T.impact + 0.45, ll: S, d: 1.7, tilt: 0, hd: 0, e: 'io' },                              // a small settle after the stop
    { t: T.out0, ll: S, d: 1.52, tilt: 0, hd: -7, e: 'lin' },                                    // locked nadir, a slow turn
    { t: T.end, ll: [-80.3, 26.66], d: 700, tilt: 14, hd: -3, e: 'i' },
    { t: T.dur, ll: [-82.6, 26.4], d: 6400, tilt: 36, hd: 6, ...LY.endCam, e: 'oL' },
  ];
  // vertical: the subject sits lower in the frame, under the readings (lens shift), unless a key sets its own
  if (V) for (const k of K) if (k.sy === undefined) k.sy = LY.sy;
  return K;
}
const EASE = { io: eio, i: t => t * t * (2.2 - 1.2 * t), o: eo, lin: t => t, dive: t => t, oL: t => 0.6 * eo(t) + 0.4 * t };
let KEYS;
// pan in step with the distance (linear in d): low down the target barely moves, high up it travels freely,
// so the ground never skates out of a narrow frame during a climb or a dive
function zoomFollow(d0, d1, d) { return clamp((d - d0) / (d1 - d0)); }
function camAt(t) {
  let i = 0; while (i < KEYS.length - 2 && t > KEYS[i + 1].t) i++;
  const a = KEYS[i], b = KEYS[i + 1];
  const u = (EASE[b.e] || eio)(seg(t, a.t, b.t));
  const sx = lerp(a.sx || 0, b.sx || 0, u), sy = lerp(a.sy || 0, b.sy || 0, u);
  if (b.e === 'dive') {        // the camera's height above the ground is the jet's reported altitude
    const tilt = lerp(a.tilt, b.tilt, ss(seg(t, a.t, b.t))), hd = lerp(a.hd, b.hd, ss(seg(t, a.t, b.t)));
    return { lon: S[0], lat: S[1], d: jetFt(t) / FT / Math.cos(tilt * Math.PI / 180), tilt, heading: hd, sx, sy, fov: LY.fov };
  }
  const da = a.e === 'dive' || (a.d === 0) ? ALT1 / FT : a.d;
  const lg = Math.exp(lerp(Math.log(da), Math.log(b.d), u));
  const k = Math.abs(Math.log(b.d / da)) > 1.2 ? zoomFollow(da, b.d, lg) : u;
  return { lon: lerp(a.ll[0], b.ll[0], k), lat: lerp(a.ll[1], b.ll[1], k), d: lg, tilt: lerp(a.tilt, b.tilt, u), heading: lerp(a.hd, b.hd, u), sx, sy, fov: LY.fov };
}

// ------------------------------------------------------------------ loading
async function init() {
  [PL, RADAR, CUES] = await Promise.all([json('assets/plates/plates.json'), json('assets/radar.json'), json('cues.json')]);
  const names = ['world', 'gulf', 'reg', 'mid', 'det'];
  const imgs = await Promise.all(names.map(n => load(`assets/plates/${n}.jpg`)));
  names.forEach((n, i) => { gl.upload(n, imgs[i]); BB[n] = PL[n].plate; });
  KEYS = camKeys();
  await Promise.all(['300 112px BC', '400 34px BC', '500 30px BC', '400 22px PM', '500 22px PM', '400 34px PS', '500 28px PS', '500 72px SF', '400 30px SF'].map(f => document.fonts.load(f, 'Learjet 0123456789')));
  subCheck();
  window.EV = events();
  window.READY = true;
}
function subCheck() {
  const rep = CUES.map(c => { const lines = wrap(ctx, c.en, SUB.font, SUB.safe, SUB.track); return { id: c.id, en: c.en, lines: lines.length, w: Math.round(Math.max(...lines.map(l => measure(ctx, l, SUB.font, SUB.track)))) }; });
  window.SUBCHECK = { safe: SUB.safe, cues: rep, ok: rep.every(r => r.w <= SUB.safe && r.lines <= SUB.maxLines) };
  if (!window.SUBCHECK.ok) throw new Error('subtitle too wide: ' + JSON.stringify(rep.filter(r => r.w > SUB.safe || r.lines > SUB.maxLines)));
}

// ------------------------------------------------------------------ the frame
const fadeBelow = (alt, k) => clamp(1 - (Math.log(alt) - Math.log(k)) / Math.log(2.2));
function render(t) {
  t = clamp(t, 0, T.dur - 1e-4);
  beginTexts();
  const cp = camAt(t);
  const cam = makeCamera(cp, W, H);
  const alt = cam.alt;
  const grey = t < T.climb + 0.4 ? 1 : t < T.storm0 ? 1 - ss(seg(t, T.climb + 0.4, T.route0 - 0.6))
    : t < T.out0 + 1 ? ss(seg(t, T.storm0, T.radar[2])) : 1 - ss(seg(t, T.end - 0.6, T.end + 2.2));
  const near = ss(seg(Math.log(alt), Math.log(60), Math.log(4)));
  gl.draw({
    cam, bbox: BB,
    plates: { gulf: 1, reg: fadeBelow(alt, 700), mid: fadeBelow(alt, 30), det: fadeBelow(alt, 4.2) },
    grey, shade: ss(seg(Math.log(alt), Math.log(500), Math.log(2500))),
    detail: 0.8 + 0.05 * near, clarity: 0.35 - 0.1 * near, contrast: 1 - 0.1 * near, expo: 1 - 0.08 * near,
    dim: 0.4 * ss(seg(t, T.end, T.end + 0.9)),
  });

  ctx.clearRect(0, 0, W, H);
  drawRadar(t, cam);
  drawRoute(t, cam);
  drawSiteMarks(t, cam);
  drawLock(t, cam);
  drawHud(t, cam);
  drawLog(t);
  drawReadouts(t, cam);
  drawSubs(t);
  drawEnd(t, cam);
  drawPaint(t);
  return endTexts();
}

// ------------------------------------------------------------------ opening: a scan paints the frame in, top to bottom
function drawPaint(t) {
  const u = seg(t, 0.0, 0.95);
  if (u >= 1) return;
  const y = lerp(-40, H + 60, eio(u));
  ctx.save();
  ctx.fillStyle = '#030507'; ctx.fillRect(0, y, W, H - y + 10);
  const g = ctx.createLinearGradient(0, y - 90, 0, y + 4);
  g.addColorStop(0, 'rgba(220,235,255,0)'); g.addColorStop(0.9, 'rgba(220,235,255,.14)'); g.addColorStop(1, 'rgba(240,248,255,.5)');
  ctx.globalCompositeOperation = 'screen'; ctx.fillStyle = g; ctx.fillRect(0, y - 90, W, 94);
  ctx.restore();
}

// ------------------------------------------------------------------ the reticle: search, then lock on the impact point
function drawLock(t, cam) {
  if (t > T.climb + 0.9) return;
  const [ax, ay] = project(cam, S[1], S[0]);
  const lockU = eo(seg(t, T.lock - 0.35, T.lock));
  const wander = [ax + 230 * Math.cos(t * 3.0 + 0.6) * (1 - lockU), ay - 130 * Math.sin(t * 2.2 + 0.3) * (1 - lockU)];
  const r = lerp(150, 70, lockU) + 12 * Math.exp(-Math.max(0, t - T.lock) * 9) * (t > T.lock ? 1 : 0) + 30 * ss(seg(t, T.climb, T.climb + 0.8));
  const a = ss(seg(t, 0.55, 0.8)) * (1 - ss(seg(t, T.climb + 0.2, T.climb + 0.9)));
  brackets(ctx, wander[0] - r, wander[1] - r, wander[0] + r, wander[1] + r, { len: 22, alpha: a, w: 2 });
  tick(ctx, wander[0], wander[1], 7, { alpha: a * lockU });
  const ca = a * ss(seg(t, T.lock, T.lock + 0.25));
  text(ctx, '26.633° N   80.113° W', wander[0] - r, wander[1] - r - 16, { font: '400 22px PM', alpha: ca * 0.92, halo: 6, id: 'coords' });
}

// ------------------------------------------------------------------ the trip: Austin -> Palm Beach (route approximate), then the planned leg to Eleuthera
function gc(a, b, n = 80) {   // great-circle points from a to b (lon, lat)
  const A = ecef(a[1], a[0]), B = ecef(b[1], b[0]);
  const pts = [];
  for (let i = 0; i <= n; i++) {
    const u = i / n, x = lerp(A[0], B[0], u), y = lerp(A[1], B[1], u), z = lerp(A[2], B[2], u), r = Math.hypot(x, y, z);
    pts.push([Math.atan2(y, x) * 180 / Math.PI, Math.asin(z / r) * 180 / Math.PI]);
  }
  return pts;
}
let LEG1, LEG2;
function drawRoute(t, cam) {
  if (t < T.austin - 0.3 || t > T.radar[3] + 1.2) return;
  LEG1 = LEG1 || gc(P.austin, S); LEG2 = LEG2 || gc(S, P.eleuthera, 30);
  const out = 1 - ss(seg(t, T.storm0 + 0.6, T.radar[1]));
  const g = eio(seg(t, T.austin, T.routeEnd));
  hair(ctx, () => pathLL(ctx, cam, LEG1, { frac: Math.max(0.0001, g) }), { w: 2.6, alpha: out, dash: [12, 8], halo: 4, haloCol: 'rgba(3,6,8,.6)' });
  const g2 = eo(seg(t, T.routeEnd, T.routeEnd + 0.9));
  if (g2 > 0) hair(ctx, () => pathLL(ctx, cam, LEG2, { frac: Math.max(0.0001, g2) }), { w: 1.6, alpha: out * 0.7, dash: [5, 8], halo: 3 });
  // the tip: a small chevron riding the line
  if (g > 0 && g < 1) {
    const i = Math.min(LEG1.length - 1, Math.floor(g * (LEG1.length - 1)));
    const [x, y] = project(cam, LEG1[i][1], LEG1[i][0]);
    brackets(ctx, x - 10, y - 10, x + 10, y + 10, { len: 6, w: 1.8, alpha: out });
  }
  // places
  const dot = (ll, a, label, sub, dx, dy, id, align = 'left') => {
    if (a <= 0) return;
    const [x, y, vis] = project(cam, ll[1], ll[0]); if (!vis) return;
    hair(ctx, () => ctx.arc(x, y, 7, 0, 6.2832), { w: 2, alpha: a, halo: 4 });
    hair(ctx, () => { ctx.moveTo(x + Math.sign(dx) * 8, y + Math.sign(dy) * 6); ctx.lineTo(x + dx * 0.6, y + dy); ctx.lineTo(x + dx, y + dy); }, { w: 1.2, alpha: a * 0.9 });
    const tx = x + dx + (align === 'left' ? 8 : -8);
    text(ctx, label, tx, y + dy + 10, { font: `500 ${F(32)}px PS`, alpha: a, align, id, halo: 8 });
    if (sub) text(ctx, sub, tx, y + dy + 10 + F(34), { font: `400 ${F(22)}px PM`, alpha: a * 0.85, align, id: id + '-sub', halo: 6 });
  };
  dot(P.austin, ss(seg(t, T.austin - 0.25, T.austin + 0.05)) * out, 'Austin, Texas', 'KAUS · departure', 50, -58, 'austin');
  dot(P.eleuthera, ss(seg(t, T.bahamas - 0.25, T.bahamas + 0.05)) * out, 'North Eleuthera', 'MYEH · destination', -40, 64, 'eleuthera', 'right');
  const pa = ss(seg(t, T.routeEnd - 0.2, T.routeEnd + 0.1)) * out;
  if (pa > 0) {
    const [x, y] = project(cam, S[1], S[0]);
    hair(ctx, () => ctx.arc(x, y, 9 + 18 * (1 - pa), 0, 6.2832), { w: 2, alpha: pa, halo: 4 });
    text(ctx, 'Palm Beach County', x - 6, y - 52, { font: `500 ${F(32)}px PS`, alpha: pa, align: V ? 'center' : 'right', id: 'pbc', halo: 8 });
  }
  const na = ss(seg(t, T.austin + 0.6, T.austin + 1.0)) * out * (1 - ss(seg(t, T.storm0, T.storm0 + 0.4)));
  text(ctx, 'route approximate · destination leg as planned', LY.routeNote[0], LY.routeNote[1], { font: `400 ${F(22)}px PM`, alpha: na * 0.8, halo: 6, id: 'route-note' });
}

// ------------------------------------------------------------------ the storm: NEXRAD outlines scan in, frame by frame (12:30 -> 12:45 EST)
const RFR = ['1730', '1735', '1740', '1745'];
let RF;
function radarFrame(hhmm) { RF = RF || {}; return RF[hhmm] || (RF[hhmm] = RADAR.frames.find(f => f.utc.endsWith(hhmm))); }
function radarState(t) {   // which frame is printed, and where the scan front is (lat; newer north of it)
  const N = RADAR.box[3], Sx = RADAR.box[1];
  let cur = null, prev = null, scan = -90;
  T.radar.forEach((tt, i) => {
    const t0 = tt - 0.55;
    if (t >= t0) { prev = cur; cur = RFR[i]; scan = t < tt ? lerp(N, Sx, ss(seg(t, t0, tt))) : -90; }
  });
  return { cur, prev, scan };
}
function drawRadar(t, cam) {
  if (t < T.radar[0] - 0.6 || t > T.dive0 + 1.5) return;
  const a = ss(seg(t, T.radar[0] - 0.6, T.radar[0] - 0.3)) * (1 - ss(seg(Math.log(cam.alt), Math.log(40), Math.log(12)))) * (1 - ss(seg(t, T.dive0 - 0.5, T.dive0 + 1.2)));
  if (a <= 0.003) return;
  const st = radarState(t);
  const draw = (hhmm, keep, al) => {
    const f = radarFrame(hhmm); if (!f) return;
    hair(ctx, () => { for (const l of f.levels['40']) pathLL(ctx, cam, l, { keep }); }, { w: 1.4, alpha: al * 0.7, halo: 2.6 });
    hair(ctx, () => { for (const l of f.levels['50']) pathLL(ctx, cam, l, { keep }); }, { w: 2.6, alpha: al, halo: 4, haloCol: 'rgba(3,6,8,.7)' });
  };
  if (st.prev && st.scan > -90) draw(st.prev, (lo, la) => la <= st.scan, a);
  if (st.cur) draw(st.cur, st.scan > -90 ? (lo, la) => la > st.scan : null, a);
  // the scan front: a soft band across the frame
  if (st.scan > -90 && cam.alt < 400) {
    const p = project(cam, st.scan, cam.tgt.lon);
    const g = ctx.createLinearGradient(0, p[1] - 70, 0, p[1] + 3);
    g.addColorStop(0, 'rgba(220,235,255,0)'); g.addColorStop(1, 'rgba(230,242,255,.16)');
    ctx.save(); ctx.globalCompositeOperation = 'screen'; ctx.fillStyle = g; ctx.fillRect(0, p[1] - 70, W, 73); ctx.restore();
  }
  // legend: what the lines are
  const la = a * ss(seg(t, T.radar[0], T.radar[0] + 0.3));
  const lx = LY.date[0], ly = LY.legend;
  panel(lx - 36, ly - 40, lx + 540, ly + F(100), la * 0.8);
  hair(ctx, () => { ctx.moveTo(lx, ly + F(34)); ctx.lineTo(lx + 40, ly + F(34)); }, { w: 2.6, alpha: la, halo: 3 });
  text(ctx, 'heavy rain, ≥ 50 dBZ', lx + 52, ly + F(42), { font: `400 ${F(22)}px PM`, alpha: la * 0.9, halo: 6, id: 'leg50' });
  hair(ctx, () => { ctx.moveTo(lx, ly + F(70)); ctx.lineTo(lx + 40, ly + F(70)); }, { w: 1.4, alpha: la * 0.7, halo: 2 });
  text(ctx, '≥ 40 dBZ', lx + 52, ly + F(78), { font: `400 ${F(22)}px PM`, alpha: la * 0.8, halo: 6, id: 'leg40' });
  text(ctx, 'NOAA NEXRAD radar', lx, ly, { font: `500 ${F(24)}px PM`, alpha: la * 0.92, halo: 6, id: 'leg-title' });
}

// ------------------------------------------------------------------ the site: impact point, Military Trail, the NTSB note
const TRAIL = [[-80.11232, 26.6440], [-80.11232, 26.6215]];   // Military Trail (SR 809), straight N-S here, traced on NAIP 2023
function drawSiteMarks(t, cam) {
  const [x, y, vis] = project(cam, S[1], S[0]);
  if (!vis) return;
  // storm section: where it came down, quietly marked
  const sa = ss(seg(t, T.r1247 - 0.3, T.r1247)) * (1 - ss(seg(t, T.dive0 - 0.4, T.dive0)));
  if (sa > 0) {
    hair(ctx, () => ctx.arc(x, y, 10, 0, 6.2832), { w: 1.8, alpha: sa * 0.9, halo: 4 });
    tick(ctx, x, y, 4, { alpha: sa });
    hair(ctx, () => { ctx.moveTo(x + 9, y - 9); ctx.lineTo(x + 40, y - 46); ctx.lineTo(x + 64, y - 46); }, { w: 1.2, alpha: sa * 0.85 });
    text(ctx, 'crash site', x + 70, y - 38, { font: '500 28px PS', alpha: sa, id: 'site-storm', halo: 8 });
  }
  // dive: brackets close on the point as the ground comes up
  if (t >= T.dive0 - 0.2 && t < T.impact + 0.6) {
    const u = seg(t, T.dive0, T.impact), r = lerp(130, 46, eo(u)) - 10 * ss(seg(t, T.impact - 0.1, T.impact + 0.1));
    const a = ss(seg(t, T.dive0 - 0.2, T.dive0 + 0.3)) * (1 - ss(seg(t, T.impact + 0.2, T.impact + 0.6)));
    brackets(ctx, x - r, y - r, x + r, y + r, { len: 16, w: 2, alpha: a });
  }
  if (t < T.impact - 0.05) return;
  const out = 1 - ss(seg(t, T.out0 + 0.9, T.out0 + 1.8));
  const kmpx = cam.alt / cam.F;
  // the impact ring: prints, then breathes slowly
  const rg = ss(seg(t, T.ring - 0.25, T.ring + 0.2));
  const rr = (0.045 / kmpx) * (0.8 + 0.2 * rg);
  const breathe = t > T.breakup ? 0.25 * (0.5 + 0.5 * Math.sin((t - T.breakup) * Math.PI * 2 / (BEAT * 4))) : 0;
  hair(ctx, () => ctx.arc(x, y, rr, 0, 6.2832), { w: 2.6 + 1.6 * breathe, alpha: out * rg, halo: 5, haloCol: 'rgba(3,6,8,.6)' });
  tick(ctx, x, y, 6, { alpha: out * ss(seg(t, T.impact, T.impact + 0.12)), w: 2 });
  const la = ss(seg(t, T.ring, T.ring + 0.3)) * out;
  hair(ctx, () => { ctx.moveTo(x - rr * 0.72, y + rr * 0.72); ctx.lineTo(x - rr - 40, y + rr + 50); ctx.lineTo(x - rr - 70, y + rr + 50); }, { w: 1.3, alpha: la });
  text(ctx, 'impact', x - rr - 78, y + rr + 60, { font: `500 ${F(32)}px PS`, align: 'right', alpha: la, id: 'impact', halo: 8 });
  text(ctx, '12:51:50 EST', x - rr - 78, y + rr + 60 + F(34), { font: `400 ${F(22)}px PM`, align: 'right', alpha: la * 0.88, id: 'impact-time', halo: 6 });
  // Military Trail traced north to south
  const tg = eio(seg(t, T.trail0, T.trail1));
  if (tg > 0) {
    const ln = [TRAIL[0], [TRAIL[0][0], lerp(TRAIL[0][1], TRAIL[1][1], tg)]];
    hair(ctx, () => pathLL(ctx, cam, ln), { w: 2.0, alpha: out * 0.9, dash: [14, 8], halo: 4 });
    const [mx, my] = project(cam, 26.6352, TRAIL[0][0]);
    const ma = ss(seg(t, T.trail0 + 0.4, T.trail0 + 0.8)) * out;
    hair(ctx, () => { ctx.moveTo(mx + 6, my); ctx.lineTo(mx + 60, my - 20); ctx.lineTo(mx + 86, my - 20); }, { w: 1.2, alpha: ma });
    text(ctx, 'Military Trail', mx + 94, my - 11, { font: `500 ${F(32)}px PS`, alpha: ma, id: 'trail', halo: 8 });
  }
  // the NTSB's first finding, pinned to the ring
  const na = ss(seg(t, T.breakup - 0.2, T.breakup + 0.2)) * out;
  if (na > 0) {
    const bx = x + rr * 0.72, by = y - rr * 0.72;
    // landscape: to the upper right of the ring; vertical: the leader runs up to a note on the left (the frame is narrow)
    const nx = V ? LY.read[0] : bx + 112, ny = V ? by - 230 : by - 82;
    hair(ctx, () => { ctx.moveTo(bx, by); if (V) { ctx.lineTo(bx + 30, ny + 22); ctx.lineTo(nx, ny + 22); } else { ctx.lineTo(bx + 70, by - 90); ctx.lineTo(bx + 104, by - 90); } }, { w: 1.3, alpha: na });
    text(ctx, 'possible break-up before impact', nx, ny, { font: `500 ${F(30)}px PS`, alpha: na, id: 'breakup', halo: 8 });
    text(ctx, 'NTSB briefing · 2 Nov 2026', nx, ny + (V ? -F(44) : 34), { font: `400 ${F(22)}px PM`, alpha: na * 0.88, id: 'breakup-src', halo: 6 });
  }
}

// ------------------------------------------------------------------ instruments: clock, altitude, scale bar, credit
function clockAt(t) {   // EST shown on screen, per section; null = hidden
  if (t < T.climb + 0.3) return '12:51:50';
  if (t < T.radar[0] - 0.6) return null;
  if (t < T.r1247) { let m = 25; T.radar.forEach((tt, i) => { if (t >= tt) m = 30 + 5 * i; }); return `12:${String(m).padStart(2, '0')}:00`; }
  if (t < T.dive0) return '12:47:00';
  if (t < T.impact) { const s = Math.round(lerp(48 * 60, 51 * 60 + 50, seg(t, T.dive0, T.impact))); return `12:${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`; }
  if (t < T.out0) return '12:51:50';
  return null;
}
function drawHud(t, cam) {
  const hudA = 1 - ss(seg(t, T.end - 0.2, T.end + 0.4));
  const ck = clockAt(t);
  const ca = hudA * ss(seg(t, 0.6, 0.9)) * (ck ? 1 : 0) * (1 - (t > T.climb && t < T.radar[0] ? 1 : 0));
  if (ck) {
    panel(LY.date[0] - 46, LY.date[1] - 42, LY.date[0] + 384, LY.clock[1] + 22, ca * 0.75);
    text(ctx, 'SUN 1 NOV 2026', LY.date[0], LY.date[1], { font: `400 ${F(22)}px PM`, alpha: ca * 0.8, halo: 5, id: 'date' });
    text(ctx, ck + ' EST', LY.clock[0], LY.clock[1], { font: `500 ${F(30)}px PM`, alpha: ca, halo: 6, id: 'clock', rep: t < T.climb ? '12:51:50 EST' : t < T.dive0 ? '12:47:00 EST' : '12:51:50 EST' });
  }
  // camera altitude (the instrument): km high up, feet near the ground
  const aa = hudA * ss(seg(t, 0.6, 0.9));
  const altTxt = cam.alt > 30 ? fmt(Math.round(cam.alt / 10) * 10) + ' km' : fmt(Math.round(cam.alt * FT / 50) * 50) + ' ft';
  text(ctx, 'CAMERA ALT', LY.alt[0] - F(244), LY.alt[1], { font: `400 ${F(20)}px PM`, alpha: aa * 0.75, halo: 5, id: 'alt-label', align: 'right' });
  text(ctx, altTxt, LY.alt[0], LY.alt[1], { font: `400 ${F(22)}px PM`, alpha: aa * 0.9, align: 'right', halo: 5 });
  // scale bar when looking nearly straight down
  const sa = hudA * (1 - ss(seg(t, T.climb, T.climb + 0.6)) + ss(seg(t, T.impact, T.impact + 0.5)) * (1 - ss(seg(t, T.out0, T.out0 + 0.6))));
  if (sa > 0.01) {
    const kmpx = cam.alt / cam.F;
    const nice = [0.05, 0.1, 0.2, 0.25, 0.5, 1, 2, 5];
    let km = nice[0]; for (const n of nice) if (n / kmpx <= 240) km = n;
    const L = km / kmpx, x1 = LY.scale[0], x0 = x1 - L, y = LY.scale[1];
    hair(ctx, () => { ctx.moveTo(x0, y - 6); ctx.lineTo(x0, y); ctx.lineTo(x1, y); ctx.lineTo(x1, y - 6); }, { w: 1.2, alpha: sa * 0.8, halo: 2 });
    text(ctx, km < 1 ? Math.round(km * 1000) + ' m' : km + ' km', x1, y - 12, { font: `400 ${F(20)}px PM`, align: 'right', alpha: sa * 0.8, halo: 5 });
  }
  // imagery credit for what is on screen
  const parts = [];
  const alt = cam.alt;
  if (alt < 40) parts.push('USDA NAIP 2023 (before the crash)');
  if (alt >= 10 && alt < 1200) parts.push('Landsat 8 · USGS, Jan 2026');
  if (alt >= 300) parts.push('Blue Marble · NASA');
  if (t > T.radar[0] - 0.6 && t < T.dive0 + 1) parts.push('Radar · NOAA NEXRAD via IEM');
  const ia = 0.78 * ss(seg(t, 0.8, 1.1)) * (1 - ss(seg(t, T.end, T.end + 0.5)));
  if (V) {   // vertical: left aligned under the subtitles, wrapped
    const lines = wrap(ctx, 'Imagery: ' + parts.join(' · '), `400 ${F(20)}px PM`, LY.creditW, 0.2);
    lines.forEach((l, i) => text(ctx, l, LY.credit[0], LY.credit[1] + i * F(28), { font: `400 ${F(20)}px PM`, alpha: ia, halo: 5, track: 0.2 }));
  } else text(ctx, 'Imagery: ' + parts.join('  ·  '), LY.credit[0], LY.credit[1], { font: '400 20px PM', align: 'right', alpha: ia, halo: 5, track: 0.2 });
}

// ------------------------------------------------------------------ the log: what the crew reported, as reported (left column, under the clock)
const LOG = [
  { t: T.r1247, s: '12:47  turbulence · icing reported' },
  { t: T.req370, s: '12:47  climb to FL370 requested' },
  { t: T.logOver, s: '       overspeed reported' },
  { t: T.log20k, s: '       descent 20,000 ft/min reported' },
  { t: T.logMay, s: '12:48  MAYDAY' },
];
function drawLog(t) {
  if (t < T.r1247 - 0.1 || t > T.impact + 1.2) return;
  const out = 1 - ss(seg(t, T.impact + 0.3, T.impact + 1.0));
  // during the storm section the radar legend sits under the clock: the log starts lower down
  let y = t < T.dive0 ? LY.logStorm : lerp(LY.logStorm, LY.logDive, ss(seg(t, T.dive0, T.dive0 + 0.8)));
  panel(LY.date[0] - 36, y - 70, LY.date[0] + 700, y + 5 * F(38), 0.5 * out * ss(seg(t, T.r1247 - 0.1, T.r1247 + 0.3)));
  text(ctx, V ? 'CREW REPORTS · as reported' : 'CREW REPORTS · as reported by AIN, Wikipedia', LY.date[0], y - F(40), { font: `400 ${F(20)}px PM`, alpha: out * 0.7 * ss(seg(t, T.r1247 - 0.1, T.r1247 + 0.2)), halo: 5, id: 'log-title' });
  LOG.forEach((L, i) => {
    const a = ss(seg(t, L.t - 0.05, L.t + 0.15)) * out;
    if (a <= 0) return;
    const fresh = Math.exp(-Math.max(0, t - L.t) * 3);
    text(ctx, L.s, LY.date[0], y + i * F(38), { font: `${i === 4 ? 500 : 400} ${F(26)}px PM`, col: i === 4 ? C.amber : C.ink, alpha: a * (0.8 + 0.2 * fresh), halo: 6, id: 'log-' + i });
  });
}

// ------------------------------------------------------------------ readouts: one finding per screen, in the right third
// the analyst dims the ground behind text so the reading never fights the imagery
function panel(x0, y0, x1, y1, a) {
  if (a <= 0.003) return;
  const cx = (x0 + x1) / 2, cy = (y0 + y1) / 2, r = (x1 - x0) * 0.75, k = (y1 - y0) / (x1 - x0);   // an ellipse over the box
  ctx.save(); ctx.translate(cx, cy); ctx.scale(1, k);
  const g = ctx.createRadialGradient(0, 0, r * 0.2, 0, 0, r);
  g.addColorStop(0, `rgba(3,6,9,${0.62 * a})`); g.addColorStop(1, 'rgba(3,6,9,0)');
  ctx.fillStyle = g; ctx.fillRect(-r, -r, 2 * r, 2 * r); ctx.restore();
}
function drawReadouts(t, cam) {
  const X = LY.read[0], Y = LY.read[1];
  const near = ss(seg(Math.log(cam.alt), Math.log(300), Math.log(40)));
  const rd = (a) => panel(X - 80, Y - 140, X + 560, Y + 140, a * near);
  // opening: the time it happened
  if (t >= T.stamp - 0.1 && t < T.climb + 0.6) {
    const a = ss(seg(t, T.stamp - 0.1, T.stamp + 0.15)) * (1 - ss(seg(t, T.climb, T.climb + 0.5)));
    panel(LY.open[0] - 80, LY.open[1] - 140, LY.open[0] + 560, LY.open[1] + 140, a * near); readout(ctx, LY.open[0], LY.open[1], { label: 'Learjet 60 · N722BD', value: '12:51', unit: 'p.m. EST', alpha: a, id: 'when', note: 'Sunday 1 November 2026 · reports' });
  }
  // route: cruise
  if (t >= T.cruise - 0.6 && t < T.storm0 + 0.6) {
    const a = ss(seg(t, T.cruise - 0.6, T.cruise - 0.3)) * (1 - ss(seg(t, T.storm0, T.storm0 + 0.5)));
    const u = eo(seg(t, T.cruise - 0.6, T.cruise));
    const pop = Math.exp(-Math.max(0, t - T.cruise) * 7) * (t >= T.cruise ? 1 : 0);
    readout(ctx, LY.cruise[0], LY.cruise[1], { label: 'cruise altitude', value: fmt(Math.round(35000 * u / 250) * 250), unit: 'ft', alpha: a, id: 'cruise', note: 'reports', rep: '35,000', size: Math.round(112 * (1 + 0.07 * pop)) });
  }
  // storm: 12:47 and the request
  if (t >= T.r1247 - 0.05 && t < T.dive0 - 0.1) {
    const a = ss(seg(t, T.r1247 - 0.05, T.r1247 + 0.15)) * (1 - ss(seg(t, T.dive0 - 1.0, T.dive0 - 0.3)));
    rd(a); readout(ctx, X, Y, { label: 'crew asks to climb', value: '37,000', unit: 'ft', alpha: a * ss(seg(t, T.req370 - 0.1, T.req370 + 0.15)), id: 'req', note: 'from 35,000 ft · approved by ATC' });
  }
  // the dive: the reading is the camera's own altitude (= the jet's reported altitude)
  if (t >= T.dive0 - 0.2 && t < T.impact + 0.9) {
    const a = ss(seg(t, T.dive0 - 0.2, T.dive0 + 0.1)) * (1 - ss(seg(t, T.impact + 0.25, T.impact + 0.85)));
    const v = t < T.land8750 ? jetFt(t) : ALT1;
    const shown = t >= T.land8750 ? fmt(ALT1) : fmt(Math.round(v / 50) * 50);
    const pop = Math.exp(-Math.max(0, t - T.land8750) * 7) * (t >= T.land8750 ? 1 : 0);
    rd(a); readout(ctx, X, Y, { label: 'N722BD altitude', value: shown, unit: 'ft', alpha: a, id: 'dive', note: 'FAA: 35,250 → 8,750 ft in about 1 min', rep: fmt(ALT1), dim: t < T.land8750 ? 0.75 : 1, size: Math.round(112 * (1 + 0.08 * pop)) });
  }
  // the site
  if (t >= T.res600 - 0.5 && t < T.breakup + 0.2) {
    const a = ss(seg(t, T.res600 - 0.5, T.res600 - 0.2)) * (1 - ss(seg(t, T.breakup - 0.4, T.breakup)));
    const u = eo(seg(t, T.res600 - 0.5, T.res600));
    const pop = Math.exp(-Math.max(0, t - T.res600) * 7) * (t >= T.res600 ? 1 : 0);
    rd(a); readout(ctx, X, Y, { label: 'residents displaced', value: '≈ ' + Math.round(600 * u / 10) * 10, alpha: a, id: 'res', note: 'mobile home community · reports', rep: '≈ 600', size: Math.round(112 * (1 + 0.07 * pop)) });
  }
}

function drawSubs(t) {
  for (const c of CUES) {
    if (t < c.t0 || t > c.t1) continue;
    const a = ss(seg(t, c.t0, c.t0 + 0.12)) * (1 - ss(seg(t, c.t1 - 0.12, c.t1)));
    subtitle(ctx, c.en, a, c.id);
  }
}

// ------------------------------------------------------------------ end card: the reticle opens into the frame
function drawEnd(t, cam) {
  if (t < T.end - 0.1) return;
  const u = eo(seg(t, T.end, T.end + 0.7));
  const [ax, ay] = project(cam, S[1], S[0]);
  const br = 12 * seg(t, T.end + 0.7, T.dur);
  const [EX0, EY0, EX1, EY1] = LY.endBox;
  const X0 = lerp(ax - 40, EX0, u) - br, Y0 = lerp(ay - 40, EY0, u) - br, X1 = lerp(ax + 40, EX1, u) + br, Y1 = lerp(ay + 40, EY1, u) + br;
  brackets(ctx, X0, Y0, X1, Y1, { len: 30, alpha: ss(seg(t, T.end - 0.1, T.end + 0.1)) });
  const pu = seg(t, T.end + 1.0, T.dur - 0.3);
  if (pu > 0 && pu < 1) {
    const yb = lerp(-120, H + 120, ss(pu));
    const g = ctx.createLinearGradient(0, yb - 120, 0, yb + 6);
    g.addColorStop(0, 'rgba(220,235,255,0)'); g.addColorStop(0.92, 'rgba(220,235,255,.08)'); g.addColorStop(1, 'rgba(240,248,255,.24)');
    ctx.save(); ctx.globalCompositeOperation = 'screen'; ctx.fillStyle = g; ctx.fillRect(0, yb - 120, W, 126); ctx.restore();
  }
  const a1 = ss(seg(t, T.end + 0.15, T.end + 0.4)), a2 = ss(seg(t, T.end + 0.3, T.end + 0.55)), a3 = ss(seg(t, T.end + 0.5, T.end + 0.8)), a4 = ss(seg(t, T.end + 1.1, T.end + 1.5));
  text(ctx, 'Learjet 60 · N722BD', LY.title[0], LY.title[1], { font: `500 ${V ? 76 : 72}px SF`, track: 1, alpha: a1, halo: 14, id: 'title' });
  if (V) { text(ctx, '1 November 2026', LY.titleSub[0], LY.titleSub[1], { font: '400 36px SF', alpha: a2, halo: 8, id: 'title-sub' }); text(ctx, 'Palm Beach County, Florida', LY.titleSub[0], LY.titleSub[1] + 46, { font: '400 36px SF', alpha: a2, halo: 8, id: 'title-sub2' }); }
  else text(ctx, '1 November 2026 · Palm Beach County, Florida', LY.titleSub[0], LY.titleSub[1], { font: '400 30px SF', alpha: a2, halo: 8, id: 'title-sub' });
  const ry = LY.titleSub[1] + (V ? 90 : 38);
  hair(ctx, () => { ctx.moveTo(LY.titleSub[0], ry); ctx.lineTo(LY.titleSub[0] + (V ? 820 : 640) * a2, ry); }, { w: 1, alpha: a2 * 0.6, halo: 0 });
  readout(ctx, LY.cause[0], LY.cause[1], { label: 'probable cause', value: 'under investigation', alpha: a3, id: 'cause', note: 'NTSB · cockpit voice recorder sought', size: V ? 92 : 84 });
  text(ctx, 'In memory of the nine people on board.', LY.memory[0], LY.memory[1], { font: `400 ${V ? 34 : 28}px SF`, alpha: a4 * 0.9, halo: 8, id: 'memory' });
}

// ------------------------------------------------------------------ sound and cue events (exported by events.mjs)
function events() {
  const E = [];
  const ev = (t, type, o = {}) => E.push({ t: +t.toFixed(4), type, ...o });
  ev(0, 'paint', { dur: 0.95 }); ev(0.55, 'servo'); ev(T.lock, 'lock'); ev(T.stamp, 'stamp');
  ev(T.climb, 'climb', { to: T.route0 }); ev(T.austin, 'mark'); ev(T.austin, 'route', { to: T.routeEnd }); ev(T.cruise, 'land');
  ev(T.bahamas, 'mark2'); ev(T.routeEnd, 'mark2');
  ev(T.storm0, 'descend', { to: T.low });
  T.radar.forEach((tt, i) => { ev(tt - 0.55, 'scan_down', { dur: 0.55 }); ev(tt, 'radar', { i }); });
  ev(T.r1247, 'log'); ev(T.req370, 'log'); ev(T.req370, 'stamp');
  ev(T.hush, 'silence', { to: T.dive0 });
  ev(T.dive0, 'dive', { to: T.land8750 });
  ev(T.logOver, 'log'); ev(T.log20k, 'log'); ev(T.logMay + BEAT, 'alarm');   // after the spoken word, never on it
  ev(T.land8750, 'land');
  ev(T.impact, 'impact'); ev(T.impact, 'silence', { to: T.trail0 });
  ev(T.ring, 'ring'); ev(T.trail0, 'trail', { to: T.trail1 }); ev(T.res600, 'land');
  ev(T.breakup, 'mark2');
  ev(T.out0, 'climb', { to: T.end + 2 }); ev(T.end, 'end'); ev(T.end + 0.6, 'lock_echo'); ev(T.end + 1.0, 'pass', { to: T.dur - 0.3 });
  for (const L of VO) ev(L.t, 'vo', { id: L.id });
  return E;
}

window.DUR = T.dur;
window.render = t => { render(t); };
window.TEXTS = t => render(t);
init().catch(e => { console.error(e); throw e; });
