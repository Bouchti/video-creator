// Timeline of "The War Australia Lost to Birds": shots timed to the voice words (shorts/emu/voice/words.json),
// the camera grammar of the skill (smootherstep glides 18-40 f, big reframes are cuts, every hold creeps in) and the
// state of the props (truck, guns, crates, marbles) as pure functions of the frame.
import { CAMP, DAM, CHASE, BURST, OFFICE, PARL, FLOOR } from "./places";
import type { LightName } from "./lights";

export const FPS = 30;
export const TOTAL = 2085;
export const D0 = 0;
export type V3 = [number, number, number];

export const clamp01 = (x: number) => Math.max(0, Math.min(1, x));
export const smooth = (x: number) => { const u = clamp01(x); return u * u * (3 - 2 * u); };
export const easeOut = (u: number) => 1 - (1 - clamp01(u)) ** 4;
export const easeIn = (u: number) => clamp01(u) ** 2;

// ---------------- shots ----------------
export type Light = LightName;
export type Crowd = "none" | "hook" | "won" | "march" | "eat" | "minister" | "lineup" | "camera" | "lunch" | "dam" | "fire" | "truck" | "chase" | "bumpy"
  | "wait" | "flock" | "burst" | "marbles" | "lookout" | "home" | "parliament" | "brass" | "ten" | "report" | "parade";
export type ShotDef = { id: number; a: number; b: number; light: Light; crowd: Crowd; sunAz?: number; sunEl?: number; fog?: [number, number] };
const FAR: [number, number] = [160, 1400];
export const SHOTS: ShotDef[] = [
  { id: 1, a: 0, b: 132, light: "day", crowd: "hook", fog: FAR, sunAz: 110, sunEl: 42 },     // soldiers with machine guns ... a war against birds
  { id: 2, a: 132, b: 167, light: "day", crowd: "won", fog: FAR, sunAz: 120 },               // and the birds won
  { id: 3, a: 167, b: 244, light: "day", crowd: "march", fog: FAR },                         // 20,000 emus marched into the wheat fields
  { id: 4, a: 244, b: 311, light: "day", crowd: "eat", fog: FAR },                           // eating everything
  { id: 5, a: 311, b: 410, light: "lab", crowd: "minister" },                                // the farmers, old soldiers, asked the minister
  { id: 6, a: 410, b: 518, light: "day", crowd: "lineup", fog: FAR },                        // a major, two gunners, two guns, 10,000 bullets
  { id: 7, a: 518, b: 586, light: "day", crowd: "camera", fog: FAR },                        // a cameraman to film the victory
  { id: 8, a: 586, b: 676, light: "day", crowd: "lunch", fog: FAR },                         // "home by lunch"
  { id: 9, a: 676, b: 774, light: "day", crowd: "dam", fog: FAR, sunAz: 120 },               // at a farm dam, a thousand birds
  { id: 10, a: 774, b: 847, light: "day", crowd: "fire", fog: FAR, sunAz: 120 },             // fired, hit twelve, jammed
  { id: 11, a: 847, b: 923, light: "day", crowd: "truck", fog: FAR },                        // a gun on a truck to chase them down
  { id: 12, a: 923, b: 990, light: "day", crowd: "chase", fog: FAR, sunAz: 100 },            // an emu runs 50 km/h
  { id: 13, a: 990, b: 1058, light: "day", crowd: "bumpy", fog: FAR, sunAz: 100 },           // so bumpy, couldn't aim at a thing
  { id: 14, a: 1058, b: 1117, light: "day", crowd: "wait", fog: FAR },                       // wait, how do birds beat a machine gun?
  { id: 15, a: 1117, b: 1262, light: "day", crowd: "flock", fog: FAR, sunAz: 140, sunEl: 55 },// works best on a crowd; refused to stay a crowd
  { id: 16, a: 1262, b: 1366, light: "day", crowd: "burst", fog: FAR, sunAz: 140, sunEl: 55 },// they split into tiny groups, every direction
  { id: 17, a: 1366, b: 1417, light: "lab", crowd: "marbles" },                              // like a dropped bag of marbles
  { id: 18, a: 1417, b: 1545, light: "day", crowd: "lookout", fog: FAR },                    // every group had a lookout
  { id: 19, a: 1545, b: 1590, light: "day", crowd: "home", fog: FAR },                       // the army went home
  { id: 20, a: 1590, b: 1663, light: "lab", crowd: "parliament" },                           // in Parliament ... a medal
  { id: 21, a: 1663, b: 1767, light: "day", crowd: "brass", fog: FAR },                      // they came back ... nearly 10,000 bullets
  { id: 22, a: 1767, b: 1823, light: "day", crowd: "ten", fog: FAR },                        // ten bullets for every emu
  { id: 23, a: 1823, b: 1897, light: "golden", crowd: "report", fog: FAR },                  // the major's report? pure admiration
  { id: 24, a: 1897, b: TOTAL, light: "golden", crowd: "parade", fog: FAR },                 // "If we had a division ... any army in the world"
];
export const XFADE: Record<number, number> = { 3: 8, 5: 8, 6: 8, 9: 8, 11: 8, 12: 8, 14: 8, 15: 8, 17: 8, 18: 8, 19: 8, 20: 8, 21: 8, 23: 10, 24: 10 };
export const FLASH_AT = 163;

