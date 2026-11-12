// Timeline of "The Jet That Landed on a Drag Race" (Air Canada 143, the Gimli Glider, 23 July 1983): shots timed to the
// voice words (shorts/gimli/voice/words.json), cameras in the reference grammar (wide lens, close, ALWAYS moving, whips
// between sets, punch-ins on the key words), and every vehicle's state as a pure function of the frame.
// HOOK RULE: frame 0 = low on the drag strip, a dragster launching past the lens (VROOM f0), two kids pedalling at us,
// the silent 767 sliding down behind them; "No fuel. No engines. Landing on a drag race." complete at 2.5 s.
// The film ends on the payoff (the mechanics' empty van) and loops.
export const FPS = 30;
export const TOTAL = 2100;
export type V3 = [number, number, number];
export const clamp01 = (x: number) => Math.max(0, Math.min(1, x));
export const smooth = (x: number) => { const u = clamp01(x); return u * u * (3 - 2 * u); };
export const easeOut = (u: number) => 1 - (1 - clamp01(u)) ** 3;
export const easeIn = (u: number) => clamp01(u) ** 2;
const lerp = (a: number, b: number, u: number) => a + (b - a) * u;
const rad = (d: number) => (d * Math.PI) / 180;

// ---------------- sets (mirrors blender/sets_gimli.py) ----------------
export const SX = 0, RX = 3000, CX6 = 6000, KX = 9000, GX = 9600, DX = 12000;
export const JET_CY = 4.4;

export type SetName = "strip" | "ramp" | "cockday" | "cruise" | "cockpit" | "glider" | "road";
export type ShotDef = { id: number; a: number; b: number; set: SetName };
export const SHOTS: ShotDef[] = [
  { id: 1, a: 0, b: 87, set: "strip" },       // No fuel. No engines. Landing on a drag race.
  { id: 2, a: 87, b: 200, set: "ramp" },      // Canada, 1983. A brand-new Air Canada jet...
  { id: 3, a: 200, b: 264, set: "cockday" },  // ...with a broken fuel gauge.
  { id: 4, a: 264, b: 354, set: "ramp" },     // So the ground crew measures the tanks with a dipstick.
  { id: 5, a: 354, b: 481, set: "ramp" },     // Canada just went metric. The new jet counts fuel in kilos.
  { id: 6, a: 481, b: 542, set: "ramp" },     // The crew's math used pounds.
  { id: 7, a: 542, b: 626, set: "ramp" },     // So they load less than half the fuel they need.
  { id: 8, a: 626, b: 716, set: "ramp" },     // In Ottawa, they check again. Same mistake.
  { id: 9, a: 716, b: 762, set: "cruise" },   // Forty-one thousand feet.
  { id: 10, a: 762, b: 871, set: "cockpit" }, // Bong. A warning nobody has ever heard.
  { id: 11, a: 871, b: 925, set: "cruise" },  // Left engine: dead.
  { id: 12, a: 925, b: 972, set: "cruise" },  // Right engine: dead.
  { id: 13, a: 972, b: 1032, set: "cockpit" },// The fancy screens: black.
  { id: 14, a: 1032, b: 1170, set: "glider" },// Lucky for them, Captain Bob Pearson flies gliders. For fun.
  { id: 15, a: 1170, b: 1282, set: "cockpit" },// His co-pilot knows an old air force base nearby. Gimli.
  { id: 16, a: 1282, b: 1414, set: "strip" }, // Nobody told them it's now a drag strip. And today is Family Day.
  { id: 17, a: 1414, b: 1442, set: "strip" }, // Race cars.
  { id: 18, a: 1442, b: 1475, set: "strip" }, // Kids on bikes.
  { id: 19, a: 1475, b: 1560, set: "strip" }, // And a silent jet, coming right at them.
  { id: 20, a: 1560, b: 1647, set: "cockpit" },// Too high, so Bob uses a glider trick.
  { id: 21, a: 1647, b: 1703, set: "strip" }, // He flies the jet sideways.
  { id: 22, a: 1703, b: 1752, set: "strip" }, // The nose wheel collapses.
  { id: 23, a: 1752, b: 1844, set: "strip" }, // The jet scrapes to a stop, just short of the crowd.
  { id: 24, a: 1844, b: 1896, set: "strip" }, // Racers put out the fire.
  { id: 25, a: 1896, b: 1939, set: "strip" }, // Everyone survives.
  { id: 26, a: 1939, b: 2010, set: "road" },  // And the mechanics sent to fix the jet?
  { id: 27, a: 2010, b: TOTAL, set: "road" }, // Their van ran out of fuel on the way.
];
export const shotAt = (f: number) => SHOTS.find((s) => f >= s.a && f < s.b) ?? SHOTS[SHOTS.length - 1];

