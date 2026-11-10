// Timeline of "The Day Boston Drowned in Syrup": shots timed to the voice words (shorts/molasses/voice/words.json),
// the skill's camera grammar, and the state of the props as pure functions of the frame.
// HOOK RULE: frame 0 = the wave already crashing down Commercial Street at the lens, people running at us shouting,
// two of them carried on the crest; "A tidal wave of syrup flooded Boston." is spoken by 1.7 s.
import { STREET, TANK, EL, WHARF_X, OFFICE, COURT, SUBWAY } from "./places";
import type { LightName } from "./lights";

export const FPS = 30;
export const TOTAL = 1940;
export const D0 = 0;
export type V3 = [number, number, number];
export const clamp01 = (x: number) => Math.max(0, Math.min(1, x));
export const smooth = (x: number) => { const u = clamp01(x); return u * u * (3 - 2 * u); };
export const easeOut = (u: number) => 1 - (1 - clamp01(u)) ** 4;
export const easeIn = (u: number) => clamp01(u) ** 2;

export type Light = LightName;
export type Crowd = "hook" | "speed" | "tank" | "office" | "blueprint" | "leak" | "paint" | "match" | "buckets" | "warm" | "groan" | "rivets" | "burst"
  | "smash" | "surf" | "rescue" | "sticky" | "seat" | "phone" | "everything" | "excuse" | "court" | "harbor" | "sniff" | "alcohol" | "ban";
export type ShotDef = { id: number; a: number; b: number; light: Light; crowd: Crowd; sunAz?: number; sunEl?: number; fog?: [number, number] };
const FAR: [number, number] = [90, 700];
export const SHOTS: ShotDef[] = [
  { id: 1, a: 0, b: 58, light: "day", crowd: "hook", fog: FAR, sunAz: 150, sunEl: 40 },        // A tidal wave of syrup flooded Boston.
  { id: 2, a: 58, b: 133, light: "day", crowd: "speed", fog: FAR, sunAz: 140 },     // 1919. Thirty-five miles an hour.
  { id: 3, a: 133, b: 257, light: "day", crowd: "tank", fog: FAR, sunAz: 120 },     // one giant tank. Fifty feet tall, full of molasses.
  { id: 4, a: 257, b: 377, light: "lab", crowd: "office" },                         // not an engineer ... the company's accountant.
  { id: 5, a: 377, b: 438, light: "lab", crowd: "blueprint" },                      // could not even read the blueprints.
  { id: 6, a: 438, b: 519, light: "day", crowd: "leak", fog: FAR, sunAz: 150 },                 // never tested it ... leaked from day one.
  { id: 7, a: 519, b: 586, light: "day", crowd: "paint", fog: FAR, sunAz: 150 },                // His solution? He painted the tank brown.
  { id: 8, a: 586, b: 634, light: "day", crowd: "match", fog: FAR, sunAz: 150 },                // So the leaks would match.
  { id: 9, a: 634, b: 731, light: "day", crowd: "buckets", fog: FAR, sunAz: 150 },              // neighbors ... buckets ... free molasses home.
  { id: 10, a: 731, b: 799, light: "day", crowd: "warm", fog: FAR, sunAz: 130 },    // Then came one warm day in January.
  { id: 11, a: 799, b: 842, light: "day", crowd: "groan", fog: FAR, sunAz: 150 },               // The tank started groaning.
  { id: 12, a: 842, b: 900, light: "day", crowd: "rivets", fog: FAR, sunAz: 150 },              // Rivets popped out like machine-gun fire.
  { id: 13, a: 900, b: 960, light: "day", crowd: "burst", fog: FAR, sunAz: 140 },               // two million gallons came out at once.
  { id: 14, a: 960, b: 1052, light: "day", crowd: "smash", fog: FAR, sunAz: 110 },  // streetcar off its tracks ... truck into the harbor.
  { id: 15, a: 1052, b: 1118, light: "day", crowd: "surf", fog: FAR, sunAz: 140 },              // One boy rode the top of it, like a surfer.
  { id: 16, a: 1118, b: 1248, light: "day", crowd: "rescue", fog: FAR, sunEl: 26 }, // Twenty-one died. Rescuers ... glue.
  { id: 17, a: 1248, b: 1300, light: "day", crowd: "sticky", fog: FAR },            // The whole city got sticky.
  { id: 18, a: 1300, b: 1330, light: "lab", crowd: "seat" },                        // Subway seats.
  { id: 19, a: 1330, b: 1355, light: "lab", crowd: "phone" },                       // Payphones.
  { id: 20, a: 1355, b: 1381, light: "day", crowd: "everything", fog: FAR },        // Everything.
  { id: 21, a: 1381, b: 1486, light: "day", crowd: "excuse", fog: FAR },            // The company's excuse? A bomb, planted by anarchists.
  { id: 22, a: 1486, b: 1600, light: "lab", crowd: "court" },                       // Three years of hearings ... just a bad tank.
  { id: 23, a: 1600, b: 1650, light: "day", crowd: "harbor", fog: FAR, sunAz: 140 },// The harbor stayed brown until summer,
  { id: 24, a: 1650, b: 1708, light: "day", crowd: "sniff", fog: FAR },             // and the streets smelled sweet for decades.
  { id: 25, a: 1708, b: 1792, light: "lab", crowd: "alcohol" },                     // what was all that molasses for? Making alcohol.
  { id: 26, a: 1792, b: TOTAL, light: "lab", crowd: "ban" },                        // The very next day, America approved the law that banned alcohol.
];
export const XFADE: Record<number, number> = { 3: 10, 4: 8, 6: 8, 10: 10, 16: 12, 18: 6, 21: 8, 22: 8, 23: 10, 25: 10 };
export const FLASH_AT = 131;

