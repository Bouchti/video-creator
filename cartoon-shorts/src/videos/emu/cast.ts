import type { LightName } from "./lights";
// The Emu War cast as lit flat sprites in the 3D world. Each frame every character asks for a drawing (a key + a draw
// call); the pool keeps one canvas per distinct drawing, so emus in step share canvases. People are yaw-only
// billboards on the 600 x 1000 card, emus on the WIDE 1000 x 1000 card; both are shaded by cardShade() and stand on a
// soft multiply contact blob. Effects are unlit cards. Everything lives on the NOINK layer (no world ink on quads).
import * as THREE from "three";
import {
  Pen, bodyFront, bodySide, fxShadow, fxContact, fxBurst, fxStars, fxPuff, fxQuestion, fxPaper,
  MAJOR, gunner, farmer, MINISTER, CAMERAMAN, mp, Outfit, Expr, FrontOpts, SideOpts, Prop,
} from "./toon";
import { emuSide, emuFront, EmuOpts, fxFeathers, fxSmoke, fxExclaim, fxHearts, fxTarget, fxCrumbs, fxCase, fxCount } from "./emudraw";
import {
  FPS, SHOTS, clamp01, smooth, HOOK_GUN, HOOK_GUNNER, HOOK_LOADER, HOOK_MAJOR, WON_EMU, FENCE_FARMER, MINISTER_AT, FARMERS_AT, LINE, LINE_Z,
  CAMERA_AT, POSE_MAJOR, DAM_GUN, DAM_GUNNER, DAM_LOADER, DAM_MAJOR, FIRE_A, JAM_AT, firing, truckAt, TRUCK_PARK, EMU_V, BURST_AT, NGROUP,
  MP_ASK, BRASS, BRASS_H, DESK_AT, PARADE_MAJOR, PARADE_Z, paradeX, LEAD_STOP, LOOKOUT, TEN_EMU, V3,
} from "./story";
import { CAMP, DAM, CHASE, BURST, PARL, FENCE_Z } from "./places";
import { BENCH_ROWS } from "./outback";
import { LIGHTS } from "./lights";
import { NOINK } from "./ink";
import { cardShade, blobMaterial, CARD_K } from "./cardshade";

// ---------------- canvas pool ----------------
type Entry = { cv: HTMLCanvasElement; tex: THREE.CanvasTexture; w: number; h: number };
export type Req = { key: string; w: number; h: number; k: number; draw: (p: Pen) => void; tex?: THREE.CanvasTexture };
const makeEntry = (w: number, h: number): Entry => {
  const cv = document.createElement("canvas");
  cv.width = w; cv.height = h;
  const tex = new THREE.CanvasTexture(cv);
  tex.colorSpace = THREE.SRGBColorSpace; tex.anisotropy = 8;
  return { cv, tex, w, h };
};
export class Pool {
  private live = new Map<string, Entry>();
  private free: Entry[] = [];
  private reqs: Req[] = [];
  req(key: string, w: number, h: number, k: number, draw: (p: Pen) => void) {
    const r: Req = { key: `${w}x${h}|${key}`, w, h, k, draw };
    this.reqs.push(r);
    return r;
  }
  flush() {
    const want = new Map<string, Req[]>();
    for (const r of this.reqs) { const l = want.get(r.key); if (l) l.push(r); else want.set(r.key, [r]); }
    for (const [key, e] of this.live) if (!want.has(key)) { this.live.delete(key); this.free.push(e); }
    for (const [key, rs] of want) {
      let e = this.live.get(key);
      if (!e) {
        const r = rs[0], i = this.free.findIndex((x) => x.w === r.w && x.h === r.h);
        e = i >= 0 ? this.free.splice(i, 1)[0] : makeEntry(r.w, r.h);
        const g = e.cv.getContext("2d")!;
        g.setTransform(1, 0, 0, 1, 0, 0); g.clearRect(0, 0, e.w, e.h); g.setTransform(r.k, 0, 0, r.k, 0, 0);
        r.draw(new Pen(g));
        e.tex.needsUpdate = true;
        this.live.set(key, e);
      }
      for (const r of rs) r.tex = e.tex;
    }
    this.reqs = [];
  }
}

// ---------------- sprite meshes ----------------
const blank = (() => { const c = document.createElement("canvas"); c.width = c.height = 2; return new THREE.CanvasTexture(c); })();
export const SU = 0.00216; // metres per design unit: 1000 units = 2.16 m
export const SU_SWING = 2.3 / 1830; // swing canvas: rope of 1830 units = 2.3 m
/** the emu card: 1000 x 1000 design units, soles at 975 */
export const WIDE = (() => { const g = new THREE.PlaneGeometry(1000 * SU, 1000 * SU); g.translate(0, (975 - 500) * SU, 0); return g; })();
export const BODY = (() => { const g = new THREE.PlaneGeometry(600 * SU, 1000 * SU); g.translate(0, (975 - 500) * SU, 0); return g; })();
const CARD = new THREE.PlaneGeometry(1, 1);
/** world roots that hold actors (to find the scene's sun when world.ts does not pass it) */
const ROOTS = new Set<THREE.Object3D>();

/** lit flat character: cardShade() material, receives shadows (dims to the bright floor only), casts its silhouette
 *  when world.ts says so (golden). Drawn after the contact blobs (renderOrder 1). */
