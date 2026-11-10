// Timeline of "The Chicken That Lived Without a Head": shots timed to the voice words (shorts/mike/voice/words.json),
// the skill's camera grammar, and the state of the props as pure functions of the frame.
// HOOK RULE: frame 0 = headless Mike mid-crow in the yard, the farmer frozen with the axe; the claim is spoken by 2.3 s.
import { BLOCK, BARN, HOUSE, SCALE, KITCHEN, DESK, SHOW, MOTEL, FEST, COPY } from "./places";
import type { LightName } from "./lights";

export const FPS = 30;
export const TOTAL = 2010;
export const D0 = 0;
export type V3 = [number, number, number];
export const clamp01 = (x: number) => Math.max(0, Math.min(1, x));
export const smooth = (x: number) => { const u = clamp01(x); return u * u * (3 - 2 * u); };
export const easeOut = (u: number) => 1 - (1 - clamp01(u)) ** 4;
export const easeIn = (u: number) => clamp01(u) ** 2;

export type Light = LightName;
export type Crowd = "none" | "hook" | "hookCrow" | "farm" | "pick" | "mil" | "aim" | "whack" | "walkoff" | "morning" | "peck" | "crow" | "nohead" | "wait"
  | "vein" | "stem" | "desk" | "dropper" | "scale" | "tour" | "queue" | "photo" | "money" | "copy" | "eleven" | "motel" | "syringe" | "facepalm" | "fest" | "dinner";
export type ShotDef = { id: number; a: number; b: number; light: Light; crowd: Crowd; sunAz?: number; sunEl?: number; fog?: [number, number] };
const FAR: [number, number] = [120, 1100];
export const SHOTS: ShotDef[] = [
  { id: 1, a: 0, b: 40, light: "day", crowd: "hook", fog: FAR, sunAz: 120 },           // This rooster lived eighteen months
  { id: 2, a: 40, b: 70, light: "day", crowd: "hookCrow", fog: FAR, sunAz: 110 },      // without a head.
  { id: 3, a: 70, b: 123, light: "day", crowd: "farm", fog: FAR, sunAz: 120 },         // Colorado, 1945.
  { id: 4, a: 123, b: 199, light: "day", crowd: "pick", fog: FAR },                    // Farmer Lloyd Olsen picks a rooster for dinner.
  { id: 5, a: 199, b: 269, light: "lab", crowd: "mil" },                               // His mother-in-law is coming, and she loves the neck.
  { id: 6, a: 269, b: 370, light: "day", crowd: "aim", fog: FAR },                     // aims the axe high ... as much neck as possible.
  { id: 7, a: 370, b: 390, light: "day", crowd: "whack", fog: FAR },                   // Whack.
  { id: 8, a: 390, b: 433, light: "day", crowd: "walkoff", fog: FAR },                 // And the chicken just walks away.
  { id: 9, a: 433, b: 504, light: "day", crowd: "morning", fog: FAR, sunAz: 140, sunEl: 30 }, // The next morning, Mike is still walking around.
  { id: 10, a: 504, b: 532, light: "day", crowd: "peck", fog: FAR },                   // Trying to peck.
  { id: 11, a: 532, b: 563, light: "day", crowd: "crow", fog: FAR, sunAz: 110 },       // Trying to crow.
  { id: 12, a: 563, b: 592, light: "day", crowd: "nohead", fog: FAR },                 // With no head.
  { id: 13, a: 592, b: 661, light: "day", crowd: "wait", fog: FAR },                   // Wait. How is that even possible?
  { id: 14, a: 661, b: 778, light: "day", crowd: "vein", fog: FAR },                   // the axe missed the big vein ... clot
  { id: 15, a: 778, b: 907, light: "day", crowd: "stem", fog: FAR },                   // brain stem: breathing, heartbeat, walking
  { id: 16, a: 907, b: 1051, light: "lab", crowd: "desk" },                            // like unplugging a computer screen ...
  { id: 17, a: 1051, b: 1147, light: "day", crowd: "dropper", fog: FAR },              // milk and water with an eyedropper
  { id: 18, a: 1147, b: 1248, light: "day", crowd: "scale", fog: FAR },                // from two and a half pounds to almost eight
  { id: 19, a: 1248, b: 1281, light: "day", crowd: "tour", fog: FAR },                 // He goes on tour.
  { id: 20, a: 1281, b: 1360, light: "day", crowd: "queue", fog: FAR },                // People pay twenty-five cents to see him.
  { id: 21, a: 1360, b: 1407, light: "day", crowd: "photo", fog: FAR },                // Life magazine takes his picture.
  { id: 22, a: 1407, b: 1481, light: "day", crowd: "money", fog: FAR },                // $4,500 a month.
  { id: 23, a: 1481, b: 1554, light: "day", crowd: "copy", fog: FAR },                 // Other farmers try ...
  { id: 24, a: 1554, b: 1620, light: "day", crowd: "eleven", fog: FAR },               // None of them last more than eleven days.
  { id: 25, a: 1620, b: 1691, light: "lab", crowd: "motel" },                          // One night, in a motel, Mike starts to choke.
  { id: 26, a: 1691, b: 1738, light: "night", crowd: "syringe", fog: [40, 300] },      // The syringe that clears his throat?
  { id: 27, a: 1738, b: 1776, light: "lab", crowd: "facepalm" },                       // Lloyd left it at the show.
  { id: 28, a: 1776, b: 1907, light: "day", crowd: "fest", fog: FAR, sunAz: 120 },     // Today ... Mike the Headless Chicken Day.
  { id: 29, a: 1907, b: TOTAL, light: "lab", crowd: "dinner" },                        // And the mother-in-law? She never got her neck.
];
export const XFADE: Record<number, number> = { 3: 8, 5: 8, 6: 8, 9: 10, 14: 8, 16: 8, 17: 8, 19: 10, 23: 8, 25: 10, 28: 10, 29: 10 };
export const FLASH_AT = 68;
export const FLASH2_AT = 372;

