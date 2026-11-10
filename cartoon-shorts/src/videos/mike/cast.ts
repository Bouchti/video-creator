import type { LightName } from "./lights";
// The headless-chicken cast as lit flat sprites in the 3D world. Each frame every character asks for a drawing (a key + a draw
// call); the pool keeps one canvas per distinct drawing, so emus in step share canvases. People are yaw-only
// billboards on the 600 x 1000 card, emus on the WIDE 1000 x 1000 card; both are shaded by cardShade() and stand on a
// soft multiply contact blob. Effects are unlit cards. Everything lives on the NOINK layer (no world ink on quads).
import * as THREE from "three";
import {
  Pen, bodyFront, bodySide, fxShadow, fxContact, fxBurst, fxStars, fxPuff, fxQuestion,
  farmer, rider, tourist, INK, Outfit, Expr, FrontOpts, SideOpts, Prop,
} from "./toon";
import { fxAim, fxDropper, henSide, HenOpts, fxGurgle, fxFeather, fxCount, fxTag, fxScale, fxCough, fxZzz, fxVein, fxStem, fxBill, fxDrop, fxExclaim, fxFlashStar } from "./mikedraw";
import {
  FPS, SHOTS, clamp01, smooth, V3, B, LLOYD_BLOCK, FLOCK, hookMike, walkoff, PORCH, morningMike, MIL_AT, TABLE, SHOW_MIKE, FEST_STATUE, DESK_AT,
  UNPLUG_AT, DARK_AT, lbAt, DINNER_MIKE,
} from "./story";
import { SCALE, SHOW, MOTEL, FEST, COPY } from "./places";
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
export type FxPlace = { key: string; cw: number; ch: number; draw: (p: Pen) => void; x: number; y: number; z: number; w: number; h: number; flat?: boolean; rot?: number; soft?: boolean; upright?: boolean };
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

// ---------------- the headless-chicken cast ----------------
const S = (f: number, a: number) => f >= a - 2; // a reaction lands 0-3 f before its word
const sit = (cam: CamInfo, out: Stage, i: number, o: Outfit, okey: string, x: number, y: number, z: number, fo: FrontOpts, scale = 1) =>
  stand(cam, out, i, o, okey, x, y, z, { ...fo, mode: "sit" }, scale, false);
const side = (cam: CamInfo, out: Stage, i: number, o: Outfit, okey: string, x: number, y: number, z: number, dirX: number, dirZ: number, so: SideOpts, shadow = true) => {
  const mirror = dirX * cam.right.x + dirZ * cam.right.z < 0;
  out.places.push(person(cam, { i, o, okey }, x, y, z, { side: true, mirror }, {}, so));
  if (shadow) blob(out, x, y, z);
};
const runner = (cam: CamInfo, out: Stage, i: number, o: Outfit, okey: string, x: number, z: number, t: number, dx: number, dz: number, expr: Expr) => {
  const view = viewOf(cam, x, z, dx, dz), ph = q(((t * 3.0 + hh(i, 5)) % 1 + 1) % 1, 12);
  out.places.push(person(cam, { i, o, okey }, x, 0, z, view, { mode: "stroll", phase: ph, expr, blink: 0 }, { mode: "march", phase: ph, expr, blink: 0, stomp: 0.9, stride: 1.1 * view.fs }));
  blob(out, x, 0, z);
};
const LLOYD: Outfit = { ...farmer(0), medal: undefined, moustache: undefined, jacket: "#5b7fa8", pants: "#3b4a6a", hatCol: "#c9a05a", skin: "#f5c9a0" };
const LLOYD_NIGHT: Outfit = { ...LLOYD, hat: "hair", hair: "#6a4a32" };
const MIL: Outfit = { jacket: "#7b3a6a", pants: "#3b3f52", boots: "#3a2a22", hat: "hair", hair: "#d9d6cf", dress: "#7b3a6a", skin: "#f5c9a0", build: "stout", buttons: "#f4efe2" };
const SHOWMAN: Outfit = { jacket: "#d9382e", pants: "#2e2a36", boots: INK, hat: "tophat", buttons: "#f6d23a", moustache: "#3a2a22", build: "stout", skin: "#f5c9a0" };
const PHOTOG: Outfit = { jacket: "#6a5a4a", pants: "#3f4454", boots: "#3a2a22", hat: "fedora", hatCol: "#3a3346", tie: "#3f6fb5", buttons: "#d9dde0", skin: "#ffe2c2" };
const COPYF = [1, 2, 3].map((v) => ({ ...farmer(v), medal: undefined }));
const folk = (i: number): Outfit => (i % 2 ? rider(i) : tourist(i));

