import type { LightName } from "./lights";
// The escalator cast as lit flat sprites in the 3D world. Each frame every character asks for a drawing (a key + a draw call);
// the pool keeps one canvas per distinct drawing, so soldiers marching in step share canvases (7 head shapes x 4
// outfits). Characters are yaw-only billboards shaded by cardShade() (scene tint, bright floor, side gradient toward
// the sun, painted crescent in the drawing); standing ones get a soft multiply contact blob. Effects are unlit cards.
// Cards, effects and blobs live on the NOINK layer so the world ink pass never outlines their quads.
import * as THREE from "three";
import {
  Pen, bodyFront, bodySide, townsfolk, rider, bunny, scientist, reporter, KID, EXEC, fxShadow, fxContact, fxNewspaper, fxFlash, Outfit, Expr, FrontOpts, SideOpts,
} from "./toon";
import { FPS, SHOTS, clamp01, smooth, PHONE_GUY, SCI, READER, NEWS, SPADE_KID, WAFER_GUY, LOOKER, FACTORY_DOOR, LAB, PULLER } from "./story";
import { CITY, SQUARE } from "./chippath";
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
const BODY = (() => { const g = new THREE.PlaneGeometry(600 * SU, 1000 * SU); g.translate(0, (975 - 500) * SU, 0); return g; })();
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
  scale?: number; mirror?: boolean; yaw?: number; geo?: "body" | "swing"; roll?: number; size?: [number, number, number];
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

