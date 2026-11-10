// Our own flat 2D cartoon cast (riflemen, officer, townsfolk, kid, parent) + 2D effects, drawn on a canvas.
// Construction v2 (characters.md, our own cast): superellipse heads (pointed crown 1.75 / full jaw 2.3, chin taper,
// seeded side bulge + tilt), bean torsos, single-stroke limbs with ink-dot hands, a thick-thin plum outline weighted
// away from the light, soft painted crescents, deadpan lidded eyes, no blush, no catchlights.
// Design space 600 x 1000 units (soles at y = 975); the canvas transform scales it.
export const INK = "#241726";
export const SKIN = "#ffe2c2";
const WHITE = "#ffffff";
const MOUTH = "#5a1e28";
const TONGUE = "#e86e78";
type C3 = [number, number, number];
const SH_SKIN: C3 = [0.96, 0.86, 0.84]; // measured shadow/lit ratio on skin heads
const SH_CLOTH: C3 = [0.64, 0.66, 0.74]; // torsos: lit side -> far side ~0.65
const SH_FELT: C3 = [0.62, 0.62, 0.7];

export type Build = "adult" | "stout" | "kid";
export type Outfit = {
  jacket: string; pants: string; boots: string; hat?: string | null; belt?: string | null; buttons?: string; rifle?: boolean;
  sash?: string; sword?: boolean; moustache?: string; skin?: string; head?: number; cap?: string; hair?: string; dress?: string;
  /** Pisan surcoat cross colour; a spear instead of the rifle; hi-vis bands across the torso */
  cross?: string; spear?: boolean; vest?: string;
  /** cleanroom: a face mask over the mouth (colour) */
  mask?: string;
  build?: Build;
  /** 1925: a tie down the shirt front (colour), the hat colour for fedora / bowler / cloche */
  tie?: string; hatCol?: string;
  /** 1932: a war medal on the chest (ribbon colour), braces over the shirt, a Sam Browne belt across the chest */
  medal?: string; braces?: string; sam?: string;
};
type P2 = [number, number];

const rad = (d: number) => (d * Math.PI) / 180;
const clamp = (x: number, a: number, b: number) => Math.max(a, Math.min(b, x));
export const mul = (c: string, m: C3) => {
  const n = parseInt(c.slice(1), 16);
  const ch = (v: number, k: number) => Math.min(255, Math.round(v * k)).toString(16).padStart(2, "0");
  return `#${ch((n >> 16) & 255, m[0])}${ch((n >> 8) & 255, m[1])}${ch(n & 255, m[2])}`;
};
export const shade = (c: string, k: number) => mul(c, [k, k, k]);
export const mix = (a: string, b: string, t: number) => {
  const A = parseInt(a.slice(1), 16), B = parseInt(b.slice(1), 16);
  const ch = (s: number) => Math.round(((A >> s) & 255) * (1 - t) + ((B >> s) & 255) * t).toString(16).padStart(2, "0");
  return `#${ch(16)}${ch(8)}${ch(0)}`;
};
/** deterministic per-character random in [0, 1) */
const rnd = (seed: number, k: number) => { const x = Math.sin(seed * 127.1 + k * 311.7) * 43758.5453; return x - Math.floor(x); };
const rotPts = (pts: P2[], a: number, cx: number, cy: number): P2[] =>
  pts.map(([x, y]) => [cx + (x - cx) * Math.cos(a) - (y - cy) * Math.sin(a), cy + (x - cx) * Math.sin(a) + (y - cy) * Math.cos(a)]);
const rotAbout = (q: P2, a: number, c: P2): P2 => rotPts([q], a, c[0], c[1])[0];
const lerp2 = (a: P2, b: P2, t: number): P2 => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];
/** smooth curve from a through (near) k to b, as a polyline */
const curve = (a: P2, k: P2, b: P2, n = 10): P2[] => {
  const c: P2 = [2 * k[0] - (a[0] + b[0]) / 2, 2 * k[1] - (a[1] + b[1]) / 2], out: P2[] = [];
  for (let i = 0; i <= n; i++) {
    const t = i / n, s = 1 - t;
    out.push([s * s * a[0] + 2 * s * t * c[0] + t * t * b[0], s * s * a[1] + 2 * s * t * c[1] + t * t * b[1]]);
  }
  return out;
};

export const RIFLEMAN: Outfit = { jacket: "#357650", pants: "#3d4440", boots: INK, hat: "shako", belt: "#f1efe6", buttons: "#d9dde0", rifle: true };
export const OFFICER: Outfit = { ...RIFLEMAN, hat: "shako_tall", buttons: "#e8c45a", sash: "#c0353a", sword: true, moustache: "#4a3020", rifle: false, belt: null, build: "stout" };
export const KID: Outfit = { jacket: "#f08a2c", pants: "#3b5b9a", boots: "#f4f1ea", hat: "cap", cap: "#e2453c", build: "kid" };
export const PARENT: Outfit = { jacket: "#7b5ac9", pants: "#3b3f52", boots: "#5a3b2a", hat: "hair", hair: "#5a3b2a" };
export const SKINS = [SKIN, "#f5c9a0", "#ecd0b6", "#c99067"];
// ---- the Pisa cast (our own): masons of 1173 / 1272, Pisan foot soldiers, 1990s engineers, today's tourists ----
export const mason = (v = 0): Outfit => {
  const tunics = ["#b5653f", "#8c6a3f", "#6f7f4a", "#9a5a4a"], caps = ["#d9c49a", "#a8714a", "#e6dcc8", "#7a5a3a"];
  const o: Outfit = { jacket: tunics[v % 4], pants: "#5a4a3a", boots: "#4a3426", hat: "cap", cap: caps[v % 4], buttons: shade(tunics[v % 4], 0.75), skin: SKINS[v % 4] };
  if (v % 4 === 2) o.moustache = "#4a3426";
  return o;
};
export const pisan = (v = 0): Outfit => {
  const o: Outfit = { jacket: "#b8332e", pants: "#4a4552", boots: "#3a2a22", hat: "helm", cross: "#f4f1ea", spear: true, buttons: "#b8332e", skin: SKINS[v % 4] };
  if (v % 4 === 1) o.moustache = "#4a3426";
  if (v % 4 === 3) o.moustache = "#2a201a";
  return o;
};
export const engineer = (v = 0): Outfit => ({
  jacket: ["#f08a2c", "#3f6fb5", "#f08a2c", "#5d7a3a"][v % 4], pants: "#3b3f52", boots: "#4a3426", hat: "hardhat", cap: ["#f2c230", "#f4f1ea", "#f2c230", "#f2c230"][v % 4],
  vest: "#e9eef2", buttons: "#3b3f52", skin: SKINS[(v + 1) % 4], moustache: v % 3 === 1 ? "#5a3b2a" : undefined,
});
export const tourist = (v = 0): Outfit => {
  const tops = ["#3fa7b5", "#e2453c", "#f2c230", "#7b5ac9", "#5d9a3a", "#f08a2c"];
  const o: Outfit = { jacket: tops[v % 6], pants: ["#3b5b9a", "#e9dcc2", "#3b3f52"][v % 3], boots: "#f4f1ea", skin: SKINS[v % 4], buttons: tops[v % 6] };
  return v % 3 === 0 ? { ...o, hat: "sunhat" } : v % 3 === 1 ? { ...o, hat: "cap", cap: ["#e2453c", "#3f6fb5"][v % 2] } : { ...o, hat: "hair", hair: ["#5a3b2a", "#2a1c18", "#c9925a"][v % 3] };
};

// ---- the escalator cast (our own): 1898 shoppers + shop staff, today's riders, the inspector, the 1950 executive ----
export const WAITER: Outfit = { jacket: "#24222c", pants: "#24222c", boots: INK, hat: "hair", hair: "#2a1c18", buttons: "#f4f1ea", moustache: "#2a1c18", sash: "#f4f1ea" };
/** cleanroom "bunny suit": white coverall, hood, mask; v varies boots/gloves/mask tint so workers read apart */
export const bunny = (v = 0): Outfit => ({
  jacket: "#eef2f8", pants: "#e3e8f1", boots: ["#8fb8e6", "#f2c230", "#9ad1a8", "#e89ab0"][v % 4], hat: "hood", cap: "#f4f6fb",
  mask: ["#cfe4f7", "#f4f6fb", "#d9f0e0", "#f7dbe4"][v % 4], buttons: "#b8c4d6", skin: SKINS[v % 4], build: v % 5 === 3 ? "stout" : "adult",
});
/** 1947 lab scientists: white lab coat over a tie, hair; v = 1 has the moustache (Brattain), v = 0 thinning hair (Bardeen) */
export const scientist = (v = 0): Outfit => ({
  jacket: "#f2efe6", pants: "#4a4552", boots: "#3a2a22", hat: "hair", hair: ["#7a6a5a", "#3a2a22", "#5a3b2a"][v % 3], buttons: "#c9c3b5",
  moustache: v % 3 === 1 ? "#3a2a22" : undefined, sash: ["#3f6fb5", "#8c3b4a", "#3a6a4a"][v % 3], skin: ["#f2d2b8", "#ecd0b6", "#f5c9a0"][v % 3],
});
export const reporter = (v = 0): Outfit => ({
  jacket: ["#6a5a4a", "#4f5566", "#7a6040"][v % 3], pants: "#3f4454", boots: "#3a2a22", hat: "tophat", buttons: "#d9dde0", skin: SKINS[v % 4],
});
export const MANAGER: Outfit = { jacket: "#3b3f52", pants: "#2f3242", boots: INK, hat: "tophat", buttons: "#e8c45a", moustache: "#6a4a32", build: "stout", sash: "#8c3b4a" };
export const EXEC: Outfit = { jacket: "#4f5566", pants: "#3f4454", boots: "#3a2a22", hat: "hair", hair: "#5a3b2a", buttons: "#d9dde0", sash: "#c0353a", skin: "#f5c9a0" };
export const rider = (v = 0): Outfit => {
  const tops = ["#3fa7b5", "#e2453c", "#f2c230", "#7b5ac9", "#5d9a3a", "#f08a2c", "#3f6fb5", "#c25a7a"];
  const o: Outfit = { jacket: tops[v % 8], pants: ["#3b5b9a", "#e9dcc2", "#3b3f52", "#5a4a3a"][v % 4], boots: ["#f4f1ea", "#3a2a22", "#e2453c"][v % 3], skin: SKINS[v % 4], buttons: tops[v % 8] };
  if (v % 5 === 4) return { ...o, hat: "bonnet", dress: ["#d9a441", "#5a8fc2"][v % 2] };
  return v % 3 === 0 ? { ...o, hat: "cap", cap: ["#e2453c", "#3f6fb5", "#f2c230"][v % 3] } : { ...o, hat: "hair", hair: ["#5a3b2a", "#2a1c18", "#c9925a", "#8a4a2a"][v % 4] };
};

export const soldier = (v = 0, extra: Partial<Outfit> = {}): Outfit => {
  const o: Outfit = { ...RIFLEMAN, skin: SKINS[v % 4] };
  if (v % 4 === 1) o.moustache = "#4a3426";
  if (v % 4 === 3) o.moustache = "#2a201a";
  return { ...o, ...extra };
};

// ---- the Eiffel cast (our own): the con man, the dealers, the wife, clerks, Parisians ----
export const CON: Outfit = { jacket: "#2b3048", pants: "#2b3048", boots: INK, hat: "fedora", hatCol: "#3a3346", tie: "#c0353a", buttons: "#d9dde0", moustache: "#2a1c18", skin: SKIN };
export const POISSON: Outfit = { jacket: "#9a7048", pants: "#6a5040", boots: "#3a2a22", hat: "bowler", hatCol: "#2e2a2a", tie: "#3f6fb5", buttons: "#e8c45a", moustache: "#5a3b2a", build: "stout", skin: "#f5c9a0" };
export const WIFE: Outfit = { jacket: "#7b3a5a", pants: "#3b3f52", boots: "#3a2a22", hat: "cloche", hatCol: "#c25a7a", dress: "#7b3a5a", skin: "#ecd0b6" };
export const dealer = (v = 0): Outfit => {
  const suits = ["#5d6a5a", "#6a5a6e", "#4f5566", "#7a6040"], hats = ["tophat", "bowler", "bowler", "tophat"];
  return { jacket: suits[v % 4], pants: shade(suits[v % 4], 0.8), boots: "#3a2a22", hat: hats[v % 4], hatCol: "#2e2a36", tie: ["#8c3b4a", "#3a6a4a", "#e8c45a", "#3f6fb5"][v % 4],
    buttons: "#d9dde0", moustache: v % 2 ? "#4a3426" : "#8a7a6a", build: v % 2 ? "stout" : "adult", skin: SKINS[(v + 1) % 4] };
};
export const clerk = (v = 0): Outfit => ({ jacket: ["#3a3d47", "#4a4552", "#3b3f52"][v % 3], pants: "#2f3242", boots: INK, hat: "kepi", hatCol: ["#3a3d47", "#4a4552", "#3b3f52"][v % 3], hair: ["#2a1c18", "#7a6a5a", "#5a3b2a"][v % 3],
  tie: "#2e2a36", buttons: "#c9c3b5", moustache: "#2a1c18", skin: SKINS[v % 4] });
export const parisian = (v = 0): Outfit => {
  const coats = ["#3f6fb5", "#8c3b4a", "#5d7a3a", "#b5653f", "#2f5f6a", "#7b5ac9"];
  const o: Outfit = { jacket: coats[v % 6], pants: "#3b3f52", boots: "#4a3426", skin: SKINS[v % 4], tie: v % 3 ? "#e8c45a" : undefined };
  return v % 2 ? { ...o, hat: "cloche", hatCol: ["#d9a441", "#c25a7a", "#5a8fc2"][v % 3], dress: coats[(v + 2) % 6] } : { ...o, hat: v % 4 ? "bowler" : "fedora", hatCol: "#3a3346", moustache: v % 4 === 2 ? "#4a3426" : undefined };
};
export const GENDARME: Outfit = { jacket: "#1f2a44", pants: "#1f2a44", boots: INK, hat: "kepi", hatCol: "#1f2a44", buttons: "#e8c45a", moustache: "#3a2a22", skin: "#f5c9a0", build: "stout" };
export const PAINTER: Outfit = { jacket: "#f2efe6", pants: "#e3e0d6", boots: "#5a3b2a", hat: "cap", cap: "#f2efe6", buttons: "#c9c3b5", skin: "#f5c9a0", moustache: "#5a3b2a" };

// ---------------- 1932: the Emu War cast ----------------
const KHAKI = "#8f7c4c";
export const MAJOR: Outfit = { jacket: KHAKI, pants: KHAKI, boots: "#5a3a22", hat: "peaked", hatCol: KHAKI, buttons: "#e8c45a", moustache: "#5a3b2a", sam: "#6a4426", build: "stout", skin: "#f5c9a0" };
export const gunner = (v = 0): Outfit => ({ jacket: KHAKI, pants: KHAKI, boots: "#5a3a22", hat: "slouch", hatCol: KHAKI, buttons: "#c9a24a", belt: null, sam: "#7a5a36",
  moustache: v === 1 ? "#7a4a2a" : undefined, skin: ["#ffe2c2", "#f5c9a0"][v % 2] });
export const farmer = (v = 0): Outfit => ({ jacket: ["#5b7fa8", "#b8a27a", "#8a5a48", "#6f8a5a"][v % 4], pants: ["#5a4a3a", "#4a4f5a", "#6a5a44", "#4a4038"][v % 4], boots: "#4a3020",
  hat: "akubra", hatCol: ["#7a5a3a", "#9a7a52", "#5f4a38", "#8a6a44"][v % 4], braces: ["#7a3a2a", "#3a3a4a", "#4a3a2a", "#6a2a2a"][v % 4], medal: v % 2 ? undefined : "#c0353a",
  moustache: ["#8a5a3a", undefined, "#c9c3b5", "#5a3b2a"][v % 4], skin: ["#f5c9a0", "#ecb88e", "#ffe2c2", "#e9b48a"][v % 4], build: v === 2 ? "stout" : "adult" });
export const MINISTER: Outfit = { jacket: "#2e3240", pants: "#2e3240", boots: INK, hat: "hair", hair: "#d9d6cf", tie: "#7a2a3a", buttons: "#d9dde0", moustache: "#e9e6df", build: "stout", skin: "#f5c9a0" };
export const CAMERAMAN: Outfit = { jacket: "#9a7a5a", pants: "#4a4038", boots: "#3a2a22", hat: "cap", cap: "#6a6a5a", tie: "#3f6a4a", skin: "#ffe2c2" };
export const mp = (v = 0): Outfit => ({ jacket: ["#2e3240", "#3a3330", "#33384a", "#4a4038"][v % 4], pants: "#2e3240", boots: INK, hat: "hair", hair: ["#d9d6cf", "#5a3b2a", "#9a9590", "#2a1c18"][v % 4],
  tie: ["#7a2a3a", "#3f5f8a", "#5a6a3a", "#8a6a2a"][v % 4], moustache: v % 2 ? "#6a5a4a" : undefined, build: v % 3 === 0 ? "stout" : "adult", skin: SKINS[v % 4] });

export const townsfolk = (v = 0): Outfit => {
  const coats = ["#3f6fb5", "#8c3b4a", "#5d7a3a", "#b5653f", "#2f5f6a", "#7b5ac9"];
  const o: Outfit = { jacket: coats[v % 6], pants: "#3b3f52", boots: "#4a3426", skin: SKINS[v % 4] };
  return v % 2 ? { ...o, hat: "bonnet", dress: ["#d9a441", "#c25a7a", "#5a8fc2"][v % 3] } : { ...o, hat: "tophat" };
};