export class Actor {
  mesh: THREE.Mesh; mat: THREE.MeshLambertMaterial; dmat: THREE.MeshDepthMaterial; r: Req | null = null;
  constructor(parent: THREE.Object3D, geo: THREE.BufferGeometry = BODY) {
    this.mat = cardShade(new THREE.MeshLambertMaterial({ map: blank, alphaTest: 0.5, side: THREE.DoubleSide }));
    this.mat.alphaToCoverage = false; // A2C + MSAA left 1 px sky-depth seams on blurred far cards (POST)
    this.dmat = new THREE.MeshDepthMaterial({ depthPacking: THREE.RGBADepthPacking, map: blank, alphaTest: 0.5, side: THREE.DoubleSide });
    this.mesh = new THREE.Mesh(geo, this.mat);
    this.mesh.customDepthMaterial = this.dmat;
    // rim width is in output pixels: tell the card shader the render height (1920 = 1080 x 1920 frame)
    this.mesh.onBeforeRender = (r) => { const rt = r.getRenderTarget(); CARD_K.uPx.value = (rt ? rt.height : r.domElement.height) / 1920; };
    this.mesh.castShadow = false; this.mesh.receiveShadow = true; this.mesh.visible = false;
    this.mesh.rotation.order = "YXZ"; this.mesh.renderOrder = 1; this.mesh.layers.set(NOINK);
    parent.add(this.mesh);
    ROOTS.add(parent);
  }
  bind() { const t = this.r?.tex; if (t) { this.mat.map = t; this.dmat.map = t; } }
}
/** unlit effect card: hard cut-out (ink drawings), soft see-through (dust, mist) or a multiply ground blob */
export class Fx {
  mesh: THREE.Mesh; mat: THREE.MeshBasicMaterial; soft: THREE.MeshBasicMaterial; blob: THREE.MeshBasicMaterial; r: Req | null = null;
  constructor(parent: THREE.Object3D) {
    this.mat = new THREE.MeshBasicMaterial({ map: blank, alphaTest: 0.5, side: THREE.DoubleSide });
    this.mat.alphaToCoverage = false; // A2C + MSAA left 1 px sky-depth seams on blurred far cards (POST)
    this.soft = new THREE.MeshBasicMaterial({ map: blank, transparent: true, depthWrite: false, side: THREE.DoubleSide });
    this.blob = blobMaterial(blank);
    this.mesh = new THREE.Mesh(CARD, this.mat);
    this.mesh.visible = false; this.mesh.layers.set(NOINK);
    parent.add(this.mesh);
  }
  use(soft: boolean) { this.mesh.material = soft ? this.soft : this.mat; }
  bind() {
    const t = this.r?.tex;
    if (!t) return;
    if (this.r!.key.includes("|blob|")) {
      // no mipmaps: at grazing views the mip chain averages the blob with its white surround and it fades out
      if (t.generateMipmaps) { t.generateMipmaps = false; t.minFilter = THREE.LinearFilter; t.needsUpdate = true; }
      this.blob.map = t; this.mesh.material = this.blob; this.mesh.renderOrder = 0.5;
    }
    else { this.mat.map = t; this.soft.map = t; this.mesh.renderOrder = 0; }
  }
}

// ---------------- placements ----------------
export type Place = {
  key: string; draw: (p: Pen) => void; x: number; y: number; z: number;
  scale?: number; mirror?: boolean; yaw?: number; geo?: "body" | "swing" | "wide"; roll?: number; size?: [number, number, number];
};
export type FxPlace = { key: string; cw: number; ch: number; draw: (p: Pen) => void; x: number; y: number; z: number; w: number; h: number; flat?: boolean; rot?: number; soft?: boolean };
/** sun = world direction TOWARD the sun (optional: when absent the scene's shadow-casting light is used) */
export type CamInfo = { pos: THREE.Vector3; right: THREE.Vector3; sun?: THREE.Vector3 };

const hh = (i: number, s = 0) => { const v = Math.sin(i * 127.1 + s * 311.7) * 43758.5453; return v - Math.floor(v); };
const q = (v: number, n = 120) => Math.round(v * n) / n;
const vOf = (i: number) => (i * 7 + (i >> 2)) % 4;
/** head-shape seed: 7 shapes, so marching soldiers in step still share canvases */
const seedOf = (i: number) => ((i * 5 + 3) % 7) + 1;
/** drawing resolution by distance: [canvas w, h, scale from the 600 x 1000 design]; sized for the 1440 x 2560 final */
const tier = (d: number): [number, number, number] =>
  d < 3.2 ? [1800, 3000, 3.0] : d < 6.5 ? [1080, 1800, 1.8] : d < 16 ? [480, 800, 0.8] : [240, 400, 0.4];

// ---------------- light ----------------
const SUN = new THREE.Vector3(0.5, 0.75, -0.4).normalize();
const tmp = new THREE.Vector3();
let LNAME: LightName = "day";
const sunOf = (root: THREE.Object3D) => {
  let s: THREE.DirectionalLight | null = null;
  root.traverse((o) => { if (!s && o instanceof THREE.DirectionalLight && o.castShadow) s = o; });
  return s as THREE.DirectionalLight | null;
};
/** the sun of the world that is calling: the attached root whose sun target sits on this camera's view axis */
const findSun = (cam: CamInfo, out: THREE.Vector3) => {
  if (cam.sun) return out.copy(cam.sun).normalize();
  let best: THREE.DirectionalLight | null = null, err = Infinity;
  for (const r of ROOTS) {
    if (!r.parent) continue;
    const s = sunOf(r);
    if (!s) continue;
    const d = tmp.copy(s.target.position).sub(cam.pos), e = Math.abs(d.dot(cam.right)) / (d.length() || 1);
    if (e < err) { err = e; best = s; }
  }
  return best ? out.copy(best.position).sub(best.target.position).normalize() : out;
};
/** canvas angle the sun comes FROM on an upright card facing the camera, in 45-degree steps (small texture cache) */
const light2D = (cam: CamInfo, mirror: boolean) => {
  const sx = SUN.dot(cam.right) * (mirror ? -1 : 1), sy = -SUN.y;
  return Math.round(Math.atan2(sy, sx) / (Math.PI / 4)) * (Math.PI / 4);
};

/** front / side view and mirroring for someone at (x, z) walking along (dx, dz); fs = foreshortening of the walk */
const viewOf = (cam: CamInfo, x: number, z: number, dx: number, dz: number) => {
  const tx = cam.pos.x - x, tz = cam.pos.z - z, tl = Math.hypot(tx, tz) || 1;
  const c = (tx * dx + tz * dz) / tl;
  return { side: c < 0.57, mirror: dx * cam.right.x + dz * cam.right.z < 0, fs: Math.round(Math.sqrt(Math.max(0, 1 - c * c)) * 20) / 20 };
};

// ---------------- life: blinks and reaction timing ----------------
/** reference expression and action changes land 0-3 f before the word onset */
const LEAD = 2 / FPS;
/** eyelid 0 open .. 1 shut. Reference: gaps 0.5-2.3 s, 4-frame blink half / shut / shut / half, plus a blink across
 *  every expression swap (the shut frames hide the swap) */
const LID = [0.5, 1, 1, 0.5];
const lidAt = (t: number, i: number, swaps: number[] = []) => {
  const f = Math.round(t * FPS);
  for (const ts of swaps) { const k = f - Math.round((ts - LEAD) * FPS) + 1; if (k >= 0 && k < 4) return LID[k]; }
  let s = Math.round(-60 * hh(i, 9));
  for (let n = 0; s <= f && n < 400; n++) {
    const k = f - s;
    if (k >= 0 && k < 4) return LID[k];
    s += Math.round(15 + 54 * hh(i * 31 + n, 13)); // next blink 0.5-2.3 s later
  }
  return 0;
};
const fkey = (o: object) => JSON.stringify(o, (_k, v) => (typeof v === "number" ? q(v) : v));