// ---- the lithography bay: workers in bunny suits among the tools ----
type Spot = [number, number, number];
const BAY: Spot[] = [[-5.2, -6.6, 0], [-1.5, -6.9, 1], [2.6, -6.7, 2], [6.8, -6.6, 3], [-10.6, -2.4, 4], [10.4, 1.2, 5], [4.6, 3.6, 6], [-7.4, 4.2, 7]];
const bay = (cam: CamInfo, t: number, out: Stage) => {
  BAY.forEach(([x, z, v], i) => {
    if (i % 3 === 1) { const xx = x + 1.4 * Math.sin(t * 0.35 + i); walker(cam, out, 400 + i, bunny(v), `b${v % 4}`, xx, 0, z, t, Math.cos(t * 0.35 + i), 0, "neutral"); }
    else stand(cam, out, 400 + i, bunny(v), `b${v % 4}`, x, 0, z, { mode: "stand", expr: i % 2 ? "smile" : "neutral", blink: lidAt(t, 400 + i), look: x > 0 ? -1 : 1 });
  });
};
/** the reveal: a few workers small in front of the scanner, looking up at it */
const bay2 = (cam: CamInfo, t: number, out: Stage) => {
  const f = t * FPS;
  if (f < 1424) { // "normal light is too blunt": a worker squints at a wafer, puzzled
    stand(cam, out, 430, bunny(3), "b3", -0.9, 0, 4.4, { mode: "stand", expr: f < 1395 ? "nervous" : "shock", blink: lidAt(t, 430), prop: "wafer", look: -1, headTilt: -6 });
    return;
  }
  ([[-2.9, 4.6, 0], [-1.5, 5.3, 1], [0.6, 4.9, 2], [-4.6, 5.6, 3]] as Spot[]).forEach(([x, z, v], i) =>
    stand(cam, out, 420 + i, bunny(v), `b${v % 4}`, x, 0, z, { mode: "stand", expr: i % 2 ? "shock" : "smile_closed", blink: lidAt(t, 420 + i), headTilt: -4, look: 0 }));
};
// ---- the phone on the street (shots 1, 7, 19) ----
const PHONE_O: Outfit = { ...rider(2), hat: "hair", hair: "#2a1c18" };
const phone = (cam: CamInfo, t: number, f: number, out: Stage, ending = false) => {
  const expr: Expr = ending ? (f >= 2150 ? "grin" : "smile") : f < 20 ? "smile" : "smile_closed";
  stand(cam, out, 600, PHONE_O, "phone", PHONE_GUY[0], 0, PHONE_GUY[2], { mode: "stand", expr, blink: lidAt(t, 600), prop: "phone", look: -1, headTilt: 4 });
  stand(cam, out, 601, townsfolk(3), "t3", PHONE_GUY[0] - 5.5, 0, PHONE_GUY[2] - 6.5, { mode: "stand", expr: "neutral", blink: lidAt(t, 601) });
  walker(cam, out, 602, rider(7), "r7", PHONE_GUY[0] + 6 - 1.2 * t % 12, 0, PHONE_GUY[2] - 4.0, t, -1, 0, "whistle");
};
// ---- 1947: two scientists behind the bench; the press with flash cameras ----
const lab = (cam: CamInfo, t: number, f: number, out: Stage, mood: "work" | "press") => {
  SCI.forEach(([x, , z], i) => stand(cam, out, 610 + i, scientist(i), `sci${i}`, x, 0, z, {
    mode: "stand", expr: mood === "press" ? (i ? "grin" : "smile_closed") : f > 313 && i === 0 ? "grin" : (["smile", "neutral"] as Expr[])[i], blink: lidAt(t, 610 + i),
    look: x < LAB.x ? 1 : -1, headTilt: mood === "work" ? 5 : 0, wave: mood === "press" && i === 1 ? 0.5 : undefined,
  }));
};
const FLASHES = [455, 468, 482, 497, 509];
const press = (cam: CamInfo, t: number, f: number, out: Stage) => {
  lab(cam, t, f, out, "press");
  ([[-1.7, 1.4], [0.3, 1.9], [1.9, 1.3]] as [number, number][]).forEach(([dx, z], i) => {
    stand(cam, out, 620 + i, reporter(i), `rep${i}`, LAB.x + dx, 0, z, { mode: "stand", expr: "smile", blink: lidAt(t, 620 + i), prop: "camera", look: dx < 0 ? 1 : -1 });
    const fl = FLASHES.find((a) => f >= a + i * 3 && f < a + i * 3 + 5);
    if (fl !== undefined) { const k = 1 - (f - fl - i * 3) / 5; out.fx.push({ key: "flash", cw: 256, ch: 256, draw: (p) => fxFlash(p), x: LAB.x + dx + 0.2, y: 1.55, z: z + 0.2, w: 1.1 * k, h: 1.1 * k }); }
  });
};
// ---- 1948: the page, then the reader in the kitchen ----
const reader = (cam: CamInfo, t: number, f: number, out: Stage) => {
  if (f < 558) {
    const ring = f >= 520 ? smooth((f - 520) / 9) : 0, rq = Math.round(ring * 20) / 20;
    out.fx.push({ key: `news46|${rq}`, cw: 600, ch: 800, draw: (p) => fxNewspaper(p, "46", rq), x: NEWS[0], y: NEWS[1], z: NEWS[2], w: 1.05, h: 1.4 });
    return;
  }
  const expr: Expr = f < 618 ? "grin" : f < 650 ? "neutral" : "whistle";
  stand(cam, out, 630, townsfolk(5), "t5", READER[0], 0, READER[2], { mode: "stand", expr, blink: lidAt(t, 630), prop: "newspaper", look: f < 618 ? 0 : 1 });
};
// ---- the beach kid ----
const beach = (cam: CamInfo, t: number, f: number, out: Stage) => f >= 884 ? undefined :
  stand(cam, out, 640, KID, "kid", SPADE_KID[0], 0, SPADE_KID[2], { mode: "stand", expr: f < 874 ? "smile_closed" : f < 902 ? "shock" : "grin", blink: lidAt(t, 640), look: 1, headTilt: f > 878 ? -8 : 0 }, 0.9);
// ---- the crystal room: a worker by the puller, one holding up a wafer by the saw ----
const puller = (cam: CamInfo, t: number, f: number, out: Stage) => {
  stand(cam, out, 650, bunny(1), "b1", PULLER.x - 1.4, 0, PULLER.z + 1.6, { mode: "stand", expr: "smile", blink: lidAt(t, 650), look: -1, headTilt: -5 });
  stand(cam, out, 651, bunny(2), "b2", WAFER_GUY[0], 0, WAFER_GUY[2], { mode: "stand", expr: f > 1059 ? "grin" : "neutral", blink: lidAt(t, 651), prop: f > 1050 ? "wafer" : null, look: -1 });
};
// ---- the mirror land: someone with a magnifier at the bump ----
const mirror = (cam: CamInfo, t: number, f: number, out: Stage) =>
  stand(cam, out, 660, engineer2(), "eng", LOOKER[0], 0, LOOKER[2], { mode: "stand", expr: f >= 1830 ? "shock" : "neutral", blink: lidAt(t, 660, [1830 / FPS]), prop: "magnifier", tilt: -8, headTilt: -10, look: -1 });