export class Pen {
  g: CanvasRenderingContext2D;
  ol = 12;
  /** [angle, cx, cy] rotation about (cx, cy), optional post-translation [.., dx, dy] */
  rot: number[] | null = null;
  constructor(g: CanvasRenderingContext2D) { this.g = g; }
  P(x: number, y: number): P2 {
    if (!this.rot) return [x, y];
    const r = this.rot, a = r[0], cx = r[1], cy = r[2], dx = r.length > 3 ? r[3] : 0, dy = r.length > 4 ? r[4] : 0, c = Math.cos(a), s = Math.sin(a);
    return [cx + (x - cx) * c - (y - cy) * s + dx, cy + (x - cx) * s + (y - cy) * c + dy];
  }
  path(pts: P2[], close: boolean) {
    const g = this.g;
    g.beginPath();
    pts.forEach((p, i) => { const [x, y] = this.P(p[0], p[1]); if (i) g.lineTo(x, y); else g.moveTo(x, y); });
    if (close) g.closePath();
  }
  /** filled shape with an ink outline; fill=null draws the outline only */
  poly(pts: P2[], fill: string | null, ol?: number) {
    const g = this.g, w = ol ?? this.ol;
    this.path(pts, true);
    if (fill) { g.fillStyle = fill; g.fill(); }
    if (w) { g.lineWidth = w; g.strokeStyle = INK; g.lineJoin = "round"; g.stroke(); }
  }
  ell(cx: number, cy: number, rx: number, ry: number, fill: string | null, ol?: number, a0 = 0, a1 = 360, rot = 0) {
    this.poly(ellPts(cx, cy, rx, ry, a0, a1, rot), fill, ol);
  }
  /** thick round-capped limb with an ink rim (effects, rope) */
  line(pts: P2[], fill: string, w: number, ink = true) {
    const g = this.g;
    g.lineCap = "round"; g.lineJoin = "round";
    if (ink) { this.path(pts, false); g.strokeStyle = INK; g.lineWidth = w + 2 * this.ol * 0.9; g.stroke(); }
    this.path(pts, false); g.strokeStyle = fill; g.lineWidth = w; g.stroke();
  }
  stroke(pts: P2[], w: number, fill = INK) {
    const g = this.g;
    g.lineCap = "round"; g.lineJoin = "round";
    this.path(pts, false); g.strokeStyle = fill; g.lineWidth = w; g.stroke();
  }
  arc(cx: number, cy: number, rx: number, ry: number, a0: number, a1: number, w: number, fill = INK) {
    const pts: P2[] = [];
    for (let i = 0; i <= 24; i++) pts.push([cx + rx * Math.cos(rad(a0 + ((a1 - a0) * i) / 24)), cy + ry * Math.sin(rad(a0 + ((a1 - a0) * i) / 24))]);
    this.stroke(pts, w, fill);
  }
  dot(cx: number, cy: number, r: number, fill = INK) {
    const [x, y] = this.P(cx, cy);
    this.g.beginPath(); this.g.arc(x, y, r, 0, Math.PI * 2); this.g.fillStyle = fill; this.g.fill();
  }
  /** draw with a closed shape as clip */
  clip(pts: P2[], fn: () => void) { const g = this.g; g.save(); this.path(pts, true); g.clip(); fn(); g.restore(); }
  /** flat fill + soft crescent on the side away from the light (light = canvas angle the light comes FROM).
   *  Radial ramp centred `shift` R toward the light: flat out to ~0.6 R on the far side, full shadow by ~0.8 R. */
  shadedFill(pts: P2[], base: string, shadow: string, light: number, R: number, shift = 0.45, r0 = 1.05, r1 = 1.25) {
    const g = this.g, n = pts.length;
    let cx = 0, cy = 0;
    for (const [x, y] of pts) { cx += x / n; cy += y / n; }
    const [gx, gy] = this.P(cx + Math.cos(light) * shift * R, cy + Math.sin(light) * shift * R);
    const gr = g.createRadialGradient(gx, gy, 0, gx, gy, r1 * R);
    gr.addColorStop(0, base); gr.addColorStop(r0 / r1, base); gr.addColorStop(1, shadow);
    this.path(pts, true); g.fillStyle = gr; g.fill();
  }
  /** broad gradient across a shape along the light: lit edge = base, far edge = shadow (torsos, coats) */
  gradFill(pts: P2[], base: string, shadow: string, light: number, flat = 0.22) {
    const g = this.g, dx = Math.cos(light), dy = Math.sin(light), n = pts.length;
    let cx = 0, cy = 0, lo = Infinity, hi = -Infinity;
    for (const [x, y] of pts) { cx += x / n; cy += y / n; const d = x * dx + y * dy; lo = Math.min(lo, d); hi = Math.max(hi, d); }
    const dc = cx * dx + cy * dy;
    const [ax, ay] = this.P(cx + dx * (hi - dc), cy + dy * (hi - dc)), [bx, by] = this.P(cx + dx * (lo - dc), cy + dy * (lo - dc));
    const gr = g.createLinearGradient(ax, ay, bx, by);
    gr.addColorStop(0, base); gr.addColorStop(flat, base); gr.addColorStop(1, shadow);
    this.path(pts, true); g.fillStyle = gr; g.fill();
  }
  /** thick-thin ink ring: w(θ) = w0 (1 + k cos(θ − thick)), θ from the contour centroid (canvas angles) */
  inkRing(pts: P2[], w0: number, thick: number, k = 0.45, col = INK) {
    const n = pts.length;
    let cx = 0, cy = 0;
    for (const [x, y] of pts) { cx += x / n; cy += y / n; }
    const out: P2[] = [], inn: P2[] = [];
    pts.forEach((q, i) => {
      const a = pts[(i + n - 1) % n], b = pts[(i + 1) % n];
      let nx = b[1] - a[1], ny = a[0] - b[0]; // outward normal for clockwise-on-screen contours
      const l = Math.hypot(nx, ny) || 1; nx /= l; ny /= l;
      const h = 0.5 * w0 * (1 + k * Math.cos(Math.atan2(q[1] - cy, q[0] - cx) - thick));
      out.push([q[0] + nx * h, q[1] + ny * h]); inn.push([q[0] - nx * h, q[1] - ny * h]);
    });
    const g = this.g;
    const trace = (r: P2[]) => { r.forEach(([x0, y0], i) => { const [x, y] = this.P(x0, y0); if (i) g.lineTo(x, y); else g.moveTo(x, y); }); g.closePath(); };
    g.beginPath(); trace(out); trace(inn.reverse());
    g.fillStyle = col; g.fill("evenodd");
  }
  /** flat strap with a thin ink rim (cross belts, sash, rifle, handles) */
  band(pts: P2[], fill: string, w: number, rim: number, cap: CanvasLineCap = "butt") {
    const g = this.g; g.lineCap = cap; g.lineJoin = "round";
    this.path(pts, false); g.strokeStyle = INK; g.lineWidth = w + 2 * rim; g.stroke();
    this.path(pts, false); g.strokeStyle = fill; g.lineWidth = w; g.stroke();
    g.lineCap = "round";
  }
}

const ellPts = (cx: number, cy: number, rx: number, ry: number, a0 = 0, a1 = 360, rot = 0, n = 48): P2[] => {
  const r = rad(rot), pts: P2[] = [];
  for (let i = 0; i <= n; i++) {
    const a = rad(a0 + ((a1 - a0) * i) / n), x = rx * Math.cos(a), y = ry * Math.sin(a);
    pts.push([cx + x * Math.cos(r) - y * Math.sin(r), cy + x * Math.sin(r) + y * Math.cos(r)]);
  }
  return pts;
};

const rrect = (x0: number, y0: number, x1: number, y1: number, r: number, n = 8): P2[] => {
  const pts: P2[] = [];
  for (const [cx, cy, a] of [[x1 - r, y0 + r, -90], [x1 - r, y1 - r, 0], [x0 + r, y1 - r, 90], [x0 + r, y0 + r, 180]])
    for (let i = 0; i <= n; i++) pts.push([cx + r * Math.cos(rad(a + (90 * i) / n)), cy + r * Math.sin(rad(a + (90 * i) / n))]);
  return pts;
};

/** tapered stroke, thick end at a: brows, moustache halves */
const taper = (p: Pen, a: P2, b: P2, wa: number, wb: number, col = INK) => {
  const dx = b[0] - a[0], dy = b[1] - a[1], l = Math.hypot(dx, dy) || 1, nx = -dy / l, ny = dx / l;
  p.poly([[a[0] + nx * wa / 2, a[1] + ny * wa / 2], [b[0] + nx * wb / 2, b[1] + ny * wb / 2],
    [b[0] - nx * wb / 2, b[1] - ny * wb / 2], [a[0] - nx * wa / 2, a[1] - ny * wa / 2]], col, 0);
  p.dot(a[0], a[1], wa / 2, col); p.dot(b[0], b[1], wb / 2, col);
};

// ---------------- contours ----------------
export type Blob = { a: number; b: number; nTop: number; nBot: number; egg: number; asym: number; rot: number; noise: number; seed: number };

/** superellipse "bean": separate crown / jaw exponents, egg taper (neg = narrower chin), one-side bulge, soft noise.
 *  Points run right -> down -> left -> up (clockwise on screen). */
export const blobPts = (cx: number, cy: number, B: Blob, n = 72): P2[] => {
  const ph = [rnd(B.seed, 11), rnd(B.seed, 12), rnd(B.seed, 13)].map((v) => v * Math.PI * 2);
  const pts: P2[] = [];
  for (let i = 0; i < n; i++) {
    const t = (i / n) * Math.PI * 2, c = Math.cos(t), s = Math.sin(t), e = 2 / (s < 0 ? B.nTop : B.nBot);
    let X = Math.sign(c) * Math.abs(c) ** e;
    const Y = Math.sign(s) * Math.abs(s) ** e;
    X *= (1 + B.egg * Y) * (1 + B.asym * Math.sign(X));
    const r = 1 + B.noise * (Math.cos(2 * t + ph[0]) + 0.7 * Math.cos(3 * t + ph[1]) + 0.5 * Math.cos(4 * t + ph[2]));
    const x = B.a * X * r, y = B.b * Y * r;
    pts.push([cx + x * Math.cos(B.rot) - y * Math.sin(B.rot), cy + x * Math.sin(B.rot) + y * Math.cos(B.rot)]);
  }
  return pts;
};

/** measured head: H/W 0.94, slightly pointed crown (1.75), fuller jaw (2.3), chin taper -0.12, 8 % bulge to the facing side */
export const headBlob = (seed: number, a = 118, facing = 0): Blob => ({
  a, b: a * (0.94 + 0.08 * (rnd(seed, 1) - 0.5)),
  nTop: 1.75 + 0.3 * (rnd(seed, 2) - 0.5), nBot: 2.3 + 0.3 * (rnd(seed, 3) - 0.5),
  egg: -0.12 + 0.06 * (rnd(seed, 4) - 0.5),
  asym: (0.06 + 0.04 * rnd(seed, 5)) * (facing || (rnd(seed, 6) < 0.5 ? -1 : 1)),
  rot: rad(8 * (rnd(seed, 7) - 0.5)), noise: 0.008, seed,
});

/** thickest outline direction: away from the light, pulled toward the ground (64 deg measured for upper-left light) */
export const thickAngle = (light: number) => Math.atan2(-Math.sin(light) + 0.8, -Math.cos(light));
const DEF_LIGHT = rad(-120);

// ---------------- faces ----------------
export type Expr = "neutral" | "stern" | "grin" | "laugh" | "whistle" | "nervous" | "shock" | "relief" | "relief_open" | "dazed"
  | "pained" | "smile" | "smile_closed" | "lick";
type EyeK = "dot" | "small" | "lid" | "slit" | "happy" | "dash" | "squeeze" | "shock" | "shockHalf" | "spiral";
type MouthK = "dash" | "frown" | "smirk" | "smile" | "smileWide" | "grin" | "laugh" | "o" | "O" | "wave" | "teeth" | "lick";
/** eyes [back, front], brows [inner, outer] offsets in u (+ = down), mouth kind */
const FACE: Record<Expr, { eye: [EyeK, EyeK]; brow: [number, number]; mouth: MouthK }> = {
  neutral: { eye: ["lid", "lid"], brow: [0, -1], mouth: "dash" },
  stern: { eye: ["lid", "lid"], brow: [3, -2], mouth: "frown" },
  grin: { eye: ["happy", "happy"], brow: [-3, -3], mouth: "grin" },
  laugh: { eye: ["squeeze", "squeeze"], brow: [-4, -4], mouth: "laugh" },
  whistle: { eye: ["dash", "dash"], brow: [-2, -4], mouth: "o" },
  nervous: { eye: ["small", "small"], brow: [-3, 2], mouth: "wave" },
  shock: { eye: ["shock", "shock"], brow: [-7, -6], mouth: "O" },
  relief: { eye: ["happy", "happy"], brow: [-2, 1], mouth: "smileWide" },
  relief_open: { eye: ["happy", "happy"], brow: [-2, 1], mouth: "grin" },
  dazed: { eye: ["spiral", "spiral"], brow: [-3, 2], mouth: "wave" },
  pained: { eye: ["squeeze", "lid"], brow: [-3, 2], mouth: "teeth" },
  smile: { eye: ["dot", "dot"], brow: [0, -1], mouth: "smirk" },
  smile_closed: { eye: ["happy", "happy"], brow: [0, -1], mouth: "smile" },
  lick: { eye: ["dot", "dot"], brow: [0, -1], mouth: "lick" },
};
const halfLid = (k: EyeK): EyeK => (k === "dot" || k === "small" ? "lid" : k === "lid" ? "slit" : k === "shock" ? "shockHalf" : k);
const eyeKind = (k: EyeK, lid: number): EyeK =>
  lid >= 1 && k !== "happy" && k !== "squeeze" && k !== "spiral" ? "dash" : lid > 0 ? halfLid(k) : k;
const lidOf = (b: boolean | number | undefined) => (b === true ? 1 : Number(b) || 0);

const eye = (p: Pen, kind: EyeK, x: number, ey: number, u: number, side: number, look: number, skin: string) => {
  const lx = x + look * 3 * u, lw = 3.8 * u;
  switch (kind) {
    case "dot": p.ell(lx, ey, 3.8 * u, 5.5 * u, INK, 0); break;
    case "small": p.ell(lx, ey, 3 * u, 4.4 * u, INK, 0); break;
    case "lid": p.ell(lx, ey - u, 7 * u, 6 * u, INK, 0, 0, 180); p.stroke([[x - 9 * u, ey - u], [x + 9 * u, ey - u]], lw); break;
    case "slit": p.ell(lx, ey, 7 * u, 2.6 * u, INK, 0, 0, 180); p.stroke([[x - 9 * u, ey], [x + 9 * u, ey]], lw); break;
    case "happy": p.arc(x, ey + 3 * u, 8 * u, 6 * u, 200, 340, lw); break;
    case "dash": p.stroke([[x - 8.5 * u, ey], [x + 8.5 * u, ey]], lw); break;
    case "squeeze": p.stroke([[x + 6 * u * side, ey - 5 * u], [x - 6 * u * side, ey], [x + 6 * u * side, ey + 5 * u]], lw); break;
    case "shock": case "shockHalf":
      p.ell(x, ey, 11 * u, 11 * u, WHITE, 2.6 * u); p.dot(lx - side * 1.5 * u, ey + 1.5 * u, 3 * u);
      if (kind === "shockHalf") { p.ell(x, ey, 11 * u, 11 * u, skin, 0, 180, 360); p.stroke([[x - 11 * u, ey], [x + 11 * u, ey]], 2.6 * u); }
      break;
    default: {
      const s: P2[] = [];
      for (let t = 1; t < 15; t++) s.push([x + Math.cos(t * 0.9) * t * 0.55 * u, ey + Math.sin(t * 0.9) * t * 0.55 * u]);
      p.stroke(s, 2.4 * u);
    }
  }
};

/** open "D" mouth with a white teeth band (+ tongue) */
const dmouth = (p: Pen, mx: number, y: number, rx: number, ry: number, u: number, tongue = false) => {
  p.ell(mx, y, rx, ry, MOUTH, 0, 0, 180);
  p.clip([[mx - rx, y], [mx + rx, y], [mx + rx, y + 3 * u], [mx - rx, y + 3 * u]], () => p.ell(mx, y, rx, ry, WHITE, 0, 0, 180));
  if (tongue) p.ell(mx + 2 * u, y + 0.62 * ry, 0.4 * rx, 0.28 * ry, TONGUE, 0);
  p.ell(mx, y, rx, ry, null, 3 * u, 0, 180);
};

const mouth = (p: Pen, kind: MouthK, mx: number, my: number, u: number, k = 1) => {
  const mw = 4 * u;
  switch (kind) {
    case "dash": p.stroke([[mx - 5.5 * u * k, my], [mx + 5.5 * u * k, my - 0.8 * u]], mw); break;
    case "frown": p.arc(mx, my + 3 * u, 6.5 * u * k, 3.5 * u, 200, 340, mw); break;
    case "smirk": p.arc(mx + u, my - 3 * u, 7 * u * k, 4 * u, 10, 150, mw); break;
    case "smile": p.arc(mx, my - 3 * u, 8 * u * k, 4.5 * u, 20, 160, mw); break;
    case "smileWide": p.arc(mx, my - 4 * u, 11 * u * k, 6 * u, 15, 165, mw); break;
    case "grin": dmouth(p, mx, my - u, 12 * u * k, 8 * u, u); break;
    case "laugh": dmouth(p, mx, my, 16 * u * k, 11 * u, u, true); break;
    case "o": p.ell(mx + 4 * u, my, 3.5 * u, 4 * u, MOUTH, 2.8 * u); break;
    case "O": p.ell(mx, my + 2 * u, 9 * u * k, 11 * u, MOUTH, 3.2 * u); break;
    case "wave": { const s: P2[] = []; for (let i = 0; i <= 12; i++) s.push([mx - 9 * u * k + i * 1.5 * u * k, my + 1.5 * u * Math.sin(i * 1.3)]); p.stroke(s, 3 * u); break; }
    case "teeth":
      p.poly([[mx - 12 * u * k, my - 4 * u], [mx + 12 * u * k, my - 4 * u], [mx + 11 * u * k, my + 4 * u], [mx - 11 * u * k, my + 4 * u]], WHITE, 3 * u);
      for (const j of [-1, 0, 1]) p.stroke([[mx + j * 6 * u * k, my - 4 * u], [mx + j * 6 * u * k, my + 4 * u]], 1.5 * u);
      break;
    case "lick": p.arc(mx, my - 3 * u, 8 * u * k, 4.5 * u, 20, 160, mw); p.ell(mx + 6 * u * k, my + 3 * u, 3.6 * u, 4.6 * u, TONGUE, 2.4 * u); break;
  }
};

