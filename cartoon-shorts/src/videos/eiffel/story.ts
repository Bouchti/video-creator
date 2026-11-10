// Timeline of "The Bribe That Sold the Eiffel Tower": shots timed to the voice words (shorts/eiffel/voice/words.json),
// the camera grammar of the skill (smootherstep glides 18-40 f, big reframes are cuts, every hold creeps in) and the
// state of the props (limousine, train, letter stamp, knocks, envelopes) as pure functions of the frame.
import { TOWER, CAFE, HOTEL, HOME, OFFICE, COUNTRY, ROAD_Z, EAST_TABLES } from "./places";
import type { LightName } from "./lights";

export const FPS = 30;
export const TOTAL = 2125;
export const D0 = 0;
export type V3 = [number, number, number];

export const clamp01 = (x: number) => Math.max(0, Math.min(1, x));
export const smooth = (x: number) => { const u = clamp01(x); return u * u * (3 - 2 * u); };
export const easeOut = (u: number) => 1 - (1 - clamp01(u)) ** 4;
export const easeIn = (u: number) => clamp01(u) ** 2;

// ---------------- shots ----------------
export type Light = LightName;
export type Crowd = "none" | "hook" | "cafe" | "painter" | "letter" | "salon" | "minister" | "shock" | "shh" | "limo" | "knock" | "dream"
  | "wife" | "leave" | "palm" | "clerks" | "deal" | "train" | "vienna" | "ashamed" | "police" | "return";
export type ShotDef = { id: number; a: number; b: number; light: Light; crowd: Crowd; sunAz?: number; sunEl?: number; fog?: [number, number] };
const FAR: [number, number] = [160, 1500];
export const SHOTS: ShotDef[] = [
  { id: 1, a: 0, b: 105, light: "day", crowd: "hook", fog: FAR, sunAz: 120, sunEl: 40 },     // he sold the Eiffel Tower ... a bribe on top
  { id: 2, a: 105, b: 202, light: "day", crowd: "cafe", fog: FAR },                           // Paris, 1925, the papers say it's rusting
  { id: 3, a: 202, b: 316, light: "day", crowd: "painter", fog: FAR },                        // a fortune to repaint; meant to stand 20 years
  { id: 4, a: 316, b: 389, light: "lab", crowd: "letter" },                                   // a forger prints fake letterhead
  { id: 5, a: 389, b: 475, light: "lab", crowd: "salon" },                                    // five scrap dealers, the fanciest hotel
  { id: 6, a: 475, b: 556, light: "lab", crowd: "minister" },                                 // the Ministry of Posts and Telegraphs
  { id: 7, a: 556, b: 611, light: "lab", crowd: "shock" },                                    // "The post office is selling the Eiffel Tower?"
  { id: 8, a: 611, b: 734, light: "lab", crowd: "shh" },                                      // "Shh. Riots. Not a word."
  { id: 9, a: 734, b: 786, light: "day", crowd: "limo", fog: FAR },                           // a tour in a limousine
  { id: 10, a: 786, b: 843, light: "day", crowd: "knock", fog: FAR },                         // knocking on the girders like a melon
  { id: 11, a: 843, b: 1049, light: "day", crowd: "dream", fog: FAR },                        // André Poisson wants it more than anyone
  { id: 12, a: 1049, b: 1205, light: "lab", crowd: "wife" },                                  // his wife isn't buying it
  { id: 13, a: 1205, b: 1325, light: "lab", crowd: "leave" },                                 // ready to walk away; the con man asks for a bribe
  { id: 14, a: 1325, b: 1398, light: "lab", crowd: "palm" },                                  // wait, a bribe?
  { id: 15, a: 1398, b: 1548, light: "lab", crowd: "clerks" },                                // everyone knew officials took bribes
  { id: 16, a: 1548, b: 1744, light: "lab", crowd: "deal" },                                  // the dealer relaxes; pays the bribe and the price
  { id: 17, a: 1744, b: 1841, light: "day", crowd: "train", fog: FAR, sunAz: 110, sunEl: 35 },// on a train to Austria with a suitcase of cash
  { id: 18, a: 1841, b: 1926, light: "day", crowd: "vienna", fog: FAR, sunAz: 140, sunEl: 30 }, // every morning he checks the papers
  { id: 19, a: 1926, b: 1966, light: "lab", crowd: "ashamed" },                               // the dealer is so embarrassed
  { id: 20, a: 1966, b: 2006, light: "day", crowd: "police", fog: FAR },                      // he never tells the police
  { id: 21, a: 2006, b: TOTAL, light: "golden", crowd: "return", fog: FAR },                  // a month later ... to sell it again
];
export const XFADE: Record<number, number> = { 4: 8, 9: 8, 12: 8, 13: 8, 15: 8, 16: 8, 17: 8, 18: 8, 19: 8, 21: 8 };
export const FLASH_AT = 101;

