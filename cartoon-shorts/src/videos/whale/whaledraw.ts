// Our own cartoon seagull + the 2D effects of the exploding-whale short (blast, stink, flies, splats, plan bubble).
// The gull is drawn on the WIDE card (1000 x 1000 design units, soles at y = 975) filling the card; cast.ts scales the
// card to ~0.6 m. Side view faces screen-right (mirror for left). Modes: stand, walk, fly (wings up/down by phase),
// peck. Eyes: norm, greedy (sly lid), shock, happy.
import { Pen, INK, mul, shade, thickAngle } from "./toon";

type P2 = [number, number];
const rad = (d: number) => (d * Math.PI) / 180;
const TAU = Math.PI * 2;
const SH: [number, number, number] = [0.66, 0.68, 0.78];
const rnd = (seed: number, k: number) => { const x = Math.sin(seed * 127.1 + k * 311.7) * 43758.5453; return x - Math.floor(x); };
const ellPts = (cx: number, cy: number, rx: number, ry: number, rot = 0, n = 40): P2[] => {
  const out: P2[] = [];
  for (let i = 0; i < n; i++) { const a = (i / n) * TAU, x = rx * Math.cos(a), y = ry * Math.sin(a); out.push([cx + x * Math.cos(rot) - y * Math.sin(rot), cy + x * Math.sin(rot) + y * Math.cos(rot)]); }
  return out;
};
const curve = (a: P2, k: P2, b: P2, n = 14): P2[] => {
  const c: P2 = [2 * k[0] - (a[0] + b[0]) / 2, 2 * k[1] - (a[1] + b[1]) / 2], out: P2[] = [];
  for (let i = 0; i <= n; i++) { const t = i / n, s = 1 - t; out.push([s * s * a[0] + 2 * s * t * c[0] + t * t * b[0], s * s * a[1] + 2 * s * t * c[1] + t * t * b[1]]); }
  return out;
};

export type GullMode = "stand" | "walk" | "fly" | "peck";
export type GullEye = "norm" | "greedy" | "shock" | "happy";
export type GullOpts = { mode?: GullMode; phase?: number; eye?: GullEye; blink?: number; light?: number; beak?: number };

const WHITE = "#f8f7f1", GREY = "#a3afbe", TIP = "#2b2b33", BEAK = "#f4c430", SPOT = "#d9382e", LEG = "#efa27c";

const gullEye = (p: Pen, x: number, y: number, eye: GullEye, lid: number, ow: number) => {
  const r = eye === "shock" ? 30 : 25;
  if (eye === "happy" || lid >= 0.99) { p.arc(x, y + 4, r * 0.8, r * 0.6, 200, 340, 7); return; }
  p.ell(x, y, r, r, "#ffffff", ow * 0.5);
  p.dot(x + (eye === "shock" ? 0 : 5), y + 2, eye === "shock" ? 7 : 11);
  const k = Math.max(lid, eye === "greedy" ? 0.45 : 0);
  if (k > 0) {
    const g = p.g; g.save(); p.path(ellPts(x, y, r, r), true); g.clip();
    p.poly([[x - r - 4, y - r - 4], [x + r + 4, y - r - 4], [x + r + 4, y - r + 2 * r * k + (eye === "greedy" ? 8 : 0)], [x - r - 4, y - r + 2 * r * k - (eye === "greedy" ? 6 : 0)]], WHITE, 0);
    g.restore();
    p.stroke([[x - r, y - r + 2 * r * k - (eye === "greedy" ? 6 : 0)], [x + r, y - r + 2 * r * k + (eye === "greedy" ? 8 : 0)]], ow * 0.6);
  }
  if (eye === "greedy") p.stroke([[x - 30, y - 42], [x + 26, y - 30]], 9);
  if (eye === "shock") p.stroke([[x - 26, y - 50], [x + 22, y - 56]], 8);
};