/** face v2 (front / 3-4). u = 1 % of the head path width W. Eyes 26u apart on the centre line, brows 20u up, mouth 20u
 *  down, everything slid toward the facing side. No blush, no catchlights. */
const faceFront = (p: Pen, cx: number, cy: number, W: number, expr: Expr, facing: number, look: number, lid: number, brim: boolean,
  skin: string, moustache?: string, stout = false) => {
  const u = W / 100, F = FACE[expr], fx = cx + 7 * u * facing;
  const ex = (F.eye[0] === "shock" ? 12 : 13) * u, ey = cy;
  for (const side of [-1, 1]) {
    const x = fx + side * ex;
    const kind = eyeKind(F.eye[(facing ? side === facing : side > 0) ? 1 : 0], lid);
    eye(p, kind, x, ey, u, side, look, skin);
    const [dI, dO] = F.brow, by = ey - (brim ? 17 : 20) * u;
    if (kind === "shock" || kind === "shockHalf") p.arc(x, by - 6 * u, 9 * u, 3 * u, 200, 340, 4 * u);
    else taper(p, [x - side * 8.5 * u, by + dI * u], [x + side * 8.5 * u, by + dO * u], 5 * u, 2.5 * u);
  }
  const mx = cx + 8 * u * facing, my = cy + 20 * u;
  mouth(p, F.mouth, mx, my, u);
  if (moustache) for (const s of [-1, 1])
    taper(p, [mx + s * 1.5 * u, cy + 12.5 * u], [mx + s * (stout ? 19 : 15) * u, cy + (stout ? 10.5 : 15) * u], stout ? 5.5 * u : 4.5 * u, 1.6 * u, moustache);
  if (expr === "nervous") p.ell(cx + 40 * u * (facing || 1), cy - 22 * u, 3 * u, 5 * u, "#9fd4ff", 2 * u);
};

/** profile face (facing screen-right): one eye, brow, nose tick, mouth near the front edge; no skin bump nose, no ear */
const faceSide = (p: Pen, hx: number, hy: number, W: number, expr: Expr, lid: number, brim: boolean, skin: string, moustache?: string, stout = false) => {
  const u = W / 100, F = FACE[expr], ex = hx + 27 * u, ey = hy;
  const kind = eyeKind(F.eye[1], lid);
  eye(p, kind, ex, ey, u, 1, 0.6, skin);
  const by = ey - (brim ? 17 : 20) * u, [dI, dO] = F.brow;
  if (kind === "shock" || kind === "shockHalf") p.arc(ex, by - 6 * u, 9 * u, 3 * u, 200, 340, 4 * u);
  else taper(p, [ex + 8 * u, by + dI * u], [ex - 7 * u, by - u + dO * u], 5 * u, 2.5 * u);
  p.stroke([[hx + 44 * u, hy + 4 * u], [hx + 47.5 * u, hy + 9 * u], [hx + 43 * u, hy + 10 * u]], 3 * u);
  mouth(p, F.mouth, hx + 33 * u, hy + 21 * u, u, 0.62);
  if (moustache) taper(p, [hx + 41 * u, hy + 13.5 * u], [hx + 25 * u, hy + (stout ? 11.5 : 16) * u], stout ? 5.5 * u : 4.5 * u, 1.6 * u, moustache);
  if (expr === "nervous") p.ell(hx - 30 * u, hy - 24 * u, 3 * u, 5 * u, "#9fd4ff", 2 * u);
};

// ---------------- hats ----------------
const BONNET = "#e9cf8f", BONNET_BRIM = "#d6b46a", HOOD = "#f1f4fa";
/** parts of a hat that sit behind the head (bonnet) */
const hatBehind = (p: Pen, o: Outfit, H: Blob, cx: number, hc: number, light: number, thick: number, ow: number, side: boolean) => {
  if (o.hat === "hood") {
    const bb = blobPts(cx - (side ? 8 : 0) * (H.a / 50), hc - 0.02 * 2 * H.b, { ...H, a: H.a * 1.2, b: H.b * 1.16, asym: 0, egg: 0.02, seed: H.seed + 5 });
    p.shadedFill(bb, o.cap ?? HOOD, mul(o.cap ?? HOOD, SH_CLOTH), light, H.a * 1.2);
    p.inkRing(bb, ow * 0.85, thick);
    return;
  }
  if (o.hat !== "bonnet") return;
  const bb = blobPts(cx - (side ? 12 : 0) * (H.a / 50), hc - 0.07 * 2 * H.b, { ...H, a: H.a * 1.17, b: H.b * 1.13, asym: 0, egg: 0.04, seed: H.seed + 3 });
  p.shadedFill(bb, BONNET, mul(BONNET, SH_CLOTH), light, H.a * 1.17);
  p.inkRing(bb, ow * 0.85, thick);
};

const hatOn = (p: Pen, o: Outfit, hp: P2[], H: Blob, cx: number, hc: number, light: number, seed: number, facing: number, side: boolean) => {
  const W = 2 * H.a, HH = 2 * H.b, u = W / 100, crown = hc - H.b, ow = 0.85 * 5 * u;
  const a = H.rot + rad(4 * (rnd(seed, 20) - 0.5)); // tilt with the head, +-2 deg extra
  const R = (pts: P2[]) => rotPts(pts, a, cx, hc);
  const sag = (yb: number, wb: number): P2[] => {
    const base: P2[] = [];
    for (let i = 0; i <= 12; i++) { const t = i / 12; base.push([cx + wb * (2 * t - 1), yb + 3 * u * (1 - (2 * t - 1) ** 2)]); }
    return base;
  };
  if (o.hat === "shako" || o.hat === "shako_tall") {
    const tall = o.hat === "shako_tall", yb = crown + 0.25 * HH, ht = (tall ? 0.66 : 0.56) * HH, wb = 46 * u, wt = 52 * u;
    const body = R([...sag(yb, wb).reverse(), [cx - wt, yb - ht], [cx + wt, yb - ht]]);
    p.shadedFill(body, "#3a3d47", "#24262d", light, wt, 0.4);
    if (tall) p.clip(body, () => p.band(R([[cx - wt - 5 * u, yb - ht + 0.07 * HH], [cx + wt + 5 * u, yb - ht + 0.07 * HH]]), "#e8c45a", 0.06 * HH, 1.5 * u));
    p.poly(body, null, ow);
    const deg = (a * 180) / Math.PI;
    if (side) {
      p.poly(R([[cx + 36 * u, yb - 1 * u], [cx + 60 * u, yb + 8 * u], [cx + 34 * u, yb + 6 * u]]), "#16171b", 2.5 * u);
      const [tx, ty] = R([[cx + 24 * u, yb - ht - 6 * u]])[0];
      p.ell(tx, ty, 7 * u, 7 * u, "#2b7a4b", 2.5 * u);
    } else {
      const [px, py] = R([[cx + 3 * u * facing, yb + 3 * u]])[0];
      p.ell(px, py, 34 * u, 0.045 * HH, "#16171b", 2.5 * u, 0, 180, deg); // peak
      const [bx, by] = R([[cx, yb - 0.45 * ht]])[0];
      p.ell(bx, by, 7 * u, 6 * u, tall ? "#e8c45a" : "#c9ccd2", 2 * u, 0, 360, deg); // badge plate
      p.arc(bx, by, 3.5 * u, 2.8 * u, 200, 500, 1.6 * u);
      const [tx, ty] = R([[cx, yb - ht - 6 * u]])[0];
      p.ell(tx, ty, 7 * u, 7 * u, "#2b7a4b", 2.5 * u); // green tuft
    }
  } else if (o.hat === "cap" || o.hat === "hair") {
    const cut = crown + (o.hat === "cap" ? 0.3 : 0.42) * HH;
    const keep = (x: number, y: number) => y < cut || (side && o.hat === "hair" && x < cx - 6 * u && y < hc + 0.42 * H.b);
    // start the arc at the first kept point after a dropped one, so the kept run is contiguous and the cut closes it
    const n = hp.length, startIdx = Math.max(0, hp.findIndex(([x, y], i) => keep(x, y) && !keep(hp[(i + n - 1) % n][0], hp[(i + n - 1) % n][1])));
    const arc = [...hp.slice(startIdx), ...hp.slice(0, startIdx)].filter(([x, y]) => keep(x, y))
      .map(([x, y]) => [cx + (x - cx) * 1.03, hc + (y - hc) * 1.03] as P2);
    if (arc.length < 3) return;
    if (o.hat === "hair") { // scalloped lower edge
      const [x0, y0] = arc[arc.length - 1], [x1, y1] = arc[0];
      for (let i = 1; i < 6; i++) arc.push([x0 + ((x1 - x0) * i) / 6, y0 + ((y1 - y0) * i) / 6 + (i % 2 ? 4 * u : 0)]);
    }
    const col = o.hat === "cap" ? o.cap! : o.hair!;
    p.shadedFill(arc, col, mul(col, SH_FELT), light, H.a, 0.35);
    p.poly(arc, null, ow);
    if (o.hat === "hair") {
      const s = side ? -1 : facing || 1;
      p.stroke([[cx + s * 10 * u, cut - 30 * u], [cx + s * 2 * u, cut - 12 * u]], 1.2 * u);
    }
    if (o.hat === "cap") {
      const deg = (a * 180) / Math.PI;
      if (side) p.poly(R([[cx + 40 * u, cut - 2 * u], [cx + 74 * u, cut + 4 * u], [cx + 40 * u, cut + 6 * u]]), shade(col, 0.8), ow);
      else {
        const s = facing || (rnd(seed, 21) < 0.5 ? -1 : 1), [px, py] = R([[cx + s * 4 * u, cut + 1.5 * u]])[0];
        p.ell(px, py, 32 * u, 0.06 * HH, shade(col, 0.8), ow, 0, 180, deg);
      }
    }
  } else if (o.hat === "hood") {
    const cut = hc - 27 * u, col = o.cap ?? HOOD;
    const n = hp.length, keep = (y: number) => y < cut;
    const startIdx = Math.max(0, hp.findIndex(([, y], i) => keep(y) && !keep(hp[(i + n - 1) % n][1])));
    const arc = [...hp.slice(startIdx), ...hp.slice(0, startIdx)].filter(([, y]) => keep(y)).map(([x, y]) => [cx + (x - cx) * 1.04, hc + (y - hc) * 1.04] as P2);
    if (arc.length < 3) return;
    p.shadedFill(arc, col, mul(col, SH_CLOTH), light, H.a, 0.35);
    p.poly(arc, null, ow);
  } else if (o.hat === "kepi") { // a short stiff cap with a flat top, a band and a visor
    const col = o.hatCol ?? "#1f2a44", yb = crown + 0.26 * HH, ht = 0.42 * HH, wb = 0.36 * W, wt = 0.4 * W, deg = (a * 180) / Math.PI;
    const body = R([...sag(yb, wb).reverse(), [cx - wt, yb - ht], [cx + wt, yb - ht]]);
    p.shadedFill(body, col, mul(col, SH_FELT), light, wt, 0.4);
    p.clip(body, () => p.band(R([[cx - wt - 4 * u, yb - 0.08 * HH], [cx + wt + 4 * u, yb - 0.08 * HH]]), "#c0353a", 0.09 * HH, 0.8 * u));
    p.poly(body, null, ow);
    const [px, py] = R([[cx + 3 * u * facing, yb + 2 * u]])[0];
    p.ell(px, py, 30 * u, 0.05 * HH, "#16171b", 2.5 * u, 0, 180, deg);
    const [bx, by] = R([[cx, yb - 0.24 * HH]])[0]; p.ell(bx, by, 5 * u, 5 * u, "#e8c45a", 1.6 * u);
  } else if (o.hat === "slouch") {
    // the Australian slouch hat: a dented crown, a puggaree band, the left brim pinned up with the rising-sun badge
    const col = o.hatCol ?? "#8f7c4c", yb = crown + 0.25 * HH, deg = (a * 180) / Math.PI, s = side ? -1 : -1;
    const flap = R(side
      ? [[cx - 0.32 * W, yb + 0.02 * HH], [cx - 0.5 * W, yb - 0.2 * HH], [cx - 0.46 * W, yb - 0.52 * HH], [cx - 0.3 * W, yb - 0.48 * HH], [cx - 0.18 * W, yb - 0.1 * HH]]
      : [[cx + s * 0.22 * W, yb + 0.03 * HH], [cx + s * 0.6 * W, yb - 0.04 * HH], [cx + s * 0.66 * W, yb - 0.42 * HH], [cx + s * 0.44 * W, yb - 0.58 * HH], [cx + s * 0.26 * W, yb - 0.34 * HH]]);
    p.shadedFill(flap, col, mul(col, SH_FELT), light, 0.4 * W, 0.4); p.poly(flap, null, ow);
    const [gx, gy] = R([[cx + (side ? -0.38 * W : s * 0.46 * W), yb - (side ? 0.3 : 0.28) * HH]])[0];
    p.ell(gx, gy, 6 * u, 5 * u, "#e8c45a", 1.4 * u, 0, 360, deg);
    for (let k = 0; k < 7; k++) { const an = rad(180 + k * 30); p.stroke([[gx + 6 * u * Math.cos(an), gy + 5 * u * Math.sin(an)], [gx + 10 * u * Math.cos(an), gy + 9 * u * Math.sin(an)]], 1.4 * u, "#c9a24a"); }
    const [bx, by] = R([[cx + (side ? 0.12 * W : 0.14 * W), yb + 1 * u]])[0];
    p.ell(bx, by, (side ? 0.62 : 0.52) * W, 0.075 * HH, shade(col, 0.85), ow, 0, 360, deg);
    const wb = 0.4 * W, wt = 0.32 * W, ht = 0.46 * HH;
    const body = R([...sag(yb, wb).reverse(), [cx - wt, yb - ht], [cx - wt * 0.4, yb - ht - 0.05 * HH], [cx, yb - ht + 0.05 * HH], [cx + wt * 0.4, yb - ht - 0.05 * HH], [cx + wt, yb - ht]]);
    p.shadedFill(body, col, mul(col, SH_FELT), light, 0.4 * W, 0.4);
    p.clip(body, () => {
      p.band(R([[cx - 0.5 * W, yb - 0.09 * HH], [cx + 0.5 * W, yb - 0.09 * HH]]), "#c8b787", 0.12 * HH, 0.6 * u);
      for (const dy of [-0.05, -0.12]) p.stroke(R([[cx - 0.5 * W, yb + dy * HH], [cx + 0.5 * W, yb + dy * HH]]), 1 * u, shade("#c8b787", 0.8));
    });
    p.poly(body, null, ow);
  } else if (o.hat === "peaked") {
    // an officer's service cap: a stiff flat top wider than the head, a dark band, a leather peak, a gold badge
    const col = o.hatCol ?? "#8f7c4c", yb = crown + 0.27 * HH, deg = (a * 180) / Math.PI;
    const top = R([...sag(yb, 0.38 * W).reverse(), [cx - 0.56 * W, yb - 0.3 * HH], [cx - 0.3 * W, yb - 0.4 * HH], [cx + 0.3 * W, yb - 0.4 * HH], [cx + 0.56 * W, yb - 0.3 * HH]]);
    p.shadedFill(top, col, mul(col, SH_FELT), light, 0.5 * W, 0.4);
    p.clip(top, () => p.band(R([[cx - 0.6 * W, yb - 0.07 * HH], [cx + 0.6 * W, yb - 0.07 * HH]]), "#5a4a30", 0.12 * HH, 0.8 * u));
    p.poly(top, null, ow);
    if (side) p.poly(R([[cx + 0.3 * W, yb - 1 * u], [cx + 0.62 * W, yb + 0.09 * HH], [cx + 0.3 * W, yb + 0.07 * HH]]), "#3a2418", 2.5 * u);
    else { const [px, py] = R([[cx + 3 * u * facing, yb + 2 * u]])[0]; p.ell(px, py, 0.36 * W, 0.06 * HH, "#3a2418", 2.5 * u, 0, 180, deg); }
    const [gx, gy] = R([[cx + (side ? 0.22 * W : 0), yb - 0.2 * HH]])[0]; p.ell(gx, gy, 6 * u, 6 * u, "#e8c45a", 1.6 * u);
  } else if (o.hat === "fedora" || o.hat === "bowler" || o.hat === "akubra") {
    const fed = o.hat !== "bowler", ak = o.hat === "akubra", col = o.hatCol ?? "#2e2a36", yb = crown + 0.24 * HH, deg = (a * 180) / Math.PI;
    let body: P2[];
    if (fed) { // pinched crown with a centre dent
      const wb = 0.4 * W, wt = 0.3 * W, ht = 0.44 * HH;
      body = R([...sag(yb, wb).reverse(), [cx - wt, yb - ht], [cx - wt * 0.4, yb - ht - 0.05 * HH], [cx, yb - ht + 0.04 * HH], [cx + wt * 0.4, yb - ht - 0.05 * HH], [cx + wt, yb - ht]]);
    } else body = R(ellPts(cx, yb, 0.39 * W, 0.42 * HH, 180, 360));
    const [bx, by] = R([[cx, yb + 1 * u]])[0];
    p.ell(bx, by, (ak ? 0.78 : fed ? 0.62 : 0.5) * W, (ak ? 0.09 : fed ? 0.075 : 0.05) * HH, shade(col, 0.85), ow, 0, 360, deg);
    p.shadedFill(body, col, mul(col, SH_FELT), light, 0.4 * W, 0.4);
    p.clip(body, () => p.band(R([[cx - 0.5 * W, yb - 0.07 * HH], [cx + 0.5 * W, yb - 0.07 * HH]]), fed ? "#1b1820" : "#4a3a3a", 0.09 * HH, 0.6 * u));
    p.poly(body, null, ow);
  } else if (o.hat === "cloche") { // a bell hat pulled low over the brow, a band and a little bow
    const col = o.hatCol ?? "#c25a7a", yb = crown + 0.3 * HH, deg = (a * 180) / Math.PI;
    const bell: P2[] = R([...ellPts(cx, yb, 0.56 * W, 0.6 * HH, 180, 360), [cx + 0.6 * W, yb + 0.06 * HH], [cx - 0.6 * W, yb + 0.06 * HH]]);
    p.shadedFill(bell, col, mul(col, SH_FELT), light, 0.56 * W, 0.4);
    p.clip(bell, () => p.band(R([[cx - 0.7 * W, yb - 0.1 * HH], [cx + 0.7 * W, yb - 0.1 * HH]]), shade(col, 0.7), 0.08 * HH, 0.6 * u));
    p.poly(bell, null, ow);
    const [fx2, fy2] = R([[cx + 0.36 * W, yb - 0.1 * HH]])[0];
    p.ell(fx2, fy2, 7 * u, 5 * u, "#f2d590", 1.6 * u, 0, 360, deg);
  } else if (o.hat === "tophat") {
    const yb = crown + 0.22 * HH, ht = 0.8 * HH, wb = 0.31 * W, wt = 0.33 * W, col = "#2e2a36";
    const body = R([...sag(yb, wb).reverse(), [cx - wt, yb - ht], [cx + wt, yb - ht]]);
    p.shadedFill(body, col, mul(col, SH_FELT), light, wt, 0.4);
    p.clip(body, () => p.band(R([[cx - wt - 4 * u, yb - 0.13 * HH], [cx + wt + 4 * u, yb - 0.13 * HH]]), shade(o.jacket, 0.9), 0.14 * HH, 0.8 * u));
    p.poly(body, null, ow);
    const [bx, by] = R([[cx, yb + 1 * u]])[0];
    p.ell(bx, by, 0.45 * W, 0.05 * HH, "#1d1b22", ow, 0, 360, (a * 180) / Math.PI);
  } else if (o.hat === "helm") {
    // conical steel cap seated low on the crown, a rim band, a nasal bar down the nose (front)
    const yb = crown + 0.3 * HH, wb = 0.53 * W, peak = crown - 0.2 * HH, col = "#9aa0aa";
    const cap: P2[] = R([[cx - wb, yb], [cx - wb * 0.92, yb - 0.25 * HH], [cx - wb * 0.5, crown - 0.08 * HH], [cx, peak], [cx + wb * 0.5, crown - 0.08 * HH], [cx + wb * 0.92, yb - 0.25 * HH], [cx + wb, yb]]);
    p.shadedFill(cap, col, "#5d6370", light, wb, 0.4);
    p.poly(cap, null, ow);
    p.band(R([[cx - wb, yb - 2 * u], [cx + wb, yb - 2 * u]]), "#7d838e", 0.06 * HH, 1.2 * u);
    if (!side) p.band(R([[cx + 2 * u * facing, yb - 3 * u], [cx + 2 * u * facing, yb + 0.2 * HH]]), "#8a909b", 5 * u, 1.2 * u, "round");
  } else if (o.hat === "hardhat") {
    const yb = crown + 0.3 * HH, wb = 0.5 * W, col = o.cap ?? "#f2c230";
    const dome: P2[] = R(ellPts(cx, yb, wb, 0.42 * HH, 180, 360));
    p.shadedFill(dome, col, mul(col, SH_FELT), light, wb, 0.35);
    p.poly(dome, null, ow);
    p.stroke(R([[cx, yb - 0.4 * HH], [cx, yb]]), 2.2 * u, shade(col, 0.75));
    const [bx, by] = R([[cx + (side ? 10 * u : 0), yb + 1.5 * u]])[0];
    p.ell(bx, by, (side ? 0.62 : 0.6) * W, 0.05 * HH, shade(col, 0.85), ow, 0, 360, (a * 180) / Math.PI);
  } else if (o.hat === "sunhat") {
    const yb = crown + 0.25 * HH, col = "#e8cf8a";
    const dome: P2[] = R(ellPts(cx, yb, 0.36 * W, 0.3 * HH, 180, 360));
    const [bx, by] = R([[cx, yb + 1 * u]])[0];
    p.ell(bx, by, 0.78 * W, 0.08 * HH, "#dcbf72", ow, 0, 360, (a * 180) / Math.PI);
    p.shadedFill(dome, col, mul(col, SH_FELT), light, 0.36 * W, 0.35);
    p.poly(dome, null, ow);
    p.band(R([[cx - 0.36 * W, yb - 0.05 * HH], [cx + 0.36 * W, yb - 0.05 * HH]]), "#c25a7a", 0.07 * HH, 1.2 * u);
  } else if (o.hat === "bonnet") {
    const [bx, by] = R([[cx + (side ? 6 * u : 0), crown + 0.16 * HH]])[0];
    p.arc(bx, by, 0.5 * W, 0.2 * HH, 200, 340, 7 * u, BONNET_BRIM);
    p.arc(bx, by, 0.5 * W + 3.5 * u, 0.2 * HH + 3.5 * u, 200, 340, 1.2 * u);
    const cy = hc + H.b * 0.98;
    p.stroke([[cx - 14 * u, cy - 4 * u], [cx, cy + 2 * u], [cx + 14 * u, cy - 4 * u]], 2 * u, BONNET_BRIM);
  }
};

