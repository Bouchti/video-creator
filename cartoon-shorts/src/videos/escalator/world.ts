// The whole place as one three.js scene: sky, a town plaza with the escalator rising to a deck in front of a store,
// the section view (cutaway) of the escalator, and the 1898 Harrods hall with its leather belt far to the west.
// update(id, f, camera) poses everything for shot `id` at frame f (a pure function of id + f).
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { staticFile } from "remotion";
import { Batch, boxGeo, V, lam, Kit, Ray, kitClone, quad, house, prop, setSight } from "./build";
import { ctex, rep, grassHD, cloudHD, facadeHD, stoneHD } from "./paint";
import { Pen } from "./toon";
import { LIGHTS, LOOK, LightPreset } from "./lights";
import { TONE, CHAR, untone } from "./shade";
import { NOINK } from "./ink";
import { Pool, Actor, Fx, stage } from "./cast";
import { FPS, SHOTS, camAt, V3, FOREGROUND, ShotDef, DECK, HALL, PLAZA, ZCUT, cutAt, noTopPlateAt, glowAt } from "./story";
import { Escalator, Belt } from "./machine";
import { RISE, X0, XS1, h, HB } from "./escpath";

// ---------------- assets ----------------
const KENNEY = ["tree_oak", "tree_default", "tree_detailed", "tree_fat", "tree_cone", "tree-high-round", "tree", "plant_bushLarge", "plant_bushDetailed",
  "plant_bush", "hedge", "flower_redA", "flower_yellowA", "flower_purpleA", "lantern", "stall-bench", "banner-red", "banner-green", "stall-red", "stall-green"];
let kitP: Promise<Kit> | null = null;
export const loadKit = () => {
  if (!kitP) {
    const loader = new GLTFLoader();
    kitP = Promise.all(KENNEY.map((n) => loader.loadAsync(staticFile(`bridge/kenney/${n}.glb`)).then((g) => [n, g.scene] as const).catch(() => [n, null] as const)))
      .then((list) => Object.fromEntries(list.filter((e) => e[1]).map(([n, s]) => [n, s!])) as Kit);
  }
  return kitP;
};

const discTex = () => ctex("sunDisc", 128, 128, (g) => {
  const gr = g.createRadialGradient(64, 64, 58, 64, 64, 64); gr.addColorStop(0, "rgba(255,255,255,1)"); gr.addColorStop(1, "rgba(255,255,255,0)");
  g.fillStyle = gr; g.fillRect(0, 0, 128, 128);
});
const haloTex = () => ctex("sunHalo", 256, 256, (g) => {
  const im = g.createImageData(256, 256);
  for (let y = 0; y < 256; y++) for (let x = 0; x < 256; x++) {
    const u = Math.hypot(x - 127.5, y - 127.5) / 128;
    const a = (0.55 * Math.exp(-((u / 0.25) ** 2)) + 0.35 * Math.exp(-((u / 0.6) ** 2))) * (1 - Math.min(1, Math.max(0, (u - 0.8) / 0.2)));
    const i = (y * 256 + x) * 4; im.data[i] = im.data[i + 1] = im.data[i + 2] = 255; im.data[i + 3] = Math.round(255 * Math.min(1, a));
  }
  g.putImageData(im, 0, 0);
});

