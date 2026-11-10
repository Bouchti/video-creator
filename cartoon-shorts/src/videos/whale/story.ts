// Timeline of "Oregon Blew Up a Whale. On Purpose.": shots timed to the voice words (shorts/whale/voice/words.json),
// the camera grammar of the skill (smootherstep glides, big reframes are cuts, every hold creeps in) and the state of
// the props (whale, chunks, car, crowd) as pure functions of the frame.
// HOOK RULE (Nov 7): frame 0 is already mid-blast (blubber flying at the lens), the claim is spoken by 2.0 s, first
// cut at 32 f.
import { WHALE, LOT, CAR, PLUNGER, SIGN, HTRUCK, DYN, KITCHEN, PARK, DEALER } from "./places";
import type { LightName } from "./lights";

export const FPS = 30;
export const TOTAL = 2150;
export const D0 = 0;
export type V3 = [number, number, number];

export const clamp01 = (x: number) => Math.max(0, Math.min(1, x));
export const smooth = (x: number) => { const u = clamp01(x); return u * u * (3 - 2 * u); };
export const easeOut = (u: number) => 1 - (1 - clamp01(u)) ** 4;
export const easeIn = (u: number) => clamp01(u) ** 2;

// ---------------- shots ----------------
export type Light = LightName;
export type Crowd = "none" | "hook" | "purpose" | "coast" | "bus" | "stink" | "highway" | "dept" | "plan" | "pieces" | "gulls" | "dyn" | "walter" | "cases"
  | "park" | "back" | "three" | "two" | "one" | "boom" | "rain" | "wait" | "slowmo" | "jelly" | "flee" | "remains" | "quote" | "memorial" | "relief" | "look" | "crush" | "deal";
export type ShotDef = { id: number; a: number; b: number; light: Light; crowd: Crowd; sunAz?: number; sunEl?: number; fog?: [number, number] };
const FAR: [number, number] = [90, 900];
export const SHOTS: ShotDef[] = [
  { id: 1, a: 0, b: 32, light: "day", crowd: "hook", fog: FAR, sunAz: 120 },          // Oregon blew up a whale.
  { id: 2, a: 32, b: 72, light: "day", crowd: "purpose", fog: FAR, sunAz: 110 },      // On purpose.
  { id: 3, a: 72, b: 159, light: "day", crowd: "coast", fog: FAR, sunAz: 120 },       // November 1970. A dead sperm whale,
  { id: 4, a: 159, b: 236, light: "day", crowd: "bus", fog: FAR, sunAz: 100 },        // longer than a bus, washes up at Florence.
  { id: 5, a: 236, b: 308, light: "day", crowd: "stink", fog: FAR },                  // eight tons, and it stinks.
  { id: 6, a: 308, b: 378, light: "day", crowd: "highway", fog: FAR, sunAz: 110 },    // the beach is legally a highway.
  { id: 7, a: 378, b: 452, light: "day", crowd: "dept", fog: FAR },                   // a job for the highway department.
  { id: 8, a: 452, b: 536, light: "day", crowd: "plan", fog: FAR },                   // George Thornton, has a plan:
  { id: 9, a: 536, b: 584, light: "day", crowd: "pieces", fog: FAR },                 // blow it into tiny pieces,
  { id: 10, a: 584, b: 619, light: "day", crowd: "gulls", fog: FAR, sunAz: 100 },     // and let the seagulls eat them.
  { id: 11, a: 619, b: 676, light: "day", crowd: "dyn", fog: FAR },                   // How much dynamite? Half a ton.
  { id: 12, a: 676, b: 830, light: "day", crowd: "walter", fog: FAR },                // Walter ... twenty sticks is plenty.
  { id: 13, a: 830, b: 873, light: "day", crowd: "cases", fog: FAR },                 // They use twenty cases.
  { id: 14, a: 873, b: 918, light: "day", crowd: "park", fog: FAR },                  // So Walter parks his brand new car,
  { id: 15, a: 918, b: 963, light: "day", crowd: "back", fog: FAR },                  // and the crowd steps way back.
  { id: 16, a: 963, b: 983, light: "day", crowd: "three", fog: FAR },                 // Three.
  { id: 17, a: 983, b: 1003, light: "day", crowd: "two", fog: FAR },                  // Two.
  { id: 18, a: 1003, b: 1020, light: "day", crowd: "one", fog: FAR, sunAz: 100 },     // One.
  { id: 19, a: 1020, b: 1070, light: "day", crowd: "boom", fog: FAR, sunAz: 120 },    // Then it starts raining whale.
  { id: 20, a: 1070, b: 1172, light: "day", crowd: "rain", fog: FAR },                // Huge chunks ... eight hundred feet away.
  { id: 21, a: 1172, b: 1272, light: "day", crowd: "wait", fog: FAR },                // Wait. How does half a ton ...?
  { id: 22, a: 1272, b: 1392, light: "day", crowd: "slowmo", fog: FAR, sunAz: 130, sunEl: 55 }, // dynamite doesn't make things disappear
  { id: 23, a: 1392, b: 1531, light: "lab", crowd: "jelly" },                         // Hit a bowl of jelly with a hammer ...
  { id: 24, a: 1531, b: 1617, light: "day", crowd: "flee", fog: FAR, sunAz: 120 },    // And the seagulls? scared them all away.
  { id: 25, a: 1617, b: 1671, light: "day", crowd: "remains", fog: FAR },             // Most of the whale is still lying there.
  { id: 26, a: 1671, b: 1764, light: "day", crowd: "quote", fog: FAR },               // it went just exactly right.
  { id: 27, a: 1764, b: 1894, light: "day", crowd: "memorial", fog: FAR, sunAz: 120 },         // Fifty years later ... Memorial Park.
  { id: 28, a: 1894, b: 1948, light: "day", crowd: "relief", fog: FAR },              // And Walter's new car?
  { id: 29, a: 1948, b: 1978, light: "day", crowd: "look", fog: FAR, sunAz: 140 },    // A falling chunk of blubber
  { id: 30, a: 1978, b: 2013, light: "day", crowd: "crush", fog: FAR },               // crushed it.
  { id: 31, a: 2013, b: TOTAL, light: "day", crowd: "deal", fog: FAR },               // He had bought it ... a whale of a deal.
];
export const XFADE: Record<number, number> = { 23: 8, 24: 8, 27: 10, 28: 10, 31: 12 };
/** white flash: the hook ends; the blast at "One" */
export const FLASH_AT = 70;
export const FLASH2_AT = 1018;