// ---------------- bodies ----------------
export type Arms = [P2[], P2[]];
/** held prop; for the hammer the number is the strike 0 (raised) .. 1 (struck) */
export type Prop = null | "salute" | "point" | "pen" | "hatInHand" | ["crank", number] | ["scratch", number] | "suitcaseOpen" | "envelope" | "cash" | "suitcase" | "palm" | "shh" | "crossed" | "facepalm" | "brush" | "present" | ["knock", number] | "icecream" | "shako" | ["hammer", number] | ["axe", number] | "dropper" | "tray" | "glass" | "salts" | "paper" | "watch" | "clipboard" | "rail" | "phone" | "wafer" | "magnifier" | "newspaper" | "camera";
const HELD = new Set(["dropper", "suitcaseOpen", "envelope", "cash", "brush", "glass", "salts", "paper", "watch", "clipboard", "phone", "wafer", "magnifier", "newspaper", "camera"]);

const BUILD: Record<Build, { a: number; torso: number; legs: number; tw: number }> = {
  adult: { a: 118, torso: 1.1, legs: 1.4, tw: 0.8 },
  stout: { a: 118, torso: 1.15, legs: 1.32, tw: 0.92 },
  kid: { a: 112, torso: 0.85, legs: 1.0, tw: 0.72 },
};

export type FrontOpts = {
  phase?: number; expr?: Expr; mode?: "march" | "stroll" | "stand" | "sit" | "fall"; look?: number; blink?: boolean | number; lift?: number;
  prop?: Prop; tilt?: number; headTilt?: number; wave?: number; blush?: boolean;
  /** canvas angle the key light comes FROM (painted crescent + thick outline side) */
  light?: number; facing?: -1 | 0 | 1; seed?: number;
};

const footStroke = (p: Pen, a: P2, b: P2, w: number, col: string) => {
  if (col !== INK) p.stroke([a, b], w + 3, INK);
  p.stroke([a, b], w, col);
};

