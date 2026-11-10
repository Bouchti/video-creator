// Timeline of the chip short ("The chip in your phone"): shots timed to the voice words (shorts/chip/voice/words.json),
// the cutaway of the EUV scanner, the tin-drop / laser / plasma beats, the switch flips in the chip city, and the camera
// grammar of the skill: smootherstep glides of 18-40 f, big reframes are cuts, every hold creeps in.
import { PLASMA, NOZZLE, CITY, EUV, SQUARE, LAB, KITCHEN, STREET, BEACH, PULLER, STENCIL, MIRROR, SKY, BUMP } from "./chippath";
export { LAB, KITCHEN, STREET, BEACH, PULLER, STENCIL, MIRROR, SKY };
import type { LightName } from "./lights";

export const FPS = 30;
export const TOTAL = 2240;
export const D0 = 0;
export type V3 = [number, number, number];

export const clamp01 = (x: number) => Math.max(0, Math.min(1, x));
export const smooth = (x: number) => { const u = clamp01(x); return u * u * (3 - 2 * u); };
export const easeOut = (u: number) => 1 - (1 - clamp01(u)) ** 4;
export const easeIn = (u: number) => clamp01(u) ** 2;

// ---------------- places ----------------
// ---------------- shots ----------------
export type Light = LightName;
export type Crowd = "none" | "night" | "phone" | "lab" | "labClose" | "press" | "reader" | "city" | "beach" | "puller" | "bay" | "bay2" | "mirror" | "queue" | "ending";
export type ShotDef = { id: number; a: number; b: number; light: Light; crowd: Crowd; sunAz?: number; sunEl?: number };
export const SHOTS: ShotDef[] = [
  { id: 1, a: 0, b: 40, light: "day", crowd: "phone" },                          // the chip inside your phone
  { id: 2, a: 40, b: 186, light: "yellow", crowd: "none", sunAz: 160, sunEl: 30 }, // printed with light: tin drops blasted 50,000 times a second
  { id: 3, a: 186, b: 336, light: "lab", crowd: "lab" },                          // 1947, Bell Labs, one tiny switch
  { id: 4, a: 336, b: 449, light: "lab", crowd: "labClose" },                     // gold foil, germanium, a bent spring
  { id: 5, a: 449, b: 516, light: "lab", crowd: "press" },                        // showed it off (press flashes)
  { id: 6, a: 516, b: 692, light: "golden", crowd: "reader", sunAz: 145, sunEl: 32 },                    // the Times, page 46; luckily / unluckily: the radio column
  { id: 7, a: 692, b: 763, light: "day", crowd: "phone" },                        // today, your phone's chip
  { id: 8, a: 763, b: 839, light: "day", crowd: "city" },                         // twenty billion switches, more than people on Earth
  { id: 9, a: 839, b: 968, light: "day", crowd: "beach" },                        // it starts as sand; one atom in a billion
  { id: 10, a: 968, b: 1101, light: "yellow", crowd: "puller" },                  // a giant crystal, sliced into wafers
  { id: 11, a: 1101, b: 1216, light: "yellow", crowd: "none" },                   // printed layer by layer, like a stencil
  { id: 12, a: 1216, b: 1338, light: "yellow", crowd: "bay" },                    // chip factories glow yellow
  { id: 13, a: 1338, b: 1474, light: "yellow", crowd: "bay2" },                   // normal light too blunt: the machine makes its own
  { id: 14, a: 1474, b: 1643, light: "yellow", crowd: "none", sunAz: 160, sunEl: 30 }, // drop, flatten, blast: plasma
  { id: 15, a: 1643, b: 1752, light: "yellow", crowd: "none", sunAz: 160, sunEl: 30 }, // a vacuum, bouncing off mirrors
  { id: 16, a: 1752, b: 1878, light: "day", crowd: "mirror" },                    // a mirror the size of Germany
  { id: 17, a: 1878, b: 2011, light: "golden", crowd: "none" },                   // 200 tons, three jumbo jets
  { id: 18, a: 2011, b: 2065, light: "day", crowd: "queue" },                     // only one company on Earth
  { id: 19, a: 2065, b: 2116, light: "day", crowd: "ending" },                     // every time you tap your screen
  { id: 20, a: 2116, b: TOTAL, light: "night", crowd: "none" },                   // twenty billion tiny switches flip
];
export const XFADE: Record<number, number> = { 3: 10, 7: 10, 16: 10 };
export const FLASH_AT = 182;

