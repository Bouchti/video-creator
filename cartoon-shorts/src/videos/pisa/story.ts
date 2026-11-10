// Timeline of the Pisa short ("The Tower That Was Saved by a War"): shots timed to the voice words
// (shorts/pisa/voice/words.json), the tower's state per shot (storeys built, lean, the banana curve, lead, drill,
// the what-if topple) and the camera grammar of the skill: symmetric smootherstep glides of 18-40 f, big reframes are
// cuts, every hold creeps in, impacts are 7-frame flip kicks. Cuts land 2 frames before their word.
export const FPS = 30;
export const TOTAL = 1962;
export const D0 = 6.0; // ground level (m) on both banks; the river surface is at 0
export type V3 = [number, number, number];

export const clamp01 = (x: number) => Math.max(0, Math.min(1, x));
export const smooth = (x: number) => { const u = clamp01(x); return u * u * (3 - 2 * u); };
export const easeOut = (u: number) => 1 - (1 - clamp01(u)) ** 4;
export const easeIn = (u: number) => clamp01(u) ** 2;

// ---------------- the place ----------------
/** tower base centre (lawn of the piazza, north bank); it leans toward -x, so the high side is +x */
export const TOWER: V3 = [0, D0, 80];
export const TR = 7.8; // outer radius of the storeys
export const BASE_H = 10.5, GAL_H = 6.2, BELL_H = 7.0, BELL_R = 5.4;
/** storey k bottom height above the base (0 = ground floor, 1..6 galleries, 7 = belfry) */
export const storeyY = (k: number) => (k === 0 ? 0 : BASE_H + (k - 1) * GAL_H);
export const storeyH = (k: number) => (k === 0 ? BASE_H : k === 7 ? BELL_H : GAL_H);
/** the march route past the piazza: along the lawn's south edge toward -x (off to war) */
export const ROUTE_Z = 52;
/** the soldiers' camp after the defeat (golden), out on the west lawn */
export const CAMP: V3 = [-82, D0, 60];
/** the wet-sand beach under the near quay (the kid), on the river side of the wall at z = -30 */
export const BEACH: V3 = [-130, 0.16, -26.6];

// ---------------- shots ----------------
export type Light = "day" | "golden";
export type Crowd = "tourists" | "masons" | "masonsTop" | "war" | "march" | "camp" | "return" | "builders" | "closed" | "lead" | "kid" | "drill" | "stop" | "none";
export type ShotDef = { id: number; a: number; b: number; light: Light; crowd: Crowd; sunAz?: number; sunEl?: number };
export const SHOTS: ShotDef[] = [
  { id: 1, a: 0, b: 116, light: "day", crowd: "tourists" },          // hook: the tower today
  { id: 2, a: 116, b: 261, light: "day", crowd: "masons", sunAz: 120 }, // 1173: aerial, the first storey going up
  { id: 3, a: 261, b: 397, light: "day", crowd: "masonsTop" },        // second floor, the sinking
  { id: 4, a: 397, b: 488, light: "day", crowd: "war" },              // war: the column passes, tools dropped
  { id: 5, a: 488, b: 557, light: "day", crowd: "march" },            // "Luckily": marching proud
  { id: 6, a: 557, b: 616, light: "golden", crowd: "camp" },          // "Unluckily": the defeated camp
  { id: 7, a: 616, b: 677, light: "day", crowd: "none" },             // a hundred years
  { id: 8, a: 677, b: 816, light: "day", crowd: "return" },           // the return, the new storeys
  { id: 9, a: 816, b: 888, light: "day", crowd: "none" },             // curved like a banana
  { id: 10, a: 888, b: 1026, light: "day", crowd: "closed" },         // tipping to 1990, closed
  { id: 11, a: 1026, b: 1229, light: "day", crowd: "lead" },          // the lead paperweight
  { id: 12, a: 1229, b: 1401, light: "day", crowd: "kid", sunAz: 110 }, // wet sand
  { id: 13, a: 1401, b: 1506, light: "day", crowd: "none" },          // the clay squeezing out
  { id: 14, a: 1506, b: 1586, light: "golden", crowd: "none", sunAz: 150, sunEl: 12 }, // what if: no war -> toppled
  { id: 15, a: 1586, b: 1817, light: "day", crowd: "drill" },         // soil out from under the high side
  { id: 16, a: 1817, b: 1865, light: "day", crowd: "stop" },          // stopped on purpose
  { id: 17, a: 1865, b: TOTAL, light: "golden", crowd: "tourists", sunAz: -40, sunEl: 10 }, // nobody flies to see a straight tower
];
/** crossfades (frames) at place/time changes; a white 4-frame flash after the hook */
export const XFADE: Record<number, number> = { 6: 8, 7: 8, 8: 8, 12: 8, 13: 8, 14: 8, 15: 8, 17: 8 };
export const FLASH_AT = 112;