export const shotAt = (f: number) => SHOTS.find((s) => f >= s.a && f < s.b) ?? SHOTS[SHOTS.length - 1];
export const layersAt = (f: number): { id: number; alpha: number }[] => {
  for (const s of SHOTS) {
    const x = XFADE[s.id];
    if (x && f >= s.a - x / 2 && f < s.a + x / 2) return [{ id: s.id - 1, alpha: 1 }, { id: s.id, alpha: (f - (s.a - x / 2) + 1) / (x + 1) }];
  }
  return [{ id: shotAt(f).id, alpha: 1 }];
};

// ---------------- where things are ----------------
export const B: V3 = [BLOCK.x, 0, BLOCK.z];
export const LLOYD_BLOCK: V3 = [BLOCK.x - 1.0, 0, BLOCK.z + 0.2];
export const FLOCK: V3 = [-6, 0, -1.5];
/** the hook: Mike struts toward the lens across the yard, Lloyd behind by the stump */
export const hookMike = (f: number): V3 => [0.5 - 0.15 * (f / FPS), 0, 2.2 + 0.5 * (f / FPS)];
/** walking off after the whack: from the stump top down and away along +x */
export const walkoff = (f: number): V3 => { const t = Math.max(0, (f - 396) / FPS); return [BLOCK.x + 0.4 + 1.1 * t, t < 0.3 ? 0.62 * (1 - t / 0.3) : 0, BLOCK.z + 0.3 + 0.2 * t]; };
export const PORCH: V3 = [HOUSE.x - 1.5, 0.3, HOUSE.z + 1.6];
export const morningMike = (f: number): V3 => [4 - 0.7 * ((f - 433) / FPS), 0, -3.5];
export const MIL_AT: V3 = [KITCHEN.x, 0, KITCHEN.z - 2.15];
export const TABLE: V3 = [KITCHEN.x, 0, KITCHEN.z - 1.3];
export const SHOW_MIKE: V3 = [SHOW.x, 1.08, SHOW.z - 2];
export const FEST_STATUE: V3 = [FEST.x, 1.4, FEST.z - 3];
export const DESK_AT: V3 = [DESK.x, 0, DESK.z - 1.65];
export const UNPLUG_AT = 916, DARK_AT = 984;
/** Mike's weight on the scale: 2.5 lb -> 8 lb between "two" and "eight" */
export const lbAt = (f: number) => 2.5 + 5.5 * smooth((f - 1189) / 40);
export const DINNER_MIKE = (f: number): V3 => [KITCHEN.x - 0.85 + 0.55 * ((f - 1925) / FPS), 0.78, KITCHEN.z - 1.0];

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
const shake = (c: Shot, f: number, at: number, amp: number): Shot => { const k = kick(f, at, amp); return { ...c, pos: [c.pos[0] + k, c.pos[1] + k * 0.6, c.pos[2]], look: [c.look[0] + k, c.look[1] + k * 0.6, c.look[2]] }; };

