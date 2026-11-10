// Timeline of "The Olympic Marathon Won by Car" (St. Louis, 1904): shots timed to the voice words
// (shorts/marathon/voice/words.json), the skill's camera grammar, and the props' state as pure functions of the frame.
// HOOK RULE: frame 0 = a 1904 car roaring down the dusty road at the lens past exhausted runners, Fred Lorz in the
// back seat waving; "got there by car." is spoken by 2.5 s. Runners run toward -z on the road.
import { ROAD, WELL, MILE9, MILE19, HICKS, ORCHARD, DOGF, BOSTON, STAD, STREET, TANK, EL, WHARF_X, OFFICE, COURT, SUBWAY } from "./places";
import type { LightName } from "./lights";

export const FPS = 30;
export const TOTAL = 2130;
export const D0 = 0;
export type V3 = [number, number, number];
export const clamp01 = (x: number) => Math.max(0, Math.min(1, x));
export const smooth = (x: number) => { const u = clamp01(x); return u * u * (3 - 2 * u); };
export const easeOut = (u: number) => 1 - (1 - clamp01(u)) ** 4;
export const easeIn = (u: number) => clamp01(u) ** 2;

export type Light = LightName;
export type Crowd = "hook" | "setting" | "well" | "science" | "dust" | "cramp" | "ride" | "breakdown" | "finish" | "wreath" | "shout"
  | "hicks" | "poison" | "dose" | "carried" | "mailman" | "shorts" | "fruit" | "nap" | "dog" | "banned" | "boston" | "foot";
export type ShotDef = { id: number; a: number; b: number; light: Light; crowd: Crowd; sunAz?: number; sunEl?: number; fog?: [number, number] };
const HAZE: [number, number] = [40, 420];
export const SHOTS: ShotDef[] = [
  { id: 1, a: 0, b: 92, light: "day", crowd: "hook", fog: HAZE, sunAz: 140, sunEl: 40 },       // The first man to finish this Olympic marathon... got there by car.
  { id: 2, a: 92, b: 236, light: "day", crowd: "setting", fog: HAZE, sunAz: 120, sunEl: 55 },  // St. Louis, 1904. Ninety degrees, on dusty dirt roads.
  { id: 3, a: 236, b: 338, light: "day", crowd: "well", fog: HAZE, sunAz: 130 },               // The man in charge set up just one water stop. On purpose.
  { id: 4, a: 338, b: 390, light: "day", crowd: "science", fog: HAZE, sunAz: 130 },            // He wanted to study dehydration.
  { id: 5, a: 390, b: 508, light: "day", crowd: "dust", fog: HAZE, sunAz: 150 },               // Officials drove cars ahead ... cloud of dust.
  { id: 6, a: 508, b: 594, light: "day", crowd: "cramp", fog: HAZE, sunAz: 120 },              // At mile nine, a runner named Fred Lorz got cramps.
  { id: 7, a: 594, b: 690, light: "day", crowd: "ride", fog: HAZE, sunAz: 120 },               // So he hopped into a car, and waved ...
  { id: 8, a: 690, b: 800, light: "day", crowd: "breakdown", fog: HAZE, sunAz: 120 },          // Ten miles later, the car broke down. So Fred jogged the rest.
  { id: 9, a: 800, b: 890, light: "day", crowd: "finish", fog: HAZE, sunAz: 140 },             // Fred crossed the line first. The crowd went wild.
  { id: 10, a: 890, b: 993, light: "day", crowd: "wreath", fog: HAZE, sunAz: 130 },            // The President's daughter put a wreath on his head ... the gold.
  { id: 11, a: 993, b: 1055, light: "day", crowd: "shout", fog: HAZE, sunAz: 130 },            // Then someone shouted: he came by car!
  { id: 12, a: 1055, b: 1178, light: "day", crowd: "hicks", fog: HAZE, sunAz: 120 },           // The real leader, Thomas Hicks, wanted to lie down. His trainers said no.
  { id: 13, a: 1178, b: 1284, light: "day", crowd: "poison", fog: HAZE, sunAz: 120 },          // They gave him rat poison, mixed with egg whites... and a shot of brandy.
  { id: 14, a: 1284, b: 1352, light: "day", crowd: "dose", fog: HAZE, sunAz: 120 },            // Then another dose. He started seeing things.
  { id: 15, a: 1352, b: 1452, light: "day", crowd: "carried", fog: HAZE, sunAz: 140 },         // His team carried him over the line, feet still running in the air.
  { id: 16, a: 1452, b: 1555, light: "day", crowd: "mailman", fog: HAZE, sunAz: 120 },         // Fourth place went to a Cuban mailman ... gambling.
  { id: 17, a: 1555, b: 1624, light: "day", crowd: "shorts", fog: HAZE, sunAz: 120 },          // He ran in his street clothes, cut into shorts.
  { id: 18, a: 1624, b: 1704, light: "day", crowd: "fruit", fog: HAZE, sunAz: 120 },           // He snatched two peaches, ate rotten apples from an orchard...
  { id: 19, a: 1704, b: 1770, light: "day", crowd: "nap", fog: HAZE, sunAz: 120 },             // and took a nap. And still came fourth.
  { id: 20, a: 1770, b: 1848, light: "day", crowd: "dog", fog: HAZE, sunAz: 120 },             // Another runner got chased a mile off course by a dog.
  { id: 21, a: 1848, b: 1975, light: "day", crowd: "banned", fog: HAZE, sunAz: 130 },          // And Fred Lorz? Banned for life. The ban lasted six months.
  { id: 22, a: 1975, b: 2040, light: "day", crowd: "boston", fog: HAZE, sunAz: 140 },          // The next spring, he won the Boston Marathon.
  { id: 23, a: 2040, b: TOTAL, light: "day", crowd: "foot", fog: HAZE, sunAz: 130 },           // On foot, this time.
];
export const XFADE: Record<number, number> = {}; // v2: whip pans (WHIPS) replace the crossfades
export const FLASH_AT = 92;

