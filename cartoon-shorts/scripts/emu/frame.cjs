"use strict";

// src/videos/emu/places.ts
var FENCE_Z = -5;
var CAMP = { x: 16, z: 14 };
var DAM = { x: 240, z: -40, r: 10, wallX: 226, wallH: 1.1 };
var CHASE = { x: 420, z: -220 };
var BURST = { x: 640, z: 40 };
var OFFICE = { x: -2e3, z: 0 };
var PARL = { x: -2100, z: 0 };
var FLOOR = { x: -2200, z: 0 };

// src/videos/emu/story.ts
var FPS = 30;
var TOTAL = 2085;
var clamp01 = (x) => Math.max(0, Math.min(1, x));
var smooth = (x) => {
  const u = clamp01(x);
  return u * u * (3 - 2 * u);
};
var FAR = [160, 1400];
var SHOTS = [
  { id: 1, a: 0, b: 132, light: "day", crowd: "hook", fog: FAR, sunAz: 110, sunEl: 42 },
  // soldiers with machine guns ... a war against birds
  { id: 2, a: 132, b: 167, light: "day", crowd: "won", fog: FAR, sunAz: 120 },
  // and the birds won
  { id: 3, a: 167, b: 244, light: "day", crowd: "march", fog: FAR },
  // 20,000 emus marched into the wheat fields
  { id: 4, a: 244, b: 311, light: "day", crowd: "eat", fog: FAR },
  // eating everything
  { id: 5, a: 311, b: 410, light: "lab", crowd: "minister" },
  // the farmers, old soldiers, asked the minister
  { id: 6, a: 410, b: 518, light: "day", crowd: "lineup", fog: FAR },
  // a major, two gunners, two guns, 10,000 bullets
  { id: 7, a: 518, b: 586, light: "day", crowd: "camera", fog: FAR },
  // a cameraman to film the victory
  { id: 8, a: 586, b: 676, light: "day", crowd: "lunch", fog: FAR },
  // "home by lunch"
  { id: 9, a: 676, b: 774, light: "day", crowd: "dam", fog: FAR, sunAz: 120 },
  // at a farm dam, a thousand birds
  { id: 10, a: 774, b: 847, light: "day", crowd: "fire", fog: FAR, sunAz: 120 },
  // fired, hit twelve, jammed
  { id: 11, a: 847, b: 923, light: "day", crowd: "truck", fog: FAR },
  // a gun on a truck to chase them down
  { id: 12, a: 923, b: 990, light: "day", crowd: "chase", fog: FAR, sunAz: 100 },
  // an emu runs 50 km/h
  { id: 13, a: 990, b: 1058, light: "day", crowd: "bumpy", fog: FAR, sunAz: 100 },
  // so bumpy, couldn't aim at a thing
  { id: 14, a: 1058, b: 1117, light: "day", crowd: "wait", fog: FAR },
  // wait, how do birds beat a machine gun?
  { id: 15, a: 1117, b: 1262, light: "day", crowd: "flock", fog: FAR, sunAz: 140, sunEl: 55 },
  // works best on a crowd; refused to stay a crowd
  { id: 16, a: 1262, b: 1366, light: "day", crowd: "burst", fog: FAR, sunAz: 140, sunEl: 55 },
  // they split into tiny groups, every direction
  { id: 17, a: 1366, b: 1417, light: "lab", crowd: "marbles" },
  // like a dropped bag of marbles
  { id: 18, a: 1417, b: 1545, light: "day", crowd: "lookout", fog: FAR },
  // every group had a lookout
  { id: 19, a: 1545, b: 1590, light: "day", crowd: "home", fog: FAR },
  // the army went home
  { id: 20, a: 1590, b: 1663, light: "lab", crowd: "parliament" },
  // in Parliament ... a medal
  { id: 21, a: 1663, b: 1767, light: "day", crowd: "brass", fog: FAR },
  // they came back ... nearly 10,000 bullets
  { id: 22, a: 1767, b: 1823, light: "day", crowd: "ten", fog: FAR },
  // ten bullets for every emu
  { id: 23, a: 1823, b: 1897, light: "golden", crowd: "report", fog: FAR },
  // the major's report? pure admiration
  { id: 24, a: 1897, b: TOTAL, light: "golden", crowd: "parade", fog: FAR }
  // "If we had a division ... any army in the world"
];
var shotAt = (f) => SHOTS.find((s) => f >= s.a && f < s.b) ?? SHOTS[SHOTS.length - 1];
var HOOK_GUN = [0, 0, -12];
var HOOK_GUNNER = [0, 0, -10.75];
var HOOK_LOADER = [-0.95, 0, -11.2];
var HOOK_MAJOR = [1.05, 0, -10.5];
var WON_EMU = [-0.35, 0, -13];
var FENCE_FARMER = [6.2, 0, -3];
var O = OFFICE;
var P = PARL;
var F = FLOOR;
var C = CAMP;
var MINISTER_AT = [O.x, 0, O.z - 2.4];
var FARMERS_AT = [[O.x - 1.05, 0, O.z - 0.55], [O.x, 0, O.z - 0.3], [O.x + 1.05, 0, O.z - 0.55]];
var LINE_Z = C.z;
var LINE = { major: C.x, g1: C.x + 0.75, g2: C.x + 1.45, guns: C.x + 2.35, crates: C.x + 3.55 };
var CAMERA_AT = [C.x - 3, 0, C.z + 2];
var POSE_MAJOR = [C.x - 0.9, 0, C.z + 1.7];
var DAM_GUN = [DAM.wallX + 0.55, 1, DAM.z];
var DAM_GUNNER = [DAM.wallX - 0.5, 0.95, DAM.z];
var DAM_LOADER = [DAM.wallX - 0.3, 0.98, DAM.z - 1.2];
var DAM_MAJOR = [DAM.wallX - 0.9, 0.85, DAM.z - 2.3];
var TRUCK_PARK = [C.x + 7, 0, C.z - 5];
var truckAt = (f, id) => {
  if (id === 11) {
    const t = Math.max(0, (f - 892) / FPS), s = 0.5 * 3.2 * t * t;
    return { x: TRUCK_PARK[0] + s, z: TRUCK_PARK[2], yaw: 0, s, bounce: 0, pitch: s > 0 ? 0.02 * Math.sin(f * 0.9) : 0 };
  }
  if (id === 12 || id === 13) {
    const s = 9 * ((f - 923) / FPS);
    const bounce = 0.11 * Math.abs(Math.sin(f * 0.55)) + 0.05 * Math.abs(Math.sin(f * 1.7 + 1));
    return { x: CHASE.x + s, z: CHASE.z, yaw: 0, s, bounce, pitch: 0.06 * Math.sin(f * 0.8) };
  }
  if (id === 19) {
    const s = 7 * ((f - 1545) / FPS);
    return { x: C.x + 12 - s, z: C.z - 9.5, yaw: Math.PI, s, bounce: 0.02 * Math.abs(Math.sin(f * 0.6)), pitch: 0 };
  }
  return { x: TRUCK_PARK[0], z: TRUCK_PARK[2], yaw: 0, s: 0, bounce: 0, pitch: 0 };
};
var MP_ASK = [P.x + 1.6, 0, P.z - 0.6];
var BRASS = [C.x + 14, 0, C.z - 1];
var BRASS_H = 1.45;
var DESK_AT = [C.x + 3, 0, C.z + 1.4];
var PARADE_MAJOR = [C.x - 0.6, 0, C.z - 1];
var PARADE_Z = C.z - 3.4;
var paradeX = (f) => C.x - 11 + 1.3 * ((f - 1897) / FPS);
var LEAD_STOP = 2012;
var MARBLE_FLOOR = [F.x, 0, F.z - 1.2];
var glide = (u) => {
  const x = clamp01(u);
  return x * x * x * (x * (6 * x - 15) + 10);
};
var mixC = (a, b, k) => ({
  pos: a.pos.map((v, i) => v + (b.pos[i] - v) * k),
  look: a.look.map((v, i) => v + (b.look[i] - v) * k),
  fov: a.fov + (b.fov - a.fov) * k,
  roll: a.roll + (b.roll - a.roll) * k
});
var full = (c) => ({ fov: 40, roll: 0, ...c });
var run = (keys, f) => {
  let cur = full(keys[0].s(f));
  for (let i = 1; i < keys.length; i++) {
    const k = keys[i];
    if (f < k.f) break;
    cur = k.cut ? full(k.s(f)) : mixC(cur, full(k.s(f)), glide((f - k.f) / (k.dur ?? 24)));
  }
  return cur;
};
var pushK = (f, f0, rate, punch = 0, n = 35) => {
  const x = Math.max(0, f - f0);
  let s = rate * x;
  if (punch > rate) for (let i = 0; i < Math.min(x, n); i++) s += (punch - rate) * Math.max(0, Math.min(1, (i + 0.5) / 8, (n - i - 0.5) / 8));
  return Math.exp(-s);
};
var dolly = (pos, look, k, rest = {}) => ({ pos: [look[0] + (pos[0] - look[0]) * k, look[1] + (pos[1] - look[1]) * k, look[2] + (pos[2] - look[2]) * k], look, ...rest });
var rad = (d) => d * Math.PI / 180;
var creep = (pos, look, f, f0, mps, rest = {}) => {
  const d = [look[0] - pos[0], look[1] - pos[1], look[2] - pos[2]], n = Math.hypot(d[0], d[1], d[2]) || 1;
  const s = mps * Math.max(0, f - f0) / FPS;
  return { pos: [pos[0] + d[0] / n * s, pos[1] + d[1] / n * s, pos[2] + d[2] / n * s], look: [look[0] + d[0] / n * s, look[1] + d[1] / n * s, look[2] + d[2] / n * s], ...rest };
};
var add3 = (a, dx, dy, dz) => [a[0] + dx, a[1] + dy, a[2] + dz];
var S1a = (f) => creep([2, 1.55, -5.4], [-0.9, 1.25, -22], f, 0, 0.22, { fov: 52, roll: rad(-2) });
var S1b = (f) => dolly([2.4, 1.3, -6.1], [0.1, 1.2, -11.6], pushK(f, 84, 25e-4, 6e-3, 25), { fov: 44 });
var S2a = (f) => dolly(add3(WON_EMU, 0.25, 1.45, 3.3), add3(WON_EMU, 0.05, 1.35, 0), pushK(f, 132, 4e-3, 0.012, 20), { fov: 42, roll: rad(4) });
var S3a = (f) => creep([34, 21, 22], [-4, 0, -70], f, 167, 0.9, { fov: 52 });
var S4a = (f) => dolly(add3(FENCE_FARMER, 0.3, 1.55, 5.6), add3(FENCE_FARMER, 0.3, 1.05, -4.5), pushK(f, 244, 2e-3, 5e-3, 25), { fov: 46 });
var S5a = (f) => dolly([O.x + 0.2, 1.75, O.z + 5.4], [O.x, 1.35, O.z - 1.6], pushK(f, 311, 18e-4, 4e-3, 25), { fov: 50 });
var S5b = (f) => dolly([MINISTER_AT[0] + 0.1, 1.6, MINISTER_AT[2] + 1.85], [MINISTER_AT[0], 1.5, MINISTER_AT[2]], pushK(f, 378, 3e-3, 8e-3, 22), { fov: 44 });
var lineCam = (x) => (f) => ({ pos: [x, 1.4, LINE_Z + 5.2], look: [x, 1.05, LINE_Z - 0.4], fov: 46 });
var S7a = (f) => dolly([CAMERA_AT[0] + 1.3, 1.5, CAMERA_AT[2] + 6.2], [CAMERA_AT[0] + 1.3, 1.1, CAMERA_AT[2] - 0.3], pushK(f, 518, 2e-3, 6e-3, 25), { fov: 48 });
var S8a = (f) => dolly([LINE.g2 - 0.45, 1.45, LINE_Z + 3.6], [LINE.g2, 1.5, LINE_Z], pushK(f, 586, 28e-4, 8e-3, 22), { fov: 40, roll: rad(3) });
var S9a = (f) => creep([DAM.wallX - 6.5, 3.4, DAM.z + 1.4], [DAM.wallX + 10, 0.5, DAM.z - 2], f, 676, 0.25, { fov: 52 });
var S10a = (f) => dolly([DAM_GUN[0] - 0.05, 2.1, DAM_GUN[2] + 5.6], [DAM_GUN[0] - 0.05, 1.65, DAM_GUN[2] - 0.3], pushK(f, 774, 3e-3, 9e-3, 22), { fov: 44 });
var S10h = (f) => creep([DAM.x + 7, 1.9, DAM.z + 2], [DAM.x + 22, 0.9, DAM.z - 3], f, 797, 0.4, { fov: 46 });
var S11a = (f) => creep([TRUCK_PARK[0] - 3.2, 1.7, TRUCK_PARK[2] + 8.6], [TRUCK_PARK[0] - 0.4, 1.4, TRUCK_PARK[2]], f, 847, 0.2, { fov: 50 });
var S12a = (f) => {
  const t = truckAt(f, 12);
  return { pos: [t.x + 0.2, 3.6, t.z + 11.5], look: [t.x + 0.6, 0.9, t.z - 6], fov: 50 };
};
var S13a = (f) => {
  const t = truckAt(f, 13);
  return { pos: [t.x - 1.2, 2.4, t.z + 4.4], look: [t.x - 0.9, 1.9, t.z], fov: 46, roll: rad(3 * Math.sin(f * 0.5)) };
};
var S14a = (f) => dolly(add3(DAM_MAJOR, 0.05, 1.75, 3.4), add3(DAM_MAJOR, 0, 1.45, 0), pushK(f, 1058, 3e-3, 0.012, 20), { fov: 40, roll: rad(-4) });
var S15a = (f) => dolly([BURST.x + 2, 15, BURST.z + 17], [BURST.x, 0, BURST.z - 1], pushK(f, 1117, 12e-4, 3e-3, 25), { fov: 42 });
var S16a = (f) => {
  const k = smooth((f - 1262) / 60);
  return { pos: [BURST.x + 2, 15 + 8 * k, BURST.z + 17 + 7 * k], look: [BURST.x, 0, BURST.z - 1], fov: 44 + 6 * k };
};
var S17a = (f) => dolly(add3(MARBLE_FLOOR, 0.15, 1.05, 1.9), add3(MARBLE_FLOOR, 0, 0.05, -0.15), pushK(f, 1366, 18e-4), { fov: 52 });
var LOOKOUT = [60, 0, -30];
var S18a = (f) => dolly(add3(LOOKOUT, 0.4, 1.6, 7.6), add3(LOOKOUT, 0.4, 1.4, -1.2), pushK(f, 1417, 18e-4, 5e-3, 25), { fov: 46 });
var S18b = (f) => dolly(add3(LOOKOUT, 0.3, 1.75, 5.2), add3(LOOKOUT, 0.3, 1.45, 0), pushK(f, 1500, 3e-3, 0.012, 20), { fov: 44 });
var S19a = (f) => creep([C.x + 11, 1.7, C.z + 1.5], [C.x + 6, 1.1, C.z - 21], f, 1545, 0.3, { fov: 54 });
var S20a = (f) => dolly([P.x - 1.4, 2.2, P.z + 5.6], [P.x + 2.2, 1.3, P.z - 1.4], pushK(f, 1590, 18e-4, 5e-3, 25), { fov: 48 });
var S21a = (f) => dolly([BRASS[0] + 1.6, 1.9, BRASS[2] + 8], [BRASS[0] + 0.4, 1.3, BRASS[2]], pushK(f, 1663, 18e-4, 4e-3, 25), { fov: 48 });
var TEN_EMU = [BRASS[0] - 4.5, 0, BRASS[2] + 1];
var S22a = (f) => dolly(add3(TEN_EMU, 0.1, 1.3, 4.2), add3(TEN_EMU, 0.1, 0.85, 0), pushK(f, 1767, 25e-4, 7e-3, 22), { fov: 44 });
var S23a = (f) => dolly(add3(DESK_AT, 0.15, 1.45, 2.6), add3(DESK_AT, 0, 1, -0.4), pushK(f, 1823, 25e-4, 6e-3, 25), { fov: 42 });
var S24a = (f) => creep([PARADE_MAJOR[0] - 0.6, 1.5, PARADE_MAJOR[2] + 6.2], [PARADE_MAJOR[0] + 0.6, 1, PARADE_Z - 0.6], f, 1897, 0.12, { fov: 54 });
var S24b = (f) => creep([(PARADE_MAJOR[0] + paradeX(LEAD_STOP) + 7.75) / 2, 1.5, PARADE_MAJOR[2] + 6.6], [(PARADE_MAJOR[0] + paradeX(LEAD_STOP) + 7.75) / 2, 1.1, PARADE_Z + 0.6], f, 2012, 0.08, { fov: 50 });
var CAMS = {
  1: [{ f: 0, s: S1a }, { f: 84, cut: true, s: S1b }],
  2: [{ f: 132, s: S2a }],
  3: [{ f: 167, s: S3a }],
  4: [{ f: 244, s: S4a }],
  5: [{ f: 311, s: S5a }, { f: 376, cut: true, s: S5b }],
  6: [{ f: 410, s: lineCam(LINE.major + 0.2) }, { f: 432, dur: 20, s: lineCam(LINE.g1 + 0.4) }, { f: 452, dur: 20, s: lineCam(LINE.guns) }, { f: 474, dur: 22, s: lineCam(LINE.crates - 0.6) }, { f: 498, dur: 18, s: (f) => ({ pos: [C.x + 1.85, 1.65, LINE_Z + 10.2], look: [C.x + 1.85, 0.9, LINE_Z - 0.4], fov: 46 }) }],
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
  24: [{ f: 1897, s: S24a }, { f: 2010, cut: true, s: S24b }]
};
var camAt = (id, f) => run(CAMS[id], f);

