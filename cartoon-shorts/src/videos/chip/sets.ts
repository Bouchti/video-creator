// The chip film's sets (all two-tone lam() geometry, so the world ink outlines them):
//  - CLEANROOM: the lithography bay under yellow light: raised perforated floor, fan-filter ceiling, tool rows with
//    status lamps, an overhead track carrying wafer pods.
//  - Euv: the EUV scanner in the middle of the bay. `cut` hides its near panels (section view): the tin-droplet
//    source, the laser, the collector mirror, the violet light path bouncing mirror to mirror, the mask on top and
//    the wafer stage below.
//  - ChipCity: a phone chip seen from inside: rows of switches (gates over fins) like little buildings, copper
//    wires as skyways on two levels, vias as pillars; every switch has a lamp that can flip.
import * as THREE from "three";
import { mergeGeometries } from "three/examples/jsm/utils/BufferGeometryUtils.js";
import { lam, Batch, boxGeo, V, quad } from "./build";
import { ctex } from "./paint";
import { NOINK } from "./ink";
import { PLASMA, BEAM, WAFER, NOZZLE, EUV, CITY, CR, SQUARE } from "./chippath";
export { PLASMA, BEAM, WAFER, NOZZLE, EUV, CITY, CR };

const TAU = Math.PI * 2;
type XY = [number, number];
const box = (x0: number, x1: number, y0: number, y1: number, z0: number, z1: number) =>
  new THREE.BoxGeometry(x1 - x0, y1 - y0, z1 - z0).translate((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2);
const cylY = (r: number, y0: number, y1: number, x: number, z: number, seg = 24) =>
  new THREE.CylinderGeometry(r, r, y1 - y0, seg).translate(x, (y0 + y1) / 2, z);
const cylZ = (r: number, z0: number, z1: number, x: number, y: number, seg = 24) =>
  new THREE.CylinderGeometry(r, r, z1 - z0, seg).rotateX(Math.PI / 2).translate(x, y, (z0 + z1) / 2);
const cylX = (r: number, x0: number, x1: number, y: number, z: number, seg = 24) =>
  new THREE.CylinderGeometry(r, r, x1 - x0, seg).rotateZ(Math.PI / 2).translate((x0 + x1) / 2, y, z);
const add = (g: THREE.BufferGeometry, m: THREE.Material, parent: THREE.Object3D, cast = true) => {
  const mesh = new THREE.Mesh(g, m); mesh.castShadow = cast; mesh.receiveShadow = true; parent.add(mesh); return mesh;
};
const hdr = (r: number, g: number, b: number) => new THREE.MeshBasicMaterial({ color: new THREE.Color(r, g, b), fog: false });

// ---------------- painted textures ----------------
/** raised cleanroom floor: 0.6 m perforated tiles (one texture = 2 x 2 tiles) */
const floorTex = () => ctex("crFloor", 512, 512, (g) => {
  g.fillStyle = "#d9dde3"; g.fillRect(0, 0, 512, 512);
  for (let ty = 0; ty < 2; ty++) for (let tx = 0; tx < 2; tx++) {
    const x0 = tx * 256, y0 = ty * 256;
    g.fillStyle = (tx + ty) % 2 ? "#dfe3e9" : "#d4d9e0"; g.fillRect(x0 + 6, y0 + 6, 244, 244);
    g.fillStyle = "rgba(90,98,112,0.55)";
    for (let j = 0; j < 9; j++) for (let i = 0; i < 9; i++) { g.beginPath(); g.arc(x0 + 28 + i * 25, y0 + 28 + j * 25, 5, 0, TAU); g.fill(); }
  }
  g.fillStyle = "rgba(60,66,78,0.6)";
  for (const p of [0, 256]) { g.fillRect(p, 0, 6, 512); g.fillRect(0, p, 512, 6); }
});
/** fan-filter ceiling: 1.2 m white filter panels in a dark grid, a soft glowing diffuser in each */
const ceilTex = () => ctex("crCeil", 512, 512, (g) => {
  g.fillStyle = "#5c6270"; g.fillRect(0, 0, 512, 512);
  for (let ty = 0; ty < 2; ty++) for (let tx = 0; tx < 2; tx++) {
    const x0 = tx * 256 + 12, y0 = ty * 256 + 12;
    g.fillStyle = "#f4f2ea"; g.fillRect(x0, y0, 232, 232);
    g.strokeStyle = "rgba(120,124,132,0.45)"; g.lineWidth = 3;
    for (let k = 1; k < 8; k++) { g.beginPath(); g.moveTo(x0 + k * 29, y0 + 8); g.lineTo(x0 + k * 29, y0 + 224); g.stroke(); }
  }
});
const wallTex = () => ctex("crWall", 512, 512, (g) => {
  g.fillStyle = "#eceef2"; g.fillRect(0, 0, 512, 512);
  g.fillStyle = "rgba(90,98,112,0.5)"; g.fillRect(0, 0, 4, 512); g.fillRect(254, 0, 4, 512);
  g.fillStyle = "#c9ced8"; g.fillRect(0, 440, 512, 72);
});
/** the tool front: a dark window, a control strip, a vent grille, a hazard stripe at the base */
const toolTex = (k: number) => ctex("crTool" + k, 512, 512, (g) => {
  g.fillStyle = "#f1f3f6"; g.fillRect(0, 0, 512, 512);
  g.fillStyle = "#3a4250"; g.fillRect(60, 70, 260, 170);              // window
  g.fillStyle = "rgba(150,190,230,0.35)"; g.fillRect(74, 84, 90, 140);
  g.fillStyle = ["#4f8fd8", "#59b36a", "#e8913a", "#9a6ad8"][k % 4]; g.fillRect(360, 80, 100, 24); // brand-free colour band
  g.fillStyle = "#2c313b"; g.fillRect(360, 130, 100, 70);             // screen
  g.fillStyle = "#7fd0ff"; g.fillRect(372, 142, 76, 10); g.fillRect(372, 160, 50, 10); g.fillRect(372, 178, 64, 10);
  g.fillStyle = "#c4cad4"; for (let i = 0; i < 9; i++) g.fillRect(70 + i * 28, 300, 16, 90); // vent
  for (let i = 0; i < 16; i++) { g.fillStyle = i % 2 ? "#2a2d33" : "#f2c230"; g.beginPath(); g.moveTo(i * 36, 512); g.lineTo(i * 36 + 36, 470); g.lineTo(i * 36 + 72, 470); g.lineTo(i * 36 + 36, 512); g.fill(); }
  g.strokeStyle = "rgba(70,78,92,0.6)"; g.lineWidth = 5; g.strokeRect(3, 3, 506, 506);
});
/** the scanner's white skin: panel seams, a few vents and a coloured stripe */
/** the scanner's inside: dark navy service panels with cable trays and small coloured labels-free plates */
const innerTex = () => ctex("euvInnerTex", 512, 512, (g) => {
  g.fillStyle = "#3d5592"; g.fillRect(0, 0, 512, 512);
  g.fillStyle = "#4c67aa"; for (let x = 8; x < 512; x += 128) g.fillRect(x, 8, 112, 496);
  g.fillStyle = "rgba(10,14,30,0.7)"; for (let x = 0; x <= 512; x += 128) g.fillRect(x - 2, 0, 4, 512);
  g.fillStyle = "#e8913a"; g.fillRect(20, 60, 36, 10); g.fillStyle = "#59b36a"; g.fillRect(150, 60, 36, 10); g.fillStyle = "#4fb3e8"; g.fillRect(280, 60, 36, 10);
  g.fillStyle = "#1e2640"; g.fillRect(0, 440, 512, 30);
});
const euvSkin = () => ctex("euvSkin", 1024, 512, (g) => {
  g.fillStyle = "#f3f4f6"; g.fillRect(0, 0, 1024, 512);
  g.fillStyle = "rgba(80,88,104,0.55)";
  for (let x = 0; x <= 1024; x += 256) g.fillRect(x - 3, 0, 6, 512);
  g.fillRect(0, 250, 1024, 5);
  g.fillStyle = "#4f6fd8"; g.fillRect(0, 300, 1024, 26);
  g.fillStyle = "#c9ced8"; for (let x = 40; x < 1024; x += 256) for (let i = 0; i < 6; i++) g.fillRect(x + i * 22, 360, 12, 80);
});
/** the die surface: dark blue-violet silicon with a faint grid */
const dieTex = () => ctex("dieSurf", 512, 512, (g) => {
  g.fillStyle = "#3b4a8a"; g.fillRect(0, 0, 512, 512);
  g.fillStyle = "rgba(160,180,255,0.12)"; for (let k = 0; k < 512; k += 64) { g.fillRect(k, 0, 3, 512); g.fillRect(0, k, 512, 3); }
});

// ---------------- the cleanroom ----------------
export class Cleanroom {
  root = new THREE.Group();
  near = new THREE.Group(); // the front wall (never in a lens; hidden anyway)
  private foups: THREE.Mesh[] = [];
  private lamps: { m: THREE.MeshBasicMaterial; base: THREE.Color; ph: number }[] = [];
  constructor(parent: THREE.Object3D) {
    parent.add(this.root);
    const b = new Batch(), C = CR;
    const rw = (t: THREE.Texture) => { t.wrapS = t.wrapT = THREE.RepeatWrapping; return t; };
    const fl = lam("crFloor", () => ({ map: rw(floorTex()) })), ce = lam("crCeil", () => ({ map: rw(ceilTex()), side: THREE.DoubleSide }));
    const wl = lam("crWall", () => ({ map: rw(wallTex()) }));
    // floor + ceiling quads with uv in metres / 1.2
    const up = (x0: number, x1: number, z0: number, z1: number, y: number, s: number, down = false) => {
      const g = new THREE.BufferGeometry(), U = (v: number) => v / s;
      const P = down ? [x0, y, z0, x1, y, z0, x1, y, z1, x0, y, z0, x1, y, z1, x0, y, z1] : [x0, y, z1, x1, y, z1, x1, y, z0, x0, y, z1, x1, y, z0, x0, y, z0];
      g.setAttribute("position", new THREE.Float32BufferAttribute(P, 3));
      const uv: number[] = []; for (let i = 0; i < 6; i++) uv.push(U(P[i * 3]), U(P[i * 3 + 2]));
      g.setAttribute("uv", new THREE.Float32BufferAttribute(uv, 2)); g.computeVertexNormals(); return g;
    };
    b.add(up(C.x0, C.x1, C.z0, C.z1 + 6, 0, 1.2), fl);
    b.add(up(C.x0, C.x1, C.z0, C.z1, C.h, 2.4, true), ce);
    b.add(quad(V(C.x0, 0, C.z0), V(C.x1, 0, C.z0), V(C.x1, C.h, C.z0), V(C.x0, C.h, C.z0), (C.x1 - C.x0) / 2.4, C.h / 2.4), wl);
    b.add(quad(V(C.x0, 0, C.z1), V(C.x0, 0, C.z0), V(C.x0, C.h, C.z0), V(C.x0, C.h, C.z1), (C.z1 - C.z0) / 2.4, C.h / 2.4), wl);
    b.add(quad(V(C.x1, 0, C.z0), V(C.x1, 0, C.z1), V(C.x1, C.h, C.z1), V(C.x1, C.h, C.z0), (C.z1 - C.z0) / 2.4, C.h / 2.4), wl);
    // tool rows along the back wall and the left/right walls (front faces painted), each with a lamp tower
    const base = lam("crToolBase", () => ({ color: "#5d6678" }));
    const lampCols = [new THREE.Color(0.4, 2.6, 0.6), new THREE.Color(2.8, 1.8, 0.2), new THREE.Color(0.4, 1.4, 3.0)];
    const tool = (x: number, z: number, w: number, d: number, hgt: number, yaw: number, k: number) => {
      const g = new THREE.Group(); g.position.set(x, 0, z); g.rotation.y = yaw; this.root.add(g);
      add(box(-w / 2, w / 2, 0, 0.18, -d / 2, d / 2), base, g);
      const skin = lam("crToolSkin" + (k % 4), () => ({ map: toolTex(k % 4) }));
      const side = lam("crToolSide", () => ({ color: "#c9d2e0" }));
      const m = add(box(-w / 2, w / 2, 0.18, hgt, -d / 2, d / 2), side, g);
      add(quad(V(-w / 2, 0.18, d / 2 + 0.002), V(w / 2, 0.18, d / 2 + 0.002), V(w / 2, hgt, d / 2 + 0.002), V(-w / 2, hgt, d / 2 + 0.002)), skin, g);
      void m;
      add(box(-w / 2 + 0.15, -w / 2 + 0.75, 0.8, 0.86, d / 2, d / 2 + 0.35), base, g); // load port shelf
      const strip = new THREE.Mesh(box(-w / 2, w / 2, hgt - 0.12, hgt - 0.06, d / 2, d / 2 + 0.01), new THREE.MeshBasicMaterial({ color: k % 2 ? new THREE.Color(2.6, 0.4, 1.9) : new THREE.Color(0.3, 2.0, 2.6) }));
      strip.layers.set(NOINK); g.add(strip);
      add(cylY(0.03, hgt, hgt + 0.5, w / 2 - 0.2, -d / 2 + 0.2, 8), base, g, false);
      for (let i = 0; i < 3; i++) {
        const mm = hdr(0, 0, 0); this.lamps.push({ m: mm, base: lampCols[i], ph: k * 1.7 + i });
        const s = new THREE.Mesh(new THREE.CylinderGeometry(0.07, 0.07, 0.12, 14), mm);
        s.position.set(w / 2 - 0.2, hgt + 0.18 + i * 0.13, -d / 2 + 0.2); s.layers.set(NOINK); g.add(s);
      }
    };
    let k = 0;
    for (let x = -12.6; x <= 12.6; x += 3.15) tool(x, C.z0 + 1.0, 2.5, 1.7, 2.4 + 0.25 * (k % 3), 0, k++);
    for (let z = -6.2; z <= 5.8; z += 3.0) { tool(C.x0 + 1.0, z, 2.4, 1.6, 2.3, Math.PI / 2, k++); tool(C.x1 - 1.0, z, 2.4, 1.6, 2.3, -Math.PI / 2, k++); }
    const led = new THREE.MeshBasicMaterial({ color: new THREE.Color(0.3, 2.2, 2.6) });
    for (const [a, b2, c, d] of [[C.x0, C.x1, C.z0 + 0.03, C.z0 + 0.06], [C.x0 + 0.03, C.x0 + 0.06, C.z0, C.z1], [C.x1 - 0.06, C.x1 - 0.03, C.z0, C.z1]] as [number, number, number, number][]) {
      const m = new THREE.Mesh(box(a, b2, 3.05, 3.12, c, d), led); m.layers.set(NOINK); this.root.add(m);
    }
    // overhead track + its hangers
    const rail = lam("crRail", () => ({ color: "#9aa2b0" }));
    for (const z of [-5.6, 4.4]) {
      b.add(box(C.x0, C.x1, 4.05, 4.15, z - 0.09, z + 0.09), rail);
      for (let x = -13; x <= 13; x += 2.6) b.add(box(x - 0.03, x + 0.03, 4.15, C.h, z - 0.03, z + 0.03), rail);
    }
    const foup = lam("crFoup", () => ({ color: "#e8eaee" })), foupTop = lam("crFoupTop", () => ({ color: "#4f6fd8" }));
    const fg = mergeGeometries([box(-0.22, 0.22, -0.22, 0.2, -0.2, 0.2), box(-0.06, 0.06, 0.2, 0.45, -0.02, 0.02)].map((x) => x.toNonIndexed()));
    for (let i = 0; i < 10; i++) {
      const m = new THREE.Mesh(fg, i % 3 ? foup : foupTop); m.castShadow = true; this.root.add(m); this.foups.push(m);
    }
    b.build(this.root, false);
  }
  update(t: number) {
    this.foups.forEach((m, i) => {
      const z = i % 2 ? -5.6 : 4.4, L = 30, x = ((((i * 6.1 + t * 0.9 * (i % 2 ? 1 : -1)) % L) + L) % L) - 15;
      m.position.set(x, 3.6, z);
    });
    for (const l of this.lamps) { const on = Math.sin(l.ph * 3.1) > -0.2 ? 1 : 0.08; l.m.color.copy(l.base).multiplyScalar(on); }
  }
}

// ---------------- the EUV scanner ----------------
export type EuvState = { cut: boolean; beam: number; drops: { y: number; flat: number; flash: number }[]; laser: number; flow: number };

const ribbon = (pts: XY[], r: number) => {
  const curve = new THREE.CurvePath<THREE.Vector3>();
  for (let i = 0; i + 1 < pts.length; i++) curve.add(new THREE.LineCurve3(V(pts[i][0], pts[i][1], 0), V(pts[i + 1][0], pts[i + 1][1], 0)));
  return new THREE.TubeGeometry(curve as unknown as THREE.Curve<THREE.Vector3>, 240, r, 10, false);
};
const beamTex = () => ctex("beamFlow", 256, 32, (g) => {
  const gr = g.createLinearGradient(0, 0, 256, 0);
  gr.addColorStop(0, "rgba(255,255,255,0.55)"); gr.addColorStop(0.5, "rgba(255,255,255,1)"); gr.addColorStop(1, "rgba(255,255,255,0.55)");
  g.fillStyle = gr; g.fillRect(0, 0, 256, 32);
});

export class Euv {
  root = new THREE.Group();
  near = new THREE.Group();
  private beam: THREE.Mesh; private beamMat: THREE.MeshBasicMaterial; private beamLen: number;
  private laser: THREE.Mesh; private laserMat: THREE.MeshBasicMaterial;
  private drops: THREE.Mesh[] = []; private flashes: THREE.Mesh[] = []; private halos: THREE.Sprite[] = []; private rays: THREE.Sprite[] = [];
  private stage: THREE.Group; private reticle: THREE.Group;
  constructor(parent: THREE.Object3D) {
    parent.add(this.root); this.root.add(this.near);
    const E = EUV;
    const skin = lam("euvSkin", () => ({ map: euvSkin() })), white = lam("euvWhite", () => ({ color: "#eef0f3" }));
    const inner = lam("euvInner", () => ({ map: innerTex() })), dark = lam("euvDark", () => ({ color: "#4a5262" }));
    const steel = lam("euvSteel", () => ({ color: "#c9d0dc" })), plinth = lam("euvPlinth", () => ({ color: "#5d6574" }));
    const mirror = lam("euvMirror", () => ({ color: "#d8b45a" })), mirrorBack = lam("euvMirrorBack", () => ({ color: "#6a5a8a" }));
    // ---- shells: main body + source module; back wall, floor and roof stay, front (z+) is the near group ----
    const shell = (x0: number, x1: number, y1: number, nearOnly = false, openX0 = false, openX1 = false) => {
      if (!nearOnly) {
        add(box(x0, x1, 0, 0.22, -E.z, E.z), plinth, this.root);
        add(box(x0, x1, 0.22, y1, -E.z - 0.06, -E.z), skin, this.root);          // back wall
        add(box(x0, x1, y1 - 0.06, y1, -E.z, E.z), white, this.root, false);       // roof
        if (!openX0) add(box(x0, x0 + 0.06, 0.22, y1, -E.z, E.z), white, this.root);           // end walls
        if (!openX1) add(box(x1 - 0.06, x1, 0.22, y1, -E.z, E.z), white, this.root);
        add(box(x0 + 0.06, x1 - 0.06, 0.22, 0.26, -E.z, E.z), inner, this.root);   // interior floor
        add(quad(V(x0 + 0.06, 0.26, -E.z + 0.001), V(x1 - 0.06, 0.26, -E.z + 0.001), V(x1 - 0.06, y1 - 0.06, -E.z + 0.001), V(x0 + 0.06, y1 - 0.06, -E.z + 0.001)), inner, this.root);
      }
      add(box(x0, x1, 0.22, y1, E.z, E.z + 0.06), skin, this.near);              // the near wall (hidden in cutaway)
    };
    shell(E.x0, E.x1, E.y1, false, true, false);
    shell(E.sx0, E.sx1, E.sy1, false, false, true);
    // top module over the mask stage + a vacuum pump stack on the roof + service cabinets behind
    add(box(-0.7, 1.1, E.y1, E.y1 + 0.55, -1.0, 1.0), white, this.root);
    for (const x of [-3.4, -2.2]) { add(cylY(0.22, E.y1, E.y1 + 0.5, x, -0.6, 20), steel, this.root); add(cylY(0.26, E.y1 + 0.5, E.y1 + 0.62, x, -0.6, 20), dark, this.root); }
    add(box(E.sx0 + 0.2, E.sx1 - 0.2, 0, 2.2, -E.z - 2.0, -E.z - 0.3), white, this.root); // laser cabinet behind the source
    // ---- outside dress so it reads as a machine: stepped top modules, a lamp tower, portholes, pipes, a control desk ----
    const blueM = lam("euvBlue", () => ({ color: "#4f6fd8" })), orange = lam("euvOrange", () => ({ color: "#f08a2c" }));
    add(box(-3.9, -1.1, E.y1, E.y1 + 0.45, -1.2, 1.2), white, this.root);
    add(box(1.4, 3.4, E.y1, E.y1 + 0.75, -1.3, 1.3), white, this.root);
    add(box(1.4, 3.4, E.y1 + 0.55, E.y1 + 0.68, -1.31, 1.31), blueM, this.root);
    add(box(E.sx0 + 0.3, E.sx1 - 0.3, E.sy1, E.sy1 + 0.4, -1.0, 1.0), white, this.root);
    add(cylY(0.05, E.y1 + 0.75, E.y1 + 1.0, 3.1, 1.0, 8), steel, this.root, false);
    const lampCol = [new THREE.Color(0.4, 2.6, 0.6), new THREE.Color(2.8, 1.8, 0.2), new THREE.Color(2.8, 0.4, 0.3)];
    lampCol.forEach((c, i) => { const m = new THREE.Mesh(new THREE.CylinderGeometry(0.09, 0.09, 0.14, 16), hdr(c.r, c.g, c.b)); m.position.set(3.1, E.y1 + 1.08 + i * 0.15, 1.0); m.layers.set(NOINK); this.root.add(m); });
    for (const x of [-3.0, -0.6, 1.9]) {
      const ring = new THREE.Mesh(new THREE.CylinderGeometry(0.36, 0.36, 0.08, 36).rotateX(Math.PI / 2), steel); ring.position.set(x, 1.95, E.z + 0.1); this.near.add(ring);
      const gl = new THREE.Mesh(new THREE.CylinderGeometry(0.28, 0.28, 0.09, 36).rotateX(Math.PI / 2), lam("euvPort", () => ({ color: "#2f3a6a" }))); gl.position.set(x, 1.95, E.z + 0.11); this.near.add(gl);
      const glow = new THREE.Mesh(new THREE.CircleGeometry(0.16, 24), hdr(1.4, 0.6, 2.6)); glow.position.set(x - 0.05, 1.98, E.z + 0.162); glow.layers.set(NOINK); this.near.add(glow);
    }
    add(new THREE.CylinderGeometry(0.08, 0.08, E.x1 - E.sx0, 16).rotateZ(Math.PI / 2).translate((E.x1 + E.sx0) / 2, 0.55, E.z + 0.14), orange, this.near);
    add(new THREE.CylinderGeometry(0.06, 0.06, E.x1 - E.x0, 16).rotateZ(Math.PI / 2).translate((E.x1 + E.x0) / 2, 0.75, E.z + 0.14), steel, this.near);
    for (const x of [-3.6, -1.8, 0.6, 2.6]) add(cylY(0.06, 0.75, E.y1, x, E.z + 0.14, 12), steel, this.near);
    add(box(2.6, 3.5, 0.22, 1.25, E.z + 0.06, E.z + 0.45), lam("euvDesk", () => ({ color: "#5d6574" })), this.near);
    const scr = new THREE.Mesh(new THREE.PlaneGeometry(0.7, 0.4), hdr(0.5, 1.4, 2.4)); scr.position.set(3.05, 1.0, E.z + 0.452); scr.layers.set(NOINK); this.near.add(scr);
    // ---- inside the source: droplet generator, catcher, collector mirror (concave dish with a hole), laser port ----
    add(cylY(0.09, NOZZLE[1], E.sy1 - 0.06, NOZZLE[0], 0, 16), steel, this.root);
    add(new THREE.ConeGeometry(0.09, 0.16, 16).rotateX(Math.PI).translate(NOZZLE[0], NOZZLE[1] - 0.08, 0), dark, this.root);
    add(cylY(0.12, 0.26, 0.5, NOZZLE[0], 0, 16), dark, this.root); // the catcher at the bottom
    {
      const pts: THREE.Vector2[] = [];
      for (let i = 0; i <= 16; i++) { const r = 0.12 + (0.62 - 0.12) * (i / 16); pts.push(new THREE.Vector2(r, 0.18 * (r / 0.62) ** 2)); }
      const dish = new THREE.LatheGeometry(pts, 48).rotateZ(-Math.PI / 2).translate(PLASMA[0] - 0.75, PLASMA[1], 0);
      add(dish, new THREE.MeshLambertMaterial({ color: "#d8b45a", side: THREE.DoubleSide }), this.root);
      add(cylX(0.66, PLASMA[0] - 0.95, PLASMA[0] - 0.85, PLASMA[1], 0, 48), mirrorBack, this.root);
    }
    add(cylX(0.1, E.sx0, E.sx0 + 0.25, PLASMA[1], 0, 16), dark, this.root); // laser port
    // ---- mirrors along the path (each a tilted disc facing the bisector of its two legs) ----
    for (let i = 2; i < BEAM.length - 1; i++) {
      if (i === 5) continue; // the mask
      const [ax, ay] = BEAM[i - 1], [px, py] = BEAM[i], [bx, by] = BEAM[i + 1];
      const a = Math.atan2(ay - py, ax - px), c = Math.atan2(by - py, bx - px);
      let n = (a + c) / 2; if (Math.abs(a - c) > Math.PI) n += Math.PI;
      const g = new THREE.Group(); g.position.set(px - Math.cos(n) * 0.05, py - Math.sin(n) * 0.05, 0); g.rotation.z = n - Math.PI / 2;
      add(new THREE.CylinderGeometry(0.26, 0.26, 0.07, 32), mirror, g);
      add(new THREE.CylinderGeometry(0.28, 0.28, 0.06, 32).translate(0, -0.06, 0), mirrorBack, g);
      add(box(-0.05, 0.05, -0.5, -0.08, -0.05, 0.05), steel, g);
      const glint = new THREE.Mesh(new THREE.CircleGeometry(0.06, 16).rotateX(-Math.PI / 2).translate(-0.1, 0.04, 0.08), hdr(3, 3, 3)); glint.layers.set(NOINK); g.add(glint);
      g.traverse((o) => { o.castShadow = false; });
      this.root.add(g);
    }
    // ---- mask (reticle) stage on top, wafer stage below ----
    this.reticle = new THREE.Group(); this.root.add(this.reticle);
    add(box(-0.55, 0.95, 2.92, 3.0, -0.4, 0.4), lam("euvReticle", () => ({ color: "#2f3a6a" })), this.reticle);
    add(box(-0.7, 1.1, 3.0, 3.12, -0.5, 0.5), steel, this.reticle);
    this.stage = new THREE.Group(); this.root.add(this.stage);
    add(box(-0.5, 0.5, 0.26, 0.82, -0.5, 0.5), dark, this.stage);
    add(new THREE.CylinderGeometry(0.34, 0.34, 0.03, 48).translate(0, 0.86, 0), lam("euvWafer", () => ({ color: "#6f7fd0" })), this.stage);
    add(box(WAFER[0] - 1.3, WAFER[0] + 1.3, 0.26, 0.36, -0.9, 0.9), steel, this.root);
    // ---- the light: violet ribbon along the path (NOINK, HDR), the infrared laser (pink), drops + plasma flashes ----
    const bg = ribbon(BEAM, 0.085);
    const tube = new THREE.Mesh(ribbon(BEAM.slice(1), 0.24), new THREE.MeshBasicMaterial({ color: new THREE.Color(0.6, 0.75, 1.0), transparent: true, opacity: 0.13, depthWrite: false, side: THREE.DoubleSide }));
    tube.layers.set(NOINK); this.root.add(tube);
    const hiPts: XY[] = BEAM.slice(1).map(([x, y]) => [x, y + 0.2]);
    const hl = new THREE.Mesh(ribbon(hiPts, 0.012), new THREE.MeshBasicMaterial({ color: new THREE.Color(1.8, 2.0, 2.4), transparent: true, opacity: 0.8, depthWrite: false }));
    hl.position.z = 0.1; hl.layers.set(NOINK); this.root.add(hl);
    this.beamLen = BEAM.slice(1).reduce((s, p, i) => s + Math.hypot(p[0] - BEAM[i][0], p[1] - BEAM[i][1]), 0);
    this.beamMat = new THREE.MeshBasicMaterial({ color: new THREE.Color(2.2, 0.9, 4.2), transparent: true, opacity: 0.9, depthWrite: false, fog: false, map: beamTex(), blending: THREE.AdditiveBlending });
    this.beamMat.map!.wrapS = THREE.RepeatWrapping; this.beamMat.map!.repeat.set(6, 1);
    this.beam = new THREE.Mesh(bg, this.beamMat); this.beam.layers.set(NOINK); this.root.add(this.beam);
    this.laserMat = new THREE.MeshBasicMaterial({ color: new THREE.Color(4.0, 0.6, 1.2), transparent: true, depthWrite: false, fog: false, blending: THREE.AdditiveBlending });
    this.laser = new THREE.Mesh(cylX(0.03, E.sx0 + 0.2, PLASMA[0], PLASMA[1], 0, 12), this.laserMat); this.laser.layers.set(NOINK); this.root.add(this.laser);
    const tin = new THREE.MeshBasicMaterial({ color: new THREE.Color(1.6, 1.65, 1.8), fog: false });
    for (let i = 0; i < 10; i++) {
      const d = new THREE.Mesh(new THREE.SphereGeometry(0.05, 20, 14), tin); d.castShadow = false; d.layers.set(NOINK); this.root.add(d); this.drops.push(d);
      const f = new THREE.Mesh(new THREE.SphereGeometry(0.1, 24, 16), hdr(9, 6, 14)); f.layers.set(NOINK); this.root.add(f); this.flashes.push(f);
      const hs = new THREE.Sprite(new THREE.SpriteMaterial({ map: haloTex(), color: new THREE.Color(1.6, 0.9, 2.4), transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, fog: false }));
      hs.layers.set(NOINK); this.root.add(hs); this.halos.push(hs);
      const rs = new THREE.Sprite(new THREE.SpriteMaterial({ map: raysTex(), color: new THREE.Color(2.6, 2.0, 3.2), transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, fog: false }));
      rs.layers.set(NOINK); this.root.add(rs); this.rays.push(rs);
    }
  }
  update(t: number, s: EuvState) {
    this.near.visible = !s.cut;
    // beam reveal: draw range grows along the tube (index-free geometry: drawRange over triangles)
    const g = this.beam.geometry as THREE.BufferGeometry, total = g.index ? g.index.count : g.attributes.position.count;
    const k = Math.max(0, Math.min(1, s.beam));
    g.setDrawRange(0, Math.floor(total * k / 60) * 60);
    this.beam.visible = k > 0.001;
    this.beamMat.map!.offset.x = -s.flow;
    this.laser.visible = s.laser > 0.01; this.laserMat.opacity = Math.min(1, s.laser);
    this.drops.forEach((d, i) => {
      const st = s.drops[i];
      d.visible = !!st && st.flash < 0.35;
      if (!st) { this.flashes[i].visible = false; this.halos[i].visible = false; this.rays[i].visible = false; return; }
      d.position.set(PLASMA[0], st.y, 0);
      const fall = st.flat === 0 && st.y > PLASMA[1] + 0.01 ? 1 : 0;
      d.scale.set(1 + 1.6 * st.flat, (1 - 0.65 * st.flat) * (1 + 0.9 * fall), 1 + 1.6 * st.flat);
      const fk = st.flash, f = this.flashes[i], h = this.halos[i];
      f.visible = h.visible = fk > 0.01;
      f.position.set(PLASMA[0], st.y, 0); f.scale.setScalar(0.4 + 1.8 * fk);
      h.position.copy(f.position); h.scale.setScalar(0.3 + 1.5 * fk); (h.material as THREE.SpriteMaterial).opacity = Math.min(1, fk * 1.4);
      const r = this.rays[i], big = s.drops.length === 1 ? 1 : 0.35; r.visible = fk > 0.05; r.position.copy(f.position);
      r.scale.setScalar((0.4 + 2.0 * fk) * big); (r.material as THREE.SpriteMaterial).opacity = Math.min(1, fk * 1.2); (r.material as THREE.SpriteMaterial).rotation = t * 0.6;
    });
    // stages scan back and forth
    this.stage.position.set(WAFER[0] + 0.25 * Math.sin(t * 1.3), 0, 0.2 * Math.sin(t * 0.7));
    this.reticle.position.set(0.25 * Math.sin(t * 1.3) * 4 / 4, 0, 0);
  }
}
const raysTex = () => ctex("euvRays", 512, 512, (g) => {
  g.translate(256, 256);
  for (let k = 0; k < 14; k++) {
    g.save(); g.rotate((k / 14) * Math.PI * 2 + (k % 2) * 0.1);
    const L = k % 2 ? 150 : 240, gr = g.createLinearGradient(0, 0, L, 0); gr.addColorStop(0, "rgba(255,255,255,0.95)"); gr.addColorStop(1, "rgba(255,255,255,0)");
    g.fillStyle = gr; g.beginPath(); g.moveTo(0, -9); g.lineTo(L, 0); g.lineTo(0, 9); g.fill(); g.restore();
  }
  g.strokeStyle = "rgba(255,255,255,0.5)"; g.lineWidth = 6; g.beginPath(); g.arc(0, 0, 120, 0, Math.PI * 2); g.stroke();
});
const haloTex = () => ctex("euvHalo", 256, 256, (g) => {
  const im = g.createImageData(256, 256);
  for (let y = 0; y < 256; y++) for (let x = 0; x < 256; x++) {
    const u = Math.hypot(x - 127.5, y - 127.5) / 128, a = Math.max(0, 0.75 * Math.exp(-((u / 0.3) ** 2)) + 0.25 * Math.exp(-((u / 0.7) ** 2)) - 0.02);
    const i = (y * 256 + x) * 4; im.data[i] = im.data[i + 1] = im.data[i + 2] = 255; im.data[i + 3] = Math.round(255 * Math.min(1, a));
  }
  g.putImageData(im, 0, 0);
});

// ---------------- the chip from inside ----------------
export class ChipCity {
  root = new THREE.Group();
  private lampMat: THREE.MeshBasicMaterial; private lamps: THREE.InstancedMesh; private roofs!: THREE.InstancedMesh; private n: number; private idx: [number, number][] = [];
  private col = new THREE.Color();
  constructor(parent: THREE.Object3D) {
    parent.add(this.root); this.root.position.set(CITY.x, 0, CITY.z);
    const C = CITY, W = C.nx * C.px, D = C.nz * C.pz;
    const die = dieTex(); die.wrapS = die.wrapT = THREE.RepeatWrapping; die.repeat.set(W / 8, D / 8);
    add(new THREE.PlaneGeometry(W + 400, D + 400).rotateX(-Math.PI / 2), lam("dieSurf", () => ({ map: die })), this.root, false);
    const finM = lam("cityFin", () => ({ color: "#7d8ec8" })), gateM = lam("cityGate", () => ({ color: "#e9e4dc" })), capM = lam("cityGateCap", () => ({ color: "#c4bdb2" }));
    const cuM = lam("cityCopper", () => ({ color: "#e08a4a" })), cu2 = lam("cityCopper2", () => ({ color: "#c96f36" })), viaM = lam("cityVia", () => ({ color: "#b8a27a" }));
    // fins: long ridges along x in each row; gates: blocks across each fin row
    const m4 = new THREE.Matrix4();
    const inst = (g: THREE.BufferGeometry, m: THREE.Material, list: [number, number, number, number, number, number][]) => {
      const im = new THREE.InstancedMesh(g, m, list.length);
      list.forEach(([x, y, z, sx, sy, sz], i) => { m4.makeScale(sx, sy, sz).setPosition(x, y, z); im.setMatrixAt(i, m4); });
      im.castShadow = true; im.receiveShadow = true; this.root.add(im); return im;
    };
    const unit = new THREE.BoxGeometry(1, 1, 1).translate(0, 0.5, 0);
    const fins: [number, number, number, number, number, number][] = [], gates: typeof fins = [], caps: typeof fins = [];
    const x0 = -W / 2, z0 = -D / 2;
    for (let j = 0; j < C.nz; j++) {
      const z = z0 + (j + 0.5) * C.pz;
      fins.push([0, 0, z - 1.0, W, 0.5, 0.45], [0, 0, z + 1.0, W, 0.5, 0.45]);
      for (let i = 0; i < C.nx; i++) {
        if (i >= SQUARE.i0 && i < SQUARE.i1 && j >= SQUARE.j0 && j < SQUARE.j1) continue;
        const x = x0 + (i + 0.5) * C.px, hgt = 3.0 + 0.6 * ((i * 7 + j * 3) % 3);
        gates.push([x, 0, z, 1.2, hgt, 2.8]);
        caps.push([x, hgt, z, 1.36, 0.2, 3.0]);
      }
    }
    inst(unit, finM, fins); inst(unit, gateM, gates); inst(unit, capM, caps);
    // the switch lamps on every gate top (instanced, colour per instance: on = warm white HDR, off = dim)
    this.n = gates.length;
    this.lampMat = new THREE.MeshBasicMaterial({ color: "#ffffff", fog: true });
    // one lamp = a window on the front face + a glowing roof plate (two meshes, the same colour per switch)
    const lampGeo = mergeGeometries([new THREE.BoxGeometry(0.7, 0.55, 0.04).translate(0, 0, 0), new THREE.BoxGeometry(0.9, 0.05, 2.2).translate(0, 0, 0)].map((g) => g.toNonIndexed()));
    void lampGeo;
    this.lamps = new THREE.InstancedMesh(new THREE.BoxGeometry(0.7, 0.55, 0.04), this.lampMat, this.n);
    this.roofs = new THREE.InstancedMesh(new THREE.BoxGeometry(1.3, 0.06, 2.95), this.lampMat, this.n);
    gates.forEach(([x, , z, , hgt], i) => {
      m4.makeTranslation(x, hgt * 0.68, z + 1.42); this.lamps.setMatrixAt(i, m4);
      m4.makeTranslation(x, hgt + 0.22, z); this.roofs.setMatrixAt(i, m4);
      this.lamps.setColorAt(i, this.col.setRGB(0.2, 0.25, 0.45)); this.roofs.setColorAt(i, this.col);
    });
    this.lamps.layers.set(NOINK); this.roofs.layers.set(NOINK); this.root.add(this.lamps, this.roofs);
    this.idx = gates.map(([x, , z]) => [Math.round((x - x0) / C.px - 0.5), Math.round((z - z0) / C.pz - 0.5)] as [number, number]);
    // copper skyways: level 1 along z every 2 columns at 4.2 m, level 2 along x every row at 6.0 m; vias down to gates
    const w1: typeof fins = [], w2: typeof fins = [], vias: typeof fins = [];
    for (let i = 1; i < C.nx; i += 4) w1.push([x0 + (i + 0.5) * C.px, 5.6, 0, 0.7, 0.4, D]);
    for (let j = 0; j < C.nz; j += 3) w2.push([0, 7.2, z0 + (j + 0.5) * C.pz - 0.2, W, 0.45, 0.8]);
    for (let i = 1; i < C.nx; i += 4) for (let j = 0; j < C.nz; j += 2) {
      const x = x0 + (i + 0.5) * C.px, z = z0 + (j + 0.5) * C.pz, hgt = 3.0 + 0.6 * ((i * 7 + j * 3) % 3);
      vias.push([x, hgt + 0.2, z, 0.3, 5.6 - hgt - 0.2, 0.3]);
      if (j % 3 === 0) vias.push([x, 6.0, z - 0.2, 0.3, 1.2, 0.3]);
    }
    inst(unit, cuM, w1); inst(unit, cu2, w2); inst(unit, viaM, vias);
  }
  /** cell centre in world space (column i, row j) */
  cell(i: number, j: number): [number, number, number] {
    const C = CITY; return [C.x - (C.nx * C.px) / 2 + (i + 0.5) * C.px, 0, C.z - (C.nz * C.pz) / 2 + (j + 0.5) * C.pz];
  }
  /** flip = 0..1 wave of switches turning on from the centre outward; base pattern flickers */
  update(t: number, flip: number) {
    const C = CITY;
    for (let idx = 0; idx < this.n; idx++) {
      const [i, j] = this.idx[idx], r = Math.hypot(i - C.nx / 2, (j - C.nz / 2) * 2.6) / (C.nx * 0.7);
      const ph = Math.abs(Math.sin(i * 91.7 + j * 47.3)) * 9.0, base = Math.sin(i * 12.9898 + j * 78.233 + Math.floor(t * 2.2 + ph) * 1.7) > 0.3;
      const on = flip > 0 ? r < flip * 1.2 && Math.sin(i * 3.1 + j * 5.7 + t * 9) > -0.75 : flip < 0 ? false : base;
      if (on) this.col.setRGB(2.6, 1.5, 0.3); else this.col.setRGB(0.1, 0.13, 0.3);
      this.lamps.setColorAt(idx, this.col); this.roofs.setColorAt(idx, this.col);
    }
    this.lamps.instanceColor!.needsUpdate = true; this.roofs.instanceColor!.needsUpdate = true;
  }
}
export { boxGeo };