export const bodyFront = (p: Pen, o: Outfit, opts: FrontOpts) => {
  const { phase = 0, expr = "neutral", mode = "march", look = 0, blink = false, lift = 60, prop = null, tilt = 0, headTilt = 0, wave, blush = false,
    light = DEF_LIGHT, facing = 0, seed = 1 } = opts;
  const Bd = BUILD[o.build ?? "adult"], skin = o.skin ?? SKIN, two = Math.PI * 2, lid = lidOf(blink);
  const H = headBlob(seed, Bd.a, facing), W = 2 * H.a, HH = 2 * H.b, u = W / 100;
  const tall = (1 + Bd.torso + Bd.legs) * HH, sole = 975;
  // body bob 5 % (march) / 3 % (stroll) of the height, lowest at contact (phase 0 and 0.5)
  const bob = mode === "march" ? 0.025 * tall * Math.cos(2 * two * phase) : mode === "stroll" ? 0.015 * tall * Math.cos(2 * two * phase) : 0;
  const torsoBot = mode === "sit" ? sole - 0.2 * HH : sole - Bd.legs * HH + bob;
  const chin = torsoBot - Bd.torso * HH, hc = chin - H.b, crown = hc - H.b, hipY = torsoBot - 0.12 * HH;
  const thick = thickAngle(light), ow = 5 * u;
  const legCol = mix(o.pants, INK, 0.55), armCol = mix(o.jacket, INK, 0.5), footCol = o.boots;
  const legW = 5.8 * u, footW = 7.5 * u;
  // ---- legs + feet (not rotated) ----
  p.rot = null;
  if (mode === "sit") {
    for (const side of [-1, 1]) {
      const h: P2 = [300 + side * 15 * u, hipY], k: P2 = [300 + side * 36 * u, hipY + 0.2 * HH], f: P2 = [300 + side * 44 * u, sole - 8 * u];
      p.stroke(curve(h, k, f), legW, legCol);
      footStroke(p, [f[0] - side * 2 * u, f[1]], [f[0] + side * 12 * u, f[1] - 5 * u], footW, footCol);
    }
  } else if (mode === "fall") {
    const legs: [P2, P2, P2][] = [
      [[300 - 15 * u, hipY], [300 - 46 * u, hipY + 0.5 * HH], [300 - 70 * u, hipY + 0.72 * HH]],
      [[300 + 15 * u, hipY], [300 + 50 * u, hipY + 0.45 * HH], [300 + 76 * u, hipY + 0.22 * HH]],
    ];
    legs.forEach(([h, k, f], i) => {
      p.stroke(curve(h, k, f), legW, legCol);
      footStroke(p, f, [f[0] + (i ? 14 : -14) * u, f[1] + (i ? -6 : 4) * u], footW, footCol);
    });
  } else if (o.dress) {
    for (const side of [-1, 1]) {
      const fx = 300 + side * 12 * u, fy = sole - 4 * u;
      p.stroke([[fx, sole - 0.4 * HH], [fx + side * u, fy]], legW, legCol);
      footStroke(p, [fx - side * 3 * u, fy], [fx + side * 12 * u, fy + u], footW, footCol);
    }
  } else {
    const L = mode === "march" ? lift * 1.25 : mode === "stroll" ? lift * 0.55 : 0;
    for (const [side, ph] of [[-1, 0], [1, 0.5]] as const) {
      const up = Math.max(0, Math.sin(two * (phase + ph))) * L;
      const hx = 300 + side * 15 * u, fx = 300 + side * 22 * u, fy = sole - 4 * u - up;
      const k: P2 = [(hx + fx) / 2 + side * (1.5 * u + up * 0.16), (hipY + fy) / 2 - up * 0.08];
      p.stroke(curve([hx, hipY], k, [fx, fy]), legW, legCol);
      footStroke(p, [fx - side * 3 * u, fy], [fx + side * 13 * u, fy + 0.5 * u], footW, footCol);
    }
  }
  // ---- upper body: rotates about the hips (tilt + a small weight-shift sway on every step) ----
  const sway = mode === "march" ? 1.6 * Math.sin(two * phase) : mode === "stroll" ? 1.0 * Math.sin(two * phase) : 0;
  const A = tilt + sway;
  p.rot = A ? [rad(A), 300, hipY] : null;
  const dress = !!o.dress && mode !== "sit" && mode !== "fall";
  const T: Blob = { a: ((Bd.tw / 2) * W) / 1.06, b: 0.5 * (torsoBot - (chin - 0.25 * HH)), nTop: 2.2, nBot: 2.6, egg: o.build === "stout" ? 0.17 : 0.12,
    asym: 0.04 * facing, rot: 0, noise: 0.006, seed: seed + 7 };
  const tcx = 300 + 3 * u * facing, tcy = torsoBot - T.b, tp = blobPts(tcx, tcy, T);
  const sh = (side: number): P2 => [tcx + side * 0.85 * T.a, chin + 0.12 * HH];
  const hang = (side: number, fwd: number): [P2, P2, P2] => {
    const S = sh(side), ex = tcx + side * (1.12 * T.a + 4 * u);
    const hx = ex + side * 3 * u - side * 6 * u * Math.max(0, fwd) + side * 4 * u * Math.max(0, -fwd);
    return [S, [ex, S[1] + 0.48 * HH], [hx, chin + 1.04 * HH - Math.abs(fwd) * 9 * u]];
  };
  const sw = mode === "march" || mode === "stroll" ? Math.sin(two * phase) : 0;
  // rifle at the order: butt by the right hip, held by the hanging right hand, muzzle past the crown
  const R0: P2 = [300 + 47 * u, torsoBot + 0.12 * HH], R1: P2 = [300 + 64 * u, crown - 0.32 * HH];
  const rifle = (!!o.rifle || !!o.spear) && (mode === "march" || mode === "stand" || mode === "stroll");
  type Arm = { pts: [P2, P2, P2]; front: boolean };
  const arms: Arm[] = [];
  if (mode === "sit" && !prop) for (const side of [-1, 1]) arms.push({ pts: [sh(side), [tcx + side * (1.1 * T.a + 6 * u), sh(side)[1] + 0.4 * HH], [tcx + side * (1.2 * T.a + 10 * u), torsoBot + 0.04 * HH]], front: false });
  else if (mode === "fall") for (const side of [-1, 1]) arms.push({ pts: [sh(side), [tcx + side * (1.15 * T.a + 12 * u), sh(side)[1] - 0.25 * HH], [tcx + side * (1.3 * T.a + 24 * u), sh(side)[1] - 0.68 * HH]], front: false });
  else {
    if (prop === "rail") { const S = sh(-1); arms.push({ pts: [S, [tcx - 1.25 * T.a - 12 * u, S[1] + 0.26 * HH], [tcx - 1.5 * T.a - 30 * u, S[1] + 0.44 * HH]], front: false }); }
    else arms.push({ pts: prop === "shako" ? hang(-1, 0) : hang(-1, -sw), front: false });
    if (rifle) {
      const G = lerp2(R0, R1, 0.1);
      arms.push({ pts: [sh(1), [tcx + 1.12 * T.a + 5 * u, sh(1)[1] + 0.45 * HH], G], front: false });
    } else if (prop === "palm") { // the hand held out, palm up, at waist height toward the viewer's side
      const S = sh(1);
      arms.push({ pts: [S, [tcx + 1.15 * T.a + 6 * u, S[1] + 0.42 * HH], [tcx + 1.35 * T.a + 22 * u, S[1] + 0.52 * HH]], front: true });
    } else if (prop === "shh") { // finger to the lips
      const S = sh(1);
      arms.push({ pts: [S, [tcx + 1.1 * T.a + 6 * u, S[1] + 0.34 * HH], [tcx + 0.1 * T.a + 6 * u * facing, chin - 0.08 * HH]], front: true });
    } else if (prop === "salute") { // the right hand up to the brim
      const S = sh(1);
      arms.push({ pts: [S, [tcx + 1.25 * T.a + 16 * u, S[1] - 0.12 * HH], [tcx + 0.55 * T.a, chin - 0.78 * HH]], front: true });
    } else if (prop === "point") { // the arm out straight, finger toward the screen right
      const S = sh(1);
      arms.push({ pts: [S, [tcx + 1.4 * T.a + 22 * u, S[1] - 0.08 * HH], [tcx + 1.85 * T.a + 52 * u, S[1] - 0.2 * HH]], front: true });
    } else if (Array.isArray(prop) && prop[0] === "scratch") { // scratching the head under the cap
      const S = sh(1), k = prop[1];
      arms.push({ pts: [S, [tcx + 1.3 * T.a + 14 * u, S[1] - 0.2 * HH], [tcx + 0.75 * T.a + 4 * u * k, chin - 0.95 * HH]], front: true });
    } else if (Array.isArray(prop) && prop[0] === "crank") { // turning a camera crank at chest height, toward the screen right
      const S = sh(1), a = prop[1] * Math.PI * 2, c: P2 = [tcx + 1.55 * T.a + 18 * u, S[1] + 0.32 * HH];
      arms.push({ pts: [S, [tcx + 1.2 * T.a + 8 * u, S[1] + 0.36 * HH], [c[0] + 12 * u * Math.cos(a), c[1] + 12 * u * Math.sin(a)]], front: true });
    } else if (prop === "pen") { // writing: the hand low in front of the chest
      const S = sh(1);
      arms.push({ pts: [S, [tcx + 1.05 * T.a + 4 * u, S[1] + 0.5 * HH], [tcx + 0.35 * T.a, S[1] + 0.62 * HH]], front: true });
    } else if (prop === "hatInHand") { // the farmer's hat held against the chest
      const S = sh(1);
      arms.push({ pts: [S, [tcx + 1.05 * T.a + 4 * u, S[1] + 0.45 * HH], [tcx + 0.2 * T.a, S[1] + 0.32 * HH]], front: true });
    } else if (prop === "facepalm") { // a hand over the eyes
      const S = sh(1);
      arms.push({ pts: [S, [tcx + 1.1 * T.a + 8 * u, S[1] + 0.2 * HH], [tcx + 0.05 * T.a, chin - 0.62 * HH]], front: true });
    } else if (prop === "crossed") { // arms folded across the chest: both forearms drawn in front
      arms.shift();
      for (const side of [1, -1]) { const S = sh(side); arms.push({ pts: [S, [tcx + side * (1.05 * T.a + 4 * u), S[1] + 0.42 * HH], [tcx - side * 0.45 * T.a, S[1] + 0.3 * HH]], front: true }); }
    } else if (prop === "present") { // a salesman's open arm toward the screen right, palm up
      const S = sh(1);
      arms.push({ pts: [S, [tcx + 1.3 * T.a + 18 * u, S[1] + 0.05 * HH], [tcx + 1.6 * T.a + 40 * u, S[1] - 0.18 * HH]], front: false });
    } else if (prop === "suitcase") { // carried at the side, arm hanging straight
      arms.push({ pts: hang(1, 0), front: false });
    } else if (Array.isArray(prop) && prop[0] === "knock") { // a raised fist, knocking forward
      const S = sh(1), k = clamp(prop[1], 0, 1);
      arms.push({ pts: [S, [tcx + 1.3 * T.a + 12 * u, S[1] + 0.12 * HH], [tcx + 1.55 * T.a + 18 * u + 12 * u * k, S[1] - 0.05 * HH]], front: true });
    } else if (wave !== undefined) {
      const S = sh(1);
      arms.push({ pts: [S, [tcx + 1.1 * T.a + 10 * u + 3 * u * wave, S[1] - 0.22 * HH], [tcx + 1.18 * T.a + 16 * u + 12 * u * wave, S[1] - 0.6 * HH]], front: false });
    } else if (prop === "tray") {
      // tray held up at shoulder height on a flat hand
      const S = sh(1);
      arms.push({ pts: [S, [tcx + 1.2 * T.a + 12 * u, S[1] + 0.12 * HH], [tcx + 1.25 * T.a + 6 * u, S[1] - 0.22 * HH]], front: false });
    } else if (prop === "icecream" || (typeof prop === "string" && HELD.has(prop))) {
      const S = sh(1);
      arms.push({ pts: [S, [tcx + 1.05 * T.a + 4 * u, S[1] + 0.45 * HH], [tcx + 0.5 * T.a, S[1] + 0.4 * HH]], front: true });
    } else if (Array.isArray(prop)) {
      const S = sh(1), k = clamp(prop[1], 0, 1);
      const E = lerp2([tcx + 1.1 * T.a + 10 * u, S[1] - 0.15 * HH], [tcx + 1.2 * T.a + 10 * u, S[1] + 0.3 * HH], k);
      const Hd = lerp2([tcx + 1.15 * T.a + 14 * u, S[1] - 0.55 * HH], [tcx + 1.45 * T.a + 22 * u, S[1] + 0.35 * HH], k);
      arms.push({ pts: [S, E, Hd], front: true });
    } else arms.push({ pts: hang(1, sw), front: false });
  }
  const drawArm = (a: Arm) => { p.stroke(curve(a.pts[0], a.pts[1], a.pts[2]), 5.2 * u, armCol); p.dot(a.pts[2][0], a.pts[2][1], 5.5 * u); };
  // behind the body: rifle, sword, arms
  if (rifle && o.spear) {
    const top = lerp2(R0, R1, 1.45), tip = lerp2(R0, R1, 1.62);
    p.band([R0, top], "#9a6a42", 4 * u, 1.4 * u, "round");
    const dx = (top[1] - tip[1]) * 0.12;
    p.poly([[top[0] - 6 * u, top[1] + 2 * u], [tip[0] - dx * 0, tip[1]], [top[0] + 6 * u, top[1] + 2 * u]], "#c9ccd2", 1.8 * u);
  } else if (rifle) {
    p.band([R0, R1], "#7a4b2a", 5 * u, 1.5 * u, "round");
    p.band([lerp2(R0, R1, 0.6), R1], "#8d949c", 2.4 * u, 1.2 * u, "round");
  }
  if (o.sword && mode !== "sit") {
    const s0: P2 = [tcx - 0.75 * T.a, torsoBot - 0.2 * HH];
    p.band([s0, [s0[0] - Math.sin(rad(25)) * 0.8 * HH, s0[1] + Math.cos(rad(25)) * 0.8 * HH]], "#c9ccd2", 3 * u, 1.2 * u, "round");
  }
  for (const a of arms) if (!a.front) drawArm(a);
  // torso / dress: shaded fill -> clothing clipped to it -> thick-thin ink ring
  if (dress) {
    const D: Blob = { a: 0.5 * W * 0.98, b: 0.5 * ((sole - 0.35 * HH) - (chin - 0.2 * HH)), nTop: 2.0, nBot: 3.0, egg: 0.35, asym: 0.03 * facing, rot: 0, noise: 0.006, seed: seed + 9 };
    const dp = blobPts(300, sole - 0.35 * HH - D.b, D);
    p.gradFill(dp, o.dress!, mul(o.dress!, SH_CLOTH), light);
    p.inkRing(dp, ow, thick);
    const Sw: Blob = { a: 0.37 * W, b: 0.3 * HH, nTop: 2.2, nBot: 2.4, egg: 0.1, asym: 0, rot: 0, noise: 0.006, seed: seed + 8 };
    const sp = blobPts(300, chin + 0.12 * HH, Sw);
    p.gradFill(sp, o.jacket, mul(o.jacket, SH_CLOTH), light);
    p.inkRing(sp, ow * 0.9, thick);
  } else {
    p.gradFill(tp, o.jacket, mul(o.jacket, SH_CLOTH), light);
    p.clip(tp, () => {
      if (o.belt) {
        for (const s of [-1, 1]) p.band([[tcx - s * 0.75 * T.a, chin - 0.05 * HH], [tcx + s * 0.8 * T.a, torsoBot - 0.1 * HH]], o.belt!, 5.5 * u, 1.8 * u);
        const xc = tcx + 0.025 * T.a, yc = chin - 0.05 * HH + (torsoBot - 0.1 * HH - (chin - 0.05 * HH)) * (0.75 / 1.55);
        p.poly([[xc - 3.5 * u, yc - 3.5 * u], [xc + 3.5 * u, yc - 3.5 * u], [xc + 3.5 * u, yc + 3.5 * u], [xc - 3.5 * u, yc + 3.5 * u]], "#d9dde0", 1.5 * u);
      }
      if (o.sash) p.band([[tcx - 1.3 * T.a, torsoBot - 0.32 * HH], [tcx + 1.3 * T.a, torsoBot - 0.32 * HH]], o.sash, 0.13 * HH, 1.8 * u);
      if (o.cross) {
        const cy = chin + 0.42 * HH;
        p.band([[tcx + 2 * u * facing, chin + 0.05 * HH], [tcx + 2 * u * facing, torsoBot - 0.05 * HH]], o.cross, 0.15 * HH, 1.4 * u);
        p.band([[tcx - 0.62 * T.a, cy], [tcx + 0.62 * T.a, cy]], o.cross, 0.15 * HH, 1.4 * u);
        return;
      }
      if (o.braces) for (const s2 of [-1, 1]) p.band([[tcx + s2 * 0.42 * T.a, chin - 0.1 * HH], [tcx + s2 * 0.36 * T.a, torsoBot]], o.braces, 4.5 * u, 1.2 * u);
      if (o.sam) { p.band([[tcx - 0.8 * T.a, torsoBot - 0.2 * HH], [tcx + 0.8 * T.a, torsoBot - 0.2 * HH]], o.sam, 0.09 * HH, 1.4 * u); p.band([[tcx + 0.55 * T.a, chin - 0.05 * HH], [tcx - 0.5 * T.a, torsoBot - 0.2 * HH]], o.sam, 4 * u, 1.2 * u); }
      if (o.medal) {
        const mx = tcx - 0.42 * T.a, my = chin + 0.28 * HH;
        p.poly([[mx - 7 * u, my - 10 * u], [mx + 7 * u, my - 10 * u], [mx + 6 * u, my + 4 * u], [mx - 6 * u, my + 4 * u]], o.medal, 1.2 * u);
        p.ell(mx, my + 10 * u, 6 * u, 6 * u, "#e8c45a", 1.4 * u);
      }
      if (o.tie) {
        const tx = tcx + 2 * u * facing;
        p.poly([[tx - 13 * u, chin - 0.05 * HH], [tx + 13 * u, chin - 0.05 * HH], [tx, chin + 0.36 * HH]], "#f4f1ea", 1.4 * u); // shirt V
        p.poly([[tx - 4 * u, chin + 0.02 * HH], [tx + 4 * u, chin + 0.02 * HH], [tx + 6 * u, chin + 0.5 * HH], [tx, chin + 0.6 * HH], [tx - 6 * u, chin + 0.5 * HH]], o.tie, 1.4 * u);
        p.poly([[tx - 5 * u, chin - 0.03 * HH], [tx + 5 * u, chin - 0.03 * HH], [tx + 4 * u, chin + 0.07 * HH], [tx - 4 * u, chin + 0.07 * HH]], shade(o.tie, 0.8), 1.2 * u);
        for (const s of [-1, 1]) p.stroke([[tx + s * 14 * u, chin - 0.04 * HH], [tx + s * 0.5 * T.a, chin + 0.55 * HH]], 1.6 * u, shade(o.jacket, 0.7)); // lapels
        return;
      }
      if (o.vest) for (const y of [chin + 0.3 * HH, torsoBot - 0.35 * HH]) p.band([[tcx - 1.3 * T.a, y], [tcx + 1.3 * T.a, y]], o.vest, 0.09 * HH, 1.4 * u);
      for (let i = 0; i < 4; i++) {
        const y = chin + 0.12 * HH + i * 0.2 * HH;
        if (o.sash && Math.abs(y - (torsoBot - 0.32 * HH)) < 0.08 * HH) continue;
        p.dot(tcx + 2 * u * facing, y, 2.2 * u + 0.8 * u, INK); p.dot(tcx + 2 * u * facing, y, 2.2 * u, o.buttons ?? shade(o.jacket, 0.7));
      }
    });
    if (o.sash) { const s = facing || 1; p.poly([[tcx + s * 0.55 * T.a, torsoBot - 0.3 * HH], [tcx + s * 0.75 * T.a, torsoBot + 0.05 * HH], [tcx + s * 0.45 * T.a, torsoBot + 0.02 * HH]], o.sash, 1.6 * u); }
    p.inkRing(tp, ow, thick);
  }
  // in front of the body: hands holding props
  const overHead = prop === "shh" || prop === "facepalm" || prop === "salute" || (Array.isArray(prop) && prop[0] === "scratch");
  const frontHand = (a: Arm, handOnly = false) => {
    if (!handOnly) drawArm(a);
    const [hx, hy] = a.pts[2];
    if (prop === "envelope") {
      // a fat brown envelope of banknotes (the bribe)
      p.poly([[hx - 26 * u, hy - 30 * u], [hx + 24 * u, hy - 33 * u], [hx + 26 * u, hy + 2 * u], [hx - 24 * u, hy + 5 * u]], "#d9b06a", 2.2 * u);
      p.stroke([[hx - 25 * u, hy - 29 * u], [hx, hy - 12 * u], [hx + 24 * u, hy - 32 * u]], 1.8 * u);
      p.poly([[hx - 14 * u, hy - 38 * u], [hx + 10 * u, hy - 40 * u], [hx + 12 * u, hy - 30 * u], [hx - 12 * u, hy - 28 * u]], "#8fc27a", 1.6 * u);
      p.dot(hx, hy, 5.5 * u);
    } else if (prop === "suitcaseOpen") {
      // the suitcase held open in front of the chest: banknotes bursting out
      p.poly([[hx - 44 * u, hy - 8 * u], [hx + 44 * u, hy - 8 * u], [hx + 40 * u, hy + 34 * u], [hx - 40 * u, hy + 34 * u]], "#9a5a32", 2.4 * u);
      p.poly([[hx - 44 * u, hy - 8 * u], [hx + 44 * u, hy - 8 * u], [hx + 50 * u, hy - 46 * u], [hx - 50 * u, hy - 46 * u]], "#7a4426", 2.4 * u);
      for (let k = 0; k < 9; k++) { const x = hx - 36 * u + k * 9 * u, y = hy - 10 * u - (k % 3) * 7 * u;
        p.poly(rotPts([[x - 9 * u, y], [x + 9 * u, y], [x + 9 * u, y - 22 * u], [x - 9 * u, y - 22 * u]], rad(-30 + k * 8), x, y), k % 2 ? "#8fc27a" : "#a9d48e", 1.4 * u); }
      for (const dx of [-24, 24]) p.band([[hx + dx * u, hy - 8 * u], [hx + dx * u, hy + 33 * u]], "#5a3424", 3 * u, 0.8 * u);
      p.dot(hx - 40 * u, hy + 10 * u, 5.5 * u); p.dot(hx + 40 * u, hy + 10 * u, 5.5 * u);
    } else if (prop === "cash") {
      // a fan of green banknotes held up
      for (let k = 0; k < 5; k++) {
        const note = rotPts([[hx - 11 * u, hy], [hx + 11 * u, hy], [hx + 11 * u, hy - 48 * u], [hx - 11 * u, hy - 48 * u]], rad(-40 + k * 20), hx, hy);
        p.poly(note, k % 2 ? "#8fc27a" : "#a9d48e", 1.8 * u);
        const [ox, oy] = rotPts([[hx, hy - 32 * u]], rad(-40 + k * 20), hx, hy)[0]; p.ell(ox, oy, 4 * u, 4 * u, "#5d8a3a", 1 * u);
      }
      p.dot(hx, hy, 5.5 * u);
    } else if (prop === "brush") {
      // a wide paint brush, a drip of fresh paint
      p.band([[hx - 2 * u, hy + 14 * u], [hx + 4 * u, hy - 30 * u]], "#c98a52", 4.5 * u, 1.4 * u, "round");
      p.poly([[hx - 4 * u, hy - 30 * u], [hx + 14 * u, hy - 32 * u], [hx + 15 * u, hy - 40 * u], [hx - 3 * u, hy - 38 * u]], "#c9ccd2", 1.8 * u);
      p.poly([[hx - 5 * u, hy - 38 * u], [hx + 16 * u, hy - 40 * u], [hx + 22 * u, hy - 62 * u], [hx - 10 * u, hy - 58 * u]], "#6a4a32", 2 * u);
      for (let k = 0; k < 5; k++) p.stroke([[hx - 3 * u + k * 4 * u, hy - 41 * u], [hx - 7 * u + k * 6.5 * u, hy - 58 * u]], 1.2 * u, "#3a2a22");
      p.poly([[hx - 10 * u, hy - 58 * u], [hx + 22 * u, hy - 62 * u], [hx + 23 * u, hy - 68 * u], [hx - 11 * u, hy - 64 * u]], "#9a6b3e", 1.6 * u);
      p.ell(hx + 18 * u, hy - 56 * u, 3 * u, 5 * u, "#9a6b3e", 1.2 * u);
      p.dot(hx, hy, 5.5 * u);
    } else if (prop === "palm") {
      // an open hand, palm up: a flat mitten with the thumb raised
      p.ell(hx + 4 * u, hy - 2 * u, 15 * u, 6 * u, skin, 2.2 * u, 0, 360, -8);
      p.ell(hx - 7 * u, hy - 9 * u, 4 * u, 7 * u, skin, 2 * u, 0, 360, -20);
    } else if (prop === "shh") {
      p.ell(hx, hy + 2 * u, 7 * u, 8 * u, skin, 2 * u);
      p.band([[hx, hy - 4 * u], [hx, hy - 17 * u]], skin, 4.5 * u, 1.6 * u, "round"); // the raised finger over the lips
    } else if (prop === "facepalm") {
      p.ell(hx, hy, 17 * u, 12 * u, skin, 2.2 * u, 0, 360, 10);
      for (const dx of [-9, -2, 5]) p.stroke([[hx + dx * u, hy - 9 * u], [hx + dx * u + 2 * u, hy + 4 * u]], 1.4 * u, mul(skin, SH_SKIN));
    } else if (prop === "crossed") {
      p.ell(hx, hy, 6.5 * u, 6.5 * u, skin, 2 * u);
    } else if (prop === "salute") {
      p.poly(rotPts([[hx - 12 * u, hy - 5 * u], [hx + 10 * u, hy - 8 * u], [hx + 11 * u, hy + 3 * u], [hx - 11 * u, hy + 5 * u]], rad(-20), hx, hy), skin, 2 * u);
    } else if (prop === "point") {
      p.ell(hx, hy, 7 * u, 6.5 * u, skin, 2 * u);
      p.band([[hx + 4 * u, hy - 2 * u], [hx + 17 * u, hy - 5 * u]], skin, 4.2 * u, 1.5 * u, "round");
    } else if (Array.isArray(prop) && prop[0] === "scratch") {
      p.ell(hx, hy, 7 * u, 7 * u, skin, 2 * u);
    } else if (Array.isArray(prop) && prop[0] === "crank") {
      p.dot(hx, hy, 5.5 * u);
    } else if (prop === "pen") {
      p.band([[hx - 2 * u, hy + 4 * u], [hx + 10 * u, hy - 16 * u]], "#2e2a36", 2.6 * u, 1 * u, "round");
      p.dot(hx, hy, 5.5 * u);
    } else if (prop === "hatInHand") {
      const col = o.hatCol ?? "#7a5a3a";
      p.ell(hx, hy + 6 * u, 34 * u, 9 * u, shade(col, 0.85), 2.2 * u);
      p.poly([[hx - 20 * u, hy + 6 * u], [hx - 16 * u, hy - 22 * u], [hx + 16 * u, hy - 22 * u], [hx + 20 * u, hy + 6 * u]], col, 2.2 * u);
      p.dot(hx, hy, 5.5 * u);
    } else if (Array.isArray(prop) && prop[0] === "knock") {
      p.ell(hx, hy, 9 * u, 8 * u, skin, 2.2 * u);
      for (const dy of [-4, 1]) p.stroke([[hx + 2 * u, hy + dy * u], [hx + 7 * u, hy + dy * u]], 1.3 * u, mul(skin, SH_SKIN));
    } else if (prop === "glass") {
      // a brandy balloon: amber in a round glass on a short stem
      p.ell(hx, hy - 18 * u, 11 * u, 10 * u, "#e9f4f6", 2 * u);
      p.ell(hx, hy - 14 * u, 9 * u, 5 * u, "#c9822e", 0);
      p.band([[hx, hy - 8 * u], [hx, hy + 4 * u]], "#e9f4f6", 2.5 * u, 1 * u);
      p.dot(hx, hy, 5.5 * u);
    } else if (prop === "salts") {
      // a little green smelling-salts bottle with a cork
      p.poly([[hx - 7 * u, hy - 4 * u], [hx + 7 * u, hy - 4 * u], [hx + 7 * u, hy - 26 * u], [hx + 3 * u, hy - 30 * u], [hx - 3 * u, hy - 30 * u], [hx - 7 * u, hy - 26 * u]], "#4f9a6a", 2 * u);
      p.poly([[hx - 3 * u, hy - 30 * u], [hx + 3 * u, hy - 30 * u], [hx + 3 * u, hy - 37 * u], [hx - 3 * u, hy - 37 * u]], "#b5834f", 1.6 * u);
      p.dot(hx, hy, 5.5 * u);
    } else if (prop === "paper") {
      // a document with a red wax seal (no writing: grey lines only)
      p.poly([[hx - 20 * u, hy - 46 * u], [hx + 18 * u, hy - 48 * u], [hx + 20 * u, hy + 2 * u], [hx - 18 * u, hy + 4 * u]], "#f7f1e1", 2 * u);
      for (let i = 0; i < 4; i++) p.stroke([[hx - 13 * u, hy - 38 * u + i * 8 * u], [hx + 12 * u, hy - 39 * u + i * 8 * u]], 1.6 * u, "#b9b2a2");
      p.ell(hx + 8 * u, hy - 4 * u, 6 * u, 6 * u, "#c0353a", 1.6 * u);
      p.dot(hx - 16 * u, hy - 2 * u, 5.5 * u);
    } else if (prop === "phone") {
      // a phone held up, screen toward the viewer: black glass, a bright screen with app tiles
      p.poly([[hx - 14 * u, hy - 50 * u], [hx + 14 * u, hy - 50 * u], [hx + 14 * u, hy + 4 * u], [hx - 14 * u, hy + 4 * u]], "#20232b", 2.2 * u);
      p.poly([[hx - 11 * u, hy - 46 * u], [hx + 11 * u, hy - 46 * u], [hx + 11 * u, hy], [hx - 11 * u, hy]], "#6fc3ff", 0);
      const tiles = ["#ffd24a", "#ff6a5a", "#59d38a", "#ffffff", "#b38aff", "#ff9a3c"];
      for (let r = 0; r < 3; r++) for (let c = 0; c < 2; c++) p.poly([[hx - 8 * u + c * 9 * u, hy - 42 * u + r * 12 * u], [hx - 2 * u + c * 9 * u, hy - 42 * u + r * 12 * u], [hx - 2 * u + c * 9 * u, hy - 35 * u + r * 12 * u], [hx - 8 * u + c * 9 * u, hy - 35 * u + r * 12 * u]], tiles[r * 2 + c], 0);
      p.dot(hx, hy, 5.5 * u);
    } else if (prop === "wafer") {
      // a polished wafer: a mirror disc with a rainbow sheen of printed chips
      const cy = hy - 26 * u;
      p.ell(hx, cy, 26 * u, 26 * u, "#c9d6f2", 2.2 * u);
      const cols = ["#ff7ad0", "#7ad8ff", "#ffe07a", "#9aff9a"];
      for (let r = -2; r <= 2; r++) for (let c = -2; c <= 2; c++) if (r * r + c * c <= 5) p.poly([[hx + c * 9 * u - 3.5 * u, cy + r * 9 * u - 3.5 * u], [hx + c * 9 * u + 3.5 * u, cy + r * 9 * u - 3.5 * u], [hx + c * 9 * u + 3.5 * u, cy + r * 9 * u + 3.5 * u], [hx + c * 9 * u - 3.5 * u, cy + r * 9 * u + 3.5 * u]], cols[(r + c + 8) % 4], 0);
      p.ell(hx - 9 * u, cy - 10 * u, 6 * u, 3 * u, "#ffffff", 0, 0, 360, -30);
      p.dot(hx, hy, 5.5 * u);
    } else if (prop === "magnifier") {
      p.stroke([[hx, hy], [hx + 10 * u, hy - 18 * u]], 4 * u, "#7a4b2a");
      p.ell(hx + 17 * u, hy - 32 * u, 15 * u, 15 * u, "rgba(200,235,255,0.55)", 3 * u);
      p.dot(hx, hy, 5.5 * u);
    } else if (prop === "newspaper") {
      // an open broadsheet held in front of the chest (no readable text: grey column lines)
      p.poly([[hx - 46 * u, hy - 62 * u], [hx + 30 * u, hy - 66 * u], [hx + 32 * u, hy + 8 * u], [hx - 44 * u, hy + 10 * u]], "#f2ecdc", 2.2 * u);
      p.stroke([[hx - 7 * u, hy - 64 * u], [hx - 6 * u, hy + 9 * u]], 1.2 * u, "#b9b2a2");
      for (let i = 0; i < 6; i++) { p.stroke([[hx - 40 * u, hy - 50 * u + i * 9 * u], [hx - 12 * u, hy - 51 * u + i * 9 * u]], 1.6 * u, "#a9a292"); p.stroke([[hx - 1 * u, hy - 52 * u + i * 9 * u], [hx + 26 * u, hy - 53 * u + i * 9 * u]], 1.6 * u, "#a9a292"); }
      p.dot(hx - 44 * u, hy - 2 * u, 5.5 * u); p.dot(hx + 30 * u, hy - 2 * u, 5.5 * u);
    } else if (prop === "camera") {
      // a 1940s press camera with a flash reflector
      p.poly([[hx - 16 * u, hy - 24 * u], [hx + 16 * u, hy - 24 * u], [hx + 16 * u, hy + 2 * u], [hx - 16 * u, hy + 2 * u]], "#2e2a36", 2.2 * u);
      p.ell(hx, hy - 11 * u, 8 * u, 8 * u, "#5a6070", 1.6 * u);
      p.ell(hx + 20 * u, hy - 36 * u, 12 * u, 12 * u, "#d9dde2", 2 * u);
      p.dot(hx, hy, 5.5 * u);
    } else if (prop === "watch") {
      // a stopwatch: steel case, white face, one hand
      p.ell(hx, hy - 16 * u, 13 * u, 13 * u, "#c9ccd2", 2.2 * u);
      p.ell(hx, hy - 16 * u, 9.5 * u, 9.5 * u, "#ffffff", 1.4 * u);
      p.stroke([[hx, hy - 16 * u], [hx + 4 * u, hy - 23 * u]], 1.8 * u);
      p.poly([[hx - 2.5 * u, hy - 29 * u], [hx + 2.5 * u, hy - 29 * u], [hx + 2.5 * u, hy - 33 * u], [hx - 2.5 * u, hy - 33 * u]], "#c9ccd2", 1.4 * u);
      p.dot(hx, hy, 5.5 * u);
    } else if (prop === "clipboard") {
      p.poly([[hx - 18 * u, hy - 44 * u], [hx + 18 * u, hy - 44 * u], [hx + 18 * u, hy + 4 * u], [hx - 18 * u, hy + 4 * u]], "#b5834f", 2 * u);
      p.poly([[hx - 14 * u, hy - 38 * u], [hx + 14 * u, hy - 38 * u], [hx + 14 * u, hy], [hx - 14 * u, hy]], "#f7f1e1", 1.2 * u);
      p.poly([[hx - 7 * u, hy - 47 * u], [hx + 7 * u, hy - 47 * u], [hx + 7 * u, hy - 40 * u], [hx - 7 * u, hy - 40 * u]], "#8d949c", 1.4 * u);
      p.dot(hx, hy, 5.5 * u);
    } else if (prop === "icecream") {
      p.poly([[hx - 8 * u, hy - 12 * u], [hx + 8 * u, hy - 12 * u], [hx, hy + 7 * u]], "#e0a35a", 1.8 * u);
      p.ell(hx, hy - 19 * u, 11 * u, 10 * u, "#f7c6d9", 2.2 * u);
      p.dot(hx, hy, 5.5 * u);
    } else if (Array.isArray(prop) && prop[0] === "axe") {
      // a farm axe: a long hickory handle, a steel head with a bright cutting edge
      const ang = rad(-70 + 105 * clamp(prop[1], 0, 1));
      const Rh = (pts: P2[]) => rotPts(pts, ang, hx, hy);
      p.band(Rh([[hx, hy + 18 * u], [hx, hy - 78 * u]]), "#b07a44", 5.5 * u, 1.5 * u, "round");
      p.poly(Rh([[hx - 4 * u, hy - 88 * u], [hx + 22 * u, hy - 96 * u], [hx + 30 * u, hy - 76 * u], [hx + 22 * u, hy - 58 * u], [hx - 4 * u, hy - 66 * u]]), "#8d949c", 2.2 * u);
      p.stroke(Rh([[hx + 25 * u, hy - 92 * u], [hx + 29 * u, hy - 62 * u]]), 2.6 * u, "#e9eef2");
      p.dot(hx, hy, 5.5 * u);
    } else if (prop === "dropper") {
      // an eyedropper: a glass tube with a red rubber bulb, a drop of milk at the tip
      p.poly([[hx - 3 * u, hy - 2 * u], [hx + 3 * u, hy - 2 * u], [hx + 2 * u, hy + 26 * u], [hx - 2 * u, hy + 26 * u]], "#e9f4f6", 1.6 * u);
      p.ell(hx, hy - 7 * u, 6 * u, 8 * u, "#d9382e", 1.8 * u);
      p.ell(hx, hy + 31 * u, 3 * u, 4 * u, "#ffffff", 1.2 * u);
      p.dot(hx, hy, 5.5 * u);
    } else if (Array.isArray(prop)) {
      const ang = rad(-70 + 105 * clamp(prop[1], 0, 1));
      const Rh = (pts: P2[]) => rotPts(pts, ang, hx, hy);
      p.band(Rh([[hx, hy + 12 * u], [hx, hy - 44 * u]]), "#8a5a34", 5 * u, 1.5 * u, "round");
      p.poly(Rh([[hx - 12 * u, hy - 58 * u], [hx + 20 * u, hy - 58 * u], [hx + 20 * u, hy - 42 * u], [hx - 12 * u, hy - 42 * u]]), "#7d848c", 2.2 * u);
      p.dot(hx, hy, 5.5 * u);
    }
  };
  for (const a of arms) if (a.front) { if (overHead) drawArm(a); else frontHand(a); }
  if (prop === "tray") { // a silver tray of brandy glasses on the raised right hand
    const [hx, hy] = arms[arms.length - 1].pts[2];
    p.ell(hx - 6 * u, hy - 3 * u, 40 * u, 8 * u, "#d9dde2", 2.4 * u);
    for (const dx of [-26, -6, 14]) {
      const gx = hx - 6 * u + dx * u, gy = hy - 12 * u;
      p.band([[gx, gy + 8 * u], [gx, gy - 2 * u]], "#e9f4f6", 2.4 * u, 1 * u);
      p.ell(gx, gy - 9 * u, 8 * u, 7.5 * u, "#e9f4f6", 1.8 * u);
      p.ell(gx, gy - 6 * u, 6.5 * u, 3.5 * u, "#c9822e", 0);
    }
    p.dot(hx, hy, 5.5 * u);
  }
  if (prop === "suitcase") { // a brown leather case with straps hanging from the right hand
    const [hx, hy] = arms[arms.length - 1].pts[2];
    p.poly([[hx - 36 * u, hy + 4 * u], [hx + 36 * u, hy + 4 * u], [hx + 38 * u, hy + 58 * u], [hx - 38 * u, hy + 58 * u]], "#9a5a32", 2.4 * u);
    for (const dx of [-20, 20]) p.band([[hx + dx * u, hy + 5 * u], [hx + dx * u, hy + 57 * u]], "#5a3424", 3 * u, 0.8 * u);
    p.stroke([[hx - 10 * u, hy + 4 * u], [hx - 8 * u, hy - 4 * u], [hx + 8 * u, hy - 4 * u], [hx + 10 * u, hy + 4 * u]], 3 * u, "#5a3424");
    // a banknote sticking out of the lid
    p.poly([[hx + 14 * u, hy + 6 * u], [hx + 30 * u, hy - 8 * u], [hx + 36 * u, hy - 2 * u], [hx + 22 * u, hy + 10 * u]], "#8fc27a", 1.4 * u);
    p.dot(hx, hy, 5.5 * u);
  }
  if (prop === "present") { const [hx, hy] = arms[arms.length - 1].pts[2]; p.ell(hx + 4 * u, hy - 2 * u, 12 * u, 6 * u, skin, 2 * u, 0, 360, -30); }
  if (prop === "shako") { // carried by the left hand
    const [hx, hy] = arms[0].pts[2];
    p.poly([[hx - 14 * u, hy + 3 * u], [hx + 14 * u, hy + 3 * u], [hx + 16 * u, hy + 30 * u], [hx - 16 * u, hy + 30 * u]], "#3a3d47", 2.2 * u);
    p.ell(hx, hy + 31 * u, 3.5 * u, 3.5 * u, "#2b7a4b", 1.5 * u);
    p.dot(hx, hy, 5.5 * u);
  }
  // ---- head: rotates with the body, plus its own tilt about the chin ----
  const Ah = A + headTilt, [cpx, cpy] = rotAbout([300, chin], rad(A), [300, hipY]);
  p.rot = Ah ? [rad(Ah), 300, chin, cpx - 300, cpy - chin] : null;
  hatBehind(p, o, H, 300, hc, light, thick, ow, false);
  const hp = blobPts(300, hc, H);
  p.shadedFill(hp, skin, mul(skin, SH_SKIN), light, H.a);
  p.inkRing(hp, ow, thick);
  hatOn(p, o, hp, H, 300, hc, light, seed, facing, false);
  const brim = !!o.hat && o.hat !== "hair" && o.hat !== "bonnet" && o.hat !== "cap" && o.hat !== "helm";
  faceFront(p, 300, hc, W, expr, facing, look, lid, brim, skin, o.moustache, o.build === "stout");
  if (blush) for (const s2 of [-1, 1]) p.ell(300 + 7 * u * facing + s2 * 24 * u, hc + 13 * u, 9 * u, 5 * u, "rgba(230,90,110,0.55)", 0);
  if (overHead) { p.rot = A ? [rad(A), 300, hipY] : null; for (const a2 of arms) if (a2.front) frontHand(a2, true); p.rot = Ah ? [rad(Ah), 300, chin, cpx - 300, cpy - chin] : null; }
  if (o.mask) { // cleanroom face mask: a soft rounded band over mouth + chin, two pleats, ear loops
    const mx = 300 + 6 * u * facing, mcy = hc + 24 * u;
    const mk = blobPts(mx, mcy, { a: 34 * u, b: 17 * u, nTop: 2.6, nBot: 2.2, egg: 0.1, asym: 0, rot: 0, noise: 0.004, seed: seed + 11 });
    p.shadedFill(mk, o.mask, mul(o.mask, SH_CLOTH), light, 34 * u);
    p.inkRing(mk, ow * 0.8, thick);
    for (const dy of [-5, 4]) p.stroke([[mx - 24 * u, mcy + dy * u], [mx + 24 * u, mcy + dy * u]], 1.3 * u, shade(o.mask, 0.78));
  }
  p.rot = null;
};