export const shotAt = (f: number) => SHOTS.find((s) => f >= s.a && f < s.b) ?? SHOTS[SHOTS.length - 1];
export const layersAt = (f: number): { id: number; alpha: number }[] => {
  for (const s of SHOTS) {
    const x = XFADE[s.id];
    if (x && f >= s.a - x / 2 && f < s.a + x / 2) return [{ id: s.id - 1, alpha: 1 }, { id: s.id, alpha: (f - (s.a - x / 2) + 1) / (x + 1) }];
  }
  return [{ id: shotAt(f).id, alpha: 1 }];
};

// ---------------- where things are ----------------
const SX = STAD.x;
/** car state: on, position (x, z; on the road surface), yaw (0 = facing -z), travelled distance (wheel spin) */
export type CarState = { on: boolean; x: number; z: number; yaw: number; d: number };
const OFF: CarState = { on: false, x: 0, z: 0, yaw: 0, d: 0 };
/** Lorz's ride (red) */
export const carAt = (id: number, f: number): CarState => {
  if (id === 1) { const d = 3.4 * (f / FPS); return { on: true, x: 1.95, z: -6.5 - d, yaw: 0, d }; }
  if (id === 7) { const s = (f - 594) / FPS, d = s < 0.75 ? 0.6 * s : 0.45 + 5.0 * (s - 0.75) + 0.6 * Math.min(1, s - 0.75); return { on: true, x: 1.35, z: MILE9.z - 3 - d, yaw: 0, d }; }
  if (id === 8) return { on: true, x: 1.35, z: -167.5, yaw: 0, d: 0 }; // the MILE 19 post stands 3.5 m behind it
  if (id === 23) return { on: true, x: -2.0, z: BOSTON.z + 9.5, yaw: 0, d: 0 };
  return OFF;
};
/** the officials' car (green), ahead of the field */
export const offCarAt = (id: number, f: number): CarState => {
  if (id === 5) { const d = 4.2 * ((f - 390) / FPS); return { on: true, x: 0.2, z: 30 - d, yaw: 0, d }; }
  return OFF;
};
export const HOOK_CAM: V3 = [3.3, 1.05, -17.5];
export const SULLY: V3 = [WELL.x + 2.0, ROAD.field, WELL.z + 3.4];
export const CRAMP: V3 = [1.7, 0, MILE9.z + 0.5];
export const ALICE: V3 = [SX - 0.55, 0, -3.3];
export const LORZ_F: V3 = [SX + 0.45, 0, -3.1];
export const CARV: V3 = [0.6, 0, ORCHARD.z + 34];
export const NAP: V3 = [ORCHARD.x + 0.4, ROAD.field, ORCHARD.z + 9.5];
export const BAN: V3 = [SX + 0.2, 0, 10];

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
const kick = (f: number, at: number, amp: number) => (f >= at && f < at + 12 ? amp * Math.sin((f - at) * 1.3) * Math.exp(-(f - at) / 4) : 0); // smooth decaying shake (v3)
const shake = (c: Shot, f: number, ats: number[], amp: number): Shot => { let k = 0; for (const at of ats) k += kick(f, at, amp); return { ...c, pos: [c.pos[0] + k, c.pos[1] + k * 0.6, c.pos[2]], look: [c.look[0] + k, c.look[1] + k * 0.6, c.look[2]] }; };
const rumble = (c: Shot, f: number, amp: number): Shot => { const k = amp * (0.65 * Math.sin(f * 0.55) + 0.35 * Math.sin(f * 1.3 + 1.7)); /* smooth engine vibration (v3) */ return { ...c, pos: [c.pos[0] + k, c.pos[1] + k * 0.5, c.pos[2]], look: [c.look[0] + k * 0.5, c.look[1] + k * 0.3, c.look[2]] }; };