export const shotAt = (f: number) => SHOTS.find((s) => f >= s.a && f < s.b) ?? SHOTS[SHOTS.length - 1];
export const layersAt = (f: number): { id: number; alpha: number }[] => {
  for (const s of SHOTS) {
    const x = XFADE[s.id];
    if (x && f >= s.a - x / 2 && f < s.a + x / 2) return [{ id: s.id - 1, alpha: 1 }, { id: s.id, alpha: (f - (s.a - x / 2) + 1) / (x + 1) }];
  }
  return [{ id: shotAt(f).id, alpha: 1 }];
};

// ---------------- the blast ----------------
/** the plunger goes down on "One" (1004) + a beat; the blast at 1018 */
export const BLAST = 1018;
/** seconds since the blast as each shot sees it: the hook is already 0.33 s in at frame 0; the slow-motion replay
 *  runs at a fifth of real time until "move", then catches up */
export const blastS = (id: number, f: number): number => {
  if (id <= 2) return (f + 26) / FPS;
  if (id === 22) { const a = 0.3 + ((Math.min(f, 1360) - 1272) / FPS) * 0.2; return f < 1360 ? a : a + ((f - 1360) / FPS) * 1.2; }
  if (id >= 19 && id <= 21) return (f - BLAST) / FPS;
  return id > 21 ? 99 : -1;
};
/** whale state by shot */
export const whaleState = (id: number, f: number): "whole" | "gone" | "remains" =>
  id <= 2 ? "gone" : id < 19 ? "whole" : id <= 21 || id === 22 ? "gone" : "remains";