export const shotAt = (f: number) => SHOTS.find((s) => f >= s.a && f < s.b) ?? SHOTS[SHOTS.length - 1];
export const layersAt = (f: number): { id: number; alpha: number }[] => {
  for (const s of SHOTS) {
    const x = XFADE[s.id];
    if (x && f >= s.a - x / 2 && f < s.a + x / 2) return [{ id: s.id - 1, alpha: 1 }, { id: s.id, alpha: (f - (s.a - x / 2) + 1) / (x + 1) }];
  }
  return [{ id: shotAt(f).id, alpha: 1 }];
};

// ---------------- where people stand ----------------
const T = TOWER, H = HOTEL, HM = HOME, O = OFFICE;
/** the hook: the con man presents the tower, the buyer beside him */
export const HOOK_CON: V3 = [-0.42, 0, 128];
export const HOOK_BUY: V3 = [0.48, 0, 127.8];
/** the café terrace table (Paris shot looks -z to the tower, the Austrian morning looks +z to the dome) */
export const CAFE_SEAT: V3 = [-CAFE.half + 2.6 - 0.56, 0, CAFE.terraceZ - 2.5 - 0.28];
export const VIENNA_SEAT: V3 = [EAST_TABLES[1][0] + 0.51, 0, EAST_TABLES[1][1] + 0.35];
/** the painter on his plank on the front-right leg, the leg corner the con man knocks on */
export const PAINTER_AT: V3 = [44, 13.6, -43.3];
export const KNOCK_CON: V3 = [40.55, 0.6, -34.5];
export const KNOCK_BEAM: V3 = [41.0, 1.85, -34.45];
export const DEALERS_TOUR: V3[] = [[39.85, 0.6, -35.2], [40.2, 0.6, -35.5], [41.6, 0.6, -35.45], [41.95, 0.6, -35.1]];
export const DREAM_POI: V3 = [33.5, 0, -21.5];
/** the salon: the long table along x at z = H.z - 1.2; dealers behind it and at the left end, the con man at the right */
export const TABLE_Z = H.z - 1.2;
export const SEATS: V3[] = [[H.x - 2.0, 0, H.z - 2.25], [H.x - 1.2, 0, H.z - 0.15], [H.x - 0.4, 0, H.z - 2.25], [H.x + 0.4, 0, H.z - 0.15], [H.x + 1.2, 0, H.z - 2.25]];
export const POI_SEAT = 2;
export const CON_HEAD: V3 = [H.x + 3.35, 0, H.z - 1.2];
/** in front of the table: the con man, and the dealer walking away then turning back */
export const CON_FRONT: V3 = [H.x + 0.95, 0, H.z - 0.05];
export const poiLeave = (f: number): V3 => { const k = smooth((f - 1210) / 50); return [H.x + 1.55 + 0.85 * k, 0, H.z + 0.05 + 0.3 * k]; };
export const POI_DEAL: V3 = [H.x + 2.1, 0, H.z + 0.15];
/** Poisson's parlour */
export const WIFE_AT: V3 = [HM.x - 0.7, 0, HM.z - 1.4];
export const POI_HOME: V3 = [HM.x + 0.85, 0, HM.z - 1.0];
/** the ministry hall: a clerk behind each desk, a citizen in front of each */
export const DESK_Z = [1.6, -0.6, -2.8];
/** the street where the dealer hurries past a policeman (the café street, Paris side) */
export const COP_AT: V3 = [-3.8, 0, 349.5];
export const poiHurry = (_f: number): V3 => [-1.7, 0, 356.2];
export const CLERK = (i: number): V3 => [O.x - 1.55, 0, O.z + DESK_Z[i]];
export const CITIZEN = (i: number): V3 => [O.x - 0.2, 0, O.z + DESK_Z[i] + 0.25];
/** the return: walking up the avenue toward the camera, the tower behind */
export const returnAt = (f: number): V3 => [0.4, 0, 134 - (1.1 * Math.min(Math.max(0, f - 2006), 66)) / FPS];