export type SideOpts = {
  phase?: number; expr?: Expr; mode?: "march" | "stand" | "swing" | "push"; blink?: boolean | number; stomp?: number; pose?: number;
  /** step length as a multiple of 0.8 m (370 units): matches 1.6 m/s at 2 steps/s; scale by the view's foreshortening */
  stride?: number; light?: number; seed?: number;
  /** push mode: where the hands land at pose 1, in final canvas units (e.g. the swing kid's back) */
  hand?: [number, number];
};

/** two-bone leg, knee bending forward (+x) */
const ik = (hip: P2, ank: P2, l1: number, l2: number): P2 => {
  const dx = ank[0] - hip[0], dy = ank[1] - hip[1], d = clamp(Math.hypot(dx, dy), 1, l1 + l2 - 0.01);
  const A = Math.acos(clamp((l1 * l1 + d * d - l2 * l2) / (2 * l1 * d), -1, 1)), k = Math.atan2(dy, dx) - A;
  return [hip[0] + l1 * Math.cos(k), hip[1] + l1 * Math.sin(k)];
};

/** hip height of the seated kid in `swing` mode (design units); swingKid seats the torso bottom on the plank */
const SWING_HIP = 733;

/** side view facing screen-right; march footfalls land at phase 0 (near foot) and 0.5 (far foot), like the front view.
 *  The stance foot is planted: it slides back at exactly the walking speed while the hip rises and falls over it. */
