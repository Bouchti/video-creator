// Timeline of the escalator short ("Where do escalator steps go?"): shots timed to the voice words
// (shorts/escalator/voice/words.json), the cutaway (section view) per shot, the story highlights on the wheels and the
// camera grammar of the skill: smootherstep glides of 18-40 f, big reframes are cuts, every hold creeps in, impacts are
// 7-frame flip kicks. Cuts land 2 frames before their word.
import { RISE, XT, XS1, X0, XB, h, poseAt, stepS, sAtX, PITCH, LOOP, SPEED, HC, HR_Z, railY, XT1, HB, beltY } from "./escpath";

export const FPS = 30;
export const TOTAL = 2080;
export const D0 = 0; // ground level of the lower plaza
export type V3 = [number, number, number];

export const clamp01 = (x: number) => Math.max(0, Math.min(1, x));
export const smooth = (x: number) => { const u = clamp01(x); return u * u * (3 - 2 * u); };
export const easeOut = (u: number) => 1 - (1 - clamp01(u)) ** 4;
export const easeIn = (u: number) => clamp01(u) ** 2;

// ---------------- the places ----------------
/** the upper deck the escalator arrives on (slab top at RISE), and the store behind it */
export const DECK = { x0: 9.0, x1: 27.0, z0: -7.0, z1: 7.0, thick: 0.5 };
/** the Harrods hall of 1898, far west of the town (an open-fronted set: floor, three walls, gallery, ceiling) */
export const HALL = { x0: HB.x0 - 8.5, x1: HB.x1 + 14, z0: -9.0, z1: 5.0, gal: HB.rise };
/** plaza paving */
export const PLAZA = { x0: -24, x1: 30, z0: -14, z1: 16 };
/** the cut plane of every section view (just outside the near truss side) */
export const ZCUT = 0.8;

// ---------------- shots ----------------
export type Light = "day" | "golden";
export type Crowd = "hook" | "hall" | "belt" | "beltRiders" | "staff" | "relief" | "queue" | "riders" | "none" | "comb" | "inspector" | "brand" | "ending";
export type ShotDef = { id: number; a: number; b: number; light: Light; crowd: Crowd; sunAz?: number; sunEl?: number };
export const SHOTS: ShotDef[] = [
  { id: 1, a: 0, b: 159, light: "day", crowd: "hook", sunAz: 150, sunEl: 32 },             // steps slide into the floor, flip, sneak back underneath
  { id: 2, a: 159, b: 318, light: "day", crowd: "hall", sunAz: 150, sunEl: 55 }, // 1898 Harrods unveils the moving staircase
  { id: 3, a: 318, b: 414, light: "day", crowd: "belt", sunAz: 140, sunEl: 55 }, // really a leather belt
  { id: 4, a: 414, b: 547, light: "day", crowd: "beltRiders", sunAz: 140, sunEl: 55 }, // shaken shoppers, brandy + salts at the top
  { id: 5, a: 547, b: 592, light: "day", crowd: "relief", sunAz: 140, sunEl: 55 }, // luckily nobody fell
  { id: 6, a: 592, b: 652, light: "golden", crowd: "queue", sunAz: 140, sunEl: 16 }, // unluckily the brandy was free
  { id: 7, a: 652, b: 739, light: "day", crowd: "riders", sunAz: 155, sunEl: 26 },          // one big loop, like a bicycle chain
  { id: 8, a: 739, b: 843, light: "day", crowd: "none", sunAz: 150, sunEl: 26 },            // motor, big gear, two chains
  { id: 9, a: 843, b: 957, light: "day", crowd: "none", sunAz: 155, sunEl: 26 },            // two wheels in front, two behind, two tracks
  { id: 10, a: 957, b: 1080, light: "day", crowd: "riders", sunAz: 155, sunEl: 26 },        // the back track rides higher: steps stay flat
  { id: 11, a: 1080, b: 1206, light: "day", crowd: "riders", sunAz: 155, sunEl: 26 },       // the tracks level out: the stairs melt flat
  { id: 12, a: 1206, b: 1366, light: "day", crowd: "comb" },         // grooves + comb, shoelaces pushed out
  { id: 13, a: 1366, b: 1499, light: "day", crowd: "riders", sunAz: 155, sunEl: 26 },       // over the gear, back down upside down under your shoes
  { id: 14, a: 1499, b: 1602, light: "day", crowd: "riders", sunAz: 155, sunEl: 26 },       // the handrail loop, pulled by the same motor
  { id: 15, a: 1602, b: 1737, light: "day", crowd: "inspector" },    // up to 2 % faster, never slower
  { id: 16, a: 1737, b: 1934, light: "day", crowd: "brand" },        // the word escalator: Otis lost it in 1950
  { id: 17, a: 1934, b: TOTAL, light: "golden", crowd: "ending", sunAz: -70, sunEl: 30 }, // watch your hand
];
/** crossfades (frames) at place/time changes; a white 4-frame flash after the hook */
export const XFADE: Record<number, number> = { 6: 8, 7: 10, 17: 10 };
export const FLASH_AT = 155;