type Who = { i: number; o: Outfit; okey: string };
/** one character drawing in the 600 x 1000 design space, sized by distance, lit from the scene's sun */
const person = (cam: CamInfo, who: Who, x: number, y: number, z: number, view: { side: boolean; mirror: boolean }, fo: FrontOpts, so: SideOpts, scale = 1): Place & { tierKey: string } => {
  const d = cam.pos.distanceTo(tmp.set(x, y + 1.2, z)) / scale;
  const [w, h, k] = tier(d);
  const mirror = view.side && view.mirror, light = light2D(cam, mirror), seed = seedOf(who.i);
  const f2: FrontOpts = { ...fo, light, seed }, s2: SideOpts = { ...so, light, seed };
  const key = view.side ? `S|${who.okey}|${fkey(s2)}` : `F|${who.okey}|${fkey(f2)}`;
  return {
    key, x, y, z, scale, mirror, tierKey: `${w}`,
    draw: (p) => (view.side ? bodySide(p, who.o, s2) : bodyFront(p, who.o, f2)),
    size: [w, h, k],
  };
};

/** ground shadow under a standing / sitting card (review rounds 2-4), multiply, blue-violet: a TIGHT contact pool right under
 *  the feet (~.5 on screen at the core) so nobody floats, plus by day (cards cast no real shadow) a lighter soft tail
 *  stretched AWAY from the sun, length ~1.6 m / tan(sun elevation), capped. Golden: world.ts casts real card shadows. */
const CONTACT: Record<LightName, [number, number, number]> = { day: [0.2, 0.21, 0.33], golden: [0.24, 0.2, 0.33], yellow: [0.32, 0.27, 0.16], lab: [0.26, 0.2, 0.22], night: [0.1, 0.1, 0.2] };
const TAIL: [number, number, number] = [0.42, 0.44, 0.62];
const toSrgb = (v: number) => { const c = clamp01(v); return c <= 0.0031308 ? 12.92 * c : 1.055 * c ** (1 / 2.4) - 0.055; };
const hexOf = (c: [number, number, number], k: number) => "#" + c.map((v) => Math.round(255 * toSrgb(1 - (1 - v) * k)).toString(16).padStart(2, "0")).join("");
const blob = (out: Stage, x: number, y: number, z: number, sc = 1, k = 1) => {
  const hl = Math.hypot(SUN.x, SUN.z) || 1, ox = -SUN.x / hl, oz = -SUN.z / hl, rot = Math.atan2(-ox, -oz);
  if (LNAME !== "golden") {
    const el = Math.asin(Math.min(0.99, Math.max(0.1, SUN.y)));
    const len = Math.min(2.4, Math.max(0.5, 1.6 / Math.tan(el))) * sc, h = len + 0.55 * sc, c = 0.3 * h; // feet at v = .2 of the card
    const tc = hexOf(TAIL, k);
    out.fx.push({ key: `blob|shadow|${tc}`, cw: 128, ch: 256, draw: (p) => fxShadow(p, tc), x: x + ox * c, y: y + 0.018, z: z + oz * c,
      w: 0.72 * sc, h, flat: true, rot });
  }
  const cc = hexOf(CONTACT[LNAME], k);
  out.fx.push({ key: `blob|contact|${cc}`, cw: 128, ch: 128, draw: (p) => fxContact(p, cc), x: x + ox * 0.03 * sc, y: y + 0.022, z: z + oz * 0.03 * sc,
    w: 0.52 * sc, h: 0.4 * sc, flat: true, rot });
};

// ---------------- crowd by shot ----------------
export type Stage = { places: Place[]; fx: FxPlace[] };
const stand = (cam: CamInfo, out: Stage, i: number, o: Outfit, okey: string, x: number, y: number, z: number, fo: FrontOpts, scale = 1, shadow = true) => {
  out.places.push(person(cam, { i, o, okey }, x, y, z, { side: false, mirror: false }, fo, {}, scale));
  if (shadow) blob(out, x, y, z, scale);
};
const walker = (cam: CamInfo, out: Stage, i: number, o: Outfit, okey: string, x: number, y: number, z: number, t: number, dx: number, dz: number, expr: Expr, scale = 1) => {
  const view = viewOf(cam, x, z, dx, dz), ph = q(((t * 1.9 + hh(i, 5)) % 1 + 1) % 1, 60);
  out.places.push(person(cam, { i, o, okey }, x, y, z, view, { mode: "stroll", phase: ph, expr, blink: lidAt(t, i) }, { mode: "march", phase: ph, expr, blink: lidAt(t, i), stomp: 0.6, stride: 0.7 * view.fs }, scale));
  blob(out, x, y, z, scale);
};

// ---------------- the Emu War crowd by shot ----------------
const S = (f: number, a: number) => f >= a - 2; // a reaction lands 0-3 f before its word
const sit = (cam: CamInfo, out: Stage, i: number, o: Outfit, okey: string, x: number, y: number, z: number, fo: FrontOpts, scale = 1) =>
  stand(cam, out, i, o, okey, x, y, z, { ...fo, mode: "sit" }, scale, false);
/** a side-view person facing along +x on screen (mirror when +x points screen-left) */
const side = (cam: CamInfo, out: Stage, i: number, o: Outfit, okey: string, x: number, y: number, z: number, dirX: number, dirZ: number, so: SideOpts, shadow = true) => {
  const mirror = dirX * cam.right.x + dirZ * cam.right.z < 0;
  out.places.push(person(cam, { i, o, okey }, x, y, z, { side: true, mirror }, {}, so));
  if (shadow) blob(out, x, y, z);
};
const G0 = gunner(0), G1 = gunner(1), G0bare: Outfit = { ...gunner(0), hat: "hair", hair: "#5a3b2a" };
const FARMERS = [0, 1, 2].map((v) => farmer(v));

/** one emu card: side view (mirrored to face its walking direction dir) or front view when it walks at the lens */
const emu = (cam: CamInfo, out: Stage, i: number, x: number, y: number, z: number, o: EmuOpts, dir: [number, number] | null, front = false, scale = 1, shadow = true) => {
  const d = cam.pos.distanceTo(tmp.set(x, y + 1.0, z)) / scale;
  const k = tier(d)[2];
  let useFront = front, mirror = false;
  if (dir && !front) {
    const tx = cam.pos.x - x, tz = cam.pos.z - z, tl = Math.hypot(tx, tz) || 1, dl = Math.hypot(dir[0], dir[1]) || 1;
    const c = (tx * dir[0] + tz * dir[1]) / (tl * dl);
    if (c > 0.82) useFront = true;
    mirror = dir[0] * cam.right.x + dir[1] * cam.right.z < 0;
  }
  if (useFront) mirror = false;
  const light = light2D(cam, mirror), oo: EmuOpts = { ...o, light, seed: o.seed ?? (i % 4) + 1 };
  out.places.push({ key: `E|${useFront ? "F" : "S"}|${fkey(oo)}`, x, y, z, scale, mirror, geo: "wide", size: [Math.round(1000 * k), Math.round(1000 * k), k],
    draw: (p) => (useFront ? emuFront(p, oo) : emuSide(p, oo)) });
  if (shadow) blob(out, x, y, z, 1.35 * scale);
};
const ph = (t: number, i: number, rate: number, n = 12) => Math.round((((t * rate + hh(i, 5)) % 1) + 1) % 1 * n) / n;
const fx1 = (out: Stage, key: string, cw: number, ch: number, draw: (p: Pen) => void, x: number, y: number, z: number, w: number, h: number, soft = false, rot = 0) =>
  out.fx.push({ key, cw, ch, draw, x, y, z, w, h, soft, rot });