export const shotAt = (f: number) => SHOTS.find((s) => f >= s.a && f < s.b) ?? SHOTS[SHOTS.length - 1];
export const layersAt = (f: number): { id: number; alpha: number }[] => {
  for (const s of SHOTS) {
    const x = XFADE[s.id];
    if (x && f >= s.a - x / 2 && f < s.a + x / 2) return [{ id: s.id - 1, alpha: 1 }, { id: s.id, alpha: (f - (s.a - x / 2) + 1) / (x + 1) }];
  }
  return [{ id: shotAt(f).id, alpha: 1 }];
};

// ---------------- where people + guns stand ----------------
/** the hook: the gun in the wheat pointing north (-z), the gunner behind its stock, the loader and the major beside */
export const HOOK_GUN: V3 = [0, 0, -12];
export const HOOK_GUNNER: V3 = [0, 0, -10.75];
export const HOOK_LOADER: V3 = [-0.95, 0, -11.2];
export const HOOK_MAJOR: V3 = [1.05, 0, -10.5];
export const WON_EMU: V3 = [-0.35, 0, -13.0];
/** the farmer at the fence and the emus eating his wheat */
export const FENCE_FARMER: V3 = [6.2, 0, -3.0];
/** the minister's office */
const O = OFFICE, P = PARL, F = FLOOR, C = CAMP;
export const MINISTER_AT: V3 = [O.x, 0, O.z - 2.4];
export const FARMERS_AT: V3[] = [[O.x - 1.05, 0, O.z - 0.55], [O.x, 0, O.z - 0.3], [O.x + 1.05, 0, O.z - 0.55]];
/** the camp line-up (along +x, facing the camera at +z) */
export const LINE_Z = C.z;
export const LINE = { major: C.x, g1: C.x + 0.75, g2: C.x + 1.45, guns: C.x + 2.35, crates: C.x + 3.55 };
export const CAMERA_AT: V3 = [C.x - 3.0, 0, C.z + 2.0];
export const POSE_MAJOR: V3 = [C.x - 0.9, 0, C.z + 1.7];
/** the dam wall top (the guns point east across the water) */
export const DAM_GUN: V3 = [DAM.wallX + 0.55, 1.0, DAM.z];
export const DAM_GUNNER: V3 = [DAM.wallX - 0.5, 0.95, DAM.z];
export const DAM_LOADER: V3 = [DAM.wallX - 0.3, 0.98, DAM.z - 1.2];
export const DAM_MAJOR: V3 = [DAM.wallX - 0.9, 0.85, DAM.z - 2.3];
/** muzzle flashes: the gun fires on "fired" until it jams on "jammed" */
export const FIRE_A = 779, JAM_AT = 826;
export const firing = (f: number) => f >= FIRE_A && f < JAM_AT && (f - FIRE_A) % 3 === 0;
/** the truck: parked at the camp, pulls away on "chase" (894); in the chase it runs along +x at 9 m/s */
export const TRUCK_PARK: V3 = [C.x + 7, 0, C.z - 5];
export const truckAt = (f: number, id: number) => {
  if (id === 11) { const t = Math.max(0, (f - 892) / FPS), s = 0.5 * 3.2 * t * t; return { x: TRUCK_PARK[0] + s, z: TRUCK_PARK[2], yaw: 0, s, bounce: 0, pitch: s > 0 ? 0.02 * Math.sin(f * 0.9) : 0 }; }
  if (id === 12 || id === 13) {
    const s = 9 * ((f - 923) / FPS);
    const bounce = 0.11 * Math.abs(Math.sin(f * 0.55)) + 0.05 * Math.abs(Math.sin(f * 1.7 + 1));
    return { x: CHASE.x + s, z: CHASE.z, yaw: 0, s, bounce, pitch: 0.06 * Math.sin(f * 0.8) };
  }
  if (id === 19) { const s = 7 * ((f - 1545) / FPS); return { x: C.x + 12 - s, z: C.z - 9.5, yaw: Math.PI, s, bounce: 0.02 * Math.abs(Math.sin(f * 0.6)), pitch: 0 }; }
  return { x: TRUCK_PARK[0], z: TRUCK_PARK[2], yaw: 0, s: 0, bounce: 0, pitch: 0 };
};
/** the emus' sprint in the chase: 14 m/s (50 km/h), starting behind the truck and overtaking it */
export const EMU_V = 14;
/** the flock on the plain: tight crowd, then bursting into 11 groups on "shooting" (1271) */
export const BURST_AT = 1271;
export const NGROUP = 11;
/** the parliament: the member asking, standing on the floor in front of the right-hand benches */
export const MP_ASK: V3 = [P.x + 1.6, 0, P.z - 0.6];
/** the brass mountain beside the camp */
export const BRASS: V3 = [C.x + 14, 0, C.z - 1];
export const BRASS_H = 1.45;
/** the report: the major at a camp table under the tent fly */
export const DESK_AT: V3 = [C.x + 3.0, 0, C.z + 1.4];
/** the parade: the emu division marching along +x in front of the saluting major */
export const PARADE_MAJOR: V3 = [C.x - 0.6, 0, C.z - 1.0];
export const PARADE_Z = C.z - 3.4;
export const paradeX = (f: number) => C.x - 11 + 1.3 * ((f - 1897) / FPS);
export const LEAD_STOP = 2012;
/** the marbles: the bag hits the floor on "dropped" */
export const DROP_AT = 1380;
export const MARBLE_FLOOR: V3 = [F.x, 0, F.z - 1.2];

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
/** move pos and look together along the view direction by m metres per second since f0 */
const creep = (pos: V3, look: V3, f: number, f0: number, mps: number, rest: Partial<Cam> = {}): Shot => {
  const d = [look[0] - pos[0], look[1] - pos[1], look[2] - pos[2]], n = Math.hypot(d[0], d[1], d[2]) || 1;
  const s = mps * Math.max(0, f - f0) / FPS;
  return { pos: [pos[0] + (d[0] / n) * s, pos[1] + (d[1] / n) * s, pos[2] + (d[2] / n) * s], look: [look[0] + (d[0] / n) * s, look[1] + (d[1] / n) * s, look[2] + (d[2] / n) * s], ...rest };
};
const add3 = (a: V3, dx: number, dy: number, dz: number): V3 => [a[0] + dx, a[1] + dy, a[2] + dz];

