// Our own cartoon rooster (a silver-laced Wyandotte: white with black lacing, a black tail, yellow legs) and the 2D
// effects of the headless-chicken short. Drawn on the WIDE card (1000 x 1000 design units, soles at y = 975), side view
// facing screen-right (mirror for left). Headless: the neck ends in a rounded pink stump (no gore, a cartoon).
//   modes: stand, walk (leg cycle), peck (neck bob), crow (neck stretched up, chest out), flap (wings up/down), run
import { Pen, INK, mul, shade, thickAngle } from "./toon";

type P2 = [number, number];
const rad = (d: number) => (d * Math.PI) / 180;
const TAU = Math.PI * 2;
const SH: [number, number, number] = [0.68, 0.68, 0.78];
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

export type HenMode = "stand" | "walk" | "peck" | "crow" | "flap" | "run" | "drink";
export type HenOpts = { mode?: HenMode; phase?: number; head?: boolean; eye?: "norm" | "shock" | "happy" | "angry"; blink?: number; light?: number; seed?: number; col?: string; proud?: boolean };

const WHITE = "#f6f3ea", LACE = "#2a2630", TAIL = "#24212b", LEG = "#f2b630", COMB = "#e03a32", BEAK = "#f2b630", STUMP = "#f4a7a0";

export const henSide = (p: Pen, o: HenOpts) => {
  const ow = 11, light = o.light ?? rad(-120), thick = thickAngle(light), ph = o.phase ?? 0, mode = o.mode ?? "stand", head = o.head ?? false;
  const body = o.col ?? WHITE;
  const run = mode === "run", bob = mode === "walk" || run ? Math.abs(Math.sin(ph * TAU)) * (run ? 26 : 14) : 0;
  const bx = 450, by = 610 - bob;
  // legs (behind)
  const sw = mode === "walk" ? Math.sin(ph * TAU) * 70 : run ? Math.sin(ph * TAU) * 120 : 0;
  for (const [hx, d] of [[420, -1], [500, 1]] as const) {
    const fx = hx + d * sw * 0.5 + 20, lift = Math.max(0, -d * Math.sin(ph * TAU)) * (mode === "walk" ? 40 : run ? 80 : 0);
    p.line([[hx, by + 120], [hx + 18 + d * sw * 0.2, 840 - lift * 0.5], [fx, 955 - lift]], LEG, 14, true);
    p.stroke([[fx - 40, 972 - lift], [fx + 52, 966 - lift]], 9, LEG); p.stroke([[fx, 968 - lift], [fx + 40, 938 - lift]], 8, LEG);
  }
  // tail: a fan of dark sickle feathers
  for (let k = 0; k < 5; k++) {
    const a = rad(-150 + k * 18), L = 230 - k * 18, b0: P2 = [bx - 170, by - 40];
    const tip: P2 = [b0[0] + Math.cos(a) * L, b0[1] + Math.sin(a) * L];
    p.poly([...curve(b0, [b0[0] + Math.cos(a + 0.4) * L * 0.6, b0[1] + Math.sin(a + 0.4) * L * 0.6], tip), ...curve(tip, [b0[0] + Math.cos(a - 0.2) * L * 0.5, b0[1] + Math.sin(a - 0.2) * L * 0.5], [b0[0] + 30, b0[1] + 40])], k % 2 ? TAIL : shade(TAIL, 1.25), 8);
  }
  // body: a round egg with laced feathers
  const flap = mode === "flap" ? Math.sin(ph * TAU) : 0;
  const bp = ellPts(bx, by, 230, 170, rad(o.proud || mode === "crow" ? -14 : -6));
  p.shadedFill(bp, body, mul(body, SH), light, 230);
  p.clip(bp, () => { for (let r = 0; r < 4; r++) for (let k = 0; k < 7; k++) { const x = bx - 170 + k * 58 + (r % 2) * 29, y = by - 90 + r * 58; p.arc(x, y, 26, 20, 20, 160, 6, LACE); } });
  p.inkRing(bp, ow, thick);
  // wing
  const wy = by - 20 - 160 * Math.max(0, flap);
  const wing: P2[] = flap > 0.05 ? [[bx - 60, by - 30], [bx + 70, by - 40], [bx - 10, wy - 120], [bx - 160, wy - 60]] : [...curve([bx + 110, by - 20], [bx - 10, by - 70], [bx - 170, by + 10]), ...curve([bx - 170, by + 10], [bx - 30, by + 90], [bx + 110, by - 20])];
  p.poly(wing, shade(body, 0.9), ow * 0.8);
  if (flap <= 0.05) for (let k = 0; k < 3; k++) p.arc(bx - 100 + k * 50, by + 20, 30, 18, 20, 160, 6, LACE);
  // neck + head (or the stump)
  const crow = mode === "crow", peck = mode === "peck" ? Math.max(0, Math.sin(ph * TAU)) : 0, drink = mode === "drink";
  const nx = bx + 170 + 40 * peck, ny = by - 150 - (crow ? 120 : 0) + 170 * peck + (drink ? -90 : 0);
  const neck: P2[] = [[bx + 90, by - 110], [nx - 52, ny + 10], [nx + 58, ny + 30], [bx + 215, by - 20]];
  p.poly(neck, body, 0);
  p.stroke(curve([bx + 90, by - 110], [nx - 70, (by - 110 + ny) / 2], [nx - 52, ny + 10]), ow, INK);
  p.stroke(curve([bx + 215, by - 20], [nx + 70, (by + ny) / 2], [nx + 58, ny + 30]), ow, INK);
  for (let k = 0; k < 3; k++) p.arc(nx - 20 + k * 22, ny + 60 + k * 30, 16, 12, 20, 160, 5, LACE);
  if (!head) {
    // the stump: a rounded pink top
    p.ell(nx + 3, ny + 18, 56, 24, STUMP, ow * 0.9, 0, 360, crow ? -8 : 0);
    p.ell(nx - 6, ny + 12, 22, 8, shade(STUMP, 1.12), 0);
    return;
  }
  const hx = nx + 10, hy = ny - 50;
  // comb, beak, wattle, head
  p.poly([[hx - 60, hy - 50], [hx - 50, hy - 110], [hx - 20, hy - 70], [hx - 5, hy - 128], [hx + 20, hy - 72], [hx + 45, hy - 112], [hx + 55, hy - 52]], COMB, ow * 0.8);
  p.ell(hx + 62, hy + 58, 20, 34, COMB, ow * 0.7);
  const hp = ellPts(hx, hy, 80, 72);
  p.shadedFill(hp, body, mul(body, SH), light, 80); p.inkRing(hp, ow, thick);
  p.poly([[hx + 70, hy - 6], [hx + 140, hy + 14], [hx + 70, hy + 34]], BEAK, ow * 0.7);
  const ex = hx + 18, ey = hy - 12, eye = o.eye ?? "norm";
  if (eye === "happy" || (o.blink ?? 0) >= 0.99) p.arc(ex, ey + 6, 18, 12, 200, 340, 7);
  else { p.ell(ex, ey, eye === "shock" ? 26 : 20, eye === "shock" ? 26 : 20, "#ffffff", ow * 0.5); p.dot(ex + 4, ey + 2, eye === "shock" ? 6 : 9); if (eye === "angry") p.stroke([[ex - 22, ey - 30], [ex + 22, ey - 18]], 8); }
};

