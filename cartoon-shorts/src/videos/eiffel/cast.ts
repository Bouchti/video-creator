import type { LightName } from "./lights";
// The escalator cast as lit flat sprites in the 3D world. Each frame every character asks for a drawing (a key + a draw call);
// the pool keeps one canvas per distinct drawing, so soldiers marching in step share canvases (7 head shapes x 4
// outfits). Characters are yaw-only billboards shaded by cardShade() (scene tint, bright floor, side gradient toward
// the sun, painted crescent in the drawing); standing ones get a soft multiply contact blob. Effects are unlit cards.
// Cards, effects and blobs live on the NOINK layer so the world ink pass never outlines their quads.
import * as THREE from "three";
import {
  Pen, bodyFront, bodySide, fxShadow, fxContact, fxBurst, fxStars, fxPuff, fxLetter, fxStamp, fxRiot, fxQuestion,
  CON, POISSON, WIFE, PAINTER, GENDARME, dealer, clerk, parisian, Outfit, Expr, FrontOpts, SideOpts, Prop,
} from "./toon";
import {
  FPS, SHOTS, clamp01, smooth, HOOK_CON, HOOK_BUY, CAFE_SEAT, VIENNA_SEAT, PAINTER_AT, KNOCK_CON, KNOCK_BEAM, DEALERS_TOUR, DREAM_POI,
  TABLE_Z, SEATS, POI_SEAT, CON_HEAD, CON_FRONT, poiLeave, POI_DEAL, WIFE_AT, POI_HOME, CLERK, CITIZEN, returnAt, stampAt, knockAt, KNOCKS, rearAt, trainAt, limoSeats, COP_AT, poiHurry,
} from "./story";
import { HOTEL } from "./places";
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

// ---------------- the Eiffel crowd by shot ----------------
const S = (f: number, a: number) => f >= a - 2; // a reaction lands 0-3 f before its word
const sit = (cam: CamInfo, out: Stage, i: number, o: Outfit, okey: string, x: number, y: number, z: number, fo: FrontOpts, scale = 1) =>
  stand(cam, out, i, o, okey, x, y, z, { ...fo, mode: "sit" }, scale, false);
const DEAL = [0, 1, 2, 3, 4].map((v) => (v === POI_SEAT ? POISSON : dealer(v)));
const dk = (v: number) => (v === POI_SEAT ? "poi" : `dl${v}`);