// ================= camera v2: the reference Short's grammar =================
// Wide lens (fov 62-76), characters filling 60-90 % of the frame height, low / high angles and Dutch tilts, every shot
// moving, and whip pans (motion smear) instead of crossfades. `orb` places the lens around a subject:
// az in degrees from +z (0 = camera on the subject's +z side), dist on the ground plane, y absolute.
const orb = (sub: V3, az: number, dist: number, y: number, lookY: number, rest: Partial<Cam> = {}, lookOff: [number, number] = [0, 0]): Shot =>
  ({ pos: [sub[0] + Math.sin(rad(az)) * dist, y, sub[2] + Math.cos(rad(az)) * dist], look: [sub[0] + lookOff[0], lookY, sub[2] + lookOff[1]], ...rest });
const lerp = (a: number, b: number, u: number) => a + (b - a) * u;
// v3 (user, 9 Nov: "the camera is still static"): near-constant speed (75 % linear + 25 % ease), sweeps 2-4x larger
const span = (f: number, a: number, b: number) => { const x = clamp01((f - a) / (b - a)); return 0.75 * x + 0.25 * glide(x); };
const SEAT = (c: CarState, lx: number, lz: number): V3 => [c.x - lx, 0, c.z - lz];

// 1: beside the back seat at Lorz's height, sweeping forward round him as the car roars on
const S1 = (f: number) => { const c = carAt(1, f), u = span(f, 0, 92);
  return rumble({ pos: [c.x + lerp(2.5, 1.7, u), lerp(2.25, 1.9, u), c.z - lerp(0.2, 1.3, u)], look: [c.x + 0.3, 1.75, c.z + lerp(1.3, 0.9, u)], fov: 62, roll: rad(lerp(-9, -3, u)) }, f, 0.012); };
// 2: drone dive: steep over the strung-out field, then down to the runners' level and the haze
const S2 = (f: number) => { const u = span(f, 92, 236);
  return { pos: [lerp(1.6, -2.4, u), lerp(12, 2.0, u), lerp(-1.5, -6.5, u)], look: [lerp(0, -0.6, u), lerp(0, 1.5, u), lerp(-14, -24, u)], fov: 70, roll: rad(lerp(16, 3, u)) } as Shot; };