// scripts/emu/frame_entry.ts
var pts = (f, id) => {
  const tr = truckAt(f, id);
  const tray = [tr.x + Math.cos(tr.yaw) * -1.65, 0.95 + tr.bounce, tr.z - Math.sin(tr.yaw) * -1.65];
  const M = {
    1: [["gunner", HOOK_GUNNER], ["loader", HOOK_LOADER], ["major", HOOK_MAJOR], ["gun", HOOK_GUN], ["emuNear", [0, 0, -24]], ["emuFar", [0, 0, -60]]],
    2: [["emu", WON_EMU], ["gunner", [WON_EMU[0] + 1, 0, WON_EMU[2] + 0.5]]],
    4: [["farmer", FENCE_FARMER], ["emu1", [6.6, 0, -7.2]], ["emu2", [9.6, 0, -8.4]], ["emu3", [5.4, 0, -10.8]]],
    5: [["minister", MINISTER_AT], ...FARMERS_AT.map((p, i) => ["farmer" + i, p])],
    7: [["cameraman", [CAMERA_AT[0] - 0.55, 0, CAMERA_AT[2]]], ["camera", CAMERA_AT], ["major", POSE_MAJOR], ["g0", [POSE_MAJOR[0] + 1, 0, POSE_MAJOR[2] - 0.8]]],
    8: [["g1", [LINE.g2, 0, LINE_Z]], ["g0", [LINE.g2 - 1.1, 0, LINE_Z - 0.9]]],
    9: [["gunner", DAM_GUNNER], ["loader", DAM_LOADER], ["major", DAM_MAJOR], ["gun", DAM_GUN], ["emuA", [DAM.x + 18, 0, DAM.z]], ["emuB", [DAM.x + 50, 0, DAM.z - 20]]],
    10: [["gunner", DAM_GUNNER], ["loader", DAM_LOADER], ["major", DAM_MAJOR], ["gun", DAM_GUN], ["emuA", [DAM.x + 15, 0, DAM.z]]],
    11: [["tray", tray], ["major", [TRUCK_PARK[0] - 1.4, 0, TRUCK_PARK[2] + 1.9]], ["truckNose", [tr.x + 3.2, 1, tr.z]]],
    12: [["tray", tray], ["truckNose", [tr.x + 3.2, 1, tr.z]], ["emu0", [CHASE.x - 16 + 14 * ((f - 923) / 30), 0, CHASE.z - 4]], ["emu7", [CHASE.x - 16 + 14 * ((f - 923) / 30) + 7 * 3.1, 0, CHASE.z - 7.2]]],
    13: [["tray", tray], ["emu7", [CHASE.x - 16 + 14 * ((f - 923) / 30) + 7 * 3.1, 0, CHASE.z - 7.2]]],
    19: [["truck", [tr.x, 1, tr.z]], ["emu0", [CAMP.x - 2, 0, FENCE_Z - 1.2]], ["emu8", [CAMP.x - 2 + 8 * 1.7, 0, FENCE_Z - 1.2]]],
    20: [["mp", MP_ASK]],
    21: [["gunner", [BRASS[0] - 0.2, BRASS_H - 0.32, BRASS[2]]], ["emuWalk", [BRASS[0] + 2, 0, BRASS[2] + 2.6]]],
    22: [["emu", TEN_EMU]],
    23: [["major", DESK_AT]],
    24: [["major", PARADE_MAJOR], ["col0", [paradeX(f), 0, PARADE_Z]], ["lead", [paradeX(Math.min(f, LEAD_STOP)) + 7.75, 0, PARADE_Z]], ["back", [paradeX(f), 0, PARADE_Z - 3.75]]],
    18: [["lookout", LOOKOUT]],
    14: [["major", DAM_MAJOR]]
  };
  return M[id] ?? [];
};
var fr = process.argv.slice(2).map(Number);
for (const f of fr) {
  const id = shotAt(f).id, c = camAt(id, f);
  const fw = [c.look[0] - c.pos[0], c.look[1] - c.pos[1], c.look[2] - c.pos[2]], n = Math.hypot(...fw);
  const F2 = fw.map((v) => v / n);
  let R = [F2[1] * 0 - F2[2] * 1, F2[2] * 0 - F2[0] * 0, F2[0] * 1 - F2[1] * 0];
  const rn = Math.hypot(...R);
  R = R.map((v) => v / rn);
  const U = [R[1] * F2[2] - R[2] * F2[1], R[2] * F2[0] - R[0] * F2[2], R[0] * F2[1] - R[1] * F2[0]];
  const ty = Math.tan(c.fov * Math.PI / 360), tx = ty * 9 / 16;
  const out = [];
  for (const [name, p] of pts(f, id)) {
    for (const [lab, dy] of [["ft", 0], ["hd", 1.75]]) {
      const d = [p[0] - c.pos[0], p[1] + dy - c.pos[1], p[2] - c.pos[2]], z = d[0] * F2[0] + d[1] * F2[1] + d[2] * F2[2];
      const sx = 0.5 + (d[0] * R[0] + d[1] * R[1] + d[2] * R[2]) / z / tx / 2, sy = 0.5 - (d[0] * U[0] + d[1] * U[1] + d[2] * U[2]) / z / ty / 2;
      if (lab === "ft") out.push(`${name}: x${sx.toFixed(2)} ft${sy.toFixed(2)}`);
      else out[out.length - 1] += ` hd${sy.toFixed(2)} z${z.toFixed(1)}`;
    }
  }
  console.log(`f${f} s${id}  ` + out.join(" | "));
}
