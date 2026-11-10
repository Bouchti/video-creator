// The emu: our own cartoon bird in the cast's construction (plum thick-thin ink, painted crescent shading, deadpan
// dot eyes). Drawn on a WIDE card: design space 1000 x 1000 units (soles at y = 975), the same 2.16 mm per unit as
// the people, so an emu stands ~1.75 m to the top of its head. Side view faces screen-right (mirror for left).
//   modes: stand, walk, run (big strides, neck forward), peck (head down in the wheat), look (tall lookout neck),
//   alarm (lookout, beak open, plumes up), salute (a wing tip raised to the hat brim)
import { Pen, INK, mul, shade, mix, thickAngle } from "./toon";

type P2 = [number, number];
const rad = (d: number) => (d * Math.PI) / 180;
const TAU = Math.PI * 2;
const SH: [number, number, number] = [0.62, 0.62, 0.72];
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
/** two-bone leg with the joint bending BACK (-x): the emu's "backward knee" (really its ankle) */
const ikBack = (hip: P2, foot: P2, l1: number, l2: number): P2 => {
  const dx = foot[0] - hip[0], dy = foot[1] - hip[1], d = Math.max(1, Math.min(Math.hypot(dx, dy), l1 + l2 - 0.5));
  const A = Math.acos(Math.max(-1, Math.min(1, (l1 * l1 + d * d - l2 * l2) / (2 * l1 * d)))), k = Math.atan2(dy, dx) + A;
  return [hip[0] + l1 * Math.cos(k), hip[1] + l1 * Math.sin(k)];
};

export type EmuMode = "stand" | "walk" | "run" | "peck" | "look" | "alarm" | "salute";
export type EmuEye = "norm" | "shock" | "smug" | "angry" | "proud";
export type EmuOpts = {
  mode?: EmuMode; phase?: number; eye?: EmuEye; blink?: number; dark?: boolean; hat?: "slouch" | "helmet" | null;
  /** head turn for the lookout: -1 looks back over the shoulder .. 1 forward */
  turn?: number; light?: number; seed?: number; beak?: number;
};

const PLUME = "#7a5c42", PLUME_DARK = "#3b302c", NECK = "#8ea2c4", HEAD = "#4a4250", BILL = "#3a3540", LEG = "#7f8494", EYE = "#ffffff";
const KHAKI = "#a08a58";

/** shaggy fringe: perturb an ellipse outline with feather points along its lower half and tail */
const shag = (cx: number, cy: number, rx: number, ry: number, rot: number, seed: number, n = 64): P2[] => {
  const out: P2[] = [];
  for (let i = 0; i < n; i++) {
    const a = (i / n) * TAU, low = Math.max(0, Math.sin(a)), back = Math.max(0, -Math.cos(a));
    const tooth = i % 2 ? 1 : 0, j = 0.6 + 0.4 * rnd(seed, i);
    const r = 1 + (0.02 + 0.1 * low + 0.06 * back) * tooth * j;
    let x = rx * Math.cos(a) * r, y = ry * Math.sin(a) * r;
    if (back > 0.3 && low > 0.2) { x -= 26 * back * low; y += 30 * back * low; } // the droopy tail skirt
    out.push([cx + x * Math.cos(rot) - y * Math.sin(rot), cy + x * Math.sin(rot) + y * Math.cos(rot)]);
  }
  return out;
};