// 3: arcing round the man in charge, the WATER STOP sign and the well beside him
const S3 = (f: number) => { const u = span(f, 236, 338); return orb(SULLY, lerp(78, 22, u), lerp(3.6, 2.4, u), lerp(2.5, 1.85, u), 1.3, { fov: 68, roll: rad(lerp(9, 3, u)) }, [-0.35, -1.5]); };
// 4: rushing in on him and his clipboard, tilted
const S4 = (f: number) => { const u = span(f, 338, 390); return orb(SULLY, lerp(34, -4, u), lerp(2.4, 1.35, u), lerp(2.2, 1.8, u), 1.55, { fov: 62, roll: rad(lerp(-10, -4, u)) }, [0.15, 0]); };
// 5: beside the field in the dust, sliding in toward a coughing runner
const S5 = (f: number) => { const c = offCarAt(5, f), u = span(f, 390, 508);
  return rumble({ pos: [lerp(4.6, 3.3, u), lerp(1.8, 1.25, u), c.z + lerp(8.2, 6.0, u)], look: [-0.6, 1.35, c.z + lerp(6.0, 4.4, u)], fov: 70, roll: rad(lerp(8, 3, u)) }, f, 0.008); };
// 6: swinging round Lorz as he runs up and seizes up by the MILE 9 post, a punch-in on the cramp
const S6 = (f: number) => { const u = span(f, 508, 590), p = f < 567 ? 0 : span(f, 567, 576);
  return orb(CRAMP, lerp(-38, -12, u), lerp(3.2, 2.1, u) - 0.5 * p, lerp(2.4, 1.85, u), 1.25, { fov: 68, roll: rad(lerp(2, 9, u)) }, [0, 0.4]); };
// 7: the lens rides with the car, swinging from behind Lorz round to his side as he waves at the runners he passes
const S7 = (f: number) => { const c = carAt(7, f), L = SEAT(c, -0.3, -0.95), u = span(f, 594, 690);
  return rumble({ pos: [L[0] + lerp(0.6, 1.9, u), lerp(2.6, 2.0, u), L[2] + lerp(2.4, -1.4, u)], look: [L[0] - 0.3, 1.15, L[2] + lerp(-0.6, 0.9, u)], fov: 70, roll: rad(lerp(4, -6, u)) }, f, 0.01); };
// 8: craning down from high over the dead car as it bangs and smokes, then with Lorz as he climbs out and jogs off
const S8a = (f: number) => { const c = carAt(8, f), u = span(f, 690, 770); return shake(orb([c.x, 0, c.z], lerp(195, 135, u), lerp(4.6, 3.0, u), lerp(5.6, 3.2, u), 0.5, { fov: 66, roll: rad(lerp(14, 5, u)) }, [0, -0.6]), f, [730], 0.06); };
const S8b = (f: number) => { const c = carAt(8, f), s = Math.max(0, (f - 772) / FPS), z = c.z + 0.6 - 2.4 * s, u = span(f, 764, 800);
  return { pos: [c.x + lerp(2.6, 1.4, u), lerp(2.4, 1.7, u), z - lerp(3.6, 2.4, u)], look: [c.x + 1.15, 1.25, z + 0.6], fov: 70, roll: rad(lerp(-8, -3, u)) } as Shot; };