// ---------------- moving things ----------------
/** limousine: drives down the avenue toward the tower (heading -z) at 11 m/s */
export const limoAt = (f: number) => { const s = 9 * ((f - 734) / FPS); return { x: -14 + s, z: ROAD_Z, yaw: Math.PI / 2, s }; };
/** the passengers: [world x, z, y, which] (0 = the con man in front, 1-2 dealers behind) */
export const limoSeats = (f: number): [number, number, number, number][] => { const c = limoAt(f); return [[c.x + 0.15, c.z + 0.33, 0.72, 0], [c.x - 1.3, c.z + 0.33, 0.72, 1], [c.x - 1.3, c.z - 0.33, 0.72, 2]]; };
/** the train nose x (Country) */
export const trainAt = (f: number) => COUNTRY.x - 140 + 14 * ((f - 1744) / FPS);
/** the stamp on the letter: down at 343 ("fake"), seal from then on */
export const stampAt = (f: number) => ({ y: f < 330 ? 1 : f < 343 ? 1 - smooth((f - 330) / 13) : f < 351 ? 0 : smooth((f - 351) / 12), seal: f >= 343 });
/** knocks on "knocking" (786) and "melon" (825): fist 0 raised .. 1 struck */
export const knockAt = (f: number) => {
  for (const k of [790, 806, 826]) if (f >= k - 6 && f < k + 6) return f < k ? smooth((f - (k - 6)) / 6) : 1 - smooth((f - k) / 6);
  return 0;
};
export const KNOCKS = [790, 806, 826];

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
/** move pos and look together along the view direction by m metres per second since f0 (+ a punch of p metres) */
const creep = (pos: V3, look: V3, f: number, f0: number, mps: number, rest: Partial<Cam> = {}, punch = 0, pf = 0): Shot => {
  const d = [look[0] - pos[0], look[1] - pos[1], look[2] - pos[2]], n = Math.hypot(d[0], d[1], d[2]) || 1;
  const s = mps * Math.max(0, f - f0) / FPS + (punch ? punch * smooth((f - pf) / 10) : 0);
  return { pos: [pos[0] + (d[0] / n) * s, pos[1] + (d[1] / n) * s, pos[2] + (d[2] / n) * s], look: [look[0] + (d[0] / n) * s, look[1] + (d[1] / n) * s, look[2] + (d[2] / n) * s], ...rest };
};