const slouchSide = (p: Pen, hx: number, hy: number, s: number, ow: number) => {
  // brim forward, crown dented, the back of the brim pinned up with the badge (rising sun)
  p.poly([[hx - 32 * s, hy - 32 * s], [hx - 44 * s, hy - 86 * s], [hx - 24 * s, hy - 88 * s], [hx - 22 * s, hy - 40 * s]], KHAKI, ow);
  p.ell(hx - 33 * s, hy - 66 * s, 8 * s, 6 * s, "#e8c45a", ow * 0.5);
  p.ell(hx + 14 * s, hy - 34 * s, 74 * s, 12 * s, shade(KHAKI, 0.88), ow, -4);
  p.poly([[hx - 30 * s, hy - 36 * s], [hx - 26 * s, hy - 74 * s], [hx - 4 * s, hy - 86 * s], [hx + 12 * s, hy - 80 * s], [hx + 34 * s, hy - 84 * s], [hx + 46 * s, hy - 66 * s], [hx + 48 * s, hy - 38 * s]], KHAKI, ow);
  p.poly([[hx - 28 * s, hy - 40 * s], [hx + 48 * s, hy - 42 * s], [hx + 47 * s, hy - 54 * s], [hx - 28 * s, hy - 52 * s]], "#c8b787", ow * 0.6);
};
const slouchFront = (p: Pen, hx: number, hy: number, s: number, ow: number) => {
  p.poly([[hx - 36 * s, hy - 38 * s], [hx - 66 * s, hy - 46 * s], [hx - 70 * s, hy - 92 * s], [hx - 50 * s, hy - 104 * s], [hx - 36 * s, hy - 84 * s]], KHAKI, ow);
  p.ell(hx - 54 * s, hy - 76 * s, 9 * s, 7 * s, "#e8c45a", ow * 0.5);
  p.ell(hx + 14 * s, hy - 36 * s, 72 * s, 13 * s, shade(KHAKI, 0.88), ow);
  p.poly([[hx - 40 * s, hy - 38 * s], [hx - 36 * s, hy - 84 * s], [hx - 10 * s, hy - 98 * s], [hx, hy - 88 * s], [hx + 10 * s, hy - 98 * s], [hx + 36 * s, hy - 84 * s], [hx + 40 * s, hy - 38 * s]], KHAKI, ow);
  p.poly([[hx - 40 * s, hy - 42 * s], [hx + 40 * s, hy - 42 * s], [hx + 39 * s, hy - 56 * s], [hx - 39 * s, hy - 56 * s]], "#c8b787", ow * 0.6);
};
const helmet = (p: Pen, hx: number, hy: number, s: number, ow: number) => {
  // the WWI "soup plate": a wide flat brim, a low dome
  p.ell(hx, hy - 34 * s, 80 * s, 14 * s, "#6f7448", ow);
  const dome: P2[] = []; for (let i = 0; i <= 16; i++) { const a = Math.PI + (i / 16) * Math.PI; dome.push([hx + 48 * s * Math.cos(a), hy - 38 * s + 40 * s * Math.sin(a)]); }
  p.poly(dome, "#7d8452", ow);
};

