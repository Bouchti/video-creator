import type { LightName } from "./lights";
// The 1904 marathon cast as lit flat sprites in the 3D world. Each frame every character asks for a drawing (a key + a draw
// call); the pool keeps one canvas per distinct drawing. People are yaw-only billboards on the 600 x 1000 card, shaded by
// cardShade() and standing on a soft multiply contact blob. Effects are unlit cards. Everything lives on the NOINK layer.
import * as THREE from "three";
import {
  Pen, bodyFront, bodySide, fxShadow, fxContact, fxPuff, fxQuestion,
  INK, Outfit, Expr, FrontOpts, SideOpts, parisian,
} from "./toon";
import { fxFlashStar, fxDrop, fxZzz } from "./mikedraw";
import { fxShout, fxRunLines, fxLabel, fxSweat, fxCalendar } from "./molassesdraw";
import {
  fxDustCloud, fxWreath, fxMedal, fxPoison, fxEggs, fxCup, fxDizzy, fxEggDream, fxScissors, fxPeach, fxApple, fxDog, fxBanned, fxBroke,
  fxCoughDust, fxSun, fxThermoF, fxSmoke, fxTape,
} from "./marathondraw";
import {
  FPS, SHOTS, clamp01, smooth, V3, carAt, offCarAt, CarState, SULLY, CRAMP, ALICE, LORZ_F, CARV, NAP, BAN, WELL, MILE9, HICKS, DOGF, BOSTON, STAD, ROAD,
  dogRunX, bosZ, footZ,
} from "./story";
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
  if (mirror && who.o.bib) who = { ...who, o: { ...who.o, bibFlip: true }, okey: who.okey + "|m" };
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


// ---------------- the marathon cast ----------------
const S = (f: number, a: number) => f >= a - 2; // a reaction lands 0-3 f before its word
const fx1 = (out: Stage, key: string, cw: number, ch: number, draw: (p: Pen) => void, x: number, y: number, z: number, w: number, h: number, soft = false, rot = 0) =>
  out.fx.push({ key, cw, ch, draw, x, y, z, w, h, soft, rot });
const pop = (f: number, f0: number) => smooth((f - f0) / 5) * (1 + 0.15 * Math.max(0, 1 - (f - f0) / 8));
const label = (out: Stage, text: string, x: number, y: number, z: number, f: number, f0: number, w: number, h: number, bg = "#f2c230", lines = false) => {
  const k = pop(f, f0), ch = Math.round((640 * h) / w);
  if (k > 0) fx1(out, `label|${text}|${bg}|${lines}`, 640, ch, (p) => fxLabel(p, text, 640, ch, bg, INK, lines), x, y, z, w * k, h * k);
};
const sit = (cam: CamInfo, out: Stage, i: number, o: Outfit, okey: string, x: number, y: number, z: number, fo: FrontOpts, scale = 1) =>
  stand(cam, out, i, o, okey, x, y, z, { ...fo, mode: "sit" }, scale, false);
/** someone running toward (dx, dz): front or side view by the camera, open-mouthed */
const runner = (cam: CamInfo, out: Stage, i: number, o: Outfit, okey: string, x: number, z: number, t: number, dx: number, dz: number, expr: Expr, y = 0, shadow = true, rate = 2.4, extra: Partial<FrontOpts> = {}) => {
  const view = viewOf(cam, x, z, dx, dz), p2 = q(((t * rate + hh(i, 5)) % 1 + 1) % 1, 12);
  out.places.push(person(cam, { i, o, okey }, x, y, z, view, { mode: "march", phase: p2, expr, blink: lidAt(t, i), tilt: -3, lift: 110, ...extra }, { mode: "march", phase: p2, expr, blink: lidAt(t, i), stomp: 0.9, stride: 1.0 * view.fs }));
  if (shadow) blob(out, x, y, z);
};
const shout = (out: Stage, text: string, f: number, f0: number, t: number, x: number, y: number, z: number, s = 1.5) => {
  if (f < f0) return;
  const k = pop(f, f0), u = Math.round(((t * 6) % 1) * 4) / 4;
  fx1(out, `shout|${text}|${u}`, 420, 300, (p) => fxShout(p, text, u), x, y, z, s * k, 0.714 * s * k);
};
const flash = (out: Stage, f: number, at: number, x: number, y: number, z: number, s = 0.8) => {
  if (f >= at && f < at + 8) { const u = Math.round(((f - at) / 8) * 8) / 8; fx1(out, `flash|${u}`, 500, 500, (p) => fxFlashStar(p, u), x, y, z, s, s); }
};
const dust = (out: Stage, f: number, x: number, y: number, z: number, s: number, i: number, a = 0.85) => {
  const u = Math.round((((f / 40) + hh(i, 3)) % 1) * 8) / 8;
  fx1(out, `dust|${u}|${a}`, 600, 400, (p) => fxDustCloud(p, u, a), x, y, z, s, s * 0.667, true);
};
const cough = (out: Stage, f: number, f0: number, x: number, y: number, z: number, s = 0.5) => {
  const u = Math.round((((f - f0) / 20) % 1) * 6) / 6;
  if (f >= f0) fx1(out, `cough|${u}`, 240, 240, (p) => fxCoughDust(p, u), x, y, z, s, s);
};
const sweat = (out: Stage, f: number, x: number, y: number, z: number, s = 0.3) => { const u = Math.round((((f) / 18) % 1) * 6) / 6; fx1(out, `sweat|${u}`, 200, 200, (p) => fxSweat(p, u), x, y, z, s, s); };
const R_SKIN = ["#f5c9a0", "#ffe2c2", "#e0b48a", "#f0c090"];
const RUN = (v: number, bib: string): Outfit => ({ jacket: ["#d9443a", "#3f7fc9", "#f2c230", "#4fa36a", "#e07a32", "#8a5ab8"][v % 6], pants: ["#f4f1ea", "#2f3a5a", "#5a3a2a"][v % 3], boots: "#3a2a22",
  hat: v % 3 === 0 ? "cap" : "hair", cap: ["#f4f1ea", "#c0353a", "#3f6fb5"][v % 3], hair: ["#3a2a1a", "#5a3b2a", "#2a1c18", "#8a5a32"][v % 4], skin: R_SKIN[v % 4], bib });