// ---------------- where people + props stand ----------------
/** the crowd in the lot after stepping back; Thornton at the plunger, the TV crew at the front */
export const THORNTON_PL: V3 = [PLUNGER.x - 0.55, 0, PLUNGER.z + 0.1];
export const TV_AT: V3 = [16, 0, 51.5];
export const WALTER_LOT: V3 = [CAR.x - 4.5, 0, CAR.z - 2.5];
/** the beach scenes before the blast */
export const STINKERS: V3[] = [[7.8, 0, -1.0], [9.4, 0, -1.6]];
export const THORNTON_AT: V3 = [-7.6, 0, 3.4];
export const WALTER_AT: V3 = [4.0, 0, 0.9];
export const THORNTON_W: V3 = [5.4, 0, 0.3];
export const WORKERS: V3[] = [[-19.4, 0, 12.4], [-18.2, 0, 13.2], [-20.5, 0, 13.4]];
/** the beach car in "legally a highway", driving +x along the wet sand */
export const beachCarX = (f: number) => -15.5 + 6 * ((f - 308) / FPS);
export const BEACH_CAR_Z = -13.5;
/** the highway truck rolls in along +x and stops at HTRUCK by 410 */
export const hwyTruckX = (id: number, f: number) => id === 7 ? HTRUCK.x - 18 * (1 - smooth((f - 378) / 34)) : HTRUCK.x;
/** dynamite cases: count by frame in the stacking shot (20 by "ton") */
export const casesAt = (id: number, f: number) => id === 11 ? Math.min(20, Math.max(0, Math.floor((f - 622) / 2.1))) : id >= 12 && id <= 18 ? 20 : 0;
/** Walter's car: rolls in from +x and stops on "car" (910) */
export const carX = (id: number, f: number) => id === 14 ? CAR.x + 16 * (1 - smooth((f - 873) / 36)) : CAR.x;
/** the crowd's walk back: from the beach (z ~ 30) to the lot (z ~ 52) between 920 and 960 */
export const backK = (id: number, f: number) => id < 15 ? 0 : id === 15 ? smooth((f - 921) / 40) : 1;
/** the falling lump: height factor > 0 while falling (lumpFall param of Car.set), crush 0..1 */
export const LUMP_HIT = 1985;
export const lumpAt = (id: number, f: number) => {
  if (id < 28) return { fall: -1, crush: 0 };
  if (f < 1952) return { fall: -1, crush: 0 };
  if (f < LUMP_HIT) return { fall: Math.max(0, (LUMP_HIT - f) / 33) ** 1.6, crush: 0 };
  return { fall: 0, crush: smooth((f - LUMP_HIT) / 4) };
};
/** the jelly: the hammer lands on "hammer" (1429) */
export const HAMMER_AT = 1431;
export const KIT_TABLE: V3 = [KITCHEN.x, 0, KITCHEN.z - 1.3];
export const PARK_SIGN: V3 = [PARK.x, 0, PARK.z];
export const DEAL_CAR: V3 = [DEALER.x - 1.0, 0, DEALER.z - 2.5];

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
/** impact shake: flips sign every frame, decays over 7 f */
const kick = (f: number, at: number, amp: number) => (f >= at && f < at + 8 ? (f % 2 ? 1 : -1) * amp * (1 - (f - at) / 8) : 0);
const shake = (c: Shot, f: number, at: number, amp: number): Shot => { const k = kick(f, at, amp); return { ...c, pos: [c.pos[0] + k, c.pos[1] + k * 0.6, c.pos[2]], look: [c.look[0] + k, c.look[1] + k * 0.6, c.look[2]] }; };