// 1: low in the yard, Mike strutting at the lens, Lloyd and the stump behind; 2: Mike's gurgling crow, close
const S1 = (f: number) => { const m = hookMike(f); return { pos: [m[0] + 0.3, 0.42, m[2] + 1.45] as V3, look: [m[0] - 0.25, 0.9, m[2] - 3.0] as V3, fov: 54, roll: rad(-3) }; };
const S2 = (f: number) => { const m = hookMike(f); return dolly(add3(m, 0.2, 0.5, 1.85), add3(m, 0.05, 0.5, 0), pushK(f, 40, 0.004, 0.012, 20), { fov: 44, roll: rad(3) }); };
// 3: the farm wide with the mesas; 4: Lloyd at the flock
const S3 = (f: number) => creep([16, 5.5, 16], [-2, 2.5, -14], f, 70, 0.8, { fov: 52 });
const S4 = (f: number) => dolly([FLOCK[0] + 1.6, 1.45, FLOCK[2] + 5.4], [FLOCK[0] + 1.7, 0.9, FLOCK[2] + 0.3], pushK(f, 123, 0.002, 0.005, 25), { fov: 48 });
// 5: the mother-in-law at the table
const S5 = (f: number) => dolly(add3(MIL_AT, 0.0, 1.35, 3.1), add3(MIL_AT, 0, 1.2, 0), pushK(f, 199, 0.0025, 0.01, 25), { fov: 44 });
// 6: the stump: Lloyd aims high; 7: whack; 8: Mike walks off
const S6 = (f: number) => dolly(add3(B, -0.45, 1.25, 4.3), add3(B, -0.45, 1.15, 0), pushK(f, 269, 0.0025, 0.008, 25), { fov: 46 });
const S7 = (f: number) => shake({ pos: add3(B, -0.3, 1.2, 3.9), look: add3(B, -0.3, 1.05, 0), fov: 50 }, f, 372, 0.12);
const S8 = (f: number) => creep(add3(B, 1.2, 1.1, 4.8), add3(B, 1.0, 0.75, 0), f, 390, 0.15, { fov: 50 });
// 9: from the porch, morning: Mike strolling across the yard; 10: pecking with the hens; 11: crowing; 12: Lloyd's face
const S9 = (f: number) => { const m = morningMike(f); return creep([m[0] - 2.6, 0.95, m[2] + 3.4], [9.0, 1.6, -11.5], f, 433, 0.2, { fov: 50 }); };
const S10 = (f: number) => { const m = morningMike(f); return dolly(add3(m, 0.2, 0.6, 2.6), add3(m, -0.3, 0.45, 0), pushK(f, 504, 0.003, 0.008, 20), { fov: 46 }); };
const S11 = (f: number) => { const m = morningMike(f); return dolly(add3(m, -0.05, 0.5, 2.2), add3(m, -0.1, 0.72, 0), pushK(f, 532, 0.004, 0.012, 20), { fov: 46, roll: rad(-3) }); };
const S12 = (f: number) => dolly(add3(PORCH, 0.0, 1.55, 2.2), add3(PORCH, 0, 1.5, 0), pushK(f, 563, 0.005, 0.02, 15), { fov: 42 });
const S13 = (f: number) => dolly(add3(PORCH, 0.3, 1.5, 3.4), add3(PORCH, 0.3, 1.35, 0), pushK(f, 592, 0.002, 0.008, 25), { fov: 44, roll: rad(-4) });
// 14-15: Mike on the stump beside the diagram card
const S14 = (f: number) => dolly(add3(B, 0.0, 1.35, 4.5), add3(B, 0.0, 1.35, 0), pushK(f, 661, 0.0015, 0.004, 25), { fov: 44 });
const S15 = (f: number) => dolly(add3(B, 0.0, 1.35, 4.5), add3(B, 0.0, 1.35, 0), pushK(f, 778, 0.0015, 0.004, 25), { fov: 44 });
// 16: the desk
const S16 = (f: number) => dolly(add3(DESK_AT, -0.3, 1.4, 5.0), add3(DESK_AT, -0.3, 1.05, 0), pushK(f, 907, 0.0015, 0.005, 25), { fov: 52 });
// 17: the eyedropper; 18: the scale
const S17 = (f: number) => dolly(add3(B, -0.2, 1.35, 4.5), add3(B, -0.2, 1.15, 0), pushK(f, 1051, 0.002, 0.006, 25), { fov: 44 });
const S18 = (f: number) => dolly([SCALE.x + 0.3, 1.2, SCALE.z + 3.2], [SCALE.x + 0.1, 0.85, SCALE.z], pushK(f, 1147, 0.002, 0.006, 25), { fov: 46 });
// 19-21: the sideshow
const S19 = (f: number) => creep([SHOW.x + 3, 3.0, SHOW.z + 14], [SHOW.x, 3.4, SHOW.z - 6], f, 1248, 0.6, { fov: 52 });
const S20 = (f: number) => dolly([SHOW.x + 1.6, 2.0, SHOW.z + 10.5], [SHOW.x + 1.6, 2.1, SHOW.z - 0.5], pushK(f, 1281, 0.002, 0.005, 25), { fov: 50 });
const S21 = (f: number) => dolly(add3(SHOW_MIKE, 0.5, 0.1, 4.3), add3(SHOW_MIKE, 0.5, 0.05, 0), pushK(f, 1360, 0.003, 0.01, 20), { fov: 46 });
// 22: Lloyd's money, by the booth
const S22 = (f: number) => dolly([SHOW.x + 3.7, 1.65, SHOW.z + 4.1], [SHOW.x + 3.7, 1.55, SHOW.z + 0.9], pushK(f, 1407, 0.003, 0.01, 20), { fov: 44 });
// 23-24: the copycats
const S23 = (f: number) => { const s = (f - 1481) / FPS; return { pos: [COPY.x - 1.5 + 2.6 * s, 1.5, COPY.z + 7.5] as V3, look: [COPY.x - 1.5 + 2.6 * s, 0.9, COPY.z - 0.5] as V3, fov: 52 }; };
const S24 = (f: number) => dolly([COPY.x + 0.0, 1.6, COPY.z + 5.4], [COPY.x + 0.0, 1.4, COPY.z], pushK(f, 1554, 0.002, 0.006, 25), { fov: 46 });
// 25: the motel; 26: the syringe on the dark stage; 27: Lloyd's facepalm
const S25 = (f: number) => dolly([MOTEL.x + 0.1, 1.55, MOTEL.z + 3.2], [MOTEL.x + 0.1, 0.95, MOTEL.z - 2.2], pushK(f, 1620, 0.002, 0.006, 25), { fov: 52 });
const S25b = (f: number) => dolly([MOTEL.x + 1.0, 1.3, MOTEL.z - 0.3], [MOTEL.x + 0.98, 1.15, MOTEL.z - 2.2], pushK(f, 1660, 0.004, 0.012, 20), { fov: 46, roll: rad(3) });
const S26 = (f: number) => dolly([SHOW.x + 0.25, 2.0, SHOW.z + 4.6], [SHOW.x, 2.0, SHOW.z - 2.5], pushK(f, 1691, 0.004, 0.01, 25), { fov: 42 });
const S27 = (f: number) => dolly([MOTEL.x + 1.4, 1.55, MOTEL.z + 1.4], [MOTEL.x + 1.0, 1.45, MOTEL.z - 1.0], pushK(f, 1738, 0.004, 0.012, 20), { fov: 44 });
// 28: the festival street; 29: dinner
const S28 = (f: number) => creep([FEST.x + 32, 2.0, FEST.z], [FEST.x - 2, 3.0, FEST.z], f, 1776, 0.9, { fov: 50 });
const S29 = (f: number) => dolly(add3(TABLE, -0.05, 1.3, 3.3), add3(TABLE, -0.05, 1.1, -0.5), pushK(f, 1907, 0.0015, 0.004, 25), { fov: 50 });