// 1: the hook: the con man presents the tower, the buyer hands over the money, then a second envelope on "bribe"
const hook = (cam: CamInfo, t: number, f: number, out: Stage) => {
  stand(cam, out, 700, CON, "con", HOOK_CON[0], 0, HOOK_CON[2], { mode: "stand", expr: S(f, 76) ? "grin" : "smile", blink: lidAt(t, 700), prop: "present", look: 1, headTilt: -4 });
  stand(cam, out, 701, POISSON, "poi", HOOK_BUY[0], 0, HOOK_BUY[2], { mode: "stand", expr: S(f, 76) ? "nervous" : "smile_closed", blink: lidAt(t, 701), prop: S(f, 62) ? "envelope" : "cash", look: -1 });
  if (f >= 78 && f < 100) { const k = (f - 78) / 22; out.fx.push({ key: `burst|${Math.round(k * 12)}`, cw: 500, ch: 500, draw: (p) => fxBurst(p, Math.round(k * 12) / 12, "#fff3b0", 10), x: HOOK_BUY[0] + 0.25, y: 1.25, z: HOOK_BUY[2] + 0.2, w: 0.7, h: 0.7 }); }
  for (let i = 0; i < 4; i++) walker(cam, out, 702 + i, parisian(i), `pa${i}`, -6 + i * 3.6 + ((t * 0.9 + i) % 6) * (i % 2 ? 1 : -1), 0, 96 - i * 5, t, i % 2 ? 1 : -1, 0, "smile");
};
// 2: the con man at the café with the morning paper
const cafe = (cam: CamInfo, t: number, f: number, out: Stage) => {
  sit(cam, out, 710, CON, "con", CAFE_SEAT[0], 0.3, CAFE_SEAT[2], { expr: f < 175 ? "smile" : "grin", blink: lidAt(t, 710), prop: "newspaper", look: 1 });
  sit(cam, out, 711, parisian(1), "pa1", CAFE_SEAT[0] + 0.2, 0.3, CAFE_SEAT[2] - 5.5, { expr: "smile_closed", blink: lidAt(t, 711) });
  for (let i = 0; i < 3; i++) walker(cam, out, 712 + i, parisian(i + 2), `pa${i + 2}`, 2.5 - i * 3, 0, CAFE_SEAT[2] - 8 - i * 7 + ((t * 1.1) % 9) * (i % 2 ? 1 : -1), t, 0, i % 2 ? 1 : -1, "neutral");
};
// 3: the painter on his plank, brush going
const painter = (cam: CamInfo, t: number, f: number, out: Stage) => {
  stand(cam, out, 720, PAINTER, "painter", PAINTER_AT[0], PAINTER_AT[1], PAINTER_AT[2], { mode: "stand", expr: f > 280 ? "dazed" : "nervous", blink: lidAt(t, 720), prop: "brush", look: -1, headTilt: 6 * Math.sin(t * 3) }, 1, false);
};
// 4: the forged letter on the table; the stamp comes down on "fake"
const letter = (cam: CamInfo, t: number, f: number, out: Stage) => {
  const st = stampAt(f);
  out.fx.push({ key: `letter|${st.seal ? 1 : 0}`, cw: 600, ch: 760, draw: (p) => fxLetter(p, st.seal), x: HOTEL.x + 0.3, y: 0.812, z: TABLE_Z + 0.18, w: 0.42, h: 0.53, flat: true, rot: 0.12 });
  out.fx.push({ key: "stamp", cw: 300, ch: 360, draw: (p) => fxStamp(p), x: HOTEL.x + 0.42, y: 0.93 + 0.42 * st.y, z: TABLE_Z + 0.1, w: 0.2, h: 0.24 });
  if (f >= 343 && f < 356) { const k = (f - 343) / 13; out.fx.push({ key: `burst|${Math.round(k * 12)}`, cw: 500, ch: 500, draw: (p) => fxBurst(p, Math.round(k * 12) / 12, "#fff3b0", 8), x: HOTEL.x + 0.42, y: 0.86, z: TABLE_Z + 0.12, w: 0.36, h: 0.36 }); }
};
// 5-8: the salon
const salon = (cam: CamInfo, t: number, f: number, out: Stage, mood: "arrive" | "listen" | "shock" | "shh") => {
  SEATS.forEach(([x, , z], v) => {
    const shocked = mood === "shock" || (mood === "shh" && v !== POI_SEAT && f < 640);
    const expr: Expr = shocked ? (v === 1 ? "shock" : v % 2 ? "nervous" : "shock") : mood === "arrive" ? (["smile", "neutral", "smile_closed", "whistle", "smile"] as Expr[])[v] : v === POI_SEAT ? "grin" : (["neutral", "smile", "grin", "smile_closed", "neutral"] as Expr[])[v];
    sit(cam, out, 730 + v, DEAL[v], dk(v), x, 0.3, z, { expr, blink: lidAt(t, 730 + v, mood === "shock" ? [557 / FPS] : []), look: x < CON_HEAD[0] ? 1 : -1, headTilt: shocked ? -5 : 0 });
  });
  const cexpr: Expr = mood === "shh" ? (f < 700 ? "stern" : "smile") : mood === "listen" ? "grin" : "smile";
  const cprop = mood === "shh" ? (f < 704 ? "shh" : null) : mood === "listen" ? "paper" : null;
  stand(cam, out, 740, CON, "con", CON_HEAD[0], 0, CON_HEAD[2], { mode: "stand", expr: cexpr, blink: lidAt(t, 740), prop: cprop, look: -1, tilt: mood === "shh" ? -6 : 0, headTilt: mood === "listen" ? -6 : 0 });
  if (mood === "shh" && f >= 684 && f < 728) {
    const k = smooth((f - 684) / 8);
    out.fx.push({ key: "riot", cw: 520, ch: 420, draw: (p) => fxRiot(p), x: CON_HEAD[0] - 0.48, y: 2.15, z: CON_HEAD[2] + 0.3, w: 0.74 * k, h: 0.6 * k });
  }
};
// 9: the limousine (world.ts drives it)
// 10: the knock on the leg; the dealers lean in
const knock = (cam: CamInfo, t: number, f: number, out: Stage) => {
  const k = knockAt(f);
  stand(cam, out, 750, CON, "con", KNOCK_CON[0], KNOCK_CON[1], KNOCK_CON[2], { mode: "stand", expr: "stern", blink: lidAt(t, 750), prop: ["knock", Math.round(k * 4) / 4], look: -1, headTilt: 8 });
  DEALERS_TOUR.forEach(([x, y, z], i) => stand(cam, out, 751 + i, DEAL[i === 3 ? POI_SEAT : i], dk(i === 3 ? POI_SEAT : i), x, y, z, { mode: "stand", expr: (["neutral", "whistle", "smile", "grin"] as Expr[])[i], blink: lidAt(t, 751 + i), look: -1, headTilt: -6 }));
  for (const kf of KNOCKS) if (f >= kf && f < kf + 8) { const u = (f - kf) / 8; out.fx.push({ key: `burst|${Math.round(u * 8)}`, cw: 500, ch: 500, draw: (p) => fxBurst(p, Math.round(u * 8) / 8, "#ffd84a", 8, 40, 230), x: KNOCK_BEAM[0], y: KNOCK_BEAM[1], z: KNOCK_BEAM[2] + 0.3, w: 0.6, h: 0.6 }); }
};
// 11: the dealer's dream at the tower's foot; the outsider apart from the others
const dream = (cam: CamInfo, t: number, f: number, out: Stage) => {
  const expr: Expr = f < 934 ? "smile_closed" : f < 963 ? "nervous" : "grin";
  stand(cam, out, 760, POISSON, "poi", DREAM_POI[0], 0, DREAM_POI[2], { mode: "stand", expr, blink: lidAt(t, 760), look: f < 934 ? 1 : f < 963 ? 1 : 0, headTilt: f < 934 ? -10 : 0, wave: f >= 975 ? 0.6 + 0.4 * Math.sin(t * 6) : undefined });
  if (f >= 934) [[37.9, -28.6], [39.0, -29.4], [39.6, -28.2], [38.6, -27.6]].forEach(([x, z], i) =>
    stand(cam, out, 761 + i, DEAL[[0, 1, 3, 4][i]], dk([0, 1, 3, 4][i]), x, 0, z, { mode: "stand", expr: (["laugh", "grin", "smile", "laugh"] as Expr[])[i], blink: lidAt(t, 761 + i), look: i < 2 ? 1 : -1 }));
  if (f >= 975) { const ph = Math.round(((t * 0.8) % 1) * 60) / 60; out.fx.push({ key: `stars|${ph}`, cw: 420, ch: 210, draw: (p) => fxStars(p, ph), x: DREAM_POI[0], y: 1.9, z: DREAM_POI[2], w: 0.9, h: 0.45 }); }
};
// 12 + 19: the parlour
const wife = (cam: CamInfo, t: number, f: number, out: Stage, ashamed = false) => {
  const wexpr: Expr = "stern";
  stand(cam, out, 770, WIFE, "wife", WIFE_AT[0], 0, WIFE_AT[2], { mode: "stand", expr: wexpr, blink: lidAt(t, 770), prop: "crossed", look: 1, headTilt: ashamed ? 0 : 8 * smooth((f - 1168) / 12) });
  const pexpr: Expr = ashamed ? "pained" : f < 1097 ? "grin" : "nervous";
  stand(cam, out, 771, POISSON, "poi", POI_HOME[0], 0, POI_HOME[2], { mode: "stand", expr: pexpr, blink: lidAt(t, 771), prop: ashamed ? "facepalm" : "paper", look: -1, headTilt: ashamed ? 10 : 0, blush: ashamed });
};
// 13: the dealer walks off; the con man holds out his hand on "asks"
const leave = (cam: CamInfo, t: number, f: number, out: Stage) => {
  const p = poiLeave(f), walking = f >= 1210 && f < 1258;
  if (walking) walker(cam, out, 780, POISSON, "poi", p[0], 0, p[2], t, 1, 0.24, "neutral");
  else stand(cam, out, 780, POISSON, "poi", p[0], 0, p[2], { mode: "stand", expr: f < 1210 ? "neutral" : f < 1290 ? "neutral" : "shock", blink: lidAt(t, 780, [1290 / FPS]), look: -1 });
  stand(cam, out, 781, CON, "con", CON_FRONT[0], 0, CON_FRONT[2], { mode: "stand", expr: f < 1283 ? "nervous" : "smile", blink: lidAt(t, 781), prop: S(f, 1283) ? "palm" : null, look: 1 });
  SEATS.forEach(([x, , z], v) => { if (v !== POI_SEAT && z < TABLE_Z) sit(cam, out, 782 + v, DEAL[v], dk(v), x, 0.3, z, { expr: "neutral", blink: lidAt(t, 782 + v), look: 1 }); });
};
// 14: the palm, close; a question mark over the dealer's side of the frame
const palm = (cam: CamInfo, t: number, f: number, out: Stage) => {
  const pp = poiLeave(1300);
  stand(cam, out, 780, POISSON, "poi", pp[0], 0, pp[2], { mode: "stand", expr: f < 1356 ? "stern" : "nervous", blink: lidAt(t, 780, [1356 / FPS]), look: -1, headTilt: 8 });
  stand(cam, out, 781, CON, "con", CON_FRONT[0], 0, CON_FRONT[2], { mode: "stand", expr: "smile", blink: lidAt(t, 781), prop: "palm", look: 1 });
  if (f >= 1330) { const k = smooth((f - 1330) / 8), wob = 0.08 * Math.sin(t * 8); out.fx.push({ key: "question", cw: 240, ch: 360, draw: (p) => fxQuestion(p), x: pp[0] + 0.3, y: 1.5, z: pp[2] + 0.2, w: 0.2 * k, h: 0.3 * k, rot: wob }); }
};
// 15: the ministry hall: every clerk's hand out, every citizen with an envelope
const clerks = (cam: CamInfo, t: number, f: number, out: Stage) => {
  for (let i = 0; i < 3; i++) {
    const c = CLERK(i), z = CITIZEN(i);
    const taken = i === 0 && f >= 1440;
    sit(cam, out, 790 + i, clerk(i), `cl${i}`, c[0], 0.3, c[2], { expr: i === 0 ? (taken ? "grin" : "smile") : (["smile", "grin", "smile_closed"] as Expr[])[i], blink: lidAt(t, 790 + i), prop: taken ? "envelope" : "palm", look: 1 });
    stand(cam, out, 795 + i, dealer(i + 1), `dl${i + 1}`, z[0], 0, z[2], { mode: "stand", expr: "nervous", blink: lidAt(t, 795 + i), prop: taken ? null : "envelope", look: -1 });
  }
};
// 16: the deal: relief, the handshake, the envelope, then the price
const deal = (cam: CamInfo, t: number, f: number, out: Stage) => {
  const pprop: Prop = f < 1684 ? null : f < 1712 ? "envelope" : "cash";
  stand(cam, out, 800, POISSON, "poi", POI_DEAL[0], 0, POI_DEAL[2], { mode: "stand", expr: f < 1596 ? "nervous" : f < 1684 ? "relief" : "relief_open", blink: lidAt(t, 800, [1596 / FPS]), prop: pprop, look: -1 });
  stand(cam, out, 801, CON, "con", CON_FRONT[0], 0, CON_FRONT[2], { mode: "stand", expr: f < 1627 ? "smile" : "grin", blink: lidAt(t, 801), prop: f < 1690 ? "palm" : f < 1720 ? "envelope" : "cash", look: 1 });
  SEATS.forEach(([x, , z], v) => { if (v !== POI_SEAT && z < TABLE_Z) sit(cam, out, 802 + v, DEAL[v], dk(v), x, 0.3, z, { expr: "smile", blink: lidAt(t, 802 + v), look: 1 }); });
};
// 17: on the rear platform of the train with the suitcase; steam puffs from the chimney
const train = (cam: CamInfo, t: number, f: number, out: Stage) => {
  const r = rearAt(f);
  stand(cam, out, 810, CON, "con", r[0], r[1], r[2] + 0.3, { mode: "stand", expr: f < 1777 ? "smile" : "laugh", blink: lidAt(t, 810), prop: f < 1790 ? "suitcase" : "suitcaseOpen", look: 1 }, 1, false);
  const nose = trainAt(f);
  for (let k = 0; k < 7; k++) {
    const age = ((f / 6 + k) % 7) / 7, q2 = Math.round(age * 10) / 10;
    out.fx.push({ key: `puff|${q2}`, cw: 300, ch: 300, draw: (p) => fxPuff(p, q2 * 0.8), x: nose + 6.6 - age * 18, y: 0.2 + 4.6 + age * 3.5, z: r[2], w: 2.2 + age * 3, h: 2.2 + age * 3, soft: true });
  }
};
// 18: the Austrian morning: the paper up, then "Nothing." (paper down, grin)
const vienna = (cam: CamInfo, t: number, f: number, out: Stage) => {
  const done = S(f, 1912);
  sit(cam, out, 820, CON, "con", VIENNA_SEAT[0], 0.3, VIENNA_SEAT[2], { expr: done ? "grin" : "neutral", blink: lidAt(t, 820, [1912 / FPS]), prop: done ? null : "newspaper", look: done ? 0 : 1, headTilt: done ? -4 : 0 });
  walker(cam, out, 821, parisian(4), "pa4", 3 - ((t * 1.1) % 8), 0, VIENNA_SEAT[2] + 9, t, -1, 0, "smile");
};
// 9: the limousine passengers, seated inside (their legs hidden by the car body)
const limo = (cam: CamInfo, t: number, f: number, out: Stage) => {
  for (const [x, z, y, w] of limoSeats(f)) sit(cam, out, 840 + w, w === 0 ? CON : DEAL[w === 1 ? POI_SEAT : 0], w === 0 ? "con" : dk(w === 1 ? POI_SEAT : 0), x, y, z, { expr: w === 0 ? "grin" : "smile_closed", blink: lidAt(t, 840 + w), look: 1 });
};
// 20: the dealer hurries past a policeman, hiding his face behind his hand
const police = (cam: CamInfo, t: number, f: number, out: Stage) => {
  stand(cam, out, 850, GENDARME, "cop", COP_AT[0], 0, COP_AT[2], { mode: "stand", expr: f < 1985 ? "whistle" : "smile", blink: lidAt(t, 850), look: 1 });
  const p = poiHurry(f);
  stand(cam, out, 851, POISSON, "poi", p[0], 0, p[2], { mode: "stand", expr: "pained", blink: lidAt(t, 851), prop: "facepalm", look: -1, headTilt: 8, blush: true });
};
// 20: the return: walking up to the tower with the suitcase, then turning with a new letter and a grin
const ret = (cam: CamInfo, t: number, f: number, out: Stage) => {
  const p = returnAt(f);
  if (f < 2072) walker(cam, out, 830, CON, "con", p[0], 0, p[2], t, 0, -1, "smile");
  else stand(cam, out, 830, CON, "con", p[0], 0, p[2], { mode: "stand", expr: f < 2094 ? "smile" : "grin", blink: lidAt(t, 830, [2094 / FPS]), prop: "paper", look: 0, headTilt: -5 });
  for (let i = 0; i < 3; i++) walker(cam, out, 831 + i, parisian(i), `pa${i}`, -5 + i * 5, 0, 118 - i * 6 + ((t * 1.2) % 5) * (i % 2 ? 1 : -1), t, 0, i % 2 ? 1 : -1, "neutral");
};