const W = WHALE;
// 1: from behind the crowd in the lot, telephoto on the blast, blubber flying at the lens; 2: Thornton proud at the plunger
const S1a = (f: number) => shake(creep([15, 1.6, 31], [1.5, 8.0, -5], f, 0, 1.2, { fov: 42, roll: rad(-3) }), f, 0, 0.35);
const S2a = (f: number) => shake(dolly(add3(THORNTON_PL, 1.1, 1.62, 3.2), add3(THORNTON_PL, 0.0, 1.62, 0), pushK(f, 32, 0.004, 0.012, 20), { fov: 44, roll: rad(3) }), f, 46, 0.06);
// 3: high over the coast, the whale small on the sand; 4: the whale beside the bus
const S3a = (f: number) => creep([17, 7, 17], [0.5, 0.8, -5], f, 72, 0.9, { fov: 46 });
const S4a = (f: number) => dolly([-7, 12.5, 25], [0.2, 0.6, -1.2], pushK(f, 159, 0.0016, 0.004, 25), { fov: 46 });
// 5: the whale's head, the two locals fanning; 6: low behind the highway sign, a car driving the beach
const S5a = (f: number) => dolly([11.5, 1.9, 8.4], [7.4, 1.5, -2.6], pushK(f, 236, 0.002, 0.006, 25), { fov: 46 });
const S6a = (f: number) => creep([SIGN.x - 1.6, 1.0, SIGN.z + 7.5], [SIGN.x + 0.4, 2.2, SIGN.z - 6], f, 308, 0.25, { fov: 50, roll: rad(-3) });
// 7: the highway truck rolls in, the workers stare
const S7a = (f: number) => creep([HTRUCK.x - 1.5, 1.8, HTRUCK.z + 9.5], [HTRUCK.x + 6, 1.3, HTRUCK.z - 2], f, 378, 0.25, { fov: 50 });
// 8-9: Thornton with his clipboard and his plan; 10: the gulls on the whale's back
const S8a = (f: number) => dolly(add3(THORNTON_AT, 0.35, 1.62, 3.8), add3(THORNTON_AT, 0.3, 1.75, 0), pushK(f, 452, 0.002, 0.006, 25), { fov: 44 });
const S9a = (f: number) => dolly(add3(THORNTON_AT, 0.35, 1.62, 3.5), add3(THORNTON_AT, 0.3, 1.75, 0), pushK(f, 536, 0.0025, 0.008, 22), { fov: 44, roll: rad(2) });
const S10a = (f: number) => dolly([9.0, 3.3, 3.6], [3.2, 2.5, -5], pushK(f, 584, 0.003, 0.01, 20), { fov: 44 });
// 11: the dynamite going in beside the whale; 12: Walter warns; 13: twenty cases
const S11a = (f: number) => dolly([DYN.x + 0.6, 1.8, DYN.z + 7.4], [DYN.x + 0.1, 1.0, DYN.z - 1], pushK(f, 619, 0.002, 0.007, 25), { fov: 46 });
const S12a = (f: number) => dolly(add3(WALTER_AT, 0.7, 1.6, 5.6), add3(WALTER_AT, 0.7, 1.4, 0), pushK(f, 676, 0.0018, 0.005, 25), { fov: 44 });
const S12b = (f: number) => dolly(add3(WALTER_AT, 0.25, 1.6, 2.7), add3(WALTER_AT, 0.25, 1.55, 0), pushK(f, 760, 0.003, 0.01, 22), { fov: 42 });
const S13a = (f: number) => dolly([3.1, 2.1, 7.6], [2.6, 1.2, -2.6], pushK(f, 830, 0.003, 0.01, 20), { fov: 46 });
// 14: Walter's new car rolls into the lot; 15: from the whale, the crowd backing off toward the lot
const S14a = (f: number) => creep([CAR.x - 3.2, 1.55, CAR.z + 8.6], [CAR.x + 0.6, 0.95, CAR.z], f, 873, 0.2, { fov: 46 });
const S15a = (f: number) => creep([28, 2.0, 34.5], [28, 1.2, 50], f, 918, 0.4, { fov: 50 });
// 16-18: the countdown: Thornton's hands on the plunger, the crowd with fingers in ears, a gull on the whale
const S16a = (f: number) => dolly(add3(THORNTON_PL, 0.35, 1.3, 2.4), add3(THORNTON_PL, 0.35, 1.15, 0), pushK(f, 963, 0.004, 0.014, 18), { fov: 42 });
const S17a = (f: number) => dolly([WALTER_LOT[0] - 0.3, 1.6, WALTER_LOT[2] - 4.4], [WALTER_LOT[0] - 0.3, 1.5, WALTER_LOT[2] + 1], pushK(f, 983, 0.004, 0.014, 18), { fov: 44 });
const S18a = (f: number) => dolly([6.6, 2.5, 4.4], [3.4, 1.9, -5], pushK(f, 1003, 0.004, 0.015, 15), { fov: 44 });
// 19: the blast, like the hook but wider; 20: high behind the crowd, the chunks raining onto the lot
const S19a = (f: number) => shake(creep([30, 1.9, 70], [4, 8, -5], f, 1020, 0.8, { fov: 40, roll: rad(-2) }), f, 1020, 0.4);
const S20a = (f: number) => creep([35.6, 1.7, 75], [35.0, 2.0, 58], f, 1070, 0.9, { fov: 48 });
// 21: Walter in the blubber; 22: the slow-motion replay from high above
const S21a = (f: number) => dolly([WALTER_LOT[0] + 0.3, 1.6, WALTER_LOT[2] + 3.6], [WALTER_LOT[0] + 0.3, 1.5, WALTER_LOT[2]], pushK(f, 1172, 0.002, 0.008, 25), { fov: 44, roll: rad(-4) });
const S22a = (f: number) => { const a = rad(70 - 0.12 * (f - 1272)), r = 46; return { pos: [W.x + Math.cos(a) * r, 26, W.z + Math.sin(a) * r] as V3, look: [W.x, 7, W.z] as V3, fov: 50 }; };
// 23: the kitchen table
const S23a = (f: number) => dolly(add3(KIT_TABLE, 0.0, 1.5, 5.2), add3(KIT_TABLE, 0, 1.0, -0.2), pushK(f, 1392, 0.0018, 0.005, 25), { fov: 58 });
// 24: low on the beach, the gulls taking off from a log; 25: the remains; 26: Thornton's quote
const S24a = (f: number) => creep([-0.6, 0.7, 10.2], [-0.6, 2.3, 3], f, 1531, 0.2, { fov: 54 });
const S25a = (f: number) => creep([7.8, 2.4, 6.0], [1.6, 1.0, -4.6], f, 1617, 0.3, { fov: 50 });
export const QUOTE_AT: V3 = [-4.2, 0, 6.2];
const S26a = (f: number) => dolly(add3(QUOTE_AT, 0.5, 1.62, 4.8), add3(QUOTE_AT, 0.5, 1.55, 0), pushK(f, 1671, 0.002, 0.006, 25), { fov: 44 });
// 27: the park at golden hour, a push onto the sign
const S27a = (f: number) => dolly([PARK.x + 1.5, 1.7, PARK.z + 13], [PARK.x, 1.3, PARK.z], pushK(f, 1764, 0.0035, 0.008, 30), { fov: 48 });
// 28: Walter relieved by his car; 29: looking up past him at the falling lump; 30: the crush
const S28a = (f: number) => dolly([CAR.x - 1.2, 1.6, CAR.z + 6.8], [CAR.x - 1.0, 1.1, CAR.z], pushK(f, 1894, 0.002, 0.005, 25), { fov: 46 });
const S29a = (f: number) => dolly([CAR.x - 2.2, 0.75, CAR.z + 6.6], [CAR.x - 0.9, 3.3, CAR.z], pushK(f, 1948, 0.002, 0.006, 20), { fov: 62, roll: rad(4) });
const S30a = (f: number) => shake({ pos: [CAR.x - 1.3, 1.9, CAR.z + 7.4] as V3, look: [CAR.x - 1.1, 1.15, CAR.z + 0.6] as V3, fov: 50 }, f, LUMP_HIT, 0.12);
// 31: the dealer's lot: Walter and the salesman by the car with the bow, then up to the banner
const S31a = (f: number) => dolly([DEALER.x + 0.1, 1.7, DEALER.z + 7.6], [DEALER.x + 0.0, 1.5, DEALER.z - 2.4], pushK(f, 2013, 0.0015, 0.004, 25), { fov: 48 });
const S31b = (f: number) => creep([DEALER.x - 0.1, 1.9, DEALER.z + 5.6], [DEALER.x - 0.1, 2.75, DEALER.z - 7], f, 2080, 0.2, { fov: 50 });