// 9: on the cinder at the line, dollying back and looking up: Lorz bursts through the tape over the lens
const S9 = (f: number) => { const u = span(f, 800, 890); return shake({ pos: [SX + lerp(1.6, 0.6, u), lerp(0.3, 0.55, u), lerp(-3.4, -5.6, u)], look: [SX + 0.15, 1.6, 0.5], fov: 74, roll: rad(lerp(-10, -4, u)) }, f, [826], 0.04); };
// 10: arcing round the two-shot at chest height: Alice crowns him, the crowd soft behind
const S10 = (f: number) => { const u = span(f, 890, 993); return { pos: [SX + lerp(1.3, -0.7, u), lerp(2.25, 1.85, u), lerp(-0.2, -0.75, u)], look: [SX - 0.05, 1.35, -3.2], fov: 70, roll: rad(lerp(6, -3, u)) } as Shot; };
// 11: rushing in on the spectator at the wall pointing and shouting; whip back to Alice snatching the medal
const S11 = (f: number) => { const u = span(f, 993, 1031); return { pos: [SX - lerp(0.0, 0.8, u), lerp(2.2, 1.8, u), lerp(3.0, 1.3, u)], look: [SX - 1.95, 1.5, -0.2], fov: 70, roll: rad(lerp(12, 6, u)) } as Shot; };
const S11b = (f: number) => { const u = span(f, 1031, 1055); return shake({ pos: [SX + lerp(0.6, -0.2, u), lerp(2.1, 1.85, u), lerp(-0.3, -1.0, u)], look: [SX - 0.1, 1.35, -3.2], fov: 70, roll: rad(lerp(-7, -2, u)) }, f, [1035], 0.03); };
// 12: circling Hicks wilting between his trainers
const S12 = (f: number) => { const u = span(f, 1055, 1178); return orb([HICKS.x, 0, HICKS.z], lerp(-40, 30, u), lerp(3.3, 2.3, u), lerp(2.4, 1.85, u), 1.3, { fov: 72, roll: rad(lerp(-7, 6, u)) }); };
// 13: closer, swinging between Hicks and the trainer as the bottles pop up one by one
const S13 = (f: number) => { const u = span(f, 1178, 1284); return orb([0.25, 0, HICKS.z], lerp(40, -12, u), lerp(2.9, 1.9, u), lerp(2.3, 1.85, u), 1.4, { fov: 70, roll: rad(lerp(-9, -2, u)) }); };
// 14: tight on Hicks, swaying Dutch tilt and creeping in as he starts seeing things
const S14 = (f: number) => { const u = span(f, 1284, 1352); return shake(orb([HICKS.x - 0.05, 0, HICKS.z], lerp(-25, 15, u), lerp(2.0, 1.2, u), 1.75, 1.82, { fov: 64, roll: rad(12 * Math.sin((f - 1284) / 8)) }), f, [1296], 0.025); };
// 15: worm's-eye at the line, dollying back as Hicks is carried over us, feet pedalling in the air
const S15 = (f: number) => { const u = span(f, 1352, 1452); return { pos: [SX + lerp(1.2, 0.3, u), lerp(0.35, 0.5, u), lerp(-4.3, -5.8, u)], look: [SX, 1.35, 0.5], fov: 74, roll: rad(lerp(10, 4, u)) } as Shot; };
// 16: sweeping round the mailman
const S16 = (f: number) => { const u = span(f, 1452, 1555); return orb(CARV, lerp(50, -30, u), lerp(3.0, 1.8, u), lerp(2.5, 1.9, u), 1.35, { fov: 66, roll: rad(lerp(-6, 5, u)) }); };
// 17: diving low onto the scissors and the trouser legs, his face at the top of frame
const S17 = (f: number) => { const u = span(f, 1555, 1624); return orb(CARV, lerp(55, 10, u), lerp(2.4, 1.5, u), lerp(1.5, 0.75, u), 1.05, { fov: 70, roll: rad(lerp(-10, -4, u)) }); };
// 18: the peaches snatched off the stall as he jogs past; then the apples in the orchard
const S18a = (f: number) => { const z = CARV[2] - 8.5 + 2.5 - 2.6 * ((f - 1624) / FPS), u = span(f, 1624, 1652);
  return { pos: [lerp(3.6, 2.9, u), lerp(2.3, 1.8, u), z - lerp(2.4, 1.4, u)], look: [2.3, 1.2, z + 0.5], fov: 72, roll: rad(lerp(8, 3, u)) } as Shot; };
const S18b = (f: number) => { const u = span(f, 1652, 1704); return orb(NAP, lerp(60, 5, u), lerp(2.6, 1.6, u), lerp(2.3, 1.85, u), 1.35, { fov: 66, roll: rad(lerp(-8, -2, u)) }, [0.1, 0]); };
// 19: craning down onto the sleeping mailman
const S19 = (f: number) => { const u = span(f, 1704, 1770);
  return { pos: [NAP[0] + lerp(0.9, -0.3, u), lerp(2.7, 1.3, u), NAP[2] + lerp(3.7, 2.8, u)], look: [NAP[0] - 0.05, 0.55, NAP[2]], fov: 68, roll: rad(lerp(-12, -3, u)) } as Shot; };
// 20: tracking side-on with the runner, the dog at his heels, the lens sliding in
export const dogRunX = (f: number) => DOGF.x + 2 - 5.0 * ((f - 1770) / FPS);
const S20 = (f: number) => { const x = dogRunX(f), u = span(f, 1770, 1848);
  return rumble({ pos: [x + lerp(1.6, 0.2, u), lerp(1.4, 1.0, u), DOGF.z + lerp(3.6, 2.6, u)], look: [x + 0.55, 1.0, DOGF.z], fov: 66, roll: rad(lerp(-9, -3, u)) }, f, 0.008); };