const CAMS: Record<number, Key[]> = {
  1: [{ f: 0, s: S1 }], 2: [{ f: 40, s: S2 }], 3: [{ f: 70, s: S3 }], 4: [{ f: 123, s: S4 }], 5: [{ f: 199, s: S5 }], 6: [{ f: 269, s: S6 }],
  7: [{ f: 370, s: S7 }], 8: [{ f: 390, s: S8 }], 9: [{ f: 433, s: S9 }], 10: [{ f: 504, s: S10 }], 11: [{ f: 532, s: S11 }], 12: [{ f: 563, s: S12 }],
  13: [{ f: 592, s: S13 }], 14: [{ f: 661, s: S14 }], 15: [{ f: 778, s: S15 }], 16: [{ f: 907, s: S16 }], 17: [{ f: 1051, s: S17 }], 18: [{ f: 1147, s: S18 }],
  19: [{ f: 1248, s: S19 }], 20: [{ f: 1281, s: S20 }], 21: [{ f: 1360, s: S21 }], 22: [{ f: 1407, s: S22 }], 23: [{ f: 1481, s: S23 }], 24: [{ f: 1554, s: S24 }],
  25: [{ f: 1620, s: S25 }, { f: 1660, cut: true, s: S25b }], 26: [{ f: 1691, s: S26 }], 27: [{ f: 1738, s: S27 }], 28: [{ f: 1776, s: S28 }], 29: [{ f: 1907, s: S29 }],
};
export const camAt = (id: number, f: number): Cam => run(CAMS[id], f);

// ---------------- lens: every shot sharp (user rule) ----------------
export type Dof = { f: number; dur?: number; cInf: number; focus?: (f: number) => V3 };
const DOF: Dof[] = [{ f: 0, cInf: 0 }];
export const dofAt = (f: number) => { const d = DOF[0]; return { cInf: d.cInf, focus: d.focus }; };
export const focusAt = (id: number, f: number): V3 => camAt(id, f).look;
export type Fg = { a: number; b: number; kit: string; pos: V3; s?: number; yaw?: number };
export const FOREGROUND: Fg[] = [];
export { BLOCK, BARN, HOUSE, SCALE, KITCHEN, DESK, SHOW, MOTEL, FEST, COPY };
