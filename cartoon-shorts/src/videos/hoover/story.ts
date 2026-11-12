// Timeline of "The Man Who Took a Hoover Van Hostage" (Workington, 1993): shots timed to the voice words
// (shorts/hoover/voice/words.json), cameras in the reference grammar (wide lens, close, always moving, whips between
// views), and the vehicles' state as pure functions of the frame.
// HOOK RULE: frame 0 = the horse truck slamming in across the drive behind Dave, BANG on f8; "...took a Hoover van
// hostage." ends at 1.7 s. The film ends back on Dave and the boxed-in van (it loops into the hook).
import { DRV, VAN_PARK, TRUCK_PARK, SHOP, FACT, OFFICE, KITCHEN, WASHER, FRONT_DOOR } from "./places";

export const FPS = 30;
export const TOTAL = 2040;
export type V3 = [number, number, number];
export const clamp01 = (x: number) => Math.max(0, Math.min(1, x));
export const smooth = (x: number) => { const u = clamp01(x); return u * u * (3 - 2 * u); };
export const easeOut = (u: number) => 1 - (1 - clamp01(u)) ** 3;
export const easeIn = (u: number) => clamp01(u) ** 2;

export type Crowd = "hook" | "days" | "blocked" | "why" | "deal" | "scale" | "crowd" | "boxes" | "ads" | "factory" | "office"
  | "bought" | "waiting" | "broke" | "repair" | "parked" | "block" | "court" | "fired" | "flew" | "sold" | "idiot";
export type SetName = "drive" | "shop" | "street" | "factory" | "office" | "kitchen";
export type ShotDef = { id: number; a: number; b: number; crowd: Crowd; set: SetName };
export const SHOTS: ShotDef[] = [
  { id: 1, a: 0, b: 63, crowd: "hook", set: "drive" },          // This man took a Hoover van hostage.
  { id: 2, a: 63, b: 103, crowd: "days", set: "drive" },        // For thirteen days.
  { id: 3, a: 103, b: 185, crowd: "blocked", set: "drive" },    // He blocked it in his driveway... with his horse truck.
  { id: 4, a: 185, b: 255, crowd: "why", set: "drive" },        // Why? It started with a free flight.
  { id: 5, a: 255, b: 459, crowd: "deal", set: "shop" },        // Britain, 1992. Hoover's deal: ... To America.
  { id: 6, a: 459, b: 596, crowd: "scale", set: "shop" },       // The cheapest vacuum cost 119 pounds. The flights were worth 600.
  { id: 7, a: 596, b: 716, crowd: "crowd", set: "street" },     // Hoover expected 50,000 people. It got 300,000.
  { id: 8, a: 716, b: 788, crowd: "boxes", set: "street" },     // People bought vacuums they didn't even need.
  { id: 9, a: 788, b: 910, crowd: "ads", set: "street" },       // The small ads filled up with Hoovers... still in the box.
  { id: 10, a: 910, b: 968, crowd: "factory", set: "factory" }, // The factory went to seven-day shifts.
  { id: 11, a: 968, b: 1113, crowd: "office", set: "office" },  // So Hoover made claiming hard. 14-day deadlines. Flights nobody wanted.
  { id: 12, a: 1113, b: 1215, crowd: "bought", set: "kitchen" },// In Workington, Dave Dixon bought a Hoover washing machine.
  { id: 13, a: 1215, b: 1271, crowd: "waiting", set: "kitchen" },// His tickets never came.
  { id: 14, a: 1271, b: 1325, crowd: "broke", set: "kitchen" }, // Then the washing machine broke.
  { id: 15, a: 1325, b: 1529, crowd: "repair", set: "kitchen" },// The repairman told him: "If you think ... idiot."
  { id: 16, a: 1529, b: 1606, crowd: "parked", set: "drive" },  // So when a Hoover van parked at Dave's house...
  { id: 17, a: 1606, b: 1675, crowd: "block", set: "drive" },   // he blocked it in. With the horse truck.
  { id: 18, a: 1675, b: 1759, crowd: "court", set: "drive" },   // Thirteen days later, the High Court set the van free.
  { id: 19, a: 1759, b: 1829, crowd: "fired", set: "office" },  // And Hoover? It fired three bosses,
  { id: 20, a: 1829, b: 1883, crowd: "flew", set: "drive" },    // flew 220,000 people,
  { id: 21, a: 1883, b: 1938, crowd: "sold", set: "factory" },  // and sold its whole European business.
  { id: 22, a: 1938, b: TOTAL, crowd: "idiot", set: "drive" },  // So... who was the idiot?
];
export const shotAt = (f: number) => SHOTS.find((s) => f >= s.a && f < s.b) ?? SHOTS[SHOTS.length - 1];