const LORZ: Outfit = { jacket: "#f4f1ea", pants: "#1f2a44", boots: "#3a2a22", hat: "hair", hair: "#3a2a1a", skin: "#f5c9a0", bib: "31" };
const HICKS_O: Outfit = { jacket: "#5aa0d8", pants: "#f4f1ea", boots: "#3a2a22", hat: "hair", hair: "#5a3b2a", moustache: "#5a3b2a", skin: "#ffe2c2", bib: "20" };
const CARV_O: Outfit = { jacket: "#f4f1ea", pants: "#3a3346", boots: "#2a1c18", hat: "cap", cap: "#2f4a7a", sam: "#7a4a2a", moustache: "#2a1c18", skin: "#c98e64", buttons: "#d9d4c8" };
const LEN_O: Outfit = { jacket: "#e8c45a", pants: "#3f4f6a", boots: "#3a2a22", hat: "hair", hair: "#1a1414", skin: "#7a4e34", bib: "35" };
const SULLY_O: Outfit = { jacket: "#3b3f52", pants: "#2f3242", boots: INK, hat: "bowler", hatCol: "#2e2a36", tie: "#c0353a", moustache: "#5a3b2a", buttons: "#d9dde0", skin: "#f5c9a0", build: "stout" };
const TRAINER = (v: number): Outfit => ({ jacket: ["#5a6070", "#6a5a4a"][v % 2], pants: "#3f4454", boots: "#3a2a22", hat: "bowler", hatCol: ["#2e2a36", "#4a3a2a"][v % 2], tie: ["#3f6fb5", "#8c3b4a"][v % 2], skin: ["#f5c9a0", "#e0b48a"][v % 2], moustache: v % 2 ? "#4a3426" : undefined });
const ALICE_O: Outfit = { jacket: "#f4f1f6", pants: "#e9e4ee", boots: "#5a3b2a", hat: "sunhat", dress: "#f4f1f6", skin: "#ffe2c2", hair: "#5a3b2a" };
const DRIVER: Outfit = { jacket: "#6a5a4a", pants: "#3f4454", boots: "#3a2a22", hat: "cap", cap: "#4a4552", skin: "#f5c9a0", moustache: "#4a3426" };
const OFFICIAL = (v: number): Outfit => ({ jacket: ["#3b3f52", "#4f5566"][v % 2], pants: "#2f3242", boots: INK, hat: "bowler", hatCol: "#2e2a36", tie: "#c0353a", skin: "#f5c9a0", moustache: v % 2 ? "#6a4a32" : undefined });
const folk = (i: number): Outfit => parisian(i);

/** a car's seat in the world: car facing -z (rotation pi), local (lx, lz) -> world */
const seat = (c: CarState, lx: number, lz: number): [number, number] => [c.x - lx, c.z - lz];
const inCar = (cam: CamInfo, out: Stage, c: CarState, i: number, o: Outfit, okey: string, lx: number, lz: number, fo: FrontOpts) => {
  const [x, z] = seat(c, lx, lz); sit(cam, out, i, o, okey, x, 0.62, z, fo);
};
const runLines = (out: Stage, f: number, x: number, y: number, z: number, s = 0.45) => {
  for (const sx of [-1, 1]) { const u = Math.round((((f / 6) + (sx > 0 ? 0.5 : 0)) % 1) * 6) / 6; fx1(out, `runlines|${u}`, 300, 300, (p) => fxRunLines(p, u), x + sx * 0.42, y, z, s, s, false, sx > 0 ? Math.PI : 0); }
};