// 1: low under the two men, the whole tower above them; a push on "bribe"
const S1a = (f: number) => creep([0.1, 0.95, 132.2], [0.05, 27.6, 32.2], f, 0, 0.3, { fov: 70, roll: rad(-2) });
const S1b = (f: number) => dolly([0.05, 1.35, 131.5], [0.03, 1.28, 127.8], pushK(f, 74, 0.003, 0.01, 22), { fov: 44 });
// 2: the café terrace, the tower at the end of the street
const S2a = (f: number) => dolly([CAFE_SEAT[0] + 1.0, 1.45, CAFE_SEAT[2] + 5.4], [CAFE_SEAT[0] + 0.2, 1.7, CAFE_SEAT[2] - 6], pushK(f, 105, 0.0022), { fov: 46 });
const S2b = (f: number) => dolly([CAFE_SEAT[0] + 0.25, 1.3, CAFE_SEAT[2] + 1.6], [CAFE_SEAT[0], 1.12, CAFE_SEAT[2]], pushK(f, 162, 0.004, 0.008, 20), { fov: 40 });
// 3: up the rusty leg to the painter, then the whole tower
const S3a = (f: number) => { const k = smooth((f - 202) / 60); return { pos: [44.1, 13.6 + 0.6 * k, -40.6] as V3, look: [44, 14.2 + 0.6 * k, -43.3] as V3, fov: 48 }; };
const S3b = (f: number) => dolly([95, 18, 210], [0, 120, -100], pushK(f, 240, 0.0012), { fov: 44 });
// 4: the letter on the salon table, the stamp coming down
const S4a = (f: number) => dolly([H.x + 0.42, 1.55, TABLE_Z + 0.95], [H.x + 0.3, 0.8, TABLE_Z + 0.18], pushK(f, 316, 0.003), { fov: 38 });
// 5: the salon, five dealers round the table
const S5a = (f: number) => dolly([H.x - 5.3, 2.45, TABLE_Z], [H.x + 1.2, 0.95, TABLE_Z], pushK(f, 389, 0.0018, 0.004, 25), { fov: 60 });
// 6-8: the con man at the head of the table, a dealer's face, the "shh"
const S6a = (f: number) => dolly([CON_HEAD[0] - 0.1, 1.55, CON_HEAD[2] + 2.5], [CON_HEAD[0] - 0.05, 1.42, CON_HEAD[2]], pushK(f, 475, 0.0025, 0.006, 25), { fov: 40 });
const S7a = (f: number) => dolly([SEATS[1][0] + 0.05, 1.2, SEATS[1][2] + 1.9], [SEATS[1][0], 1.12, SEATS[1][2]], pushK(f, 556, 0.003, 0.012, 20), { fov: 36 });
const S8a = (f: number) => dolly([CON_HEAD[0] - 0.05, 1.45, CON_HEAD[2] + 1.6], [CON_HEAD[0] - 0.02, 1.48, CON_HEAD[2]], pushK(f, 611, 0.003, 0.008, 25), { fov: 38, roll: rad(4) });
const S8b = (f: number) => dolly([CON_HEAD[0] - 0.25, 1.4, CON_HEAD[2] + 2.3], [CON_HEAD[0] - 0.35, 1.62, CON_HEAD[2]], pushK(f, 676, 0.003, 0.008, 25), { fov: 44, roll: rad(-4) });
// 9: the limousine down the avenue toward the tower
const S9a = (f: number) => { const c = limoAt(f); return { pos: [c.x - 0.3, 1.55, c.z + 7.2] as V3, look: [c.x - 0.5, 4.4, c.z - 40] as V3, fov: 46 }; };
// 10: the knock on the leg
const S10a = (f: number) => dolly([KNOCK_CON[0] + 0.25, 1.75, KNOCK_CON[2] + 3.4], [KNOCK_CON[0] + 0.25, 1.75, KNOCK_CON[2]], pushK(f, 786, 0.0025, 0.007, 25), { fov: 44 });
// 11: the dealer gazing up at the tower; the outsider; his dream
const S11a = (f: number) => creep([DREAM_POI[0] + 1.0, 1.0, DREAM_POI[2] + 2.9], [16, 22, -88], f, 843, 0.2, { fov: 60 });
const S11b = (f: number) => dolly([31.5, 1.6, -16.5], [37, 1.2, -27], pushK(f, 934, 0.002), { fov: 46 });
const S11c = (f: number) => dolly([DREAM_POI[0] + 0.1, 1.4, DREAM_POI[2] + 2.0], [DREAM_POI[0], 1.45, DREAM_POI[2]], pushK(f, 965, 0.0025, 0.006, 25), { fov: 40 });
// 12, 19: the parlour
const S12a = (f: number) => dolly([HM.x + 0.1, 1.5, HM.z + 3.6], [HM.x + 0.08, 1.25, HM.z - 1.2], pushK(f, 1049, 0.0016), { fov: 46 });
const S12b = (f: number) => dolly([WIFE_AT[0] + 0.05, 1.45, WIFE_AT[2] + 2.2], [WIFE_AT[0], 1.35, WIFE_AT[2]], pushK(f, 1097, 0.003, 0.008, 22), { fov: 40 });
const S20p = (f: number) => dolly([-2.1, 1.5, 359.2], [-2.4, 1.3, 353.5], pushK(f, 1966, 0.002), { fov: 46 });
const S19a = (f: number) => dolly([POI_HOME[0] + 0.05, 1.4, POI_HOME[2] + 2.4], [POI_HOME[0] - 0.05, 1.3, POI_HOME[2]], pushK(f, 1926, 0.0025, 0.006, 25), { fov: 42 });
// 13-14, 16: in front of the table
const S13a = (f: number) => dolly([H.x + 1.7, 1.5, H.z + 4.7], [H.x + 1.7, 1.2, H.z - 0.1], pushK(f, 1205, 0.0018), { fov: 50 });
const S14a = (f: number) => { const p = poiLeave(1300); return dolly([p[0] - 0.1, 1.3, p[2] + 2.0], [p[0] - 0.05, 1.32, p[2]], pushK(f, 1325, 0.003, 0.012, 22), { fov: 40, roll: rad(-4) }); };
const S16a = (f: number) => dolly([H.x + 1.5, 0.75, H.z + 3.6], [H.x + 1.5, 1.45, H.z], pushK(f, 1548, 0.002), { fov: 46 });
const S16b = (f: number) => dolly([POI_DEAL[0] - 0.2, 1.35, POI_DEAL[2] + 2.0], [POI_DEAL[0] - 0.2, 1.2, POI_DEAL[2]], pushK(f, 1684, 0.003, 0.006, 22), { fov: 40 });
// 15: the ministry hall
const S15a = (f: number) => dolly([O.x - 0.6, 1.6, O.z + 5.4], [O.x - 0.95, 1.1, O.z - 0.6], pushK(f, 1398, 0.0018, 0.004, 25), { fov: 46 });
const S15b = (f: number) => dolly([O.x - 0.86, 1.35, O.z + 1.6 + 4.2], [O.x - 0.88, 1.1, O.z + 1.6], pushK(f, 1487, 0.003, 0.008, 22), { fov: 44 });
// 17: alongside the train, the Alps behind
const S17a = (f: number) => { const r = rearAt(f); return { pos: [r[0] + 1.6, 2.55, r[2] + 3.9] as V3, look: [r[0] + 0.1, 2.25, r[2]] as V3, fov: 44 }; };
// 18: the Austrian morning, looking up the street to the dome
const S18a = (f: number) => dolly([VIENNA_SEAT[0] - 0.4, 1.45, VIENNA_SEAT[2] - 4.0], [VIENNA_SEAT[0] - 0.1, 1.4, VIENNA_SEAT[2] + 1.5], pushK(f, 1841, 0.0025, 0.006, 25), { fov: 44 });
// 20: the return, low in front of him with the tower behind; up to the tower on "again"
const S20a = (f: number) => { const p = returnAt(f); return { pos: [p[0] + 0.55, 1.0, p[2] + 3.9] as V3, look: [p[0] + 0.2, 4.2, p[2] - 14] as V3, fov: 54 }; };
const S20b = (f: number) => { const p = returnAt(2076); return creep([p[0] + 0.3, 0.85, p[2] + 5.2], [0.2, 38, T.z + 30], f, 2074, 0.3, { fov: 62 }); };
export const rearAt = (f: number): V3 => { const x = trainAt(f); return [x - 6.4 - 13.2 - 12.4 - 0.9, 1.34, COUNTRY.z]; };

