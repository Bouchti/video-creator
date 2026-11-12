// The Hoover-van cast as flat toon cards for the Blender renderer (scripts/export_hoover.ts): every frame each character
// asks for a drawing (key + draw call); effects are unlit cards. Same drawing kit as the marathon (../marathon/toon).
import * as THREE from "three";
import { Pen, bodyFront, bodySide, fxShadow, fxContact, fxQuestion, INK, Outfit, Expr, FrontOpts, SideOpts, SKINS } from "../marathon/toon";
import { fxFlashStar } from "../marathon/mikedraw";
import { fxShout, fxRunLines, fxLabel, fxSweat, fxCalendar } from "../marathon/molassesdraw";
import {
  fxVacuum, fxVacBox, fxTicket, fxPlane, fxScale, fxSmallAds, fxWeek, fxClock, fxForm, fxStampText, fxSuds, fxCourtOrder, fxGavel,
  fxTea, fxOfficeBox, fxHorse, fxCountTag, fxSold, HRED,
} from "./hooverdraw";
import {
  FPS, SHOTS, clamp01, smooth, V3, DAVE_H, HORSE_WIN, SALES, DOOR_EXT, EXEC_DESK, DAVE_K, REPAIR_K, DOOR_K, DAVE_DOOR, BAILIFF, TEA,
  SCALE_AT, PAPER, ROW_Z, boxManZ, firedZ, planeX, vanAt, truckAt, HOOK_BANG, BLOCK_BANG, SHOP, FACT, OFFICE, WASHER, VAN_PARK, TRUCK_PARK, FRONT_DOOR,
} from "./story";

export type Place = { key: string; draw: (p: Pen) => void; x: number; y: number; z: number; scale?: number; mirror?: boolean; yaw?: number; geo?: "body" | "wide"; roll?: number };
export type FxPlace = { key: string; cw: number; ch: number; draw: (p: Pen) => void; x: number; y: number; z: number; w: number; h: number; flat?: boolean; rot?: number; soft?: boolean; upright?: boolean };
export type CamInfo = { pos: THREE.Vector3; right: THREE.Vector3; sun?: THREE.Vector3 };
export type PropPlace = { k: string; x: number; y: number; z: number; yaw: number; s: number; pitch: number; roll: number };
export type Overlay = { t: "label" | "shout" | "stamp" | "q"; text: string; x: number; y: number; z: number; k: number; w: number; bg?: string; rot?: number; wob?: number };
export type Stage = { places: Place[]; fx: FxPlace[]; props: PropPlace[]; ov: Overlay[] };

const hh = (i: number, s = 0) => { const v = Math.sin(i * 127.1 + s * 311.7) * 43758.5453; return v - Math.floor(v); };
const q = (v: number, n = 120) => Math.round(v * n) / n;
const seedOf = (i: number) => ((i * 5 + 3) % 7) + 1;
const SUN = new THREE.Vector3(0.5, 0.75, -0.4).normalize();
const tmp = new THREE.Vector3();
const light2D = (cam: CamInfo, mirror: boolean) => {
  const sx = SUN.dot(cam.right) * (mirror ? -1 : 1), sy = -SUN.y;
  return Math.round(Math.atan2(sy, sx) / (Math.PI / 4)) * (Math.PI / 4);
};
const viewOf = (cam: CamInfo, x: number, z: number, dx: number, dz: number) => {
  const tx = cam.pos.x - x, tz = cam.pos.z - z, tl = Math.hypot(tx, tz) || 1;
  const c = (tx * dx + tz * dz) / tl;
  return { side: c < 0.57, mirror: dx * cam.right.x + dz * cam.right.z < 0, fs: Math.round(Math.sqrt(Math.max(0, 1 - c * c)) * 20) / 20 };
};
const LEAD = 2 / FPS;
const LID = [0.5, 1, 1, 0.5];
const lidAt = (t: number, i: number, swaps: number[] = []) => {
  const f = Math.round(t * FPS);
  for (const ts of swaps) { const k = f - Math.round((ts - LEAD) * FPS) + 1; if (k >= 0 && k < 4) return LID[k]; }
  let s = Math.round(-60 * hh(i, 9));
  for (let n = 0; s <= f && n < 400; n++) {
    const k = f - s;
    if (k >= 0 && k < 4) return LID[k];
    s += Math.round(15 + 54 * hh(i * 31 + n, 13));
  }
  return 0;
};
const fkey = (o: object) => JSON.stringify(o, (_k, v) => (typeof v === "number" ? q(v) : v));
type Who = { i: number; o: Outfit; okey: string };
const person = (cam: CamInfo, who: Who, x: number, y: number, z: number, view: { side: boolean; mirror: boolean }, fo: FrontOpts, so: SideOpts, scale = 1): Place => {
  const mirror = view.side && view.mirror, light = light2D(cam, mirror), seed = seedOf(who.i);
  const f2: FrontOpts = { ...fo, light, seed }, s2: SideOpts = { ...so, light, seed };
  const key = view.side ? `S|${who.okey}|${fkey(s2)}` : `F|${who.okey}|${fkey(f2)}`;
  return { key, x, y, z, scale, mirror, draw: (p) => (view.side ? bodySide(p, who.o, s2) : bodyFront(p, who.o, f2)) };
};
const TAIL: [number, number, number] = [0.42, 0.44, 0.62];
const CONTACT: [number, number, number] = [0.2, 0.21, 0.33];
const toSrgb = (v: number) => { const c = clamp01(v); return c <= 0.0031308 ? 12.92 * c : 1.055 * c ** (1 / 2.4) - 0.055; };
const hexOf = (c: [number, number, number], k: number) => "#" + c.map((v) => Math.round(255 * toSrgb(1 - (1 - v) * k)).toString(16).padStart(2, "0")).join("");
const blob = (out: Stage, x: number, y: number, z: number, sc = 1, k = 1) => {
  const hl = Math.hypot(SUN.x, SUN.z) || 1, ox = -SUN.x / hl, oz = -SUN.z / hl, rot = Math.atan2(-ox, -oz);
  const el = Math.asin(Math.min(0.99, Math.max(0.1, SUN.y)));
  const len = Math.min(2.4, Math.max(0.5, 1.6 / Math.tan(el))) * sc, h = len + 0.55 * sc, c = 0.3 * h;
  const tc = hexOf(TAIL, k);
  out.fx.push({ key: `blob|shadow|${tc}`, cw: 128, ch: 256, draw: (p) => fxShadow(p, tc), x: x + ox * c, y: y + 0.018, z: z + oz * c, w: 0.72 * sc, h, flat: true, rot });
  const cc = hexOf(CONTACT, k);
  out.fx.push({ key: `blob|contact|${cc}`, cw: 128, ch: 128, draw: (p) => fxContact(p, cc), x: x + ox * 0.03 * sc, y: y + 0.022, z: z + oz * 0.03 * sc, w: 0.52 * sc, h: 0.4 * sc, flat: true, rot });
};
const stand = (cam: CamInfo, out: Stage, i: number, o: Outfit, okey: string, x: number, y: number, z: number, fo: FrontOpts, scale = 1, shadow = true) => {
  out.places.push(person(cam, { i, o, okey }, x, y, z, { side: false, mirror: false }, fo, {}, scale));
  if (shadow) blob(out, x, y, z, scale);
};
const walker = (cam: CamInfo, out: Stage, i: number, o: Outfit, okey: string, x: number, y: number, z: number, t: number, dx: number, dz: number, expr: Expr, extra: Partial<FrontOpts> = {}) => {
  const view = viewOf(cam, x, z, dx, dz), ph = q(((t * 1.9 + hh(i, 5)) % 1 + 1) % 1, 30);
  out.places.push(person(cam, { i, o, okey }, x, y, z, view, { mode: "stroll", phase: ph, expr, blink: lidAt(t, i), ...extra }, { mode: "march", phase: ph, expr, blink: lidAt(t, i), stomp: 0.6, stride: 0.7 * view.fs }));
  blob(out, x, y, z);
};
const runner = (cam: CamInfo, out: Stage, i: number, o: Outfit, okey: string, x: number, z: number, t: number, dx: number, dz: number, expr: Expr, rate = 2.4, extra: Partial<FrontOpts> = {}) => {
  const view = viewOf(cam, x, z, dx, dz), p2 = q(((t * rate + hh(i, 5)) % 1 + 1) % 1, 12);
  out.places.push(person(cam, { i, o, okey }, x, 0, z, view, { mode: "march", phase: p2, expr, blink: lidAt(t, i), tilt: -3, lift: 110, ...extra }, { mode: "march", phase: p2, expr, blink: lidAt(t, i), stomp: 0.9, stride: 1.0 * view.fs }));
  blob(out, x, 0, z);
};
const S = (f: number, a: number) => f >= a - 2;
const fx1 = (out: Stage, key: string, cw: number, ch: number, draw: (p: Pen) => void, x: number, y: number, z: number, w: number, h: number, soft = false, rot = 0) =>
  out.fx.push({ key, cw, ch, draw, x, y, z, w, h, soft, rot });