// 1: the soldiers in the wheat aiming north at the flock; 2: the emu in the gunner's hat
const S1a = (f: number) => creep([2.0, 1.55, -5.4], [-0.9, 1.25, -22], f, 0, 0.22, { fov: 52, roll: rad(-2) });
const S1b = (f: number) => dolly([2.4, 1.3, -6.1], [0.1, 1.2, -11.6], pushK(f, 84, 0.0025, 0.006, 25), { fov: 44 });
const S2a = (f: number) => dolly(add3(WON_EMU, 0.25, 1.45, 3.3), add3(WON_EMU, 0.05, 1.35, 0), pushK(f, 132, 0.004, 0.012, 20), { fov: 42, roll: rad(4) });
// 3: high over the wheat, the flock marching in from the north; 4: the fence, the farmer, the emus eating
const S3a = (f: number) => creep([34, 21, 22], [-4, 0, -70], f, 167, 0.9, { fov: 52 });
const S4a = (f: number) => dolly(add3(FENCE_FARMER, 0.3, 1.55, 5.6), add3(FENCE_FARMER, 0.3, 1.05, -4.5), pushK(f, 244, 0.002, 0.005, 25), { fov: 46 });
// 5: the minister's office
const S5a = (f: number) => dolly([O.x + 0.2, 1.75, O.z + 5.4], [O.x, 1.35, O.z - 1.6], pushK(f, 311, 0.0018, 0.004, 25), { fov: 50 });
const S5b = (f: number) => dolly([MINISTER_AT[0] + 0.1, 1.6, MINISTER_AT[2] + 1.85], [MINISTER_AT[0], 1.5, MINISTER_AT[2]], pushK(f, 378, 0.003, 0.008, 22), { fov: 44 });
// 6: a slide along the camp line-up as each thing is named
const lineCam = (x: number) => (f: number): Shot => ({ pos: [x, 1.4, LINE_Z + 5.2] as V3, look: [x, 1.05, LINE_Z - 0.4] as V3, fov: 46 });
// 7: the cameraman cranking, the major posing for him
const S7a = (f: number) => dolly([CAMERA_AT[0] + 1.3, 1.5, CAMERA_AT[2] + 6.2], [CAMERA_AT[0] + 1.3, 1.1, CAMERA_AT[2] - 0.3], pushK(f, 518, 0.002, 0.006, 25), { fov: 48 });
// 8: the gunner, close
const S8a = (f: number) => dolly([LINE.g2 - 0.45, 1.45, LINE_Z + 3.6], [LINE.g2, 1.5, LINE_Z], pushK(f, 586, 0.0028, 0.008, 22), { fov: 40, roll: rad(3) });
// 9: behind the dam wall, the flock walking in across the plain; 10: the gun, close, then the scatter
const S9a = (f: number) => creep([DAM.wallX - 6.5, 3.4, DAM.z + 1.4], [DAM.wallX + 10, 0.5, DAM.z - 2.0], f, 676, 0.25, { fov: 52 });
const S10a = (f: number) => dolly([DAM_GUN[0] - 0.05, 2.1, DAM_GUN[2] + 5.6], [DAM_GUN[0] - 0.05, 1.65, DAM_GUN[2] - 0.3], pushK(f, 774, 0.003, 0.009, 22), { fov: 44 });
/** the hits: across the water at the flock, feathers flying */
const S10h = (f: number) => creep([DAM.x + 7, 1.9, DAM.z + 2], [DAM.x + 22, 0.9, DAM.z - 3], f, 797, 0.4, { fov: 46 });
const S10b = (f: number) => creep([DAM.wallX - 7.5, 2.7, DAM.z + 0.9], [DAM.wallX + 12, 1.0, DAM.z - 1.0], f, 814, 0.25, { fov: 54 });
// 11: the camp, the truck pulls away
const S11a = (f: number) => creep([TRUCK_PARK[0] - 3.2, 1.7, TRUCK_PARK[2] + 8.6], [TRUCK_PARK[0] - 0.4, 1.4, TRUCK_PARK[2]], f, 847, 0.2, { fov: 50 });
// 12: alongside the truck, the emus overtaking; 13: the gunner bouncing on the tray
const S12a = (f: number) => { const t = truckAt(f, 12); return { pos: [t.x + 0.2, 3.6, t.z + 11.5] as V3, look: [t.x + 0.6, 0.9, t.z - 6] as V3, fov: 50 }; };
const S13a = (f: number) => { const t = truckAt(f, 13); return { pos: [t.x - 1.2, 2.4, t.z + 4.4] as V3, look: [t.x - 0.9, 1.9, t.z] as V3, fov: 46, roll: rad(3 * Math.sin(f * 0.5)) }; };
// 14: the major on the dam wall, close: wait, how?
const S14a = (f: number) => dolly(add3(DAM_MAJOR, 0.05, 1.75, 3.4), add3(DAM_MAJOR, 0, 1.45, 0), pushK(f, 1058, 0.003, 0.012, 20), { fov: 40, roll: rad(-4) });
// 15-16: high over the plain: the tight flock, then the burst
const S15a = (f: number) => dolly([BURST.x + 2, 15, BURST.z + 17], [BURST.x, 0, BURST.z - 1], pushK(f, 1117, 0.0012, 0.003, 25), { fov: 42 });
const S16a = (f: number) => { const k = smooth((f - 1262) / 60); return { pos: [BURST.x + 2, 15 + 8 * k, BURST.z + 17 + 7 * k] as V3, look: [BURST.x, 0, BURST.z - 1] as V3, fov: 44 + 6 * k }; };
// 17: the marbles on the floorboards, low
const S17a = (f: number) => dolly(add3(MARBLE_FLOOR, 0.15, 1.05, 1.9), add3(MARBLE_FLOOR, 0, 0.05, -0.15), pushK(f, 1366, 0.0018), { fov: 52 });
// 18: the lookout, close, his group pecking around him
export const LOOKOUT: V3 = [60, 0, -30];
const S18a = (f: number) => dolly(add3(LOOKOUT, 0.4, 1.6, 7.6), add3(LOOKOUT, 0.4, 1.4, -1.2), pushK(f, 1417, 0.0018, 0.005, 25), { fov: 46 });
const S18b = (f: number) => dolly(add3(LOOKOUT, 0.3, 1.75, 5.2), add3(LOOKOUT, 0.3, 1.45, 0), pushK(f, 1500, 0.003, 0.012, 20), { fov: 44 });
// 19: the truck drives off down the farm road, the emus at the fence see it off
const S19a = (f: number) => creep([C.x + 11, 1.7, C.z + 1.5], [C.x + 6, 1.1, C.z - 21], f, 1545, 0.3, { fov: 54 });
// 20: parliament
const S20a = (f: number) => dolly([P.x - 1.4, 2.2, P.z + 5.6], [P.x + 2.2, 1.3, P.z - 1.4], pushK(f, 1590, 0.0018, 0.005, 25), { fov: 48 });
// 21: the brass mountain; 22: the single emu and its ten bullets
const S21a = (f: number) => dolly([BRASS[0] + 1.6, 1.9, BRASS[2] + 8.0], [BRASS[0] + 0.4, 1.3, BRASS[2]], pushK(f, 1663, 0.0018, 0.004, 25), { fov: 48 });
export const TEN_EMU: V3 = [BRASS[0] - 4.5, 0, BRASS[2] + 1.0];
const S22a = (f: number) => dolly(add3(TEN_EMU, 0.1, 1.3, 4.2), add3(TEN_EMU, 0.1, 0.85, 0), pushK(f, 1767, 0.0025, 0.007, 22), { fov: 44 });
// 23: the report at the camp table, golden hour
const S23a = (f: number) => dolly(add3(DESK_AT, 0.15, 1.45, 2.6), add3(DESK_AT, 0, 1.0, -0.4), pushK(f, 1823, 0.0025, 0.006, 25), { fov: 42 });
// 24: the parade passing the saluting major; a last creep on the lead emu's salute
const S24a = (f: number) => creep([PARADE_MAJOR[0] - 0.6, 1.5, PARADE_MAJOR[2] + 6.2], [PARADE_MAJOR[0] + 0.6, 1.0, PARADE_Z - 0.6], f, 1897, 0.12, { fov: 54 });
const S24b = (f: number) => creep([(PARADE_MAJOR[0] + paradeX(LEAD_STOP) + 7.75) / 2, 1.5, PARADE_MAJOR[2] + 6.6], [(PARADE_MAJOR[0] + paradeX(LEAD_STOP) + 7.75) / 2, 1.1, PARADE_Z + 0.6], f, 2012, 0.08, { fov: 50 });