export const shotAt = (f: number) => SHOTS.find((s) => f >= s.a && f < s.b) ?? SHOTS[SHOTS.length - 1];
export const layersAt = (f: number): { id: number; alpha: number }[] => {
  for (const s of SHOTS) {
    const x = XFADE[s.id];
    if (x && f >= s.a - x / 2 && f < s.a + x / 2) return [{ id: s.id - 1, alpha: 1 }, { id: s.id, alpha: (f - (s.a - x / 2) + 1) / (x + 1) }];
  }
  return [{ id: shotAt(f).id, alpha: 1 }];
};

// ---------------- the tower ----------------
/** storeys: a continuous count (2.4 = two built, the third 40 % up); lean in degrees at the base (toward -x);
 *  curve = the post-1272 storeys built taller on the low side (each turned back by CURVE deg); sink = the soil
 *  slump at the low side (0..1); lead = blocks stacked (0..1); fence = the 1990 barrier; drill = the extraction rig
 *  (spin 0..1); weeds = the abandoned stub greening (0..1); scaffold = timber scaffold at the working storey;
 *  topple = the what-if fall angle (deg) of a tower built straight through; spoil = soil heaps (0..1) */
export type TowerState = {
  storeys: number; lean: number; curve: boolean; sink: number; lead: number; fence: number; drill: number; weeds: number;
  scaffold: boolean; topple: number; spoil: number; wet: number;
};
export const CURVE = 0.42;
const NOW = 4.0, Y1990 = 5.5, PAUSE = 1.6;
const base: TowerState = { storeys: 8, lean: NOW, curve: true, sink: 1, lead: 0, fence: 0, drill: 0, weeds: 0, scaffold: false, topple: 0, spoil: 0, wet: 0 };
const kf = (f: number, pts: [number, number][]) => {
  if (f <= pts[0][0]) return pts[0][1];
  for (let i = 1; i < pts.length; i++) if (f <= pts[i][0]) {
    const [x0, y0] = pts[i - 1], [x1, y1] = pts[i];
    return y0 + (y1 - y0) * smooth((f - x0) / (x1 - x0));
  }
  return pts[pts.length - 1][1];
};
/** the sinking: 0 until "sinking" (f 354), then a slump over 20 f with a little overshoot */
const SINK_F = 352;
export const towerAt = (id: number, f: number): TowerState => {
  switch (id) {
    case 1: return { ...base };
    case 2: return { ...base, storeys: kf(f, [[116, 0.35], [255, 1.0]]), lean: 0, curve: false, sink: 0, scaffold: true };
    case 3: {
      const u = clamp01((f - SINK_F) / 20), over = u < 1 ? Math.sin(u * Math.PI) * 0.25 : 0;
      return { ...base, storeys: kf(f, [[261, 1.75], [303, 2.0], [350, 2.45]]), lean: PAUSE * (easeOut(u) + over), curve: false, sink: easeOut(u), scaffold: true };
    }
    case 4: return { ...base, storeys: 2.45, lean: PAUSE, curve: false, sink: 1, scaffold: true };
    case 5: case 6: return { ...base, storeys: 2.45, lean: PAUSE, curve: false, sink: 1, scaffold: true };
    case 7: return { ...base, storeys: 3, lean: PAUSE, curve: false, sink: 1, weeds: kf(f, [[616, 0.1], [677, 1]]) };
    case 8: return { ...base, storeys: kf(f, [[743, 3], [799, 7]]), lean: PAUSE + 0.3, sink: 1, weeds: f < 743 ? 1 : 0, scaffold: f >= 735 };
    case 9: return { ...base, storeys: 8, lean: PAUSE + 0.5 };
    case 10: return { ...base, lean: kf(f, [[888, PAUSE + 0.6], [962, Y1990]]), fence: f >= 1006 ? 1 : 0 };
    case 11: return { ...base, lean: kf(f, [[1192, Y1990], [1222, Y1990 - 0.25]]), fence: 1, lead: kf(f, [[1050, 0], [1165, 1]]) };
    case 12: return { ...base };
    case 13: return { ...base, storeys: 3, lean: PAUSE, curve: false, weeds: kf(f, [[1401, 0.3], [1506, 1]]), wet: kf(f, [[1401, 0], [1500, 1]]) };
    case 14: {
      const tip = f < 1540 ? 0 : 90 * easeIn((f - 1540) / 38);
      return { ...base, storeys: kf(f, [[1506, 3], [1534, 8]]), lean: 0, curve: false, sink: 0, topple: Math.min(90, tip) };
    }
    case 15: return { ...base, lean: kf(f, [[1762, Y1990 - 0.25], [1812, NOW]]), fence: 1, lead: 1, drill: f >= 1664 ? 1 : 0, spoil: kf(f, [[1668, 0], [1815, 1]]) };
    case 16: return { ...base, lean: NOW, fence: 1, lead: 1, drill: f < 1838 ? 1 : 0, spoil: 1 };
    case 17: return { ...base, lean: NOW };
    default: return { ...base };
  }
};
/** world point on the tower's axis at height h above the base for state s (follows the lean + the banana curve) */
export const towerPoint = (s: TowerState, h: number): V3 => {
  // pivot = the high-side foot (x + TR): the low side sank, the high side stayed put
  let x = TOWER[0], y = 0, ang = (s.lean + s.topple) * (Math.PI / 180);
  let rem = h, k = 0;
  const px = TOWER[0] + TR;
  // walk up the storeys, turning back by CURVE for the corrected ones
  let cx = TOWER[0] - px, cy = 0; // axis point relative to the pivot, before the base turn
  while (rem > 0 && k < 8) {
    const hk = Math.min(rem, storeyH(k)), a = s.curve && k >= 3 ? -(k - 2) * CURVE * (Math.PI / 180) : 0;
    cx += -Math.sin(a) * hk; cy += Math.cos(a) * hk;
    rem -= hk; k++;
  }
  x = px + cx * Math.cos(ang) - cy * Math.sin(ang);
  y = cx * Math.sin(ang) + cy * Math.cos(ang);
  return [x, D0 + y, TOWER[2]];
};