const engineer2 = (): Outfit => ({ ...bunny(0), hat: "hair", hair: "#5a3b2a", mask: undefined, jacket: "#f08a2c", pants: "#3b3f52", boots: "#4a3426" });
// ---- the one factory: a long queue at its door ----
const queue = (cam: CamInfo, t: number, f: number, out: Stage) => {
  for (let i = 0; i < 30; i++) {
    const a = i * 0.07, x = FACTORY_DOOR[0] - 0.4 + Math.sin(i * 1.7) * 0.25 - 12 * (1 - Math.cos(a)) - i * 0.25, z = FACTORY_DOOR[2] + 1.2 + 14 * Math.sin(a) + i * 0.15;
    const o = i % 3 === 0 ? EXEC : i % 3 === 1 ? reporter(i) : townsfolk(i % 8);
    stand(cam, out, 670 + i, o, `q${i % 6}`, x, 0, z, { mode: "stand", expr: (["neutral", "whistle", "smile", "nervous"] as Expr[])[i % 4], blink: lidAt(t, 670 + i), look: 1, prop: i % 4 === 1 ? "clipboard" : null });
  }
};
// ---- the chip city: people in its streets (between the rows of switches), all small next to the switches ----
const cityCell = (i: number, j: number): [number, number] => [CITY.x - (CITY.nx * CITY.px) / 2 + (i + 0.5) * CITY.px, CITY.z - (CITY.nz * CITY.pz) / 2 + (j + 0.5) * CITY.pz];
const city = (cam: CamInfo, t: number, out: Stage) => {
  for (let n = 0; n < 34; n++) {
    const [ax, az] = cityCell(SQUARE.i0, SQUARE.j0), [bx, bz] = cityCell(SQUARE.i1 - 1, SQUARE.j1 - 1);
    const xx = ax + (bx - ax) * hh(n, 1), zz = az - 1.5 + (bz - az + 3) * hh(n, 2);
    const o = n % 2 ? rider(n % 23) : townsfolk(n % 8);
    if (n % 4 === 0) walker(cam, out, 500 + n, o, n % 2 ? `r${n % 23}` : `t${n % 8}`, xx + 0.8 * Math.sin(t * 0.5 + n), 0, zz, t, Math.cos(t * 0.5 + n), 0, "smile");
    else stand(cam, out, 500 + n, o, n % 2 ? `r${n % 23}` : `t${n % 8}`, xx, 0, zz, { mode: "stand", expr: (["shock", "smile", "neutral", "whistle"] as Expr[])[n % 4], blink: lidAt(t, 500 + n), headTilt: -6, look: hh(n, 5) < 0.5 ? -1 : 1 });
  }
};

/** everything with a face (and every 2D effect) in shot `id` at time t */
export const stage = (id: number, t: number, f: number, cam: CamInfo): Stage => {
  const out: Stage = { places: [], fx: [] };
  const s = SHOTS[id - 1];
  LNAME = s.light;
  findSun(cam, SUN);
  switch (s.crowd) {
    case "bay": bay(cam, t, out); break;
    case "bay2": bay2(cam, t, out); break;
    case "city": city(cam, t, out); break;
    case "phone": phone(cam, t, f, out); break;
    case "ending": if (f < 2116) phone(cam, t, f, out, true); break;
    case "lab": lab(cam, t, f, out, "work"); break;
    case "labClose": break;
    case "press": press(cam, t, f, out); break;
    case "reader": reader(cam, t, f, out); break;
    case "beach": beach(cam, t, f, out); break;
    case "puller": puller(cam, t, f, out); break;
    case "mirror": if (f >= 1822) mirror(cam, t, f, out); break;
    case "queue": queue(cam, t, f, out); break;
    default: break;
  }
  return out;
};
export { FPS };