export const shotAt = (f: number) => SHOTS.find((s) => f >= s.a && f < s.b) ?? SHOTS[SHOTS.length - 1];
export const layersAt = (f: number): { id: number; alpha: number }[] => {
  for (const s of SHOTS) {
    const x = XFADE[s.id];
    if (x && f >= s.a - x / 2 && f < s.a + x / 2) return [{ id: s.id - 1, alpha: 1 }, { id: s.id, alpha: (f - (s.a - x / 2) + 1) / (x + 1) }];
  }
  return [{ id: shotAt(f).id, alpha: 1 }];
};

// ---------------- the scanner ----------------
const CUT = new Set([2, 14, 15]);
export const cutAt = (id: number, _f: number) => CUT.has(id);
export type Drop = { y: number; flat: number; flash: number };
const FALL = NOZZLE[1] - 0.08 - PLASMA[1];
/** one drop launched at fl, blasted at fb (pre-pulse fp): position, pancake, plasma */
const dropAt = (f: number, fl: number, fp: number, fb: number, glow = 18): Drop | null => {
  if (f < fl || f > fb + glow * 3) return null;
  const y = f < fp ? NOZZLE[1] - 0.08 - FALL * clamp01((f - fl) / (fp - fl)) : PLASMA[1];
  const flat = f < fp ? 0 : smooth((f - fp) / 6);
  const flash = f < fb ? 0 : f < fb + 4 ? (f - fb) / 4 : Math.exp(-(f - fb - 4) / glow);
  return { y, flat, flash };
};
export const euvAt = (id: number, f: number) => {
  const drops: Drop[] = [];
  let beam = 0, laser = 0;
  if (id === 2) {
    // a stroboscope of the 50,000-a-second stream: a drop every 9 frames, pre-pulse + blast as it reaches the laser
    for (let k = 0; k < 8; k++) {
      const n = Math.floor((f - 40) / 9) + 3 - k, fl = 40 + n * 9 - 30;
      const d = dropAt(f, fl, fl + 30, fl + 32, 4); if (d) drops.push(d);
    }
    beam = 1; laser = 0.35 + 0.65 * ((f % 9) < 4 ? 1 : 0.2);
  } else if (id === 14) {
    const d = dropAt(f, 1474, 1512, 1556, 40); if (d) drops.push(d);
    laser = f >= 1510 && f < 1520 ? 1 : f >= 1554 && f < 1568 ? 1 : 0.15;
    beam = clamp01((f - 1585) / 50);
  } else if (id === 15) { beam = 1; laser = 0.5; for (let k = 0; k < 4; k++) { const fl = 1643 + k * 30 - 20; const d = dropAt(f, fl, fl + 14, fl + 17, 6); if (d) drops.push(d); } }
  else if (id === 11 || id === 12 || id === 13) beam = 0;
  return { cut: cutAt(id, f), beam, laser, drops, flow: f * 0.06 };
};
/** the beach: lattice grows in on "cleaned", the odd atom pulses on "one atom" */
export const beachAt = (f: number) => ({ lattice: smooth((f - 872) / 16), odd: f >= 900 ? smooth((f - 900) / 6) : 0 });
/** the crystal grows while the shot runs; the saw slices from "sliced" */
export const pullerAt = (f: number) => ({ grow: clamp01((f - 940) / 110), slice: clamp01((f - 1036) / 50) });
/** the stencil: light on "printed", the pattern, then a layer on each "layer" beat */
export const stencilAt = (f: number) => ({ light: smooth((f - 1118) / 6), print: smooth((f - 1124) / 12), layers: clamp01((f - 1140) / 30) * 6 });
/** the chip city switch wave (0 = idle flicker) */
export const flipAt = (id: number, f: number) => (id === 20 ? (f < 2145 ? -1 : Math.max(0.001, clamp01((f - 2145) / 34))) : 0);

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