export const shotAt = (f: number) => SHOTS.find((s) => f >= s.a && f < s.b) ?? SHOTS[SHOTS.length - 1];
export const layersAt = (f: number): { id: number; alpha: number }[] => {
  for (const s of SHOTS) {
    const x = XFADE[s.id];
    if (x && f >= s.a - x / 2 && f < s.a + x / 2) return [{ id: s.id - 1, alpha: 1 }, { id: s.id, alpha: (f - (s.a - x / 2) + 1) / (x + 1) }];
  }
  return [{ id: shotAt(f).id, alpha: 1 }];
};

// ---------------- where things are ----------------
export const XC = (STREET.x0 + STREET.x1) / 2;
/** the wave front (world z of its foot) per shot */
export const waveZ = (id: number, f: number) => {
  const s = (a: number) => (f - a) / FPS;
  if (id === 1) return -3.6 + 3.0 * s(0);
  if (id === 2) return 12 + 7 * s(58);
  if (id === 13) return TANK.z + TANK.r * 0.6 + 9 * Math.max(0, s(912));
  if (id === 14) return 6 + 8 * s(960);
  if (id === 15) return 30 + 7 * s(1052);
  return 0;
};
export type WaveState = { on: boolean; z: number; dir: number; hk: number; xc: number; wx: number };
export const waveAt = (id: number, f: number): WaveState => {
  const off: WaveState = { on: false, z: 0, dir: 1, hk: 1, xc: XC, wx: 1 };
  if (id === 1 || id === 2 || id === 14 || id === 15) return { on: true, z: waveZ(id, f), dir: 1, hk: 1, xc: XC, wx: 1 };
  if (id === 13) { const k = smooth((f - 910) / 22); return k > 0 ? { on: true, z: waveZ(id, f), dir: 1, hk: 0.3 + 0.75 * k, xc: TANK.x - 3, wx: 1.5 } : off; }
  return off;
};
export type FloodState = { on: boolean; z0: number; z1: number; y: number };
export const floodAt = (id: number, f: number): FloodState => {
  const w = waveAt(id, f);
  if (w.on) return { on: true, z0: -120, z1: w.z - 15.5, y: 0.9 };
  if (id === 16) return { on: true, z0: -120, z1: 160, y: 0.7 };
  return { on: false, z0: 0, z1: 0, y: 0 };
};
export type TankState = { look: "grey" | "leak" | "brown"; paint: number; burst: number; wobble: number };
export const tankAt = (id: number, f: number): TankState => {
  if (id <= 3) return { look: "grey", paint: 0, burst: 0, wobble: 0 };
  if (id === 6) return { look: "leak", paint: 0, burst: 0, wobble: 0 };
  if (id === 7) return { look: "leak", paint: 0.1 * smooth((f - 552) / 26), burst: 0, wobble: 0 };
  if (id === 11) return { look: "brown", paint: 0, burst: 0, wobble: Math.sin(f * 1.3) * (0.5 + 0.5 * smooth((f - 812) / 20)) };
  if (id === 12) return { look: "brown", paint: 0, burst: 0, wobble: Math.sin(f * 2.1) };
  if (id === 13) return { look: "brown", paint: 0, burst: 1.3 * smooth((f - 905) / 24), wobble: 0 };
  if (id >= 14) return { look: "brown", paint: 0, burst: 1.35, wobble: 0 };
  return { look: "brown", paint: 0, burst: 0, wobble: 0 };
};
/** the streetcar: parked on its rails; knocked over in shot 14, lying tipped after */
export const streetcarAt = (id: number, f: number): { on: boolean; pos: V3; roll: number } => {
  if (id === 14) { const k = smooth((f - 980) / 14); return { on: true, pos: [-2 - 1.4 * k, 0.6 * Math.sin(k * Math.PI) * 0.6 + 1.2 * k, 12 + 2 * k], roll: 1.25 * k }; }
  if (id === 16 || id === 17 || id === 20) return { on: true, pos: [-3.4, 1.2, 14], roll: 1.25 };
  if (id === 1) { const z = waveZ(1, f); return { on: true, pos: [XC + 3.2, 6.3, z - 0.8], roll: 0.9 + f * 0.07 }; }
  if (id === 3) return { on: true, pos: [-2, 0, 4], roll: 0 };
  if (id === 10) return { on: true, pos: [-2, 0, 12], roll: 0 };
  return { on: false, pos: [0, 0, 0], roll: 0 };
};
export const truckAt = (id: number, f: number): { on: boolean; pos: V3; rot: V3 } => {
  if (id === 14) { const s = Math.max(0, (f - 1018) / FPS), k = clamp01(s / 0.8);
    return { on: f < 1046, pos: [10.5 + 18 * k, 6 * Math.sin(Math.min(1, k * 1.15) * Math.PI) - 1.6 * k * k, 22 + 4 * k], rot: [0.3 * k, 0, -2.4 * k] }; }
  if (id === 3 || id === 10) return { on: true, pos: [10.5, 0, 22], rot: [0, 0, 0] };
  return { on: false, pos: [0, 0, 0], rot: [0, 0, 0] };
};
/** the ladder against the tank (street side): its foot 1.2 m out from the wall along LDIR */
export const LDIR: [number, number] = [-0.45, 0.893];
export const boardAt = (id: number, f: number): { on: boolean; pos: V3; rot: V3 } => {
  if (id !== 15) return { on: false, pos: [0, 0, 0], rot: [0, 0, 0] };
  const z = waveZ(15, f), t = f / FPS;
  return { on: true, pos: [XC - 0.85, 7.36 + 0.18 * Math.sin(t * 4), z + 1.62], rot: [0, 0.15, 0.1 * Math.sin(t * 3)] };
};
export const LADDER: V3 = [TANK.x + (TANK.r + 1.2) * LDIR[0], 0, TANK.z + (TANK.r + 1.2) * LDIR[1]];
export const JELL_DESK: V3 = [OFFICE.x, 0, OFFICE.z - 2.35];
export const BOSS_DESK: V3 = [OFFICE.x, 0, OFFICE.z - 2.35];
export const JUDGE: V3 = [COURT.x, 0.5, COURT.z - 3.6];
export const BENCH: V3 = [SUBWAY.x - 1.4, 0, SUBWAY.z - 2.75];
export const BOOTH: V3 = [SUBWAY.x + 2.4, 0, SUBWAY.z - 2.95];
/** the tank wall point facing the street (where the leaks, the paint and the rivets are seen) */
export const WALL: V3 = [TANK.x + TANK.r * LDIR[0], 0, TANK.z + TANK.r * LDIR[1]];
/** a point k metres along the street-side wall (+k toward +x+z), `out` metres out from it, at height y */
export const TANG: [number, number] = [LDIR[1], -LDIR[0]];
export const wallPt = (k: number, out: number, y: number): V3 => [WALL[0] + LDIR[0] * out + TANG[0] * k, y, WALL[2] + LDIR[1] * out + TANG[1] * k];

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
const pushK = (f: number, f0: number, rate: number, punch = 0, n = 35) => {
  const x = Math.max(0, f - f0);
  let s = rate * x;
  if (punch > rate) for (let i = 0; i < Math.min(x, n); i++) s += (punch - rate) * Math.max(0, Math.min(1, (i + 0.5) / 8, (n - i - 0.5) / 8));
  return Math.exp(-s);
};
const dolly = (pos: V3, look: V3, k: number, rest: Partial<Cam> = {}): Shot =>
  ({ pos: [look[0] + (pos[0] - look[0]) * k, look[1] + (pos[1] - look[1]) * k, look[2] + (pos[2] - look[2]) * k], look, ...rest });