export const gullSide = (p: Pen, o: GullOpts) => {
  const ow = 11, light = o.light ?? rad(-120), thick = thickAngle(light), ph = o.phase ?? 0, mode = o.mode ?? "stand";
  const fly = mode === "fly", peck = mode === "peck" ? Math.max(0, Math.sin(ph * TAU)) : 0;
  const by = fly ? 520 : 640, bx = 470;
  // legs (behind the body)
  if (!fly) {
    const sw = mode === "walk" ? Math.sin(ph * TAU) * 60 : 0;
    for (const [hx, d] of [[430, -1], [520, 1]] as const) {
      const fx = hx + d * sw * 0.5 + 10, kx = hx + d * sw * 0.25;
      p.line([[hx, by + 110], [kx, 880], [fx, 960]], LEG, 13, true);
      p.poly([[fx - 40, 975], [fx + 46, 975], [fx + 6, 948]], LEG, 7);
    }
  }
  // the far wing in flight
  const flap = fly ? Math.sin(ph * TAU) : 0;
  if (fly) {
    const tipY = by - 60 - 300 * flap;
    p.poly([[bx - 40, by - 50], [bx + 120, by - 70], [bx - 10, tipY - 40], [bx - 150, tipY]], shade(GREY, 0.8), ow);
  }
  // tail + body
  p.poly([[bx - 200, by - 40], [bx - 330, by - 70 + (fly ? 30 : 0)], [bx - 320, by + 10], [bx - 190, by + 40]], WHITE, ow);
  p.poly([[bx - 300, by - 66 + (fly ? 30 : 0)], [bx - 330, by - 70 + (fly ? 30 : 0)], [bx - 322, by - 6], [bx - 290, by - 10]], TIP, 0);
  const body = ellPts(bx, by, 250, fly ? 120 : 150, fly ? 0 : rad(-6));
  p.shadedFill(body, WHITE, mul(WHITE, SH), light, 250);
  p.inkRing(body, ow, thick);
  // the folded near wing (stand) / the near wing in flight
  if (fly) {
    const tipY = by - 20 - 330 * flap;
    const w: P2[] = [[bx - 70, by - 30], [bx + 140, by - 40], [bx + 40, tipY + 10], [bx - 60, tipY - 30], [bx - 220, tipY + 30]];
    p.poly(w, GREY, ow);
    p.poly([[bx - 60, tipY - 30], [bx - 220, tipY + 30], [bx - 150, tipY + 40], [bx - 20, tipY + 2]], TIP, ow * 0.6);
    for (let k = 0; k < 3; k++) p.dot(bx - 150 + k * 45, tipY + 18 - k * 14, 9, "#ffffff");
  } else {
    const w: P2[] = [...curve([bx + 170, by - 70], [bx, by - 130], [bx - 260, by - 60]), [bx - 330, by - 30], ...curve([bx - 250, by + 10], [bx - 20, by + 60], [bx + 180, by - 20])];
    p.gradFill(w, GREY, shade(GREY, 0.8), light, 0.3);
    p.poly(w, null, ow);
    p.poly([[bx - 220, by - 58], [bx - 330, by - 30], [bx - 250, by + 6], [bx - 180, by - 10]], TIP, ow * 0.6);
    for (let k = 0; k < 3; k++) p.dot(bx - 270 + k * 30, by - 20 + k * 4, 8, "#ffffff");
  }
  // neck + head
  const hx = bx + 230 + 40 * peck, hy = (fly ? by - 70 : by - 210) + 150 * peck;
  p.poly([[bx + 120, by - 90], [hx - 40, hy - 40], [hx + 30, hy + 60], [bx + 200, by + 20]], WHITE, 0);
  const hp = ellPts(hx, hy, 105, 92);
  p.shadedFill(hp, WHITE, mul(WHITE, SH), light, 105);
  p.inkRing(hp, ow, thick);
  // beak: yellow, a hooked tip, the red spot on the lower bill; open by `beak`
  const open = 34 * (o.beak ?? 0), bxx = hx + 80;
  p.poly([[bxx, hy - 10], [bxx + 140, hy + 12], [bxx + 150, hy + 34], [bxx + 128, hy + 26], [bxx, hy + 24]], BEAK, ow * 0.8);
  p.poly([[bxx, hy + 24 + open * 0.2], [bxx + 120, hy + 30 + open], [bxx + 118, hy + 48 + open], [bxx, hy + 44 + open * 0.2]], BEAK, ow * 0.8);
  p.dot(bxx + 100, hy + 40 + open * 0.8, 10, SPOT);
  gullEye(p, hx + 20, hy - 18, o.eye ?? "norm", o.blink ?? 0, ow);
};