const PX = PLASMA[0], PY = PLASMA[1];
const CX = CITY.x;
const SQZ = CITY.z - (CITY.nz * CITY.pz) / 2 + ((SQUARE.j0 + SQUARE.j1) / 2) * CITY.pz;
/** the people the cameras frame (cast.ts stands them here) */
export const PHONE_GUY: V3 = [STREET.x, 0, 2.0];
export const SCI: V3[] = [[LAB.x - 0.75, 0, -2.75], [LAB.x + 0.7, 0, -2.8]];
export const READER: V3 = [KITCHEN.x + 0.95, 0, 0.55];
export const NEWS: V3 = [KITCHEN.x - 2.0, 1.4, 1.2];
export const SPADE_KID: V3 = [BEACH.x - 0.4, 0, -0.2 + BEACH.z];
export const WAFER_GUY: V3 = [PULLER.x + 5.4, 0, PULLER.z + 1.6];
export const LOOKER: V3 = [MIRROR.x + BUMP[0] + 0.55, 0, MIRROR.z + BUMP[1] + 0.25];
export const FACTORY_DOOR: V3 = [STREET.x + 18, 0, STREET.z - 10.6];
const P0 = PHONE_GUY, L = LAB, K = KITCHEN, B = BEACH, P = PULLER, ST = STENCIL, M = MIRROR;