const flash = (out: Stage, f: number, x: number, y: number, z: number, s = 0.5) => {
  const k = (f % 3) / 3; fx1(out, `muzzle|${k}`, 500, 500, (p) => fxBurst(p, 0.25 + k * 0.5, "#ffd84a", 9, 40, 220), x, y, z, s, s);
};
const puff = (out: Stage, f: number, f0: number, x: number, y: number, z: number, s = 1.2, len = 18) => {
  if (f < f0 || f >= f0 + len) return;
  const q2 = Math.round(((f - f0) / len) * 10) / 10;
  fx1(out, `puff|${q2}`, 300, 300, (p) => fxPuff(p, q2 * 0.9), x, y + 0.2 * q2, z, s * (0.7 + q2), s * (0.7 + q2), true);
};
const feathers = (out: Stage, f: number, f0: number, x: number, y: number, z: number, s = 0.9) => {
  if (f < f0 || f >= f0 + 16) return;
  const q2 = Math.round(((f - f0) / 16) * 8) / 8;
  fx1(out, `feath|${q2}`, 300, 300, (p) => fxFeathers(p, q2), x, y, z, s, s);
};

// 1: the gun in the wheat, the gunner on the stock, the loader, the major pointing; the flock beyond
const hook = (cam: CamInfo, t: number, f: number, out: Stage) => {
  side(cam, out, 900, G0, "g0", HOOK_GUNNER[0], 0, HOOK_GUNNER[2], 0, -1, { mode: "push", pose: 0.85, expr: f < 99 ? "grin" : "stern", blink: lidAt(t, 900) });
  stand(cam, out, 901, G1, "g1", HOOK_LOADER[0], 0, HOOK_LOADER[2], { mode: "stand", expr: "grin", blink: lidAt(t, 901), look: 1, prop: f > 40 ? "point" : null });
  stand(cam, out, 902, MAJOR, "major", HOOK_MAJOR[0], 0, HOOK_MAJOR[2], { mode: "stand", expr: "stern", blink: lidAt(t, 902), prop: "point", look: 1, facing: 1 });
  if (f >= 99 && f < 126 && (f - 99) % 3 === 0) flash(out, f, HOOK_GUN[0], 1.15, HOOK_GUN[2] - 1.05, 0.6);
  for (let i = 0; i < 70; i++) {
    const x = -16 + hh(i, 1) * 34, z = -22 - hh(i, 2) * 46, pk = i % 3 !== 0;
    emu(cam, out, i, x, 0, z, { mode: pk ? "peck" : "walk", phase: ph(t, i, pk ? 0.7 : 1.2) }, [hh(i, 3) < 0.5 ? 1 : -1, 0]);
  }
};
// 2: the emu wearing the gunner's slouch hat; the gunner sitting dazed beside the tipped gun
const won = (cam: CamInfo, t: number, f: number, out: Stage) => {
  emu(cam, out, 910, WON_EMU[0], 0, WON_EMU[2], { mode: "stand", hat: "slouch", eye: "smug", blink: lidAt(t, 910) }, null, true);
  sit(cam, out, 911, G0bare, "g0bare", WON_EMU[0] + 0.75, 0.0, WON_EMU[2] - 2.0, { expr: "dazed", blink: lidAt(t, 911), headTilt: 8 * Math.sin(t * 4) });
  const sp = Math.round(((t * 0.8) % 1) * 60) / 60;
  fx1(out, `stars|${sp}`, 420, 210, (p) => fxStars(p, sp), WON_EMU[0] + 0.75, 1.05, WON_EMU[2] - 1.95, 0.6, 0.3);
  for (let i = 0; i < 8; i++) emu(cam, out, 912 + i, WON_EMU[0] - 3 + i * 1.1, 0, WON_EMU[2] - 3 - (i % 3) * 1.6, { mode: "peck", phase: ph(t, i, 0.7) }, [i % 2 ? 1 : -1, 0]);
};
// 3: the flock marching south through the wheat toward the farm
const march = (cam: CamInfo, t: number, f: number, out: Stage) => {
  for (let i = 0; i < 320; i++) {
    const x = -70 + hh(i, 1) * 140, z0 = -330 + hh(i, 2) * 270, z = z0 + 1.3 * (t - 167 / FPS) * 3;
    emu(cam, out, i, x, 0, z, { mode: "walk", phase: ph(t, i, 1.4, 8) }, [0, 1]);
  }
};
// 4: the farmer at his fence, the emus eating his wheat
const eat = (cam: CamInfo, t: number, f: number, out: Stage) => {
  const fx = FENCE_FARMER;
  stand(cam, out, 920, FARMERS[0], "fa0", fx[0], 0, fx[2], { mode: "stand", expr: S(f, 275) ? "shock" : "stern", blink: lidAt(t, 920, [275 / FPS]), look: 1, prop: S(f, 283) ? "facepalm" : null, facing: 1 });
  const spots: [number, number][] = [[6.6, -7.2], [8.1, -6.9], [9.6, -8.4], [7.2, -9.6], [10.8, -7.6], [5.4, -10.8], [8.8, -11.6], [11.8, -10.4], [6.2, -13.4], [9.9, -13.8], [12.6, -12.8], [4.4, -8.2]];
  spots.forEach(([x, z], i) => {
    emu(cam, out, 921 + i, x, 0, z, { mode: "peck", phase: ph(t, i, 0.9) }, [i % 2 ? 1 : -1, 0]);
    const c0 = 250 + ((i * 13) % 50);
    if (i < 5 && f >= c0 && f < c0 + 14) { const q2 = Math.round(((f - c0) / 14) * 7) / 7; fx1(out, `crumb|${q2}`, 300, 300, (p) => fxCrumbs(p, q2), x + (i % 2 ? 0.9 : -0.9), 0.6, z + 0.3, 0.6, 0.6); }
  });
};
// 5: the farmers before the minister: a salute on "old soldiers", hats in hand on "asked"
const minister = (cam: CamInfo, t: number, f: number, out: Stage) => {
  stand(cam, out, 930, MINISTER, "minister", MINISTER_AT[0], 0, MINISTER_AT[2], { mode: "stand", expr: f < 387 ? "neutral" : "smile", blink: lidAt(t, 930), look: 0, headTilt: S(f, 387) ? 5 * Math.sin((f - 387) * 0.25) : 0 });
  FARMERS_AT.forEach(([x, , z], i) => {
    const prop: Prop = f >= 324 && f < 352 ? "salute" : S(f, 357) ? "hatInHand" : null;
    const o = prop === "hatInHand" ? { ...FARMERS[i], hat: "hair", hair: ["#8a5a3a", "#3a2a22", "#c9c3b5"][i] } : FARMERS[i];
    stand(cam, out, 931 + i, o, `fa${i}${prop === "hatInHand" ? "h" : ""}`, x, 0, z, { mode: "stand", expr: f < 357 ? "stern" : "nervous", blink: lidAt(t, 931 + i, [357 / FPS]), prop, look: 0 });
  });
};
// 6: the line-up: each named thing appears on its word
const lineup = (cam: CamInfo, t: number, f: number, out: Stage) => {
  const z = LINE_Z;
  if (f >= 416) stand(cam, out, 940, MAJOR, "major", LINE.major, 0, z, { mode: "stand", expr: "stern", blink: lidAt(t, 940), prop: f < 434 ? "salute" : null, look: 1 });
  if (f >= 437) { stand(cam, out, 941, G0, "g0", LINE.g1, 0, z, { mode: "stand", expr: "grin", blink: lidAt(t, 941), prop: f < 456 ? "salute" : null }); stand(cam, out, 942, G1, "g1", LINE.g2, 0, z + 0.1, { mode: "stand", expr: "grin", blink: lidAt(t, 942), prop: f < 456 ? "salute" : null }); }
  for (const [a, x] of [[416, LINE.major], [437, LINE.g1], [437, LINE.g2], [457, LINE.guns - 0.35], [457, LINE.guns + 0.35]] as const) puff(out, f, a, x, 0, z + 0.25, 1.0, 14);
  for (let k = 0; k < 3; k++) puff(out, f, 488 + k * 4, LINE.crates - 0.74 + k * 0.74, 0, z + 0.2, 1.1, 16);
};
// 7: the cameraman cranking; the major posing, chin up
const camera = (cam: CamInfo, t: number, f: number, out: Stage) => {
  stand(cam, out, 950, CAMERAMAN, "cameraman", CAMERA_AT[0] - 0.55, 0, CAMERA_AT[2] + 0.05, { mode: "stand", expr: "grin", blink: lidAt(t, 950), prop: ["crank", Math.round(((t * 2) % 1) * 12) / 12], look: 1 });
  stand(cam, out, 951, MAJOR, "major", POSE_MAJOR[0], 0, POSE_MAJOR[2], { mode: "stand", expr: S(f, 565) ? "grin" : "smile_closed", blink: lidAt(t, 951), prop: S(f, 565) ? "point" : "crossed", look: -1, headTilt: -6, facing: -1 });
  stand(cam, out, 952, G0, "g0", POSE_MAJOR[0] + 1.0, 0, POSE_MAJOR[2] - 0.8, { mode: "stand", expr: "grin", blink: lidAt(t, 952), prop: S(f, 565) ? "salute" : null, look: -1 });
  if (f >= 567 && f < 580) { const k = (f - 567) / 13; fx1(out, `burst|${Math.round(k * 10)}`, 500, 500, (p) => fxBurst(p, Math.round(k * 10) / 10, "#fff3b0", 10), POSE_MAJOR[0] + 0.3, 1.9, POSE_MAJOR[2] + 0.2, 0.7, 0.7); }
};
// 8: "home by lunch": the gunner laughing, tapping his watch
const lunch = (cam: CamInfo, t: number, f: number, out: Stage) => {
  stand(cam, out, 960, G1, "g1", LINE.g2, 0, LINE_Z, { mode: "stand", expr: f < 618 ? "grin" : f < 640 ? "laugh" : "grin", blink: lidAt(t, 960), prop: S(f, 645) ? "watch" : null, look: -1, headTilt: f >= 618 && f < 640 ? 6 * Math.sin(t * 14) : 0 });
  stand(cam, out, 961, G0, "g0", LINE.g2 - 1.1, 0, LINE_Z - 0.9, { mode: "stand", expr: f < 620 ? "smile" : "laugh", blink: lidAt(t, 961) });
};
// 9-10: the dam: the gun on the wall, the flock walking in from the east; the volley, twelve hits, the jam, the scatter
const DAM_EMUS = 170;
const damEmu = (i: number, f: number): { x: number; z: number; dir: [number, number]; run: boolean } => {
  const z = DAM.z - 26 + hh(i, 2) * 46, xs = DAM.x + 12 + hh(i, 1) * 46 + 0.5 * (i % 7);
  if (f < JAM_AT + 4) return { x: xs - 1.4 * ((Math.min(f, JAM_AT) - 676) / FPS), z, dir: [-1, 0], run: false };
  const x0 = xs - 1.4 * ((JAM_AT - 676) / FPS), a = hh(i, 6) * Math.PI - Math.PI / 2; // run away east-ish, every direction
  const s = 9 * ((f - JAM_AT - 4) / FPS), dx = Math.cos(a), dz = Math.sin(a);
  return { x: x0 + dx * s, z: z + dz * s, dir: [dx, dz], run: true };
};
/** the twelve hit birds: the nearest ones in the middle of the hits shot */
const HITS = (() => {
  const cx = DAM.x + 7, cz = DAM.z + 2, la = Math.atan2(-5, 15);
  return Array.from({ length: 170 }, (_, i) => i).map((i) => { const e = damEmu(i, 805); return { i, d: Math.hypot(e.x - cx, e.z - cz), a: Math.atan2(e.z - cz, e.x - cx) - la }; })
    .filter((o) => Math.abs(o.a) < 0.2 && o.d > 9 && o.d < 26).sort((a, b) => a.a - b.a).filter((_, k, arr) => k % Math.max(1, Math.floor(arr.length / 12)) === 0).slice(0, 12).map((o) => o.i);
})();
const damCrew = (cam: CamInfo, t: number, f: number, out: Stage) => {
  const jam = f >= JAM_AT;
  side(cam, out, 970, G0, "g0", DAM_GUNNER[0], DAM_GUNNER[1], DAM_GUNNER[2], 1, 0, { mode: "push", pose: 0.9, expr: jam ? "shock" : f >= FIRE_A ? "grin" : "stern", blink: lidAt(t, 970, [JAM_AT / FPS]) }, false);
  stand(cam, out, 971, G1, "g1", DAM_LOADER[0], DAM_LOADER[1], DAM_LOADER[2], { mode: "stand", expr: jam ? "shock" : "grin", blink: lidAt(t, 971, [JAM_AT / FPS]), look: 1 }, 1, false);
  stand(cam, out, 972, MAJOR, "major", DAM_MAJOR[0], DAM_MAJOR[1], DAM_MAJOR[2], { mode: "stand", expr: jam ? "shock" : "stern", blink: lidAt(t, 972), prop: jam ? null : "point", look: 1, facing: 1 }, 1, false);
};
const dam = (cam: CamInfo, t: number, f: number, out: Stage) => {
  damCrew(cam, t, f, out);
  for (let i = 0; i < DAM_EMUS; i++) { const e = damEmu(i, f); emu(cam, out, i, e.x, 0, e.z, { mode: e.run ? "run" : "walk", phase: ph(t, i, e.run ? 2.4 : 1.2, 8) }, e.dir); }
};
const fire = (cam: CamInfo, t: number, f: number, out: Stage) => {
  dam(cam, t, f, out);
  if (firing(f)) flash(out, f, DAM_GUN[0] + 1.05, DAM_GUN[1] + 1.0, DAM_GUN[2], 0.6);
  HITS.forEach((i, k) => {
    const e = damEmu(i, 798 + k * 2), dx = cam.pos.x - e.x, dz = cam.pos.z - e.z, dl = Math.hypot(dx, dz) || 1, x = e.x + (dx / dl) * 0.9, z = e.z + (dz / dl) * 0.9;
    feathers(out, f, 798 + k * 2, x, 1.2, z, 2.6); puff(out, f, 798 + k * 2, x, 0.6, z, 2.0, 12);
  });
  if (f >= JAM_AT && f < JAM_AT + 24) { const q2 = Math.round(((f - JAM_AT) / 24) * 8) / 8; fx1(out, `smoke|${q2}`, 300, 300, (p) => fxSmoke(p, q2), DAM_GUN[0] + 0.25 + 0.3 * q2, DAM_GUN[1] + 1.12 + 0.3 * q2, DAM_GUN[2] + 0.12, 0.6 + 0.4 * q2, 0.6 + 0.4 * q2, true); }
  if (f >= JAM_AT && f < JAM_AT + 9) { const k = (f - JAM_AT) / 9; fx1(out, `burst|${Math.round(k * 8)}`, 500, 500, (p) => fxBurst(p, Math.round(k * 8) / 8, "#ffffff", 8), DAM_GUN[0] - 0.1, DAM_GUN[1] + 1.05, DAM_GUN[2] + 0.15, 0.5, 0.5); }
};
// 11: the major points, the gunner on the tray, the truck pulls away in a cloud of dust
const TRAY = (tr: { x: number; z: number; yaw: number; bounce: number }, dx = -1.65): V3 => [tr.x + Math.cos(tr.yaw) * dx, 0.95 + tr.bounce, tr.z - Math.sin(tr.yaw) * dx];
const truck = (cam: CamInfo, t: number, f: number, out: Stage) => {
  const tr = truckAt(f, 11), g = TRAY(tr);
  side(cam, out, 980, G0, "g0", g[0], g[1], g[2], 1, 0, { mode: "push", pose: 0.9, expr: f < 894 ? "grin" : "nervous", blink: lidAt(t, 980) }, false);
  stand(cam, out, 981, MAJOR, "major", TRUCK_PARK[0] - 1.4, 0, TRUCK_PARK[2] + 1.9, { mode: "stand", expr: "stern", blink: lidAt(t, 981), prop: S(f, 859) ? "point" : null, look: 1, facing: 1 });
  for (let k = 0; k < 6; k++) { const a = 896 + k * 5; if (f >= a) puff(out, f, a, truckAt(a, 11).x - 2.4, 0, TRUCK_PARK[2] + (k % 2 ? 0.6 : -0.6), 1.6, 22); }
};
// 12-13: the chase: the emus at 14 m/s overtake the truck at 9; the gunner bounces, firing at the sky
const CHASE_EMUS = 16;
const chaseEmu = (i: number, f: number, close = false) => ({ x: CHASE.x - (close ? 30 : 16) + EMU_V * ((f - 923) / FPS) + (i % 8) * 3.1 + hh(i, 1) * 2, z: CHASE.z - (close ? 4 : 7) - Math.floor(i / 8) * 3.2 - hh(i, 2) * 1.2 });
const chase = (cam: CamInfo, t: number, f: number, out: Stage, close: boolean) => {
  const id = close ? 13 : 12, tr = truckAt(f, id), g = TRAY(tr);
  const expr: Expr = close ? "dazed" : f < 960 ? "stern" : "nervous";
  side(cam, out, 990, G0, "g0", g[0], g[1], g[2], 1, 0, { mode: "push", pose: 0.6 + 0.3 * Math.sin(f * 0.9), expr, blink: lidAt(t, 990) }, false);
  if (f % 4 === 0 && f > 940) { const up = 0.5 + 0.5 * Math.sin(f * 0.37); flash(out, f, tr.x - 0.9 + 1.0, 2.05 + tr.bounce + up * 0.35, tr.z, 0.5); }
  for (let i = 0; i < CHASE_EMUS; i++) {
    const e = chaseEmu(i, f, close);
    emu(cam, out, i, e.x, 0, e.z, { mode: "run", phase: ph(t, i, 2.6, 8), eye: i % 3 ? "norm" : "smug" }, [1, 0]);
    const a = Math.floor(f / 6) * 6; puff(out, f, a, chaseEmu(i, a, close).x - 0.8, 0, e.z, 0.9, 6);
  }
  const a = Math.floor(f / 5) * 5; puff(out, f, a, truckAt(a, id).x - 2.6, 0, tr.z + 0.5, 1.8, 5);
};
// 14: the major on the dam wall: wait, how?
const wait = (cam: CamInfo, t: number, f: number, out: Stage) => {
  stand(cam, out, 1000, MAJOR, "major", DAM_MAJOR[0], DAM_MAJOR[1], DAM_MAJOR[2], { mode: "stand", expr: f < 1085 ? "nervous" : "dazed", blink: lidAt(t, 1000), prop: ["scratch", Math.round((0.5 + 0.5 * Math.sin(t * 12)) * 4) / 4], look: 0 }, 1, false);
  if (f >= 1062) { const k = smooth((f - 1062) / 8), wob = 0.08 * Math.sin(t * 8); out.fx.push({ key: "question", cw: 240, ch: 360, draw: (p) => fxQuestion(p), x: DAM_MAJOR[0] + 0.42, y: 2.35, z: DAM_MAJOR[2] + 0.2, w: 0.22 * k, h: 0.33 * k, rot: wob }); }
};
// 15-16: the flock on the plain; the gunsight ring on "crowd"; the burst into small groups on "shooting"
const FLOCK = 130;
const flockAt = (i: number, f: number) => {
  const g = i % NGROUP, a = (g / NGROUP) * Math.PI * 2 + 0.3 * hh(g, 3), local = [(hh(i, 1) - 0.5) * 2.6, (hh(i, 2) - 0.5) * 2.6];
  const r0 = 2.0 + 4.5 * Math.sqrt(hh(i, 4));
  const c0 = [Math.cos(a) * r0 * 0.5 + local[0] * 0.6, Math.sin(a) * r0 * 0.5 + local[1] * 0.6];
  if (f < BURST_AT) return { x: BURST.x + c0[0], z: BURST.z + c0[1], dir: [Math.cos(a), Math.sin(a)] as [number, number], run: false };
  const s = 10 * Math.max(0, (f - BURST_AT - (g % 3) * 2) / FPS);
  return { x: BURST.x + c0[0] + Math.cos(a) * s + local[0] * 0.6 * Math.min(1, s / 6), z: BURST.z + c0[1] + Math.sin(a) * s + local[1] * 0.6 * Math.min(1, s / 6), dir: [Math.cos(a), Math.sin(a)] as [number, number], run: s > 0 };
};
const flock = (cam: CamInfo, t: number, f: number, out: Stage, burst: boolean) => {
  for (let i = 0; i < FLOCK; i++) {
    const e = flockAt(i, f), look = !e.run && f >= 1219;
    emu(cam, out, i, e.x, 0, e.z, { mode: e.run ? "run" : look ? "look" : "peck", phase: ph(t, i, e.run ? 2.6 : 0.7, 8), dark: !!burst && i < NGROUP }, e.run ? e.dir : [hh(i, 7) < 0.5 ? 1 : -1, 0]);
  }
  if (!burst && f >= 1160 && f < 1250) {
    const k = Math.round(smooth((f - 1160) / 8) * 8) / 8;
    out.fx.push({ key: `target|${k}`, cw: 600, ch: 600, draw: (p) => fxTarget(p, Math.max(0.05, k)), x: BURST.x, y: 0.4, z: BURST.z, w: 17, h: 17, flat: true });
  }
  // the gunner at the bottom of the frame
  side(cam, out, 1010, G0, "g0", BURST.x - 1.5, 0, BURST.z + 13, 1, -1, { mode: "push", pose: 0.9, expr: burst && f >= BURST_AT ? "shock" : "grin", blink: lidAt(t, 1010) });
  if (burst && f >= BURST_AT - 2 && f < BURST_AT + 22 && (f - BURST_AT) % 3 === 0) flash(out, f, BURST.x - 0.4, 1.0, BURST.z + 12.2, 0.8);
};
// 18: the lookout: a tall black emu turning his head while his group pecks; "!" and they're off on "soldiers"
const LOOK_GROUP: [number, number][] = [[-1.6, -1.2], [1.8, -0.9], [-0.9, -2.6], [2.6, -2.8], [0.6, -3.6], [-2.4, -3.3]];
const lookout = (cam: CamInfo, t: number, f: number, out: Stage) => {
  const L = LOOKOUT, alarm = f >= 1514, flee = f >= 1524;
  const turn = Math.sin((f - 1417) / 14) > 0 ? 1 : -1;
  emu(cam, out, 1020, L[0], 0, L[2], { mode: alarm ? "alarm" : "look", dark: true, turn, eye: alarm ? "shock" : "norm", blink: lidAt(t, 1020) }, flee ? [1, 0] : [turn, 0], f >= 1488 && f < 1514, 1.25);
  LOOK_GROUP.forEach(([dx, dz], i) => {
    const s = flee ? 9 * ((f - 1524 - i) / FPS) : 0;
    emu(cam, out, 1021 + i, L[0] + dx + Math.max(0, s), 0, L[2] + dz, { mode: flee && s > 0 ? "run" : alarm ? "look" : "peck", phase: ph(t, i, flee ? 2.6 : 0.8, 8) }, [1, 0]);
  });
  if (alarm) { const k = smooth((f - 1514) / 6), wob = 0.06 * Math.sin(t * 20); out.fx.push({ key: "exclaim", cw: 200, ch: 360, draw: (p) => fxExclaim(p), x: L[0] + 0.1, y: 2.75, z: L[2] + 0.2, w: 0.2 * k, h: 0.36 * k, rot: wob }); }
  // two soldiers sneaking up through the wheat, far behind
  for (let k = 0; k < 2; k++) side(cam, out, 1030 + k, k ? G1 : G0, k ? "g1" : "g0", L[0] - 9 + k * 1.2 + 0.5 * ((f - 1417) / FPS), 0, L[2] - 12 - k * 0.6, 1, 0, { mode: "march", phase: ph(t, k, 0.8, 12), expr: "stern", stride: 0.4 });
};
// 19: the truck drives off; the emus line the fence to see it go, one salutes
const home = (cam: CamInfo, t: number, f: number, out: Stage) => {
  const tr = truckAt(f, 19);
  for (let k = 0; k < 2; k++) { const g = TRAY(tr, -1.2 - k * 0.8); sit(cam, out, 1040 + k, k ? G1 : G0, k ? "g1" : "g0", g[0], g[1] - 0.1, g[2] + (k ? 0.3 : -0.3), { expr: "pained", blink: lidAt(t, 1040 + k), headTilt: 8 }); }
  for (let i = 0; i < 9; i++) emu(cam, out, 1050 + i, CAMP.x - 2 + i * 1.7, 0, FENCE_Z - 1.2 - (i % 2) * 0.5, { mode: i === 4 ? "salute" : "stand", eye: "smug", hat: i === 4 ? "slouch" : null, blink: lidAt(t, 1050 + i) }, null, true);
  const a = Math.floor(f / 5) * 5; puff(out, f, a, truckAt(a, 19).x + 2.4, 0, tr.z, 1.8, 5);
};
// 20: parliament: the member asks about a medal; the house laughs on "medal"
const parliament = (cam: CamInfo, t: number, f: number, out: Stage) => {
  const P = PARL;
  stand(cam, out, 1060, mp(1), "mp1", MP_ASK[0], 0, MP_ASK[2], { mode: "stand", expr: f < 1640 ? "smile" : "laugh", blink: lidAt(t, 1060), prop: f < 1640 ? "point" : null, look: -1, facing: -1 });
  let n = 0;
  for (const s of [-1, 1]) for (let r = 0; r < BENCH_ROWS; r++) for (let z = P.z - 6.4; z < P.z + 5.5; z += 1.05) {
    const x = P.x + s * (2.3 + r * 1.05), i = 1061 + n++;
    if (s > 0 && r === 0 && Math.abs(z - MP_ASK[2]) < 0.8) continue;
    if (hh(i, 9) < 0.25) continue;
    const laugh = f >= 1646 + (i % 5);
    sit(cam, out, i, mp(i), `mp${i % 4}`, x, r * 0.35 + 0.42, z, { expr: laugh ? "laugh" : (["neutral", "smile", "smile_closed", "stern"] as Expr[])[i % 4], blink: lidAt(t, i), look: -s, headTilt: laugh ? 5 * Math.sin(t * 12 + i) : 0 });
  }
};
// 21: the gunner on a mountain of spent cases, still firing; the emus stroll past
const brass = (cam: CamInfo, t: number, f: number, out: Stage) => {
  sit(cam, out, 1100, G0, "g0", BRASS[0] - 0.2, BRASS_H - 0.32, BRASS[2] + 0.1, { expr: "dazed", blink: lidAt(t, 1100) });
  if (f % 3 === 0) flash(out, f, BRASS[0] + 1.25, BRASS_H + 0.45, BRASS[2] + 0.05, 0.5);
  for (let k = 0; k < 4; k++) { const u = (((f + k * 7) % 28) / 28), q2 = Math.round(u * 10) / 10; fx1(out, `case|0`, 120, 300, (p) => fxCase(p), BRASS[0] + 0.2 + q2 * 0.9 * (k % 2 ? 1 : -1), BRASS_H + 0.5 + 1.2 * q2 - 2.2 * q2 * q2, BRASS[2] + 0.3, 0.05, 0.12, false, q2 * 6 + k); }
  for (let i = 0; i < 5; i++) emu(cam, out, 1110 + i, BRASS[0] + 8 - 1.6 * ((f - 1663) / FPS) - i * 2.6, 0, BRASS[2] + 2.6 + (i % 2) * 0.8, { mode: "walk", phase: ph(t, i, 1.1, 12), eye: "smug" }, [-1, 0]);
};
// 22: one emu, ten cases landing in a row at its feet
const ten = (cam: CamInfo, t: number, f: number, out: Stage) => {
  emu(cam, out, 1120, TEN_EMU[0], 0, TEN_EMU[2], { mode: "stand", eye: "smug", blink: lidAt(t, 1120) }, null, true);
  let shown = 0;
  for (let k = 0; k < 10; k++) {
    const a = 1777 + k * 3; if (f < a) continue;
    shown = k + 1;
    const drop = 1 - smooth((f - a) / 4), an = Math.PI * (0.08 + 0.84 * (k / 9));
    fx1(out, "case|0", 120, 300, (p) => fxCase(p), TEN_EMU[0] - Math.cos(an) * 0.72, 0.13 + 0.6 * drop, TEN_EMU[2] + 0.25 + Math.sin(an) * 0.5, 0.11, 0.27);
  }
  if (shown) fx1(out, `count|${shown}`, 240, 240, (p) => fxCount(p, shown), TEN_EMU[0] + 0.5, 1.95, TEN_EMU[2] + 0.2, 0.34, 0.34);
};
// 23: the major writing his report at the camp table; hearts on "admiration"
const report = (cam: CamInfo, t: number, f: number, out: Stage) => {
  const D = DESK_AT;
  sit(cam, out, 1130, MAJOR, "major", D[0], 0.32, D[2] - 0.45, { expr: f < 1860 ? "neutral" : "relief", blink: lidAt(t, 1130, [1860 / FPS]), prop: f < 1858 ? "pen" : null, look: 0, headTilt: f >= 1860 ? -8 : 0 });
  out.fx.push({ key: "paperA", cw: 300, ch: 400, draw: (p) => fxPaper(p), x: D[0] + 0.05, y: 0.785, z: D[2] - 0.05, w: 0.24, h: 0.32, flat: true, rot: 0.15 });
  if (f >= 1862) { const hp = Math.round(((t * 0.6) % 1) * 30) / 30; fx1(out, `hearts|${hp}`, 360, 300, (p) => fxHearts(p, hp), D[0] + 0.1, 1.95, D[2] - 0.3, 0.7, 0.58); }
};
// 24: the division: emus in slouch hats marching in step past the saluting major; the leader stops and salutes back
const parade = (cam: CamInfo, t: number, f: number, out: Stage) => {
  stand(cam, out, 1140, MAJOR, "major", PARADE_MAJOR[0], 0, PARADE_MAJOR[2], { mode: "stand", expr: f < 1990 ? "relief" : "grin", blink: lidAt(t, 1140), prop: "salute", look: 1 });
  const step = Math.round(((t * 1.5) % 1) * 12) / 12;
  for (let r = 0; r < 4; r++) for (let c = 0; c < 6; c++) {
    const lead = r === 0 && c === 5, x0 = paradeX(lead ? Math.min(f, LEAD_STOP) : f) + c * 1.55, z = PARADE_Z - r * 1.25;
    if (lead && f >= LEAD_STOP) { const k = smooth((f - LEAD_STOP) / 10); emu(cam, out, 1150, x0, 0, z + 1.3 * k, { mode: "salute", hat: "slouch", eye: "proud", blink: lidAt(t, 1150) }, null, true, 1.1); }
    else emu(cam, out, 1151 + r * 6 + c, x0, 0, z, { mode: "walk", phase: step, hat: "slouch", eye: "proud", seed: 1 + ((r + c) % 2) }, [1, 0]);
  }
};