// ---------------- vehicles ----------------
/** vehicle state: position on the ground (x, z), yaw (0 = nose to -z), d = wheel turn (radians x 0.45), y lift, roll/pitch */
export type VState = { x: number; z: number; yaw: number; d: number; y?: number; roll?: number; pitch?: number } | null;
const VAN_R = 0.36, TRK_R = 0.5;
const PARKED_VAN: VState = { x: VAN_PARK.x, z: VAN_PARK.z, yaw: 0, d: 0 };
const PARKED_TRK: VState = { x: TRUCK_PARK.x, z: TRUCK_PARK.z, yaw: Math.PI / 2, d: 0 };
const DRIVE_SHOTS = new Set([1, 2, 3, 4, 16, 17, 18, 20, 22]);
/** the white Hoover van */
export const vanAt = (id: number, f: number): VState => {
  if (!DRIVE_SHOTS.has(id)) return null;
  if (id === 16) { const u = easeOut((f - 1529) / 68), z = 13 + (VAN_PARK.z - 13) * u; return { x: VAN_PARK.x, z, yaw: 0, d: ((13 - z) * 0.45) / VAN_R, pitch: f > 1595 && f < 1604 ? 0.012 * Math.sin((f - 1595) * 1.2) : 0 }; }
  if (id === 18 && f >= 1739) { const s = (f - 1739) / FPS, z = VAN_PARK.z + 4.5 * s * s * 2.2; return { x: VAN_PARK.x, z, yaw: 0, d: (-(z - VAN_PARK.z) * 0.45) / VAN_R }; }
  if (id === 20) return null;
  return PARKED_VAN;
};
/** truck reversing (nose to -x, so reversing = moving +x) into the drive mouth, arriving at frame `at` */
const reverseIn = (f: number, f0: number, at: number, from: number): VState => {
  const u = clamp01((f - f0) / (at - f0)), k = 1 - (1 - u) ** 2, x = from + (TRUCK_PARK.x - from) * k;
  const jolt = f >= at && f < at + 10 ? 0.02 * Math.sin((f - at) * 1.4) * Math.exp(-(f - at) / 4) : 0;
  return { x, z: TRUCK_PARK.z, yaw: Math.PI / 2, d: (-(x - from) * 0.45) / TRK_R, roll: jolt };
};
export const HOOK_BANG = 8, BLOCK_BANG = 1629;
/** Dave's horse truck */
export const truckAt = (id: number, f: number): VState => {
  if (id === 1) return reverseIn(f, -10, HOOK_BANG, TRUCK_PARK.x - 4.5);
  if (id === 17) return reverseIn(f, 1606, BLOCK_BANG, TRUCK_PARK.x - 9);
  if (id === 18 && f >= 1724) { const s = (f - 1724) / FPS, x = TRUCK_PARK.x - 3.2 * s * s * 1.6; return { x, z: TRUCK_PARK.z, yaw: Math.PI / 2, d: ((TRUCK_PARK.x - x) * 0.45) / TRK_R }; }
  if (DRIVE_SHOTS.has(id) && id !== 16 && id !== 20) return PARKED_TRK;
  return null;
};
/** the Hoover washing machine in Dave's kitchen (front to +z) */
export const washerAt = (id: number, f: number): VState => {
  if (![12, 13, 14, 15].includes(id)) return null;
  let x = WASHER.x, y = 0, roll = 0;
  if (id === 14) {
    const sh = f < 1303 ? smooth((f - 1275) / 20) : Math.max(0, 1 - (f - 1303) / 10);
    x += 0.035 * sh * Math.sin(f * 2.1); roll = 0.05 * sh * Math.sin(f * 1.7);
    if (f >= 1303 && f < 1314) y = 0.12 * Math.sin(((f - 1303) / 11) * Math.PI);
  }
  return { x, z: WASHER.z, yaw: Math.PI, d: 0, y, roll };
};
export const vehiclesAt = (id: number, f: number) => ({ van: vanAt(id, f), truck: truckAt(id, f), washer: washerAt(id, f) });