const rad = (d: number) => (d * Math.PI) / 180;
const creep = (pos: V3, look: V3, f: number, f0: number, mps: number, rest: Partial<Cam> = {}): Shot => {
  const d = [look[0] - pos[0], look[1] - pos[1], look[2] - pos[2]], n = Math.hypot(d[0], d[1], d[2]) || 1;
  const s = mps * Math.max(0, f - f0) / FPS;
  return { pos: [pos[0] + (d[0] / n) * s, pos[1] + (d[1] / n) * s, pos[2] + (d[2] / n) * s], look: [look[0] + (d[0] / n) * s, look[1] + (d[1] / n) * s, look[2] + (d[2] / n) * s], ...rest };
};
const add3 = (a: V3, dx: number, dy: number, dz: number): V3 => [a[0] + dx, a[1] + dy, a[2] + dz];
const kick = (f: number, at: number, amp: number) => (f >= at && f < at + 8 ? (f % 2 ? 1 : -1) * amp * (1 - (f - at) / 8) : 0);
const shake = (c: Shot, f: number, ats: number[], amp: number): Shot => { let k = 0; for (const at of ats) k += kick(f, at, amp); return { ...c, pos: [c.pos[0] + k, c.pos[1] + k * 0.6, c.pos[2]], look: [c.look[0] + k, c.look[1] + k * 0.6, c.look[2]] }; };
/** rumble: a small continuous flip-shake while the wave is in frame */
const rumble = (c: Shot, f: number, amp: number): Shot => { const k = (f % 2 ? 1 : -1) * amp * (0.6 + 0.4 * Math.sin(f * 0.7)); return { ...c, pos: [c.pos[0] + k, c.pos[1] + k * 0.5, c.pos[2]], look: [c.look[0] + k * 0.5, c.look[1] + k * 0.3, c.look[2]] }; };