const CAMS: Record<number, Key[]> = {
  1: [{ f: 0, s: S1a }, { f: 84, cut: true, s: S1b }],
  2: [{ f: 132, s: S2a }],
  3: [{ f: 167, s: S3a }],
  4: [{ f: 244, s: S4a }],
  5: [{ f: 311, s: S5a }, { f: 376, cut: true, s: S5b }],
  6: [{ f: 410, s: lineCam(LINE.major + 0.2) }, { f: 432, dur: 20, s: lineCam(LINE.g1 + 0.4) }, { f: 452, dur: 20, s: lineCam(LINE.guns) }, { f: 474, dur: 22, s: lineCam(LINE.crates - 0.6) }, { f: 498, dur: 18, s: (f: number): Shot => ({ pos: [C.x + 1.85, 1.65, LINE_Z + 10.2] as V3, look: [C.x + 1.85, 0.9, LINE_Z - 0.4] as V3, fov: 46 }) }],
  7: [{ f: 518, s: S7a }],
  8: [{ f: 586, s: S8a }],
  9: [{ f: 676, s: S9a }],
  10: [{ f: 774, s: S10a }, { f: 797, cut: true, s: S10h }, { f: 822, cut: true, s: S10a }],
  11: [{ f: 847, s: S11a }],
  12: [{ f: 923, s: S12a }],
  13: [{ f: 990, s: S13a }],
  14: [{ f: 1058, s: S14a }],
  15: [{ f: 1117, s: S15a }],
  16: [{ f: 1262, s: S16a }],
  17: [{ f: 1366, s: S17a }],
  18: [{ f: 1417, s: S18a }, { f: 1498, cut: true, s: S18b }],
  19: [{ f: 1545, s: S19a }],
  20: [{ f: 1590, s: S20a }],
  21: [{ f: 1663, s: S21a }],
  22: [{ f: 1767, s: S22a }],
  23: [{ f: 1823, s: S23a }],
  24: [{ f: 1897, s: S24a }, { f: 2010, cut: true, s: S24b }],
};
export const camAt = (id: number, f: number): Cam => run(CAMS[id], f);

// ---------------- lens ----------------
export type Dof = { f: number; dur?: number; cInf: number; focus?: (f: number) => V3 };
// user feedback (Nov 4): every subject sharp; only the marbles macro keeps a light background blur
const DOF: Dof[] = [
  { f: 0, cInf: 0 },
  { f: 1366, cInf: 5, focus: () => MARBLE_FLOOR },
  { f: 1417, cInf: 0 },
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