// ---------------- where people stand ----------------
export const DAVE_H: V3 = [5.15, 0, -0.4];            // the hook: right of the van's tail, the truck behind him
export const HORSE_WIN: V3 = [1.5, 2.6, 7.75];    // the horse's head in the horsebox window (near side, facing the house)
export const SALES: V3 = [SHOP.x - 0.2, 0, SHOP.counterZ - 0.75];
export const DOOR_EXT: V3 = [SHOP.x + 1.3, 0, 1.3];
export const EXEC_DESK: V3 = [OFFICE.x, 0, OFFICE.deskZ - 0.8];
export const DAVE_K: V3 = [WASHER.x - 1.0, 0, WASHER.z + 1.2];
export const REPAIR_K: V3 = [WASHER.x + 0.75, 0, WASHER.z + 1.05];
export const DOOR_K: V3 = [FRONT_DOOR.x + 0.9, 0, FRONT_DOOR.z];
export const DAVE_DOOR: V3 = [1.15, 0, -5.3];
export const BAILIFF: V3 = [5.05, 0, 4.4];
export const TEA: V3 = [5.15, 0, -0.4];

// ---------------- camera ----------------
export type Cam = { pos: V3; look: V3; fov: number; roll: number };
type Shot = Partial<Cam> & { pos: V3; look: V3 };
type Key = { f: number; dur?: number; cut?: boolean; s: (f: number) => Shot };
export const glide = (u: number) => { const x = clamp01(u); return x * x * x * (x * (6 * x - 15) + 10); };
const mixC = (a: Cam, b: Cam, k: number): Cam => ({
  pos: a.pos.map((v, i) => v + (b.pos[i] - v) * k) as V3, look: a.look.map((v, i) => v + (b.look[i] - v) * k) as V3,
  fov: a.fov + (b.fov - a.fov) * k, roll: a.roll + (b.roll - a.roll) * k,
});
const full = (c: Shot): Cam => ({ fov: 64, roll: 0, ...c });
const run = (keys: Key[], f: number) => {
  let cur = full(keys[0].s(f));
  for (let i = 1; i < keys.length; i++) {
    const k = keys[i];
    if (f < k.f) break;
    cur = k.cut ? full(k.s(f)) : mixC(cur, full(k.s(f)), glide((f - k.f) / (k.dur ?? 24)));
  }
  return cur;
};
const rad = (d: number) => (d * Math.PI) / 180;
const lerp = (a: number, b: number, u: number) => a + (b - a) * u;
const span = (f: number, a: number, b: number) => { const x = clamp01((f - a) / (b - a)); return 0.75 * x + 0.25 * glide(x); };
const kick = (f: number, at: number, amp: number) => (f >= at && f < at + 12 ? amp * Math.sin((f - at) * 1.3) * Math.exp(-(f - at) / 4) : 0);
const shake = (c: Shot, f: number, ats: number[], amp: number): Shot => { let k = 0; for (const at of ats) k += kick(f, at, amp); return { ...c, pos: [c.pos[0] + k, c.pos[1] + k * 0.6, c.pos[2]], look: [c.look[0] + k, c.look[1] + k * 0.6, c.look[2]] }; };
/** the lens around a subject: az in degrees from +z (0 = camera on the subject's +z side), dist on the ground, y absolute */
const orb = (sub: V3, az: number, dist: number, y: number, lookY: number, rest: Partial<Cam> = {}, lookOff: [number, number] = [0, 0]): Shot =>
  ({ pos: [sub[0] + Math.sin(rad(az)) * dist, y, sub[2] + Math.cos(rad(az)) * dist], look: [sub[0] + lookOff[0], lookY, sub[2] + lookOff[1]], ...rest });