// 21: Lorz and the stamps: swinging in, slam on BANNED
const S21 = (f: number) => { const u = span(f, 1848, 1975); return shake(orb(BAN, lerp(45, 6, u), lerp(3.2, 2.1, u), lerp(2.3, 1.85, u), 1.4, { fov: 66, roll: rad(lerp(7, -3, u)) }, [0.42, 0]), f, [1886], 0.045); };
// 22: Boston 1905: low under the banner, dollying back and rising as Lorz breaks the tape toward the lens
export const bosZ = (f: number) => BOSTON.z - 3.8 + 4.2 * ((f - 1975) / FPS);
const S22 = (f: number) => { const u = span(f, 1975, 2040); return { pos: [lerp(1.0, -0.2, u), lerp(0.4, 1.1, u), BOSTON.z + lerp(3.2, 5.6, u)], look: [0.0, 2.3, BOSTON.z - 1.0], fov: 74, roll: rad(lerp(-8, -3, u)) } as Shot; };
// 23: tracking ahead of Lorz as he jogs past the parked car, swinging round as he points at his feet
export const footZ = (f: number) => BOSTON.z + 8 + 3.0 * ((f - 2040) / FPS);
const S23 = (f: number) => { const z = footZ(Math.min(f, 2088)), u = span(f, 2040, 2130);
  return { pos: [lerp(2.6, 0.6, u), lerp(2.3, 1.9, u), z + lerp(3.2, 2.0, u)], look: [0.1, 1.15, z - 0.8], fov: 70, roll: rad(lerp(8, -3, u)) } as Shot; };

const CAMS: Record<number, Key[]> = {
  1: [{ f: 0, s: S1 }], 2: [{ f: 92, s: S2 }], 3: [{ f: 236, s: S3 }], 4: [{ f: 338, s: S4 }], 5: [{ f: 390, s: S5 }], 6: [{ f: 508, s: S6 }],
  7: [{ f: 594, s: S7 }], 8: [{ f: 690, s: S8a }, { f: 764, dur: 20, s: S8b }], 9: [{ f: 800, s: S9 }], 10: [{ f: 890, s: S10 }],
  11: [{ f: 993, s: S11 }, { f: 1031, cut: true, s: S11b }], 12: [{ f: 1055, s: S12 }],
  13: [{ f: 1178, s: S13 }], 14: [{ f: 1284, s: S14 }], 15: [{ f: 1352, s: S15 }], 16: [{ f: 1452, s: S16 }], 17: [{ f: 1555, s: S17 }],
  18: [{ f: 1624, s: S18a }, { f: 1652, cut: true, s: S18b }], 19: [{ f: 1704, s: S19 }], 20: [{ f: 1770, s: S20 }], 21: [{ f: 1848, s: S21 }],
  22: [{ f: 1975, s: S22 }], 23: [{ f: 2040, s: S23 }],
};

// ---------------- whip pans: the lens swings away at the end of one view and swings in at the start of the next ----------------
// at = the cut frame; dir +1 = swing one way, -1 the other. The cut hides inside the smear.
const WHIP_W = 4, WHIP_A = 42;
export const WHIPS: { at: number; dir: number }[] = [236, 390, 508, 594, 690, 800, 890, 993, 1031, 1055, 1178, 1352, 1452, 1624, 1652, 1704, 1770, 1848, 1975, 2040]
  .map((at, i) => ({ at, dir: i % 2 ? -1 : 1 }));