const pop = (f: number, f0: number) => smooth((f - f0) / 5) * (1 + 0.15 * Math.max(0, 1 - (f - f0) / 8));
// ---- v2 (owner, 11 Nov): labels, sound words and stamps are 2D overlays composited after the render, anchored to a 3D point
// but clamped inside the frame (they were cut off or hidden); props are real 3D objects (blender/sets_hoover.py PROPS).
/** a text label overlay (w = width as a fraction of the frame width) */
const label = (out: Stage, text: string, x: number, y: number, z: number, f: number, f0: number, w = 0.42, bg = "#f2c230") => {
  const k = pop(f, f0); if (k > 0) out.ov.push({ t: "label", text, bg, x, y, z, k, w });
};
/** a comic sound word in a starburst */
const shout = (out: Stage, text: string, f: number, f0: number, _t: number, x: number, y: number, z: number, s = 1.0) => {
  if (f < f0) return; out.ov.push({ t: "shout", text, x, y, z, k: pop(f, f0), w: 0.36 * Math.min(1.4, s), wob: Math.round(((f - f0) / 3) % 2) });
};
const stamp = (out: Stage, text: string, f: number, f0: number, x: number, y: number, z: number, w = 0.3, rot = -8) => {
  if (f < f0) return; const k = 1 + 1.3 * (1 - smooth((f - f0 + 1) / 5)); out.ov.push({ t: "stamp", text, x, y, z, k, w, rot });
};
const flash = (out: Stage, f: number, at: number, x: number, y: number, z: number, s = 0.8) => {
  if (f >= at && f < at + 8) { const u = Math.round(((f - at) / 8) * 8) / 8; fx1(out, `flash|${u}`, 500, 500, (p) => fxFlashStar(p, u), x, y, z, s, s); }
};
const sweat = (out: Stage, f: number, x: number, y: number, z: number, s = 0.3) => { const u = Math.round(((f / 18) % 1) * 6) / 6; fx1(out, `sweat|${u}`, 200, 200, (p) => fxSweat(p, u), x, y, z, s, s); };
const question = (out: Stage, f: number, f0: number, _t: number, x: number, y: number, z: number) => { if (f >= f0) out.ov.push({ t: "q", text: "?", x, y, z, k: smooth((f - f0) / 8), w: 0.12 }); };
/** mouth-only talking (same eyes): smug <-> smug_talk at a syllable rate */
const talk = (f: number) => (Math.floor(f / 5) % 2 ? "smug_talk" : "smug") as Expr;