// 1 + 7 + 19: the phone in a hand on a street
const S1a = (f: number) => dolly([P0[0] + 0.5, 1.5, P0[2] + 1.55], [P0[0] + 0.16, 1.3, P0[2]], pushK(f, 0, 0.004, 0.01, 30), { fov: 38 });
const S7a = (f: number) => dolly([P0[0] + 0.7, 1.7, P0[2] + 2.6], [P0[0] + 0.18, 1.32, P0[2]], pushK(f, 692, 0.003), { fov: 38 });
const S7b = (f: number) => dolly([P0[0] + 0.45, 1.42, P0[2] + 1.3], [P0[0] + 0.3, 1.28, P0[2]], pushK(f, 715, 0.012), { fov: 34 });
// 2: the hook: in at the plasma, then back to show the light leaving for the machine
const S2a = (f: number) => dolly([PX + 2.0, PY + 0.55, 4.3], [PX + 0.15, PY + 0.4, 0], pushK(f, 40, 0.0022, 0.006, 30), { fov: 42 });
const S2b = (f: number) => dolly([-2.2, 2.3, 7.6], [-1.8, 1.7, 0], pushK(f, 120, 0.0018), { fov: 46 });
// 3-5: 1947
const S3a = (f: number) => dolly([L.x + 3.6, 2.0, 4.4], [L.x - 0.2, 1.25, -1.9], pushK(f, 186, 0.0018), { fov: 46 });
const S3b = (f: number) => dolly([L.x + 1.1, 1.55, 1.3], [L.x, 1.1, -1.5], pushK(f, 300, 0.003), { fov: 40 });
const S4a = (f: number) => { const a = 0.45 - 0.0014 * (f - 336); return dolly([L.x + Math.sin(a) * 0.95, 1.16, -1.45 + Math.cos(a) * 0.95], [L.x, 1.1, -1.45], pushK(f, 336, 0.0015, 0.004, 30), { fov: 28 }); };
const S5a = (f: number) => dolly([L.x + 0.4, 2.0, 5.6], [L.x, 1.4, -1.0], pushK(f, 449, 0.002), { fov: 48 });
// 6: the page, then the reader at breakfast with the radio behind
const S6a = (f: number) => dolly([NEWS[0], NEWS[1] + 0.05, NEWS[2] + 2.5], [NEWS[0], NEWS[1], NEWS[2]], pushK(f, 516, 0.002, 0.006, 25), { fov: 40 });
const S6b = (f: number) => dolly([K.x + 2.6, 1.6, 3.6], [K.x + 0.8, 1.15, -0.4], pushK(f, 560, 0.002), { fov: 46 });
const S6c = (f: number) => dolly([K.x + 2.4, 1.45, 0.2], [K.x + 1.75, 1.2, -2.7], pushK(f, 650, 0.003, 0.006, 20), { fov: 40 });
// 8: in the chip city square, then up over the city
const S8a = (f: number) => dolly([CX + 3, 4.6, SQZ + 13], [CX - 1, 2.6, SQZ - 4], pushK(f, 763, 0.002, 0.005, 30), { fov: 46 });
const S8b = (f: number) => dolly([CX + 10, 26, SQZ + 46], [CX, 1, SQZ - 6], pushK(f, 783, 0.0016), { fov: 44 });
// 9: the beach and the lattice
const S9a = (f: number) => dolly([B.x + 2.2, 1.35, B.z - 5.4], [B.x - 0.7, 0.8, B.z + 1.5], pushK(f, 839, 0.002), { fov: 44 });
const S9b = (f: number) => dolly([B.x + 1.4, 2.9, B.z - 8.4], [B.x + 0.1, 3.0, B.z - 2.0], pushK(f, 880, 0.002, 0.006, 25), { fov: 44 });
// 10: the crystal, then the saw and the wafers
const S10a = (f: number) => dolly([P.x - 1.2, 3.0, P.z + 4.4], [P.x - 3.0, 1.4, P.z], pushK(f, 968, 0.0022), { fov: 46 });
const S10b = (f: number) => dolly([P.x + 6.6, 1.75, P.z + 5.6], [P.x + 4.6, 1.3, P.z + 0.8], pushK(f, 1034, 0.0025), { fov: 44 });
// 11: light through the stencil
const S11a = (f: number) => dolly([ST.x + 2.7, 2.1, ST.z + 4.0], [ST.x, 1.55, ST.z], pushK(f, 1101, 0.0022, 0.005, 25), { fov: 44 });
const S11b = (f: number) => dolly([ST.x + 1.1, 3.4, ST.z + 1.7], [ST.x, 2.62, ST.z], pushK(f, 1166, 0.003), { fov: 40 });
// 12-15: the bay and the scanner
const S12a = (f: number) => dolly([10.2, 2.2, 7.6], [4.0, 1.35, -4.5], pushK(f, 1216, 0.0016, 0.004, 30), { fov: 50 });
const S13a = (f: number) => dolly([-0.3, 1.55, 6.9], [-0.9, 1.35, 4.4], pushK(f, 1338, 0.0025, 0.006, 25), { fov: 40 });
const S13b = (f: number) => dolly([4.0, 0.7, 8.4], [-1.4, 2.1, 0], pushK(f, 1426, 0.0016, 0.004, 26), { fov: 62 });
const S14a = (f: number) => dolly([PX + 0.95, PY + 0.2, 2.1], [PX + 0.05, PY + 0.12, 0], pushK(f, 1474, 0.0022, 0.006, 30), { fov: 36 });
const S14b = (f: number) => dolly([PX + 2.6, PY + 0.6, 4.6], [PX + 1.0, PY + 0.4, 0], pushK(f, 1585, 0.002), { fov: 44 });
const S15a = (f: number) => dolly([-1.4, 1.95, 7.9], [-1.4, 1.85, 0], pushK(f, 1643, 0.0018), { fov: 50 });
// 16: the Germany-sized mirror from high up, then the person and the bump
const S16a = (f: number) => dolly([M.x + 20, 230, M.z + 170], [M.x, 0, M.z + 6], pushK(f, 1752, 0.0015), { fov: 50 });
const S16b = (f: number) => dolly([LOOKER[0] + 2.0, 1.25, LOOKER[2] + 2.6], [LOOKER[0] - 0.3, 0.6, LOOKER[2] - 0.1], pushK(f, 1822, 0.003, 0.006, 25), { fov: 40 });
// 17: flying with the jets (planes move: sets2.ts Jets, v = 9 m/s from the shot start)
const jet = (f: number, i = 0): V3 => [SKY.x + 9 * ((f - 1878) / FPS) - 34 * i, SKY.y + [0, 5, -4][i], SKY.z + [0, -30, 28][i]];
const S17a = (f: number) => { const p = jet(f); return dolly([p[0] + 12, p[1] + 3.5, p[2] + 23], [p[0] - 1, p[1], p[2]], 1, { fov: 44 }); };
const S17b = (f: number) => { const p = jet(f, 1); return dolly([p[0] + 44, p[1] + 14, p[2] + 78], [p[0] - 4, p[1], p[2]], pushK(f, 1966, 0.001), { fov: 42 }); };
// 18: the one factory and its queue
const S18a = (f: number) => dolly([FACTORY_DOOR[0] - 13, 6.5, FACTORY_DOOR[2] + 24], [FACTORY_DOOR[0] - 5, 1.6, FACTORY_DOOR[2] + 7], pushK(f, 2011, 0.002), { fov: 46 });
// 19: the tap, then the city flipping
const S19a = (f: number) => dolly([P0[0] + 0.5, 1.5, P0[2] + 1.55], [P0[0] + 0.16, 1.3, P0[2]], pushK(f, 2065, 0.003, 0.008, 25), { fov: 38 });
const S19b = (f: number) => dolly([CX + 34, 46, 52], [CX, 0, 0], pushK(f, 2118, 0.0012), { fov: 44 });