/** one chicken card, ~0.8 m card (scale 0.38 of the 2.16 m WIDE card) */
const hen = (cam: CamInfo, out: Stage, i: number, x: number, y: number, z: number, o: HenOpts, dir: [number, number], scale = 0.38, shadow = true) => {
  const d = cam.pos.distanceTo(tmp.set(x, y + 0.35, z)) / scale;
  const k = tier(d)[2];
  const mirror = dir[0] * cam.right.x + dir[1] * cam.right.z < 0;
  const light = light2D(cam, mirror), oo: HenOpts = { ...o, light };
  out.places.push({ key: `H|${fkey(oo)}`, x, y, z, scale, mirror, geo: "wide", size: [Math.max(80, Math.round(1000 * k)), Math.max(80, Math.round(1000 * k)), k], draw: (p) => henSide(p, oo) });
  if (shadow) blob(out, x, y, z, 0.55 * scale / 0.38);
};
const mike = (cam: CamInfo, out: Stage, t: number, x: number, y: number, z: number, mode: HenOpts["mode"], dir: [number, number], head = false, scale = 0.38, extra: Partial<HenOpts> = {}) =>
  hen(cam, out, 500, x, y, z, { mode, phase: ph(t, 3, mode === "walk" ? 1.8 : mode === "peck" ? 1.6 : mode === "run" ? 3 : 0.6, 12), head, eye: "norm", blink: lidAt(t, 500), proud: !head, ...extra }, dir, scale, y < 0.1);
const ph = (t: number, i: number, rate: number, n = 12) => Math.round((((t * rate + hh(i, 5)) % 1) + 1) % 1 * n) / n;
const fx1 = (out: Stage, key: string, cw: number, ch: number, draw: (p: Pen) => void, x: number, y: number, z: number, w: number, h: number, soft = false, rot = 0) =>
  out.fx.push({ key, cw, ch, draw, x, y, z, w, h, soft, rot });
const puff = (out: Stage, f: number, f0: number, x: number, y: number, z: number, s = 1.2, len = 18) => {
  if (f < f0 || f >= f0 + len) return;
  const q2 = Math.round(((f - f0) / len) * 10) / 10;
  fx1(out, `puff|${q2}`, 300, 300, (p) => fxPuff(p, q2 * 0.9), x, y + 0.2 * q2, z, s * (0.7 + q2), s * (0.7 + q2), true);
};
const pop = (f: number, f0: number) => smooth((f - f0) / 5) * (1 + 0.15 * Math.max(0, 1 - (f - f0) / 8));
const count = (out: Stage, n: number | string, x: number, y: number, z: number, f: number, f0: number, s = 0.5) => {
  const k = pop(f, f0); if (k > 0) fx1(out, `count|${n}`, 240, 240, (p) => fxCount(p, n), x, y, z, s * k, s * k);
};
const gurgle = (out: Stage, t: number, x: number, y: number, z: number, s = 0.45) => { const u = Math.round(((t * 1.4) % 1) * 20) / 20; fx1(out, `gurgle|${u}`, 300, 300, (p) => fxGurgle(p, u), x, y, z, s, s); };
const feathers = (out: Stage, f: number, f0: number, x: number, y: number, z: number, n = 8, spread = 1.4) => {
  if (f < f0) return;
  const s = (f - f0) / FPS;
  if (s > 2.5) return;
  for (let k = 0; k < n; k++) { const a = (k / n) * Math.PI * 2 + 0.3, r = spread * Math.min(1, s * 2.2) * (0.6 + 0.4 * hh(k, 2)), sp = Math.round(((s * 2 + k * 0.4) % 1) * 12) / 12;
    fx1(out, `feather|${sp}`, 200, 120, (p) => fxFeather(p, sp * Math.PI * 2), x + Math.cos(a) * r, y + Math.sin(a) * r * 0.6 + 0.4 * s - 0.5 * s * s * 0.6, z + 0.25, 0.16, 0.1); }
};
const flock = (cam: CamInfo, t: number, out: Stage, cx: number, cz: number, n = 6, eye: HenOpts["eye"] = "norm", pecking = true) => {
  for (let i = 0; i < n; i++) { const x = cx + (i % 3) * 0.9 - 0.9 + hh(i, 1) * 0.4, z = cz + Math.floor(i / 3) * 0.9 - 0.4 + hh(i, 2) * 0.3;
    hen(cam, out, 520 + i, x, 0, z, { mode: pecking && i % 2 ? "peck" : "stand", phase: ph(t, i, 1.2, 8), head: true, eye, blink: lidAt(t, 520 + i), col: i % 3 === 2 ? "#e0a35a" : undefined }, [i % 2 ? 1 : -1, 0], 0.32); }
};