/** everything with a face (and every 2D effect) in shot `id` at time t */
export const stage = (id: number, t: number, f: number, cam: CamInfo): Stage => {
  const out: Stage = { places: [], fx: [] };
  const s = SHOTS[id - 1];
  LNAME = s.light;
  findSun(cam, SUN);
  switch (s.crowd) {
    case "hook": hook(cam, t, f, out); break;
    case "won": won(cam, t, f, out); break;
    case "march": march(cam, t, f, out); break;
    case "eat": eat(cam, t, f, out); break;
    case "minister": minister(cam, t, f, out); break;
    case "lineup": lineup(cam, t, f, out); break;
    case "camera": camera(cam, t, f, out); break;
    case "lunch": lunch(cam, t, f, out); break;
    case "dam": dam(cam, t, f, out); break;
    case "fire": fire(cam, t, f, out); break;
    case "truck": truck(cam, t, f, out); break;
    case "chase": chase(cam, t, f, out, false); break;
    case "bumpy": chase(cam, t, f, out, true); break;
    case "wait": wait(cam, t, f, out); break;
    case "flock": flock(cam, t, f, out, false); break;
    case "burst": flock(cam, t, f, out, true); break;
    case "lookout": lookout(cam, t, f, out); break;
    case "home": home(cam, t, f, out); break;
    case "parliament": parliament(cam, t, f, out); break;
    case "brass": brass(cam, t, f, out); break;
    case "ten": ten(cam, t, f, out); break;
    case "report": report(cam, t, f, out); break;
    case "parade": parade(cam, t, f, out); break;
    default: break;
  }
  return out;
};
export { FPS, clamp01, NOINK, CHASE };