/** everything with a face (and every 2D effect) in shot `id` at time t */
export const stage = (id: number, t: number, f: number, cam: CamInfo): Stage => {
  const out: Stage = { places: [], fx: [] };
  const s = SHOTS[id - 1];
  LNAME = s.light;
  findSun(cam, SUN);
  switch (s.crowd) {
    case "hook": hook(cam, t, f, out); break;
    case "cafe": cafe(cam, t, f, out); break;
    case "painter": painter(cam, t, f, out); break;
    case "letter": letter(cam, t, f, out); break;
    case "salon": salon(cam, t, f, out, "arrive"); break;
    case "minister": salon(cam, t, f, out, "listen"); break;
    case "shock": salon(cam, t, f, out, "shock"); break;
    case "shh": salon(cam, t, f, out, "shh"); break;
    case "knock": knock(cam, t, f, out); break;
    case "dream": dream(cam, t, f, out); break;
    case "wife": wife(cam, t, f, out); break;
    case "ashamed": wife(cam, t, f, out, true); break;
    case "leave": leave(cam, t, f, out); break;
    case "palm": palm(cam, t, f, out); break;
    case "clerks": clerks(cam, t, f, out); break;
    case "deal": deal(cam, t, f, out); break;
    case "train": train(cam, t, f, out); break;
    case "vienna": vienna(cam, t, f, out); break;
    case "limo": limo(cam, t, f, out); break;
    case "police": police(cam, t, f, out); break;
    case "return": ret(cam, t, f, out); break;
    default: break;
  }
  return out;
};
export { FPS };