// ---------------- painted textures of this film ----------------
/** plaza paving: big pale slabs with dark seams (one 2 x 2 m tile = 4 slabs) */
const pavingHD = () => ctex("pavingHD", 1024, 1024, (g, r) => {
  g.fillStyle = "#ddd3c2"; g.fillRect(0, 0, 1024, 1024);
  for (let y = 0; y < 2; y++) for (let x = 0; x < 2; x++) {
    const c = ["#e2d8c6", "#d6ccb9", "#ddd2bf", "#cfc5b2"][(x + 2 * y) % 4];
    g.fillStyle = c; g.fillRect(x * 512 + 6, y * 512 + 6, 500, 500);
    for (let k = 0; k < 60; k++) { g.fillStyle = `rgba(120,105,90,${0.04 + r() * 0.05})`; g.beginPath(); g.arc(x * 512 + 20 + r() * 470, y * 512 + 20 + r() * 470, 3 + r() * 14, 0, 7); g.fill(); }
  }
  g.fillStyle = "rgba(70,60,55,0.55)";
  g.fillRect(0, 0, 1024, 6); g.fillRect(0, 512, 1024, 6); g.fillRect(0, 0, 6, 1024); g.fillRect(512, 0, 6, 1024);
});
/** the section through the ground: paving slab, gravel bed, brown earth, darker clay, stones (14 m tall, 4 m wide tile) */
const sectionTex = () => ctex("sectionHD", 512, 1792, (g, r) => {
  const H = 1792, px = H / 14; // 128 px per metre
  const band = (y0: number, y1: number, c: string) => { g.fillStyle = c; g.fillRect(0, H - y1 * px, 512, (y1 - y0) * px); };
  band(0, 14, "#8a6748"); band(0, 9, "#7a5a3e"); band(0, 4.5, "#6a4c36");
  band(13.62, 14, "#cfc5b2"); band(13.3, 13.62, "#a7a094");
  for (let i = 0; i < 260; i++) {
    const y = r() * 13.2, x = r() * 512, rr = 3 + r() * 10;
    g.fillStyle = y > 9 ? "rgba(160,130,100,0.6)" : "rgba(60,44,32,0.45)";
    g.beginPath(); g.ellipse(x, H - y * px, rr * 1.3, rr, r() * 3, 0, 7); g.fill();
  }
  g.fillStyle = "rgba(30,20,14,0.6)"; g.fillRect(0, H - 13.62 * px, 512, 4);
});
const parquetHD = () => ctex("parquetHD", 1024, 1024, (g, r) => {
  g.fillStyle = "#9a6438"; g.fillRect(0, 0, 1024, 1024);
  const W = 128, L = 384;
  for (let y = -L; y < 1024 + L; y += W) for (let x = -L; x < 1024 + L; x += 2 * W) {
    const off = ((y / W) % 2) * W;
    for (const [dx, rot] of [[0, 0.785], [W, -0.785]] as const) {
      g.save(); g.translate(x + dx + off, y); g.rotate(rot);
      g.fillStyle = ["#a86e3e", "#94602f", "#b07644", "#8c5a2e"][Math.floor(r() * 4)];
      g.fillRect(0, 0, L * 0.55, W * 0.42); g.strokeStyle = "rgba(50,28,12,0.55)"; g.lineWidth = 4; g.strokeRect(0, 0, L * 0.55, W * 0.42);
      g.restore();
    }
  }
});
const wallpaperHD = () => ctex("wallpaperHD", 512, 512, (g) => {
  g.fillStyle = "#2f5d4f"; g.fillRect(0, 0, 512, 512);
  for (let x = 0; x < 512; x += 128) { g.fillStyle = "#386a5b"; g.fillRect(x + 40, 0, 48, 512); g.fillStyle = "rgba(225,190,110,0.55)"; g.fillRect(x + 62, 0, 4, 512); }
  for (let y = 64; y < 512; y += 128) for (let x = 0; x < 512; x += 128) {
    g.fillStyle = "rgba(225,190,110,0.6)";
    g.beginPath(); g.moveTo(x + 64, y - 26); g.quadraticCurveTo(x + 92, y, x + 64, y + 26); g.quadraticCurveTo(x + 36, y, x + 64, y - 26); g.fill();
  }
});
const ceilingHD = () => ctex("ceilingHD", 512, 512, (g) => {
  g.fillStyle = "#efe3c8"; g.fillRect(0, 0, 512, 512);
  g.strokeStyle = "#c9b48a"; g.lineWidth = 18; g.strokeRect(9, 9, 494, 494);
  g.strokeStyle = "#d9c79f"; g.lineWidth = 8; g.strokeRect(60, 60, 392, 392);
  g.fillStyle = "#e2a94a"; g.beginPath(); g.arc(256, 256, 40, 0, 7); g.fill();
});
const storeFacade = () => lam("storeFacade", () => ({ map: facadeHD("storeFront", 28, 17.5, { wall: "#e8d2a6", shutter: "#2f5f6a", door: true }) }));

type Mats = Record<string, THREE.Material>;

/** horizontal quad facing up at y covering x0..x1, z0..z1, uv tiled every `tile` m */
function quadUp(x0: number, x1: number, z0: number, z1: number, tile: number, y = 0) {
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute([x0, y, z1, x1, y, z1, x1, y, z0, x0, y, z1, x1, y, z0, x0, y, z0], 3));
  g.setAttribute("normal", new THREE.Float32BufferAttribute([0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0], 3));
  g.setAttribute("uv", new THREE.Float32BufferAttribute([x0 / tile, z1 / tile, x1 / tile, z1 / tile, x1 / tile, z0 / tile, x0 / tile, z1 / tile, x1 / tile, z0 / tile, x0 / tile, z0 / tile], 2));
  return g;
}

export class World {
  root = new THREE.Group();
  private nearG = new THREE.Group();   // hidden in section views
  private cap: THREE.Mesh;
  private pool = new Pool();
  private actors: Actor[] = [];
  private fxs: Fx[] = [];
  private hemi: THREE.HemisphereLight; private sun: THREE.DirectionalLight; private fill: THREE.DirectionalLight;
  private sky: THREE.Mesh; private skyMat: THREE.ShaderMaterial;
  private fog = new THREE.Fog("#bccbec", 25, 420);
  private sunDisc: THREE.Sprite; private sunHalo: THREE.Sprite;
  private sunCache = new Map<number, THREE.Vector3>();
  private shadowCache = new Map<number, number>();
  private cloudMaps: Record<"day" | "golden", THREE.Texture[]>;
  private fgs: { o: THREE.Object3D; a: number; b: number }[] = [];
  private clouds: THREE.Mesh[] = [];
  private cloudHome: THREE.Vector3[] = [];
  private esc: Escalator; private belt: Belt;
  private frustum = new THREE.Frustum();
  private m4 = new THREE.Matrix4(); private v = new THREE.Vector3(); private sph = new THREE.Sphere();