/** the emu's head: dark feathered skull, a blue face patch, a big round eye, a short flat bill */
const HS = 1.5; // cartoon head scale: the head and eye read from across a paddock
const head = (p: Pen, hx: number, hy: number, dir: number, o: EmuOpts, ow0: number, thick: number, front: boolean) => {
  const g0 = p.g; g0.save(); g0.translate(hx, hy); g0.scale(HS, HS); g0.translate(-hx, -hy);
  try { headIn(p, hx, hy, dir, o, ow0 / HS, thick, front); } finally { g0.restore(); }
};
const headIn = (p: Pen, hx: number, hy: number, dir: number, o: EmuOpts, ow: number, thick: number, front: boolean) => {
  const eye = o.eye ?? "norm", lid = o.blink ?? 0, beak = o.beak ?? (o.mode === "alarm" ? 1 : 0);
  if (front) {
    const hp = ellPts(hx, hy, 50, 46);
    p.shadedFill(hp, HEAD, mul(HEAD, SH), o.light ?? rad(-120), 50);
    p.inkRing(hp, ow, thick);
    for (const s of [-1, 1]) p.ell(hx + s * 22, hy - 2, 21, 22, NECK, 0);
    // bill seen from the front: a short wide wedge pointing down at the viewer
    if (beak > 0) { p.poly([[hx - 20, hy + 16], [hx + 20, hy + 16], [hx + 14, hy + 30], [hx - 14, hy + 30]], "#6a2a32", ow * 0.7); p.poly([[hx - 20, hy + 34 + 16 * beak], [hx + 20, hy + 34 + 16 * beak], [hx, hy + 48 + 16 * beak]], BILL, ow * 0.7); }
    p.poly([[hx - 22, hy + 12], [hx + 22, hy + 12], [hx, hy + 44]], BILL, ow * 0.7);
    for (const s of [-1, 1]) eyeAt(p, hx + s * 22, hy - 6, eye, lid, 0, s, ow);
    if (o.hat === "slouch") slouchFront(p, hx, hy, 1, ow * 0.9);
    if (o.hat === "helmet") helmet(p, hx, hy, 1, ow * 0.9);
    return;
  }
  const hp = ellPts(hx, hy, 52, 42, 0);
  p.shadedFill(hp, HEAD, mul(HEAD, SH), o.light ?? rad(-120), 52);
  p.inkRing(hp, ow, thick);
  p.ell(hx + 10 * dir, hy - 2, 26, 22, NECK, 0);
  // the bill: upper + lower halves, open by `beak`
  const bx = hx + 42 * dir, open = 14 * beak;
  p.poly([[bx - 6 * dir, hy - 12], [bx + 52 * dir, hy - 2 - open * 0.3], [bx - 4 * dir, hy + 6]], BILL, ow * 0.8);
  if (beak > 0) { p.poly([[bx - 4 * dir, hy + 6], [bx + 44 * dir, hy + 6 + open], [bx - 6 * dir, hy + 16]], BILL, ow * 0.8); p.ell(bx + 6 * dir, hy + 6 + open * 0.4, 10, 4 + open * 0.3, "#6a2a32", 0); }
  else p.stroke([[bx + 2 * dir, hy + 2], [bx + 40 * dir, hy]], 2.4);
  eyeAt(p, hx + 12 * dir, hy - 8, eye, lid, dir, dir, ow);
  if (o.hat === "slouch") slouchSide(p, hx, hy, 1, ow * 0.9);
  if (o.hat === "helmet") helmet(p, hx, hy, 1, ow * 0.9);
};
const eyeAt = (p: Pen, x: number, y: number, eye: EmuEye, lid: number, look: number, side: number, ow: number) => {
  const r = eye === "shock" ? 22 : 18;
  p.ell(x, y, r, r, EYE, ow * 0.55);
  if (lid >= 0.99) { p.ell(x, y, r, r, NECK, ow * 0.55); p.stroke([[x - r, y + 2], [x + r, y + 2]], 3.2); return; }
  const pr = eye === "shock" ? 4.5 : 7.5;
  p.dot(x + look * 6, y + 1, pr);
  const g = p.g;
  if (eye === "smug" || eye === "proud" || lid > 0) {
    const k = Math.max(lid, eye === "smug" ? 0.5 : eye === "proud" ? 0.42 : 0);
    g.save(); p.path(ellPts(x, y, r, r), true); g.clip();
    p.poly([[x - r - 2, y - r - 2], [x + r + 2, y - r - 2], [x + r + 2, y - r + 2 * r * k], [x - r - 2, y - r + 2 * r * k]], NECK, 0);
    g.restore();
    p.stroke([[x - r, y - r + 2 * r * k], [x + r, y - r + 2 * r * k]], 3.4);
  }
  if (eye === "angry") p.stroke([[x - 20 * side, y - 30], [x + 18 * side, y - 18]], 6);
  if (eye === "shock") p.stroke([[x - 16, y - 34], [x + 16, y - 36]], 4);
};