// ---------------- effects ----------------
/** a gurgly "crow": three bubbles and two wobbly sound arcs (300 x 300) */
export const fxGurgle = (p: Pen, t: number) => {
  for (let k = 0; k < 3; k++) { const u = (t + k / 3) % 1, r = 12 + 18 * u; p.ell(80 + k * 30 + 20 * Math.sin(u * 9), 250 - 200 * u, r, r, `rgba(255,255,255,${(1 - u).toFixed(2)})`, 5); }
  for (let k = 0; k < 2; k++) p.arc(150, 230, 90 + k * 40, 80 + k * 40, -120, -30, 9, "#ffd84a");
};
/** a white impact/swoosh star for the axe (500 x 500) is fxBurst in toon; a feather (200 x 120) */
export const fxFeather = (p: Pen, spin: number) => {
  const c = Math.cos(spin), s = Math.sin(spin), P = (u: number, v: number): P2 => [100 + u * c - v * s, 60 + u * s + v * c];
  const vane: P2[] = []; for (let k = 0; k <= 10; k++) vane.push(P(-70 + 140 * (k / 10), -22 * Math.sin((k / 10) * Math.PI))); for (let k = 10; k >= 0; k--) vane.push(P(-70 + 140 * (k / 10), 18 * Math.sin((k / 10) * Math.PI)));
  p.poly(vane, "#f6f3ea", 5); p.stroke([P(-80, 0), P(70, 0)], 4, "#8a8590");
};
/** a counted number in a white bubble (240 x 240) */
export const fxCount = (p: Pen, n: number | string) => {
  p.ell(120, 120, 100, 100, "#ffffff", 10);
  const g = p.g; g.fillStyle = INK; g.font = `900 ${String(n).length > 2 ? 86 : 120}px sans-serif`; g.textAlign = "center"; g.textBaseline = "middle"; g.fillText(String(n), 120, 128);
};
/** a price tag / money bubble with text (320 x 200) */
export const fxTag = (p: Pen, text: string, col = "#7ac46a") => {
  p.poly([[20, 100], [70, 30], [300, 30], [300, 170], [70, 170]], col, 9);
  p.ell(70, 100, 14, 14, "#ffffff", 6);
  const g = p.g; g.fillStyle = INK; g.font = `900 ${text.length > 5 ? 56 : 72}px sans-serif`; g.textAlign = "center"; g.textBaseline = "middle"; g.fillText(text, 190, 104);
};
/** a scale's dial face (300 x 300), needle by pounds 0..10 */
export const fxScale = (p: Pen, lb: number) => {
  p.ell(150, 150, 130, 130, "#f4f1ea", 10);
  for (let k = 0; k <= 10; k++) { const a = rad(-210 + 24 * k); p.stroke([[150 + 100 * Math.cos(a), 150 + 100 * Math.sin(a)], [150 + 118 * Math.cos(a), 150 + 118 * Math.sin(a)]], k % 5 ? 4 : 8); }
  const g = p.g; g.fillStyle = INK; g.font = "900 38px sans-serif"; g.textAlign = "center"; g.fillText("LB", 150, 218);
  const a = rad(-210 + 24 * lb);
  p.stroke([[150, 150], [150 + 92 * Math.cos(a), 150 + 92 * Math.sin(a)]], 9, "#d9382e"); p.dot(150, 150, 12);
};
/** cough puffs (300 x 300) */
export const fxCough = (p: Pen, t: number) => {
  for (let k = 0; k < 4; k++) { const a = rad(-30 - k * 25), d = 40 + 140 * t, r = 26 * (1 - 0.5 * t) + 8; p.ell(80 + Math.cos(a) * d, 200 + Math.sin(a) * d, r, r * 0.8, `rgba(255,255,255,${(1 - t).toFixed(2)})`, 6); }
};
/** "Zzz" (240 x 240) */
export const fxZzz = (p: Pen, t: number) => {
  const g = p.g; g.fillStyle = "#ffffff"; g.strokeStyle = INK; g.lineWidth = 8; g.textAlign = "center";
  for (let k = 0; k < 3; k++) { const u = (t + k / 3) % 1; g.font = `900 ${40 + 30 * u}px sans-serif`; g.globalAlpha = 1 - u; g.strokeText("Z", 60 + 120 * u, 200 - 160 * u); g.fillText("Z", 60 + 120 * u, 200 - 160 * u); }
  g.globalAlpha = 1;
};
export const fxColors = { WHITE, LACE, COMB, STUMP };
export { shade };