// ---------------- the column (off to war) ----------------
export const FILES = [-1.5, -0.5, 0.5, 1.5];
export const ROWS = 6, ROW_GAP = 1.35, COUNT = 24;
/** x of the front row along the route (marching toward -x at 1.6 m/s) */
export const front = (t: number) => 6 - 1.6 * (t - 13.2);
export const marchPhase = (t: number) => ((t % 1) + 1) % 1;

// ---------------- camera ----------------
export type Cam = { pos: V3; look: V3; fov: number; roll: number };
type Shot = Partial<Cam> & { pos: V3; look: V3 };
type Key = { f: number; dur?: number; cut?: boolean; s: (f: number) => Shot };
export const glide = (u: number) => { const x = clamp01(u); return x * x * x * (x * (6 * x - 15) + 10); };
const mixC = (a: Cam, b: Cam, k: number): Cam => ({
  pos: a.pos.map((v, i) => v + (b.pos[i] - v) * k) as V3, look: a.look.map((v, i) => v + (b.look[i] - v) * k) as V3,
  fov: a.fov + (b.fov - a.fov) * k, roll: a.roll + (b.roll - a.roll) * k,
});
const full = (c: Shot): Cam => ({ fov: 40, roll: 0, ...c });
const run = (keys: Key[], f: number) => {
  let cur = full(keys[0].s(f));
  for (let i = 1; i < keys.length; i++) {
    const k = keys[i];
    if (f < k.f) break;
    cur = k.cut ? full(k.s(f)) : mixC(cur, full(k.s(f)), glide((f - k.f) / (k.dur ?? 24)));
  }
  return cur;
};
const T = (f: number) => f / FPS;
/** push-in factor since f0 (the subject grows ~rate per frame; `punch` raises it for n frames, 8 f soft edges) */
const pushK = (f: number, f0: number, rate: number, punch = 0, n = 35) => {
  const x = Math.max(0, f - f0);
  let s = rate * x;
  if (punch > rate) for (let i = 0; i < Math.min(x, n); i++) s += (punch - rate) * Math.max(0, Math.min(1, (i + 0.5) / 8, (n - i - 0.5) / 8));
  return Math.exp(-s);
};
const dolly = (pos: V3, look: V3, k: number, rest: Partial<Cam> = {}): Shot =>
  ({ pos: [look[0] + (pos[0] - look[0]) * k, look[1] + (pos[1] - look[1]) * k, look[2] + (pos[2] - look[2]) * k], look, ...rest });