// 1: low on Commercial Street, backing away from the wave crashing at the lens; 2: alongside, the wave racing past
export const HOOK_CAM: V3 = [XC - 0.4, 1.15, 8.2];
const S1 = (f: number) => rumble({ pos: [HOOK_CAM[0], HOOK_CAM[1], HOOK_CAM[2] + 0.4 * glide(f / 58)], look: [XC + 0.5, 4.7 + 1.0 * glide(f / 58), -2.0], fov: 64, roll: rad(-4) }, f, 0.035 + 0.04 * glide(f / 50));
const S2 = (f: number) => { const z = waveZ(2, f); return rumble({ pos: [STREET.x0 + 2.2, 2.2, z + 8.5], look: [XC + 3.5, 3.6, z - 1], fov: 56, roll: rad(3) }, f, 0.02); };
// 3: the calm street, the tank in its yard, rising up its side
const S3 = (f: number) => { const u = glide((f - 140) / 110); return { pos: [-6, 2.2 + 1.5 * u, 30 - 3 * u] as V3, look: [TANK.x - 2, 6 + 3.5 * u, TANK.z + 2] as V3, fov: 56 }; };
// 4-5: the office; 5 close on the blueprint
const S4 = (f: number) => dolly(add3(JELL_DESK, 0.1, 1.45, 3.9), add3(JELL_DESK, 0.1, 1.25, 0), pushK(f, 257, 0.0015, 0.005, 25), { fov: 46 });
const S5 = (f: number) => dolly(add3(JELL_DESK, 0.2, 1.45, 2.6), add3(JELL_DESK, 0.2, 1.35, 0), pushK(f, 377, 0.0025, 0.008, 20), { fov: 46, roll: rad(-3) });
// 6-9: at the tank wall (street side)
const S6 = (f: number) => dolly(wallPt(-1.4, 9.5, 1.8), wallPt(-0.6, 0, 3.0), pushK(f, 438, 0.002, 0.006, 25), { fov: 56 });
const S7 = (f: number) => dolly(wallPt(-0.6, 7.0, 3.0), wallPt(0.4, 0, 3.6), pushK(f, 519, 0.002, 0.006, 25), { fov: 54 });
const S8 = (f: number) => dolly(wallPt(-1.2, 4.6, 1.8), wallPt(-0.8, 0, 2.0), pushK(f, 586, 0.003, 0.01, 20), { fov: 52, roll: rad(3) });
const S9 = (f: number) => creep(wallPt(-0.6, 7.2, 1.7), wallPt(0.0, 0.5, 1.4), f, 634, 0.25, { fov: 56 });
// 10: the warm January day, snow banks melting, the brown tank up the street
const S10 = (f: number) => creep([-4.5, 1.8, 30], [5, 4.5, -20], f, 731, 0.6, { fov: 58 });
// 11-12: low at the foot of the tank, the wall groaning; rivets shooting out
const S11 = (f: number) => shake(dolly(wallPt(-0.6, 8.5, 1.0), wallPt(0.0, 0, 5.0), pushK(f, 799, 0.003, 0.01, 20), { fov: 64, roll: rad(-5) }), f, [823, 831], 0.05);
const RIVETS = [858, 864, 869, 874, 878, 882, 887, 891];
const S12 = (f: number) => shake(dolly(wallPt(-0.3, 8.0, 1.8), wallPt(0.0, 0, 2.6), pushK(f, 842, 0.004, 0.01, 20), { fov: 56 }), f, RIVETS, 0.06);
// 13: the burst, wide from up the street
const S13 = (f: number) => shake(creep([16, 8, 8], [TANK.x, 11, TANK.z], f, 900, 0.6, { fov: 62 }), f, [906, 912], 0.18);
// 14: the street, the wave rolling at us, the streetcar tipping, the truck flying into the harbor
const S14a = (f: number) => rumble(shake({ pos: [-4.8, 2.4, 36], look: [3, 3.8, 10], fov: 60, roll: rad(-3) }, f, [984, 1022], 0.12), f, 0.02);
const S14b = (f: number) => rumble(shake({ pos: [-3.8, 2.6, 38], look: [17, 3.5, 22], fov: 60, roll: rad(2) }, f, [1022, 1040], 0.12), f, 0.02);
// 15: up on the el, level with the crest, the boy riding it
const S15 = (f: number) => { const z = waveZ(15, f); return rumble({ pos: [XC - 2.6, 1.9, z + 13.5], look: [XC - 1.0, 7.9, z + 1.5], fov: 30, roll: rad(-4) }, f, 0.01); };
// 16: the flooded street, quiet; sailors wading in
const S16 = (f: number) => creep([-3.5, 3.2, 40], [4, 1.2, 4], f, 1118, 0.35, { fov: 52 });
const S16b = (f: number) => dolly([-1.6, 1.7, 33.5], [-0.2, 1.0, 26.5], pushK(f, 1160, 0.002, 0.006, 25), { fov: 50 });
// 17: a man stuck in the street; 18 subway bench; 19 payphone; 20 everybody stuck
const STUCK: V3 = [0.5, 0, 20];
const S17 = (f: number) => dolly(add3(STUCK, 0.3, 1.2, 3.6), add3(STUCK, 0.2, 0.9, 0), pushK(f, 1248, 0.003, 0.01, 20), { fov: 48 });
const S18 = (f: number) => dolly(add3(BENCH, 0.1, 1.2, 3.4), add3(BENCH, 0.1, 0.9, 0), pushK(f, 1300, 0.005, 0.015, 15), { fov: 46 });
const S19 = (f: number) => dolly(add3(BOOTH, -0.4, 1.6, 3.0), add3(BOOTH, -0.1, 1.4, 0), pushK(f, 1330, 0.005, 0.015, 15), { fov: 46, roll: rad(-3) });
const S20 = (f: number) => creep([XC - 1.5, 1.9, 25], [XC - 1, 1.1, 14], f, 1355, 0.5, { fov: 56 });
// 21: the boss in the street with the reporters
const PRESS: V3 = [-2.5, 0, 30];
const S21 = (f: number) => dolly(add3(PRESS, 0.8, 1.6, 5.6), add3(PRESS, 0.8, 1.7, 0), pushK(f, 1381, 0.002, 0.006, 25), { fov: 50 });
// 22: the court
const S22 = (f: number) => dolly([COURT.x + 0.5, 1.8, COURT.z + 5.4], [COURT.x + 0.6, 1.6, COURT.z - 1.4], pushK(f, 1486, 0.0015, 0.005, 25), { fov: 58 });
// 23: the brown harbor in summer, from the wharf; 24: a man sniffing the sweet air
const S23 = (f: number) => creep([WHARF_X - 6.5, 2.0, 38], [WHARF_X + 10, 0.6, 24], f, 1600, 0.5, { fov: 56 });
const SNIFF: V3 = [-3.0, 0, 26];
const S24 = (f: number) => dolly(add3(SNIFF, 0.3, 1.5, 3.4), add3(SNIFF, 0.2, 1.55, 0), pushK(f, 1650, 0.003, 0.008, 20), { fov: 46 });
// 25-26: the boss's office
const S25 = (f: number) => dolly(add3(BOSS_DESK, 0.0, 1.5, 3.7), add3(BOSS_DESK, 0.0, 1.35, 0), pushK(f, 1708, 0.002, 0.006, 25), { fov: 46 });
const S26 = (f: number) => dolly(add3(BOSS_DESK, 0.0, 1.5, 3.3), add3(BOSS_DESK, 0.0, 1.45, 0), pushK(f, 1792, 0.0015, 0.004, 25) * pushK(f, 1861, 0, 0.012, 14), { fov: 46 });