  constructor(kit: Kit) {
    const R = this.root, M: Mats = {};
    R.add(this.nearG);
    // ---- sky + light ----
    this.skyMat = new THREE.ShaderMaterial({
      uniforms: { c0: { value: new THREE.Color() }, c1: { value: new THREE.Color() }, c2: { value: new THREE.Color() },
        c3: { value: new THREE.Color() }, c4: { value: new THREE.Color() }, e: { value: new THREE.Vector4() } },
      vertexShader: "varying vec3 vP; void main(){ vP = normalize(position); gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }",
      fragmentShader: `uniform vec3 c0, c1, c2, c3, c4; uniform vec4 e; varying vec3 vP;
        void main(){ float el = asin(clamp(normalize(vP).y, -1.0, 1.0));
          vec3 c = mix(c0, c1, smoothstep(0.0, e.x, el));
          c = mix(c, c2, smoothstep(e.x, e.y, el));
          c = mix(c, c3, smoothstep(e.y, e.z, el));
          c = mix(c, c4, smoothstep(e.z, e.w, el));
          gl_FragColor = vec4(c, 1.0); }`,
      side: THREE.BackSide, depthWrite: false, fog: false,
    });
    this.sky = new THREE.Mesh(new THREE.SphereGeometry(1100, 48, 24), this.skyMat);
    this.sky.renderOrder = -1; this.sky.frustumCulled = false; this.sky.layers.set(NOINK);
    R.add(this.sky);
    this.sunDisc = new THREE.Sprite(new THREE.SpriteMaterial({ map: discTex(), color: new THREE.Color(6.0, 4.4, 2.4), fog: false, depthWrite: false }));
    this.sunHalo = new THREE.Sprite(new THREE.SpriteMaterial({ map: haloTex(), color: new THREE.Color(1, 1, 1), fog: false, depthWrite: false, depthTest: true,
      transparent: true, blending: THREE.AdditiveBlending }));
    this.sunDisc.renderOrder = -0.5; this.sunHalo.renderOrder = 5;
    for (const m of [this.sunDisc, this.sunHalo]) { m.frustumCulled = false; m.layers.set(NOINK); R.add(m); }
    this.hemi = new THREE.HemisphereLight("#cfe6ff", "#6c5c8c", 1.1);
    this.sun = new THREE.DirectionalLight("#fff0d6", 2.6);
    this.sun.castShadow = true;
    this.sun.shadow.mapSize.set(4096, 4096);
    this.fill = new THREE.DirectionalLight("#9fb8ff", 0.35);
    R.add(this.hemi, this.sun, this.sun.target, this.fill, this.fill.target);
    this.cloudMaps = { day: [0, 1, 2, 3].map((k) => cloudHD(k, LOOK.day.cloud)), golden: [0, 1, 2, 3].map((k) => cloudHD(k, LOOK.golden.cloud)) };
    for (let i = 0; i < 9; i++) {
      const a = (i / 9) * Math.PI * 2 + 0.3, d = 620 + (i % 3) * 60;
      const m = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), new THREE.MeshBasicMaterial({ map: this.cloudMaps.day[i % 4], color: new THREE.Color(1.1, 1.1, 1.1), transparent: true, depthWrite: false, fog: false }));
      const w = 130 + (i % 4) * 30;
      m.position.set(Math.cos(a) * d, 120 + (i % 4) * 38, Math.sin(a) * d); m.scale.set(w, w / 2, 1);
      m.layers.set(NOINK);
      this.clouds.push(m); this.cloudHome.push(m.position.clone()); R.add(m);
    }

    // ---- ground: plaza paving + grass, split at the cut plane (the near halves are hidden in section views) ----
    const b = new Batch(), bn = new Batch();
    M.grass = lam("grassHD", () => ({ map: grassHD() }));
    M.pave = lam("pavingHD", () => ({ map: pavingHD() }));
    const P = PLAZA, HX0 = X0 - 0.95, HX1 = 5.2; // the escalator's hole in the floor (its pit)
    const NX0 = -40, NX1 = 50, NZ1 = 40;          // the near region that is cut away in section views
    // grass outside the plaza
    b.add(quadUp(-600, 600, -600, P.z0, 4), M.grass);
    b.add(quadUp(-600, NX0, P.z0, 600, 4), M.grass);
    b.add(quadUp(NX1, 600, P.z0, 600, 4), M.grass);
    b.add(quadUp(NX0, NX1, NZ1, 600, 4), M.grass);
    b.add(quadUp(NX0, P.x0, P.z0, ZCUT, 4), M.grass); b.add(quadUp(P.x1, NX1, P.z0, ZCUT, 4), M.grass);
    bn.add(quadUp(NX0, P.x0, ZCUT, NZ1, 4), M.grass); bn.add(quadUp(P.x1, NX1, ZCUT, NZ1, 4), M.grass);
    bn.add(quadUp(P.x0, P.x1, P.z1, NZ1, 4), M.grass);
    // paving: far part, the strips beside the pit, the near part
    b.add(quadUp(P.x0, P.x1, P.z0, -ZCUT, 2), M.pave);
    b.add(quadUp(P.x0, HX0, -ZCUT, ZCUT, 2), M.pave); b.add(quadUp(HX1, P.x1, -ZCUT, ZCUT, 2), M.pave);
    bn.add(quadUp(P.x0, P.x1, ZCUT, P.z1, 2), M.pave);
    // the section face of the ground (seen only in section views): 14 m of soil with the pit cut out of it
    {
      const s = new THREE.Shape([V(NX0, -14, 0), V(NX1, -14, 0), V(NX1, 0, 0), V(NX0, 0, 0)].map((p) => new THREE.Vector2(p.x, p.y)));
      const pit = new THREE.Path();
      pit.moveTo(HX0, 0); pit.lineTo(HX1, 0);
      for (let x = HX1; x >= 1.6; x -= 0.1) pit.lineTo(x, Math.min(0, h(x) - 2.25));
      pit.lineTo(1.6, -2.3); pit.lineTo(HX0, -2.3); pit.lineTo(HX0, 0);
      s.holes.push(pit);
      const g = new THREE.ShapeGeometry(s, 8);
      const pos = g.attributes.position as THREE.BufferAttribute, uv = g.attributes.uv as THREE.BufferAttribute;
      for (let i = 0; i < pos.count; i++) uv.setXY(i, pos.getX(i) / 4, (pos.getY(i) + 14) / 14);
      g.translate(0, 0, ZCUT);
      const t = sectionTex(); t.wrapS = THREE.RepeatWrapping; t.wrapT = THREE.ClampToEdgeWrapping;
      this.cap = new THREE.Mesh(g, lam("section", () => ({ map: t })));
      this.cap.receiveShadow = true; this.cap.visible = false;
      R.add(this.cap);
    }

    // ---- the upper deck the escalator arrives on, its columns and railing, and the store behind ----
    M.deck = lam("deckPave", () => ({ map: pavingHD() }));
    M.conc = lam("concrete", () => ({ color: "#cfc8bb" }));
    M.rail = lam("deckRail", () => ({ color: "#5d6470" }));
    const D = DECK, yb = RISE - D.thick, holeX1 = XS1 + 2.15;
    b.add(boxGeo(V(D.x0, yb, D.z0), V(D.x1, RISE, -ZCUT), 2, true), M.deck);
    b.add(boxGeo(V(holeX1, yb, -ZCUT), V(D.x1, RISE, ZCUT), 2, true), M.deck);
    bn.add(boxGeo(V(D.x0, yb, ZCUT), V(D.x1, RISE, D.z1), 2, true), M.deck);
    for (const x of [11.6, 17.0, 22.4, 26.4]) for (const z of [-6.2, 6.2]) {
      const g = new THREE.CylinderGeometry(0.3, 0.34, yb, 18).translate(x, yb / 2, z);
      (z > 0 ? bn : b).add(g, M.conc);
    }
    // railing posts + top rail along the deck's front edge (gap for the escalator) and its sides
    const railRun = (bb: Batch, a: THREE.Vector3, c: THREE.Vector3) => {
      const L = a.distanceTo(c), n = Math.max(1, Math.round(L / 1.2));
      for (let i = 0; i <= n; i++) { const p = a.clone().lerp(c, i / n); bb.add(boxGeo(V(p.x - 0.04, RISE, p.z - 0.04), V(p.x + 0.04, RISE + 1.05, p.z + 0.04)), M.rail); }
      const dx = c.x - a.x, dz = c.z - a.z;
      bb.add(boxGeo(V(Math.min(a.x, c.x) - 0.05, RISE + 1.0, Math.min(a.z, c.z) - 0.05), V(Math.max(a.x, c.x) + 0.05, RISE + 1.1, Math.max(a.z, c.z) + 0.05)), M.rail);
      if (Math.abs(dx) + Math.abs(dz) > 0) bb.add(boxGeo(V(Math.min(a.x, c.x) - 0.02, RISE + 0.5, Math.min(a.z, c.z) - 0.02), V(Math.max(a.x, c.x) + 0.02, RISE + 0.55, Math.max(a.z, c.z) + 0.02)), M.rail);
    };
    railRun(b, V(D.x0 + 0.05, 0, D.z0 + 0.05), V(D.x0 + 0.05, 0, -1.0));
    railRun(bn, V(D.x0 + 0.05, 0, 1.0), V(D.x0 + 0.05, 0, D.z1 - 0.05));
    railRun(b, V(D.x0 + 0.05, 0, D.z0 + 0.05), V(D.x1 - 0.5, 0, D.z0 + 0.05));
    railRun(bn, V(D.x0 + 0.05, 0, D.z1 - 0.05), V(D.x1 - 0.5, 0, D.z1 - 0.05));
    // the store: facade on x = 27 from the plaza up past the deck, flat roof with a cornice
    const SX = D.x1, SZ = 14, SH = 17.5;
    b.add(quad(V(SX, 0, SZ), V(SX, 0, -SZ), V(SX, SH, -SZ), V(SX, SH, SZ)), storeFacade());
    b.add(boxGeo(V(SX, 0, -SZ), V(SX + 16, SH, SZ), 4), lam("storeSide", () => ({ color: "#e0c99c" })));
    b.add(boxGeo(V(SX - 0.5, SH - 0.6, -SZ - 0.5), V(SX + 16.5, SH, SZ + 0.5)), lam("cornice", () => ({ color: "#efe3c8" })));
    b.add(boxGeo(V(SX - 1.8, RISE + 3.2, -6), V(SX, RISE + 3.45, 6)), lam("canopy", () => ({ color: "#c0353a" })));
    // plaza furniture (far side only, so nothing stands between the section views and the lens)
    for (const [n, x, z, hgt] of [["tree_oak", -14, -9, 7.5], ["tree_default", -4, -11, 7], ["tree-high-round", 6, -11.5, 8], ["tree_fat", -20, -3, 6.5],
      ["tree_oak", 17, -11, 7.5], ["lantern", -9, -1.8, 3], ["lantern", 3.8, -2.2, 3], ["stall-bench", -11.5, -6, 1.0], ["stall-bench", -1.5, -7.5, 1.0],
      ["plant_bushLarge", -16.5, -12.5, 1.4], ["plant_bushDetailed", 0.5, -12.6, 1.3], ["flower_redA", -6.5, -12.8, 0.5], ["flower_yellowA", 2.2, -12.9, 0.5]] as const)
      prop(b, kit, n, x, 0, z, hgt, x);
    for (const [n, x, z, hgt] of [["lantern", -9, 3.2, 3], ["stall-bench", -11, 6.5, 1.0]] as const)
      prop(bn, kit, n, x, 0, z, hgt, x);
    // the town round the plaza (houses that would block a lens are left out by the sight lines)
    setSight(sightLines());
    const rr = (i: number) => { const v = Math.sin(i * 91.7) * 43758.5; return v - Math.floor(v); };
    let x = -26;
    for (let i = 0; x < 26; i++) { const w = [7, 9][i % 2], hgt = [8.4, 9.8, 7][i % 3]; house(b, x + w / 2, P.z0 - 5, 0, w, 8, hgt, i * 3 + 1); x += w + 0.4; }
    for (let i = 0, z = -12; z < 30; i++) { const w = [9, 7][i % 2]; house(b, P.x0 - 5, z + w / 2, Math.PI / 2, w, 8, [9.8, 8.4][i % 2], i * 5 + 2); z += w + 0.4; }
    for (let i = 0, xx = -24; xx < 24; i++) { const w = [7, 9][i % 2]; house(i % 2 ? bn : bn, xx + w / 2, P.z1 + 6, Math.PI, w, 8, [8.4, 7, 9.8][i % 3], i * 7 + 3); xx += w + 0.6; }
    for (let i = 0; i < 40; i++) {
      const a = rr(i) * Math.PI * 2, d = 70 + rr(i + 50) * 120;
      prop(b, kit, ["tree_cone", "tree_default", "tree_oak"][i % 3], Math.cos(a) * d, 0, Math.sin(a) * d, 10 + rr(i + 9) * 6, i);
    }
    setSight([]);
    b.build(R); bn.build(this.nearG);

    // ---- 1898: the Harrods hall (open-fronted set; walls and ceiling cast no shadow so the sun lights the room) ----
    const hb = new Batch(), H = HALL, GY = H.gal;
    const par = lam("parquet", () => ({ map: parquetHD() })), wp = lam("wallpaper", () => ({ map: wallpaperHD() }));
    const mah = lam("mahoganyWall", () => ({ color: "#6e3320" })), cream = lam("hallCream", () => ({ color: "#efe3c8" })), gold = lam("hallGold", () => ({ color: "#d9a845" }));
    const HZ1 = 14;
    hb.add(quadUp(H.x0, H.x1, H.z0, HZ1, 3, 0.004), par);
    hb.add(quad(V(H.x0, 0, H.z0), V(H.x1, 0, H.z0), V(H.x1, 8, H.z0), V(H.x0, 8, H.z0), (H.x1 - H.x0) / 2, 4), wp);
    hb.add(quad(V(H.x0, 0, HZ1), V(H.x0, 0, H.z0), V(H.x0, 8, H.z0), V(H.x0, 8, HZ1), (HZ1 - H.z0) / 2, 4), wp);
    hb.add(quad(V(H.x1, 0, H.z0), V(H.x1, 0, HZ1), V(H.x1, 8, HZ1), V(H.x1, 8, H.z0), (HZ1 - H.z0) / 2, 4), wp);
    hb.add(quad(V(H.x0, 8, H.z0), V(H.x1, 8, H.z0), V(H.x1, 8, HZ1), V(H.x0, 8, HZ1), (H.x1 - H.x0) / 4, (HZ1 - H.z0) / 4), lam("ceiling", () => ({ map: ceilingHD(), side: THREE.DoubleSide })));
    // wainscot + cornice round the walls
    hb.add(boxGeo(V(H.x0, 0, H.z0), V(H.x1, 1.2, H.z0 + 0.08)), mah);
    hb.add(boxGeo(V(H.x0, 0, H.z0), V(H.x0 + 0.08, 1.2, HZ1)), mah);
    hb.add(boxGeo(V(H.x1 - 0.08, 0, H.z0), V(H.x1, 1.2, HZ1)), mah);
    hb.add(boxGeo(V(H.x0, 7.6, H.z0), V(H.x1, 8, H.z0 + 0.3)), cream);
    // the gallery the belt climbs to: slab, fascia, balustrade, cast-iron columns
    const gx0 = HB.x1, gz1 = -2.4;
    hb.add(boxGeo(V(gx0, GY - 0.35, H.z0), V(H.x1, GY, gz1), 2, true), par);
    hb.add(boxGeo(V(gx0 - 0.05, GY - 0.45, gz1), V(H.x1, GY - 0.1, gz1 + 0.12)), gold);
    const bal = (a: THREE.Vector3, c: THREE.Vector3) => {
      const L = a.distanceTo(c), n = Math.max(1, Math.round(L / 0.28));
      for (let i = 0; i <= n; i++) { const p = a.clone().lerp(c, i / n); hb.add(new THREE.CylinderGeometry(0.035, 0.045, 0.85, 8).translate(p.x, GY + 0.425, p.z), cream); }
      hb.add(boxGeo(V(Math.min(a.x, c.x) - 0.07, GY + 0.85, Math.min(a.z, c.z) - 0.07), V(Math.max(a.x, c.x) + 0.07, GY + 0.97, Math.max(a.z, c.z) + 0.07)), mah);
    };
    bal(V(gx0 + 0.3, 0, gz1 + 0.05), V(H.x1 - 0.2, 0, gz1 + 0.05));
    bal(V(gx0 + 0.05, 0, gz1 + 0.05), V(gx0 + 0.05, 0, HB.z + 0.75));
    bal(V(gx0 + 0.05, 0, HB.z - 0.75), V(gx0 + 0.05, 0, H.z0 + 0.1));
    for (const xc of [gx0 + 2.5, gx0 + 6.5, gx0 + 10.5]) {
      hb.add(new THREE.CylinderGeometry(0.16, 0.2, GY - 0.35, 14).translate(xc, (GY - 0.35) / 2, gz1 - 0.2), cream);
      hb.add(boxGeo(V(xc - 0.28, GY - 0.6, gz1 - 0.48), V(xc + 0.28, GY - 0.35, gz1 + 0.08)), gold);
    }
    // counters with goods + shelves on the back wall
    const goods = ["#c0353a", "#3f6fb5", "#e8c45a", "#5d9a3a", "#f08a2c", "#7b5ac9", "#f4f1ea"];
    for (const [cx, cz] of [[H.x0 + 1.8, -1.5], [H.x0 + 1.8, 3.5]] as const) {
      hb.add(boxGeo(V(cx - 1.5, 0, cz - 0.45), V(cx + 1.5, 0.95, cz + 0.45)), lam("mahoganyHall", () => ({ color: "#7a3a22" })));
      hb.add(boxGeo(V(cx - 1.55, 0.95, cz - 0.5), V(cx + 1.55, 1.0, cz + 0.5)), gold);
      for (let k = 0; k < 4; k++) hb.add(boxGeo(V(cx - 1.2 + k * 0.65, 1.0, cz - 0.2), V(cx - 0.75 + k * 0.65, 1.3 + 0.12 * (k % 2), cz + 0.2)), lam("goods" + k, () => ({ color: goods[k] })));
    }
    for (let sh = 0; sh < 3; sh++) {
      const y = 1.6 + sh * 0.75;
      hb.add(boxGeo(V(H.x0 + 0.5, y, H.z0), V(HB.x0 - 1.2, y + 0.06, H.z0 + 0.45)), mah);
      for (let k = 0; k < 9; k++) {
        const bx = H.x0 + 0.7 + k * 0.75;
        if (bx > HB.x0 - 1.6) break;
        hb.add(boxGeo(V(bx, y + 0.06, H.z0 + 0.05), V(bx + 0.5, y + 0.36 + 0.1 * ((k + sh) % 3), H.z0 + 0.4)), lam("goods" + ((k + sh) % 7), () => ({ color: goods[(k + sh) % 7] })));
      }
    }
    hb.build(R, false);
    // chandeliers: brass rings with glowing bulbs (HDR: bloom)
    const bulb = new THREE.MeshBasicMaterial({ color: new THREE.Color(3.2, 2.5, 1.5) });
    for (const [cx, cz] of [[HB.x0 + 1.5, 1.5], [HB.x0 + 9.5, 3.0], [HB.x0 + 4.5, 8.5]] as const) {
      const g = new THREE.Group();
      g.add(new THREE.Mesh(new THREE.TorusGeometry(0.55, 0.035, 8, 40).rotateX(Math.PI / 2), gold));
      g.add(new THREE.Mesh(new THREE.CylinderGeometry(0.012, 0.012, 1.3, 6).translate(0, 0.65, 0), gold));
      for (let k = 0; k < 6; k++) { const a = (k / 6) * Math.PI * 2; g.add(new THREE.Mesh(new THREE.SphereGeometry(0.07, 12, 8).translate(Math.cos(a) * 0.55, 0.1, Math.sin(a) * 0.55), bulb)); }
      g.position.set(cx, 6.7, cz); R.add(g);
    }

    // ---- the machines ----
    this.esc = new Escalator(R);
    this.belt = new Belt(R);
    for (const fg of FOREGROUND) {
      const o = kitClone(kit, fg.kit, fg.s ?? 1);
      if (!o) continue;
      o.position.set(...fg.pos); o.rotation.y = fg.yaw ?? 0; o.visible = false;
      this.fgs.push({ o, a: fg.a, b: fg.b }); R.add(o);
    }
  }

  /** camera-relative sun, frozen per shot: the shot's mean view direction turned by az toward screen right, lifted by el */
  private shotSun(id: number, s: ShotDef, L: LightPreset) {
    let v = this.sunCache.get(id);
    if (v) return v;
    let fx = 0, fz = 0;
    for (let f = s.a; f < s.b; f += 3) {
      const c = camAt(id, f), x = c.look[0] - c.pos[0], z = c.look[2] - c.pos[2], n = Math.hypot(x, z) || 1;
      fx += x / n; fz += z / n;
    }
    const n = Math.hypot(fx, fz) || 1; fx /= n; fz /= n;
    const az = THREE.MathUtils.degToRad(s.sunAz ?? L.az), el = THREE.MathUtils.degToRad(s.sunEl ?? L.el);
    const hx = fx * Math.cos(az) - fz * Math.sin(az), hz = fz * Math.cos(az) + fx * Math.sin(az);
    v = new THREE.Vector3(hx * Math.cos(el), Math.sin(el), hz * Math.cos(el)).normalize();
    this.sunCache.set(id, v);
    return v;
  }
  private shadowR(id: number, s: ShotDef) {
    let r = this.shadowCache.get(id);
    if (r === undefined) {
      r = 12;
      for (let f = s.a; f < s.b; f += 2) {
        const c = camAt(id, f), d = Math.hypot(c.look[0] - c.pos[0], c.look[1] - c.pos[1], c.look[2] - c.pos[2]);
        r = Math.max(r, THREE.MathUtils.clamp(d * 1.15 + 7, 12, 95));
      }
      this.shadowCache.set(id, r);
    }
    return r;
  }
  private actor(i: number) { while (this.actors.length <= i) this.actors.push(new Actor(this.root)); return this.actors[i]; }
  private fx(i: number) { while (this.fxs.length <= i) this.fxs.push(new Fx(this.root)); return this.fxs[i]; }

  update(id: number, f: number, cam: THREE.PerspectiveCamera, scene: THREE.Scene) {
    const t = f / FPS, s = SHOTS[id - 1], L = LIGHTS[s.light];
    const c = camAt(id, f);
    cam.position.set(...c.pos); cam.up.set(0, 1, 0); cam.lookAt(...c.look); cam.rotateZ(c.roll);
    cam.fov = c.fov; cam.near = THREE.MathUtils.clamp(0.22 * Math.hypot(c.look[0] - c.pos[0], c.look[1] - c.pos[1], c.look[2] - c.pos[2]), 0.05, 3.0); cam.far = 1500; cam.updateProjectionMatrix(); cam.updateMatrixWorld();
    const focus = V(...c.look);
    cam.layers.enable(NOINK);
    // ---- light rig: camera-relative sun frozen per shot, two-tone uniforms, shadow fit ----
    const K = LOOK[s.light], sunDir = this.shotSun(id, s, L);
    this.hemi.color.set(L.sky); this.hemi.groundColor.set(L.ground); this.hemi.intensity = L.hemiI;
    this.sun.color.set(L.sunCol); this.sun.intensity = L.sunI;
    let Rr = this.shadowR(id, s);
    if (s.light === "golden") Rr = Math.max(Rr, 30);
    const texel = (2 * Rr) / this.sun.shadow.mapSize.x;
    const lr = this.v.set(0, 1, 0).cross(sunDir).normalize().clone(), lu = sunDir.clone().cross(lr).normalize();
    const fr2 = Math.round(focus.dot(lr) / texel) * texel, fu = Math.round(focus.dot(lu) / texel) * texel, fd = focus.dot(sunDir);
    const snapped = lr.multiplyScalar(fr2).addScaledVector(lu, fu).addScaledVector(sunDir, fd);
    this.sun.position.copy(snapped).addScaledVector(sunDir, 220); this.sun.target.position.copy(snapped);
    const sc = this.sun.shadow.camera;
    sc.left = -Rr; sc.right = Rr; sc.top = Rr; sc.bottom = -Rr; sc.near = 20; sc.far = 480; sc.updateProjectionMatrix();
    this.sun.shadow.bias = L.bias; this.sun.shadow.normalBias = L.normalBias * (Rr / 12);
    this.fill.intensity = 0;
    TONE.uLitCol.value.set(...L.lit); TONE.uShadeCol.value.set(...L.shade); TONE.uShadeLift.value.set(...L.lift);
    TONE.uLambert.value = L.lambert; TONE.uSideK.value = L.sideK; TONE.uTerm.value = L.term; TONE.uBounce.value.set(...LOOK[s.light].bounce); TONE.uSat.value = LOOK[s.light].sat;
    CHAR.uCharTint.value.set(...L.charTint); CHAR.uCharShade.value = L.charShade; CHAR.uGrad.value = L.charGrad;
    CHAR.uBodyGrad.value = L.bodyGrad; CHAR.uSideTint.value.set(...L.sideTint);
    // ---- sky, fog, sun disc + halo, clouds ----
    const su = this.skyMat.uniforms;
    K.sky.c.forEach((hx, i) => untone(hx, su["c" + i].value));
    const e = K.sky.e.map((deg) => THREE.MathUtils.degToRad(deg));
    su.e.value.set(e[1], e[2], e[3], e[4]);
    this.sky.position.copy(cam.position);
    untone(L.fog, this.fog.color); this.fog.near = L.fogNear; this.fog.far = L.fogFar;
    scene.fog = this.fog; scene.background = null;
    const showSun = s.light === "golden";
    this.sunDisc.visible = this.sunHalo.visible = showSun;
    if (showSun) {
      this.sunDisc.position.copy(cam.position).addScaledVector(sunDir, 900);
      this.sunDisc.scale.setScalar(2 * 900 * Math.tan(THREE.MathUtils.degToRad(1.7)));
      this.sunHalo.position.copy(this.sunDisc.position); this.sunHalo.scale.setScalar(2 * 900 * Math.tan(THREE.MathUtils.degToRad(24)));
      (this.sunHalo.material as THREE.SpriteMaterial).color.set(L.sunDisc).multiplyScalar(1.3);
    }
    for (let i = 0; i < this.clouds.length; i++) {
      const m = this.clouds[i], mat = m.material as THREE.MeshBasicMaterial, hm = this.cloudHome[i], a = Math.atan2(hm.z, hm.x) + t * 0.6 * 0.004;
      const dd = Math.hypot(hm.x, hm.z);
      m.position.set(Math.cos(a) * dd, hm.y, Math.sin(a) * dd);
      m.lookAt(cam.position.x, m.position.y, cam.position.z);
      mat.map = this.cloudMaps[s.light][i % 4];
    }
    for (const g of this.fgs) g.o.visible = f >= g.a && f < g.b && g.a < s.b && g.b > s.a;
    // ---- the machines + the section view ----
    const cut = cutAt(id, f);
    this.nearG.visible = !cut; this.cap.visible = cut;
    this.esc.update(t, { cut, noTopPlate: noTopPlateAt(id, f), ...glowAt(id, f) });
    this.belt.update(t);
    // ---- cast + effects ----
    const right = V(0, 0, 0).setFromMatrixColumn(cam.matrixWorld, 0);
    const st = stage(id, t, f, { pos: cam.position, right });
    this.frustum.setFromProjectionMatrix(this.m4.multiplyMatrices(cam.projectionMatrix, cam.matrixWorldInverse));
    const tint = s.light === "golden" ? "#ffcf9e" : "#ffffff";
    let ai = 0;
    const used: Actor[] = [];
    for (const p of st.places) {
      const sc2 = p.scale ?? 1;
      if (!this.frustum.intersectsSphere(this.sph.set(this.v.set(p.x, p.y + 1.1 * sc2, p.z), 3.5))) continue;
      const a = this.actor(ai++);
      const [w, hgt, k] = p.size ?? [300, 500, 0.5];
      a.r = this.pool.req(p.key, w, hgt, k, p.draw);
      a.mesh.visible = true;
      a.mesh.position.set(p.x, p.y, p.z);
      a.mesh.rotation.set(0, p.yaw ?? Math.atan2(cam.position.x - p.x, cam.position.z - p.z), p.roll ?? 0);
      a.mesh.scale.set(p.mirror ? -sc2 : sc2, sc2, sc2);
      if (a.mat.emissiveMap) a.mat.emissive.set(tint);
      a.mesh.castShadow = L.actorShadow;
      used.push(a);
    }
    for (let i = ai; i < this.actors.length; i++) this.actors[i].mesh.visible = false;
    let fi = 0;
    const fused: Fx[] = [];
    for (const p of st.fx) {
      if (!this.frustum.intersectsSphere(this.sph.set(this.v.set(p.x, p.y, p.z), Math.max(p.w, p.h)))) continue;
      const ef = this.fx(fi++);
      ef.r = this.pool.req(p.key, p.cw, p.ch, 1, p.draw);
      ef.use(!!p.soft);
      ef.mesh.visible = true;
      ef.mesh.position.set(p.x, p.y, p.z);
      if (p.flat) ef.mesh.rotation.set(-Math.PI / 2, 0, p.rot ?? 0);
      else { ef.mesh.quaternion.copy(cam.quaternion); ef.mesh.rotateZ(p.rot ?? 0); }
      ef.mesh.scale.set(p.w, p.h, 1);
      fused.push(ef);
    }
    for (let i = fi; i < this.fxs.length; i++) this.fxs[i].mesh.visible = false;
    this.pool.flush();
    for (const a of used) a.bind();
    for (const ef of fused) ef.bind();
    return focus;
  }
}

/** every lens position of the film looking at its subject: centre, sides and top of frame (houses there are left out) */
function sightLines(): Ray[] {
  const out: Ray[] = [];
  for (const s of SHOTS) for (let f = s.a - 8; f < s.b + 8; f += 2) {
    const c = camAt(s.id, Math.max(0, Math.min(f, s.b - 1))), o = V(...c.pos), look = V(...c.look);
    const fw = look.clone().sub(o), len = fw.length();
    fw.normalize();
    const rt = fw.clone().cross(V(0, 1, 0)).normalize(), up = rt.clone().cross(fw);
    const ty = Math.tan((c.fov * Math.PI) / 360), tx = ty * (9 / 16);
    for (const [sx, sy] of [[0, 0], [-0.6, 0], [0.6, 0], [0, 0.6], [0, -0.4]])
      out.push({ o, d: fw.clone().addScaledVector(rt, sx * tx).addScaledVector(up, sy * ty), len, core: sx === 0 && sy === 0 });
  }
  return out;
}
export { V3 };