export const shotAt = (f: number) => SHOTS.find((s) => f >= s.a && f < s.b) ?? SHOTS[SHOTS.length - 1];
export const layersAt = (f: number): { id: number; alpha: number }[] => {
  for (const s of SHOTS) {
    const x = XFADE[s.id];
    if (x && f >= s.a - x / 2 && f < s.a + x / 2) return [{ id: s.id - 1, alpha: 1 }, { id: s.id, alpha: (f - (s.a - x / 2) + 1) / (x + 1) }];
  }
  return [{ id: shotAt(f).id, alpha: 1 }];
};

// ---------------- section view + highlights ----------------
const CUT_SHOTS = new Set([7, 8, 9, 10, 11, 13, 14]);
/** is shot `id` a section view at frame f (the hook cuts into the floor at its second key) */
export const cutAt = (id: number, f: number) => CUT_SHOTS.has(id) || (id === 1 && f >= 85);
/** the top landing plate is lifted off for the view down into the drive */
export const noTopPlateAt = (id: number, f: number) => id === 8 && f >= 788;
const pulse = (f: number, a: number, b: number) => (f < a || f > b ? 0 : Math.sin(Math.PI * clamp01((f - a) / (b - a))) ** 0.6);
export const glowAt = (id: number, f: number) => ({
  glowFront: id === 9 ? pulse(f, 840, 899) : 0,
  glowRear: id === 9 ? pulse(f, 899, 944) : id === 10 ? pulse(f, 974, 1012) : 0,
  glowTracks: id === 9 ? pulse(f, 925, 960) : id === 11 ? pulse(f, 1102, 1140) : 0,
  glowRail: id === 14 ? pulse(f, 1500, 1552) : 0,
  glowChain: id === 8 ? pulse(f, 788, 838) : 0,
  glowMotor: id === 8 ? pulse(f, 739, 786) : id === 14 ? pulse(f, 1570, 1602) : 0,
});

// ---------------- riders (modern) ----------------
/** a rider boards at time tb on the step whose nose is just past the bottom comb; returns where they are at time t */
export type RiderPose = { x: number; y: number; mode: "walk" | "ride" | "off"; s: number; away?: number };
const S_IN = sAtX(XB + 0.28), S_OUT = sAtX(XT + 0.05);
export const riderBoard = (tb: number) => {
  // the step whose nose is nearest past S_IN at tb
  const u = ((S_IN - SPEED * tb) % LOOP + LOOP) % LOOP, k = Math.ceil(u / PITCH) % Math.round(LOOP / PITCH);
  return { k, s0: (((stepS(k, tb)) % LOOP) + LOOP) % LOOP, tb };
};
export const riderAt = (tb: number, t: number, walk = 1.1): RiderPose => {
  const b = riderBoard(tb);
  if (t < tb) { const x = XB - 0.35 - walk * (tb - t); return { x, y: 0, mode: "walk", s: 0 }; }
  const s = b.s0 + SPEED * (t - tb);
  if (s < S_OUT) { const p = poseAt(s); return { x: p.x - 0.2, y: p.y + HC, mode: "ride", s }; }
  const tOut = tb + (S_OUT - b.s0) / SPEED, p = poseAt(S_OUT);
  return { x: p.x - 0.2 + walk * (t - tOut), y: RISE, mode: "off", s: S_OUT, away: Math.min(2.4, 0.8 * walk * (t - tOut)) };
};

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
const add = (a: V3, b: V3): V3 => [a[0] + b[0], a[1] + b[1], a[2] + b[2]];