export const bodySide = (p: Pen, o: Outfit, opts: SideOpts) => {
  const { phase = 0, expr = "neutral", mode = "march", blink = false, stomp = 1, pose = 0, stride = 1, light = DEF_LIGHT, seed = 1 } = opts;
  const Bd = BUILD[o.build ?? "adult"], skin = o.skin ?? SKIN, two = Math.PI * 2, lid = lidOf(blink);
  const H: Blob = { ...headBlob(seed, Bd.a, 1), asym: 0.12, rot: rad(3 + 3 * (rnd(seed, 7) - 0.5)) };
  const W = 2 * H.a, HH = 2 * H.b, u = W / 100, sole = 975, ankY = sole - 4 * u;
  const thick = thickAngle(light), ow = 5 * u;
  const legLen = (Bd.legs + 0.12) * HH - 4 * u, l1 = legLen / 2, l2 = legLen / 2;
  const nearCol = mix(o.pants, INK, 0.55), farCol = mix(o.pants, INK, 0.75), footCol = o.boots;
  type LegS = { ank: P2; pitch: number; near: boolean };
  const legs: LegS[] = [];
  let hipY = ankY - legLen * 0.995, lean = 0, nearFwd = 0;
  if (mode === "march") {
    const S = 370 * stride, liftH = Math.max(22, 40 + 70 * (stomp - 1));
    const st = (ph: number) => {
      const c = (((phase + ph) % 1) + 1) % 1;
      if (c < 0.5) { const s = c / 0.5; return { x: S / 2 - S * s, h: 0, stance: true, s }; }
      const s = (c - 0.5) / 0.5; // swing: cycloid in world space, so the foot leaves and lands at zero ground speed
      return { x: -S / 2 + S * s - (S / Math.PI) * Math.sin(2 * Math.PI * s), h: liftH * Math.sin(Math.PI * s), stance: false, s };
    };
    const nL = st(0), fL = st(0.5), stance = nL.stance ? nL : fL;
    const Leff = legLen * (1 - 0.035 * Math.sin(Math.PI * stance.s));
    hipY = ankY - Math.sqrt(Math.max(1, Leff * Leff - stance.x * stance.x));
    for (const [L, near] of [[fL, false], [nL, true]] as const)
      legs.push({ ank: [300 + L.x, ankY - L.h], pitch: L.stance ? 0 : rad(35 * Math.sin(Math.PI * L.s) * (1 - 1.6 * L.s)), near });
    lean = 4 + 3 * Math.cos(2 * two * phase); // 7 deg at contact, 1 deg at passing
    nearFwd = nL.x / (S / 2);
  } else if (mode === "push") {
    hipY = ankY - 0.87 * legLen;
    legs.push({ ank: [300 - 0.5 * legLen, ankY], pitch: rad(-8), near: false }, { ank: [300 + 0.32 * legLen, ankY], pitch: 0, near: true });
    lean = 14 * pose;
  } else if (mode === "swing") {
    hipY = SWING_HIP;
    const a = rad(60 * pose);
    for (const [dx, near] of [[-6, false], [0, true]] as const) {
      const knee: P2 = [300 + l1 * 0.98 + dx * u, hipY + 6 * u];
      legs.push({ ank: [knee[0] + l2 * Math.sin(a), knee[1] + l2 * Math.cos(a)], pitch: -a * 0.5, near });
    }
  } else {
    legs.push({ ank: [300 - 4 * u, ankY], pitch: 0, near: false }, { ank: [300 + 4 * u, ankY], pitch: 0, near: true });
  }
  const torsoBot = hipY + 0.12 * HH, chin = torsoBot - Bd.torso * HH, hc = chin - H.b, crown = hc - H.b, hip: P2 = [300, hipY];
  p.rot = null;
  for (const L of legs) {
    const knee = mode === "swing" ? ([300 + l1 * 0.98 + (L.near ? 0 : -6 * u), hipY + 6 * u] as P2) : ik(hip, L.ank, l1, l2);
    const hp0: P2 = [300 + (L.near ? 0 : -5 * u), hipY];
    p.stroke([hp0, knee, L.ank], 5.8 * u, L.near ? nearCol : farCol);
    const c = Math.cos(L.pitch), s = Math.sin(L.pitch);
    footStroke(p, [L.ank[0] - 3 * u * c, L.ank[1] - 3 * u * s], [L.ank[0] + 13 * u * c, L.ank[1] + 13 * u * s + 0.5 * u],
      7.5 * u, L.near ? footCol : footCol === INK ? INK : shade(footCol, 0.82));
  }
  // ---- upper body leans about the hip ----
  p.rot = lean ? [rad(lean), 300, hipY] : null;
  const T: Blob = { a: (o.build === "stout" ? 0.36 : 0.31) * W, b: 0.5 * (torsoBot - (chin - 0.25 * HH)), nTop: 2.2, nBot: 2.5, egg: 0.1, asym: 0.06,
    rot: 0, noise: 0.006, seed: seed + 7 };
  const tcx = 300 + 2 * u, tcy = torsoBot - T.b, tp = blobPts(tcx, tcy, T);
  const armCol = mix(o.jacket, INK, 0.5), farArm = mix(o.jacket, INK, 0.68);
  const S: P2 = [tcx + 0.05 * T.a, chin + 0.14 * HH], aLen = 0.95 * HH;
  const swingArm = (ang: number): [P2, P2, P2] => {
    const e: P2 = [S[0] + Math.sin(ang) * aLen * 0.5, S[1] + Math.cos(ang) * aLen * 0.5], a2 = ang + rad(16) * Math.sign(ang || 1);
    return [S, e, [e[0] + Math.sin(a2) * aLen * 0.5, e[1] + Math.cos(a2) * aLen * 0.5]];
  };
  const rifle = (!!o.rifle || !!o.spear) && (mode === "march" || mode === "stand");
  const B0: P2 = [tcx + 0.72 * T.a, chin + 0.58 * HH], B1: P2 = [tcx - 0.95 * T.a - 22 * u, crown - 0.4 * HH];
  let near: [P2, P2, P2], far: [P2, P2, P2] | null;
  if (mode === "swing") { near = [S, [S[0] + 12 * u, S[1] - 0.16 * HH], [300 + 6 * u, chin - 0.3 * HH]]; far = [S, [S[0] + 8 * u, S[1] - 0.18 * HH], [300 + 2 * u, chin - 0.36 * HH]]; }
  else if (mode === "push") {
    const reach = 0.55 * HH + 0.45 * HH * pose;
    let hN: P2 = [S[0] + reach, S[1] + 0.06 * HH];
    if (opts.hand) {
      // target is in final canvas units; the arm is drawn inside the lean rotation, so undo it
      const th = -rad(lean), dx = opts.hand[0] - 300, dy = opts.hand[1] - hipY;
      const tg: P2 = [300 + dx * Math.cos(th) - dy * Math.sin(th), hipY + dx * Math.sin(th) + dy * Math.cos(th)];
      hN = [hN[0] + (tg[0] - hN[0]) * pose, hN[1] + (tg[1] - hN[1]) * pose];
    }
    near = [S, [(S[0] + hN[0]) / 2, (S[1] + hN[1]) / 2 + 0.06 * HH], hN];
    far = [S, [(S[0] + hN[0]) / 2 - 4 * u, (S[1] + hN[1]) / 2 - 0.02 * HH], [hN[0] - 6 * u, hN[1] - 0.08 * HH]];
  } else if (rifle) { near = [S, [S[0] - 4 * u, S[1] + 0.42 * HH], B0]; far = mode === "march" ? swingArm(rad(30) * nearFwd) : swingArm(0); }
  else { near = swingArm(rad(-30) * nearFwd); far = mode === "march" ? swingArm(rad(30) * nearFwd) : null; }
  if (far) { p.stroke(curve(far[0], far[1], far[2]), 5.2 * u, farArm); p.dot(far[2][0], far[2][1], 5.5 * u); }
  p.gradFill(tp, o.jacket, mul(o.jacket, SH_CLOTH), light);
  p.clip(tp, () => {
    if (o.belt) p.band([[tcx - 0.65 * T.a, chin - 0.05 * HH], [tcx + 0.75 * T.a, torsoBot - 0.1 * HH]], o.belt!, 5.5 * u, 1.8 * u);
    if (o.sash) p.band([[tcx - 1.3 * T.a, torsoBot - 0.32 * HH], [tcx + 1.3 * T.a, torsoBot - 0.32 * HH]], o.sash, 0.13 * HH, 1.8 * u);
    if (o.cross) { p.band([[tcx + 0.45 * T.a, chin + 0.05 * HH], [tcx + 0.45 * T.a, torsoBot - 0.05 * HH]], o.cross, 0.14 * HH, 1.4 * u); p.band([[tcx - 0.1 * T.a, chin + 0.42 * HH], [tcx + 1.2 * T.a, chin + 0.42 * HH]], o.cross, 0.14 * HH, 1.4 * u); }
    else if (o.vest) for (const y of [chin + 0.3 * HH, torsoBot - 0.35 * HH]) p.band([[tcx - 1.3 * T.a, y], [tcx + 1.3 * T.a, y]], o.vest, 0.09 * HH, 1.4 * u);
    if (!o.dress && !o.cross) for (let i = 0; i < 3; i++) { const y = chin + 0.16 * HH + i * 0.24 * HH; p.dot(tcx + 0.8 * T.a, y, 3 * u, INK); p.dot(tcx + 0.8 * T.a, y, 2.2 * u, o.buttons ?? shade(o.jacket, 0.7)); }
  });
  p.inkRing(tp, ow, thick);
  if (rifle && o.spear) {
    const top = lerp2(B0, B1, 1.45), tip = lerp2(B0, B1, 1.62);
    p.band([B0, top], "#9a6a42", 4 * u, 1.4 * u, "round");
    p.poly([[top[0] - 6 * u, top[1] + 2 * u], [tip[0], tip[1]], [top[0] + 6 * u, top[1] + 2 * u]], "#c9ccd2", 1.8 * u);
  } else if (rifle) {
    p.band([B0, B1], "#7a4b2a", 5 * u, 1.5 * u, "round");
    p.band([lerp2(B0, B1, 0.6), B1], "#8d949c", 2.4 * u, 1.2 * u, "round");
  }
  p.stroke(curve(near[0], near[1], near[2]), 5.2 * u, armCol); p.dot(near[2][0], near[2][1], 5.5 * u);
  // ---- head ----
  const hx = 300 + 4 * u;
  hatBehind(p, o, H, hx, hc, light, thick, ow, true);
  const hp = blobPts(hx, hc, H);
  p.shadedFill(hp, skin, mul(skin, SH_SKIN), light, H.a);
  p.inkRing(hp, ow, thick);
  hatOn(p, o, hp, H, hx, hc, light, seed, 1, true);
  const brim = !!o.hat && o.hat !== "hair" && o.hat !== "bonnet" && o.hat !== "cap";
  faceSide(p, hx, hc, W, expr, lid, brim, skin, o.moustache, o.build === "stout");
  p.rot = null;
};

/** rope + seat + seated kid on a 700 x 2300 canvas; the pivot is design (350, 20); kid drawn at 0.92 scale */
export const swingKid = (p: Pen, o: Outfit, kick: number, expr: Expr, light = DEF_LIGHT, blink: number = 0) => {
  const rope = 1830, k = 1.1, HH = 2 * headBlob(5, BUILD[o.build ?? "adult"].a, 1).b;
  // two ropes from the pivot to the ends of a wide plank, the kid framed between them: a single rope behind the kid
  // ended at the cap and read as a hanging. Far rope behind the kid, near rope drawn over (clear of the face).
  const seat = rope + 18, x0 = 150, x1 = 550;
  p.line([[350, 20], [x0 + 16, seat + 4]], "#a07a4c", 10);
  p.poly(rrect(x0, seat, x1, seat + 36, 10), "#b5653f", 9);
  const g = p.g;
  g.save();
  g.translate(350 - 300 * k, rope + 18 - (SWING_HIP + 0.12 * HH) * k);
  g.scale(k, k);
  bodySide(new Pen(g), o, { expr, mode: "swing", pose: kick, light, seed: 5, blink });
  g.restore();
  p.line([[350, 20], [x1 - 16, seat + 4]], "#a07a4c", 10);
};

// ---------------- effects ----------------
export const fxNote = (p: Pen, kind: number, col = "#1f2a44") => {
  p.ell(70, 200, 46, 34, col, 8, 0, 360, -20);
  p.stroke([[110, 190], [110, 40]], 14);
  if (kind === 0) p.poly([[110, 40], [170, 70], [170, 110], [110, 82]], col, 8);
  else {
    p.ell(150, 170, 40, 30, col, 8, 0, 360, -20);
    p.stroke([[186, 160], [186, 20]], 14);
    p.poly([[110, 40], [186, 20], [186, 50], [110, 70]], col, 8);
  }
};

/** spark / impact star on a 500 x 500 canvas; t in 0..1 */
export const fxBurst = (p: Pen, t: number, col = "#fff3b0", rays = 10, r0 = 40, r1 = 230) => {
  const c = 250, e = 1 - (1 - t) ** 3;
  for (let i = 0; i < rays; i++) {
    const a = rad((i * 360) / rays + 7 * (i % 2)), ra = r0 + (r1 - r0) * e * (0.75 + 0.25 * (i % 2));
    p.poly([[c + r0 * 0.5 * Math.cos(a + 0.18), c + r0 * 0.5 * Math.sin(a + 0.18)], [c + ra * Math.cos(a), c + ra * Math.sin(a)],
      [c + r0 * 0.5 * Math.cos(a - 0.18), c + r0 * 0.5 * Math.sin(a - 0.18)]], col, Math.max(3, 8 * (1 - t)));
  }
  if (t < 0.5) p.ell(c, c, r0 * (1.4 - t), r0 * (1.4 - t), WHITE, 8);
};

/** water splash crown on an 800 x 800 canvas; t in 0..1 */
export const fxSplash = (p: Pen, t: number) => {
  const c = 400, size = 800, rise = Math.sin(Math.min(1, t * 1.3) * Math.PI);
  const blue = "#bfe8ff", deep = "#6cc0f0";
  if (rise > 0.02) {
    const pts: P2[] = [];
    for (let i = 0; i < 19; i++) {
      const h = (i % 2 ? 260 : 130) * rise * (0.7 + 0.3 * Math.sin(i * 1.7));
      pts.push([c - 330 + (660 * i) / 18, size - 120 - h]);
    }
    p.poly([...pts, [c + 330, size - 90], [c - 330, size - 90]], blue, 10);
    p.ell(c, size - 100, 360, 46, deep, 10);
  }
  for (let i = 0; i < 8; i++) {
    const a = rad(200 + i * 18), d = 120 + 380 * t, y = size - 160 + d * Math.sin(a) + 520 * t * t, r = 26 * (1 - t) + 6;
    if (t > 0.08 && y < size - 40) p.ell(c + d * Math.cos(a), y, r, r * 1.25, blue, 7);
  }
};

/** dust puff on a 300 x 300 canvas; t in 0..1 */
export const fxPuff = (p: Pen, t: number) => {
  for (let i = 0; i < 5; i++) {
    const a = rad(160 + i * 55), d = 40 + 70 * t, r = (34 + 20 * (i % 2)) * (1 - 0.6 * t);
    p.ell(150 + d * Math.cos(a), 180 + d * 0.45 * Math.sin(a), r, r * 0.8, `rgba(238,225,205,${(1 - t).toFixed(3)})`, 0);
  }
};

/** circling stars on a 420 x 210 canvas */
export const fxStars = (p: Pen, t: number) => {
  for (let i = 0; i < 4; i++) {
    const a = t * Math.PI * 2 + (i * Math.PI) / 2, x = 210 + 150 * Math.cos(a), y = 110 + 40 * Math.sin(a), pts: P2[] = [];
    for (let k = 0; k < 10; k++) { const r = k % 2 ? 14 : 34, b = rad(k * 36 - 90); pts.push([x + r * Math.cos(b), y + r * Math.sin(b)]); }
    p.poly(pts, "#ffd84a", 6);
  }
};

/** three jittering strain ticks on a 300 x 300 canvas */
export const fxCreak = (p: Pen, t: number) => {
  const j = 6 * Math.sin(t * 40);
  for (const a of [-30, 0, 30]) {
    const b = rad(a - 90);
    p.stroke([[150 + 70 * Math.cos(b) + j, 230 + 70 * Math.sin(b)], [150 + 100 * Math.cos(b) + 10 + j, 230 + 100 * Math.sin(b)],
      [150 + 130 * Math.cos(b) + j, 230 + 130 * Math.sin(b)]], 10);
  }
};

/** flat water ring (drawn top-down) on a 600 x 600 canvas; t in 0..1 */
export const fxRing = (p: Pen, t: number) => {
  // thin light water rings (white crest, pale blue trailing rings), thinning as they spread
  const g = p.g;
  for (let k = 0; k < 3; k++) {
    const u = t - k * 0.22;
    if (u <= 0 || u >= 1) continue;
    g.beginPath(); g.ellipse(300, 300, 60 + 230 * u, 60 + 230 * u, 0, 0, Math.PI * 2);
    g.strokeStyle = k === 0 ? "#f6fcff" : "#cfe8fa"; g.lineWidth = 9 * (1 - u) + 3; g.stroke();
  }
};

/** text-free sign on a 700 x 520 canvas: "no marching in step on the bridge". A bridge (deck + arch + piers), four
 *  identical pairs of marching legs in the same stride (in step), a bold red X over all of it. */
export const fxSign = (p: Pen) => {
  const g = p.g, RED = "#d42f2f";
  p.poly(rrect(14, 14, 686, 506, 40), "#f6ecd2", 0);
  p.poly(rrect(14, 14, 686, 506, 40), null, 14);
  // bridge: deck, stone arch underneath, two piers
  p.poly(rrect(70, 352, 630, 384, 8), "#8a5a3a", 9);
  g.beginPath(); g.moveTo(112, 470); g.quadraticCurveTo(350, 300, 588, 470);
  g.strokeStyle = INK; g.lineWidth = 16; g.lineCap = "round"; g.stroke();
  for (const x of [88, 612]) p.poly(rrect(x - 16, 384, x + 16, 470, 4), "#8a5a3a", 9);
  // four identical soldiers' legs mid-stride: same leg forward on every one = in step
  for (const x of [150, 278, 406, 534]) {
    p.poly(rrect(x - 30, 150, x + 30, 214, 14), "#357650", 9);                  // coat hem
    p.stroke([[x - 8, 210], [x + 34, 262], [x + 46, 338]], 15, INK);           // front leg
    p.stroke([[x + 6, 210], [x - 12, 274], [x - 36, 336]], 15, INK);           // back leg
    p.poly(rrect(x + 30, 330, x + 74, 350, 9), INK, 0);                          // boots point forward
    p.poly(rrect(x - 52, 328, x - 8, 348, 9), INK, 0);
  }
  // big red X
  for (const [a, b] of [[[96, 70], [604, 452]], [[604, 70], [96, 452]]] as [[number, number], [number, number]][]) {
    p.stroke([a, b], 58, "#ffffff");
    p.stroke([a, b], 42, RED);
  }
};

/** soft cartoon cloud on a 600 x 300 canvas */
export const fxCloud = (p: Pen, seed: number) => {
  const blobs: [number, number, number][] = [[150, 190, 80], [250, 150, 105], [360, 160, 95], [450, 195, 70], [300, 210, 90]];
  for (const [x, y, r] of blobs) p.ell(x + ((seed * 37) % 20) - 10, y, r, r * 0.8, "#ffffff", 0);
  p.ell(300, 235, 230, 40, "#ffffff", 0);
};

/** cast shadow on a 128 x 256 canvas: dark soft contact pool at the feet (y 205) and a softer tail that runs up the
 *  canvas = away from the sun, fading with distance; multiply colour (sRGB-encoded linear ratio), white = no change */
