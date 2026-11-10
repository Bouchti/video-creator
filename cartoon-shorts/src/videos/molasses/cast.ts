import type { LightName } from "./lights";
// The molasses-flood cast as lit flat sprites in the 3D world. Each frame every character asks for a drawing (a key + a draw
// call); the pool keeps one canvas per distinct drawing. People are yaw-only billboards on the 600 x 1000 card, shaded by
// cardShade() and standing on a soft multiply contact blob. Effects are unlit cards. Everything lives on the NOINK layer.
import * as THREE from "three";
import {
  Pen, bodyFront, bodySide, fxShadow, fxContact, fxPuff, fxQuestion, fxCreak, fxSplash,
  INK, Outfit, Expr, FrontOpts, SideOpts, parisian, tourist, KID, MANAGER, MINISTER,
} from "./toon";
import { fxCount, fxTag, fxExclaim, fxFlashStar } from "./mikedraw";
import {
  fxTankFill, fxBlueprint, fxLeak, fxBucket, fxRivet, fxThermo, fxBomb, fxHeadline, fxStrands, fxScent, fxBottle, fxShout, fxCross, fxEngineer,
  fxPaintCan, fxSparkle, fxCalendar, fxSpeed, fxSweat, fxSyrupDrop, fxShatter, fxReceiver, fxLabel, fxGoo, fxGooFeet, fxStill, fxGull, fxRunLines,
} from "./molassesdraw";
import {
  FPS, SHOTS, clamp01, smooth, V3, XC, waveZ, HOOK_CAM, TANK, EL, WHARF_X, OFFICE, COURT, SUBWAY, LADDER, LDIR, JELL_DESK, BOSS_DESK, JUDGE, BENCH, BOOTH, WALL,
  STUCK, PRESS, SNIFF, RIVETS, STREET,
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


// ---------------- the molasses cast ----------------
const S = (f: number, a: number) => f >= a - 2; // a reaction lands 0-3 f before its word
const ph = (t: number, i: number, rate: number, n = 12) => Math.round((((t * rate + hh(i, 5)) % 1) + 1) % 1 * n) / n;
const fx1 = (out: Stage, key: string, cw: number, ch: number, draw: (p: Pen) => void, x: number, y: number, z: number, w: number, h: number, soft = false, rot = 0) =>
  out.fx.push({ key, cw, ch, draw, x, y, z, w, h, soft, rot });
const pop = (f: number, f0: number) => smooth((f - f0) / 5) * (1 + 0.15 * Math.max(0, 1 - (f - f0) / 8));
const label = (out: Stage, text: string, x: number, y: number, z: number, f: number, f0: number, w: number, h: number, bg = "#f2c230", lines = false) => {
  const k = pop(f, f0), ch = Math.round((640 * h) / w);
  if (k > 0) fx1(out, `label|${text}|${bg}|${lines}`, 640, ch, (p) => fxLabel(p, text, 640, ch, bg, INK, lines), x, y, z, w * k, h * k);
};
const sit = (cam: CamInfo, out: Stage, i: number, o: Outfit, okey: string, x: number, y: number, z: number, fo: FrontOpts, scale = 1) =>
  stand(cam, out, i, o, okey, x, y, z, { ...fo, mode: "sit" }, scale, false);
/** someone running toward (dx, dz): front or side view by the camera, fast stroll phase, open-mouthed */
const runner = (cam: CamInfo, out: Stage, i: number, o: Outfit, okey: string, x: number, z: number, t: number, dx: number, dz: number, expr: Expr, y = 0, shadow = true, sprint = false) => {
  const view = viewOf(cam, x, z, dx, dz), p2 = q(((t * (sprint ? 2.6 : 3.2) + hh(i, 5)) % 1 + 1) % 1, 12);
  out.places.push(person(cam, { i, o, okey }, x, y, z, view, { mode: sprint ? "march" : "stroll", phase: p2, expr, blink: 0, tilt: -4, lift: sprint ? 150 : 60 }, { mode: "march", phase: p2, expr, blink: 0, stomp: 0.9, stride: 1.1 * view.fs }));
  if (shadow) blob(out, x, y, z);
};
const JELL: Outfit = { jacket: "#5a6070", pants: "#3f4454", boots: "#3a2a22", hat: "bowler", hatCol: "#2e2a36", tie: "#c0353a", buttons: "#d9dde0", moustache: "#4a3426", skin: "#f5c9a0" };
const BOSS: Outfit = { ...MANAGER, jacket: "#2e3240", sash: undefined, tie: "#8c3b4a" };
const JUDGE_O: Outfit = { ...MINISTER, jacket: "#1f1d24", pants: "#1f1d24", tie: undefined };
const SAILOR: Outfit = { jacket: "#1f2a44", pants: "#1f2a44", boots: INK, hat: "cap", cap: "#f4f6fb", buttons: "#f4f6fb", skin: "#f5c9a0" };
const WORKER = (v: number): Outfit => ({ jacket: ["#6a5a4a", "#4f5566", "#7a6040"][v % 3], pants: "#3f4454", boots: "#3a2a22", hat: "cap", cap: ["#4a4552", "#6a5a44", "#3a3d47"][v % 3], skin: ["#f5c9a0", "#e0b48a", "#c98e64"][v % 3], braces: "#5a3b2a" });
const REPORTER = (v: number): Outfit => ({ jacket: ["#6a5a4a", "#4f5566", "#7a6040"][v % 3], pants: "#3f4454", boots: "#3a2a22", hat: "fedora", hatCol: ["#3a3346", "#5a4a3a", "#2e2a36"][v % 3], tie: ["#3f6fb5", "#c0353a", "#3a6a4a"][v % 3], skin: ["#ffe2c2", "#f5c9a0", "#e0b48a"][v % 3] });
const BOY: Outfit = { ...KID, jacket: "#5d7a3a", cap: "#8c3b4a" };
const folk = (i: number): Outfit => parisian(i);
const tang: [number, number] = [LDIR[1], -LDIR[0]]; // along the tank wall (street side), unit
const onWall = (k: number, outk = 0.2): [number, number] => [WALL[0] + LDIR[0] * outk + tang[0] * k, WALL[2] + LDIR[1] * outk + tang[1] * k];
const leaks = (out: Stage, f: number, spots: number[], top = 6.0, w = 0.5) => spots.forEach((k, i) => {
  const [x, z] = onWall(k, 0.25), u = Math.round((((f / 20) + hh(i, 4)) % 1) * 10) / 10, h = top - (i % 2) * 1.6;
  fx1(out, `leak|${u}`, 80, 400, (p) => fxLeak(p, u), x, h / 2, z, w, h);
  fx1(out, "pool", 300, 120, (p) => p.ell(150, 60, 140, 50, "#7a4218", 5), x + LDIR[0] * 0.5, 0.06, z + LDIR[1] * 0.5, 1.1, 0.45, false);
});
const flash = (out: Stage, f: number, at: number, x: number, y: number, z: number, s = 0.8) => {
  if (f >= at && f < at + 8) { const u = Math.round(((f - at) / 8) * 8) / 8; fx1(out, `flash|${u}`, 500, 500, (p) => fxFlashStar(p, u), x, y, z, s, s); }
};
const puff = (out: Stage, f: number, f0: number, x: number, y: number, z: number, s = 1.2, len = 18) => {
  if (f < f0 || f >= f0 + len) return;
  const q2 = Math.round(((f - f0) / len) * 10) / 10;
  fx1(out, `puff|${q2}`, 300, 300, (p) => fxPuff(p, q2 * 0.9), x, y + 0.2 * q2, z, s * (0.7 + q2), s * (0.7 + q2), true);
};
const shout = (out: Stage, text: string, f: number, f0: number, t: number, x: number, y: number, z: number, s = 1.5) => {
  if (f < f0) return;
  const k = pop(f, f0), u = Math.round(((t * 6) % 1) * 4) / 4;
  fx1(out, `shout|${text}|${u}`, 420, 300, (p) => fxShout(p, text, u), x, y, z, s * k, 0.714 * s * k);
};

/** syrup flung off the crest and splashing at the foot, across the wave's width */
const spray = (out: Stage, f: number, z: number, xc = XC, width = 20, n = 6) => {
  for (let i = 0; i < n; i++) {
    const x = xc - width / 2 + (i + 0.5) * (width / n) + (hh(i, 7) - 0.5) * 1.5, u = Math.round((((f / 18) + hh(i, 3)) % 1) * 8) / 8, v = Math.round((((f / 14) + hh(i, 9)) % 1) * 8) / 8;
    fx1(out, `goo|${u}`, 400, 300, (p) => fxGoo(p, u), x, 7.6 + 0.4 * hh(i, 1), z + 3.0, 2.6, 1.95);
    fx1(out, `goo|${v}`, 400, 300, (p) => fxGoo(p, v), x + 1.2, 0.9, z + 1.4, 2.2, 1.65);
  }
};
// 1: the hook: the wave crashing down the street at the lens, people sprinting at us shouting, two carried on the crest
const hook = (cam: CamInfo, t: number, f: number, out: Stage) => {
  const z = waveZ(1, f), s = f / FPS;
  // the hero, sprinting at the lens 2-3 m in front of it; the others between him and the wave
  runner(cam, out, 99, folk(0), "folk0", HOOK_CAM[0] - 0.15, HOOK_CAM[2] - 3.0 + 0.4 * s, t, 0, 1, "shock", 0, true, true);
  for (const sx of [-1, 1]) { const u = Math.round((((f / 6) + (sx > 0 ? 0.5 : 0)) % 1) * 6) / 6; fx1(out, `runlines|${u}`, 300, 300, (p) => fxRunLines(p, u), HOOK_CAM[0] - 0.15 + sx * 0.42, 1.15, HOOK_CAM[2] - 3.1 + 0.4 * s, 0.45, 0.45, false, sx > 0 ? Math.PI : 0); }
  puff(out, f, 0, HOOK_CAM[0] - 0.15, 0.1, HOOK_CAM[2] - 3.1 + 0.4 * s, 0.8, 14); puff(out, f, 14, HOOK_CAM[0] - 0.15, 0.1, HOOK_CAM[2] - 3.1 + 0.4 * s, 0.8, 14);
  puff(out, f, 28, HOOK_CAM[0] - 0.15, 0.1, HOOK_CAM[2] - 3.1 + 0.4 * s, 0.8, 14); puff(out, f, 42, HOOK_CAM[0] - 0.15, 0.1, HOOK_CAM[2] - 3.1 + 0.4 * s, 0.8, 14);
  const lanes: [number, number][] = [[1.9, 5.4], [-3.4, 4.6], [4.4, 3.8], [-1.6, 3.2], [2.8, 2.6], [-5.2, 2.9]];
  lanes.forEach(([dx, g], i) => { const zz = z + g + 1.2 * s; if (zz < HOOK_CAM[2] - 1.5) runner(cam, out, 101 + i, folk(i + 1), `folk${i + 1}`, XC + dx, zz, t, 0, 1, "shock"); });
  for (let i = 0; i < 7; i++) { const u = Math.round((((f / 16) + hh(i, 6)) % 1) * 8) / 8, x = XC - 7 + i * 2.3 + hh(i, 2);
    fx1(out, `drip|${u}`, 80, 400, (p) => fxLeak(p, u), x, 4.6 - 0.4 * hh(i, 4), z + 3.1, 0.34, 1.7); }
  ([[0, -2.6], [1, 2.8]] as const).forEach(([i, dx]) => stand(cam, out, 120 + i, folk(i + 7), `folk${i + 7}`, XC + dx, 6.0 + 0.25 * Math.sin(t * 5 + i), z + 2.4,
    { mode: "fall", expr: "shock", blink: 0, tilt: (i ? 10 : -10) * Math.sin(t * 4 + i) }, 1, false));
  ([[2, -5.2, 3.4], [3, 6.2, 2.8]] as const).forEach(([i, dx, y]) => stand(cam, out, 122 + i, folk(i + 9), `folk${i + 9}`, XC + dx, y + 0.5 * Math.sin(t * 3 + i), z + 1.9,
    { mode: "fall", expr: "shock", blink: 0, tilt: (i % 2 ? 1 : -1) * (20 + 25 * Math.sin(t * 5 + i)) }, 1, false));
  if (f < 46) { shout(out, "AAAH!", f, 2, t, HOOK_CAM[0] - 0.75, 2.6, HOOK_CAM[2] - 3.6, 0.8); shout(out, "RUN!", f, 18, t, HOOK_CAM[0] + 1.3, 2.9, HOOK_CAM[2] - 4.2, 0.85); }
  spray(out, f, z);
};
// 2: alongside the wave: the 35 MPH tag riding with it
const speed = (cam: CamInfo, t: number, f: number, out: Stage) => {
  const z = waveZ(2, f), s = (f - 58) / FPS;
  [-4.5, -1.5, 1.8, 5.2, 9.0].forEach((x, i) => runner(cam, out, 130 + i, folk(i + 2), `folk${i + 2}`, x, z + 3.4 + i * 1.4 - 1.0 * s, t, 0, 1, "shock"));
  stand(cam, out, 140, folk(9), "folk9", XC + 1.5, 6.4 + 0.2 * Math.sin(t * 5), z + 0.7, { mode: "fall", expr: "shock", blink: 0, tilt: 8 * Math.sin(t * 4) }, 1, false);
  label(out, "35 MPH", 0.2, 4.8, z + 4.0, f, 89, 3.0, 1.33, "#f2c230", true);
  spray(out, f, z);
};
// 3: the calm street before: the tank in its yard, walkers; the 50 FT tag, the molasses gauge
const tankShot = (cam: CamInfo, t: number, f: number, out: Stage) => {
  for (let i = 0; i < 5; i++) walker(cam, out, 150 + i, folk(i + 3), `folk${i + 3}`, -5 + (i % 2) * 3.2, 0, 4 + i * 3.5 + (i % 2 ? -1 : 1) * 0.9 * ((f - 133) / FPS), t, 0, i % 2 ? -1 : 1, "smile");
  label(out, "50 FT", TANK.x - 11.5, 16.5, TANK.z + 9, f, 176, 6.5, 2.9, "#ffffff");
  if (f >= 224) { const k = pop(f, 224), lvl = smooth((f - 228) / 22); fx1(out, `fill|${Math.round(lvl * 20) / 20}`, 300, 420, (p) => fxTankFill(p, lvl), TANK.x - 17, 7.5, TANK.z + 17, 3.6 * k, 5.0 * k); }
};
// 4: the treasurer at his desk: NOT an engineer (a crossed-out hard hat), an accountant (the nameplate, the adding machine)
const office = (cam: CamInfo, t: number, f: number, out: Stage) => {
  stand(cam, out, 200, JELL, "jell", JELL_DESK[0], 0, JELL_DESK[2], { mode: "stand", expr: S(f, 361) ? "grin" : S(f, 301) ? "nervous" : "smile", blink: lidAt(t, 200, [301 / FPS, 361 / FPS]),
    prop: S(f, 361) ? ["crank", Math.round(((t * 4) % 1) * 4) / 4] : "pen", look: 0 });
  if (S(f, 301)) {
    const k = pop(f, 301); fx1(out, "engineer", 240, 240, (p) => fxEngineer(p), JELL_DESK[0] - 1.0, 2.25, JELL_DESK[2] + 0.4, 0.62 * k, 0.62 * k);
    if (S(f, 309)) { const k2 = pop(f, 309); fx1(out, "cross", 300, 300, (p) => fxCross(p), JELL_DESK[0] - 1.0, 2.25, JELL_DESK[2] + 0.45, 0.72 * k2, 0.72 * k2); }
  }
  label(out, "ACCOUNTANT", JELL_DESK[0] + 0.05, 0.92, JELL_DESK[2] + 1.42, f, 361, 1.05, 0.26, "#e8c45a");
};
// 5: the blueprint: held upside down, turned sideways, then the "?"
const blueprint = (cam: CamInfo, t: number, f: number, out: Stage) => {
  stand(cam, out, 201, JELL, "jell", JELL_DESK[0], 0, JELL_DESK[2], { mode: "stand", expr: S(f, 421) ? "dazed" : "smile", blink: lidAt(t, 201, [421 / FPS]), prop: "palm", look: 0, headTilt: S(f, 410) ? -10 : 0 });
  const rot = S(f, 410) ? (-Math.PI / 2) * smooth((f - 408) / 8) : 0;
  fx1(out, "blueprint|1", 520, 380, (p) => fxBlueprint(p, true), JELL_DESK[0] + 0.36, 1.0, JELL_DESK[2] + 0.42, 0.6, 0.44, false, rot);
  if (S(f, 423)) { const k = smooth((f - 421) / 8), wob = 0.08 * Math.sin(t * 8); out.fx.push({ key: "question", cw: 240, ch: 360, draw: (p) => fxQuestion(p), x: JELL_DESK[0] - 0.35, y: 2.25, z: JELL_DESK[2] + 0.3, w: 0.26 * k, h: 0.39 * k, rot: wob }); }
};
// 6: the leaks, and the treasurer whistling beside them
const leak = (cam: CamInfo, t: number, f: number, out: Stage) => {
  leaks(out, f, [-1.6, -0.2, 1.3, 2.7]);
  const [x, z] = onWall(-1.9, 2.4);
  stand(cam, out, 202, JELL, "jell", x, 0, z, { mode: "stand", expr: S(f, 488) ? "whistle" : "smile", blink: lidAt(t, 202), prop: "present", look: 1 });
  if (S(f, 490)) { const [x2, z2] = onWall(0.6, 0.6), k = pop(f, 490); fx1(out, "syrupPool", 300, 300, (p) => p.ell(150, 150, 140, 60, "#7a4218", 6), x2, 0.3, z2, 2.0 * k, 0.8 * k); }
};
// 7: up the ladder, the brush, painting the plates brown ("His solution?" -> "!")
const paint = (cam: CamInfo, t: number, f: number, out: Stage) => {
  leaks(out, f, [1.4, 2.8]);
  const x = LADDER[0] - LDIR[0] * 0.35, z = LADDER[2] - LDIR[1] * 0.35, sw = Math.round(Math.sin(t * 9) * 4) / 4;
  stand(cam, out, 203, JELL, "jell", x, 2.25, z, { mode: "stand", expr: S(f, 549) ? "grin" : "neutral", blink: lidAt(t, 203, [530 / FPS]), prop: "brush", look: -1, tilt: S(f, 549) ? 5 * sw : 0 }, 1, false);
  if (S(f, 530) && f < 556) { const k = pop(f, 530); fx1(out, "exclaim", 200, 360, (p) => fxExclaim(p), x + 0.2, 4.7, z + 0.2, 0.22 * k, 0.4 * k); }
  fx1(out, "paintcan", 240, 240, (p) => fxPaintCan(p), LADDER[0] + 0.9, 0.4, LADDER[2] + 0.4, 0.75, 0.75);
};
// 8: the brown tank, the leaks gone invisible; ta-da
const match = (cam: CamInfo, t: number, f: number, out: Stage) => {
  const [x, z] = onWall(-1.3, 1.4);
  stand(cam, out, 204, JELL, "jell", x, 0, z, { mode: "stand", expr: S(f, 620) ? "smile_closed" : "grin", blink: lidAt(t, 204), prop: "brush", look: 0 });
  if (S(f, 618)) { const u = Math.round((((f - 618) / 20) % 1) * 10) / 10; fx1(out, `sparkle|${u}`, 300, 300, (p) => fxSparkle(p, u), x + 0.9, 3.0, z, 1.4, 1.4); }
  fx1(out, "paintcan", 240, 240, (p) => fxPaintCan(p), x - 0.55, 0.62, z + 0.35, 0.6, 0.6);
};
// 9: the neighbours with buckets under the leaks, a kid licking his finger
const buckets = (cam: CamInfo, t: number, f: number, out: Stage) => {
  const spots = [-1.6, 0.2, 2.0];
  leaks(out, f, spots, 4.2, 0.42);
  spots.forEach((k, i) => {
    const [x, z] = onWall(k, 0.9 + (i % 2) * 0.2), lvl = clamp01((f - 650 - i * 12) / 70);
    stand(cam, out, 210 + i, folk(i + 1), `folk${i + 1}`, x + LDIR[0] * 0.5, 0, z + LDIR[1] * 0.5, { mode: "stand", expr: S(f, 701) ? "grin" : "smile", blink: lidAt(t, 210 + i), prop: "palm", look: 0 });
    fx1(out, `bucket|${Math.round(lvl * 10) / 10}`, 200, 220, (p) => fxBucket(p, lvl), x + LDIR[0] * 0.9, 0.55, z + LDIR[1] * 0.9, 0.5, 0.55);
  });
  const [kx, kz] = onWall(-3.3, 2.0);
  stand(cam, out, 215, BOY, "boy", kx, 0, kz, { mode: "stand", expr: "lick", blink: lidAt(t, 215), prop: "point", look: 1 });
};
// 10: the warm January day: walkers, the thermometer climbing from 2 F to 41 F
const warm = (cam: CamInfo, t: number, f: number, out: Stage) => {
  for (let i = 0; i < 6; i++) walker(cam, out, 220 + i, folk(i + 4), `folk${i + 4}`, -1.8 + (i % 3) * 2.4, 0, 6 + i * 3.1 + (i % 2 ? -1 : 1) * 1.0 * ((f - 731) / FPS), t, 0, i % 2 ? -1 : 1, i % 2 ? "smile" : "grin");
  const v = 2 + 39 * smooth((f - 748) / 42);
  fx1(out, `thermo|${Math.round(v)}`, 160, 520, (p) => fxThermo(p, v), -3.4, 3.2, 21.0, 1.0, 3.2);
};
// 11: the groan: two workers look up at the wall; strain ticks
const groan = (cam: CamInfo, t: number, f: number, out: Stage) => {
  for (let i = 0; i < 2; i++) { const [x, z] = onWall(-1.6 + i * 1.8, 2.2 + i * 0.5); stand(cam, out, 230 + i, WORKER(i), `worker${i}`, x, 0, z, { mode: "stand", expr: S(f, 823) ? "shock" : "neutral", blink: S(f, 823) ? 0 : lidAt(t, 230 + i), look: i ? -1 : 1, headTilt: -8 }); }
  if (S(f, 812)) for (let k = 0; k < 3; k++) { const [x, z] = onWall(-2 + k * 2.4, 0.4), u = Math.round(((t * 6 + k * 0.3) % 1) * 6) / 6; fx1(out, `creak|${u}`, 300, 300, (p) => fxCreak(p, u), x, 5.5 + k * 1.8, z, 1.2, 1.2); }
};
// 12: rivets popping out like machine-gun fire, the workers ducking
const rivets = (cam: CamInfo, t: number, f: number, out: Stage) => {
  for (let i = 0; i < 2; i++) { const [x, z] = onWall(-1.6 + i * 2.6, 2.6); stand(cam, out, 232 + i, WORKER(i), `worker${i}`, x, 0, z, { mode: S(f, 870) ? "fall" : "stand", expr: "shock", blink: 0, look: i ? -1 : 1 }); }
  RIVETS.forEach((r, i) => {
    if (f < r || f > r + 7) return;
    const u = (f - r) / 7, k0 = -1.6 + (i % 4) * 1.1, y = 2.6 + (i % 3) * 1.1;
    const [x, z] = onWall(k0 + (i % 2 ? 1 : -1) * 1.5 * u, 0.3 + 3.5 * u), [x0, z0] = onWall(k0, 0.2);
    fx1(out, "rivet", 240, 120, (p) => fxRivet(p), x, y + 0.2 * u, z, 0.9, 0.45, false, i % 2 ? Math.PI : 0);
    flash(out, f, r, x0, y, z0 + 0.1, 1.2);
  });
};
// 13: the burst: workers running from the yard; the 2,000,000 GALLONS tag
const burst = (cam: CamInfo, t: number, f: number, out: Stage) => {
  for (let i = 0; i < 4; i++) runner(cam, out, 240 + i, WORKER(i), `worker${i}`, 1 + i * 2.2, -6 + i * 1.5 + 3 * ((f - 900) / FPS), t, -0.3, 1, "shock");
  label(out, "2,000,000 GALLONS", TANK.x - 3, 19.5, TANK.z + 10, f, 914, 9.0, 2.0, "#ffffff");
  if (f >= 905 && f < 950) for (let i = 0; i < 6; i++) { const u = Math.round(clamp01((f - 905 - i * 3) / 30) * 10) / 10, a = (i / 6) * Math.PI * 2;
    fx1(out, `goo|${u}`, 400, 300, (p) => fxGoo(p, u), TANK.x + Math.cos(a) * 5, 9 + 6 * u + i * 0.8, TANK.z + Math.sin(a) * 5 + 4, 12, 9); }
};
// 14: the street: people fleeing; the truck's splash in the harbor
const smash = (cam: CamInfo, t: number, f: number, out: Stage) => {
  const z = waveZ(14, f);
  [-6.4, -4.8, 0.6, 3.2].forEach((x, i) => { const zz = z + 4 + i * 2.2 + 0.7 * ((f - 960) / FPS); if (zz < 46) runner(cam, out, 250 + i, folk(i + 5), `folk${i + 5}`, x, zz, t, 0, 1, "shock"); });
  spray(out, f, z);
  if (f >= 1040 && f < 1066) { const u = Math.round(((f - 1040) / 26) * 13) / 13; fx1(out, `splash|${u}`, 800, 800, (p) => fxSplash(p, u), 30, 1.2, 27, 9, 9); }
};
// 15: the boy riding the crest like a surfer
const surf = (cam: CamInfo, t: number, f: number, out: Stage) => {
  const z = waveZ(15, f);
  stand(cam, out, 260, BOY, "boy", XC - 1, 7.42 + 0.18 * Math.sin(t * 4), z + 1.5, { mode: "stand", expr: "relief_open", blink: 0, prop: "present", look: 1, tilt: 9 * Math.sin(t * 3) }, 1, false);
  stand(cam, out, 261, folk(8), "folk8", XC + 4.2, 6.2, z - 1.0, { mode: "fall", expr: "shock", blink: 0, tilt: -12 }, 1, false);
  spray(out, f, z, XC + 6, 8, 2);
  for (let k = 0; k < 2; k++) { const u = Math.round(((((f / 10) + k * 0.5)) % 1) * 8) / 8; fx1(out, `goo|${u}`, 400, 300, (p) => fxGoo(p, u), XC - 1.95 - k * 0.3, 7.55 + k * 0.2, z + 1.3, 1.6, 1.2); }
};
// 16: quiet: the flooded street, then sailors wading in; one stuck
const rescue = (cam: CamInfo, t: number, f: number, out: Stage) => {
  if (f < 1124) return;
  for (let i = 0; i < 5; i++) {
    const stuck = i === 2 && f >= 1203, s = ((stuck ? 1203 : f) - 1150) / FPS, x = -2.6 + i * 1.25, zz = 29.5 - 0.55 * s - (i % 3) * 0.9;
    stand(cam, out, 270 + i, SAILOR, `sailor${i % 2}`, x, stuck ? 0.12 * (0.5 + 0.5 * Math.sin(t * 6)) : 0, zz, { mode: stuck ? "stand" : "stroll", phase: ph(t, i, 0.8, 12), expr: stuck ? "pained" : "stern", blink: lidAt(t, 270 + i), tilt: stuck ? 8 * Math.sin(t * 6) : 0, prop: stuck ? ["scratch", 0.5 + 0.5 * Math.sin(t * 6)] : null }, 1, false);
    if (stuck) { const pull = Math.round((0.5 + 0.5 * Math.sin(t * 6)) * 6) / 6; fx1(out, `strands|${pull}`, 300, 300, (p) => fxStrands(p, 0.3 + 0.6 * pull), x, 0.78, zz + 0.2, 0.6, 0.4); }
  }
};
// 17-20: everything sticky
const sticky = (cam: CamInfo, t: number, f: number, out: Stage) => {
  const pull = Math.round((0.5 + 0.5 * Math.sin(t * 5)) * 6) / 6, lift = 0.16 * pull;
  stand(cam, out, 280, folk(10), "folk10", STUCK[0], 0.06 * pull, STUCK[2], { mode: "stand", expr: "pained", blink: lidAt(t, 280), tilt: 6 * pull, prop: ["scratch", pull] }, 1, false);
  fx1(out, `goofeet|${pull}`, 360, 160, (p) => fxGooFeet(p, pull), STUCK[0], 0.14, STUCK[2] + 0.12, 0.85, 0.38);
};
const seat = (cam: CamInfo, t: number, f: number, out: Stage) => {
  const pull = Math.round((0.5 + 0.5 * Math.sin(t * 7)) * 4) / 4;
  sit(cam, out, 281, folk(11), "folk11", BENCH[0], 0.18 + 0.12 * pull, BENCH[2], { expr: "pained", blink: lidAt(t, 281), tilt: 4 * pull, look: 0 });
  fx1(out, `goofeet|${pull}`, 360, 160, (p) => fxGooFeet(p, pull), BENCH[0], 0.6, BENCH[2] + 0.12, 0.75, 0.3);
};
const phone = (cam: CamInfo, t: number, f: number, out: Stage) => {
  const pull = Math.round((0.5 + 0.5 * Math.sin(t * 7)) * 4) / 4;
  stand(cam, out, 282, folk(12), "folk12", BOOTH[0], 0, BOOTH[2] + 0.35, { mode: "stand", expr: "pained", blink: lidAt(t, 282), headTilt: 10 + 4 * pull, look: 0 });
  fx1(out, "receiver", 160, 260, (p) => fxReceiver(p), BOOTH[0] + 0.3 + 0.05 * pull, 1.48, BOOTH[2] + 0.5, 0.2, 0.32, false, -0.6);
  fx1(out, `strands|${pull}`, 300, 300, (p) => fxStrands(p, 0.3 + 0.6 * pull), BOOTH[0] + 0.21, 1.5, BOOTH[2] + 0.52, 0.2, 0.2, false, 1.5);
};
const everything = (cam: CamInfo, t: number, f: number, out: Stage) => {
  for (let i = 0; i < 6; i++) {
    const x = XC - 4.2 + (i % 3) * 2.6, z = 13 + Math.floor(i / 3) * 4 + hh(i, 2) * 1.5, pull = Math.round((0.5 + 0.5 * Math.sin(t * 5 + i)) * 6) / 6;
    stand(cam, out, 290 + i, folk(i + 13), `folk${(i + 13) % 20}`, x, 0.05 * pull, z, { mode: "stand", expr: (["pained", "nervous", "shock"] as Expr[])[i % 3], blink: lidAt(t, 290 + i), tilt: 6 * (pull - 0.5) }, 1, false);
    fx1(out, `goofeet|${pull}`, 360, 160, (p) => fxGooFeet(p, pull), x, 0.14, z + 0.12, 0.85, 0.38);
  }
};
// 21: the company boss blames anarchists for the press; the bomb thought bubble
const excuse = (cam: CamInfo, t: number, f: number, out: Stage) => {
  stand(cam, out, 300, BOSS, "boss", PRESS[0], 0, PRESS[2], { mode: "stand", expr: S(f, 1430) ? "stern" : "neutral", blink: lidAt(t, 300, [1430 / FPS]), prop: S(f, 1430) ? "point" : "crossed", look: 1 });
  for (let i = 0; i < 3; i++) stand(cam, out, 301 + i, REPORTER(i), `rep${i}`, PRESS[0] + 1.3 + i * 0.85, 0, PRESS[2] + 0.9 + (i % 2) * 0.4,
    { mode: "stand", expr: i === 1 ? "shock" : "neutral", blink: lidAt(t, 301 + i), prop: i === 0 ? "camera" : "pen", look: -1, facing: -1 });
  flash(out, f, 1392, PRESS[0] + 1.3, 1.6, PRESS[2] + 1.2, 0.8); flash(out, f, 1470, PRESS[0] + 1.3, 1.6, PRESS[2] + 1.2, 0.8);
  if (S(f, 1432)) { const k = pop(f, 1432), u = Math.round(((t * 3) % 1) * 6) / 6; fx1(out, `bomb|${u}`, 520, 420, (p) => fxBomb(p, u), PRESS[0] + 1.0, 2.55, PRESS[2] + 0.5, 1.2 * k, 0.97 * k); }
};
// 22: the court: 3 YEARS, the gavel on "no", the boss sweating at "a bad tank"
const court = (cam: CamInfo, t: number, f: number, out: Stage) => {
  const g = f < 1532 ? 0 : f < 1538 ? smooth((f - 1532) / 6) : f < 1546 ? 1 - smooth((f - 1538) / 3) : 0;
  stand(cam, out, 310, JUDGE_O, "judge", JUDGE[0], JUDGE[1], JUDGE[2], { mode: "stand", expr: S(f, 1538) ? "stern" : "neutral", blink: lidAt(t, 310, [1538 / FPS]), prop: S(f, 1576) ? "point" : ["hammer", Math.round(g * 4) / 4], look: 1 }, 1, false);
  stand(cam, out, 311, BOSS, "boss", COURT.x + 1.0, 0, COURT.z + 1.9, { mode: "stand", expr: S(f, 1576) ? "pained" : S(f, 1538) ? "nervous" : "smile", blink: lidAt(t, 311, [1538 / FPS]), look: -1, facing: -1 });
  if (f < 1532) { const k = pop(f, 1491); if (k > 0) fx1(out, "calendar|3", 260, 300, (p) => fxCalendar(p, "3", "YEARS"), COURT.x - 1.6, 2.6, COURT.z - 1.0, 0.95 * k, 1.1 * k); }
  if (S(f, 1576)) { const u = Math.round((((f - 1576) / 18) % 1) * 6) / 6; fx1(out, `sweat|${u}`, 200, 200, (p) => fxSweat(p, u), COURT.x + 1.35, 2.0, COURT.z + 2.05, 0.35, 0.35); }
  if (S(f, 1538) && f < 1548) { const u = Math.round(((f - 1538) / 10) * 5) / 5; fx1(out, `flash|${u}`, 500, 500, (p) => fxFlashStar(p, u), JUDGE[0] + 0.45, 1.75, JUDGE[2] + 0.7, 0.8, 0.8); }
};
// 23: summer on the wharf: the harbor still brown, puzzled tourists; 24: a man smelling the sweet street
const harbor = (cam: CamInfo, t: number, f: number, out: Stage) => {
  for (let i = 0; i < 3; i++) stand(cam, out, 320 + i, tourist(i), `tour${i}`, WHARF_X - 1.6 - (i % 2) * 0.8, 0, 33 - i * 1.6,
    { mode: "stand", expr: (["dazed", "nervous", "shock"] as Expr[])[i], blink: lidAt(t, 320 + i), prop: i === 1 ? "point" : null, look: 1, facing: 1 });
  if (f >= 1615) { const k = smooth((f - 1615) / 8), wob = 0.08 * Math.sin(t * 8); out.fx.push({ key: "question", cw: 240, ch: 360, draw: (p) => fxQuestion(p), x: WHARF_X - 1.6, y: 2.4, z: 33, w: 0.26 * k, h: 0.39 * k, rot: wob }); }
  fx1(out, "gull", 240, 200, (p) => fxGull(p), WHARF_X + 4.5, -0.85, 30, 0.75, 0.62);
};
const sniff = (cam: CamInfo, t: number, f: number, out: Stage) => {
  stand(cam, out, 330, folk(14), "folk14", SNIFF[0], 0, SNIFF[2], { mode: "stand", expr: "smile_closed", blink: 1, look: 0, headTilt: -8 });
  const u = Math.round((((f - 1650) / 40) % 1) * 10) / 10; fx1(out, `scent|${u}`, 300, 360, (p) => fxScent(p, u), SNIFF[0] + 0.55, 1.15, SNIFF[2] + 0.2, 0.8, 0.96);
};
// 25: the boss with a glass: what was it all for? Alcohol. 26: next day's paper: AMERICA BANS ALCOHOL
const alcohol = (cam: CamInfo, t: number, f: number, out: Stage) => {
  stand(cam, out, 340, BOSS, "boss", BOSS_DESK[0], 0, BOSS_DESK[2], { mode: "stand", expr: S(f, 1764) ? "grin" : "neutral", blink: lidAt(t, 340, [1764 / FPS]), prop: S(f, 1764) ? "glass" : "crossed", look: 0 });
  if (S(f, 1736)) { const k = Math.round(clamp01((f - 1736) / 40) * 10) / 10; fx1(out, `still|${k}`, 720, 360, (p) => fxStill(p, k), BOSS_DESK[0] + 0.08, 2.1, BOSS_DESK[2] + 0.9, 0.95, 0.475); }
};
const ban = (cam: CamInfo, t: number, f: number, out: Stage) => {
  const shock = S(f, 1861);
  stand(cam, out, 341, BOSS, "boss", BOSS_DESK[0], 0, BOSS_DESK[2], { mode: "stand", expr: shock ? "shock" : "neutral", blink: shock ? 0 : lidAt(t, 341), prop: shock ? null : "glass", look: 0, headTilt: shock ? 0 : -4 });
  const k = smooth((f - 1800) / 10);
  fx1(out, "headline", 600, 760, (p) => fxHeadline(p, ["AMERICA", "BANS", "ALCOHOL"]), BOSS_DESK[0] - 0.05, 1.1 + (shock ? -0.06 : 0), BOSS_DESK[2] + 1.32, 0.54 * k, 0.68 * k, false, shock ? 0.08 : 0);
  if (f >= 1866 && f < 1890) { const u = Math.round(((f - 1866) / 24) * 8) / 8; fx1(out, `shatter|${u}`, 300, 300, (p) => fxShatter(p, u), BOSS_DESK[0] + 0.5, 0.2, BOSS_DESK[2] + 0.7, 0.8, 0.8); }
  if (f >= 1862 && f < 1868) { const y = 1.1 - 0.9 * ((f - 1862) / 6); fx1(out, "dropglass", 60, 90, (p) => fxSyrupDrop(p), BOSS_DESK[0] + 0.5, y, BOSS_DESK[2] + 0.7, 0.1, 0.15); }
};

/** everything with a face (and every 2D effect) in shot `id` at time t */
export const stage = (id: number, t: number, f: number, cam: CamInfo): Stage => {
  const out: Stage = { places: [], fx: [] };
  const s = SHOTS[id - 1];
  LNAME = s.light;
  findSun(cam, SUN);
  const fn: Record<string, (c: CamInfo, t: number, f: number, o: Stage) => void> = {
    hook, speed, tank: tankShot, office, blueprint, leak, paint, match, buckets, warm, groan, rivets, burst, smash, surf, rescue, sticky, seat, phone,
    everything, excuse, court, harbor, sniff, alcohol, ban,
  };
  fn[s.crowd]?.(cam, t, f, out);
  return out;
};
export { FPS, clamp01, NOINK };