const zoom = (pos: V3, look: V3, fov: number, k: number, rest: Partial<Cam> = {}): Shot =>
  ({ pos, look, fov: (360 / Math.PI) * Math.atan(Math.tan((fov * Math.PI) / 360) * k), ...rest });
const rolled = (s: (f: number) => Shot, roll: number) => (f: number): Shot => ({ ...s(f), roll });
const Fx = (f: number) => front(T(f));

// ---- framings ----
// 1 hook: low on the lawn among the tourists, the whole tower leaning over screen right; punch on "went off to war"
const S1a = (f: number) => zoom([-12, 7.5, 16], [-4, 27, 80], 52, pushK(f, 0, 0.0018));
const S1b = (f: number) => dolly([-10.5, 6.8, 44], [-7.5, 12.5, 62], pushK(f, 60, 0.002, 0.006, 30), { fov: 48, roll: -0.05 });
// 2 aerial over the river town -> down to the piazza, the first storey going up
const S2a = (f: number) => zoom([46, 52, -55], [0, 10, 80], 34, pushK(f, 116, 0.002));
const S2b = (f: number) => dolly([18, 20, 44], [0, 9, 80], pushK(f, 190, 0.0022), { fov: 40 });
// 3 masons on the rim of storey 2 -> wide low as it sinks -> the slumped soil at the low side's foot
const RIM = BASE_H + GAL_H + D0; // top of storey 2
const S3a = (f: number) => dolly([-6.5, RIM + 3.4, 62.5], [-2.5, RIM + 1.2, 73.5], pushK(f, 261, 0.0025), { fov: 42 });
const S3b = (f: number) => zoom([-30, 8.5, 36], [-2, 15, 80], 42, pushK(f, 352, 0.002), { roll: 0.05 });
const S3c = (f: number) => dolly([-12.5, 7.1, 66], [-8.2, 6.4, 73.2], pushK(f, 370, 0.003), { fov: 38, roll: -0.04 });
// 4 the column passing the stub -> the masons dropping their tools
const S4a = (f: number) => zoom([12.5, 7.3, 41], [1.5, 8.6, 56], 46, pushK(f, 397, 0.0022));
const S4b = (f: number) => dolly([-1.6, 7.6, 63.2], [-3.4, 7.2, 70.4], pushK(f, 452, 0.003, 0.006, 24), { fov: 40, roll: 0.04 });
// 5 "Luckily": low ahead of the column, the drummer + banner proud
const S5a = (f: number) => { const F = Fx(f); return dolly([F - 7.5, 6.9, ROUTE_Z - 2.4], [F + 1, 7.6, ROUTE_Z], pushK(f, 488, 0.0025), { fov: 42, roll: -0.04 }); };
// 6 "Unluckily": the defeated camp at dusk
const S6a = (f: number) => dolly([CAMP[0] + 1.4, D0 + 1.45, CAMP[2] - 6.4], [CAMP[0], D0 + 0.85, CAMP[2] - 0.6], pushK(f, 553, 0.0025, 0.005, 30), { fov: 42, roll: 0.04 });
// 7 a hundred years: the stub alone, the clouds racing; slow push
const S7a = (f: number) => zoom([-32, 9.5, 32], [-2, 17, 80], 50, pushK(f, 612, 0.003));
// 8 the return: new masons look up at the leaning stub -> wide from across the river as the storeys go up
const S8a = (f: number) => zoom([-11, 6.8, 50], [-3, 18, 80], 50, pushK(f, 673, 0.0022));
const S8b = (f: number) => zoom([-6, 22, -8], [-4, 30, 80], 44, pushK(f, 741, 0.0016));
// 9 curved like a banana: low side view tilting up the tower, punch on "banana"
const S9a = (f: number) => zoom([2, 20, -10], [2, 30, 80], 50, pushK(f, 816, 0.0018));
const S9b = (f: number) => zoom([2, 20, -10], [3, 31, 80], 48, pushK(f, 866, 0.002, 0.005, 24), { roll: 0.05 });
// 10 tipping year on year (wide) -> "close it": the barrier at the foot
const S10a = (f: number) => zoom([-8, 18, 6], [-4, 28, 80], 46, pushK(f, 888, 0.0018));
const S10b = (f: number) => dolly([-17, 7.6, 57], [-6.5, 8.2, 71.5], pushK(f, 1008, 0.003), { fov: 42 });
// 11 the lead: engineers stack the blocks on the high side (east of the foot), "It helped, a little" wide
const LEADP: V3 = [TOWER[0] + TR + 3.2, D0, TOWER[2]];
const S11a = (f: number) => dolly([LEADP[0] + 13, 8.4, LEADP[2] - 13], [LEADP[0] - 1, 7.6, LEADP[2] - 1], pushK(f, 1026, 0.0022), { fov: 42 });
const S11b = (f: number) => dolly([LEADP[0] + 9.5, 7.6, LEADP[2] - 8.5], [LEADP[0] - 0.5, 7.4, LEADP[2] - 0.5], pushK(f, 1165, 0.0025, 0.005, 26), { fov: 40, roll: -0.04 });
const S11c = (f: number) => zoom([-6, 22, -8], [-4, 30, 80], 44, pushK(f, 1192, 0.0018));
// 12 wet sand: the kid on the beach under the quay -> his feet, the water squeezing out -> his face, firm
const S12a = (f: number) => dolly([BEACH[0] + 3.4, 1.15, BEACH[2] + 3.4], [BEACH[0], 0.95, BEACH[2]], pushK(f, 1225, 0.0022), { fov: 40 });
const S12b = (f: number) => dolly([BEACH[0] + 0.7, 0.42, BEACH[2] + 2.1], [BEACH[0], 0.22, BEACH[2] + 0.1], pushK(f, 1314, 0.0025), { fov: 36, roll: 0.04 });
const S12c = (f: number) => dolly([BEACH[0] - 0.5, 1.2, BEACH[2] + 3.0], [BEACH[0], 1.25, BEACH[2]], pushK(f, 1380, 0.003), { fov: 38 });
// 13 the clay: low at the stub's foot, the water beading out over a hundred years
const S13a = (f: number) => zoom([-23, 7.6, 50], [-5, 10, 76], 50, pushK(f, 1397, 0.0025));
// 14 what if: built straight through, it topples TOWARD the lens (camera on the low side, -x)
const S14a = (f: number) => zoom([-56, 9, 30], [-8, 24, 80], 52, pushK(f, 1502, 0.0015));
// 15 the drill on the high side -> wide, the tower sinks back
/** the extraction rig and the bore hole its auger enters, aimed under the high side's foot */
export const BORE: V3 = [12.2, D0, 85.5];
export const DRILL: V3 = [14.14, D0, 86.37];
const S15a = (f: number) => dolly([DRILL[0] + 17, 9.2, DRILL[2] - 18], [DRILL[0] - 3, 8.6, DRILL[2] - 3.5], pushK(f, 1586, 0.002), { fov: 42 });
// from the south-east: the bore hole, the soil coming up, the growing heap and the high side's foot in one frame
const S15b = (f: number) => dolly([27, 9.6, 65], [12.6, 7.9, 84.0], pushK(f, 1666, 0.0022), { fov: 34, roll: 0.03 });
const S15c = (f: number) => zoom([-6, 22, -8], [-4, 30, 80], 44, pushK(f, 1762, 0.0018));
// 16 the engineer switches off -> the tourists "holding it up", crane out (callback to the hook)
const S16a = (f: number) => dolly([DRILL[0] + 9, 7.9, DRILL[2] - 10], [DRILL[0] - 2, 7.6, DRILL[2] - 2], pushK(f, 1817, 0.0025), { fov: 40 });
const S16b = (f: number) => dolly([-10.5, 6.8, 44], [-7.5, 12.5, 62], pushK(f, 1865, 0.0018), { fov: 48 });
const CRANE: V3[] = [[-14, 18, 38], [-18, 34, 18]];
const S16c = (f: number): Shot => {
  const a = S16b(1905), s = glide((f - 1905) / 57), r = 1 - s, [C, B] = CRANE;
  return { pos: [0, 1, 2].map((i) => r * r * a.pos[i] + 2 * s * r * C[i] + s * s * B[i]) as V3,
    look: [0, 1, 2].map((i) => a.look[i] + ([-4, 30, 80][i] - a.look[i]) * s) as V3, fov: (a.fov ?? 50) + (46 - (a.fov ?? 50)) * s, roll: 0 };
};