const CAMS: Record<number, Key[]> = {
  1: [{ f: 0, s: S1a }], 2: [{ f: 32, s: S2a }], 3: [{ f: 72, s: S3a }], 4: [{ f: 159, s: S4a }], 5: [{ f: 236, s: S5a }],
  6: [{ f: 308, s: S6a }], 7: [{ f: 378, s: S7a }], 8: [{ f: 452, s: S8a }], 9: [{ f: 536, s: S9a }], 10: [{ f: 584, s: S10a }],
  11: [{ f: 619, s: S11a }], 12: [{ f: 676, s: S12a }, { f: 760, cut: true, s: S12b }], 13: [{ f: 830, s: S13a }],
  14: [{ f: 873, s: S14a }], 15: [{ f: 918, s: S15a }], 16: [{ f: 963, s: S16a }], 17: [{ f: 983, s: S17a }], 18: [{ f: 1003, s: S18a }],
  19: [{ f: 1020, s: S19a }], 20: [{ f: 1070, s: S20a }], 21: [{ f: 1172, s: S21a }], 22: [{ f: 1272, s: S22a }], 23: [{ f: 1392, s: S23a }],
  24: [{ f: 1531, s: S24a }], 25: [{ f: 1617, s: S25a }], 26: [{ f: 1671, s: S26a }], 27: [{ f: 1764, s: S27a }],
  28: [{ f: 1894, s: S28a }], 29: [{ f: 1948, s: S29a }], 30: [{ f: 1978, s: S30a }], 31: [{ f: 2013, s: S31a }, { f: 2072, dur: 36, s: S31b }],
};
export const camAt = (id: number, f: number): Cam => run(CAMS[id], f);

// ---------------- lens ----------------
export type Dof = { f: number; dur?: number; cInf: number; focus?: (f: number) => V3 };
// user feedback (Nov 4): every subject sharp
const DOF: Dof[] = [{ f: 0, cInf: 0 }];
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
export { LOT, CAR, PLUNGER, SIGN, HTRUCK, DYN, KITCHEN, PARK, DEALER };
