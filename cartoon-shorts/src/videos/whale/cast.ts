import type { LightName } from "./lights";
// The exploding-whale cast as lit flat sprites in the 3D world. Each frame every character asks for a drawing (a key + a draw
// call); the pool keeps one canvas per distinct drawing, so emus in step share canvases. People are yaw-only
// billboards on the 600 x 1000 card, emus on the WIDE 1000 x 1000 card; both are shaded by cardShade() and stand on a
// soft multiply contact blob. Effects are unlit cards. Everything lives on the NOINK layer (no world ink on quads).
import * as THREE from "three";
import {
  Pen, bodyFront, bodySide, fxShadow, fxContact, fxBurst, fxStars, fxPuff, fxQuestion,
  engineer, rider, tourist, CAMERAMAN, KID, PARENT, INK, Outfit, Expr, FrontOpts, SideOpts, Prop,
} from "./toon";
import { gullSide, GullOpts, fxBoom, fxStink, fxFlies, fxSplat, fxPlan, fxCount, fxStick } from "./whaledraw";
import {
  FPS, SHOTS, clamp01, smooth, V3, blastS, BLAST, THORNTON_PL, TV_AT, WALTER_LOT, STINKERS, THORNTON_AT, WALTER_AT, THORNTON_W, WORKERS,
  hwyTruckX, backK, LUMP_HIT, HAMMER_AT, KIT_TABLE, PARK_SIGN, DEAL_CAR, QUOTE_AT, casesAt,
} from "./story";
import { WHALE, LOT, CAR, PLUNGER, HTRUCK, DYN, KITCHEN, PARK, DEALER } from "./places";
import { Chunks } from "./beach";
import { CHUNKS, LOT_HITS, THORNTON_HIT, NEAR_HIT } from "./chunks";
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

// ---------------- the exploding-whale cast ----------------
const S = (f: number, a: number) => f >= a - 2; // a reaction lands 0-3 f before its word
const sit = (cam: CamInfo, out: Stage, i: number, o: Outfit, okey: string, x: number, y: number, z: number, fo: FrontOpts, scale = 1) =>
  stand(cam, out, i, o, okey, x, y, z, { ...fo, mode: "sit" }, scale, false);
/** a side-view person facing along (dirX, dirZ) */
const side = (cam: CamInfo, out: Stage, i: number, o: Outfit, okey: string, x: number, y: number, z: number, dirX: number, dirZ: number, so: SideOpts, shadow = true) => {
  const mirror = dirX * cam.right.x + dirZ * cam.right.z < 0;
  out.places.push(person(cam, { i, o, okey }, x, y, z, { side: true, mirror }, {}, so));
  if (shadow) blob(out, x, y, z);
};
/** a running person (front view toward the lens, side view across it) */
const runner = (cam: CamInfo, out: Stage, i: number, o: Outfit, okey: string, x: number, z: number, t: number, dx: number, dz: number, expr: Expr) => {
  const view = viewOf(cam, x, z, dx, dz), ph = q(((t * 3.2 + hh(i, 5)) % 1 + 1) % 1, 12);
  out.places.push(person(cam, { i, o, okey }, x, 0, z, view, { mode: "stroll", phase: ph, expr, blink: 0, wave: i % 2 ? Math.sin(t * 20 + i) : undefined, headTilt: 6 * Math.sin(t * 9 + i) },
    { mode: "march", phase: ph, expr, blink: 0, stomp: 0.9, stride: 1.1 * view.fs }));
  blob(out, x, 0, z);
};
const THORNTON: Outfit = { jacket: "#4f5566", pants: "#3f4454", boots: INK, hat: "hardhat", cap: "#f4f1ea", tie: "#c0353a", buttons: "#d9dde0", skin: "#f5c9a0", build: "stout" };
const WALTER: Outfit = { jacket: "#7a5034", pants: "#4a4038", boots: "#3a2a22", hat: "cap", cap: "#5a6a4a", medal: "#3f6fb5", moustache: "#8a7a6a", skin: "#ecb88e", buttons: "#c9a24a" };
const WALTER_BARE: Outfit = { ...WALTER, hat: "hair", hair: "#9a9590" };
const REPORTER: Outfit = { jacket: "#c98a3a", pants: "#3f4454", boots: "#3a2a22", hat: "hair", hair: "#2a1c18", tie: "#3f6fb5", buttons: "#d9dde0", skin: "#ffe2c2" };
const SALESMAN: Outfit = { jacket: "#d9a441", pants: "#5a4a3a", boots: "#3a2a22", hat: "hair", hair: "#c9925a", tie: "#c0353a", moustache: "#5a3b2a", buttons: "#f4f1ea", build: "stout", skin: "#f5c9a0" };
const DAD: Outfit = { jacket: "#3f6fb5", pants: "#3b3f52", boots: "#3a2a22", hat: "hair", hair: "#5a3b2a", moustache: "#5a3b2a", skin: "#f5c9a0" };
const MUM: Outfit = { ...PARENT, hat: "hair", hair: "#c9925a", dress: "#e2453c", jacket: "#e2453c", skin: "#ffe2c2" };
const KID2: Outfit = { ...KID, jacket: "#5d9a3a", cap: "#f2c230" };
const WORK = [0, 2, 3].map((v) => engineer(v));
const folk = (i: number): Outfit => (i % 2 ? rider(i) : tourist(i));