const CAMS: Record<number, Key[]> = {
  1: [{ f: 0, s: S1a }, { f: 60, cut: true, s: S1b }],
  2: [{ f: 116, s: S2a }, { f: 182, dur: 40, s: S2b }],
  3: [{ f: 261, s: S3a }, { f: 352, cut: true, s: S3b }, { f: 370, cut: true, s: S3c }],
  4: [{ f: 397, s: S4a }, { f: 452, cut: true, s: S4b }],
  5: [{ f: 488, s: S5a }],
  6: [{ f: 553, s: S6a }],
  7: [{ f: 612, s: S7a }],
  8: [{ f: 673, s: S8a }, { f: 741, cut: true, s: S8b }],
  9: [{ f: 816, s: S9a }, { f: 862, dur: 24, s: S9b }],
  10: [{ f: 888, s: S10a }, { f: 1008, cut: true, s: S10b }],
  11: [{ f: 1026, s: S11a }, { f: 1165, cut: true, s: S11b }, { f: 1192, cut: true, s: S11c }],
  12: [{ f: 1225, s: S12a }, { f: 1314, cut: true, s: S12b }, { f: 1380, cut: true, s: S12c }],
  13: [{ f: 1397, s: S13a }],
  14: [{ f: 1502, s: S14a }],
  15: [{ f: 1586, s: S15a }, { f: 1666, cut: true, s: S15b }, { f: 1762, cut: true, s: S15c }],
  16: [{ f: 1817, s: S16a }],
  17: [{ f: 1861, s: S16b }, { f: 1905, cut: true, s: S16c }],
};