// ---------------- key beats (frames, from the voice) ----------------
export const B = { landing: 49, gauge: 231, dipstick: 328, kilos: 453, pounds: 514, half: 577, same: 684, bong: 762, left: 903, right: 954,
  black: 1011, fun: 1147, gimli: 1264, family: 1387, race: 1414, kids: 1442, silent: 1487, sideways: 1672, collapse: 1720, stop: 1826,
  fire: 1874, survive: 1907, van: 2014, empty: 2045 };

// ---------------- where people stand ----------------
export const KID_X: [number, number] = [-7.85, -6.75];
export const kidZ = (f: number) => (f < 300 ? 176 + 5.2 * (f / FPS) : 268 + 4.6 * ((f - 1442) / FPS));     // hook / shot 18
export const DAD: V3 = [-20.0, 0, 360.2];
export const BBQ: V3 = [-18.7, 0, 359.0];
export const CREW: V3 = [RX - 10.6, 0, -1.2];
export const NOZZLE_CREW: V3 = [RX - 12.2, 0, 1.6];
export const BOB: V3 = [CX6 + 0.55, 0.22, -0.28];      // captain = left seat (facing +z, left is +x)
export const MAU: V3 = [CX6 - 0.55, 0.22, -0.28];
export const JET_STOP_Z = 240;
export const RACERS: V3[] = [[-1.1, 0, 269.8], [1.0, 0, 270.4], [-2.2, 0, 267.8]];
export const SPECT: V3[] = [[-1.6, 0, 283], [1.05, 0, 283.5], [-0.95, 0, 286.2], [1.6, 0, 280.5], [-2.3, 0, 280.5]];
export const MECHS: V3[] = [[DX + 3.4, 0, 0], [DX + 3.9, 0, 1.6]];
export const VAN_STOP_Z = 1.0;