// 1: the hook: headless Mike crowing, then strutting at the lens; Lloyd frozen by the stump with the axe; hens agape
const hook = (cam: CamInfo, t: number, f: number, out: Stage) => {
  const m = hookMike(f), crowing = f < 16;
  mike(cam, out, t, m[0], 0, m[2], crowing ? "crow" : "walk", [-0.2, 1]);
  if (crowing || f >= 26) gurgle(out, t, m[0] - 0.12, 0.58, m[2] + 0.12, 0.26);
  stand(cam, out, 600, LLOYD, "lloyd", B[0] - 0.3, 0, B[2] - 0.6, { mode: "stand", expr: "shock", blink: 0, prop: ["axe", 0.5], look: 1 });
  for (let i = 0; i < 4; i++) hen(cam, out, 610 + i, -1.7 + i * 0.75 + (i > 1 ? 1.2 : 0), 0, 0.6 + (i % 2) * 0.7, { mode: "stand", head: true, eye: "shock", blink: 0, col: i % 2 ? "#e0a35a" : undefined }, [i < 2 ? 1 : -1, 0], 0.32);
};
const hookCrow = (cam: CamInfo, t: number, f: number, out: Stage) => {
  const m = hookMike(f);
  mike(cam, out, t, m[0], 0, m[2], "crow", [1, 0]);
  gurgle(out, t, m[0] + 0.1, 0.6, m[2] + 0.1, 0.28);
  hen(cam, out, 615, m[0] - 0.9, 0, m[2] - 1.0, { mode: "stand", head: true, eye: "shock", blink: 0 }, [1, 0], 0.32);
};
// 3: the farm wide; 4: Lloyd at the flock pointing at Mike (still with a head), Mike's "!"
const farm = (cam: CamInfo, t: number, f: number, out: Stage) => {
  flock(cam, t, out, FLOCK[0], FLOCK[2], 6);
  mike(cam, out, t, FLOCK[0] + 1.6, 0, FLOCK[2] + 0.3, "peck", [1, 0], true);
  walker(cam, out, 601, LLOYD, "lloyd", 3 - 1.1 * ((f - 70) / FPS), 0, 1.5, t, -1, 0, "smile");
};
const pick = (cam: CamInfo, t: number, f: number, out: Stage) => {
  flock(cam, t, out, FLOCK[0], FLOCK[2] - 0.4, 5);
  mike(cam, out, t, FLOCK[0] + 1.2, 0, FLOCK[2] + 0.4, S(f, 165) ? "stand" : "peck", [1, 0], true, 0.38, { eye: S(f, 165) ? "shock" : "norm" });
  stand(cam, out, 602, LLOYD, "lloyd", FLOCK[0] + 2.2, 0, FLOCK[2] + 0.7, { mode: "stand", expr: S(f, 177) ? "grin" : "neutral", blink: lidAt(t, 602), prop: S(f, 150) ? "point" : null, look: -1, facing: -1 });
  if (S(f, 165)) { const k = pop(f, 165); fx1(out, "exclaim", 200, 360, (p) => fxExclaim(p), FLOCK[0] + 1.25, 1.1, FLOCK[2] + 0.5, 0.14 * k, 0.25 * k); }
};
// 5: the mother-in-law at the table, knife and fork, licking her lips on "neck"
const milShot = (cam: CamInfo, t: number, f: number, out: Stage) => {
  stand(cam, out, 630, MIL, "mil", MIL_AT[0], 0, MIL_AT[2], { mode: "stand", expr: S(f, 247) ? "lick" : "smile", blink: lidAt(t, 630, [247 / FPS]), prop: S(f, 240) ? "present" : "crossed", look: 0, headTilt: S(f, 247) ? -6 : 0 });
};
// 6: Lloyd at the stump, the axe high; Mike's neck stretched long on the block; 7: whack; 8: Mike walks off
const aim = (cam: CamInfo, t: number, f: number, out: Stage) => {
  const stretch = S(f, 337);
  mike(cam, out, t, B[0] + 0.15, 0.62, B[2], stretch ? "crow" : "stand", [1, 0], true, 0.38, { eye: "shock" });
  const k = S(f, 299) ? 0 : 0.25;
  stand(cam, out, 640, LLOYD, "lloyd", LLOYD_BLOCK[0], 0, LLOYD_BLOCK[2], { mode: "stand", expr: S(f, 299) ? "stern" : "smile", blink: lidAt(t, 640), prop: ["axe", k], look: 1, facing: 1 });
  if (S(f, 299)) { const k2 = smooth((f - 297) / 8); fx1(out, "aim", 600, 120, (p) => fxAim(p), B[0] + 0.22, stretch ? 1.14 : 1.05, B[2] + 0.3, 1.3 * k2, 0.24); }
};
const whack = (cam: CamInfo, t: number, f: number, out: Stage) => {
  const hit = f >= 372;
  stand(cam, out, 641, LLOYD, "lloyd", LLOYD_BLOCK[0], 0, LLOYD_BLOCK[2], { mode: "stand", expr: hit ? "nervous" : "stern", blink: 0, prop: hit ? null : ["axe", 0.9], look: 1, facing: 1 });
  if (!hit) mike(cam, out, t, B[0] + 0.15, 0.62, B[2], "crow", [1, 0], true, 0.38, { eye: "shock" });
  else mike(cam, out, t, B[0] + 0.15, 0.62, B[2], "stand", [1, 0], false);
  if (hit && f < 386) { const u = Math.round(((f - 372) / 14) * 8) / 8; fx1(out, `flash|${u}`, 500, 500, (p) => fxFlashStar(p, u), B[0] + 0.25, 1.15, B[2] + 0.45, 1.2, 1.2); }
  feathers(out, f, 376, B[0] + 0.2, 1.15, B[2], 8, 1.0);
};
const walkoffShot = (cam: CamInfo, t: number, f: number, out: Stage) => {
  const m = walkoff(f);
  mike(cam, out, t, m[0], m[1], m[2], f < 396 ? "stand" : "walk", [1, 0.1]);
  stand(cam, out, 642, LLOYD, "lloyd", LLOYD_BLOCK[0] - 0.2, 0, LLOYD_BLOCK[2], { mode: "stand", expr: "shock", blink: 0, look: 1 });
  feathers(out, f, 360, B[0] + 0.2, 0.9, B[2], 6, 1.4);
};
// 9: morning, from the porch; 10: pecking among the hens; 11: the gurgling crow; 12: Lloyd's face
const morning = (cam: CamInfo, t: number, f: number, out: Stage) => {
  const m = morningMike(f);
  mike(cam, out, t, m[0], 0, m[2], "walk", [-1, 0]);
  flock(cam, t, out, -1.5, -5.2, 6, "shock", false);
  stand(cam, out, 650, LLOYD, "lloyd", PORCH[0] - 0.4, PORCH[1], PORCH[2] + 0.2, { mode: "stand", expr: S(f, 462) ? "shock" : "neutral", blink: lidAt(t, 650, [462 / FPS]), prop: null, look: -1 }, 1, false);
};
const peck = (cam: CamInfo, t: number, f: number, out: Stage) => {
  const m = morningMike(f);
  mike(cam, out, t, m[0], 0, m[2], "peck", [-1, 0]);
  for (let i = 0; i < 3; i++) hen(cam, out, 660 + i, m[0] - 1.0 - i * 0.7, 0, m[2] - 0.6 + i * 0.3, { mode: "stand", head: true, eye: "shock", blink: 0, col: i === 1 ? "#e0a35a" : undefined }, [1, 0], 0.32);
};
const crow = (cam: CamInfo, t: number, f: number, out: Stage) => {
  const m = morningMike(f);
  mike(cam, out, t, m[0], 0, m[2], "crow", [-1, 0]);
  gurgle(out, t, m[0] - 0.1, 0.72, m[2] + 0.06, 0.38);
};
const nohead = (cam: CamInfo, t: number, f: number, out: Stage) => {
  stand(cam, out, 651, LLOYD, "lloyd", PORCH[0], PORCH[1], PORCH[2], { mode: "stand", expr: "shock", blink: 0, look: 0 }, 1, false);
};
const wait = (cam: CamInfo, t: number, f: number, out: Stage) => {
  stand(cam, out, 652, LLOYD, "lloyd", PORCH[0] + 0.3, PORCH[1], PORCH[2], { mode: "stand", expr: f < 615 ? "dazed" : "nervous", blink: lidAt(t, 652), prop: ["scratch", Math.round((0.5 + 0.5 * Math.sin(t * 12)) * 4) / 4], look: 0 }, 1, false);
  if (f >= 606) { const k = smooth((f - 606) / 8), wob = 0.08 * Math.sin(t * 8); out.fx.push({ key: "question", cw: 240, ch: 360, draw: (p) => fxQuestion(p), x: PORCH[0] + 0.8, y: PORCH[1] + 2.15, z: PORCH[2] + 0.2, w: 0.24 * k, h: 0.36 * k, rot: wob }); }
};
// 14-15: Mike on the stump, a diagram card beside him
const vein = (cam: CamInfo, t: number, f: number, out: Stage) => {
  mike(cam, out, t, B[0] - 0.25, 0.62, B[2] + 0.35, "stand", [1, 0]);
  const st = S(f, 735) ? 2 : S(f, 684) ? 1 : 0, k = smooth((f - 664) / 8);
  fx1(out, `vein|${st}`, 600, 700, (p) => fxVein(p, st), B[0] + 0.2, 1.78, B[2] + 0.3, 1.0 * k, 1.17 * k);
};
const stem = (cam: CamInfo, t: number, f: number, out: Stage) => {
  mike(cam, out, t, B[0] - 0.25, 0.62, B[2] + 0.35, f >= 884 ? "walk" : "stand", [1, 0]);
  const st = S(f, 884) ? 3 : S(f, 867) ? 2 : S(f, 842) ? 1 : 0;
  fx1(out, `stem|${st}`, 600, 700, (p) => fxStem(p, st), B[0] + 0.2, 1.78, B[2] + 0.3, 1.0, 1.17);
};
// 16: the desk: a hand pulls the plug (the man at the desk), the screen goes dark, the lights keep blinking
const desk = (cam: CamInfo, t: number, f: number, out: Stage) => {
  stand(cam, out, 670, LLOYD, "lloyd", DESK_AT[0] - 0.95, 0, DESK_AT[2] + 0.75, { mode: "stand", expr: f >= DARK_AT + 25 ? "grin" : f >= DARK_AT ? "shock" : "neutral", blink: lidAt(t, 670), prop: f >= UNPLUG_AT && f < DARK_AT + 20 ? "point" : null, look: 1, facing: 1 });
};
// 17: Lloyd feeding Mike with the eyedropper; drops falling into the neck
const dropper = (cam: CamInfo, t: number, f: number, out: Stage) => {
  mike(cam, out, t, B[0] + 0.25, 0.62, B[2], "drink", [-1, 0]);
  stand(cam, out, 680, LLOYD, "lloyd", B[0] - 0.55, 0, B[2] + 0.25, { mode: "stand", expr: "smile", blink: lidAt(t, 680), prop: "dropper", look: 1, facing: 1 });
  if (f >= 1100) for (let k = 0; k < 2; k++) { const u = (((f - 1100) / 14 + k * 0.5) % 1); fx1(out, "drop", 60, 90, (p) => fxDrop(p), B[0] + 0.15, 1.42 - 0.3 * u, B[2] + 0.25, 0.07, 0.105); }
  fx1(out, "bigDropper", 120, 400, (p) => fxDropper(p), B[0] + 0.12, 1.62, B[2] + 0.26, 0.1, 0.34, false, 0.35);
};
// 18: the weigh-in: Mike swells on the platform, the dial swings from 2.5 to 8
const scale = (cam: CamInfo, t: number, f: number, out: Stage) => {
  const lb = lbAt(f), sc = 0.28 + 0.2 * ((lb - 2.5) / 5.5);
  if (f < 1222) count(out, "2.5 lb", SCALE.x + 0.35, 0.85, SCALE.z + 0.1, f, 1190, 0.34); else count(out, "8 lb", SCALE.x + 0.35, 0.85, SCALE.z + 0.1, f, 1226, 0.38);
  mike(cam, out, t, SCALE.x, 0.12, SCALE.z - 0.05, "stand", [1, 0], false, sc);
  fx1(out, `dial|${Math.round(lb * 4) / 4}`, 300, 300, (p) => fxScale(p, lb), SCALE.x, 1.25, SCALE.z - 0.25, 0.42, 0.42);
};
// 19-21: the sideshow: the crowd at the tent; paying 25 cents; the photographer's flash
const tour = (cam: CamInfo, t: number, f: number, out: Stage) => {
  mike(cam, out, t, SHOW_MIKE[0], SHOW_MIKE[1], SHOW_MIKE[2], "crow", [1, 0]);
  stand(cam, out, 690, SHOWMAN, "showman", SHOW.x - 1.5, 0, SHOW.z - 1.4, { mode: "stand", expr: "grin", blink: lidAt(t, 690), prop: "present", look: 1, facing: 1 });
  for (let i = 0; i < 10; i++) stand(cam, out, 700 + i, folk(i), `folk${i % 12}`, SHOW.x - 4 + (i % 5) * 2.0 + hh(i, 1), 0, SHOW.z + 2.5 + Math.floor(i / 5) * 1.6, { mode: "stand", expr: (["shock", "grin", "laugh", "nervous"] as Expr[])[i % 4], blink: lidAt(t, 700 + i), prop: i % 3 === 1 ? "point" : null });
};
const queue = (cam: CamInfo, t: number, f: number, out: Stage) => {
  stand(cam, out, 691, LLOYD, "lloyd", SHOW.x + 4.1, 0, SHOW.z + 0.9, { mode: "stand", expr: "grin", blink: lidAt(t, 691), prop: "palm", look: -1 });
  for (let i = 0; i < 5; i++) { const k = Math.max(0, (f - 1286 - i * 10) / FPS); stand(cam, out, 710 + i, folk(i + 3), `folk${(i + 3) % 12}`, SHOW.x + 2.9 - i * 0.9 + Math.min(0.5, k * 0.3), 0, SHOW.z + 1.6 + i * 0.25, { mode: "stand", expr: i ? "smile" : "grin", blink: lidAt(t, 710 + i), prop: i === 0 ? "cash" : null }); }
  count(out, "25¢", SHOW.x + 3.4, 2.2, SHOW.z + 1.0, f, 1293, 0.42);
};
const photo = (cam: CamInfo, t: number, f: number, out: Stage) => {
  mike(cam, out, t, SHOW_MIKE[0], SHOW_MIKE[1], SHOW_MIKE[2], "crow", [1, 0]);
  stand(cam, out, 692, PHOTOG, "photog", SHOW_MIKE[0] + 1.0, 0, SHOW_MIKE[2] + 0.8, { mode: "stand", expr: "grin", blink: lidAt(t, 692), prop: "camera", look: -1, facing: -1 });
  for (const a of [1378, 1392]) if (f >= a && f < a + 8) { const u = Math.round(((f - a) / 8) * 8) / 8; fx1(out, `flash|${u}`, 500, 500, (p) => fxFlashStar(p, u), SHOW_MIKE[0] + 0.78, 1.18, SHOW_MIKE[2] + 1.0, 0.7, 0.7); }
};
// 22: Lloyd fanning his cash, bills raining down, the $4,500 tag
const money = (cam: CamInfo, t: number, f: number, out: Stage) => {
  stand(cam, out, 693, LLOYD, "lloyd", SHOW.x + 3.7, 0, SHOW.z + 0.9, { mode: "stand", expr: "grin", blink: lidAt(t, 693), prop: "cash", look: 0 });
  for (let k = 0; k < 10; k++) { const u = (((f - 1407) / 40 + hh(k, 3)) % 1); fx1(out, "bill", 260, 120, (p) => fxBill(p), SHOW.x + 2.9 + hh(k, 1) * 1.6, 2.8 - 2.6 * u, SHOW.z + 1.2 + hh(k, 2) * 0.3, 0.26, 0.12, false, Math.sin(f * 0.2 + k) * 0.6); }
  const k = pop(f, 1421); if (k > 0) fx1(out, "tag4500", 320, 200, (p) => fxTag(p, "$4,500"), SHOW.x + 3.62, 2.05, SHOW.z + 1.15, 0.7 * k, 0.44 * k);
};
// 23-24: the copycats: three farmers with axes chasing their chickens; then the 11-day count and their sad faces
const copy = (cam: CamInfo, t: number, f: number, out: Stage) => {
  const s = (f - 1481) / FPS;
  hen(cam, out, 735, COPY.x + 2.6, 0.62, COPY.z - 0.6, { mode: "stand", head: true, eye: "shock", blink: 0 }, [-1, 0], 0.32, false);
  stand(cam, out, 736, COPYF[2], "copy2b", COPY.x + 3.5, 0, COPY.z - 0.5, { mode: "stand", expr: "stern", blink: lidAt(t, 736), prop: ["axe", 0], look: -1, facing: -1 });
  for (let i = 0; i < 4; i++) hen(cam, out, 720 + i, COPY.x - 4 + i * 2.2 + 2.8 * s, 0, COPY.z - 1.0 + (i % 2) * 1.2, { mode: "run", phase: ph(t, i, 3, 8), head: true, eye: "shock", blink: 0, col: i % 2 ? "#e0a35a" : undefined }, [1, 0], 0.32);
  COPYF.forEach((o, i) => stand(cam, out, 725 + i, o, `copy${i}`, COPY.x - 5.2 + i * 2.2 + 2.6 * s, 0, COPY.z - 0.4 + (i % 2) * 1.0, { mode: "stroll", phase: ph(t, i, 2, 12), expr: "stern", prop: ["axe", 0.15], blink: 0 }));
};
const eleven = (cam: CamInfo, t: number, f: number, out: Stage) => {
  COPYF.forEach((o, i) => stand(cam, out, 730 + i, o, `copy${i}`, COPY.x - 0.9 + i * 0.9, 0, COPY.z - 0.3 + (i % 2) * 0.4, { mode: "stand", expr: (["pained", "nervous", "pained"] as Expr[])[i], blink: lidAt(t, 730 + i), prop: i === 1 ? "facepalm" : ["axe", 0.9] }));
  count(out, "11", COPY.x + 0.45, 2.1, COPY.z + 0.2, f, 1588, 0.4);
};
// 25: the motel at night: Lloyd asleep (Zzz), Mike in his box coughing; Lloyd wakes on "choke"
const motel = (cam: CamInfo, t: number, f: number, out: Stage) => {
  const awake = f >= 1673;
  sit(cam, out, 740, LLOYD_NIGHT, "lloydN", MOTEL.x - 0.6, 0.62, MOTEL.z - 1.6, { expr: awake ? "shock" : "relief", blink: awake ? 0 : 1, look: 1 });
  if (!awake) { const u = Math.round(((t * 0.5) % 1) * 20) / 20; fx1(out, `zzz|${u}`, 240, 240, (p) => fxZzz(p, u), MOTEL.x - 0.45, 1.95, MOTEL.z - 1.5, 0.4, 0.4); }
  mike(cam, out, t, MOTEL.x + 1.05, 0.8, MOTEL.z - 2.2, f >= 1668 ? "crow" : "stand", [-1, 0], false, 0.34);
  if (f >= 1668) { const u = Math.round((((f - 1668) / 12) % 1) * 10) / 10; fx1(out, `cough|${u}`, 300, 300, (p) => fxCough(p, u), MOTEL.x + 0.88, 1.34, MOTEL.z - 2.05, 0.34, 0.34);
    const k = pop(f, 1670); fx1(out, "exclaim", 200, 360, (p) => fxExclaim(p), MOTEL.x + 0.98, 1.6, MOTEL.z - 2.05, 0.07 * k, 0.13 * k); }
};
const syringe = (_cam: CamInfo, _t: number, _f: number, _out: Stage) => {};
const facepalm = (cam: CamInfo, t: number, f: number, out: Stage) => {
  stand(cam, out, 741, LLOYD_NIGHT, "lloydN", MOTEL.x + 1.0, 0, MOTEL.z - 1.0, { mode: "stand", expr: "pained", blink: lidAt(t, 741), prop: "facepalm", look: 0 });
};
// 28: the festival: the statue of headless Mike on its plinth, runners in the street
const fest = (cam: CamInfo, t: number, f: number, out: Stage) => {
  hen(cam, out, 750, FEST_STATUE[0], FEST_STATUE[1], FEST_STATUE[2], { mode: "crow", head: false, col: "#a8b0b8", proud: true }, [1, 0], 3.0, false);
  for (let i = 0; i < 12; i++) { const x = FEST.x + 14 - ((t * (2.5 + hh(i, 1)) + i * 3.1) % 30), z = FEST.z - 4 + (i % 4) * 2.2 + hh(i, 2); runner(cam, out, 760 + i, folk(i), `folk${i % 12}`, x, z, t, -1, 0, i % 3 ? "laugh" : "grin"); }
  for (let i = 0; i < 3; i++) hen(cam, out, 780 + i, FEST.x + 10 - ((t * 3 + i * 7) % 26), 0, FEST.z + 3 + i * 0.8, { mode: "run", phase: ph(t, i, 3, 8), head: true, eye: "happy" }, [-1, 0], 0.32);
};
// 29: dinner: the mother-in-law with an empty plate, arms crossed; headless Mike walks across the table past her
const dinner = (cam: CamInfo, t: number, f: number, out: Stage) => {
  stand(cam, out, 790, MIL, "mil", MIL_AT[0], 0, MIL_AT[2], { mode: "stand", expr: f >= 1952 ? "stern" : "pained", blink: lidAt(t, 790), prop: "crossed", look: f >= 1925 ? (DINNER_MIKE(f)[0] < MIL_AT[0] ? -1 : 1) : 0, headTilt: f >= 1952 ? 6 : 0 });
  if (f >= 1925) { const m = DINNER_MIKE(f); mike(cam, out, t, m[0], m[1], m[2], "walk", [1, 0], false, 0.36); }
};

/** everything with a face (and every 2D effect) in shot `id` at time t */
export const stage = (id: number, t: number, f: number, cam: CamInfo): Stage => {
  const out: Stage = { places: [], fx: [] };
  const s = SHOTS[id - 1];
  LNAME = s.light;
  findSun(cam, SUN);
  const fn: Record<string, (c: CamInfo, t: number, f: number, o: Stage) => void> = {
    hook, hookCrow, farm, pick, mil: milShot, aim, whack, walkoff: walkoffShot, morning, peck, crow, nohead, wait, vein, stem, desk, dropper, scale,
    tour, queue, photo, money, copy, eleven, motel, syringe, facepalm, fest, dinner,
  };
  fn[s.crowd]?.(cam, t, f, out);
  return out;
};
export { FPS, clamp01, NOINK };