/** yaw offset (deg) of the whip at frame f: ease-in before the cut, ease-out after */
export const whipYaw = (f: number) => {
  for (const w of WHIPS) {
    if (f >= w.at - WHIP_W && f < w.at) { const u = (f - (w.at - WHIP_W) + 1) / WHIP_W; return w.dir * WHIP_A * u * u; }
    if (f >= w.at && f < w.at + WHIP_W) { const u = (f - w.at) / WHIP_W; return -w.dir * WHIP_A * (1 - u) * (1 - u); }
  }
  return 0;
};
/** smear vector in px at 1080x1920 for the whip at frame f (angular speed x focal length), for the composer */
export const smearAt = (id: number, f: number): [number, number] => {
  const w = whipYaw(f);
  if (!w) return [0, 0];
  const prev = whipYaw(f - 1) || (f > 0 ? 0 : w), dy = Math.abs(w - prev) > 0 ? w - prev : 0;
  const fov = run(CAMS[id], f).fov, fpx = 960 / Math.tan(rad(fov) / 2);
  const px = Math.min(480, Math.abs(rad(dy)) * fpx * 1.2);
  return [px, 0];
};
const yawAbout = (c: Cam, deg: number): Cam => {
  if (!deg) return c;
  const a = rad(deg), dx = c.look[0] - c.pos[0], dz = c.look[2] - c.pos[2], ca = Math.cos(a), sa = Math.sin(a);
  return { ...c, look: [c.pos[0] + dx * ca - dz * sa, c.look[1], c.pos[2] + dx * sa + dz * ca] };
};
export const camAt = (id: number, f: number): Cam => yawAbout(run(CAMS[id], f), whipYaw(f));

// ---------------- lens: background blur on close-ups, the subject sharp (user, 9 Nov: match the reference) ----------------
// cInf in px at 1080x1920 (x0.75 in the composer); focus = the subject's eyes; wides stay sharp.
export type Dof = { f: number; dur?: number; cInf: number; focus?: (f: number) => V3 };
const eyes = (p: V3, dy = 1.62): V3 => [p[0], dy, p[2]];
const DOFS: Record<number, { cInf: number; focus: (f: number) => V3 }> = {
  1: { cInf: 6, focus: (f) => { const c = carAt(1, f); return [c.x + 0.42, 2.3, c.z + 1.05]; } },
  3: { cInf: 9, focus: () => eyes(SULLY, 1.7) }, 4: { cInf: 13, focus: () => eyes(SULLY, 1.7) },
  6: { cInf: 10, focus: () => eyes(CRAMP) },
  7: { cInf: 8, focus: (f) => { const c = carAt(7, f); return [c.x + 0.3, 1.9, c.z + 0.95]; } },
  9: { cInf: 7, focus: (f) => [SX + 0.2, 1.6, Math.max(-2.8, 4.2 - 4.5 * ((f - 800) / FPS))] },
  10: { cInf: 13, focus: () => [SX - 0.05, 1.65, -3.2] }, 11: { cInf: 12, focus: (f) => (f < 1031 ? [SX - 1.9, 1.7, -0.2] : [SX - 0.05, 1.65, -3.2]) },
  12: { cInf: 10, focus: () => [HICKS.x, 1.65, HICKS.z] }, 13: { cInf: 12, focus: () => [0.25, 1.4, HICKS.z + 0.3] }, 14: { cInf: 14, focus: () => [HICKS.x, 1.8, HICKS.z] },
  16: { cInf: 13, focus: () => eyes(CARV) }, 17: { cInf: 11, focus: () => [CARV[0], 0.9, CARV[2]] },
  20: { cInf: 9, focus: (f) => [dogRunX(f) + 0.5, 1.0, DOGF.z] },
  18: { cInf: 11, focus: (f) => (f < 1652 ? [2.0, 1.6, CARV[2] - 8.5 + 2.5 - 2.6 * ((f - 1624) / FPS)] : eyes(NAP, 1.6)) },
  19: { cInf: 10, focus: () => [NAP[0] - 0.1, 0.42, NAP[2]] },
  21: { cInf: 13, focus: () => eyes(BAN, 1.6) },
  23: { cInf: 9, focus: (f) => [0.6, 1.6, footZ(Math.min(f, 2088))] },
};
export const dofAt = (id: number, _f: number) => { const d = DOFS[id]; return d ? { cInf: d.cInf, focus: d.focus } : { cInf: 0, focus: undefined }; };
export const focusAt = (id: number, f: number): V3 => (DOFS[id]?.focus(f) ?? camAt(id, f).look);
export type Fg = { a: number; b: number; kit: string; pos: V3; s?: number; yaw?: number };
export const FOREGROUND: Fg[] = [];
export { ROAD, WELL, MILE9, MILE19, HICKS, ORCHARD, DOGF, BOSTON, STAD, STREET, TANK, EL, WHARF_X, OFFICE, COURT, SUBWAY };