// 1: low behind Dave's shoulder line, swinging round him as the truck slams in behind; the HOOVER van at frame left
const S1 = (f: number) => { const u = span(f, 0, 63); return shake(orb(DAVE_H, lerp(132, 150, u), lerp(3.2, 2.5, u), lerp(1.5, 1.35, u), 1.5, { fov: 66, roll: rad(lerp(-9, -3, u)) }, [lerp(-1.3, -0.9, u), lerp(2.6, 1.6, u)]), f, [HOOK_BANG, HOOK_BANG + 3], 0.07); };
// 2: craning up and over: the van boxed in on the drive, the truck across the mouth, Dave standing guard
const S2 = (f: number) => { const u = span(f, 63, 103); return { pos: [lerp(7.2, 8.0, u), lerp(2.6, 8.4, u), lerp(-2.6, -4.6, u)], look: [lerp(4.9, 4.0, u), lerp(1.8, 0.6, u), lerp(0.2, 2.6, u)], fov: 70, roll: rad(lerp(8, 14, u)) } as Shot; };
// 3: sliding along the truck's flank from Dave to the horsebox window, the horse popping out at the lens
const S3 = (f: number) => { const u = span(f, 103, 185), x = lerp(5.6, 2.15, u);
  return { pos: [x, lerp(1.75, 2.3, u), lerp(4.6, 5.0, u)], look: [lerp(4.6, 1.75, u), lerp(1.6, 2.5, u), lerp(7.6, 8.0, u)], fov: 66, roll: rad(lerp(6, -5, u)) } as Shot; };
// 4: worm's-eye at Dave's feet, tilting up past him to the jet crossing the sky
const S4 = (f: number) => { const u = span(f, 185, 255);
  return { pos: [DAVE_H[0] + lerp(1.0, 0.7, u), lerp(0.45, 0.6, u), DAVE_H[2] - lerp(1.9, 1.5, u)], look: [DAVE_H[0] + lerp(0, -0.6, u), lerp(2.0, 9.0, u), DAVE_H[2] + lerp(0.1, 5.8, u)], fov: 72, roll: rad(lerp(-8, 6, u)) } as Shot; };
// 5a: the shop front in the street, flying in through the door; 5b: round the salesman at the counter
const S5a = (f: number) => { const u = span(f, 255, 345);
  return { pos: [SHOP.x + lerp(0.9, 0.1, u), lerp(2.4, 1.7, u), lerp(10.5, -3.2, u)], look: [SHOP.x + lerp(0.6, -0.1, u), lerp(3.3, 1.5, u), lerp(0, -8.5, u)], fov: 70, roll: rad(lerp(-6, 2, u)) } as Shot; };
const S5b = (f: number) => { const u = span(f, 345, 459); return orb(SALES, lerp(24, -18, u), lerp(2.7, 2.0, u), lerp(1.85, 1.7, u), 1.6, { fov: 66, roll: rad(lerp(4, -4, u)) }, [0.15, 0.4]); };
// 6: round the giant scale on the counter, slam on "six hundred"
export const SCALE_AT: V3 = [SHOP.x + 1.25, 1.0, SHOP.counterZ - 0.15];
const S6 = (f: number) => { const u = span(f, 459, 596); return shake(orb([SCALE_AT[0] - 0.2, 0, SCALE_AT[2]], lerp(-24, 14, u), lerp(4.1, 3.3, u), lerp(1.7, 1.95, u), 1.65, { fov: 66, roll: rad(lerp(-6, 5, u)) }), f, [568], 0.06); };
// 7: low along the queue to the man from Hoover at the door; the crowd stampedes past on "three hundred thousand"
const S7 = (f: number) => { const u = span(f, 596, 716);
  return shake({ pos: [SHOP.x + lerp(6.2, 3.3, u), lerp(0.55, 1.2, u), lerp(5.4, 3.7, u)], look: [SHOP.x + lerp(2.0, 1.3, u), lerp(1.7, 1.55, u), lerp(1.4, 1.3, u)], fov: 70, roll: rad(lerp(10, 4, u)) }, f, [680], 0.05); };
// 8: backing away in front of the shopper carrying his tower of boxes out of the door
export const boxManZ = (f: number) => 0.4 + 1.25 * ((f - 716) / FPS);
const S8 = (f: number) => { const z = boxManZ(f), u = span(f, 716, 788);
  return { pos: [SHOP.x + lerp(1.4, 0.4, u), lerp(1.5, 1.85, u), z + lerp(2.6, 2.1, u)], look: [SHOP.x - 0.05, lerp(1.7, 1.55, u), z], fov: 68, roll: rad(lerp(-7, 3, u)) } as Shot; };