const HX = HB.x0, HZ = HB.z, HG = HB.rise;
/** the step the shot-9 camera rides with: the one nearest x = 3.2 at frame 843 */
const K9 = (() => { const s = sAtX(3.2), u = ((s - SPEED * T(843)) % LOOP + LOOP) % LOOP; return Math.round(u / PITCH); })();
const step9 = (f: number): V3 => { const p = poseAt(stepS(K9, T(f))); return [p.x, p.y + HC, 0]; };
/** the shot-17 rider (boards early, mid-incline at the ending) */
export const TB17 = 1934 / FPS - 9.5;
export const ride17 = (f: number): V3 => { const r = riderAt(TB17, T(f)); return [r.x, r.y, 0.26]; };
/** the hand on the rail drifts ahead of the rider (cartoon-exaggerated 2 %) */
export const hand17 = (f: number): V3 => {
  const r = ride17(f), drift = 0.05 + 0.32 * smooth((f - 1975) / 60);
  const x = r[0] + 0.16 + drift;
  return [x, railY(x) + 0.05, HR_Z - 0.02];
};

// ---- framings ----
// 1 hook: low on the top landing looking down the incline (steps sliding into the comb) -> section view of the top
// end (a step flipping round the drive sprocket) -> glide down the return run under the riders' feet
const S1a = (f: number) => zoom([XT + 3.2, RISE + 1.9, 0.15], [XT - 1.0, RISE + 0.5, 0], 46, pushK(f, 0, 0.0025, 0.006, 30), { roll: -0.03 });
const S1b = (f: number) => dolly([XS1 + 0.75, RISE - 0.75, 5.6], [XS1 - 0.15, RISE - 0.75, 0], pushK(f, 85, 0.0025), { fov: 46 });
const S1c = (f: number) => dolly([XT - 2.6, RISE - 1.2, 5.4], [XT - 3.0, RISE - 0.85, 0], pushK(f, 118, 0.0025), { fov: 48, roll: 0.03 });
// 2 Harrods 1898: wide of the hall, the belt in the middle -> the manager presenting at the belt's foot
const S2a = (f: number) => zoom([HX - 6.8, 2.1, HZ + 5.0], [HX + 1.5, 2.0, HZ], 50, pushK(f, 159, 0.0016));
const S2b = (f: number) => dolly([HX + 2.4, 1.65, HZ + 3.4], [HX + 0.2, 1.45, HZ + 0.5], pushK(f, 256, 0.0028, 0.006, 26), { fov: 44 });
// 3 the belt: low beside the bottom drum, along the leather up to the gallery
const S3a = (f: number) => dolly([HX - 1.6, 0.85, HZ + 1.9], [HX + 4.5, 1.9, HZ], pushK(f, 318, 0.002), { fov: 44 });
const S3b = (f: number) => dolly([HX + 4.6, beltY(HX + 4.6) + 2.1, HZ + 3.3], [HX + 5.4, beltY(HX + 5.4) + 0.75, HZ], pushK(f, 355, 0.002), { fov: 46, roll: -0.03 });
// 4 the riders, nervous -> the staff at the top with brandy + salts
const S4a = (f: number) => dolly([HX + 4.6, beltY(HX + 4.6) + 1.7, HZ + 3.8], [HX + 4.2, beltY(HX + 4.2) + 0.9, HZ], pushK(f, 414, 0.0025), { fov: 44, roll: 0.03 });
const S4b = (f: number) => dolly([HB.x1 + 3.6, HG + 1.5, HZ + 3.6], [HB.x1 + 1.3, HG + 1.15, HZ - 0.1], pushK(f, 490, 0.0022, 0.004, 28), { fov: 46 });
// 5 luckily: everyone safely up, relief (a little wider on the gallery)
const S5a = (f: number) => dolly([HB.x1 + 5.5, HG + 1.7, HZ + 4.0], [HB.x1 + 1.0, HG + 1.2, HZ - 0.4], pushK(f, 547, 0.003), { fov: 46, roll: -0.04 });
// 6 unluckily: golden, the grinning queue back at the bottom
const S6a = (f: number) => dolly([HX - 4.0, 1.6, HZ + 3.6], [HX - 1.6, 1.35, HZ - 0.1], pushK(f, 592, 0.003, 0.006, 26), { fov: 44, roll: 0.04 });
// 7 today: the whole loop in section, from across the cut plaza (the bicycle chain pops in above it)
const S7a = (f: number) => zoom([6.8, 4.6, 16.5], [6.8, 4.4, 0], 50, pushK(f, 652, 0.0012));
// 8 the motor -> the big gear -> from above into the drive end (both step chains round both sprockets)
const S8a = (f: number) => dolly([XS1 + 1.6, RISE - 0.9, 3.6], [XS1 + 0.5, RISE - 1.0, -0.6], pushK(f, 739, 0.0025), { fov: 50 });
const S8b = (f: number) => dolly([XS1 + 0.9, RISE - 1.2, 2.8], [XS1 + 0.2, RISE - 0.85, -0.6], pushK(f, 756, 0.0025), { fov: 46 });
const S8c = (f: number) => dolly([XS1 + 1.9, RISE + 1.3, 0.0], [XS1 - 0.6, RISE - 0.7, 0.0], pushK(f, 788, 0.0022), { fov: 52 });
// 9 one step close, riding up with it (section view)
const S9a = (f: number) => { const p = step9(f); return dolly(add(p, [0.15, 0.05, 1.75]), add(p, [-0.15, -0.3, 0.45]), pushK(f, 843, 0.0015), { fov: 40 }); };
// 10 mid-incline side view: the stair forming, a rider standing level
const S10a = (f: number) => zoom([5.1, 3.3, 7.6], [5.0, 3.0, 0], 50, pushK(f, 957, 0.0018));
// 11 the top transition: steps flattening into the landing
const S11a = (f: number) => dolly([XT1 + 1.0, RISE + 0.2, 4.6], [XT1 + 1.2, RISE - 0.1, 0], pushK(f, 1080, 0.0022), { fov: 50 });
const S11b = (f: number) => dolly([XT - 0.4, RISE + 0.3, 4.4], [XT - 0.6, RISE + 0.0, 0], pushK(f, 1146, 0.0025), { fov: 50, roll: -0.03 });
// 12 the comb macro -> a rider stepping off over it
const S12a = (f: number) => dolly([XT - 0.6, RISE + 0.34, 0.42], [XT + 0.05, RISE + 0.01, 0.1], pushK(f, 1206, 0.0025), { fov: 36 });
const S12b = (f: number) => dolly([XT + 2.6, RISE + 0.75, -0.35], [XT - 0.3, RISE + 0.45, 0.05], pushK(f, 1292, 0.0022, 0.005, 26), { fov: 44 });
// 13 section at the top sprocket: a step tips over -> glide back down the return run under the riders' shoes
const S13a = (f: number) => dolly([XS1 + 0.9, RISE - 1.05, 4.8], [XS1 - 0.3, RISE - 1.05, 0], pushK(f, 1366, 0.0025), { fov: 46 });
const S13b = (f: number) => dolly([XT - 1.4, RISE - 1.3, 3.3], [XT - 1.9, RISE - 1.15, 0], pushK(f, 1405, 0.002), { fov: 44 });
const S13c = (f: number) => dolly([XT - 3.0, h(XT - 3.0) - 0.3, 4.2], [XT - 3.4, h(XT - 3.4) + 0.2, 0], pushK(f, 1452, 0.0025), { fov: 50, roll: 0.03 });
// 14 the handrail loop (wide section) -> its drive wheel
const S14a = (f: number) => zoom([8.5, 4.4, 7.5], [8.6, 3.6, 0], 50, pushK(f, 1499, 0.0016));
const S14b = (f: number) => dolly([XT + 1.0, RISE - 0.6, 6.0], [XT + 1.0, RISE - 1.0, -0.6], pushK(f, 1552, 0.0018), { fov: 52 });
// 15 the inspector with the stopwatch at the top landing
const S15a = (f: number) => dolly([XT + 3.8, RISE + 1.55, 3.3], [XT + 1.4, RISE + 1.15, 0.9], pushK(f, 1602, 0.0012, 0.003, 26), { fov: 44 });
// 16 the businessman with the trademark -> it blows away -> everyone riding
const S16a = (f: number) => dolly([XB - 5.2, 1.55, 4.6], [XB - 1.6, 1.35, 1.2], pushK(f, 1737, 0.0025), { fov: 42 });
const S16b = (f: number) => dolly([XB - 3.6, 1.7, 3.8], [XB - 1.0, 1.9, 1.4], pushK(f, 1807, 0.002, 0.005, 22), { fov: 44, roll: -0.04 });
const S16c = (f: number) => zoom([-7.5, 3.2, 12.5], [3.5, 2.4, 0], 50, pushK(f, 1835, 0.0016));
// 17 golden: riding along with the hand on the rail -> crane out
const S17a = (f: number) => { const r = ride17(f); return dolly([r[0] + 2.0, r[1] + 1.55, 0.05], [r[0], r[1] + 0.95, 0.32], pushK(f, 1934, 0.0018, 0.004, 30), { fov: 42 }); };
const S17b = (f: number) => zoom([1.0, 4.2, 13.5], [5.6, 3.0, 0], 50, pushK(f, 2003, 0.0012));