const CAMS: Record<number, Key[]> = {
  1: [{ f: 0, s: S1a }, { f: 72, cut: true, s: S1b }],
  2: [{ f: 105, s: S2a }, { f: 160, dur: 30, s: S2b }],
  3: [{ f: 202, s: S3a }, { f: 240, cut: true, s: S3b }],
  4: [{ f: 316, s: S4a }],
  5: [{ f: 389, s: S5a }],
  6: [{ f: 475, s: S6a }],
  7: [{ f: 556, s: S7a }],
  8: [{ f: 611, s: S8a }, { f: 676, cut: true, s: S8b }],
  9: [{ f: 734, s: S9a }],
  10: [{ f: 786, s: S10a }],
  11: [{ f: 843, s: S11a }, { f: 932, cut: true, s: S11b }, { f: 963, cut: true, s: S11c }],
  12: [{ f: 1049, s: S12a }, { f: 1095, cut: true, s: S12b }],
  13: [{ f: 1205, s: S13a }],
  14: [{ f: 1325, s: S14a }],
  15: [{ f: 1398, s: S15a }, { f: 1485, cut: true, s: S15b }],
  16: [{ f: 1548, s: S16a }, { f: 1682, cut: true, s: S16b }],
  17: [{ f: 1744, s: S17a }],
  18: [{ f: 1841, s: S18a }],
  19: [{ f: 1926, s: S19a }],
  20: [{ f: 1966, s: S20p }],
  21: [{ f: 2006, s: S20a }, { f: 2080, dur: 36, s: S20b }],
};
export const camAt = (id: number, f: number): Cam => run(CAMS[id], f);

// ---------------- lens ----------------
export type Dof = { f: number; dur?: number; cInf: number; focus?: (f: number) => V3 };
const DOF: Dof[] = [
  // user feedback (Nov 4): every subject sharp; only the letter macro keeps a light background blur
  { f: 0, cInf: 0 },
  { f: 316, cInf: 5, focus: () => [H.x + 0.3, 0.81, TABLE_Z + 0.18] },
  { f: 389, cInf: 0 },
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