/** diagram card (600 x 700): Mike's neck in cut-away, the big vein (blue) running up beside the windpipe; stage 1 =
 *  the axe line passes ABOVE the vein's opening (a green tick), stage 2 = a red clot plugs the cut */
export const fxVein = (p: Pen, stage: number) => {
  p.poly([[40, 40], [560, 40], [560, 660], [40, 660]], "#fbf6e8", 10);
  // neck outline
  p.poly([[200, 640], [190, 300], [220, 170], [380, 170], [410, 300], [400, 640]], "#f6f3ea", 9);
  p.ell(300, 170, 80, 26, STUMP, 8);
  // windpipe + vein
  p.poly([[262, 630], [262, 190], [292, 190], [292, 630]], "#f2c9be", 6);
  p.poly([[330, 630], [330, 214], [360, 214], [360, 630]], "#5a8fd2", 6);
  // the axe line, dashed, above the vein top
  for (let x = 120; x < 480; x += 40) p.stroke([[x, 168], [x + 22, 168]], 8, "#d9382e");
  if (stage >= 1) p.stroke([[420, 250], [450, 280], [510, 200]], 16, "#3aa64a");
  if (stage >= 2) { p.ell(300, 176, 46, 20, "#a8222a", 8); p.ell(286, 170, 14, 6, "#e0565a", 0); }
  const g = p.g; g.font = "900 56px Arial"; g.textAlign = "center"; g.fillStyle = "#2f5fa8"; g.fillText("VEIN", 470, 470);
  p.stroke([[420, 450], [366, 420]], 8, "#2f5fa8");
  if (stage >= 2) { g.fillStyle = "#a8222a"; g.fillText("CLOT", 140, 120); p.stroke([[190, 130], [250, 165]], 8, "#a8222a"); }
};
/** diagram card (600 x 700): the stump with the brain stem kept (a purple knot at the top), three icons light up as they
 *  are named: 1 lungs (breathing), 2 heart, 3 foot (walking) */