/** one gull card (side view, mirrored to face its direction), ~0.65 m tall */
const gull = (cam: CamInfo, out: Stage, i: number, x: number, y: number, z: number, o: GullOpts, dir: [number, number], scale = 0.3, shadow = true) => {
  const d = cam.pos.distanceTo(tmp.set(x, y + 0.3, z)) / scale;
  const k = tier(d)[2];
  const mirror = dir[0] * cam.right.x + dir[1] * cam.right.z < 0;
  const light = light2D(cam, mirror), oo: GullOpts = { ...o, light };
  out.places.push({ key: `G|${fkey(oo)}`, x, y, z, scale, mirror, geo: "wide", size: [Math.max(60, Math.round(1000 * k)), Math.max(60, Math.round(1000 * k)), k], draw: (p) => gullSide(p, oo) });
  if (shadow && y < 0.1) blob(out, x, y, z, 0.5);
};
const ph = (t: number, i: number, rate: number, n = 12) => Math.round((((t * rate + hh(i, 5)) % 1) + 1) % 1 * n) / n;
const fx1 = (out: Stage, key: string, cw: number, ch: number, draw: (p: Pen) => void, x: number, y: number, z: number, w: number, h: number, soft = false, rot = 0) =>
  out.fx.push({ key, cw, ch, draw, x, y, z, w, h, soft, rot });
const puff = (out: Stage, f: number, f0: number, x: number, y: number, z: number, s = 1.2, len = 18) => {
  if (f < f0 || f >= f0 + len) return;
  const q2 = Math.round(((f - f0) / len) * 10) / 10;
  fx1(out, `puff|${q2}`, 300, 300, (p) => fxPuff(p, q2 * 0.9), x, y + 0.2 * q2, z, s * (0.7 + q2), s * (0.7 + q2), true);
};
const count = (out: Stage, n: number | string, x: number, y: number, z: number, f: number, f0: number, s = 0.5) => {
  const k = smooth((f - f0) / 5) * (1 + 0.15 * Math.max(0, 1 - (f - f0) / 8));
  if (k > 0) fx1(out, `count|${n}`, 240, 240, (p) => fxCount(p, n), x, y, z, s * k, s * k);
};
/** the blast cloud at s seconds: a growing fireball turning to smoke, card slid toward the camera so it covers the crater */
const boom = (cam: CamInfo, out: Stage, s: number, scale = 1) => {
  if (s < 0 || s > 12) return;
  const t = Math.round(Math.min(1, s / 2.4) * 24) / 24, w = (9 + 30 * smooth(s / 1.4) + 3 * Math.max(0, s - 1.4)) * scale;
  const a = Math.round(clamp01(1.25 - (s - 3) / 7) * 10) / 10;
  const dx = cam.pos.x - WHALE.x, dz = cam.pos.z - WHALE.z, dl = Math.hypot(dx, dz) || 1;
  out.fx.push({ key: `boom|${t}|${a}`, cw: 1000, ch: 1000, draw: (p) => { p.g.globalAlpha = a; fxBoom(p, t); p.g.globalAlpha = 1; }, x: WHALE.x - (dx / dl) * 5, y: 0.485 * w, z: WHALE.z - (dz / dl) * 5, w, h: w, soft: a < 1, upright: true });
};
/** a blubber splat on the sand where a chunk came down (after it lands) */
const splats = (out: Stage, s: number, list: { x: number; z: number; t: number; s: number }[]) => {
  list.forEach((h, k) => { if (s >= h.t) out.fx.push({ key: `splat|${k % 4}`, cw: 400, ch: 400, draw: (p) => fxSplat(p, k % 4), x: h.x, y: 0.03, z: h.z, w: 2.6 * h.s + 0.6, h: 2.6 * h.s + 0.6, flat: true, rot: k }); });
};
const LOT_PEOPLE = 26;
const lotSpot = (i: number): [number, number] => {
  const x = 13 + (i % 9) * 5.2 + hh(i, 1) * 2.2, z = 50.5 + Math.floor(i / 9) * 2.4 + hh(i, 2) * 1.2;
  return [x > 42 && x < 50 && z > 55 ? x - 6 : x, z];
};
/** the lot crowd: `phase` watch (front), back (side, facing the whale), run (toward +z), or the walk back from the beach */
const crowd = (cam: CamInfo, t: number, f: number, out: Stage, mode: "watch" | "back" | "run" | "walk", s = 0, k = 1) => {
  for (let i = 0; i < LOT_PEOPLE; i++) {
    const [x0, z0] = lotSpot(i), o = folk(i), key = `folk${i % 12}`;
    if (mode === "walk") {
      const z = 30 + (z0 - 30) * k, x = 28 + (x0 - 28) * 0.3;
      if (k < 1) out.places.push(person(cam, { i, o, okey: key }, x, 0, z, { side: false, mirror: false }, { mode: "stroll", phase: ph(t, i, 1.4), expr: i % 3 ? "nervous" : "neutral", blink: lidAt(t, i), look: 0 }, {}));
      else out.places.push(person(cam, { i, o, okey: key }, x, 0, z, { side: false, mirror: false }, { mode: "stand", expr: i % 3 ? "nervous" : "grin", blink: lidAt(t, i) }, {}));
      blob(out, x, 0, z);
    } else if (mode === "watch") stand(cam, out, i, o, key, x0, 0, z0, { mode: "stand", expr: (["grin", "nervous", "neutral", "shh"] as Expr[])[i % 3] ?? "grin", blink: lidAt(t, i), prop: i % 4 === 1 ? "shh" : null });
    else if (mode === "back") side(cam, out, i, o, key, x0, 0, z0, WHALE.x - x0, WHALE.z - z0, { mode: "stand", expr: "grin", blink: 0 });
    else {
      const go = Math.max(0, s - 0.85 - 0.25 * hh(i, 3)), v = 4.2 + 1.2 * hh(i, 4), z = z0 + v * go, x = x0 + (hh(i, 6) - 0.5) * 1.2 * go;
      if (go <= 0) side(cam, out, i, o, key, x0, 0, z0, WHALE.x - x0, WHALE.z - z0, { mode: "stand", expr: "shock", blink: 0 });
      else if ((i % 7 === 3 && go > 1.2) || (i === 4 && s >= NEAR_HIT.t)) { const g2 = i === 4 ? NEAR_HIT.t - 0.85 - 0.25 * hh(4, 3) : 1.2; stand(cam, out, i, o, key, x0 + (hh(i, 6) - 0.5) * 1.2 * g2, 0, z0 + v * g2, { mode: "fall", expr: i === 4 ? "dazed" : "shock", blink: 0 }); }
      else runner(cam, out, i, o, key, x, z, t, 0, 1, "shock");
    }
  }
};
const lotGulls = (cam: CamInfo, t: number, out: Stage, s: number) => {
  for (let i = 0; i < 14; i++) {
    const a = 0.3 + 0.12 * i, u = Math.max(0, s - 0.1), r = 6 + 9 * u + i * 0.8;
    gull(cam, out, 600 + i, WHALE.x + Math.cos(a) * r * 0.9 + 4, 3 + 6 * u + (i % 4) * 1.5, WHALE.z + Math.sin(a) * r + 6, { mode: "fly", phase: ph(t, i, 4, 8), eye: "shock" }, [Math.cos(a), Math.sin(a)], 0.45, false);
  }
};