// ---------------- effects ----------------
const lerpHex = (a: string, b: string, t: number) => {
  const pa = [1, 3, 5].map((i) => parseInt(a.slice(i, i + 2), 16)), pb = [1, 3, 5].map((i) => parseInt(b.slice(i, i + 2), 16));
  return "#" + pa.map((v, i) => Math.round(v + (pb[i] - v) * t).toString(16).padStart(2, "0")).join("");
};
/** the blast on a 1000 x 1000 canvas: a white-yellow core, an orange fireball of round puffs, a grey smoke rim that
 *  takes over as t runs 0..1, sand thrown in a crown; ground line at y = 900 */
export const fxBoom = (p: Pen, t: number, seed = 1) => {
  const GY = 985, R = 120 + 300 * Math.min(1, t * 1.6), cx = 500, cy = Math.min(GY - 260 - 220 * t, GY - R * 1.08);
  const fire = Math.max(0, 1 - t * 1.4);
  // sand crown: brown spikes from the ground
  for (let i = 0; i < 11; i++) {
    const a = rad(-170 + i * 16 + 6 * rnd(seed, i)), L = (200 + 260 * rnd(seed, i + 20)) * Math.min(1, t * 2.5 + 0.2);
    p.poly([[cx - 40 + i * 8, GY], [cx + Math.cos(a) * L, GY + Math.sin(a) * L], [cx + 40 + i * 8 - 80, GY]], i % 2 ? "#c9a878" : "#b08a5c", 8);
  }
  // the stem of smoke down to the ground
  for (let k = 0; k < 4; k++) p.ell(cx + 18 * Math.sin(k * 2.1), GY - 20 - k * (GY - 20 - cy) / 4, 70 + 30 * t, 60, lerpHex("#f08a2c", "#8f8a94", Math.min(1, t * 1.8 + 0.2)), 9);
  const ring = (rr: number, col: string, n: number, sz: number, off: number) => {
    for (let i = 0; i < n; i++) { const a = (i / n) * TAU + off, j = 0.85 + 0.3 * rnd(seed + n, i); p.ell(cx + Math.cos(a) * rr * j, cy + Math.sin(a) * rr * 0.8 * j, sz * j, sz * 0.9 * j, col, 10); }
  };
  ring(R * 0.85, lerpHex("#e2723a", "#7f7a86", Math.min(1, t * 1.5)), 13, R * 0.42, 0.2);
  ring(R * 0.55, lerpHex("#f5a23a", "#9a95a0", Math.min(1, t * 1.3)), 9, R * 0.4, 0.5);
  // the hot core cools smoothly to smoke (no pop when the fire is gone)
  const cool = Math.min(1, Math.max(0, (t - 0.45) / 0.55));
  ring(R * 0.3, cool <= 0 ? lerpHex("#ffd84a", "#f5a23a", 1 - fire) : lerpHex("#f5a23a", "#a7a2ac", cool), 7, R * 0.34, 0.1);
  if (fire > 0) p.ell(cx, cy, R * 0.32 * fire + 10, R * 0.28 * fire + 10, "#fff6c8", 0);
};
/** three wavy stink lines rising (300 x 400), t loops 0..1 */
export const fxStink = (p: Pen, t: number) => {
  for (let k = 0; k < 3; k++) {
    const pts: P2[] = [], x0 = 70 + k * 80, u = (t + k * 0.33) % 1;
    for (let i = 0; i <= 12; i++) { const y = 380 - i * 26 - 60 * u; pts.push([x0 + 22 * Math.sin(i * 0.9 + u * TAU + k), y]); }
    p.line(pts, "#9ccb5a", 16, true);
  }
};
/** flies buzzing in loops (400 x 300) */
export const fxFlies = (p: Pen, t: number) => {
  for (let k = 0; k < 5; k++) {
    const a = t * TAU * (1 + k * 0.3) + k * 1.3, x = 200 + 140 * Math.cos(a) * (0.5 + 0.1 * k), y = 150 + 70 * Math.sin(a * 1.7 + k);
    p.ell(x - 9, y - 12, 12, 8, "rgba(255,255,255,0.9)", 4, 0, 360, -30); p.ell(x + 9, y - 12, 12, 8, "rgba(255,255,255,0.9)", 4, 0, 360, 30);
    p.ell(x, y, 11, 9, INK, 0);
  }
};
/** a splat (400 x 400): blob with droplets; col = blubber pink-grey or jelly green */
export const fxSplat = (p: Pen, seed: number, col = "#d99a8e") => {
  const pts: P2[] = [];
  for (let i = 0; i < 28; i++) { const a = (i / 28) * TAU, r = 110 * (i % 2 ? 0.75 + 0.3 * rnd(seed, i) : 1 + 0.35 * rnd(seed, i)); pts.push([200 + r * Math.cos(a), 200 + r * Math.sin(a) * 0.8]); }
  p.poly(pts, col, 9);
  p.ell(170, 180, 36, 22, shade(col, 1.18), 0);
  for (let k = 0; k < 6; k++) { const a = rnd(seed, k + 40) * TAU, d = 150 + 30 * rnd(seed, k + 50), r = 10 + 12 * rnd(seed, k + 60); p.ell(200 + d * Math.cos(a), 200 + d * Math.sin(a) * 0.8, r, r, col, 6); }
};
/** a thought cloud (600 x 500) with the plan drawn in it: 0 = the whale, 1 = the whale in little pieces, 2 = a gull
 *  eating the pieces */