// ---------------- the cast (1992-93 northern England) ----------------
const DAVE: Outfit = { jacket: "#3f5a3a", pants: "#3a4f7a", boots: "#3a2a22", hat: "cap", cap: "#6a5a44", moustache: "#5a3b2a", hair: "#5a3b2a", skin: "#f5c9a0", build: "stout" };
const REPAIR: Outfit = { jacket: "#2f56a8", pants: "#2f56a8", boots: INK, hat: "cap", cap: "#2f56a8", buttons: "#d9dde0", skin: "#ffe2c2", hair: "#2a1c18" };
const VANMAN: Outfit = { ...REPAIR, moustache: "#3a2a1a", skin: "#ecd0b6" };
const EXEC: Outfit = { jacket: "#2e3240", pants: "#2e3240", boots: INK, hat: "hair", hair: "#9a9590", tie: HRED, buttons: "#d9dde0", skin: "#f5c9a0", build: "stout" };
const EXEC2: Outfit = { jacket: "#3a3d52", pants: "#3a3d52", boots: INK, hat: "hair", hair: "#3a2a1a", tie: "#3f6fb5", skin: "#ecd0b6", moustache: "#3a2a1a" };
const EXEC3: Outfit = { jacket: "#4a3f3a", pants: "#4a3f3a", boots: INK, hat: "hair", hair: "#d9d6cf", tie: "#e8c45a", skin: "#f5c9a0" };
const SALESMAN: Outfit = { jacket: "#e8e4dc", pants: "#2f3242", boots: INK, hat: "hair", hair: "#2a1c18", tie: HRED, skin: "#ffe2c2", buttons: "#c9c3b5" };
const BAILIFF_O: Outfit = { jacket: "#24222c", pants: "#24222c", boots: INK, hat: "bowler", hatCol: "#24222c", tie: "#f4f1ea", skin: "#f5c9a0", moustache: "#6a6a6a" };
const WORKER = (v: number): Outfit => ({ jacket: ["#3f6fb5", "#2f5f6a", "#5a6070"][v % 3], pants: "#2f3242", boots: INK, hat: v % 2 ? "cap" : "hair", cap: "#e8c45a", hair: ["#3a2a1a", "#8a5a32", "#2a1c18"][v % 3], vest: "#f2c230", skin: SKINS[v % 4] });
const SHELL = ["#7b3fb0", "#1fa3a3", "#e2453c", "#2f6fd0", "#e07a32", "#3fae5a"];
const shopper = (v: number): Outfit => {
  const c = SHELL[v % 6], o: Outfit = { jacket: c, pants: v % 3 === 0 ? c : "#3a4f7a", boots: "#f4f1ea", skin: SKINS[v % 4], hair: ["#3a2a1a", "#c8a050", "#8a5a32", "#2a1c18"][v % 4] };
  return v % 2 ? { ...o, hat: "hair", dress: SHELL[(v + 3) % 6] } : { ...o, hat: v % 4 === 0 ? "cap" : "hair", cap: "#f4f1ea", moustache: v % 4 === 2 ? "#4a3426" : undefined };
};

// ---------------- 3D props ----------------
/** yaw that turns a prop's front (+z) toward the camera */
const faceCam = (cam: CamInfo, x: number, z: number) => Math.atan2(cam.pos.x - x, cam.pos.z - z);
const P = (out: Stage, k: string, x: number, y: number, z: number, o: { yaw?: number; s?: number; pitch?: number; roll?: number } = {}) =>
  out.props.push({ k, x, y, z, yaw: o.yaw ?? 0, s: o.s ?? 1, pitch: o.pitch ?? 0, roll: o.roll ?? 0 });
const vac = (out: Stage, x: number, y: number, z: number, yaw = 0, s = 1) => P(out, "vac", x, y, z, { yaw, s });
const carton = (out: Stage, x: number, y: number, z: number, yaw = 0, s = 1, roll = 0) => P(out, "carton", x, y, z, { yaw, s, roll });
const horse = (out: Stage, f: number, t: number, at: number, x = HORSE_WIN[0], y = HORSE_WIN[1], z = HORSE_WIN[2], s = 0.95) => {
  const k = at < 0 ? 1 : smooth((f - at) / 6), bl = lidAt(t, 77) > 0.5 ? 1 : 0, ears = 0.5 + 0.5 * Math.sin(t * 3), chew = Math.round(Math.abs(Math.sin(t * 7)) * 2) / 2;
  if (k > 0) fx1(out, `horse|${bl}|${q(ears, 4)}|${chew}`, 400, 400, (p) => fxHorse(p, bl, q(ears, 4), chew), x - 0.25 * (1 - k), y - 0.35 * (1 - k), z, s, s);
};
/** a 3D desk calendar (front to the camera) counting up the days */
const dayCounter = (cam: CamInfo, out: Stage, f: number, f0: number, f1: number, x: number, y: number, z: number, s = 1.0) => {
  const n = Math.max(1, Math.min(13, 1 + Math.floor(12 * clamp01((f - f0) / (f1 - f0)))));
  const k = pop(f, f0); if (k > 0) P(out, `cal_${n}`, x, y, z, { yaw: faceCam(cam, x, z), s: s * k });
};
const BANG = (out: Stage, f: number, at: number, t: number, x: number, y: number, z: number, s = 1.1, text = "BANG!") => { if (f >= at - 1 && f < at + 26) shout(out, text, f, at - 1, t, x, y, z, s); };