// 1: the hook: mid-blast, the crowd running at the lens, blubber flying overhead
const hook = (cam: CamInfo, t: number, f: number, out: Stage) => {
  const s = blastS(1, f) + 1.3;
  boom(cam, out, blastS(1, f), 0.85);
  const ax = WHALE.x + 5 - cam.pos.x, az = WHALE.z - cam.pos.z, al = Math.hypot(ax, az), ux = ax / al, uz = az / al;
  for (let k = 0; k < 8; k++) {
    const d = 11 + k * 3.6 - 4.6 * (f / FPS), lat = ((k % 3) - 1) * 0.5 * d * 0.13 + (k === 0 ? 0.35 : 0);
    runner(cam, out, 690 + k, folk(k + 1), `folk${(k + 1) % 12}`, cam.pos.x + ux * d - uz * lat, cam.pos.z + uz * d + ux * lat, t, -ux, -uz, k % 3 === 1 ? "laugh" : "shock");
  }
  lotGulls(cam, t, out, s);
  stand(cam, out, 700, CAMERAMAN, "tvcam", TV_AT[0], 0, TV_AT[2] + 1.0 + 3 * Math.max(0, s - 1.2), { mode: "stand", expr: "shock", blink: 0, prop: "camera" });
};
// 2: "On purpose.": Thornton at the plunger, proud, a chunk smacking down beside him
const purpose = (cam: CamInfo, t: number, f: number, out: Stage) => {
  const s = blastS(2, f), hit = s >= THORNTON_HIT.t;
  boom(cam, out, s, 1.0);
  stand(cam, out, 710, THORNTON, "thornton", THORNTON_PL[0], 0, THORNTON_PL[2], { mode: "stand", expr: hit && f < 60 ? "relief_open" : "grin", blink: lidAt(t, 710), prop: "clipboard", headTilt: -5 });
  if (hit) { const k = Math.round(((s - THORNTON_HIT.t) / 0.5) * 8) / 8; if (k < 1) fx1(out, `burst|${k}`, 500, 500, (p) => fxBurst(p, k, "#f2c9be", 10), THORNTON_HIT.x - 0.3, 0.5, THORNTON_HIT.z + 0.4, 1.6, 1.6); }
  splats(out, s, [THORNTON_HIT]);
  for (let i = 0; i < 6; i++) { const [x0, z0] = lotSpot(i), go = Math.max(0, s - 0.9); runner(cam, out, i, folk(i), `folk${i % 12}`, x0, z0 + 4.5 * go, t, 0, 1, "shock"); }
};
// 3: the beach from high up: the whale small on the sand, gulls circling; 4: the bus beside the whale
const coastGulls = (cam: CamInfo, t: number, out: Stage, n = 8, sc = 0.45) => {
  for (let i = 0; i < n; i++) { const a = t * 0.5 + (i / n) * Math.PI * 2; gull(cam, out, 620 + i, WHALE.x + Math.cos(a) * (5 + i % 3 * 2), 6 + (i % 3) * 1.6, WHALE.z + Math.sin(a) * 4, { mode: "fly", phase: ph(t, i, 3, 8) }, [-Math.sin(a), Math.cos(a)], sc, false); }
};
const onWhale: [number, number][] = [[-3.2, -0.2], [-1.6, 0.4], [0.2, -0.3], [1.8, 0.3], [3.4, -0.2]];
const whaleGulls = (cam: CamInfo, t: number, out: Stage, eye: GullOpts["eye"] = "norm", sc = 0.3) => {
  onWhale.forEach(([dx, dz], i) => {
    const u = (dx + 7) / 14, hy = u > 0.62 ? 1.43 : 0.18 + 1.25 * Math.sin(Math.min(1, u / 0.62) * Math.PI / 2) ** 1.4;
    gull(cam, out, 640 + i, WHALE.x + dx, hy * 1.75 - 0.08, WHALE.z + dz, { mode: i % 2 ? "peck" : "stand", phase: ph(cam.pos.x > -100 ? t : 0, i, 0.8, 8), eye, blink: lidAt(t, 640 + i) }, [i % 2 ? 1 : -1, 0], sc, false);
  });
};
const coast = (cam: CamInfo, t: number, f: number, out: Stage) => { coastGulls(cam, t, out, 10, 0.6); whaleGulls(cam, t, out); };
const busShot = (cam: CamInfo, t: number, f: number, out: Stage) => {
  whaleGulls(cam, t, out);
  for (let i = 0; i < 3; i++) gull(cam, out, 650 + i, -6 + i * 4.2, 0, 4.2 + i * 0.6, { mode: "walk", phase: ph(t, i, 1.4, 8) }, [1, 0]);
  coastGulls(cam, t, out, 5);
};
// 5: two locals at the whale's head fanning the smell; stink lines and flies
const stink = (cam: CamInfo, t: number, f: number, out: Stage) => {
  STINKERS.forEach(([x, , z], i) => stand(cam, out, 720 + i, folk(i + 3), `stink${i}`, x, 0, z, { mode: "stand", expr: S(f, 284) ? "pained" : "neutral", blink: lidAt(t, 720 + i, [284 / FPS]), wave: S(f, 284) ? Math.sin(t * 18 + i) : undefined, prop: i === 1 && S(f, 284) ? "facepalm" : null, look: -1 }));
  for (let k = 0; k < 3; k++) { const u = Math.round(((t * 0.7 + k * 0.33) % 1) * 20) / 20; fx1(out, `stink|${u}`, 300, 400, (p) => fxStink(p, u), WHALE.x + 4.8 + k * 0.9, 3.1 + k * 0.25, WHALE.z + 1.8, 0.75, 1.0); }
  const fl = Math.round(((t * 0.5) % 1) * 30) / 30; fx1(out, `flies|${fl}`, 400, 300, (p) => fxFlies(p, fl), WHALE.x + 6.0, 2.2, WHALE.z + 1.9, 1.0, 0.75);
  whaleGulls(cam, t, out);
};
// 6: the highway sign; a red sedan cruising the beach behind it
const highway = (cam: CamInfo, t: number, f: number, out: Stage) => { coastGulls(cam, t, out, 4); };
// 7: the highway truck rolls in; three workers hop out and stare at the whale
const dept = (cam: CamInfo, t: number, f: number, out: Stage) => {
  const tx = hwyTruckX(7, f);
  if (f < 412) puff(out, f, Math.floor(f / 5) * 5, tx - 3.4, 0, HTRUCK.z + 0.6, 1.6, 5);
  if (f >= 414) WORKERS.forEach(([x, , z], i) => {
    const k = smooth((f - 414 - i * 4) / 18), xx = HTRUCK.x + 1.2 + (x - HTRUCK.x - 1.2) * k, zz = HTRUCK.z + 1.3 + (z - HTRUCK.z - 1.3) * k;
    stand(cam, out, 730 + i, WORK[i], `work${i}`, xx, 0, zz, { mode: k < 1 ? "stroll" : "stand", phase: ph(t, i, 1.6), expr: S(f, 434) ? (i === 1 ? "shock" : "nervous") : "neutral", blink: lidAt(t, 730 + i, [434 / FPS]), prop: i === 0 && S(f, 434) ? ["scratch", Math.round((0.5 + 0.5 * Math.sin(t * 12)) * 4) / 4] : null, look: 1 });
  });
  whaleGulls(cam, t, out);
};
// 8-9: Thornton and his plan (a thought cloud: the whale, then little pieces); 10: the gulls on the whale, greedy
const plan = (cam: CamInfo, t: number, f: number, out: Stage, pieces: boolean) => {
  const T = THORNTON_AT, talk = Math.round((0.5 + 0.5 * Math.sin(t * 9)) * 3) / 3;
  stand(cam, out, 740, THORNTON, "thornton", T[0], 0, T[2], { mode: "stand", expr: pieces ? (f >= 570 ? "grin" : "smile") : f >= 485 ? "smile" : "neutral", blink: lidAt(t, 740), prop: pieces && f >= 560 ? "point" : "clipboard", look: 1, headTilt: pieces ? -4 : 0 });
  if (pieces || f >= 517) {
    const step = !pieces ? 0 : f >= 563 ? 2 : 1, k = smooth((f - (pieces ? 536 : 517)) / 8);
    fx1(out, `plan|${step}`, 600, 500, (p) => fxPlan(p, step), T[0] + 0.62, 2.4 + 0.03 * Math.sin(t * 3), T[2] + 0.1, 0.95 * (pieces ? 1 : k), 0.8 * (pieces ? 1 : k));
  }
  void talk;
};
const gulls = (cam: CamInfo, t: number, f: number, out: Stage) => whaleGulls(cam, t, out, f >= 600 ? "greedy" : "norm", 0.32);
// 11: the dynamite going in; workers carrying cases, Thornton pointing
const dyn = (cam: CamInfo, t: number, f: number, out: Stage) => {
  stand(cam, out, 750, WORK[0], "work0", DYN.x + 2.1, 0, DYN.z + 0.9, { mode: "stand", expr: "grin", blink: lidAt(t, 750), look: -1 });
  stand(cam, out, 751, THORNTON, "thornton", DYN.x - 2.0, 0, DYN.z + 1.3, { mode: "stand", expr: S(f, 657) ? "grin" : "smile", blink: lidAt(t, 751), prop: "point", look: 1, facing: 1 });
  const n = casesAt(11, f);
  if (n >= 20) count(out, "½ t", DYN.x, 2.3, DYN.z + 0.4, f, 657, 0.6);
};
// 12: Walter warns: palm out, three sticks fanned in his other hand; Thornton waves it off
const walter = (cam: CamInfo, t: number, f: number, out: Stage) => {
  const W2 = WALTER_AT;
  stand(cam, out, 760, WALTER, "walter", W2[0], 0, W2[2], { mode: "stand", expr: S(f, 766) ? "stern" : "neutral", blink: lidAt(t, 760, [766 / FPS]), prop: S(f, 766) ? "palm" : null, look: 1 });
  if (f < 760) stand(cam, out, 761, THORNTON, "thornton", THORNTON_W[0], 0, THORNTON_W[2], { mode: "stand", expr: "smile_closed", blink: lidAt(t, 761), prop: "clipboard", look: -1 });
  if (S(f, 777)) for (let k = 0; k < 3; k++) fx1(out, "stick", 120, 360, (p) => fxStick(p), W2[0] + 0.42 + (k - 1) * 0.07, 1.15, W2[2] + 0.12, 0.09, 0.27, false, (k - 1) * 0.25);
  if (S(f, 792)) count(out, 20, W2[0] + 0.36, 2.08, W2[2] + 0.1, f, 792, 0.3);
};
// 13: twenty cases: the full stack, Walter's facepalm, the count
const cases = (cam: CamInfo, t: number, f: number, out: Stage) => {
  stand(cam, out, 765, WALTER, "walter", 3.3, 0, 0.6, { mode: "stand", expr: S(f, 845) ? "pained" : "stern", blink: lidAt(t, 765), prop: S(f, 845) ? "facepalm" : "palm", look: -1 });
  if (!S(f, 845)) for (let k = 0; k < 3; k++) fx1(out, "stick", 120, 360, (p) => fxStick(p), 3.3 + 0.42 + (k - 1) * 0.07, 1.15, 0.72, 0.09, 0.27, false, (k - 1) * 0.25);
  if (!S(f, 845)) count(out, 3, 3.3 + 0.5, 1.75, 0.75, f, 832, 0.26);
  stand(cam, out, 766, WORK[1], "work1", DYN.x - 1.3, 0, DYN.z + 1.0, { mode: "stand", expr: "grin", blink: lidAt(t, 766), look: 1 });
  count(out, 20, DYN.x + 0.1, 2.2, DYN.z + 0.4, f, 845, 0.55);
};
// 14: Walter's new car rolls in and stops; Walter beside it, patting the roof; a sparkle
const parkCar = (cam: CamInfo, t: number, f: number, out: Stage) => {
  if (f >= 902) stand(cam, out, 770, WALTER, "walter", CAR.x - 1.6, 0, CAR.z + 1.5, { mode: "stand", expr: "grin", blink: lidAt(t, 770), look: 1, prop: f >= 906 ? "present" : null });
  for (let k = 0; k < 2; k++) if (f >= 904 + k * 5 && f < 916 + k * 5) { const u = Math.round(((f - 904 - k * 5) / 12) * 8) / 8; fx1(out, `spark|${u}`, 500, 500, (p) => fxBurst(p, u, "#ffffff", 8, 20, 200), CAR.x + 1.2 - k * 2.0, 1.25 + k * 0.1, CAR.z + 1.1, 0.5, 0.5); }
  for (let i = 0; i < 6; i++) { const [x, z] = lotSpot(i + 9); stand(cam, out, 771 + i, folk(i + 9), `folk${(i + 9) % 12}`, x, 0, z, { mode: "stand", expr: "neutral", blink: lidAt(t, 771 + i) }); }
};
// 15: from the whale: the crowd backing off toward the lot (front views, walking backwards); Thornton waves them back
const back = (cam: CamInfo, t: number, f: number, out: Stage) => {
  crowd(cam, t, f, out, "walk", 0, backK(15, f));
  stand(cam, out, 780, THORNTON, "thornton", THORNTON_PL[0], 0, THORNTON_PL[2], { mode: "stand", expr: "grin", blink: lidAt(t, 780), wave: Math.sin(t * 10) });
  whaleGulls(cam, t, out);
};
// 16: "Three": Thornton's hands on the plunger; 17: "Two": Walter with his fingers in his ears; 18: "One": the gull
const three = (cam: CamInfo, t: number, f: number, out: Stage) => {
  side(cam, out, 790, THORNTON, "thornton", THORNTON_PL[0], 0, THORNTON_PL[2], 1, 0, { mode: "push", pose: 0.75, expr: "grin", blink: lidAt(t, 790) });
  count(out, 3, THORNTON_PL[0] + 0.62, 1.62, THORNTON_PL[2] + 0.2, f, 965, 0.26);
};
const two = (cam: CamInfo, t: number, f: number, out: Stage) => {
  stand(cam, out, 791, WALTER, "walter", WALTER_LOT[0], 0, WALTER_LOT[2], { mode: "stand", expr: "nervous", blink: lidAt(t, 791), prop: "shh", look: 0 });
  for (let i = 0; i < 4; i++) stand(cam, out, 792 + i, folk(i + 2), `folk${(i + 2) % 12}`, WALTER_LOT[0] - 1.7 + i * 1.15 + (i > 1 ? 1.1 : 0), 0, WALTER_LOT[2] + 1.4 + (i % 2) * 0.5, { mode: "stand", expr: (["nervous", "shock", "nervous", "pained"] as Expr[])[i], blink: lidAt(t, 792 + i), prop: i % 2 ? "facepalm" : "shh" });
  count(out, 2, WALTER_LOT[0] - 0.5, 2.15, WALTER_LOT[2] - 0.3, f, 985, 0.4);
};
const one = (cam: CamInfo, t: number, f: number, out: Stage) => {
  const late = f >= 1012;
  gull(cam, out, 800, 3.4, 2.43, WHALE.z + 0.2, { mode: "stand", eye: late ? "shock" : "norm", blink: lidAt(t, 800) }, [1, 0], 0.42, false);
  count(out, 1, 3.05, 3.2, WHALE.z + 0.4, f, 1005, 0.3);
  side(cam, out, 801, THORNTON, "thornton", THORNTON_PL[0], 0, THORNTON_PL[2], 1, 0, { mode: "push", pose: 1, expr: "grin" });
};
// 19: the blast: the crowd watching from behind, then turning to run; 20: the chunks raining on the lot
const boomShot = (cam: CamInfo, t: number, f: number, out: Stage) => {
  const s = blastS(19, f);
  boom(cam, out, s, 1.0);
  crowd(cam, t, f, out, "run", s);
  lotGulls(cam, t, out, s);
  side(cam, out, 810, THORNTON, "thornton", THORNTON_PL[0], 0, THORNTON_PL[2], 1, 0, { mode: "push", pose: 1, expr: s > 0.6 ? "grin" : "shock" });
};
const rain = (cam: CamInfo, t: number, f: number, out: Stage) => {
  const s = blastS(20, f);
  boom(cam, out, s, 1.0);
  crowd(cam, t, f, out, "run", s);
  splats(out, s, [...LOT_HITS, NEAR_HIT]);
  [...LOT_HITS, NEAR_HIT].forEach((h, k) => { const u = (s - h.t) / 0.4; if (u >= 0 && u < 1) fx1(out, `burst|${Math.round(u * 8) / 8}`, 500, 500, (p) => fxBurst(p, Math.round(u * 8) / 8, "#f2c9be", 10), h.x, 0.8, h.z, 2.4, 2.4); void k; });
};
// 21: "Wait. How ...?": Walter among the splats, a chunk on his shoulder, a question mark
const wait = (cam: CamInfo, t: number, f: number, out: Stage) => {
  stand(cam, out, 820, WALTER, "walter", WALTER_LOT[0], 0, WALTER_LOT[2], { mode: "stand", expr: f < 1200 ? "dazed" : "nervous", blink: lidAt(t, 820), prop: ["scratch", Math.round((0.5 + 0.5 * Math.sin(t * 12)) * 4) / 4], look: 0 });
  if (f >= 1194) { const k = smooth((f - 1194) / 8), wob = 0.08 * Math.sin(t * 8); out.fx.push({ key: "question", cw: 240, ch: 360, draw: (p) => fxQuestion(p), x: WALTER_LOT[0] + 0.48, y: 2.25, z: WALTER_LOT[2] + 0.2, w: 0.24 * k, h: 0.36 * k, rot: wob }); }
  fx1(out, "splat|1", 400, 400, (p) => fxSplat(p, 1), WALTER_LOT[0] - 0.24, 1.52, WALTER_LOT[2] + 0.08, 0.3, 0.26);
  splats(out, 9, LOT_HITS);
};
// 22: the slow-motion replay from above: the cloud and the chunks drifting out
const slowmo = (cam: CamInfo, t: number, f: number, out: Stage) => { boom(cam, out, blastS(22, f), 1.0); };
// 23: the kitchen: dad's hammer comes down on the jelly; green splats on everyone
const JELLY = ["#57c24a"];
const jelly = (cam: CamInfo, t: number, f: number, out: Stage) => {
  const K = KIT_TABLE, hit = f >= HAMMER_AT;
  const hk = f < 1418 ? 0 : f < HAMMER_AT ? smooth((f - 1418) / (HAMMER_AT - 1418)) : 1;
  stand(cam, out, 830, DAD, "dad", K[0], 0, K[2] - 0.95, { mode: "stand", expr: hit ? "shock" : "grin", blink: lidAt(t, 830, [HAMMER_AT / FPS]), prop: ["hammer", hk], look: 0 });
  sit(cam, out, 831, MUM, "mum", K[0] - 0.95, 0.05, K[2] - 0.05, { expr: hit ? (f > 1500 ? "pained" : "shock") : "smile", blink: lidAt(t, 831, [HAMMER_AT / FPS]), look: 1 });
  sit(cam, out, 832, KID, "kid", K[0] + 0.95, 0.05, K[2] - 0.05, { expr: hit ? (f > 1500 ? "laugh" : "shock") : "grin", blink: lidAt(t, 832), look: -1 }, 0.85);
  sit(cam, out, 833, KID2, "kid2", K[0] + 0.35, 0.05, K[2] + 0.75, { expr: hit ? "lick" : "grin", blink: lidAt(t, 833), look: 0 }, 0.8);
  if (hit) {
    const u = Math.round(clamp01((f - HAMMER_AT) / 8) * 8) / 8;
    if (u < 1) fx1(out, `burst|${u}`, 500, 500, (p) => fxBurst(p, u, "#9ae07a", 12), K[0], 1.05, K[2] + 0.1, 1.2, 1.2);
    const spots: [number, number, number, number][] = [[K[0] - 0.02, 1.55, K[2] - 0.9, 0.22], [K[0] - 0.95, 1.12, K[2] + 0.02, 0.2], [K[0] + 0.95, 1.0, K[2] + 0.02, 0.18], [K[0] + 0.35, 0.95, K[2] + 0.82, 0.17],
      [K[0] - 1.9, 2.1, KITCHEN.z - 3.96, 0.5], [K[0] + 1.4, 1.6, KITCHEN.z - 3.96, 0.4], [K[0] + 0.3, 2.6, KITCHEN.z - 3.96, 0.35], [K[0] - 0.4, 0.8, K[2] + 0.2, 0.3]];
    spots.forEach(([x, y, z, w], k) => { const a = HAMMER_AT + 2 + k * 2 + (k < 4 ? 0 : 0); if (f >= a && (k >= 4 || f >= 1494 || k === 0)) fx1(out, `jsplat|${k % 4}`, 400, 400, (p) => fxSplat(p, k % 4, JELLY[0]), x, y, z + 0.05, w, w * 0.85); });
  }
};
// 24: the gulls on a log by the crater take off, shocked; 25: the remains, the workers staring; 26: Thornton's quote
const flee = (cam: CamInfo, t: number, f: number, out: Stage) => {
  for (let i = 0; i < 9; i += 2) {
    const go = Math.max(0, (f - 1569 - (i % 3) * 3) / FPS), x = -1.7 + i * 0.27, y = 2.8 * go * go + 3 * go, z = 6.4 - 4 * go + (i % 2) * 0.5;
    gull(cam, out, 840 + i, x + go * (i - 4) * 1.6, y, z, { mode: go > 0 ? "fly" : "stand", phase: ph(t, i, 4, 8), eye: f >= 1565 ? "shock" : "norm", blink: lidAt(t, 840 + i), beak: f >= 1565 ? 1 : 0 }, [i % 2 ? 1 : -1, 0], 0.4, false);
  }
  for (let k = 0; k < 3; k++) { const u = Math.round(((t * 0.4 + k * 0.33) % 1) * 20) / 20; fx1(out, `smoke|${u}`, 300, 300, (p) => fxPuff(p, u), WHALE.x - 2 + k * 2.5, 1.5 + 3 * u, WHALE.z + 1, 3 + 2 * u, 3 + 2 * u, true); }
};
const remains = (cam: CamInfo, t: number, f: number, out: Stage) => {
  WORKERS.forEach((_, i) => stand(cam, out, 850 + i, WORK[i], `work${i}`, 4.0 + i * 1.1, 0, -0.4 + (i % 2) * 0.7, { mode: "stand", expr: (["nervous", "shock", "pained"] as Expr[])[i], blink: lidAt(t, 850 + i), prop: i === 2 ? ["scratch", Math.round((0.5 + 0.5 * Math.sin(t * 12)) * 4) / 4] : null, look: -1 }));
  for (let k = 0; k < 2; k++) { const u = Math.round(((t * 0.5 + k * 0.5) % 1) * 20) / 20; fx1(out, `stink|${u}`, 300, 400, (p) => fxStink(p, u), WHALE.x - 1 + k * 3, 2.8, WHALE.z + 1.5, 0.9, 1.2); }
};
const quote = (cam: CamInfo, t: number, f: number, out: Stage) => {
  const Q = QUOTE_AT;
  stand(cam, out, 860, THORNTON, "thornton", Q[0], 0, Q[2], { mode: "stand", expr: f >= 1716 ? "grin" : "smile", blink: lidAt(t, 860), prop: "clipboard", look: 1, headTilt: f >= 1716 ? -6 : 0 });
  stand(cam, out, 861, REPORTER, "reporter", Q[0] + 1.25, 0, Q[2] - 0.5, { mode: "stand", expr: f >= 1745 ? "nervous" : "neutral", blink: lidAt(t, 861), prop: "pen", look: -1 });
  const a = 1733, u = (f - a) / FPS;
  if (u > -0.6 && u < 0) fx1(out, "chunkfall", 400, 400, (p) => fxSplat(p, 2, "#d99a8e"), Q[0] - 0.5, 0.25 - u * 14, Q[2] - 2.4, 0.9, 0.8);
  if (u >= 0) { out.fx.push({ key: "splat|2", cw: 400, ch: 400, draw: (p) => fxSplat(p, 2), x: Q[0] - 0.5, y: 0.03, z: Q[2] - 2.4, w: 2.2, h: 2.2, flat: true }); if (u < 0.3) { const k2 = Math.round((u / 0.3) * 8) / 8; fx1(out, `burst|${k2}`, 500, 500, (p) => fxBurst(p, k2, "#f2c9be", 10), Q[0] - 0.5, 0.6, Q[2] - 2.3, 1.6, 1.6); } }
};
// 27: the memorial park at golden hour: a family by the sign, a kid with a whale balloon
const memorial = (cam: CamInfo, t: number, f: number, out: Stage) => {
  const P = PARK_SIGN;
  stand(cam, out, 870, DAD, "dad", P[0] - 2.6, 0, P[2] + 1.6, { mode: "stand", expr: "grin", blink: lidAt(t, 870), prop: "camera", look: 1 });
  stand(cam, out, 871, KID, "kid", P[0] + 2.4, 0, P[2] + 1.4, { mode: "stand", expr: "grin", blink: lidAt(t, 871), prop: "salute", look: -1 }, 0.85);
  stand(cam, out, 872, MUM, "mum", P[0] + 3.3, 0, P[2] + 0.9, { mode: "stand", expr: "smile", blink: lidAt(t, 872), look: -1 });
  for (let i = 0; i < 6; i++) walker(cam, out, 873 + i, folk(i + 5), `folk${(i + 5) % 12}`, P[0] - 10 + ((i * 4 + 1.1 * t) % 20), 0, P[2] - 6 - (i % 3) * 3, t, 1, 0, "smile");
};
// 28: Walter, relieved, beside his untouched car (splats all around); 29: looking up past him at the falling lump; 30: crush
const relief = (cam: CamInfo, t: number, f: number, out: Stage) => {
  stand(cam, out, 880, WALTER, "walter", CAR.x - 1.4, 0, CAR.z + 1.6, { mode: "stand", expr: f < 1924 ? "relief" : "relief_open", blink: lidAt(t, 880), prop: f >= 1924 ? "present" : null, look: 1 });
  splats(out, 9, LOT_HITS);
};
const look = (cam: CamInfo, t: number, f: number, out: Stage) => {
  stand(cam, out, 881, WALTER, "walter", CAR.x - 1.8, 0, CAR.z + 4.1, { mode: "stand", expr: f >= 1960 ? "shock" : "relief", blink: lidAt(t, 881, [1960 / FPS]), look: 0, headTilt: -10 });
};
const crush = (cam: CamInfo, t: number, f: number, out: Stage) => {
  const hit = f >= LUMP_HIT;
  stand(cam, out, 882, WALTER, "walter", CAR.x - 1.15, 0, CAR.z + 3.3, { mode: "stand", expr: !hit ? "shock" : f < 2002 ? "shock" : "pained", blink: 0, prop: hit && f >= 2000 ? "facepalm" : null, look: 1, lift: hit && f < 1994 ? 90 : 60 });
  if (hit && f < LUMP_HIT + 14) { const u = Math.round(((f - LUMP_HIT) / 14) * 8) / 8; fx1(out, `glass|${u}`, 500, 500, (p) => fxBurst(p, u, "#cfe8f6", 14, 30, 240), CAR.x - 1.3, 1.15, CAR.z + 1.15, 1.3, 1.3); }
  if (hit && f < LUMP_HIT + 9) { const u = Math.round(((f - LUMP_HIT) / 9) * 8) / 8; fx1(out, `burst|${u}`, 500, 500, (p) => fxBurst(p, u, "#f2c9be", 12), CAR.x - 0.3, 1.6, CAR.z + 1.2, 2.6, 2.6); }
  if (hit) for (let k = 0; k < 3; k++) puff(out, f, LUMP_HIT + k * 2, CAR.x - 1.5 + k * 1.5, 0, CAR.z + 1.1, 1.4, 16);
  splats(out, 9, LOT_HITS);
};
// 31: the dealer's lot: the salesman presents the car with the bow, Walter grins; then up to the banner
const deal = (cam: CamInfo, t: number, f: number, out: Stage) => {
  const D = DEAL_CAR;
  stand(cam, out, 890, SALESMAN, "salesman", D[0] + 1.75, 0, D[2] + 2.0, { mode: "stand", expr: "grin", blink: lidAt(t, 890), prop: "present", look: -1, facing: -1 });
  stand(cam, out, 891, WALTER, "walter", D[0] + 0.15, 0, D[2] + 2.3, { mode: "stand", expr: f >= 2020 ? "grin" : "smile", blink: lidAt(t, 891), look: 1, facing: 1 });
  for (let k = 0; k < 2; k++) { const a = 2030 + k * 40, u = (f - a) / 12; if (u >= 0 && u < 1) { const q2 = Math.round(u * 8) / 8; fx1(out, `spark|${q2}`, 500, 500, (p) => fxBurst(p, q2, "#ffffff", 8, 20, 200), D[0] + 1.3 - k * 2.4, 1.3, D[2] + 1.1, 0.5, 0.5); } }
};