const CAMS: Record<number, Key[]> = {
  1: [{ f: 0, s: S1a }, { f: 85, cut: true, s: S1b }, { f: 118, dur: 36, s: S1c }],
  2: [{ f: 159, s: S2a }, { f: 256, cut: true, s: S2b }],
  3: [{ f: 318, s: S3a }, { f: 352, dur: 40, s: S3b }],
  4: [{ f: 414, s: S4a }, { f: 490, cut: true, s: S4b }],
  5: [{ f: 547, s: S5a }],
  6: [{ f: 592, s: S6a }],
  7: [{ f: 652, s: S7a }],
  8: [{ f: 739, s: S8a }, { f: 754, dur: 28, s: S8b }, { f: 788, cut: true, s: S8c }],
  9: [{ f: 843, s: S9a }],
  10: [{ f: 957, s: S10a }],
  11: [{ f: 1080, s: S11a }, { f: 1144, dur: 34, s: S11b }],
  12: [{ f: 1206, s: S12a }, { f: 1292, cut: true, s: S12b }],
  13: [{ f: 1366, s: S13a }, { f: 1403, dur: 40, s: S13b }, { f: 1450, dur: 30, s: S13c }],
  14: [{ f: 1499, s: S14a }, { f: 1550, dur: 32, s: S14b }],
  15: [{ f: 1602, s: S15a }],
  16: [{ f: 1737, s: S16a }, { f: 1807, cut: true, s: S16b }, { f: 1835, cut: true, s: S16c }],
  17: [{ f: 1929, s: S17a }, { f: 2003, dur: 60, s: S17b }],
};