// impact kicks: the sinking, the tools hitting the ground, the last lead block, the what-if crash
const KICKS: [number, number][] = [[352 / FPS, 1.2], [460 / FPS, 0.4], [1163 / FPS, 0.6], [1578 / FPS, 1.8], [1764 / FPS, 0.5]];
export const kickAt = (t: number) => {
  let a = 0;
  for (const [t0, g] of KICKS) {
    const n = Math.floor((t - t0) * FPS + 1e-6);
    if (n >= 0 && n < 7) a += g * (n % 2 ? -1 : 1) * (1 - n / 7) ** 1.5;
  }
  return a;
};
export const camAt = (id: number, f: number): Cam => {
  const c = run(CAMS[id], f), a = kickAt(T(f));
  if (!a) return c;
  const d: V3 = [c.look[0] - c.pos[0], c.look[1] - c.pos[1], c.look[2] - c.pos[2]];
  const L = Math.hypot(...d), h = Math.hypot(d[0], d[2]) || 1;
  const m = (3 / 640) * Math.tan((c.fov * Math.PI) / 360) * L * a;
  return { ...c, look: [c.look[0] - (d[2] / h) * m, c.look[1] + 0.6 * m, c.look[2] + (d[0] / h) * m], roll: c.roll + a * 0.004 };
};
export const keyEnd = (id: number, f: number) => {
  let e = 0;
  for (const k of CAMS[id]) if (f >= k.f) e = k.f + (k.cut ? 0 : k.dur ?? 24);
  return Math.max(f, e);
};