// 9a: rushing in on the small ads filling up; 9b: tracking low along a pavement lined with boxed Hoovers for sale
export const PAPER: V3 = [SHOP.x - 3.2, 0, 3.6];
const S9a = (f: number) => { const u = span(f, 788, 852); return { pos: [PAPER[0] + lerp(0.9, 0.25, u), lerp(1.6, 1.5, u), PAPER[2] + lerp(2.6, 1.2, u)], look: [PAPER[0] + 0.05, 1.35, PAPER[2] + 0.3], fov: 62, roll: rad(lerp(8, 2, u)) } as Shot; };
export const ROW_Z = 15.7;
const S9b = (f: number) => { const u = span(f, 852, 910), x = lerp(-3.5, -12.5, u);
  return { pos: [x, lerp(0.55, 0.9, u), ROW_Z - lerp(1.6, 1.3, u)], look: [x - 2.4, 0.45, ROW_Z + 0.1], fov: 70, roll: rad(lerp(-9, -3, u)) } as Shot; };
// 10: rushing along the conveyor against the flow, the clock and the week's shifts on the wall ahead
const S10 = (f: number) => { const s = (f - 910) / FPS, u = span(f, 910, 968);
  return shake({ pos: [FACT.x + lerp(0.8, 0.7, u), lerp(1.5, 1.65, u), 4.5 - 4.2 * s], look: [FACT.x + lerp(-0.4, 0.2, u), lerp(1.25, 1.8, u), -6 - 4.2 * s], fov: 72, roll: rad(lerp(-8, 4, u)) }, f, [944], 0.04); };
// 11: round the boss's desk as the stamps land
const S11 = (f: number) => { const u = span(f, 968, 1113); return shake(orb(EXEC_DESK, lerp(-30, 25, u), lerp(2.9, 2.1, u), lerp(1.85, 1.7, u), 1.45, { fov: 66, roll: rad(lerp(7, -5, u)) }, [0, 0.35]), f, [994, 1004, 1037], 0.03); };
// 12: arcing low round Dave and his new machine
const S12 = (f: number) => { const u = span(f, 1113, 1215); return orb([WASHER.x - 0.4, 0, WASHER.z + 0.6], lerp(-35, 25, u), lerp(2.9, 2.2, u), lerp(1.2, 1.55, u), 1.15, { fov: 66, roll: rad(lerp(-6, 4, u)) }); };
// 13: creeping in on Dave waiting on his suitcase by the front door
const S13 = (f: number) => { const u = span(f, 1215, 1271); return orb(DOOR_K, lerp(110, 80, u), lerp(2.6, 1.8, u), lerp(1.1, 1.0, u), 0.95, { fov: 64, roll: rad(lerp(5, -2, u)) }, [-0.25, 0]); };
// 14: tight on the shaking machine, Dave jumping back
const S14 = (f: number) => { const u = span(f, 1271, 1325); return shake(orb([WASHER.x - 0.75, 0, WASHER.z + 0.9], lerp(25, -5, u), lerp(2.9, 2.5, u), lerp(1.1, 1.35, u), 1.05, { fov: 68, roll: rad(12 * Math.sin((f - 1271) / 5) * 0.4) }), f, [1303], 0.07); };
// 15: over Dave's shoulder onto the repairman; then the swing onto Dave's face for "idiot"
const MID: V3 = [(DAVE_K[0] + REPAIR_K[0]) / 2, 0, (DAVE_K[2] + REPAIR_K[2]) / 2];
const S15a = (f: number) => { const u = span(f, 1325, 1452); return orb(MID, lerp(-10, 18, u), lerp(3.3, 2.8, u), lerp(1.75, 1.7, u), 1.45, { fov: 66, roll: rad(lerp(-4, 3, u)) }, [lerp(0.1, 0.0, u), 0]); };
const S15b = (f: number) => { const u = span(f, 1452, 1529), p = f < 1510 ? 0 : span(f, 1510, 1520);
  return orb(DAVE_K, lerp(60, 30, u), lerp(1.9, 1.35, u) - 0.35 * p, lerp(1.75, 1.7, u), 1.65, { fov: 62, roll: rad(lerp(6, 1, u)) }); };
// 16: from Dave at his front door, the van rolling up the drive toward us
const S16 = (f: number) => { const u = span(f, 1529, 1606), w = span(f, 1576, 1598), vz = vanAt(16, Math.min(f, 1576))?.z ?? 0;
  return { pos: [lerp(-0.6, -0.2, u), lerp(1.6, 1.7, u), lerp(-0.6, -1.6, u)], look: [lerp(3.6, 1.2, w), lerp(1.4, 1.6, w), lerp(vz, -5.0, w)], fov: 66, roll: rad(lerp(-5, 3, u)) } as Shot; };