// impact kicks: the step dropping into the comb (hook), the paper snatched away
const KICKS: [number, number][] = [[52 / FPS, 0.4], [1809 / FPS, 0.6]];
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
  const L = Math.hypot(...d), hh = Math.hypot(d[0], d[2]) || 1;
  const m = (3 / 640) * Math.tan((c.fov * Math.PI) / 360) * L * a;
  return { ...c, look: [c.look[0] - (d[2] / hh) * m, c.look[1] + 0.6 * m, c.look[2] + (d[0] / hh) * m], roll: c.roll + a * 0.004 };
};

// ---------------- lens: depth of field + foreground framing ----------------
export type Dof = { f: number; dur?: number; cInf: number; focus?: (f: number) => V3 };
export const DOF: Dof[] = [
  { f: 0, cInf: 9, focus: () => [XT - 0.2, RISE + 0.3, 0] },           // hook: the riders arriving at the comb
  { f: 85, cInf: 0 },                                                    // section views stay sharp
  { f: 159, cInf: 0 },                                                   // the hall (wide)
  { f: 256, cInf: 10, focus: () => [HX + 0.2, 1.4, HZ + 1.1] },          // the manager presenting
  { f: 318, cInf: 7 },                                                   // the belt (focus follows the camera)
  { f: 414, cInf: 11, focus: () => [HX + 4.2, beltY(HX + 4.2) + 1.3, HZ] }, // nervous riders
  { f: 490, cInf: 8, focus: () => [HB.x1 + 1.5, HG + 1.4, HZ - 0.1] },   // the staff with the trays
  { f: 547, cInf: 10, focus: () => [HB.x1 + 1.2, HG + 1.3, HZ - 0.4] },  // relief
  { f: 592, cInf: 11, focus: () => [HX - 1.6, 1.4, HZ] },                // the queue
  { f: 652, cInf: 0 },                                                   // section views (loop, drive, wheels, slope, ends)
  { f: 1206, cInf: 14, focus: () => [XT, RISE, 0.05] },                  // comb macro
  { f: 1292, cInf: 11, focus: () => [XT + 0.2, RISE + 0.5, 0] },         // the rider stepping off
  { f: 1366, cInf: 0 },                                                  // section views
  { f: 1602, cInf: 11, focus: () => [XT + 1.4, RISE + 1.4, 1.15] },      // the inspector
  { f: 1737, cInf: 11, focus: () => [XB - 1.6, 1.4, 1.5] },              // the businessman
  { f: 1835, cInf: 0 },                                                  // everyone riding (wide)
  { f: 1934, cInf: 8, focus: (f) => { const r = ride17(f); return [r[0], r[1] + 0.95, 0.55]; } }, // the hand on the rail
  { f: 2003, dur: 40, cInf: 0 },                                         // crane out
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
export const FOREGROUND: Fg[] = [];
export { X0, XB, XT, XS1, RISE };