// ---------------- lens: depth of field + foreground framing ----------------
export type Dof = { f: number; dur?: number; cInf: number; focus?: (f: number) => V3 };
export const DOF: Dof[] = [
  // Every blurred shot names its subject: the camera's look point often sits inside or behind it (a tower's
  // centre, a spot past the rig), and focusing there left the subject soft and the background sharp. Wides,
  // establishing shots and the tower/drill shots stay sharp (the skill: DOF only on CU / MS of characters).
  { f: 0, cInf: 0 },                                                      // hook: the whole tower
  { f: 60, cInf: 10, focus: () => [-7.5, D0 + 1.5, 56] },                 // the tourists holding it up
  { f: 116, cInf: 0 },                                                    // aerial
  { f: 261, cInf: 10, focus: () => [-1.2, D0 + 17.6, 73.3] },             // masons on the rim
  { f: 352, cInf: 0 },                                                    // the sinking (wide) + the slumped foot
  { f: 452, cInf: 10, focus: () => [-3.4, D0 + 1.4, 70.8] },              // masons drop their tools
  { f: 488, cInf: 12, focus: (f) => [Fx(f) + 0.5, D0 + 1.6, ROUTE_Z] },   // the front row
  { f: 557, cInf: 10, focus: () => [CAMP[0], D0 + 0.9, CAMP[2] + 0.4] },  // the camp
  { f: 616, cInf: 0 },                                                    // the stub, the return, banana, tipping
  { f: 1008, cInf: 9, focus: () => [-7.6, D0 + 1.4, 68.0] },             // turned away at the barrier
  { f: 1026, cInf: 0 },                                                   // the lead (wide on the stack)
  { f: 1229, cInf: 12, focus: () => [BEACH[0], 1.0, BEACH[2]] },          // the kid
  { f: 1314, cInf: 13, focus: () => [BEACH[0], 0.25, BEACH[2]] },         // his feet
  { f: 1380, cInf: 12, focus: () => [BEACH[0], 1.35, BEACH[2]] },         // his face
  { f: 1401, cInf: 0 },                                                   // the clay, the topple, the drill, sank back
  { f: 1817, cInf: 9, focus: () => [17.2, D0 + 1.5, 84.0] },              // the switch-off
  { f: 1865, cInf: 10, focus: () => [-7.5, D0 + 1.5, 56] },               // tourists
  { f: 1905, dur: 40, cInf: 0 },                                          // crane out
];
export const dofAt = (f: number) => {
  let i = 0; while (i + 1 < DOF.length && f >= DOF[i + 1].f) i++;
  const d = DOF[i], p = DOF[Math.max(0, i - 1)];
  const k = d.dur ? Math.min(1, (f - d.f) / d.dur) : 1;
  return { cInf: p.cInf + (d.cInf - p.cInf) * k, focus: d.focus };
};
export const focusAt = (id: number, f: number): V3 => {
  const d = dofAt(f);
  return d.focus ? d.focus(f) : camAt(id, f).look;
};

export type Fg = { a: number; b: number; kit: string; pos: V3; s?: number; yaw?: number };
export const FOREGROUND: Fg[] = [
  // the column passing: a market cart in the bottom-right corner
  { a: 397, b: 452, kit: "cart", pos: [11.2, D0, 43.4], s: 0.8, yaw: 0.8 },
  // the stub alone: a bush low left
  { a: 616, b: 677, kit: "plant_bushDetailed", pos: [-21.5, D0, 45.5], s: 1.5, yaw: 0.4 },
  // the barrier close: a lantern post right
  { a: 1008, b: 1026, kit: "lantern", pos: [-13.4, D0, 60.2], s: 2.8 },
];