/** side view, facing screen-right */
export const emuSide = (p: Pen, o: EmuOpts) => {
  const mode = o.mode ?? "stand", ph = o.phase ?? 0, seed = o.seed ?? 1, light = o.light ?? rad(-120), thick = thickAngle(light), ow = 9;
  const plume = o.dark ? PLUME_DARK : mix(PLUME, "#8a6a4a", rnd(seed, 1) * 0.6), sole = 975;
  // ---- gait ----
  const run = mode === "run", walk = mode === "walk";
  const S = run ? 190 : walk ? 90 : 0, L = run ? 150 : walk ? 60 : 0;
  const bob = run ? 26 * Math.cos(2 * TAU * ph) : walk ? 8 * Math.cos(2 * TAU * ph) : 0;
  let bx = 450, by = (run ? 520 : 500) + bob, tilt = run ? rad(-10) : mode === "peck" ? rad(-6) : mode === "look" || mode === "alarm" ? rad(6) : 0;
  if (mode === "salute") tilt = rad(4);
  const rx = 215, ry = 150;
  // neck base (front-top of the body) and head
  const nb: P2 = [bx + rx * 0.72 * Math.cos(tilt) - (-ry * 0.45) * Math.sin(tilt), by + rx * 0.72 * Math.sin(tilt) + (-ry * 0.45) * Math.cos(tilt)];
  let hd: P2, nk: P2;
  if (run) { hd = [nb[0] + 220, nb[1] - 210 + 10 * Math.sin(2 * TAU * ph)]; nk = [nb[0] + 150, nb[1] - 70]; }
  else if (mode === "peck") { const d = 0.5 + 0.5 * Math.sin(TAU * ph); hd = [nb[0] + 210, 860 + 50 * d]; nk = [nb[0] + 190, nb[1] + 60]; }
  else if (mode === "look" || mode === "alarm" || mode === "salute") { hd = [nb[0] + 50, nb[1] - 280]; nk = [nb[0] + 10, nb[1] - 140]; }
  else { const sw = walk ? 12 * Math.sin(2 * TAU * ph) : 0; hd = [nb[0] + 90 + sw, nb[1] - 250]; nk = [nb[0] + 30 + sw * 0.5, nb[1] - 130]; }
  const dir = mode === "look" || mode === "alarm" ? ((o.turn ?? 1) < 0 ? -1 : 1) : 1;
  // ---- legs (far first, then near): hip under the body, joint back, three toes forward ----
  const hip: P2 = [bx + 10, by + 90];
  const legL1 = 230, legL2 = 250;
  const foot = (k: number): { f: P2; up: number } => {
    if (!S) { const off = k ? 34 : -30; return { f: [bx + 20 + off, sole - 14], up: 0 }; }
    const c = (((ph + k * 0.5) % 1) + 1) % 1;
    if (c < 0.5) { const s = c / 0.5; return { f: [bx + 30 + S / 2 - S * s, sole - 14], up: 0 }; }
    const s = (c - 0.5) / 0.5; return { f: [bx + 30 - S / 2 + S * s, sole - 14 - L * Math.sin(Math.PI * s)], up: Math.sin(Math.PI * s) };
  };
  for (const k of [1, 0]) {
    const { f, up } = foot(k), near = k === 0;
    const hp0: P2 = [hip[0] + (near ? 12 : -12), hip[1]];
    const j = ikBack(hp0, f, legL1, legL2);
    const col = near ? LEG : shade(LEG, 0.78), w = near ? 30 : 26;
    // the feathered "drumstick" at the top of the leg, then the bare scaly shin
    p.line([hp0, lerp(hp0, j, 0.55)], near ? shade(plume, 0.9) : shade(plume, 0.7), w + 22);
    p.line([lerp(hp0, j, 0.45), j, f], col, w);
    for (let i = 1; i < 5; i++) { const q = lerp(j, f, i / 5); p.stroke([[q[0] - 8, q[1]], [q[0] + 8, q[1] + 2]], 2.4, shade(col, 0.7)); }
    // toes: curl up during the swing
    const curl = up * 0.6;
    for (const [len, ang] of [[64, 6], [48, 34], [44, -22]] as const) {
      const a = rad(ang + 40 * curl);
      p.line([f, [f[0] + len * Math.cos(a), f[1] + len * Math.sin(a) * 0.4 + 4]], col, 13);
    }
  }
  // ---- body: shaggy blob, feather strokes, a stubby wing ----
  const body = shag(bx, by, rx, ry, tilt, seed);
  p.gradFill(body, plume, mul(plume, SH), light, 0.3);
  p.clip(body, () => {
    for (let i = 0; i < 46; i++) {
      const a = rnd(seed, 40 + i) * TAU, r = Math.sqrt(rnd(seed, 90 + i)), x = bx + rx * 0.9 * r * Math.cos(a), y = by + ry * 0.85 * r * Math.sin(a);
      const lightTip = i % 3 === 0;
      p.stroke(curve([x, y], [x - 14, y + 14], [x - 32, y + 34], 6), 5, lightTip ? mix(plume, "#e6cfa6", 0.35) : shade(plume, 0.62));
    }
  });
  p.inkRing(body, ow, thick);
  if (mode !== "salute") {
    const wx = bx + 60, wy = by - 10, wing = shag(wx, wy, 64, 34, tilt + rad(18), seed + 3, 28);
    p.gradFill(wing, shade(plume, 0.86), mul(plume, SH), light, 0.3);
    p.inkRing(wing, ow * 0.7, thick);
  }
  // ---- neck: feathered lower part, bare blue upper part ----
  const neck = curve(nb, nk, hd, 16);
  p.line(neck, shade(plume, 0.95), 74);
  p.stroke(neck.slice(7), 52, NECK);
  p.stroke(neck.slice(0, 9), 60, shade(plume, 0.95));
  for (let i = 1; i < 8; i++) { const q = neck[i]; p.stroke([[q[0] - 14, q[1] - 4], [q[0] - 26, q[1] + 16]], 4.5, shade(plume, 0.62)); }
  if (mode === "alarm") for (let i = 0; i < 5; i++) { const q = neck[3 + i]; p.line([q, [q[0] - 40, q[1] - 30 + i * 4]], shade(plume, 0.9), 12); }
  head(p, hd[0], hd[1], dir, o, ow, thick, false);
  if (mode === "salute") {
    // the wing tip up to the hat brim, a proud chest
    wingUp(p, [bx + 110, by - 60], [hd[0] - 30, hd[1] - 40], plume, light, ow, thick, seed);
  }
};