// 17: from beside the van's tail, the truck reversing across the mouth, BANG, the horse
const S17 = (f: number) => { const u = span(f, 1606, 1675); return shake({ pos: [lerp(5.9, 5.3, u), lerp(1.3, 1.9, u), lerp(1.9, 4.2, u)], look: [lerp(3.4, 2.1, u), lerp(1.6, 2.2, u), lerp(9.0, 8.4, u)], fov: 68, roll: rad(lerp(8, -3, u)) }, f, [BLOCK_BANG], 0.06); };
// 18: the man with the court order walking up; the truck pulls away, the van shoots out backwards
const S18 = (f: number) => { const u = span(f, 1675, 1759); return shake({ pos: [lerp(6.6, 7.3, u), lerp(1.7, 2.6, u), lerp(2.0, 3.0, u)], look: [lerp(5.0, 3.6, u), lerp(1.55, 1.2, u), lerp(4.6, 6.0, u)], fov: 68, roll: rad(lerp(-7, 4, u)) }, f, [1722], 0.05); };
// 19: backing away in front of the three bosses carrying their boxes out
export const firedZ = (f: number) => OFFICE.deskZ + 1.1 + 1.0 * ((f - 1759) / FPS);
const S19 = (f: number) => { const z = firedZ(f), u = span(f, 1759, 1829);
  return shake({ pos: [OFFICE.x + lerp(0.9, -0.4, u), lerp(1.6, 1.8, u), z + lerp(3.0, 2.6, u)], look: [OFFICE.x, 1.4, z], fov: 70, roll: rad(lerp(5, -4, u)) }, f, [1780, 1796, 1806], 0.03); };
// 20: low in the street, whipping up to follow the jumbo over the rooftops
export const planeX = (f: number) => -38 + 30 * ((f - 1829) / FPS);
const S20 = (f: number) => { const u = span(f, 1829, 1883);
  return { pos: [lerp(-3, 4, u), lerp(1.2, 1.6, u), 12.5], look: [planeX(f) + 3, lerp(9, 13, u), -12], fov: 74, roll: rad(lerp(-10, 6, u)) } as Shot; };
// 21: rushing up the factory hall at the end wall as the SOLD sign slams over HOOVER
const S21 = (f: number) => { const u = span(f, 1883, 1938);
  return shake({ pos: [FACT.x + lerp(2.4, 1.0, u), lerp(1.4, 2.6, u), lerp(-14, -24.5, u)], look: [FACT.x + lerp(0.6, 0.2, u), lerp(4.6, 5.2, u), -32], fov: 70, roll: rad(lerp(9, 2, u)) }, f, [1888], 0.06); };
// 22: pushing in on Dave with his tea between the boxed-in van and the truck, swinging round to the hook's angle
const S22 = (f: number) => { const u = span(f, 1938, TOTAL); return orb(TEA, lerp(172, 134, u), lerp(4.2, 3.2, u), lerp(2.3, 1.55, u), 1.3, { fov: 66, roll: rad(lerp(5, -8, u)) }, [lerp(-1.0, -1.3, u), lerp(1.2, 2.6, u)]); };

const CAMS: Record<number, Key[]> = {
  1: [{ f: 0, s: S1 }], 2: [{ f: 63, s: S2 }], 3: [{ f: 103, s: S3 }], 4: [{ f: 185, s: S4 }],
  5: [{ f: 255, s: S5a }, { f: 345, cut: true, s: S5b }], 6: [{ f: 459, s: S6 }], 7: [{ f: 596, s: S7 }], 8: [{ f: 716, s: S8 }],
  9: [{ f: 788, s: S9a }, { f: 852, cut: true, s: S9b }], 10: [{ f: 910, s: S10 }], 11: [{ f: 968, s: S11 }], 12: [{ f: 1113, s: S12 }],
  13: [{ f: 1215, s: S13 }], 14: [{ f: 1271, s: S14 }], 15: [{ f: 1325, s: S15a }, { f: 1452, cut: true, s: S15b }], 16: [{ f: 1529, s: S16 }],
  17: [{ f: 1606, s: S17 }], 18: [{ f: 1675, s: S18 }], 19: [{ f: 1759, s: S19 }], 20: [{ f: 1829, s: S20 }], 21: [{ f: 1883, s: S21 }], 22: [{ f: 1938, s: S22 }],
};