/** everything with a face (and every 2D effect) in shot `id` at time t */
export const stage = (id: number, t: number, f: number, cam: CamInfo): Stage => {
  const out: Stage = { places: [], fx: [] };
  const s = SHOTS[id - 1];
  LNAME = s.light;
  findSun(cam, SUN);
  switch (s.crowd) {
    case "hook": hook(cam, t, f, out); break;
    case "purpose": purpose(cam, t, f, out); break;
    case "coast": coast(cam, t, f, out); break;
    case "bus": busShot(cam, t, f, out); break;
    case "stink": stink(cam, t, f, out); break;
    case "highway": highway(cam, t, f, out); break;
    case "dept": dept(cam, t, f, out); break;
    case "plan": plan(cam, t, f, out, false); break;
    case "pieces": plan(cam, t, f, out, true); break;
    case "gulls": gulls(cam, t, f, out); break;
    case "dyn": dyn(cam, t, f, out); break;
    case "walter": walter(cam, t, f, out); break;
    case "cases": cases(cam, t, f, out); break;
    case "park": parkCar(cam, t, f, out); break;
    case "back": back(cam, t, f, out); break;
    case "three": three(cam, t, f, out); break;
    case "two": two(cam, t, f, out); break;
    case "one": one(cam, t, f, out); break;
    case "boom": boomShot(cam, t, f, out); break;
    case "rain": rain(cam, t, f, out); break;
    case "wait": wait(cam, t, f, out); break;
    case "slowmo": slowmo(cam, t, f, out); break;
    case "jelly": jelly(cam, t, f, out); break;
    case "flee": flee(cam, t, f, out); break;
    case "remains": remains(cam, t, f, out); break;
    case "quote": quote(cam, t, f, out); break;
    case "memorial": memorial(cam, t, f, out); break;
    case "relief": relief(cam, t, f, out); break;
    case "look": look(cam, t, f, out); break;
    case "crush": crush(cam, t, f, out); break;
    case "deal": deal(cam, t, f, out); break;
    default: break;
  }
  return out;
};
export { FPS, clamp01, NOINK, BLAST, Chunks, CHUNKS, LOT, PLUNGER, DEALER, PARK };
