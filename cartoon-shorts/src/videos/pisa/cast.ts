// The Pisa cast as lit flat sprites in the 3D world. Each frame every character asks for a drawing (a key + a draw call);
// the pool keeps one canvas per distinct drawing, so soldiers marching in step share canvases (7 head shapes x 4
// outfits). Characters are yaw-only billboards shaded by cardShade() (scene tint, bright floor, side gradient toward
// the sun, painted crescent in the drawing); standing ones get a soft multiply contact blob. Effects are unlit cards.
// Cards, effects and blobs live on the NOINK layer so the world ink pass never outlines their quads.
import * as THREE from "three";
import {
  Pen, bodyFront, bodySide, KID, mason, pisan, engineer, tourist, fxStars, fxRing, fxShadow, fxContact, fxPuff, fxBanana, fxBead, fxDust, fxTool, fxSoil,
  Outfit, Expr, FrontOpts, SideOpts,
} from "./toon";
import {
  FPS, D0, SHOTS, V3, TOWER, TR, BEACH, CAMP, ROUTE_Z, BORE, FILES, ROW_GAP, COUNT, front, marchPhase, towerAt, TowerState, smooth, clamp01,
} from "./story";
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
let LNAME: "day" | "golden" = "day";
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
const CONTACT: Record<"day" | "golden", [number, number, number]> = { day: [0.2, 0.21, 0.33], golden: [0.24, 0.2, 0.33] };
const TAIL: [number, number, number] = [0.42, 0.44, 0.62];
const toSrgb = (v: number) => { const c = clamp01(v); return c <= 0.0031308 ? 12.92 * c : 1.055 * c ** (1 / 2.4) - 0.055; };
const hexOf = (c: [number, number, number], k: number) => "#" + c.map((v) => Math.round(255 * toSrgb(1 - (1 - v) * k)).toString(16).padStart(2, "0")).join("");
const blob = (out: Stage, x: number, y: number, z: number, sc = 1, k = 1) => {
  const hl = Math.hypot(SUN.x, SUN.z) || 1, ox = -SUN.x / hl, oz = -SUN.z / hl, rot = Math.atan2(-ox, -oz);
  if (LNAME === "day") {
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

const MASON = [0, 1, 2, 3, 4, 5, 6, 7].map((v) => mason(v));
const PISAN = [0, 1, 2, 3].map((v) => pisan(v));
const ENG = [0, 1, 2, 3].map((v) => engineer(v));
const TOUR = [0, 1, 2, 3, 4, 5].map((v) => tourist(v));
const DEG = Math.PI / 180;

/** a point riding on the tower (x, height above the base, z): turned with the lean about the high-side foot */
const onTower = (s: TowerState, x: number, h: number, z: number): V3 => {
  const px = TOWER[0] + TR, a = (s.lean + s.topple) * DEG, rx = x - px;
  return [px + rx * Math.cos(a) - h * Math.sin(a), D0 + rx * Math.sin(a) + h * Math.cos(a), z];
};
/** hammer strike 0 (raised) .. 1 (struck), a blow every `per` seconds (4 f wind-up, ~7 f hold, 1-frame strike) */
const hammer = (t: number, per: number, off: number) => {
  const n = (((t + off) % per) + per) % per * FPS, last = per * FPS;
  if (n < 4) return 1 - smooth(n / 4);
  if (n < 11) return 0;
  if (n < 12) return 1;
  return n > last - 1 ? 1 : 1;
};
const stand = (cam: CamInfo, out: Stage, i: number, o: Outfit, okey: string, x: number, y: number, z: number, fo: FrontOpts, scale = 1, shadow = true) => {
  out.places.push(person(cam, { i, o, okey }, x, y, z, { side: false, mirror: false }, fo, {}, scale));
  if (shadow) blob(out, x, y, z, scale);
};

/** today's visitors on the lawn: some "holding the tower up" for a photo (shots 1 and 16) */
const TOURIST_SPOTS: [number, number, boolean][] = [[-8.6, 55.2, true], [-6.1, 56.6, false], [-11.2, 57.4, false], [-4.2, 54.4, true], [-13.6, 54.6, true],
  [-2.2, 58.4, false], [-9.4, 60.2, true], [-15.4, 59.4, false], [-5.4, 61.6, false], [-0.6, 55.8, false]];
const tourists = (cam: CamInfo, t: number, out: Stage) => {
  TOURIST_SPOTS.forEach(([x, z, pose], i) => {
    const kid = i === 5, o = kid ? KID : TOUR[i % 6];
    const expr: Expr = (["grin", "smile", "laugh", "smile_closed", "grin"] as Expr[])[i % 5];
    const fo: FrontOpts = { mode: "stand", expr, blink: lidAt(t, i + 40), wave: pose ? 0.6 : undefined, prop: !pose && i % 4 === 1 ? "icecream" : null, facing: pose ? -1 : 0 };
    stand(cam, out, i + 400, o, kid ? "kid" : `tour${i % 6}`, x, D0, z, fo, kid ? 0.72 : 1);
  });
};

/** 1173: masons round the first storey's foot and on its rising top (shot 2) */
const masonsBase = (cam: CamInfo, t: number, f: number, out: Stage) => {
  const s = towerAt(2, f), top = s.storeys * 10.5;
  [200, 225, 250, 290, 315, 340].forEach((deg, i) => {
    const a = deg * DEG, r = TR + 1.6;
    stand(cam, out, i + 10, MASON[i], `m${i}`, TOWER[0] + Math.cos(a) * r, D0, TOWER[2] + Math.sin(a) * r,
      { mode: "stand", expr: i % 2 ? "smile" : "neutral", blink: lidAt(t, i + 10), prop: ["hammer", q(hammer(t, 0.9, i * 0.31), 30)] });
  });
  [255, 285].forEach((deg, i) => {
    const a = deg * DEG, r = TR - 0.9;
    stand(cam, out, i + 16, MASON[6 + i], `m${6 + i}`, TOWER[0] + Math.cos(a) * r, D0 + top, TOWER[2] + Math.sin(a) * r,
      { mode: "stand", expr: "grin", blink: lidAt(t, i + 16), prop: ["hammer", q(hammer(t, 1.1, i * 0.5), 30)] }, 1, false);
  });
};

/** the second floor: masons hammering on the working rim, then the sinking (shot 3) */
const SINK_T = 352 / FPS;
const masonsTop = (cam: CamInfo, t: number, f: number, out: Stage) => {
  const s = towerAt(3, f), n = Math.min(s.storeys, 2.45), top = n <= 1 ? n * 10.5 : 10.5 + (n - 1) * 6.2;
  const floor = Math.min(top, 16.7);
  [238, 256, 274, 292, 308].forEach((deg, i) => {
    const a = deg * DEG, r = TR - 0.95, [x, y, z] = onTower(s, TOWER[0] + Math.cos(a) * r, floor, TOWER[2] + Math.sin(a) * r);
    const shock = t >= SINK_T - LEAD;
    const fo: FrontOpts = { mode: "stand", expr: shock ? (i % 2 ? "shock" : "nervous") : i === 2 ? "whistle" : "grin", blink: lidAt(t, i + 20, [SINK_T]),
      prop: shock ? null : ["hammer", q(hammer(t, 0.8, i * 0.23), 30)], tilt: shock ? -(s.lean * 1.5) : 0, look: shock ? -1 : 0 };
    stand(cam, out, i + 20, MASON[i], `m${i}`, x, y, z, fo, 1, false);
  });
  // the slump: soil puffs at the low side's foot as it sinks
  if (t >= SINK_T && t < SINK_T + 0.9) {
    const u = (t - SINK_T) / 0.9;
    for (const [dz, s2] of [[-3, 1], [0, 1.3], [3.2, 1]] as const)
      out.fx.push({ key: `puff${q(u, 30)}`, cw: 300, ch: 300, draw: (p) => fxPuff(p, q(u, 30)), x: TOWER[0] - TR - 0.6, y: D0 + 0.9 * s2, z: TOWER[2] + dz, w: 3.4 * s2, h: 3.4 * s2 });
  }
};

/** the column of Pisan foot soldiers off to war along the piazza's south edge (shots 4, 5) */
const DROP_T = 452 / FPS, TOOLS_T = 455 / FPS, LEAVE_T = 466 / FPS;
const column = (id: number, t: number, cam: CamInfo, out: Stage) => {
  const F = front(t), ph = marchPhase(t);
  for (let i = 0; i < COUNT; i++) {
    const row = i >> 2, z = ROUTE_Z + FILES[i & 3] + (hh(i) - 0.5) * 0.12, x = F + row * ROW_GAP + (hh(i, 2) - 0.5) * 0.12;
    const v = (i * 7 + (i >> 2)) % 4, who: Who = { i, o: PISAN[v], okey: `p${v}` };
    const expr: Expr = id === 5 ? (i % 3 === 0 ? "laugh" : "grin") : i % 4 === 3 ? "grin" : i % 2 ? "neutral" : "stern";
    const view = viewOf(cam, x, z, -1, 0);
    const blink = lidAt(t, i);
    const fo: FrontOpts = { phase: ph, expr, mode: "march", look: 0, blink, lift: 70 };
    const so: SideOpts = { phase: ph, expr, mode: "march", blink, stomp: 1.2, stride: view.fs };
    out.places.push(person(cam, who, x, D0, z, view, fo, so));
    blob(out, x, D0, z);
  }
};
/** the masons at the foot drop their tools and go after the column (shot 4) */
const masonsDrop = (cam: CamInfo, t: number, out: Stage) => {
  const spots: [number, number][] = [[-5.0, 71.0], [-3.4, 70.6], [-1.8, 71.4]];
  spots.forEach(([x0, z], i) => {
    const leave = clamp01((t - LEAVE_T - i * 0.1) / 1.2), x = x0 - leave * leave * 3.0;
    const dropped = t >= DROP_T - LEAD;
    const expr: Expr = !dropped ? "neutral" : t < TOOLS_T + 0.3 ? "shock" : "grin";
    if (leave > 0) {
      const view = viewOf(cam, x, z, -1, 0), ph = q(((t - LEAVE_T) * 2) % 1, 60);
      out.places.push(person(cam, { i: 30 + i, o: MASON[i + 1], okey: `m${i + 1}` }, x, D0, z, view,
        { mode: "march", phase: ph, expr, blink: lidAt(t, 30 + i) }, { mode: "march", phase: ph, expr, stride: view.fs }));
      blob(out, x, D0, z);
    } else stand(cam, out, 30 + i, MASON[i + 1], `m${i + 1}`, x, D0, z,
      { mode: "stand", expr, blink: lidAt(t, 30 + i, [DROP_T]), prop: dropped ? null : ["hammer", q(hammer(t, 0.85, i * 0.3), 30)] });
    // the tool tumbling to the ground: 0.3 s fall from the hand
    if (dropped) {
      const u = clamp01((t - (DROP_T - LEAD)) / 0.3), y = D0 + 1.25 * (1 - u * u);
      out.fx.push({ key: `tool${i % 2}`, cw: 300, ch: 300, draw: (p) => fxTool(p, i % 2), x: x0 + 0.55, y: y + 0.15, z: z - 0.1, w: 0.45, h: 0.45, rot: u * (i % 2 ? 2.6 : -2.2) });
      if (u >= 1 && t < DROP_T + 0.6) {
        const k = clamp01((t - DROP_T - 0.25) / 0.35);
        out.fx.push({ key: `puff${q(k, 30)}`, cw: 300, ch: 300, draw: (p) => fxPuff(p, q(k, 30)), x: x0 + 0.55, y: D0 + 0.25, z: z - 0.15, w: 0.8, h: 0.8 });
      }
    }
  });
};
/** "Unluckily": the beaten column sitting in the camp at dusk, helmets askew, stars round some heads (shot 6) */
const camp = (cam: CamInfo, t: number, out: Stage) => {
  const spots: [number, number][] = [[-1.6, 0.6], [-0.4, -0.4], [0.9, 0.5], [2.0, -0.6], [-2.6, -0.9], [0.2, 1.9], [-1.4, 2.4], [1.8, 2.1], [3.1, 1.0]];
  const ex: Expr[] = ["dazed", "pained", "dazed", "relief", "pained"];
  spots.forEach(([dx, dz], i) => {
    const x = CAMP[0] + dx, z = CAMP[2] + dz, v = (i + 1) % 4;
    out.places.push(person(cam, { i: 50 + i, o: { ...PISAN[v], spear: false }, okey: `ps${v}` }, x, D0, z, { side: false, mirror: false },
      { mode: "sit", expr: ex[i % 5], blink: lidAt(t, 50 + i), tilt: (hh(i, 3) - 0.5) * 14 }, {}));
    blob(out, x, D0, z, 1.1);
    if (i % 3 === 0) {
      const u = (t * 0.9 + hh(i)) % 1;
      out.fx.push({ key: `stars${q(u, 30)}`, cw: 420, ch: 210, draw: (p) => fxStars(p, q(u, 30)), x, y: D0 + 1.3, z, w: 0.75, h: 0.375 });
    }
  });
  // broken spears lying about
  for (const [dx, dz, r] of [[-3.4, 0.4, 0.4], [3.8, -0.2, -0.3]] as const)
    out.fx.push({ key: "tool1", cw: 300, ch: 300, draw: (p) => fxTool(p, 1), x: CAMP[0] + dx, y: D0 + 0.05, z: CAMP[2] + dz, w: 0.7, h: 0.7, flat: true, rot: r });
};
/** 1272: a new generation of masons looks up at the leaning stub (shot 8) */
const returners = (cam: CamInfo, t: number, out: Stage) => {
  const spots: [number, number][] = [[-8.8, 59.4], [-6.9, 58.6], [-5.2, 60.2], [-3.4, 59.0]];
  const LOOKUP = 690 / FPS, BUILD_T = 745 / FPS;
  spots.forEach(([x, z], i) => {
    const expr: Expr = t < LOOKUP ? "neutral" : t < BUILD_T - LEAD ? (i % 2 ? "nervous" : "shock") : "grin";
    stand(cam, out, 60 + i, MASON[4 + i], `m${4 + i}`, x, D0, z,
      { mode: "stand", expr, blink: lidAt(t, 60 + i, [LOOKUP, BUILD_T]), headTilt: t > LOOKUP ? -10 : 0, prop: i === 1 ? ["hammer", 1] : null });
  });
};
/** the banana (shot 9): pops in beside the tower on "banana" */
const BANANA_T = 869 / FPS;
const banana = (t: number, out: Stage) => {
  if (t < BANANA_T) return;
  const u = clamp01((t - BANANA_T) / 0.3), s = u < 1 ? 1 + 0.15 * Math.sin(u * Math.PI) : 1;
  out.fx.push({ key: "banana", cw: 600, ch: 600, draw: (p) => fxBanana(p), x: 21, y: D0 + 30, z: 80, w: 34 * s * u, h: 34 * s * u, rot: -Math.PI / 2 - 0.08 });
};
/** 1990: two visitors turned away at the new barrier (shot 10) */
const turnedAway = (cam: CamInfo, t: number, out: Stage) => {
  if (t < 1006 / FPS) return;
  [[-8.2, 68.4, "shock"], [-7.0, 67.6, "nervous"]].forEach(([x, z, e], i) =>
    stand(cam, out, 70 + i, TOUR[i + 2], `tour${i + 2}`, x as number, D0, z as number, { mode: "stand", expr: e as Expr, blink: lidAt(t, 70 + i), look: -1 }));
};
/** engineers at the lead stack on the high side (shot 11); the last ingot lands on "paperweight" */
const LAST_T = 1163 / FPS;
const leadCrew = (cam: CamInfo, t: number, out: Stage) => {
  const spots: [number, number][] = [[TOWER[0] + TR + 5.4, TOWER[2] - 3.0], [TOWER[0] + TR + 6.6, TOWER[2] - 1.0], [TOWER[0] + TR + 5.2, TOWER[2] + 1.8]];
  spots.forEach(([x, z], i) => {
    const expr: Expr = t < LAST_T - LEAD ? (i === 1 ? "stern" : "neutral") : t < 1194 / FPS ? "grin" : "smile";
    stand(cam, out, 80 + i, ENG[i], `e${i}`, x, D0, z, { mode: "stand", expr, blink: lidAt(t, 80 + i, [LAST_T]), wave: i === 0 && t > LAST_T ? 0.2 : undefined });
  });
  if (t >= LAST_T && t < LAST_T + 0.5) {
    const u = (t - LAST_T) / 0.5;
    out.fx.push({ key: `puff${q(u, 30)}`, cw: 300, ch: 300, draw: (p) => fxPuff(p, q(u, 30)), x: TOWER[0] + TR + 2.4, y: D0 + 2.6, z: TOWER[2] - 1, w: 2.4, h: 2.4 });
  }
};
/** the kid on the wet sand (shot 12): feet settle, the water squeezes out round them, the sand goes firm */
const SQUEEZE_T = 1314 / FPS, FIRM_T = 1380 / FPS;
const WET = "#8f7a58";
const kid = (cam: CamInfo, t: number, out: Stage) => {
  const sink = 0.07 * smooth((t - 41.2) / 1.6), [x, y, z] = BEACH;
  const expr: Expr = t < SQUEEZE_T - LEAD ? "smile" : t < FIRM_T - LEAD ? "whistle" : "grin";
  out.places.push(person(cam, { i: 90, o: { ...KID, boots: "#f5c9a0" }, okey: "kidbare" }, x, y - sink, z, { side: false, mirror: false },
    { mode: "stand", expr, blink: lidAt(t, 90, [SQUEEZE_T, FIRM_T]), headTilt: t > SQUEEZE_T - LEAD && t < FIRM_T ? 12 : 0, look: 0 }, {}, 0.95));
  // the dark wet patch spreading under the feet, then water rings out over the sand
  const w = smooth((t - SQUEEZE_T + 0.2) / 1.6);
  out.fx.push({ key: `blob|contact|${WET}`, cw: 128, ch: 128, draw: (p) => fxContact(p, WET), x, y: y + 0.03, z: z + 0.05, w: 0.6 + 0.9 * w, h: 0.45 + 0.7 * w, flat: true });
  if (t > SQUEEZE_T)
    for (let k = 0; k < 3; k++) {
      const u = (((t - SQUEEZE_T) * 0.55 + k / 3) % 1);
      if (t > FIRM_T + 0.4 && u < 0.2) continue;
      out.fx.push({ key: `ring${q(u, 30)}`, cw: 600, ch: 600, draw: (p) => fxRing(p, q(u, 30)), x, y: y + 0.035, z, w: 1.6, h: 1.6, flat: true });
    }
  blob(out, x, y, z, 0.8);
};
/** the century in the clay (shot 13): beads of water squeezed up out of the ground round the stub's foot */
const beads = (t: number, out: Stage) => {
  for (let i = 0; i < 26; i++) {
    const a = (200 + 140 * hh(i, 3)) * DEG, r = TR + 1.2 + 4.5 * hh(i, 4), per = 1.3 + hh(i, 5);
    const u = ((t * 1.0 + hh(i, 6) * per) % per) / per;
    out.fx.push({ key: `bead${q(u, 20)}`, cw: 200, ch: 260, draw: (p) => fxBead(p, q(u, 20)), x: TOWER[0] + Math.cos(a) * r, y: D0 + 0.5, z: TOWER[2] + Math.sin(a) * r, w: 0.9, h: 1.17 });
  }
};
/** the what-if topple (shot 14): dust along the line where the tower lands */
const LAND_T = 1578 / FPS;
const crash = (t: number, out: Stage) => {
  if (t < LAND_T || t > LAND_T + 1.6) return;
  const u = (t - LAND_T) / 1.6;
  for (let k = 0; k < 6; k++) {
    const x = TOWER[0] + TR - 8 - k * 8.5, s = 14 + 4 * (k % 2);
    out.fx.push({ key: `dust${q(u, 30)}`, cw: 600, ch: 400, draw: (p) => fxDust(p, q(u, 30)), x, y: D0 + s * 0.28, z: TOWER[2] + (k % 2 ? 3 : -3), w: s * 1.5, h: s });
  }
};
/** engineers at the extraction rig (shots 15, 16): the drill, the strange idea, the switch-off */
const STRANGE_T = 1650 / FPS, OFF_T = 1836 / FPS;
const drillCrew = (cam: CamInfo, t: number, out: Stage, id: number) => {
  // beside the rig, clear of the lens's line to the bore hole: the switch man on its near side, two behind
  const spots: [number, number][] = [[17.2, 84.0], [5.8, 89.2], [16.4, 90.6]];
  spots.forEach(([x, z], i) => {
    let expr: Expr = i === 2 ? "stern" : "neutral";
    let wave: number | undefined;
    if (id === 15) expr = t < STRANGE_T - LEAD ? expr : i === 1 ? "nervous" : t < 1668 / FPS ? "smile" : "grin";
    if (id === 16) {
      // the near engineer reaches up to the switch and pulls it down on "stopped"
      if (i === 0) { const k = clamp01((t - OFF_T + 0.5) / 0.5); wave = q(0.8 - 1.6 * k, 30); expr = t < OFF_T ? "stern" : "smile_closed"; }
      else expr = t < OFF_T ? "neutral" : "grin";
    }
    stand(cam, out, 95 + i, ENG[(i + 1) % 4], `e${(i + 1) % 4}`, x, D0, z, { mode: "stand", expr, blink: lidAt(t, 95 + i, [STRANGE_T, OFF_T]), wave });
  });
  // soil coming up out of the bore hole: clods thrown out onto the growing heaps while the auger turns
  if (t > 1668 / FPS && t < OFF_T) {
    for (let k = 0; k < 3; k++) {
      const u = ((t * 1.6 + k / 3) % 1);
      out.fx.push({ key: `soil${q(u, 30)}`, cw: 300, ch: 300, draw: (p) => fxSoil(p, q(u, 30)), x: BORE[0] + 0.3, y: D0 + 1.1, z: BORE[2] - 0.2, w: 3.2, h: 3.2 });
    }
  }
};

/** everything with a face (and every 2D effect) in shot `id` at time t */
export const stage = (id: number, t: number, f: number, cam: CamInfo): Stage => {
  const out: Stage = { places: [], fx: [] };
  const s = SHOTS[id - 1];
  LNAME = s.light;
  findSun(cam, SUN);
  switch (s.crowd) {
    case "tourists": tourists(cam, t, out); break;
    case "masons": masonsBase(cam, t, f, out); break;
    case "masonsTop": masonsTop(cam, t, f, out); break;
    case "war": column(id, t, cam, out); masonsDrop(cam, t, out); break;
    case "march": column(id, t, cam, out); break;
    case "camp": camp(cam, t, out); break;
    case "return": returners(cam, t, out); break;
    case "closed": turnedAway(cam, t, out); break;
    case "lead": leadCrew(cam, t, out); break;
    case "kid": kid(cam, t, out); break;
    case "drill": drillCrew(cam, t, out, 15); break;
    case "stop": drillCrew(cam, t, out, 16); break;
  }
  if (id === 9) banana(t, out);
  if (id === 13) beads(t, out);
  if (id === 14) crash(t, out);
  return out;
};
export { FPS };