export const fxPlan = (p: Pen, step: number) => {
  for (const [x, y, r] of [[150, 210, 110], [300, 160, 140], [450, 210, 110], [300, 280, 140], [200, 300, 90], [400, 300, 90]] as const) p.ell(x, y, r, r * 0.85, "#ffffff", 9);
  for (const [x, y, r] of [[150, 210, 110], [300, 160, 140], [450, 210, 110], [300, 280, 140], [200, 300, 90], [400, 300, 90]] as const) p.ell(x, y, r - 8, (r - 8) * 0.85, "#ffffff", 0);
  p.ell(150, 430, 30, 24, "#ffffff", 8); p.ell(110, 475, 16, 13, "#ffffff", 7);
  const W = "#5f6672";
  if (step === 0) {
    p.poly([[160, 250], [190, 190], [360, 180], [420, 200], [430, 270], [200, 280]], W, 8);
    p.poly([[160, 250], [110, 210], [120, 280]], W, 8); p.dot(400, 220, 6, "#ffffff");
  } else {
    for (let k = 0; k < 9; k++) { const x = 150 + (k % 3) * 70 + 20 * rnd(3, k), y = 170 + Math.floor(k / 3) * 55 + 10 * rnd(4, k); p.ell(x, y, 20 + 6 * rnd(5, k), 15, k % 2 ? W : "#d99a8e", 6); }
    if (step === 2) {
      // a gull head with a piece in its beak
      p.ell(420, 230, 50, 44, "#ffffff", 8); p.poly([[455, 230], [520, 242], [455, 254]], BEAK, 6); p.dot(424, 218, 7);
      p.ell(512, 244, 14, 11, "#d99a8e", 5);
    }
  }
};
/** a counted number in a white bubble (240 x 240) */
export const fxCount = (p: Pen, n: number | string) => {
  p.ell(120, 120, 100, 100, "#ffffff", 10);
  const g = p.g; g.fillStyle = INK; g.font = "900 130px sans-serif"; g.textAlign = "center"; g.textBaseline = "middle"; g.fillText(String(n), 120, 128);
};
/** a stick of dynamite (120 x 360): red tube, a paper band, the fuse */
export const fxStick = (p: Pen) => {
  p.poly([[30, 340], [90, 340], [90, 90], [30, 90]], "#d9382e", 8);
  p.poly([[30, 200], [90, 200], [90, 240], [30, 240]], "#f2ead8", 6);
  p.line([[60, 90], [64, 50], [80, 26]], "#6a5a4a", 6, true);
};
/** speed / motion lines behind a flying chunk (300 x 120) */
export const fxStreak = (p: Pen) => {
  for (let k = 0; k < 3; k++) p.stroke([[20 + k * 20, 30 + k * 30], [260, 30 + k * 30]], 8, "rgba(255,255,255,0.85)");
};
export const fxWhale = { BEAK, WHITE, GREY };
export { shade };