// v2 (gate: "bare roadside"): farm folk along the fence line, cheering, gawping, waving hats; ids 300+ (own canvases)
const roadside = (cam: CamInfo, out: Stage, t: number, f: number, zc: number, n = 6, side = -1, cheer = true) => {
  for (let i = 0; i < n; i++) {
    const x = side * (5.05 + 0.55 * (i % 2)), z = zc - 1.6 * i - 0.5 * hh(i, 5), id = 300 + i, o = folk(i + 3);
    const ex: Expr = (["grin", "shock", "laugh", "smile", "nervous", "grin"] as Expr[])[i % 6];
    stand(cam, out, id, o, `folk${i + 3}`, x, ROAD.field, z, { mode: "stand", expr: ex, blink: lidAt(t, id), prop: cheer && i % 3 === 0 ? "hatInHand" : null,
      wave: cheer && i % 3 === 1 ? 0.6 + 0.4 * Math.sin(t * 9 + i) : undefined, look: -side }, 1, true);
  }
};
// 1: the hook: the car roaring at the lens past the runners, Lorz waving from the back seat, dust behind
const hook = (cam: CamInfo, t: number, f: number, out: Stage) => {
  const c = carAt(1, f), s = f / FPS;
  inCar(cam, out, c, 100, DRIVER, "driver", 0.35, 0.05, { expr: "grin", blink: lidAt(t, 100), look: 0 });
  // Lorz up on the back seat, smug, a royal wave at the runners he is passing
  { const [x, z] = seat(c, -0.42, -1.05); stand(cam, out, 101, LORZ, "lorz", x, 0.42, z, { mode: "stand", expr: S(f, 84) ? "laugh" : "smug", blink: lidAt(t, 101), look: -1, wave: 0.6 + 0.4 * Math.sin(t * 7), tilt: -4 }, 1, false); }
  // two runners right in front of us beside the car, tongues out, coughing in its dust; the field behind
  ([[2.1, -3.8, "lick"], [-0.15, -4.5, "pained"], [1.6, -1.6, "shock"]] as const).forEach(([x, z0, ex], i) => {
    const z = z0 - 3.25 * s, passed = c.z < z + 0.8;
    runner(cam, out, 110 + i, RUN(i, `${12 + i * 7}`), `run${i}`, x, z, t, 0, -1, passed && i < 2 ? "pained" : ex, 0, true, 1.8);
    cough(out, f, 6 + i * 9, x - 0.35, 1.85, z - 0.2, 0.55); sweat(out, f, x + 0.25, 2.0, z - 0.1, 0.3);
    if (i < 2) dust(out, f, x - 0.5, 0.7, z + 1.4, 1.8, i + 40, 0.3);
  });
  for (let k = 0; k < 6; k++) dust(out, f, c.x - 0.8 + (k % 3) * 1.2, 0.7 + 0.3 * k, c.z + 2.3 + k * 1.3, 2.6 + 0.8 * k, k, 0.9);
  if (f < 46) shout(out, "HONK!", f, -6, t, c.x - 0.2, 3.0, c.z + 1.6, 0.85);
  if (S(f, 70)) shout(out, "BYE!", f, 70, t, c.x - 0.1, 3.0, c.z + 1.6, 0.9);
  roadside(cam, out, t, f, -3, 9, -1);
};
// 2: the field strung out in the heat: ST. LOUIS 1904, the thermometer to 90
const setting = (cam: CamInfo, t: number, f: number, out: Stage) => {
  const s = (f - 92) / FPS;
  for (let i = 0; i < 9; i++) runner(cam, out, 120 + i, RUN(i + 1, `${3 + i * 5}`), `run${i + 1}`, -1.8 + (i % 4) * 1.1, -8 - i * 3.6 - 2.1 * s, t, 0, -1, i % 2 ? "pained" : "nervous", 0, true, 2.0);
  const u = Math.round((((f / 30)) % 1) * 8) / 8; fx1(out, `sun|${u}`, 360, 360, (p) => fxSun(p, u), 9, 16, -55, 9, 9);
  label(out, "ST. LOUIS, 1904", -3.4, 5.0, -18, f, 100, 4.6, 1.0, "#ffffff");
  if (S(f, 132)) { const v = 50 + 40 * smooth((f - 132) / 14), k = pop(f, 141); fx1(out, `thermo|${Math.round(v)}`, 160, 520, (p) => fxThermoF(p, v), -3.6, 2.4, -15, 0.9 * k, 2.9 * k); }
  for (let k = 0; k < 3; k++) dust(out, f, -1 + k * 1.5, 0.5, -16 - k * 9, 4.5, k + 10, 0.5);
};
// 3: the only water stop and the man in charge
const well = (cam: CamInfo, t: number, f: number, out: Stage) => {
  stand(cam, out, 130, SULLY_O, "sully", SULLY[0], SULLY[1], SULLY[2], { mode: "stand", expr: S(f, 300) ? "grin" : "smile", blink: lidAt(t, 130, [300 / FPS]), prop: S(f, 300) ? "point" : "clipboard", look: -1 });
  for (let i = 0; i < 3; i++) runner(cam, out, 131 + i, RUN(i + 4, `${40 + i * 3}`), `run${i + 4}`, -1.3 + i * 1.0, WELL.z + 12 - i * 2.5 - 2.0 * ((f - 236) / FPS), t, 0, -1, i === 1 ? "lick" : "pained", 0, true, 2.0);
  // v2: a parched runner begging in the foreground, tongue out, while the man in charge grins by his sign
  stand(cam, out, 134, RUN(3, "44"), "run3", SULLY[0] + 1.25, SULLY[1], SULLY[2] + 0.35, { mode: "stand", expr: "lick", blink: lidAt(t, 134), prop: "palm", look: -1, tilt: 5 * Math.sin(t * 3) }, 1, true);
  sweat(out, f, SULLY[0] + 1.5, 2.0, SULLY[2] + 0.4, 0.3);
  if (S(f, 273)) { const k = pop(f, 273); fx1(out, "drop1", 60, 90, (p) => fxDrop(p), WELL.x + 0.6, 2.2 + 0.05 * Math.sin(t * 6), WELL.z + 0.6, 0.28 * k, 0.42 * k); }
};
// 4: closer: his clipboard, DEHYDRATION STUDY; a parched runner begging behind him
const science = (cam: CamInfo, t: number, f: number, out: Stage) => {
  stand(cam, out, 135, SULLY_O, "sully", SULLY[0], SULLY[1], SULLY[2], { mode: "stand", expr: S(f, 351) ? "grin" : "smile", blink: lidAt(t, 135, [351 / FPS]), prop: "clipboard", look: 1 });
  stand(cam, out, 136, RUN(5, "44"), "run5", SULLY[0] - 1.3, 0, SULLY[2] - 2.2, { mode: "stand", expr: "lick", blink: lidAt(t, 136), prop: "palm", look: 1, tilt: 4 * Math.sin(t * 3) });
  sweat(out, f, SULLY[0] - 1.0, 2.0, SULLY[2] - 2.1, 0.32);
  label(out, "DEHYDRATION STUDY", SULLY[0] + 0.3, 2.08, SULLY[2] + 0.6, f, 351, 0.78, 0.15, "#ffffff");
};
// 5: the officials' car ahead, its dust swallowing the runners
const dustShot = (cam: CamInfo, t: number, f: number, out: Stage) => {
  const c = offCarAt(5, f);
  inCar(cam, out, c, 140, DRIVER, "driver", 0.35, 0.05, { expr: "neutral", blink: lidAt(t, 140), look: 0 });
  inCar(cam, out, c, 141, OFFICIAL(0), "off0", -0.3, -0.95, { expr: "smile", blink: lidAt(t, 141), look: 0 });
  inCar(cam, out, c, 142, OFFICIAL(1), "off1", 0.3, -0.95, { expr: "neutral", blink: lidAt(t, 142), look: 0 });
  const big = smooth((f - 470) / 20);
  // v2: the lens is beside the field at x ~4: dust stays ahead of the runners and off the near side
  for (let k = 0; k < 6; k++) dust(out, f, c.x - 2.6 + (k % 3) * 1.4, 0.9 + 0.4 * (k % 2), c.z + 1.6 + k * 0.7, 2.4 + 1.4 * big + 0.3 * k, k + 20, 0.75 + 0.18 * big);
  [[-2.3, 5.0], [2.4, 6.4], [-1.2, 8.6], [1.4, 10.2]].forEach(([x, g], i) => {
    const z = c.z + g;
    runner(cam, out, 143 + i, RUN(i + 2, `${8 + i * 9}`), `run${i + 2}`, x, z, t, 0, -1, S(f, 450) ? "pained" : "nervous", 0, true, 2.2, { blink: S(f, 482) ? 1 : lidAt(t, 143 + i) });
    cough(out, f, 455 + i * 6, x + 0.35, 1.8, z - 0.2, 0.5);
  });
};
// 6: Lorz by the MILE 9 post: the cramp
const cramp = (cam: CamInfo, t: number, f: number, out: Stage) => {
  const hop = S(f, 567) ? 0.1 * Math.abs(Math.sin(t * 9)) : 0;
  const zz = S(f, 567) ? CRAMP[2] : CRAMP[2] + 1.0 * (1 - smooth((f - 508) / 50));
  if (S(f, 567)) stand(cam, out, 150, LORZ, "lorz", CRAMP[0], hop, zz, { mode: "stand", expr: "pained", blink: lidAt(t, 150, [567 / FPS]), tilt: 12 * Math.sin(t * 9), prop: ["scratch", 0.5 + 0.5 * Math.sin(t * 9)] }, 1, true);
  else runner(cam, out, 150, LORZ, "lorz", CRAMP[0], zz, t, 0, -1, "smile", 0, true, 2.2);
  if (S(f, 572)) shout(out, "OUCH!", f, 572, t, CRAMP[0] + 0.45, 2.15, CRAMP[2] - 0.7, 0.6);
  for (let i = 0; i < 2; i++) runner(cam, out, 151 + i, RUN(i + 6, `${50 + i * 4}`), `run${i + 6}`, -0.6 - i * 1.1, CRAMP[2] + 6 - i * 2 - 2.2 * ((f - 508) / FPS), t, 0, -1, "pained", 0, true, 2.0);
  roadside(cam, out, t, f, CRAMP[2] + 3, 6, -1, false);
};
// 7: into the car, then waving at the runners as it pulls away past them
const ride = (cam: CamInfo, t: number, f: number, out: Stage) => {
  const c = carAt(7, f), s = (f - 594) / FPS;
  inCar(cam, out, c, 160, DRIVER, "driver", 0.35, 0.05, { expr: "grin", blink: lidAt(t, 160), look: 0 });
  const climb = smooth((f - 600) / 16);
  if (climb < 1) { const [x, z] = seat(c, -0.3, -0.95); stand(cam, out, 161, LORZ, "lorz", x + 1.0 * (1 - climb), 0.62 * climb, z, { mode: climb > 0.5 ? "sit" : "stand", expr: "grin", blink: lidAt(t, 161), look: -1 }, 1, climb < 0.3); }
  else inCar(cam, out, c, 161, LORZ, "lorz", -0.3, -0.95, { expr: S(f, 634) ? "laugh" : "grin", blink: lidAt(t, 161), look: -1, wave: S(f, 632) ? Math.sin(t * 14) : undefined });
  for (let i = 0; i < 3; i++) {
    const x = -1.4 + i * 0.75, z = MILE9.z - 3.5 - i * 2.5 - 2.4 * s, passed = c.z < z + 2;
    runner(cam, out, 162 + i, RUN(i + 7, `${22 + i * 6}`), `run${i + 7}`, x, z, t, 0, -1, passed ? "shock" : "pained", 0, true, 2.0);
  }
  for (let k = 0; k < 3; k++) dust(out, f, c.x - 0.2, 0.8 + 0.3 * k, c.z + 2.6 + k * 1.8, 2.6 + 0.7 * k, k + 30, 0.6);
  roadside(cam, out, t, f, MILE9.z - 4, 9, -1);
};
// 8: the breakdown: BANG, smoke from the hood; Lorz climbs out and jogs off
const breakdown = (cam: CamInfo, t: number, f: number, out: Stage) => {
  const c = carAt(8, f);
  inCar(cam, out, c, 170, DRIVER, "driver", 0.35, 0.05, { expr: S(f, 732) ? "shock" : "neutral", blink: lidAt(t, 170, [732 / FPS]), look: 0 });
  if (f < 764) inCar(cam, out, c, 171, LORZ, "lorz", -0.3, -0.95, { expr: S(f, 732) ? "nervous" : "grin", blink: lidAt(t, 171, [732 / FPS]), look: 0 });
  else { const s = Math.max(0, (f - 772) / FPS), z = c.z + 0.6 - 2.4 * s, x = c.x + 1.4 + 0.2 * smooth((f - 764) / 8);
    if (f < 772) stand(cam, out, 171, LORZ, "lorz", x, 0, c.z + 0.6, { mode: "stand", expr: "grin", blink: lidAt(t, 171), look: -1 });
    else runner(cam, out, 171, LORZ, "lorz", x, z, t, 0, -1, "grin", 0, true, 2.2); }
  if (S(f, 730)) for (let k = 0; k < 3; k++) { const u = Math.round(((((f - 730) / 30) + k / 3) % 1) * 8) / 8; fx1(out, `smoke|${u}`, 300, 300, (p) => fxSmoke(p, u), c.x + 0.15 * (k - 1), 1.2 + 1.2 * u, c.z - 1.6, 0.6 + 0.6 * u, 0.6 + 0.6 * u, true); }
  if (f < 752) shout(out, "BANG!", f, 731, t, c.x - 0.6, 2.4, c.z - 1.8, 1.0);
};
// 9: Lorz breaks the tape; the crowd goes wild
const crowdWall = (cam: CamInfo, t: number, f: number, out: Stage, wild: number, n = 9, z0 = -9) => {
  for (let i = 0; i < n; i++) {
    const side = i % 2 ? 1 : -1, z = z0 + Math.floor(i / 2) * 1.4 + (side > 0 ? 0.7 : 0), j = Math.max(0, Math.sin(t * 9 + i)) * 0.14 * (f >= wild ? 1 : 0);
    stand(cam, out, 180 + i, folk(i + 1), `folk${i + 1}`, STAD.x + side * (1.6 + 0.45 * (i % 3)), j, z, { mode: "stand", expr: f >= wild ? (i % 2 ? "laugh" : "grin") : "smile", blink: lidAt(t, 180 + i), prop: f >= wild && i % 3 === 0 ? "hatInHand" : null, wave: f >= wild && i % 3 !== 0 ? 0.6 + 0.4 * Math.sin(t * 12 + i) : undefined, look: -side }, 1, true);
  }
  if (f >= wild) for (let k = 0; k < 10; k++) { const u = (((f - wild) / 45) + hh(k, 2)) % 1, x = STAD.x - 3 + 6 * hh(k, 3) + 0.3 * Math.sin(t * 3 + k), y = 3.6 - 3.2 * u, z = z0 + 2 + 7 * hh(k, 4);
    const col = ["#e2453c", "#f2c230", "#3f6fb5", "#ffffff"][k % 4]; fx1(out, `conf|${col}|${k % 3}`, 40, 60, (p) => p.poly([[4, 4], [36, 8], [32, 56], [6, 52]], col, 3), x, y, z, 0.09, 0.13, false, k + t * 4); }
};
const tape = (out: Stage, f: number, at: number, z = 0, x = STAD.x, w = 9.2) => {
  const sn = clamp01((f - at) / 8), q2 = Math.round(sn * 8) / 8;
  fx1(out, `tape|${q2}`, 600, 120, (p) => fxTape(p, q2), x, 1.15 - 0.3 * sn, z, w, w * 0.2);
};
const finish = (cam: CamInfo, t: number, f: number, out: Stage) => {
  const s = (f - 800) / FPS, z = Math.max(-2.8, 4.2 - 4.5 * s);
  if (z > -2.8) runner(cam, out, 190, LORZ, "lorz", STAD.x + 0.2, z, t, 0, -1, S(f, 826) ? "laugh" : "grin", 0, true, 2.4, S(f, 826) ? { wave: Math.sin(t * 12) } : {});
  else stand(cam, out, 190, LORZ, "lorz", STAD.x + 0.2, 0, z, { mode: "stand", expr: "laugh", blink: lidAt(t, 190), wave: Math.sin(t * 12), look: 0 });
  tape(out, f, 826);
  crowdWall(cam, t, f, out, 836, 12, 0.8);
  if (S(f, 836)) for (let k = 0; k < 8; k++) { const u = (((f - 836) / 40) + hh(k, 7)) % 1, col = ["#e2453c", "#f2c230", "#3f6fb5", "#ffffff"][k % 4]; fx1(out, `conf|${col}|${k % 3}`, 40, 60, (p) => p.poly([[4, 4], [36, 8], [32, 56], [6, 52]], col, 3), STAD.x - 1.2 + 2.6 * hh(k, 8), 2.6 - 2.2 * u, -4.8 + 1.2 * hh(k, 9), 0.07, 0.1, false, k + t * 5); }
  if (S(f, 866)) for (let k = 0; k < 4; k++) flash(out, f, 866 + k * 4, STAD.x - 3.4 + k * 2.2, 2.6, -2 + k * 1.5, 0.8);
};
const WREATH_Y = 1.58; // centre of the laurel on Lorz's crown
// 10: Alice Roosevelt crowns him; the medal on its way
const wreath = (cam: CamInfo, t: number, f: number, out: Stage) => {
  stand(cam, out, 200, ALICE_O, "alice", ALICE[0], 0, ALICE[2], { mode: "stand", expr: "smile", blink: lidAt(t, 200), prop: S(f, 956) ? "present" : "palm", look: 1 });
  stand(cam, out, 201, LORZ, "lorz", LORZ_F[0], 0, LORZ_F[2], { mode: "stand", expr: S(f, 925) ? "grin" : "smile", blink: lidAt(t, 201, [925 / FPS]), look: -1 });
  const w = smooth((f - 912) / 14), wx = ALICE[0] + 0.35 + (LORZ_F[0] - ALICE[0] - 0.35) * w, wy = 1.25 + (WREATH_Y - 1.25) * w;
  // v3 (user: "medal and wreath not in the right place"): upright and 3 cm in front of their owner's card, so they stay on him from every angle
  out.fx.push({ key: "wreath", cw: 400, ch: 260, draw: (p) => fxWreath(p), x: wx, y: wy, z: LORZ_F[2] + 0.03 + 0.25 * (1 - w), w: 0.58, h: 0.38, upright: true });
  { const m = smooth((f - 958) / 16); out.fx.push({ key: `medal|${m > 0 ? 1 : 0}`, cw: 240, ch: 360, draw: (p) => fxMedal(p, m > 0 ? 1 : 0), x: ALICE[0] + 0.42 + 0.3 * m, y: 1.12 + 0.08 * m, z: ALICE[2] + 0.03, w: 0.22, h: 0.33, upright: true }); }
  crowdWall(cam, t, f, out, 99999, 12, -11);
  for (let i = 0; i < 3; i++) stand(cam, out, 202 + i, folk(i + 5), `folk${i + 5}`, ALICE[0] - 1.6 + i * 2.6, 0, ALICE[2] - 3.0 - (i % 2), { mode: "stand", expr: "grin", blink: lidAt(t, 202 + i), wave: i === 1 ? Math.sin(t * 10) : undefined, look: 0 }, 1, true);
};
/** the woman at the wall who shouts "He came by car!" (the shout is a woman's voice, user 9 Nov) */
const SHOUTER: Outfit = { jacket: "#e07a32", pants: "#8a3a8a", boots: "#5a3b2a", hat: "sunhat", dress: "#9a4a9a", skin: "#f5c9a0", hair: "#7a4a2a" };
// 11: HE CAME BY CAR! from the wall: Lorz sweats, the medal goes back
const shoutShot = (cam: CamInfo, t: number, f: number, out: Stage) => {
  const back = smooth((f - 1033) / 7);
  stand(cam, out, 210, ALICE_O, "alice", ALICE[0], 0, ALICE[2], { mode: "stand", expr: S(f, 1033) ? "stern" : S(f, 1023) ? "shock" : "smile", blink: lidAt(t, 210, [1023 / FPS, 1033 / FPS]), prop: "palm", look: 1 });
  stand(cam, out, 211, LORZ, "lorz", LORZ_F[0], 0, LORZ_F[2], { mode: "stand", expr: S(f, 1033) ? "pained" : S(f, 1023) ? "nervous" : "grin", blink: lidAt(t, 211, [1023 / FPS]), look: -1 });
  out.fx.push({ key: "wreath", cw: 400, ch: 260, draw: (p) => fxWreath(p), x: LORZ_F[0], y: WREATH_Y, z: LORZ_F[2] + 0.03, w: 0.58, h: 0.38, upright: true });
  // the medal: held out to Lorz, then snatched back
  out.fx.push({ key: "medal|1", cw: 240, ch: 360, draw: (p) => fxMedal(p, 1), x: ALICE[0] + 0.72 - 0.5 * back, y: 1.2 + 0.05 * back, z: ALICE[2] + 0.03, w: 0.22, h: 0.33, upright: true });
  if (S(f, 1035) && f < 1050) shout(out, "MINE!", f, 1035, t, ALICE[0] + 0.1, 2.2, ALICE[2] + 0.3, 0.55);
  stand(cam, out, 212, SHOUTER, "shouter", STAD.x - 1.9, 0, -0.2, { mode: "stand", expr: S(f, 1015) ? "shock" : "neutral", blink: lidAt(t, 212, [1015 / FPS]), prop: S(f, 1015) ? "point" : null, look: 1 }, 1, true);
  for (let i = 0; i < 4; i++) stand(cam, out, 213 + i, folk(i + 10), `folk${i + 10}`, STAD.x - 3.6 - 0.5 * (i % 2), 0, -2.6 + i * 1.3, { mode: "stand", expr: S(f, 1028) ? "shock" : "grin", blink: lidAt(t, 213 + i), look: 1 }, 1, true);
  if (f < 1031) shout(out, "HE CAME BY CAR!", f, 1015, t, STAD.x - 1.45, 2.3, 0.15, 0.62); // beside her head, in front of the stand
  if (S(f, 1030)) sweat(out, f, LORZ_F[0] + 0.3, 1.75, LORZ_F[2] + 0.1, 0.3);
};
// 12-14: Thomas Hicks and his trainers
const T1: V3 = [-0.78, 0, HICKS.z], T2: V3 = [0.8, 0, HICKS.z];
const hicks = (cam: CamInfo, t: number, f: number, out: Stage) => {
  const sag = S(f, 1111) ? smooth((f - 1109) / 14) : 0, sway = 7 * Math.sin(t * 3);
  stand(cam, out, 220, HICKS_O, "hicks", HICKS.x, -0.1 * sag, HICKS.z, { mode: "stand", expr: S(f, 1111) ? "dazed" : "pained", blink: lidAt(t, 220), tilt: sway + 22 * sag, headTilt: 10 * sag, look: 0 });
  for (const [i, T] of [[0, T1], [1, T2]] as const) {
    const no = S(f, 1161) ? Math.round(Math.sin(t * 16) * 2) / 2 : 0;
    stand(cam, out, 221 + i, TRAINER(i), `trainer${i}`, T[0] * 0.7, 0, T[2] + 0.15, { mode: "stand", expr: S(f, 1161) ? "stern" : "nervous", blink: lidAt(t, 221 + i, [1161 / FPS]), prop: "palm", look: i ? -1 : 1, headTilt: 12 * no });
  }
  sweat(out, f, HICKS.x + 0.32, 2.0, HICKS.z + 0.1, 0.3);
  if (S(f, 1161)) shout(out, "NO!", f, 1161, t, T2[0] + 0.5, 2.45, T2[2] + 0.2, 0.9);
  roadside(cam, out, t, f, HICKS.z + 3, 6, -1, false);
};
const poison = (cam: CamInfo, t: number, f: number, out: Stage) => {
  stand(cam, out, 225, HICKS_O, "hicks", HICKS.x - 0.35, 0, HICKS.z, { mode: "stand", expr: S(f, 1268) ? "shock" : "dazed", blink: lidAt(t, 225), tilt: 6 * Math.sin(t * 3), look: 1 });
  stand(cam, out, 226, TRAINER(0), "trainer0", T2[0], 0, T2[2], { mode: "stand", expr: "grin", blink: lidAt(t, 226), prop: "palm", look: -1 });
  const items: [number, string, (p: Pen) => void, number, number][] = [
    [1191, "poison", (p) => fxPoison(p, 0), 0.26, 0.6], [1226, "eggs", (p) => fxEggs(p), 0.34, 0.26], [1259, "brandy", (p) => fxPoison(p, 1), 0.26, 0.6]];
  items.forEach(([at, key, dr, w, h], i) => { if (!S(f, at)) return; const k = pop(f, at); fx1(out, key, key === "eggs" ? 260 : 180, key === "eggs" ? 200 : 420, dr, 0.2 + i * 0.22, 1.05 + (i === 1 ? -0.12 : 0), T2[2] + 0.5, w * k, h * k); });
  label(out, "RAT POISON", 0.25, 2.34, T2[2] + 0.4, f, 1191, 1.0, 0.23, "#d9382e");
  label(out, "+ EGG WHITES", 0.25, 2.09, T2[2] + 0.4, f, 1226, 1.0, 0.2, "#ffffff");
  label(out, "+ BRANDY", 0.25, 1.86, T2[2] + 0.4, f, 1259, 0.8, 0.2, "#f2c230");
  if (S(f, 1268)) { const u = Math.round((((f - 1268) / 15) % 1) * 6) / 6; fx1(out, `cup|${u}`, 200, 200, (p) => fxCup(p, u), HICKS.x - 0.05, 1.45, HICKS.z + 0.25, 0.22, 0.22); }
};
const dose = (cam: CamInfo, t: number, f: number, out: Stage) => {
  const see = S(f, 1316);
  stand(cam, out, 227, HICKS_O, "hicks", HICKS.x - 0.05, 0, HICKS.z, { mode: "stand", expr: see ? "dazed" : S(f, 1296) ? "shock" : "pained", blink: lidAt(t, 227, [1296 / FPS, 1316 / FPS]), tilt: see ? 8 * Math.sin(t * 4) : 0, headTilt: see ? 8 * Math.sin(t * 3) : 0, look: 0 });
  if (f < 1300) { const u = Math.round((((f - 1284) / 15) % 1) * 6) / 6; fx1(out, `cup|${u}`, 200, 200, (p) => fxCup(p, u), HICKS.x + 0.22, 1.72, HICKS.z + 0.3, 0.2, 0.2); }
  if (S(f, 1296) && f < 1316) flash(out, f, 1296, HICKS.x - 0.05, 2.2, HICKS.z + 0.2, 0.7);
  if (see) { const u = Math.round((((f - 1316) / 20) % 1) * 10) / 10; fx1(out, `dizzy|${u}`, 400, 260, (p) => fxDizzy(p, u), HICKS.x - 0.05, 2.32, HICKS.z + 0.1, 0.75, 0.49); }
  if (S(f, 1325)) { const k = pop(f, 1325), u = Math.round((((f - 1325) / 15) % 1) * 6) / 6; fx1(out, `eggdream|${u}`, 420, 340, (p) => fxEggDream(p, u), HICKS.x + 0.45, 2.32, HICKS.z + 0.1, 0.6 * k, 0.49 * k); }
};
// 15: carried over the line, feet pedalling in the air
const carried = (cam: CamInfo, t: number, f: number, out: Stage) => {
  const s = (f - 1352) / FPS, z = Math.max(-2.2, 2.6 - 2.3 * s);
  for (let i = 0; i < 2; i++) runner(cam, out, 230 + i, TRAINER(i), `trainer${i}`, STAD.x + (i ? 0.5 : -0.5), z + 0.15, t, 0, -1, "stern", 0, true, 1.6, { prop: "palm" });
  const q2 = q(((t * 4.5) % 1 + 1) % 1, 12);
  out.places.push(person(cam, { i: 232, o: HICKS_O, okey: "hicks" }, STAD.x, 0.58, z - 0.25, { side: false, mirror: false }, { mode: "march", phase: q2, expr: "dazed", blink: 0, lift: 170, tilt: 4 * Math.sin(t * 5) }, {}));
  blob(out, STAD.x, 0, z - 0.25, 0.8, 0.5);
  runLines(out, f, STAD.x, 0.75, z - 0.15, 0.36);
  for (let k = 0; k < 3; k++) { const u = Math.round(((((f - 1352) / 14) + k / 3) % 1) * 8) / 8; fx1(out, `puff|${u}`, 300, 300, (p) => fxPuff(p, u * 0.9), STAD.x + (k - 1) * 0.25, 0.25 + 0.2 * u, z - 0.1, 0.45 + 0.3 * u, 0.45 + 0.3 * u, true); }
  tape(out, f, 1384);
  crowdWall(cam, t, f, out, 1390, 10, 1.5);
};
// 16-19: Andarin Carvajal
const mailman = (cam: CamInfo, t: number, f: number, out: Stage) => {
  stand(cam, out, 240, CARV_O, "carv", CARV[0], 0, CARV[2], { mode: "stand", expr: S(f, 1530) ? "nervous" : "grin", blink: lidAt(t, 240, [1530 / FPS]), prop: S(f, 1530) ? "palm" : "envelope", look: 0 });
  if (f < 1481) label(out, "4TH PLACE", CARV[0], 2.22, CARV[2] + 0.2, f, 1455, 0.85, 0.22, "#f2c230");
  else label(out, "CUBAN MAILMAN", CARV[0], 2.22, CARV[2] + 0.2, f, 1481, 1.15, 0.24, "#ffffff");
  if (S(f, 1534)) { const k = pop(f, 1534), u = Math.round((((f - 1534) / 20) % 1) * 6) / 6; fx1(out, `broke|${u}`, 360, 260, (p) => fxBroke(p, u), CARV[0] + 0.45, 1.15, CARV[2] + 0.35, 0.55 * k, 0.4 * k); }
  roadside(cam, out, t, f, CARV[2] - 1, 6, -1);
};
const shortsShot = (cam: CamInfo, t: number, f: number, out: Stage) => {
  stand(cam, out, 241, CARV_O, "carv", CARV[0], 0, CARV[2], { mode: "stand", expr: S(f, 1604) ? "grin" : "nervous", blink: lidAt(t, 241, [1604 / FPS]), look: 1 });
  if (S(f, 1590) && f < 1618) { const o = Math.round(Math.abs(Math.sin((f - 1590) * 0.6)) * 4) / 4; fx1(out, `scissors|${o}`, 300, 200, (p) => fxScissors(p, o), CARV[0] + 0.32, 0.55, CARV[2] + 0.25, 0.42, 0.28); }
  if (S(f, 1604)) for (let k = 0; k < 2; k++) { const u = clamp01((f - 1604 - k * 3) / 14), y = 0.3 - 0.12 * u; fx1(out, `leg${k}|${Math.round(u * 6) / 6}`, 80, 260, (p) => p.poly([[8, 8], [72, 8], [70, 252], [10, 252]], "#3a3346", 6), CARV[0] - 0.12 + k * 0.24 + (k ? 0.15 : -0.15) * u, y, CARV[2] + 0.25, 0.11, 0.36, false, (k ? -1 : 1) * 1.2 * u); }
  if (S(f, 1600)) { const u = Math.round((((f - 1600) / 10) % 1) * 4) / 4; void u; shout(out, "SNIP!", f, 1597, t, CARV[0] + 0.5, 1.85, CARV[2] + 0.3, 0.45); }
};
const fruit = (cam: CamInfo, t: number, f: number, out: Stage) => {
  if (f < 1652) {
    const z = CARV[2] - 8.5, s = (f - 1624) / FPS;
    stand(cam, out, 242, folk(14), "folk14", 3.9, ROAD.field, z - 0.2, { mode: "stand", expr: S(f, 1638) ? "shock" : "smile", blink: lidAt(t, 242, [1638 / FPS]), prop: "palm", look: -1 }, 1, true);
    runner(cam, out, 243, CARV_O, "carv", 2.0 - 0.0 * s, z + 2.5 - 2.6 * s, t, 0, -1, S(f, 1636) ? "grin" : "smile", 0, true, 2.2);
    const grab = smooth((f - 1630) / 8);
    for (let k = 0; k < 2; k++) fx1(out, `peach`, 160, 160, (p) => fxPeach(p), 3.55 + (2.25 - 3.55) * grab + k * 0.16, 1.15 + 0.2 * grab, z - 0.05 + (2.5 - 2.6 * s + 0.2) * grab, 0.17, 0.17);
  } else {
    stand(cam, out, 244, CARV_O, "carv", NAP[0], NAP[1], NAP[2], { mode: "stand", expr: S(f, 1671) ? "pained" : "grin", blink: lidAt(t, 244, [1671 / FPS]), look: 0 });
    const u = Math.round((((f) / 15) % 1) * 6) / 6; fx1(out, `apple|${u}`, 180, 180, (p) => fxApple(p, u), NAP[0] + 0.2, 1.42, NAP[2] + 0.3, 0.2, 0.2);
    for (let k = 0; k < 3; k++) fx1(out, `apple|${u}|g`, 180, 180, (p) => fxApple(p, u), NAP[0] - 0.7 + k * 0.4, NAP[1] + 0.08, NAP[2] + 0.5 + (k % 2) * 0.3, 0.18, 0.18);
    if (S(f, 1680)) sweat(out, f, NAP[0] + 0.3, 2.0, NAP[2] + 0.1, 0.3);
  }
};
const nap = (cam: CamInfo, t: number, f: number, out: Stage) => {
  out.places.push({ ...person(cam, { i: 245, o: CARV_O, okey: "carv" }, NAP[0] + 0.95, NAP[1] + 0.22, NAP[2], { side: false, mirror: false }, { mode: "stand", expr: "smile_closed", blink: 1, look: 0 }, {}), roll: Math.PI / 2 });
  const u = Math.round((((f - 1704) / 40) % 1) * 10) / 10; fx1(out, `zzz|${u}`, 240, 240, (p) => fxZzz(p, u), NAP[0] - 0.8, 0.95, NAP[2] + 0.1, 0.6, 0.6);
  for (let k = 0; k < 2; k++) fx1(out, `apple|0|g`, 180, 180, (p) => fxApple(p, 0), NAP[0] + 0.5 + k * 0.3, NAP[1] + 0.08, NAP[2] + 0.45, 0.18, 0.18);
  label(out, "STILL 4TH!", NAP[0] - 0.1, 1.5, NAP[2] + 0.2, f, 1745, 1.3, 0.32, "#f2c230");
};
// 20: the dog chase across the field
const dog = (cam: CamInfo, t: number, f: number, out: Stage) => {
  const x = dogRunX(f);
  runner(cam, out, 250, LEN_O, "len", x, DOGF.z, t, -1, 0, "shock", ROAD.field, true, 3.4, { lift: 170, tilt: 14, wave: Math.sin(t * 22) });
  for (let k = 0; k < 4; k++) { const u = Math.round(((((f - 1770) / 12) + k / 4) % 1) * 8) / 8; fx1(out, `puff|${u}`, 300, 300, (p) => fxPuff(p, u * 0.9), x + 0.5 + 0.9 * k + 0.6 * u, ROAD.field + 0.2 + 0.25 * u, DOGF.z + 0.05, 0.45 + 0.35 * u, 0.45 + 0.35 * u, true); }
  runLines(out, f, x + 0.8, 1.0, DOGF.z - 0.05, 0.35);
  sweat(out, f, x - 0.25, 2.0, DOGF.z + 0.1, 0.3); sweat(out, f + 9, x + 0.3, 2.05, DOGF.z + 0.1, 0.26);
  const ph2 = Math.round((((f / 7)) % 1) * 8) / 8, leap = 0.25 * Math.abs(Math.sin(f / 7 * Math.PI));
  fx1(out, `dog|${ph2}`, 420, 300, (p) => { p.g.translate(420, 0); p.g.scale(-1, 1); fxDog(p, ph2); }, x + 1.15, ROAD.field + 0.6 + 0.4 * leap, DOGF.z + 0.12, 1.6, 1.14);
  if (f < 1832) shout(out, "GRRR!", f, 1789, t, x + 1.05, 1.8, DOGF.z + 0.15, 0.6);
  label(out, "1 MILE OFF COURSE", x + 1.0, 2.2, DOGF.z, f, 1803, 1.6, 0.28, "#ffffff");
};
// 21: banned for life... for six months
const banned = (cam: CamInfo, t: number, f: number, out: Stage) => {
  stand(cam, out, 260, LORZ, "lorz", BAN[0], 0, BAN[2], { mode: "stand", expr: S(f, 1956) ? "grin" : S(f, 1886) ? "shock" : "nervous", blink: lidAt(t, 260, [1886 / FPS, 1956 / FPS]), look: 0 });
  if (S(f, 1886)) { const k = 1 + 1.5 * (1 - smooth((f - 1884) / 5)), cr = Math.round(smooth((f - 1950) / 12) * 6) / 6; fx1(out, `banned|${cr}`, 600, 260, (p) => fxBanned(p, "BANNED", "FOR LIFE", cr), BAN[0] + 0.3, 1.42, BAN[2] + 0.75, 0.95 * k, 0.41 * k); }
  if (S(f, 1945)) { const k = pop(f, 1945); fx1(out, "cal6", 260, 300, (p) => fxCalendar(p, "6", "MONTHS"), BAN[0] + 0.45, 1.98, BAN[2] + 0.95, 0.3 * k, 0.35 * k); }
};
// 22: Boston 1905: Lorz breaks the tape under the banner
const bostonShot = (cam: CamInfo, t: number, f: number, out: Stage) => {
  const z = Math.min(bosZ(f), BOSTON.z + 2.6);
  if (bosZ(f) < BOSTON.z + 2.6) runner(cam, out, 270, LORZ, "lorz", 0.1, z, t, 0, 1, S(f, 2002) ? "laugh" : "grin", 0, true, 2.4, S(f, 2004) ? { wave: Math.sin(t * 12) } : {});
  else stand(cam, out, 270, LORZ, "lorz", 0.1, 0, z, { mode: "stand", expr: "laugh", blink: lidAt(t, 270), wave: Math.sin(t * 12), look: 0 });
  tape(out, f, 2002, BOSTON.z, 0, 4.8);
  // a race official checking around him for a car with a magnifying glass
  stand(cam, out, 279, OFFICIAL(0), "off0", -0.5, 0, BOSTON.z + 2.5, { mode: "stand", expr: S(f, 2010) ? "stern" : "neutral", blink: lidAt(t, 279), prop: "point", look: 1, headTilt: 10 * Math.sin(t * 3) });
  fx1(out, "lens", 200, 300, (p) => { p.stroke([[100, 170], [130, 290]], 16, "#6a4426"); p.ell(100, 100, 80, 80, "rgba(200,230,255,0.55)", 12); }, -0.46, 1.72 + 0.05 * Math.sin(t * 4), BOSTON.z + 2.7, 0.3, 0.45);
  if (S(f, 2014)) { const k = smooth((f - 2014) / 8), wob = 0.08 * Math.sin(t * 8); out.fx.push({ key: "question", cw: 240, ch: 360, draw: (p) => fxQuestion(p), x: -0.95, y: 1.95, z: BOSTON.z + 2.6, w: 0.26 * k, h: 0.39 * k, rot: wob }); }
  for (let i = 0; i < 8; i++) { const s2 = i % 2 ? 1 : -1, zz = BOSTON.z - 1 + Math.floor(i / 2) * 1.6; stand(cam, out, 271 + i, folk(i + 2), `folk${i + 2}`, s2 * (2.4 + 0.3 * (i % 3)), 0, zz, { mode: "stand", expr: S(f, 2004) ? "laugh" : "grin", blink: lidAt(t, 271 + i), wave: S(f, 2004) && i % 2 ? Math.sin(t * 11 + i) : undefined, prop: i % 4 === 0 && S(f, 2004) ? "hatInHand" : null, look: -s2 }, 1, true); }
};
// 23: on foot, this time: jogging past a parked car, a grin and a point at his feet
const foot = (cam: CamInfo, t: number, f: number, out: Stage) => {
  const z = footZ(f), c = carAt(23, f);
  if (f < 2088) runner(cam, out, 280, LORZ, "lorz", 0.6, z, t, 0, 1, S(f, 2052) ? "grin" : "smile", 0, true, 2.2, S(f, 2052) ? { prop: "point" } : {});
  else stand(cam, out, 280, LORZ, "lorz", 0.6, 0, footZ(2088), { mode: "stand", expr: "grin", blink: lidAt(t, 280), prop: "point", look: 1 });
  inCar(cam, out, c, 281, DRIVER, "driver", 0.35, 0.05, { expr: "shock", blink: lidAt(t, 281), look: -1 });
  roadside(cam, out, t, f, BOSTON.z + 18, 8, -1);
};

/** everything with a face (and every 2D effect) in shot `id` at time t */
export const stage = (id: number, t: number, f: number, cam: CamInfo): Stage => {
  const out: Stage = { places: [], fx: [] };
  const s = SHOTS[id - 1];
  LNAME = s.light;
  findSun(cam, SUN);
  const fn: Record<string, (c: CamInfo, t: number, f: number, o: Stage) => void> = {
    hook, setting, well, science, dust: dustShot, cramp, ride, breakdown, finish, wreath, shout: shoutShot, hicks, poison, dose, carried,
    mailman, shorts: shortsShot, fruit, nap, dog, banned, boston: bostonShot, foot,
  };
  fn[s.crowd]?.(cam, t, f, out);
  return out;
};
export { FPS, clamp01, NOINK };