// ---------------- whip pans: the lens swings away at the end of one view and in at the start of the next ----------------
const WHIP_W = 4, WHIP_A = 40;
export const WHIPS: { at: number; dir: number }[] = [63, 185, 255, 345, 459, 596, 716, 788, 852, 910, 968, 1113, 1215, 1271, 1325, 1452, 1529, 1606, 1675, 1759, 1829, 1883, 1938]
  .map((at, i) => ({ at, dir: i % 2 ? -1 : 1 }));
export const whipYaw = (f: number) => {
  for (const w of WHIPS) {
    if (f >= w.at - WHIP_W && f < w.at) { const u = (f - (w.at - WHIP_W) + 1) / WHIP_W; return w.dir * WHIP_A * u * u; }
    if (f >= w.at && f < w.at + WHIP_W) { const u = (f - w.at) / WHIP_W; return -w.dir * WHIP_A * (1 - u) * (1 - u); }
  }
  return 0;
};
const yawAbout = (c: Cam, deg: number): Cam => {
  if (!deg) return c;
  const a = rad(deg), dx = c.look[0] - c.pos[0], dz = c.look[2] - c.pos[2], ca = Math.cos(a), sa = Math.sin(a);
  return { ...c, look: [c.pos[0] + dx * ca - dz * sa, c.look[1], c.pos[2] + dx * sa + dz * ca] };
};
export const camAt = (id: number, f: number): Cam => yawAbout(run(CAMS[id], f), whipYaw(f));

// ---------------- lens: background blur on close-ups, the subject sharp; wides stay sharp ----------------
const eyes = (p: V3, dy = 1.62): V3 => [p[0], dy, p[2]];
const DOFS: Record<number, { cInf: number; focus: (f: number) => V3 }> = {
  1: { cInf: 9, focus: () => eyes(DAVE_H) }, 3: { cInf: 6, focus: (f) => (f < 150 ? [lerp(5.0, 2.0, span(f, 103, 150)), 1.8, 7.6] : [HORSE_WIN[0], HORSE_WIN[1] + 0.2, HORSE_WIN[2]]) },
  5: { cInf: 9, focus: (f) => (f < 345 ? [SHOP.x, 1.6, lerp(0, -8, span(f, 255, 345))] : eyes(SALES)) },
  6: { cInf: 10, focus: () => [SCALE_AT[0] - 0.3, 1.7, SCALE_AT[2]] }, 7: { cInf: 9, focus: () => eyes(DOOR_EXT) },
  8: { cInf: 11, focus: (f) => [SHOP.x, 1.6, boxManZ(f)] }, 9: { cInf: 10, focus: (f) => (f < 852 ? [PAPER[0], 1.35, PAPER[2] + 0.3] : [lerp(-6, -15, span(f, 852, 910)), 0.45, ROW_Z]) },
  11: { cInf: 11, focus: () => eyes(EXEC_DESK) }, 12: { cInf: 10, focus: () => eyes(DAVE_K, 1.55) }, 13: { cInf: 11, focus: () => [DOOR_K[0], 1.2, DOOR_K[2]] },
  14: { cInf: 10, focus: () => [WASHER.x, 0.8, WASHER.z + 0.3] },
  15: { cInf: 12, focus: (f) => (f < 1452 ? eyes(REPAIR_K) : eyes(DAVE_K)) }, 16: { cInf: 6, focus: (f) => [VAN_PARK.x, 1.4, vanAt(16, f)?.z ?? 0] },
  18: { cInf: 7, focus: () => eyes(BAILIFF) }, 19: { cInf: 10, focus: (f) => [OFFICE.x, 1.6, firedZ(f)] }, 22: { cInf: 9, focus: () => eyes(TEA, 1.2) },
};
export const dofAt = (id: number, _f: number) => { const d = DOFS[id]; return d ? { cInf: d.cInf, focus: d.focus } : { cInf: 0, focus: undefined }; };
export const focusAt = (id: number, f: number): V3 => (DOFS[id]?.focus(f) ?? camAt(id, f).look);
export { DRV, VAN_PARK, TRUCK_PARK, SHOP, FACT, OFFICE, KITCHEN, WASHER, FRONT_DOOR };