// 1: the hook: Dave standing guard, arms folded and smug, the truck slamming in behind him; the van at his side
const hook = (cam: CamInfo, t: number, f: number, out: Stage) => {
  stand(cam, out, 1, DAVE, "dave", DAVE_H[0], 0, DAVE_H[2], { mode: "stand", expr: f < HOOK_BANG + 4 ? "stern" : "smug", blink: lidAt(t, 1), prop: "crossed", look: -1, tilt: f < 14 ? 3 * Math.sin(f * 0.9) : 0 });
  BANG(out, f, HOOK_BANG, t, 5.0, 2.85, 2.6, 1.15, "CRUNCH!");
  horse(out, f, t, 18);
  label(out, "HOSTAGE", DAVE_H[0] - 0.55, 2.55, DAVE_H[2] + 0.6, f, 30, 0.38, HRED);
};
// 2: a 3D day calendar racing to 13 over the boxed-in van
const days = (cam: CamInfo, t: number, f: number, out: Stage) => {
  stand(cam, out, 1, DAVE, "dave", DAVE_H[0], 0, DAVE_H[2], { mode: "stand", expr: "smug", blink: lidAt(t, 1), prop: "crossed", look: 1 });
  horse(out, f, t, -1);
  dayCounter(cam, out, f, 66, 98, DAVE_H[0] + 0.2, 3.1, DAVE_H[2] - 0.6, 1.6);
};
// 3: Dave pointing at his truck; along its flank the horse pops out of the window
const blocked = (cam: CamInfo, t: number, f: number, out: Stage) => {
  stand(cam, out, 1, DAVE, "dave", DAVE_H[0], 0, DAVE_H[2], { mode: "stand", expr: S(f, 161) ? "grin" : "smug", blink: lidAt(t, 1), prop: f < 140 ? "point" : "crossed", look: -1 });
  horse(out, f, t, 158);
  if (S(f, 166)) shout(out, "NEIGH!", f, 166, t, HORSE_WIN[0] - 0.75, HORSE_WIN[1] + 0.75, HORSE_WIN[2] - 0.15, 0.85);
  stand(cam, out, 31, shopper(3), "neigh1", 0.4, 0, 6.1, { mode: "stand", expr: "shock", blink: lidAt(t, 31), look: 1 }, 1, false);
  stand(cam, out, 32, shopper(2), "neigh2", -0.6, 0, 6.0, { mode: "stand", expr: "laugh", blink: lidAt(t, 32), look: 1, prop: "point" }, 1, false);
};
// 4: Dave looking up; a 3D jumbo crossing the sky, nose first (flies -x = screen right for this view)
export const plane4X = (f: number) => 34 - 40 * ((f - 205) / FPS);
const why = (cam: CamInfo, t: number, f: number, out: Stage) => {
  stand(cam, out, 1, DAVE, "dave", DAVE_H[0], 0, DAVE_H[2], { mode: "stand", expr: S(f, 232) ? "grin" : "nervous", blink: lidAt(t, 1), look: 0, headTilt: -12, prop: S(f, 232) ? "point" : null });
  question(out, f, 186, t, DAVE_H[0] + 0.35, 2.35, DAVE_H[2] - 0.1);
  if (f >= 205) P(out, "plane", plane4X(f), 42, 46, { yaw: -Math.PI / 2, s: 0.8, roll: 0.06 });
  if (S(f, 228)) label(out, "FREE FLIGHT?", plane4X(f), 34, 46, f, 228, 0.4, "#ffffff");
};
// 5: the 1992 shop: the deal; the salesman holds up a real vacuum, two real tickets in his other hand
const shopFloor = (cam: CamInfo, t: number, f: number, out: Stage, n = 6) => {
  for (let i = 0; i < n; i++) {
    const x = SHOP.x + [-5.2, -2.9, 3.4][i % 3] + 0.4 * hh(i, 2), z = -3.5 - Math.floor(i / 3) * 6.5 - 1.2 * hh(i, 3);
    stand(cam, out, 40 + i, shopper(i), `shop${i}`, x, 0, z, { mode: "stand", expr: (["grin", "shock", "smile", "laugh", "grin", "nervous"] as Expr[])[i % 6], blink: lidAt(t, 40 + i), look: i % 2 ? 1 : -1, prop: i % 3 === 0 ? "point" : null });
  }
};
const deal = (cam: CamInfo, t: number, f: number, out: Stage) => {
  if (f < 345) label(out, "BRITAIN, 1992", SHOP.x + 0.3, 3.2, 0.6, f, 262, 0.5, "#ffffff");
  shopFloor(cam, t, f, out);
  stand(cam, out, 50, SALESMAN, "sales", SALES[0], 0, SALES[2], { mode: "stand", expr: S(f, 428) ? "grin" : "smile", blink: lidAt(t, 50, [428 / FPS]), prop: S(f, 376) ? "point" : "palm", look: 1 });
  vac(out, SALES[0] + 0.6, 1.06, SALES[2] + 0.55, faceCam(cam, SALES[0] + 0.6, SALES[2] + 0.55), 0.95);
  if (S(f, 343)) label(out, "SPEND £100", SALES[0] - 0.7, 2.25, SALES[2] + 0.6, f, 343, 0.4, "#fff4a8");
  for (let k = 0; k < 2; k++) { const at = 376 + k * 6; if (S(f, at)) { const u = pop(f, at), x = SALES[0] - 0.55 + k * 0.48, z = SALES[2] + 0.85;
    P(out, k ? "ticket_orl" : "ticket_ny", x, 1.72 + 0.12 * k + 0.03 * Math.sin(t * 5 + k), z, { yaw: faceCam(cam, x, z), s: 1.3 * u, roll: k ? -0.12 : 0.1 }); } }
  if (S(f, 428)) label(out, "TO AMERICA!", SALES[0] + 0.1, 2.85, SALES[2] + 0.7, f, 428, 0.44, HRED);
};
// 6: the 3D balance scale: vacuum £119 against two tickets £600, slamming down on "six hundred"
const SCL_P: V3 = [SCALE_AT[0], 2.0, SCALE_AT[2]], SCL_L = 0.62;
const scale = (cam: CamInfo, t: number, f: number, out: Stage) => {
  shopFloor(cam, t, f, out, 3);
  stand(cam, out, 50, SALESMAN, "sales", SALES[0] - 0.4, 0, SALES[2], { mode: "stand", expr: S(f, 568) ? "shock" : "nervous", blink: lidAt(t, 50, [568 / FPS]), look: 1, prop: S(f, 568) ? "facepalm" : null });
  const tl = f < 541 ? -0.15 : f < 566 ? 0.15 * smooth((f - 541) / 20) : 0.15 + 0.85 * clamp01((f - 566) / 3) - 0.08 * Math.sin(Math.max(0, f - 569) * 0.9) * Math.exp(-Math.max(0, f - 569) / 6);
  const a = 0.3 * tl; // beam angle: right side (tickets) down for a > 0
  P(out, "scale_base", SCALE_AT[0], 1.06, SCALE_AT[2]);
  P(out, "scale_beam", SCL_P[0], SCL_P[1], SCL_P[2], { roll: a });
  P(out, "scale_panL", SCL_P[0] - SCL_L * Math.cos(a), SCL_P[1] + SCL_L * Math.sin(a), SCL_P[2]);
  P(out, "scale_panR", SCL_P[0] + SCL_L * Math.cos(a), SCL_P[1] - SCL_L * Math.sin(a), SCL_P[2]);
  if (S(f, 568)) { BANG(out, f, 568, t, SCALE_AT[0] + 0.6, 2.4, SCALE_AT[2] + 0.3, 0.9, "THUD!"); sweat(out, f, SALES[0] - 0.4, 2.0, SALES[2] + 0.1); }
};
// 7: the man from Hoover expecting 50,000; the stampede of 300,000
const crowd = (cam: CamInfo, t: number, f: number, out: Stage) => {
  stand(cam, out, 60, EXEC, "exec", DOOR_EXT[0], 0, DOOR_EXT[2], { mode: "stand", expr: S(f, 680) ? "shock" : "smug", blink: lidAt(t, 60, [680 / FPS]), prop: "clipboard", look: 1, tilt: S(f, 680) ? 8 * Math.sin(t * 14) : 0 });
  label(out, "EXPECTED: 50,000", DOOR_EXT[0] - 0.2, 2.35, DOOR_EXT[2] + 0.4, f, 614, 0.5, "#ffffff");
  if (S(f, 680)) label(out, "GOT: 300,000!", DOOR_EXT[0] + 0.1, 2.85, DOOR_EXT[2] + 0.5, f, 682, 0.56, HRED);
  for (let i = 0; i < 12; i++) {
    const rush = f >= 676, s = Math.max(0, (f - 676) / FPS), x0 = SHOP.x + 3.0 + i * 1.05, z = 2.3 + 0.7 * (i % 2) + 0.2 * hh(i, 4);
    const x = rush ? Math.max(SHOP.x + 0.2 + 0.3 * (i % 3), x0 - 6.5 * s - 0.4 * i * s) : x0;
    if (rush && x > SHOP.x + 0.6) runner(cam, out, 70 + i, shopper(i + 1), `q${i}`, x, z, t, -1, 0, (["grin", "laugh", "shock"] as Expr[])[i % 3], 3.0, { lift: 150, tilt: -10 });
    else if (!rush) stand(cam, out, 70 + i, shopper(i + 1), `q${i}`, x, 0, z, { mode: "stand", expr: "grin", blink: lidAt(t, 70 + i), look: -1, prop: i % 4 === 1 ? "cash" : null });
  }
};
// 8: a shopper walking out with a tower of real cartons, his wife with two more
const boxes = (cam: CamInfo, t: number, f: number, out: Stage) => {
  const z = boxManZ(f), yw = faceCam(cam, SHOP.x, z);
  walker(cam, out, 80, shopper(4), "boxman", SHOP.x - 0.1, 0, z, t, 0, 1, "grin");
  carton(out, SHOP.x - 0.1, 0.42, z + 0.35, yw, 0.8, 0.03 * Math.sin(t * 3)); carton(out, SHOP.x - 0.08, 0.92, z + 0.33, yw + 0.1, 0.8, -0.04 * Math.sin(t * 3));
  carton(out, SHOP.x - 0.08, 1.96, z + 0.02, yw - 0.15, 0.75, 0.08 * Math.sin(t * 4));
  walker(cam, out, 81, shopper(5), "boxwife", SHOP.x + 0.9, 0, z - 0.9, t + 0.3, 0, 1, "laugh");
  carton(out, SHOP.x + 0.9, 0.45, z - 0.55, yw, 0.78); carton(out, SHOP.x + 0.9, 0.94, z - 0.57, yw + 0.12, 0.78);
  if (S(f, 760)) label(out, "DON'T NEED ONE", SHOP.x + 0.4, 3.0, z, f, 760, 0.5, "#ffffff");
  for (let i = 0; i < 3; i++) stand(cam, out, 82 + i, shopper(i + 7), `pass${i}`, SHOP.x - 2.4 - i * 1.2, 0, 1.4 + i * 0.9, { mode: "stand", expr: "shock", blink: lidAt(t, 82 + i), look: 1 });
};
// 9: a real newspaper of small ads filling up; the pavement lined with boxed Hoovers FOR SALE
const ads = (cam: CamInfo, t: number, f: number, out: Stage) => {
  if (f < 852) {
    stand(cam, out, 90, shopper(6), "reader", PAPER[0], 0, PAPER[2], { mode: "stand", expr: S(f, 828) ? "laugh" : "shock", blink: lidAt(t, 90), look: 0 });
    const n = [0, 3, 6, 9, 12, 15, 18][Math.min(6, Math.floor(7 * clamp01((f - 796) / 50)))];
    P(out, `ads_${n}`, PAPER[0] + 0.05, 1.02, PAPER[2] + 0.42, { yaw: faceCam(cam, PAPER[0], PAPER[2] + 0.42), pitch: -0.08 });
  } else {
    for (let i = 0; i < 16; i++) carton(out, -4 - i * 1.0, 0.12, ROW_Z + 0.1 * hh(i, 3), Math.PI + 0.3 * (hh(i, 4) - 0.5), 0.9);
    label(out, "STILL IN THE BOX!", -9.5, 1.3, ROW_Z, f, 858, 0.58, HRED);
    stand(cam, out, 91, shopper(8), "seller", -14.5, 0.12, ROW_Z + 0.4, { mode: "stand", expr: "grin", blink: lidAt(t, 91), look: 1, prop: "palm" });
  }
};
// 10: real vacuums on the conveyor, yawning workers, the wall clock spinning, the shift board crossed out
const factory = (cam: CamInfo, t: number, f: number, out: Stage) => {
  for (let k = 0; k < 14; k++) { const z = -28 + ((k * 2.0 + 3.2 * ((f - 910) / FPS)) % 30); vac(out, FACT.x, FACT.belt, z, 0, 0.9); }
  for (let i = 0; i < 6; i++) {
    const sd = i % 2 ? 1 : -1, z = 1.5 - Math.floor(i / 2) * 5.5;
    stand(cam, out, 100 + i, WORKER(i), `wk${i}`, FACT.x + sd * 1.75, 0, z, { mode: "stand", expr: (["dazed", "pained", "nervous"] as Expr[])[i % 3], blink: i % 3 === 0 ? 0.6 : lidAt(t, 100 + i), look: -sd, tilt: 4 * Math.sin(t * 2 + i) });
  }
  const ct = ((f - 910) / 30) % 1, CX = FACT.x - 2.6, CY = 4.2, CZ = -14;
  P(out, "clock", CX, CY, CZ, { s: 2.4 }); P(out, "hand_l", CX, CY, CZ + 0.08, { s: 2.4, roll: -ct * Math.PI * 24 }); P(out, "hand_s", CX, CY, CZ + 0.07, { s: 2.4, roll: -ct * Math.PI * 2 });
  const kk = Math.min(7, Math.floor(7 * clamp01((f - 914) / 26)));
  P(out, kk === 7 && f >= 942 ? "week_7s" : `week_${kk}`, FACT.x + 1.6, 3.4, -10, { s: 2.1 });
};
// 11: the boss stamping real claim forms REJECTED; a 14-day calendar; a ticket with the flight HE chose
const office = (cam: CamInfo, t: number, f: number, out: Stage) => {
  const stamping = f >= 990 && f < 1060, hit = stamping && (f - 990) % 14 < 4;
  stand(cam, out, 110, EXEC, "exec", EXEC_DESK[0], 0, EXEC_DESK[2], { mode: "stand", expr: S(f, 1071) ? "laugh" : hit ? "grin" : "smug", blink: lidAt(t, 110), look: 0, prop: S(f, 1071) ? "point" : null, tilt: hit ? 4 : 0 });
  const nf = Math.min(5, Math.max(0, Math.floor((f - 990) / 14) + 1));
  for (let k = 0; k < 5; k++) P(out, k < nf ? "form_rej" : "form", EXEC_DESK[0] - 0.62 + k * 0.31, 0.8, OFFICE.deskZ + 0.22 - 0.03 * (k % 2), { pitch: -1.35, roll: (k % 2 ? 0.12 : -0.15), yaw: 0 });
  if (hit) flash(out, f, 990 + 14 * Math.floor((f - 990) / 14), EXEC_DESK[0] - 0.5 + 0.3 * Math.min(4, Math.floor((f - 990) / 14)), 1.0, OFFICE.deskZ + 0.35, 0.45);
  if (S(f, 994)) stamp(out, "REJECTED", f, 994, EXEC_DESK[0] + 0.35, 1.9, OFFICE.deskZ + 0.1, 0.42);
  if (S(f, 1004)) { const k = pop(f, 1004); P(out, "cal_14", EXEC_DESK[0] - 1.05, 1.95, OFFICE.deskZ - 0.3, { yaw: faceCam(cam, EXEC_DESK[0] - 1.05, OFFICE.deskZ - 0.3), s: 1.2 * k }); }
  if (S(f, 1071)) { const u = pop(f, 1071), x = EXEC_DESK[0] + 0.65, z = OFFICE.deskZ + 0.15; P(out, "ticket_ours", x, 1.4, z, { yaw: faceCam(cam, x, z), s: 1.5 * u, roll: -0.08 }); }
};
// 12: Dave proudly patting his new Hoover washing machine, a free-flight ticket dreamed above it
const bought = (cam: CamInfo, t: number, f: number, out: Stage) => {
  stand(cam, out, 120, DAVE, "dave", DAVE_K[0], 0, DAVE_K[2], { mode: "stand", expr: S(f, 1179) ? "grin" : "smile", blink: lidAt(t, 120), look: 1, prop: S(f, 1162) ? "palm" : null });
  label(out, "WORKINGTON", WASHER.x + 0.05, 1.75, WASHER.z + 0.45, f, 1116, 0.42, "#ffffff");
  label(out, "DAVE DIXON", DAVE_K[0] + 0.05, 2.2, DAVE_K[2] + 0.1, f, 1146, 0.4, "#f2c230");
  if (S(f, 1185)) { const u = pop(f, 1185), x = WASHER.x + 0.1, z = WASHER.z + 0.5; P(out, "ticket_wus", x, 1.5 + 0.05 * Math.sin(t * 4), z, { yaw: faceCam(cam, x, z), s: 1.2 * u, roll: 0.1 }); }
};
// 13: waiting by the front door on a real suitcase, the calendar flipping through the months, no tickets
const waiting = (cam: CamInfo, t: number, f: number, out: Stage) => {
  stand(cam, out, 121, DAVE, "dave", DOOR_K[0], 0.38, DOOR_K[2], { mode: "sit", expr: S(f, 1250) ? "stern" : S(f, 1236) ? "nervous" : "smile", blink: lidAt(t, 121, [1250 / FPS]), look: -1 }, 1, false);
  P(out, "suitcase", DOOR_K[0], 0, DOOR_K[2] + 0.05, { yaw: faceCam(cam, DOOR_K[0], DOOR_K[2]) });
  const M = ["JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC", "JAN", "FEB", "MAR"], m = M[Math.min(M.length - 1, Math.floor(clamp01((f - 1222) / 40) * M.length))];
  P(out, `cal_${m}`, FRONT_DOOR.x + 0.06, 1.75, FRONT_DOOR.z - 0.95, { yaw: Math.PI / 2, s: 1.0 });
  if (S(f, 1250)) label(out, "NO TICKETS", DOOR_K[0] + 0.1, 1.7, DOOR_K[2] + 0.5, f, 1250, 0.42, HRED);
};
// 14: the machine shaking itself to bits; KLONK, real foam everywhere, Dave jumping back
const broke = (cam: CamInfo, t: number, f: number, out: Stage) => {
  const jump = f >= 1303 && f < 1318 ? 0.18 * Math.sin(((f - 1303) / 15) * Math.PI) : 0;
  stand(cam, out, 122, DAVE, "dave", DAVE_K[0] - 0.2, jump, DAVE_K[2] + 0.2, { mode: "stand", expr: S(f, 1303) ? "shock" : "nervous", blink: lidAt(t, 122, [1303 / FPS]), look: 1, prop: S(f, 1303) ? "facepalm" : null, tilt: S(f, 1303) ? -8 : 0 });
  if (S(f, 1303)) { const u = clamp01((f - 1303) / 14); for (let k = 0; k < 3; k++) P(out, "suds", WASHER.x - 0.25 + 0.3 * k, 0.2 + 0.15 * k * u, WASHER.z + 0.45 + 0.12 * k, { s: 0.25 + 0.95 * u * (1 - 0.2 * k), yaw: k }); }
  BANG(out, f, 1303, t, WASHER.x + 0.35, 1.75, WASHER.z + 0.5, 0.9, "KLONK!");
  if (f < 1303) sweat(out, f, WASHER.x, 1.1, WASHER.z + 0.35, 0.35);
};
// 15: the repairman delivers his verdict (mouth-only talking); Dave's face for "idiot"
const repair = (cam: CamInfo, t: number, f: number, out: Stage) => {
  const talking = f >= 1360 && f < 1520;
  stand(cam, out, 123, DAVE, "dave", DAVE_K[0], 0, DAVE_K[2], { mode: "stand", expr: S(f, 1513) ? "shock" : S(f, 1430) ? "stern" : "nervous", blink: lidAt(t, 123, [1430 / FPS, 1513 / FPS]), look: 1, prop: f < 1360 ? "palm" : null });
  stand(cam, out, 124, REPAIR, "repair", REPAIR_K[0], 0, REPAIR_K[2], { mode: "stand", expr: talking ? talk(f) : "smug", blink: lidAt(t, 124), look: -1, prop: f > 1470 ? "point" : f > 1380 ? "crossed" : null });
  for (let k = 0; k < 3; k++) P(out, "suds", WASHER.x - 0.2 + 0.3 * k, 0.15, WASHER.z + 0.55 + 0.1 * k, { s: 1.0 - 0.15 * k, yaw: k });
  if (S(f, 1513)) flash(out, f, 1513, DAVE_K[0] + 0.3, 1.85, DAVE_K[2] + 0.2, 0.55);
};
// 16: Dave at his front door watching the Hoover van roll up his drive
const parked = (cam: CamInfo, t: number, f: number, out: Stage) => {
  stand(cam, out, 130, DAVE, "dave", DAVE_DOOR[0], 0, DAVE_DOOR[2], { mode: "stand", expr: S(f, 1574) ? "smug" : "stern", blink: lidAt(t, 130), look: 1, prop: ["scratch", 0.5 + 0.5 * Math.sin(t * 8)] });
};
// 17: the truck reversing across the drive mouth; the van man staring; the horse
const block = (cam: CamInfo, t: number, f: number, out: Stage) => {
  stand(cam, out, 131, VANMAN, "vanman", 4.0, 0, 5.0, { mode: "stand", expr: f >= BLOCK_BANG ? "shock" : "neutral", blink: lidAt(t, 131, [BLOCK_BANG / FPS]), look: 1, prop: f >= BLOCK_BANG ? "facepalm" : "clipboard" });
  BANG(out, f, BLOCK_BANG, t, TRUCK_PARK.x + 2.2, 2.9, TRUCK_PARK.z - 1.4, 1.3, "CRUNCH!");
  if (f >= BLOCK_BANG + 6) stand(cam, out, 1, DAVE, "dave", 2.6, 0, 6.2, { mode: "stand", expr: "smug", blink: lidAt(t, 1), look: -1, prop: "crossed" });
  horse(out, f, t, 1648);
  if (S(f, 1652)) shout(out, "NEIGH!", f, 1652, t, HORSE_WIN[0] - 0.7, HORSE_WIN[1] + 0.7, HORSE_WIN[2] - 0.15, 0.8);
};
// 18: thirteen days later: the High Court order (real paper); the gavel; the truck pulls away, the van shoots out backwards
const court = (cam: CamInfo, t: number, f: number, out: Stage) => {
  const bz = BAILIFF[2] + 2.0 * (1 - smooth((f - 1675) / 30));
  stand(cam, out, 140, BAILIFF_O, "bailiff", BAILIFF[0], 0, bz, { mode: "stand", expr: "stern", blink: lidAt(t, 140), look: -1, prop: "paper" });
  if (S(f, 1709)) { const u = pop(f, 1709), x = BAILIFF[0] - 0.42, z = bz + 0.35; P(out, "order", x, 1.55, z, { yaw: faceCam(cam, x, z), s: 1.3 * u, roll: 0.06 }); }
  if (f >= 1712 && f < 1742) { const a = clamp01((f - 1716) / 6); P(out, "gavel", BAILIFF[0] + 0.55, 1.3, bz + 0.3, { yaw: faceCam(cam, BAILIFF[0], bz), pitch: 0, roll: 1.0 - 1.3 * a, s: 1.6 }); }
  BANG(out, f, 1722, t, BAILIFF[0] + 0.5, 2.85, bz, 0.8, "BANG!");
  dayCounter(cam, out, f, 1675, 1676, BAILIFF[0] - 1.6, 2.6, bz - 0.5, 1.2);
  stand(cam, out, 1, DAVE, "dave", 1.2, 0.05, 4.8, { mode: "stand", expr: S(f, 1722) ? "pained" : "stern", blink: lidAt(t, 1, [1722 / FPS]), look: 1, prop: "crossed" });
  if (f >= 1739) label(out, "FREE!", VAN_PARK.x + 0.4, 3.0, (vanAt(18, f)?.z ?? 0) + 0.5, f, 1741, 0.3, "#9be07a");
};
// 19: three bosses walking out with real office boxes, FIRED stamped on each
const fired = (cam: CamInfo, t: number, f: number, out: Stage) => {
  const z = firedZ(f);
  ([[EXEC, "exec", -0.85, 1780], [EXEC2, "exec2", 0.0, 1796], [EXEC3, "exec3", 0.85, 1806]] as [Outfit, string, number, number][]).forEach(([o, k, dx, at], i) => {
    const zz = z - 0.5 * Math.abs(dx) * 0.6;
    walker(cam, out, 150 + i, o, k, OFFICE.x + dx, 0, zz, t + i * 0.2, 0, 1, S(f, at) ? "pained" : "nervous");
    P(out, "obox", OFFICE.x + dx, 0.82, zz + 0.32, { yaw: faceCam(cam, OFFICE.x + dx, zz) });
    stamp(out, "FIRED", f, at, OFFICE.x + dx, 2.15, zz + 0.35, 0.26, -12 + 8 * i);
  });
};
// 20: the 3D jumbo over the rooftops (flies +x = screen right here), 220,000 on the tag
const flew = (cam: CamInfo, t: number, f: number, out: Stage) => {
  const x = planeX(f);
  P(out, "plane", x, 16, -12, { yaw: Math.PI / 2, s: 0.75, roll: -0.05 });
  label(out, "220,000 FLEW FREE", x, 10.5, -12, f, 1834, 0.62, "#f2c230");
  for (let i = 0; i < 4; i++) stand(cam, out, 160 + i, shopper(i + 2), `look${i}`, -2.5 + i * 1.6, 0.12, 7.2 + 0.4 * (i % 2), { mode: "stand", expr: (["grin", "laugh", "shock", "grin"] as Expr[])[i], blink: lidAt(t, 160 + i), look: 1, headTilt: -14, wave: i % 2 ? 0.6 + 0.4 * Math.sin(t * 10 + i) : undefined });
};
// 21: a real SOLD board slammed over the HOOVER sign at the end of the factory
const sold = (cam: CamInfo, t: number, f: number, out: Stage) => {
  if (S(f, 1888)) { const k = 1 + 0.6 * (1 - smooth((f - 1886) / 6)); P(out, "sold", FACT.x, 3.35, -31.4, { s: 5.2 * k }); }
  if (S(f, 1901)) label(out, "SOLD TO CANDY. YES, CANDY.", FACT.x, 2.6, -30.6, f, 1903, 0.72, "#ffffff");
  for (let i = 0; i < 4; i++) stand(cam, out, 170 + i, WORKER(i), `wk${i}`, FACT.x - 2.4 + i * 1.6, 0, -27.5 - (i % 2), { mode: "stand", expr: (["shock", "nervous", "shock", "pained"] as Expr[])[i], blink: lidAt(t, 170 + i), look: 0, prop: i === 1 ? "hatInHand" : null });
  BANG(out, f, 1888, t, FACT.x + 2.6, 7.4, -30.8, 1.3, "BAM!");
};
// 22: Dave with his tea in a real deckchair, the van boxed in behind, the horse; a look to camera on "idiot"
const idiot = (cam: CamInfo, t: number, f: number, out: Stage) => {
  stand(cam, out, 1, DAVE, "dave", TEA[0], 0.42, TEA[2], { mode: "sit", expr: S(f, 1977) ? "grin" : S(f, 1958) ? "smug" : "smile_closed", blink: lidAt(t, 1, [1958 / FPS]), look: S(f, 1958) ? 0 : -1 }, 1, false);
  const yw = faceCam(cam, TEA[0], TEA[2]);
  P(out, "chair", TEA[0] - 0.4 * Math.sin(yw), 0, TEA[2] - 0.4 * Math.cos(yw), { yaw: yw });
  P(out, "mug", TEA[0] + 0.33, 0.95, TEA[2] + 0.2 * Math.cos(yw), { yaw: yw });
  horse(out, f, t, -1);
  dayCounter(cam, out, f, 1940, 1941, TEA[0] - 0.9, 2.25, TEA[2] + 0.5, 1.0);
};

/** everything with a face, every 2D effect, every 3D prop and every overlay in shot `id` at time t */
export const stage = (id: number, t: number, f: number, cam: CamInfo): Stage => {
  const out: Stage = { places: [], fx: [], props: [], ov: [] };
  const s = SHOTS[id - 1];
  if (cam.sun) SUN.copy(cam.sun).normalize();
  const fn: Record<string, (c: CamInfo, t: number, f: number, o: Stage) => void> = {
    hook, days, blocked, why, deal, scale, crowd, boxes, ads, factory, office, bought, waiting, broke, repair, parked, block, court, fired, flew, sold, idiot,
  };
  fn[s.crowd]?.(cam, t, f, out);
  return out;
};
export { FPS, clamp01, tmp, truckAt, fxRunLines };