const CAMS: Record<number, Key[]> = {
  1: [{ f: 0, s: S1a }],
  2: [{ f: 40, s: S2a }, { f: 118, dur: 40, s: S2b }],
  3: [{ f: 186, s: S3a }, { f: 296, dur: 30, s: S3b }],
  4: [{ f: 336, s: S4a }],
  5: [{ f: 449, s: S5a }],
  6: [{ f: 516, s: S6a }, { f: 558, cut: true, s: S6b }, { f: 646, cut: true, s: S6c }],
  7: [{ f: 692, s: S7a }, { f: 712, dur: 40, s: S7b }],
  8: [{ f: 763, s: S8a }, { f: 781, cut: true, s: S8b }],
  9: [{ f: 839, s: S9a }, { f: 870, dur: 30, s: S9b }],
  10: [{ f: 968, s: S10a }, { f: 1034, cut: true, s: S10b }],
  11: [{ f: 1101, s: S11a }, { f: 1164, dur: 30, s: S11b }],
  12: [{ f: 1216, s: S12a }],
  13: [{ f: 1338, s: S13a }, { f: 1424, cut: true, s: S13b }],
  14: [{ f: 1474, s: S14a }, { f: 1583, cut: true, s: S14b }],
  15: [{ f: 1643, s: S15a }],
  16: [{ f: 1752, s: S16a }, { f: 1822, cut: true, s: S16b }],
  17: [{ f: 1878, s: S17a }, { f: 1964, cut: true, s: S17b }],
  18: [{ f: 2011, s: S18a }],
  19: [{ f: 2065, s: S19a }],
  20: [{ f: 2116, s: S19b }],
};
export const camAt = (id: number, f: number): Cam => run(CAMS[id], f);

// ---------------- lens ----------------
export type Dof = { f: number; dur?: number; cInf: number; focus?: (f: number) => V3 };
const DOF: Dof[] = [
  // user feedback (Nov 4, twice): no soft subjects. Everything is sharp; only the two macro close-ups keep a light
  // background blur, focused on their subject.
  { f: 0, cInf: 0 },
  { f: 336, cInf: 5, focus: () => [L.x, 1.12, -1.45] },          // the transistor macro
  { f: 449, cInf: 0 },
  { f: 1474, cInf: 5, focus: () => [PX, PY + 0.1, 0] },          // the drop close-up
  { f: 1583, cInf: 0 },
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
export { EUV };