export const fxShadow = (p: Pen, col: string) => {
  const g = p.g;
  g.fillStyle = WHITE; g.fillRect(0, 0, 128, 256);
  g.save(); g.filter = "blur(9px)";
  const lg = g.createLinearGradient(0, 205, 0, 22);
  lg.addColorStop(0, mix(col, WHITE, 0.08)); lg.addColorStop(0.55, mix(col, WHITE, 0.3)); lg.addColorStop(1, mix(col, WHITE, 0.85));
  g.fillStyle = lg;
  g.beginPath(); g.moveTo(40, 205); g.bezierCurveTo(36, 120, 46, 50, 64, 30); g.bezierCurveTo(82, 50, 92, 120, 88, 205); g.closePath(); g.fill();
  g.fillStyle = col; g.beginPath(); g.ellipse(64, 205, 30, 17, 0, 0, Math.PI * 2); g.fill();
  g.restore();
};

/** tight contact shadow right under the feet on a 128 x 128 canvas: dark core, short fall-off (multiply colour) */
export const fxContact = (p: Pen, col: string) => {
  const g = p.g;
  g.fillStyle = WHITE; g.fillRect(0, 0, 128, 128);
  const gr = g.createRadialGradient(64, 64, 0, 64, 64, 64);
  for (const [r, k] of [[0, 0], [0.32, 0.02], [0.5, 0.22], [0.66, 0.58], [0.82, 0.88], [1, 1]] as const) gr.addColorStop(r, mix(col, WHITE, k));
  g.fillStyle = gr; g.fillRect(0, 0, 128, 128);
};

/** floating wooden plank, side-on, on a 320 x 110 canvas */
export const fxPlank = (p: Pen) => {
  p.poly(rrect(14, 30, 306, 78, 10), "#a8744a", 9);
  p.line([[40, 46], [150, 44], [270, 50]], "#7d5234", 4);
  p.line([[60, 62], [200, 64], [284, 60]], "#7d5234", 4);
  p.dot(36, 54, 5, INK); p.dot(284, 54, 5, INK);
};

/** floating marching drum (no text) on a 260 x 240 canvas: white shell, red hoops, ink zig-zag cord */
export const fxDrum = (p: Pen) => {
  p.poly(rrect(40, 70, 220, 190, 16), "#f1ece0", 9);
  p.poly(rrect(32, 58, 228, 86, 12), "#c9373a", 8);
  p.poly(rrect(32, 176, 228, 204, 12), "#c9373a", 8);
  p.line([[52, 88], [82, 172], [112, 88], [142, 172], [172, 88], [202, 172]], INK, 6);
  p.ell(130, 58, 98, 18, "#f7f3ea", 8);
};

/** soft ground contact blob on a 128 x 128 canvas, multiply colour (sRGB-encoded linear ratio) in the centre */
export const fxBlob = (p: Pen, col: string) => {
  const g = p.g;
  g.fillStyle = WHITE; g.fillRect(0, 0, 128, 128);
  // soft contact shadow: flat core, then a long smooth (roughly gaussian) fall-off to white = no change
  const gr = g.createRadialGradient(64, 64, 0, 64, 64, 64);
  for (const [r, k] of [[0, 0], [0.5, 0.04], [0.64, 0.18], [0.76, 0.42], [0.87, 0.72], [0.95, 0.92], [1, 1]] as const) gr.addColorStop(r, mix(col, WHITE, k));
  g.fillStyle = gr; g.fillRect(0, 0, 128, 128);
};

/** a ripe banana lying on its side on a 600 x 300 canvas (the curve of the tower) */
export const fxBanana = (p: Pen) => {
  const pts: P2[] = [];
  for (let i = 0; i <= 24; i++) { const t = i / 24, a = rad(200 + 140 * t); pts.push([300 + 250 * Math.cos(a), 330 + 210 * Math.sin(a) - 10 * Math.sin(t * Math.PI)]); }
  for (let i = 24; i >= 0; i--) { const t = i / 24, a = rad(205 + 130 * t); pts.push([300 + 235 * Math.cos(a), 330 + 150 * Math.sin(a)]); }
  p.poly(pts, "#f4d24a", 9);
  p.line([[300 + 250 * Math.cos(rad(210)), 330 + 210 * Math.sin(rad(210))], [300 + 240 * Math.cos(rad(330)), 330 + 200 * Math.sin(rad(330))]], "#e3b93a", 0.1, false);
  p.ell(300 + 252 * Math.cos(rad(200)) - 6, 330 + 205 * Math.sin(rad(200)) + 4, 14, 10, "#6a4a2a", 5);
  p.ell(300 + 245 * Math.cos(rad(340)) + 4, 330 + 205 * Math.sin(rad(340)) + 2, 10, 8, "#3a2a1a", 5);
};
/** a water bead on a 200 x 260 canvas; t 0..1 swells, rolls, fades */
export const fxBead = (p: Pen, t: number) => {
  const r = 34 + 22 * Math.min(1, t * 2), a = t > 0.75 ? (1 - t) / 0.25 : 1;
  p.ell(100, 200 - r, r * 0.85, r, `rgba(120,180,230,${a.toFixed(3)})`, 6 * a);
  p.ell(100 - r * 0.3, 200 - r * 1.35, r * 0.18, r * 0.24, `rgba(255,255,255,${(0.9 * a).toFixed(3)})`, 0);
};
/** big dust cloud on a 600 x 400 canvas; t 0..1 */
export const fxDust = (p: Pen, t: number) => {
  for (let i = 0; i < 9; i++) {
    const a = rad(170 + i * 22), d = 60 + 230 * t, r = (70 + 30 * (i % 3)) * (1 - 0.45 * t);
    p.ell(300 + d * Math.cos(a), 330 + d * 0.32 * Math.sin(a) - 60 * t, r, r * 0.75, `rgba(232,218,196,${(0.95 * (1 - t ** 1.5)).toFixed(3)})`, 0);
  }
};
/** a mallet or a chisel falling (drawn on 300 x 300) */
export const fxTool = (p: Pen, kind: number) => {
  if (kind === 0) {
    p.band([[150, 250], [150, 110]], "#8a5a34", 18, 5, "round");
    p.poly([[100, 70], [200, 70], [200, 120], [100, 120]], "#9a6a42", 7);
  } else {
    p.band([[150, 250], [150, 150]], "#8a5a34", 20, 5, "round");
    p.poly([[138, 150], [162, 150], [158, 60], [150, 40], [142, 60]], "#9aa0aa", 6);
  }
};

/** soil clods thrown up out of a bore hole on a 300 x 300 canvas; t 0..1 (they fly out and fall onto the heap) */
export const fxSoil = (p: Pen, t: number) => {
  for (let i = 0; i < 7; i++) {
    const a = rad(200 + i * 22), v = 70 + 25 * (i % 3), x = 150 + Math.cos(a) * v * t * 1.6, y = 230 - (Math.sin(-a) * v * 1.9) * t + 210 * t * t;
    const r = (11 + 5 * (i % 2)) * (1 - 0.3 * t);
    if (y < 290) p.ell(x, y, r, r * 0.85, i % 2 ? "#7a5a3c" : "#5e4430", 3);
  }
};

/** a bicycle drive on a 600 x 400 canvas: chainring + rear sprocket and the chain loop round both; a = turn (rad) */
export const fxBike = (p: Pen, a: number) => {
  const C1: P2 = [430, 230], R1 = 95, C2: P2 = [150, 230], R2 = 45;
  const gear = (c: P2, r: number, n: number, col: string) => {
    const pts: P2[] = [];
    for (let i = 0; i < n * 2; i++) { const ang = a * (R1 / r) + (i / (n * 2)) * Math.PI * 2, rr = i % 2 ? r : r + 14; pts.push([c[0] + rr * Math.cos(ang), c[1] + rr * Math.sin(ang)]); }
    p.poly(pts, col, 6);
    p.ell(c[0], c[1], r * 0.35, r * 0.35, "#f4f1ea", 5);
  };
  const top1: P2 = [C1[0], C1[1] - R1 - 6], top2: P2 = [C2[0], C2[1] - R2 - 6], bot1: P2 = [C1[0], C1[1] + R1 + 6], bot2: P2 = [C2[0], C2[1] + R2 + 6];
  p.stroke([top2, top1], 16, "#3d414c"); p.stroke([bot2, bot1], 16, "#3d414c");
  p.arc(C1[0], C1[1], R1 + 6, R1 + 6, -90, 90, 16, "#3d414c"); p.arc(C2[0], C2[1], R2 + 6, R2 + 6, 90, 270, 16, "#3d414c");
  // links moving along the top run (toward the chainring) and the bottom run (back)
  const L = C1[0] - C2[0], off = (((a * (R1 + 6)) % 40) + 40) % 40;
  for (let d = off; d < L; d += 40) {
    const k = d / L;
    p.ell(C2[0] + d, top2[1] + (top1[1] - top2[1]) * k, 7, 4, "#c9ccd2", 0);
    p.ell(C1[0] - d, bot1[1] + (bot2[1] - bot1[1]) * k, 7, 4, "#c9ccd2", 0);
  }
  gear(C1, R1, 16, "#c8823a"); gear(C2, R2, 9, "#c8823a");
  const px = C1[0] + 70 * Math.cos(a), py = C1[1] + 70 * Math.sin(a);
  p.band([C1, [px, py]], "#4b505c", 14, 5, "round");
  p.poly([[px - 26, py - 9], [px + 26, py - 9], [px + 26, py + 9], [px - 26, py + 9]], "#24222c", 5);
};
/** the trademark certificate tumbling away (300 x 300): parchment, grey lines, red seal */
export const fxPaper = (p: Pen) => {
  p.poly([[60, 40], [235, 30], [245, 265], [70, 275]], "#f7f1e1", 7);
  for (let i = 0; i < 6; i++) p.stroke([[90, 75 + i * 26], [215, 70 + i * 26]], 5, "#b9b2a2");
  p.ell(200, 235, 24, 24, "#c0353a", 5);
  p.poly([[188, 252], [178, 285], [196, 274], [204, 290], [212, 254]], "#c0353a", 4);
};
/** a cartoon hand resting on a handrail, seen from the side (300 x 200): mitten fingers forward (+x), a cuff */
export const fxHand = (p: Pen, skin = SKIN, cuff = "#e2453c") => {
  p.poly([[18, 70], [96, 62], [100, 150], [24, 158]], cuff, 7);
  const palm: P2[] = [];
  for (let i = 0; i <= 28; i++) { const a = rad(-100 + (i / 28) * 200); palm.push([150 + 95 * Math.cos(a), 112 + 50 * Math.sin(a)]); }
  palm.push([95, 166], [95, 58]);
  p.poly(palm, skin, 7);
  for (const y of [92, 116, 140]) p.stroke([[196, y], [236, y + 2]], 5, mul(skin, SH_SKIN));
  p.ell(150, 68, 32, 16, skin, 6);
};

/** a big newspaper page (600 x 800): masthead bar, columns of grey lines, a tiny article boxed low in the last column
 *  (with a little transistor sketch), the page number in the top corner; `ring` 0..1 circles the tiny article */
export const fxNewspaper = (p: Pen, page: string, ring = 0) => {
  p.poly([[20, 20], [580, 14], [586, 786], [26, 790]], "#f3edde", 9);
  p.poly([[60, 56], [540, 52], [540, 96], [60, 100]], "#3a3a40", 0);
  p.stroke([[40, 118], [560, 114]], 4, "#8a8478");
  for (let c = 0; c < 4; c++) {
    const x0 = 50 + c * 128;
    for (let i = 0; i < 26; i++) { const y = 140 + i * 24; if (c === 3 && (y > 600 || y < 200)) continue; p.stroke([[x0, y], [x0 + 110 - (i % 7 === 6 ? 40 : 0), y - 1]], 5, "#b4ad9c"); }
  }
  p.poly([[434, 620], [550, 618], [552, 742], [436, 744]], "#f8f3e6", 3);
  for (let i = 0; i < 4; i++) p.stroke([[446, 640 + i * 16], [540, 639 + i * 16]], 3, "#9a9384");
  p.poly([[470, 718], [492, 700], [514, 718]], "#d9a845", 2); p.poly([[462, 718], [522, 718], [522, 734], [462, 734]], "#5a6070", 2);
  const g = p.g; g.fillStyle = "#3a3a40"; g.font = "bold 64px Georgia, serif"; g.textAlign = "right"; g.fillText(page, 556, 180);
  if (ring > 0) {
    g.save(); g.globalAlpha = Math.min(1, ring); g.strokeStyle = "#e2453c"; g.lineWidth = 12; g.lineCap = "round";
    const k = 1.3 - 0.3 * Math.min(1, ring); g.beginPath(); g.ellipse(494, 681, 92 * k, 82 * k, -0.1, 0.2, Math.PI * 2 * Math.min(1, ring * 1.1)); g.stroke(); g.restore();
  }
};
/** a camera flash burst (256 x 256) */
export const fxFlash = (p: Pen) => {
  const g = p.g, gr = g.createRadialGradient(128, 128, 4, 128, 128, 124);
  gr.addColorStop(0, "rgba(255,255,255,1)"); gr.addColorStop(0.35, "rgba(255,250,220,0.8)"); gr.addColorStop(1, "rgba(255,250,220,0)");
  g.fillStyle = gr; g.fillRect(0, 0, 256, 256);
  for (let k = 0; k < 8; k++) { const a = (k / 8) * Math.PI * 2; p.stroke([[128 + 30 * Math.cos(a), 128 + 30 * Math.sin(a)], [128 + 100 * Math.cos(a), 128 + 100 * Math.sin(a)]], 6, "#fff6c8"); }
};

// ---------------- the Eiffel film's effect cards ----------------
/** the forged letter (600 x 760): cream paper, a gold crest (a post horn in a wreath), grey lines, a drawing of the
 *  tower, a signature scrawl; `seal` stamps a red ministry seal at the bottom right */
export const fxLetter = (p: Pen, seal: boolean) => {
  p.poly([[24, 20], [576, 26], [570, 742], [30, 736]], "#f7f1e1", 8);
  p.ell(300, 108, 62, 52, "#f2d590", 5);
  p.arc(300, 112, 34, 22, 180, 360, 9, "#c9a24a"); p.ell(338, 116, 12, 9, "#c9a24a", 4); p.stroke([[266, 112], [252, 132]], 7, "#c9a24a");
  for (const s of [-1, 1]) for (let k = 0; k < 5; k++) p.ell(300 + s * (70 + k * 4), 70 + k * 20, 10, 6, "#5d8a3a", 3, 0, 360, s * 40);
  p.stroke([[60, 186], [540, 186]], 4, "#c9a24a");
  for (let i = 0; i < 6; i++) p.stroke([[70, 230 + i * 34], [i === 5 ? 330 : 520, 230 + i * 34]], 6, "#b9b2a2");
  // the tower sketch, as if the letter describes the sale
  p.stroke([[150, 650], [190, 470], [200, 420], [204, 380]], 5, "#7a5a3a"); p.stroke([[258, 650], [218, 470], [208, 420], [204, 380]], 5, "#7a5a3a");
  p.stroke([[168, 560], [240, 560]], 5, "#7a5a3a"); p.stroke([[184, 500], [224, 500]], 5, "#7a5a3a"); p.arc(204, 650, 30, 34, 180, 360, 5, "#7a5a3a");
  p.stroke([[320, 640], [350, 610], [372, 636], [400, 600], [430, 630], [470, 612]], 5, "#2e2a36");
  if (seal) {
    const pts: P2[] = []; for (let k = 0; k < 24; k++) { const r = k % 2 ? 58 : 66, a = rad(k * 15); pts.push([450 + r * Math.cos(a), 520 + r * Math.sin(a)]); }
    p.poly(pts, "#c0353a", 5); p.ell(450, 520, 38, 38, "#a42a30", 3); p.arc(450, 522, 18, 12, 180, 360, 6, "#f2d590");
  }
};
/** the rubber stamp (300 x 360): wooden knob and handle, a brass base */
export const fxStamp = (p: Pen) => {
  p.ell(150, 70, 56, 50, "#8a5a34", 7);
  p.poly([[126, 110], [174, 110], [182, 250], [118, 250]], "#9a6a42", 7);
  p.poly([[60, 250], [240, 250], [250, 300], [50, 300]], "#e8c45a", 7);
  p.poly([[56, 300], [244, 300], [244, 330], [56, 330]], "#c0353a", 6);
};
/** a thought cloud of an angry Paris (520 x 420): little faces with angry brows, raised fists, the tower in between */
export const fxRiot = (p: Pen) => {
  const blobs: [number, number, number][] = [[140, 190, 110], [260, 140, 130], [390, 170, 115], [420, 270, 90], [260, 290, 120], [120, 290, 80]];
  for (const [x, y, r] of blobs) p.ell(x, y, r + 9, (r + 9) * 0.82, INK, 0);
  for (const [x, y, r] of blobs) p.ell(x, y, r, r * 0.82, "#ffffff", 0);
  p.ell(150, 395, 22, 18, "#ffffff", 7); p.ell(110, 412, 12, 10, "#ffffff", 6);
  p.stroke([[248, 300], [262, 170], [276, 300]], 7, "#7a5a3a"); p.stroke([[254, 250], [270, 250]], 6, "#7a5a3a");
  const face = (x: number, y: number, col: string, s: number) => {
    p.ell(x, y, 30, 28, SKINS[s % 4], 6);
    p.poly([[x - 32, y - 18], [x + 32, y - 18], [x + 26, y - 40], [x - 26, y - 40]], col, 5);
    taper(p, [x - 20, y - 12], [x - 4, y - 4], 6, 3); taper(p, [x + 20, y - 12], [x + 4, y - 4], 6, 3);
    p.dot(x - 10, y + 2, 4); p.dot(x + 10, y + 2, 4); p.arc(x, y + 20, 10, 6, 200, 340, 5);
    p.stroke([[x + 28, y + 10], [x + 44, y - 30]], 9, col); p.ell(x + 46, y - 38, 12, 11, SKINS[s % 4], 5);
  };
  face(150, 220, "#3f6fb5", 0); face(350, 210, "#8c3b4a", 1); face(200, 300, "#5d7a3a", 2); face(330, 300, "#b5653f", 3);
};
/** a big wobbly question mark (240 x 360) */
export const fxQuestion = (p: Pen) => {
  p.line([[70, 110], [80, 60], [130, 34], [180, 60], [186, 116], [130, 160], [122, 220]], "#ffd84a", 34);
  p.ell(122, 296, 26, 26, "#ffd84a", 10);
};