export const fxStem = (p: Pen, stage: number) => {
  p.poly([[40, 40], [560, 40], [560, 660], [40, 660]], "#fbf6e8", 10);
  p.poly([[220, 640], [210, 330], [240, 230], [360, 230], [390, 330], [380, 640]], "#f6f3ea", 9);
  p.ell(300, 230, 70, 24, STUMP, 8);
  p.ell(300, 262, 34, 26, "#9a6ad2", 8); p.stroke([[300, 288], [300, 470]], 18, "#9a6ad2");
  const icon = (k: number, x: number, y: number, draw: () => void) => { const on = stage >= k; p.ell(x, y, 62, 62, on ? "#fff2a0" : "#e9e4d8", 8); draw(); if (on) for (let r = 0; r < 8; r++) { const a = (r / 8) * TAU; p.stroke([[x + 72 * Math.cos(a), y + 72 * Math.sin(a)], [x + 88 * Math.cos(a), y + 88 * Math.sin(a)]], 6, "#f2b630"); } };
  icon(1, 130, 120, () => { p.ell(112, 126, 18, 30, "#e88a9a", 6); p.ell(148, 126, 18, 30, "#e88a9a", 6); p.stroke([[130, 90], [130, 110]], 8); });
  icon(2, 470, 120, () => { p.poly([[470, 158], [432, 118], [440, 96], [458, 94], [470, 108], [482, 94], [500, 96], [508, 118]], "#d9382e", 6); });
  const g = p.g; g.font = "900 46px Arial"; g.textAlign = "center"; g.fillStyle = "#6a3aa8"; g.fillText("BRAIN STEM", 210, 600);
  icon(3, 470, 520, () => { p.stroke([[470, 490], [470, 540]], 10, "#f2b630"); p.stroke([[440, 548], [500, 548]], 10, "#f2b630"); p.stroke([[470, 548], [496, 528]], 9, "#f2b630"); });
};
/** a dollar bill (260 x 120) */
export const fxBill = (p: Pen) => {
  p.poly([[10, 10], [250, 10], [250, 110], [10, 110]], "#9ad08a", 7);
  p.ell(130, 60, 30, 34, "#6aa85a", 5);
  const g = p.g; g.fillStyle = "#2f5a2a"; g.font = "900 46px Georgia"; g.textAlign = "center"; g.textBaseline = "middle"; g.fillText("$", 130, 62); g.fillText("1", 40, 36); g.fillText("1", 220, 86);
};
/** milk drops (60 x 90) */
export const fxDrop = (p: Pen) => { p.poly([[30, 6], [50, 52], [30, 84], [10, 52]], "#ffffff", 5); };
/** "!" (200 x 360) */
export const fxExclaim = (p: Pen) => { p.poly([[70, 30], [140, 30], [124, 230], [86, 230]], "#ff5a3c", 12); p.ell(105, 300, 36, 36, "#ff5a3c", 12); };
/** a camera flash star (500 x 500) */
export const fxFlashStar = (p: Pen, t: number) => {
  const c = 250, r = 60 + 190 * (1 - (1 - t) ** 3);
  for (let i = 0; i < 12; i++) { const a = (i / 12) * TAU; p.poly([[c + 30 * Math.cos(a + 0.2), c + 30 * Math.sin(a + 0.2)], [c + r * Math.cos(a), c + r * Math.sin(a)], [c + 30 * Math.cos(a - 0.2), c + 30 * Math.sin(a - 0.2)]], "#ffffff", 0); }
  p.ell(c, c, 50 * (1 - t) + 10, 50 * (1 - t) + 10, "#ffffff", 0);
};

/** a dashed red aim line with a little arrowhead (600 x 120) */
export const fxAim = (p: Pen) => {
  for (let x = 20; x < 500; x += 60) p.stroke([[x, 60], [x + 34, 60]], 14, "#d9382e");
  p.poly([[500, 30], [580, 60], [500, 90]], "#d9382e", 6);
};
/** a big eyedropper held over the neck (120 x 400) */
export const fxDropper = (p: Pen) => {
  p.ell(60, 70, 42, 60, "#d9382e", 8);
  p.poly([[44, 120], [76, 120], [70, 360], [50, 360]], "#e9f4f6", 7);
  p.poly([[50, 250], [70, 250], [70, 358], [50, 358]], "#ffffff", 0);
};