const CAMS: Record<number, Key[]> = {
  1: [{ f: 0, s: S1 }], 2: [{ f: 58, s: S2 }], 3: [{ f: 133, s: S3 }], 4: [{ f: 257, s: S4 }], 5: [{ f: 377, s: S5 }], 6: [{ f: 438, s: S6 }],
  7: [{ f: 519, s: S7 }], 8: [{ f: 586, s: S8 }], 9: [{ f: 634, s: S9 }], 10: [{ f: 731, s: S10 }], 11: [{ f: 799, s: S11 }], 12: [{ f: 842, s: S12 }],
  13: [{ f: 900, s: S13 }], 14: [{ f: 960, s: S14a }, { f: 1005, dur: 16, s: S14b }], 15: [{ f: 1052, s: S15 }], 16: [{ f: 1118, s: S16 }, { f: 1146, cut: true, s: S16b }], 17: [{ f: 1248, s: S17 }], 18: [{ f: 1300, s: S18 }],
  19: [{ f: 1330, s: S19 }], 20: [{ f: 1355, s: S20 }], 21: [{ f: 1381, s: S21 }], 22: [{ f: 1486, s: S22 }], 23: [{ f: 1600, s: S23 }], 24: [{ f: 1650, s: S24 }],
  25: [{ f: 1708, s: S25 }], 26: [{ f: 1792, s: S26 }],
};
export const camAt = (id: number, f: number): Cam => run(CAMS[id], f);

// ---------------- lens: every shot sharp (user rule) ----------------
export type Dof = { f: number; dur?: number; cInf: number; focus?: (f: number) => V3 };
const DOF: Dof[] = [{ f: 0, cInf: 0 }];
export const dofAt = (_f: number) => { const d = DOF[0]; return { cInf: d.cInf, focus: d.focus }; };
export const focusAt = (id: number, f: number): V3 => camAt(id, f).look;
export type Fg = { a: number; b: number; kit: string; pos: V3; s?: number; yaw?: number };
export const FOREGROUND: Fg[] = [];
export { STREET, TANK, EL, WHARF_X, OFFICE, COURT, SUBWAY, STUCK, PRESS, SNIFF, RIVETS };