/** front view: body square to the camera, neck straight up, two eyes */
export const emuFront = (p: Pen, o: EmuOpts) => {
  const mode = o.mode ?? "stand", seed = o.seed ?? 1, light = o.light ?? rad(-120), thick = thickAngle(light), ow = 9;
  const plume = o.dark ? PLUME_DARK : mix(PLUME, "#8a6a4a", rnd(seed, 1) * 0.6), sole = 975, ph = o.phase ?? 0;
  const bx = 500, by = 520 + (mode === "walk" ? 8 * Math.cos(2 * TAU * ph) : 0);
  // legs
  for (const s of [-1, 1]) {
    const lift = mode === "walk" ? Math.max(0, Math.sin(TAU * (ph + (s > 0 ? 0.5 : 0)))) * 50 : 0;
    const top: P2 = [bx + s * 50, by + 110], j: P2 = [bx + s * 62, by + 290 - lift * 0.5], f: P2 = [bx + s * 56, sole - 14 - lift];
    p.line([top, lerp(top, j, 0.5)], shade(plume, 0.85), 50);
    p.line([lerp(top, j, 0.4), j, f], LEG, 30);
    for (const a of [-60, 0, 60]) p.line([f, [f[0] + 40 * Math.sin(rad(a)), f[1] + 10]], LEG, 13);
  }
  const body = shag(bx, by, 175, 160, 0, seed);
  p.gradFill(body, plume, mul(plume, SH), light, 0.3);
  p.clip(body, () => {
    for (let i = 0; i < 40; i++) {
      const a = rnd(seed, 40 + i) * TAU, r = Math.sqrt(rnd(seed, 90 + i)), x = bx + 160 * r * Math.cos(a), y = by + 140 * r * Math.sin(a);
      p.stroke(curve([x, y], [x + (x < bx ? -8 : 8), y + 16], [x + (x < bx ? -18 : 18), y + 36], 6), 5, i % 3 ? shade(plume, 0.62) : mix(plume, "#e6cfa6", 0.35));
    }
  });
  p.inkRing(body, ow, thick);
  const hx = bx + (mode === "look" || mode === "alarm" ? 14 * (o.turn ?? 0) : 0), hy = mode === "salute" || mode === "look" || mode === "alarm" ? 190 : 220;
  p.line([[bx, by - 120], [hx, hy + 30]], shade(plume, 0.95), 74);
  p.stroke([[(bx + hx) / 2, (by - 120 + hy) / 2 - 10], [hx, hy + 30]], 50, NECK);
  if (mode === "salute") {
    wingUp(p, [bx + 140, by - 80], [hx + 78, hy - 50], plume, light, ow, thick, seed);
  } else for (const s of [-1, 1]) { const w = shag(bx + s * 150, by - 10, 30, 56, s * rad(-12), seed + 4 + s, 24); p.gradFill(w, shade(plume, 0.86), mul(plume, SH), light, 0.3); p.inkRing(w, ow * 0.7, thick); }
  head(p, hx, hy, 0, o, ow, thick, true);
};
/** the salute: a shaggy wing raised from the shoulder, its feather tips at the hat brim */
const wingUp = (p: Pen, sh: P2, tip: P2, plume: string, light: number, ow: number, thick: number, seed: number) => {
  const cx = (sh[0] + tip[0]) / 2, cy = (sh[1] + tip[1]) / 2, len = Math.hypot(tip[0] - sh[0], tip[1] - sh[1]), rot = Math.atan2(tip[1] - sh[1], tip[0] - sh[0]);
  const w = shag(cx, cy, len / 2, 44, rot, seed + 9, 36);
  p.gradFill(w, shade(plume, 0.95), mul(plume, SH), light, 0.3);
  p.inkRing(w, ow * 1.0, thick);
  for (let i = -1; i <= 1; i++) { const a = rot + i * 0.35; p.line([tip, [tip[0] + 34 * Math.cos(a), tip[1] + 34 * Math.sin(a)]], shade(plume, 0.88), 12); }
};
const lerp = (a: P2, b: P2, t: number): P2 => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];
export { INK };