// ---------------- vehicles ----------------
export type VState = { x: number; z: number; yaw: number; d: number; y?: number; roll?: number; pitch?: number } | null;
const FACE_PZ = Math.PI;                                   // yaw that faces +z (yaw 0 faces -z)
/** the 767 over the strip: approach, sideslip, flare, touchdown, nose collapse, scrape, stop */
export const jetStrip = (f: number): { x: number; y: number; z: number; yaw: number; pitch: number; roll: number; nose: boolean } | null => {
  if (f < 87) {   // hook: low and close over the runway, sliding down out of the sunset (silent)
    const u = f / 87; return { x: lerp(-3, -5, u), y: lerp(27, 19, u), z: lerp(96, 150, u), yaw: FACE_PZ + rad(lerp(7, 5, u)), pitch: 0.03, roll: rad(lerp(-6, -4, u)), nose: true };
  }
  if (f >= 1442 && f < 1475) { const u = (f - 1442) / 33; return { x: 6, y: lerp(150, 140, u), z: lerp(-900, -870, u), yaw: FACE_PZ, pitch: -0.04, roll: 0, nose: true }; }
  if (f >= 1475 && f < 1560) { const u = (f - 1475) / 85; return { x: lerp(-18, -16, u), y: lerp(48, 32, u), z: lerp(-160, -60, u), yaw: FACE_PZ + rad(6), pitch: -0.05, roll: rad(-4), nose: true }; }
  if (f >= 1647 && f < 1703) { const u = (f - 1647) / 56; return { x: lerp(4, 0.6, u), y: lerp(16, 1.2, easeOut(u)), z: lerp(-14, 117, u), yaw: FACE_PZ + rad(lerp(28, 10, smooth(u))), pitch: lerp(-0.07, -0.05, u), roll: rad(lerp(-13, -3, u)), nose: true }; }
  if (f >= 1703 && f < 1844 + 200) {
    // touchdown on the mains at 1703 (60 m/s), nose gear collapses at B.collapse, decelerating to a stop at B.stop
    const T = (B.stop - 1703) / FPS, t = Math.min((f - 1703) / FPS, T), v0 = 2 * (JET_STOP_Z - 117) / T, z = 117 + v0 * t - 0.5 * (v0 / T) * t * t;
    const y = f < 1709 ? lerp(1.2, 0, (f - 1703) / 6) : 0;
    const k = smooth((f - B.collapse) / 8), pitch = lerp(-0.05, 0.098, k) + (f >= B.collapse + 8 && f < B.collapse + 16 ? 0.012 * Math.sin((f - B.collapse - 8) * 1.4) : 0);
    const sway = f < B.stop ? rad(2.5) * Math.sin((f - 1703) * 0.35) * (1 - t / T) : 0;
    return { x: lerp(0.6, 0.0, clamp01((f - 1703) / 40)), y, z, yaw: FACE_PZ + rad(lerp(8, 1.5, clamp01((f - 1703) / 30))) + sway, pitch, roll: f < 1712 ? rad(-3) * (1 - (f - 1703) / 9) : 0, nose: f < B.collapse };
  }
  return null;
};
const jetState = (j: ReturnType<typeof jetStrip>, d = 0): VState => (j ? { x: j.x, z: j.z, y: j.y, yaw: j.yaw, d, pitch: j.pitch, roll: j.roll } : null);
/** cruise: the jet flies +z at the camera's pace; the sky set is local to the jet */
export const CRUISE_V = 30;          // set-space metres per second (the clouds are far below: the sense of speed comes from the camera)
export const cruiseZ = (f: number) => CRUISE_V * (f / FPS);
const fanD = (f: number, deadAt: number | null) => {
  // fan angle (radians * 0.45): fast spool until deadAt, then winding down to a slow windmill
  const fast = 0.85, slow = 0.08;
  if (deadAt === null || f < deadAt) return fast * f * 0.45;
  const t = f - deadAt, k = 14; return (fast * deadAt + slow * t + (fast - slow) * k * (1 - Math.exp(-t / k))) * 0.45;
};
export const vehiclesAt = (id: number, f: number) => {
  const set = shotAt(f).set;
  let jet: VState = null, fanL: VState = null, fanR: VState = null, ngear: VState = null, slide: VState = null;
  let drag: VState = null, drag2: VState = null, van: VState = null, glider: VState = null, scron: VState = null, warn: VState = null, mtl: VState = null, ott: VState = null;
  if (set === "ramp") {
    jet = { x: RX, z: 0, yaw: FACE_PZ, d: 0 }; fanL = { ...jet, d: f * 0.02 }; fanR = { ...jet, d: f * 0.02 }; ngear = jet;
    if (id === 8) ott = { x: RX, z: 45.4, y: 15.6, yaw: 0, d: 0 }; else mtl = { x: RX, z: 45.4, y: 15.6, yaw: 0, d: 0 };
  }
  if (set === "cruise") {
    jet = { x: KX, z: cruiseZ(f), y: 0, yaw: FACE_PZ, d: 0, pitch: -0.02, roll: id === 9 ? rad(4) * Math.sin(f / 20) : 0 };
    fanL = { ...jet, d: fanD(f, B.left - 30) }; fanR = { ...jet, d: fanD(f, B.right - 24) };
  }
  if (set === "strip") {
    const j = jetStrip(f);
    if (j) {
      jet = jetState(j); fanL = jetState(j, fanD(f, 0)); fanR = jetState(j, fanD(f, 0));
      if (j.nose) ngear = jet;
      if (f >= B.survive - 8) slide = { x: j.x + 2.55, z: j.z - 11.2, y: 6.05, yaw: -Math.PI / 2, d: 0 };
    }
    // the dragster: hook = launching past the lens toward the jet; shot 17 = burnout then launch at the start line
    if (id === 1) { const t = f / FPS; drag = { x: -5.1, z: 183 - 10 * t - 14 * t * t, yaw: 0, d: (6 * t + 9 * t * t) / 0.62 * 0.45 }; }
    if (id === 17) { const t = Math.max(0, (f - 1428) / FPS), burn = f < 1428 ? (f - 1414) * 0.9 : 0; drag = { x: -8.2, z: 330.5 - 8 * t * t * 2, yaw: 0, d: (burn + 16 * t * t) / 0.62 * 0.45, pitch: f >= 1428 && f < 1440 ? -0.04 * Math.sin(((f - 1428) / 12) * Math.PI) : 0 }; drag2 = { x: -3.6, z: 330.5 - 7 * t * t * 2, yaw: 0, d: (burn + 14 * t * t) / 0.62 * 0.45 }; }
    if (id === 16) { drag = { x: -8.2, z: 331, yaw: 0, d: 0 }; drag2 = { x: -3.6, z: 331, yaw: 0, d: 0 }; }
  }
  if (set === "cockday" || set === "cockpit") {
    const off = id === 13 && f >= B.black - 2;
    if (!off && (id === 3 || id === 10 || id === 13)) scron = { x: CX6, z: 1.225, y: 1.25, yaw: 0, d: 0 };
    if (id === 10 && f >= B.bong && Math.floor((f - B.bong) / 7) % 2 === 0) warn = { x: CX6, z: 1.32, y: 1.76, yaw: 0, d: 0 };
    if (id === 13 && f < B.black && Math.floor(f / 7) % 2 === 0) warn = { x: CX6, z: 1.32, y: 1.76, yaw: 0, d: 0 };
  }
  if (set === "glider") {
    const z = 26 * ((f - 1032) / FPS), roll = f < 1128 ? rad(8) * Math.sin((f - 1032) / 14) : f < 1160 ? -2 * Math.PI * smooth((f - 1128) / 30) : 0;
    glider = { x: GX, z, y: 0, yaw: FACE_PZ, d: 0, roll, pitch: 0.02 * Math.sin(f / 9) };
  }
  if (set === "road") {
    // shot 26: cruising at 22 m/s; shot 27: coughs (lurches) and rolls to a stop at VAN_STOP_Z
    let z: number, pitch = 0;
    const T = 1.4, z27 = VAN_STOP_Z - 22 * T / 2;   // shot 27 starts here at 22 m/s and brakes to VAN_STOP_Z
    if (f < 2010) z = z27 - 22 * ((2010 - f) / FPS);
    else { const t = Math.min((f - 2010) / FPS, T); z = z27 + 22 * t - 0.5 * (22 / T) * t * t; pitch = f < 2052 ? 0.025 * Math.sin((f - 2010) * 0.9) * (1 - clamp01((f - 2010) / 42)) : 0; }
    van = { x: DX + 1.8, z, yaw: FACE_PZ, d: (z - (VAN_STOP_Z - 80)) / 0.38 * 0.45, pitch };
  }
  return { jet, fanL, fanR, ngear, slide, drag, drag2, van, glider, scron, warn, mtl, ott };
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
const span = (f: number, a: number, b: number) => { const x = clamp01((f - a) / (b - a)); return 0.6 * x + 0.4 * glide(x); };
const kick = (f: number, at: number, amp: number) => (f >= at && f < at + 14 ? amp * Math.sin((f - at) * 1.3) * Math.exp(-(f - at) / 4.5) : 0);
const shake = (c: Shot, f: number, ats: number[], amp: number): Shot => { let k = 0; for (const at of ats) k += kick(f, at, amp); return { ...c, pos: [c.pos[0] + k, c.pos[1] + k * 0.6, c.pos[2]], look: [c.look[0] + k, c.look[1] + k * 0.6, c.look[2]] }; };
/** handheld life: a small continuous drift on every shot (reference cameras never sit still) */
const hand = (c: Shot, f: number, amp = 0.025): Shot => {
  const n = (s: number) => Math.sin(f * 0.13 + s) * 0.6 + Math.sin(f * 0.31 + s * 2.1) * 0.4;
  return { ...c, pos: [c.pos[0] + amp * n(1), c.pos[1] + amp * n(2), c.pos[2] + amp * n(3)], look: [c.look[0] + amp * 1.6 * n(4), c.look[1] + amp * 1.6 * n(5), c.look[2] + amp * 1.6 * n(6)] };
};
/** a punch-in on a word: the lens narrows hard for a few frames then settles a little wider */
const punch = (fov: number, f: number, at: number, k = 0.22) => (f < at ? fov : fov * (1 - k * (1 - Math.exp(-(f - at) / 3))));
const orb = (sub: V3, az: number, dist: number, y: number, lookY: number, rest: Partial<Cam> = {}, lookOff: [number, number] = [0, 0]): Shot =>
  ({ pos: [sub[0] + Math.sin(rad(az)) * dist, y, sub[2] + Math.cos(rad(az)) * dist], look: [sub[0] + lookOff[0], lookY, sub[2] + lookOff[1]], ...rest });
const jetAt = (f: number) => jetStrip(f) ?? { x: 0, y: 0, z: JET_STOP_Z, yaw: FACE_PZ, pitch: 0.098, roll: 0, nose: false };

// 1 HOOK: low on the strip just ahead of the kids, backing away as they pedal at us; the dragster rockets past the lens
// toward the jet; on "Landing" the lens punches up to the jet sliding down out of the sunset
const S1 = (f: number) => {
  const u = span(f, 0, 87), kz = kidZ(f), up = smooth((f - 36) / 26), rush = easeOut(f / 34);
  return hand({ pos: [lerp(-6.9, -7.35, rush), lerp(0.4, 0.78, rush), kz + lerp(6.5, 2.6, rush) + 0.3 * u], look: [lerp(-7.2, -6.5, up), lerp(1.2, 5.5, up), lerp(kz - 8, kz - 20, up)],
    fov: punch(lerp(70, 58, rush), f, B.landing, 0.12), roll: rad(lerp(-16, 4, rush) + 3 * Math.sin(f / 9)) }, f, 0.04);
};
// 2: Montreal, day: flying low along the brand-new jet from the tail to the nose, rising to the cockpit windows
const S2 = (f: number) => { const u = span(f, 87, 200);
  return hand({ pos: [RX + lerp(9.5, 5.2, u), lerp(2.2, 6.4, u), lerp(-34, 26, u)], look: [RX + lerp(0, 0.3, u), lerp(5.5, 5.6, u), lerp(-16, 27, u)], fov: 70, roll: rad(lerp(-8, 6, u)) }, f); };
// 3: the blank fuel gauge in close-up, pulling back to the captain tapping it, baffled
const S3 = (f: number) => { const u = span(f, 200, 264), turn = smooth((f - 228) / 12);
  return hand({ pos: [CX6 + lerp(-0.25, 0.45, u), lerp(0.8, 1.15, u), lerp(0.75, 0.95, u)], look: [lerp(CX6 + 0.02, BOB[0], turn), lerp(0.75, 1.15, turn), lerp(1.22, BOB[2], turn)], fov: lerp(52, 68, turn), roll: rad(lerp(10, -6, u)) }, f, 0.01); };
// 4: under the right wing: worm's-eye on the crewman pulling down the long dipstick, tilting up the stick to the wing
const S4 = (f: number) => { const u = span(f, 264, 354), a = rad(lerp(-35, 40, u));
  return hand({ pos: [CREW[0] + Math.sin(a) * lerp(3.0, 2.0, u), lerp(0.35, 0.8, u), CREW[2] + Math.cos(a) * lerp(3.0, 2.0, u)], look: [CREW[0], lerp(1.3, 3.2, smooth((f - 296) / 40)), CREW[2]], fov: punch(72, f, B.dipstick, 0.15), roll: rad(lerp(-12, 8, u)) }, f, 0.03); };
// 5: rising up past the wing's leading edge and over the tank, the "KILOS" label
const S5 = (f: number) => { const u = span(f, 354, 481);
  return hand({ pos: [RX + lerp(-15, -9, u), lerp(1.8, 7.8, u), lerp(9.5, 6.0, u)], look: [RX + lerp(-11, -7.5, u), lerp(3.4, 4.0, u), lerp(-1.0, -2.0, u)], fov: 70, roll: rad(lerp(10, -4, u)) }, f); };
// 6: tight on the crewman's clipboard and smug face
const S6 = (f: number) => { const u = span(f, 481, 542);
  return hand({ pos: [CREW[0] + lerp(-0.9, -0.4, u), lerp(1.55, 1.7, u), CREW[2] + lerp(2.3, 1.6, u)], look: [CREW[0] - 0.15, 1.5, CREW[2]], fov: punch(60, f, B.pounds, 0.12), roll: rad(lerp(5, -3, u)) }, f, 0.012); };
// 7: along the fuel hose from the truck to the wing, the nozzle crewman, "LESS THAN HALF"
const S7 = (f: number) => { const u = span(f, 542, 626), a = rad(lerp(40, -25, u));
  return hand({ pos: [NOZZLE_CREW[0] + Math.sin(a) * 3.6 + 1.2, lerp(1.1, 2.2, u), NOZZLE_CREW[2] + Math.cos(a) * 3.6], look: [NOZZLE_CREW[0] - 0.5, lerp(1.6, 2.2, u), NOZZLE_CREW[2] - 0.6], fov: 64, roll: rad(lerp(-10, 6, u)) }, f, 0.03); };
// 8: Ottawa: a whip onto the terminal's OTTAWA sign, down to the crewman checking again, nodding; "SAME MISTAKE"
const S8 = (f: number) => { const u = span(f, 626, 716), d = smooth((f - 640) / 40);
  return hand({ pos: [RX + lerp(-6, -12, u), lerp(9, 1.6, d), lerp(18, 3.0, u)], look: [lerp(RX, CREW[0], d), lerp(15, 1.5, d), lerp(45, CREW[2], d)], fov: punch(70, f, B.same, 0.15), roll: rad(lerp(8, -4, u)) }, f); };
// 9: 41,000 ft at sunset: swinging under the wing out to the side of the jet over the cloud sea
const S9 = (f: number) => { const u = span(f, 716, 762), z = cruiseZ(f);
  return hand({ pos: [KX + lerp(-14, -30, u), lerp(-3.5, 3.0, u), z + lerp(18, 4, u)], look: [KX, lerp(3.0, 4.2, u), z - 2], fov: 66, roll: rad(lerp(-14, -4, u)) }, f, 0.05); };
// 10: in the cockpit from the panel: BONG, the red light, both pilots snapping round
// cockpit framing (vertical frame): from beside the captain's side window, across both pilots stacked in depth
const cockCam = (f: number, a: number, b: number, side: number, near: number, far: number, tgt: V3, fov: number, roll0: number, roll1: number, amp = 0.01): Shot => { const u = span(f, a, b);
  return hand({ pos: [CX6 + side * lerp(1.42, 1.25, u), lerp(1.32, 1.28, u), lerp(near, far, u)], look: tgt, fov, roll: rad(lerp(roll0, roll1, u)) }, f, amp); };
const S10 = (f: number) => shake(cockCam(f, 762, 871, 1, 1.2, 0.35, [CX6 - 0.1, 1.12, -0.3], punch(70, f, B.bong + 2, 0.14), -12, 8), f, [B.bong, B.bong + 4, B.bong + 9], 0.05);
// 11: tight on the left engine's intake: the fan winds down, a puff of smoke out the back
const S11 = (f: number) => { const u = span(f, 871, 925), z = cruiseZ(f), a = rad(lerp(70, 25, u));
  return hand({ pos: [KX + 8.1 + Math.sin(a) * lerp(9, 6, u), lerp(-2.5, 1.2, u), z + 6.8 + Math.cos(a) * lerp(9, 6, u)], look: [KX + 8.1, 1.45, z + 6.0], fov: punch(56, f, B.left, 0.12), roll: rad(lerp(14, -4, u)) }, f, 0.05); };
// 12: the right engine from the other side, the same
const S12 = (f: number) => { const u = span(f, 925, 972), z = cruiseZ(f), a = rad(lerp(-70, -25, u));
  return hand({ pos: [KX - 8.1 + Math.sin(a) * lerp(9, 6, u), lerp(-2.0, 1.4, u), z + 6.8 + Math.cos(a) * lerp(9, 6, u)], look: [KX - 8.1, 1.45, z + 6.0], fov: punch(56, f, B.right, 0.12), roll: rad(lerp(-14, 4, u)) }, f, 0.05); };
// 13: back on the pilots, the screens click to black, two deadpan faces in the sunset light
// 13: from behind the seats: the glass panel dies behind the two pilots, who turn and give us a deadpan look
const S13 = (f: number) => { const u = span(f, 972, 1032);
  return hand({ pos: [CX6 + lerp(0.6, -0.3, u), lerp(2.15, 1.85, u), lerp(-2.4, -1.75, u)], look: [CX6, 1.2, 1.2], fov: punch(76, f, B.black, 0.12), roll: rad(lerp(9, -6, u)) }, f, 0.015); };
// 14: midday cutaway: alongside Bob's glider over the clouds; the barrel roll on "for fun"
const S14 = (f: number) => { const u = span(f, 1032, 1170), z = 26 * ((f - 1032) / FPS), a = rad(lerp(35, -25, u));
  return hand({ pos: [GX + Math.sin(a) * 6.0, lerp(0.7, 1.1, u), z + 1.9 + Math.cos(a) * 6.0], look: [GX, 0.75, z + 1.9], fov: punch(38, f, B.fun, 0.1), roll: rad(lerp(-10, 10, u)) }, f, 0.04); };
// 15: the co-pilot with the chart, pointing ahead; push in on "Gimli"
const S15 = (f: number) => cockCam(f, 1170, 1282, -1, 1.25, 0.35, [MAU[0] + 0.15, 1.15, MAU[2]], punch(68, f, B.gimli, 0.18), -12, 8, 0.02);
// 16: craning down over the pits on Family Day to the FAMILY DAY banner
const S16 = (f: number) => { const u = span(f, 1282, 1414);
  return hand({ pos: [lerp(-60, -22, u), lerp(42, 6.2, u), lerp(470, 358, u)], look: [lerp(-10, -17, u), lerp(0, 5.0, u), lerp(250, 345, u)], fov: punch(70, f, B.family, 0.1), roll: rad(lerp(10, -3, u)) }, f, 0.06); };
// 17: wheel level beside the dragster: burnout smoke, then the launch
const S17 = (f: number) => { const u = span(f, 1414, 1442);
  return shake(hand({ pos: [lerp(-5.4, -6.0, u), lerp(1.0, 1.2, u), lerp(342.5, 341.0, u)], look: [-8.2, 0.8, lerp(328, 318, u)], fov: 64, roll: rad(lerp(-10, -5, u)) }, f, 0.03), f, [1428], 0.06); };
// 18: low in front of the kids pedalling at us down the strip, the jet a speck in the sky behind them
const S18 = (f: number) => { const u = span(f, 1442, 1475), kz = kidZ(f), rush = easeOut((f - 1442) / 30);
  return hand({ pos: [lerp(-5.8, -7.3, rush), lerp(0.4, 0.8, rush), kz + lerp(6.0, 2.4, rush)], look: [-7.3, 1.25, kz - 6], fov: lerp(68, 60, rush), roll: rad(lerp(14, 2, rush)) }, f, 0.04); };
// 19: behind the BBQ kettle: the dad turns, drops his spatula; behind him the jet coming in silently over the strip
const S19 = (f: number) => { const u = span(f, 1475, 1560), j = jetAt(f), k = smooth((f - 1500) / 40);
  return hand({ pos: [DAD[0] + lerp(-0.1, 0.1, u), lerp(1.0, 0.9, u), DAD[2] + lerp(3.6, 2.7, u)], look: [DAD[0] + lerp(-0.3, -0.1, k), lerp(1.55, 3.4, k), lerp(DAD[2] - 2, DAD[2] - 30, k)], fov: lerp(54, 48, u), roll: rad(lerp(-6, 2, u)) }, f, 0.025); };
// 20: Bob hauling on the yoke, sweating
const S20 = (f: number) => shake(cockCam(f, 1560, 1647, 1, 0.75, 0.5, [BOB[0] - 0.2, 1.1, BOB[2]], punch(66, f, 1617, 0.12), 12, 18, 0.02), f, [1628], 0.02);
// 21: from the grass beside the runway: the jet sliding past sideways, the lens whipping round with it
const S21 = (f: number) => { const j = jetAt(f), u = span(f, 1647, 1703);
  return hand({ pos: [lerp(-4, -16, u), lerp(1.0, 2.4, u), lerp(172, 150, u)], look: [j.x, j.y + 3.5, j.z], fov: lerp(30, 56, u), roll: rad(lerp(-12, 10, u)) }, f, 0.06); };
// 22: low ahead on the strip: the mains hit, the nose slams down, sparks
const S22 = (f: number) => { const j = jetAt(f), u = span(f, 1703, 1752);
  return shake(hand({ pos: [lerp(-19, -9, u), lerp(0.6, 1.2, u), lerp(190, 212, u)], look: [j.x + 1, lerp(3.0, 2.0, u), j.z + 18], fov: punch(60, f, B.collapse, 0.12), roll: rad(lerp(-8, -3, u)) }, f, 0.04), f, [1704, B.collapse + 6], 0.08); };
// 23: among the crowd at the end of the strip: the nose scraping straight at us, stopping just short
const S23 = (f: number) => { const j = jetAt(f), u = span(f, 1752, 1844);
  return shake(hand({ pos: [lerp(-0.8, -0.4, u), lerp(1.0, 1.25, u), lerp(289, 287, u)], look: [j.x, lerp(2.2, 2.8, u), Math.min(j.z + 24, 268)], fov: lerp(60, 66, u), roll: rad(lerp(4, -2, u)) }, f, 0.03), f, [1780, B.stop], 0.05); };
// 24: circling the nose: racers blasting their extinguishers
const S24 = (f: number) => { const u = span(f, 1844, 1896);
  return hand(orb([0, 0, JET_STOP_Z + 24], lerp(-7, 6, u), lerp(12.5, 11, u), lerp(1.5, 2.0, u), 1.7, { fov: punch(64, f, B.fire, 0.1), roll: rad(lerp(-6, 4, u)) }, [0, lerp(-2, 0, u)]), f, 0.03); };
// 25: craning up from Bob's thumbs-up to the whole jet, nose on the tarmac, the crowd round it
const S25 = (f: number) => { const u = span(f, 1896, 1939);
  return hand({ pos: [lerp(2.4, 18, u), lerp(1.4, 12, u), lerp(271.8, 296, u)], look: [lerp(1.8, 0, u), lerp(1.45, 3.0, u), lerp(266, 248, u)], fov: lerp(58, 70, u), roll: rad(lerp(4, -3, u)) }, f, 0.03); };
// 26: dusk, the mechanics' van on the country road, tracking alongside
const vanZ = (f: number) => vehiclesAt(26, f).van?.z ?? 0;
const S26 = (f: number) => { const u = span(f, 1939, 2010), z = vanZ(f), a = rad(lerp(150, 70, u));
  return hand({ pos: [DX + 1.8 + Math.sin(a) * lerp(9, 5.5, u), lerp(0.8, 1.6, u), z + Math.cos(a) * lerp(9, 5.5, u)], look: [DX + 1.8, 1.2, z], fov: 62, roll: rad(lerp(-10, 6, u)) }, f, 0.04); };
// 27a: low in front as it coughs and rolls to a stop; 27b: the two mechanics, the empty jerrycan, deadpan
const S27a = (f: number) => { const u = span(f, 2010, 2045), z = vanZ(f);
  return hand({ pos: [DX + lerp(-3.5, -0.4, u), lerp(0.4, 0.9, u), VAN_STOP_Z + lerp(17, 8, u)], look: [DX + 1.6, 1.1, z], fov: lerp(70, 58, u), roll: rad(lerp(10, 0, u)) }, f, 0.03); };
const S27b = (f: number) => { const u = span(f, 2045, TOTAL);
  return hand({ pos: [DX + lerp(5.9, 5.4, u), lerp(1.55, 1.5, u), lerp(3.2, 2.7, u)], look: [DX + 3.6, 1.35, 0.85], fov: lerp(52, 44, u), roll: rad(lerp(-3, 1, u)) }, f, 0.006); };
const CAMS: Record<number, Key[]> = {
  1: [{ f: 0, s: S1 }], 2: [{ f: 87, s: S2 }], 3: [{ f: 200, s: S3 }], 4: [{ f: 264, s: S4 }], 5: [{ f: 354, s: S5 }], 6: [{ f: 481, s: S6 }],
  7: [{ f: 542, s: S7 }], 8: [{ f: 626, s: S8 }], 9: [{ f: 716, s: S9 }], 10: [{ f: 762, s: S10 }], 11: [{ f: 871, s: S11 }], 12: [{ f: 925, s: S12 }],
  13: [{ f: 972, s: S13 }], 14: [{ f: 1032, s: S14 }], 15: [{ f: 1170, s: S15 }], 16: [{ f: 1282, s: S16 }], 17: [{ f: 1414, s: S17 }], 18: [{ f: 1442, s: S18 }],
  19: [{ f: 1475, s: S19 }], 20: [{ f: 1560, s: S20 }], 21: [{ f: 1647, s: S21 }], 22: [{ f: 1703, s: S22 }], 23: [{ f: 1752, s: S23 }], 24: [{ f: 1844, s: S24 }],
  25: [{ f: 1896, s: S25 }], 26: [{ f: 1939, s: S26 }], 27: [{ f: 2010, s: S27a }, { f: 2045, cut: true, s: S27b }],
};
// ---------------- whips: the lens swings out at the end of a shot and in at the start of the next (set changes) ----------------
const WHIP_W = 4, WHIP_A = 42;
export const WHIPS: { at: number; dir: number }[] = [87, 264, 481, 542, 626, 716, 762, 871, 925, 972, 1032, 1170, 1282, 1414, 1442, 1475, 1560, 1647, 1844, 1939]
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

// ---------------- lens: background blur on close-ups (subject sharp), wides sharp ----------------
const DOFS: Record<number, { cInf: number; focus: (f: number) => V3 }> = {
  3: { cInf: 8, focus: (f) => (f < 232 ? [CX6, 0.745, 1.2] : [BOB[0], 1.1, BOB[2]]) }, 4: { cInf: 6, focus: () => [CREW[0], 1.6, CREW[2]] },
  6: { cInf: 9, focus: () => [CREW[0], 1.5, CREW[2]] }, 7: { cInf: 5, focus: () => [NOZZLE_CREW[0], 1.7, NOZZLE_CREW[2]] },
  10: { cInf: 6, focus: () => [CX6, 1.15, -0.28] }, 13: { cInf: 6, focus: () => [CX6, 1.15, -0.28] }, 15: { cInf: 7, focus: () => [MAU[0], 1.15, MAU[2]] },
  18: { cInf: 6, focus: (f) => [-7.3, 1.1, kidZ(f)] }, 19: { cInf: 7, focus: (f) => (f < 1505 ? [DAD[0], 1.5, DAD[2]] : [DAD[0], 1.5, DAD[2]]) },
  20: { cInf: 7, focus: () => [BOB[0], 1.1, BOB[2]] }, 27: { cInf: 6, focus: (f) => (f < 2045 ? [DX + 1.8, 1.2, VAN_STOP_Z] : [DX + 3.6, 1.4, 0.8]) },
};
export const dofAt = (id: number, _f: number) => { const d = DOFS[id]; return d ? { cInf: d.cInf, focus: d.focus } : { cInf: 0, focus: undefined }; };
export const focusAt = (id: number, f: number): V3 => (DOFS[id]?.focus(f) ?? camAt(id, f).look);