// ---------------- effect cards of the Emu War film ----------------
/** a few brown feathers tumbling out (300 x 300); t 0..1 */
export const fxFeathers = (p: Pen, t: number, col = "#dcc4a0") => {
  // soft curved plumes: a quill with a fluffy vane either side, drifting and spinning out
  for (let i = 0; i < 6; i++) {
    const a = (i / 6) * TAU + 0.4, d = 30 + 110 * t, x = 150 + d * Math.cos(a), y = 150 + d * Math.sin(a) * 0.7 + 60 * t * t, r = rad(i * 50 + 200 * t);
    const c = Math.cos(r), s = Math.sin(r), P = (u: number, v: number): P2 => [x + u * c - v * s, y + u * s + v * c];
    const vane: P2[] = [];
    for (let k = 0; k <= 10; k++) { const u = -30 + 60 * (k / 10); vane.push(P(u, -10 * Math.sin((k / 10) * Math.PI) - 2 * Math.sin(k * 1.7))); }
    for (let k = 10; k >= 0; k--) { const u = -30 + 60 * (k / 10); vane.push(P(u, 9 * Math.sin((k / 10) * Math.PI) + 2 * Math.cos(k * 1.9))); }
    p.poly(vane, i % 2 ? col : shade(col, 0.88), 3.5);
    p.stroke([P(-36, 0), P(28, 0)], 2.5, shade(col, 0.55));
  }
};
/** a grey smoke puff (300 x 300) from the jammed gun; t 0..1 */
export const fxSmoke = (p: Pen, t: number) => {
  for (let i = 0; i < 6; i++) {
    const a = rad(200 + i * 30), d = 20 + 60 * t, r = (30 + 16 * (i % 3)) * (0.7 + 0.5 * t);
    p.ell(150 + d * Math.cos(a) * 0.8, 190 - 90 * t + d * 0.5 * Math.sin(a), r, r * 0.85, `rgba(120,120,128,${(0.95 - 0.8 * t).toFixed(3)})`, 0);
  }
};
/** a big "!" (200 x 360) */
export const fxExclaim = (p: Pen) => {
  p.poly([[70, 30], [140, 30], [124, 230], [86, 230]], "#ff5a3c", 12);
  p.ell(105, 300, 30, 30, "#ff5a3c", 12);
};
/** floating hearts (360 x 300); t 0..1 loops */
export const fxHearts = (p: Pen, t: number) => {
  for (let i = 0; i < 3; i++) {
    const u = (t + i / 3) % 1, x = 90 + i * 90 + 18 * Math.sin(u * TAU), y = 260 - 220 * u, s = 0.6 + 0.5 * Math.sin(u * Math.PI);
    const pts: P2[] = []; for (let k = 0; k <= 32; k++) { const a = (k / 32) * TAU; pts.push([x + s * 30 * 16 * Math.sin(a) ** 3 / 16, y - s * 30 * (13 * Math.cos(a) - 5 * Math.cos(2 * a) - 2 * Math.cos(3 * a) - Math.cos(4 * a)) / 16]); }
    p.poly(pts, "#ff6a8a", 7);
  }
};
/** a red gunsight ring with ticks (600 x 600) laid over the crowd */
export const fxTarget = (p: Pen, k: number) => {
  p.arc(300, 300, 250 * k, 250 * k, 0, 360, 16, "#ff4a3c");
  p.arc(300, 300, 140 * k, 140 * k, 0, 360, 10, "#ff4a3c");
  for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) p.stroke([[300 + dx * 180 * k, 300 + dy * 180 * k], [300 + dx * 290 * k, 300 + dy * 290 * k]], 14, "#ff4a3c");
};
/** wheat ears flying out of a pecking beak (300 x 300) */
export const fxCrumbs = (p: Pen, t: number) => {
  for (let i = 0; i < 7; i++) {
    const a = rad(200 + i * 22), d = 30 + 120 * t, x = 150 + d * Math.cos(a), y = 200 + d * Math.sin(a) + 120 * t * t;
    p.ell(x, y, 9, 15, i % 2 ? "#f0c868" : "#e4b452", 4, 0, 360, i * 40);
  }
};
/** a counted number in a white bubble (240 x 240) */
export const fxCount = (p: Pen, n: number) => {
  p.ell(120, 120, 100, 100, "#ffffff", 10);
  const g = p.g; g.fillStyle = INK; g.font = "900 130px sans-serif"; g.textAlign = "center"; g.textBaseline = "middle"; g.fillText(String(n), 120, 128);
};
/** a brass cartridge case standing up (120 x 300) */
export const fxCase = (p: Pen) => {
  p.poly([[30, 290], [90, 290], [90, 90], [72, 60], [48, 60], [30, 90]], "#e0aa44", 8);
  p.poly([[22, 290], [98, 290], [98, 272], [22, 272]], "#c99636", 6);
  p.stroke([[44, 100], [44, 260]], 8, "#f6d886");
};
