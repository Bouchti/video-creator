// The chip film's other sets (two-tone lam() geometry, outlined by the world ink):
//  Lab (1947 Bell Labs room + the big transistor prop), Kitchen (1948 breakfast, the radio column), Street (a town
//  street for the phone shots and the one-company factory), Beach (sand + the silicon atom lattice), Puller (the
//  crystal puller, the wire saw, wafers), Stencil (light through a mask onto a wafer, layers stacking),
//  MirrorLand (a mirror the shape of Germany lying in the countryside, a tiny bump), Jets (three cargo jumbo jets).
import * as THREE from "three";
import { mergeGeometries } from "three/examples/jsm/utils/BufferGeometryUtils.js";
import { lam, Batch, V, quad, house, prop, Kit } from "./build";
import { ctex, planksHD, grassHD, cloudHD, facadeHD } from "./paint";
import { NOINK } from "./ink";
import { LAB, KITCHEN, STREET, BEACH, PULLER, STENCIL, MIRROR, SKY, GERMANY, BUMP } from "./chippath";

const TAU = Math.PI * 2;
const box = (x0: number, x1: number, y0: number, y1: number, z0: number, z1: number) =>
  new THREE.BoxGeometry(x1 - x0, y1 - y0, z1 - z0).translate((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2);
const cylY = (r: number, y0: number, y1: number, x: number, z: number, seg = 24, r2 = r) =>
  new THREE.CylinderGeometry(r2, r, y1 - y0, seg).translate(x, (y0 + y1) / 2, z);
const add = (g: THREE.BufferGeometry, m: THREE.Material, parent: THREE.Object3D, cast = true) => {
  const mesh = new THREE.Mesh(g, m); mesh.castShadow = cast; mesh.receiveShadow = true; parent.add(mesh); return mesh;
};
const hdr = (r: number, g: number, b: number) => new THREE.MeshBasicMaterial({ color: new THREE.Color(r, g, b), fog: false });
const rw = (t: THREE.Texture) => { t.wrapS = t.wrapT = THREE.RepeatWrapping; return t; };
/** floor quad facing up, uv in metres / s */
const floorQ = (x0: number, x1: number, z0: number, z1: number, y: number, s: number) => {
  const g = new THREE.BufferGeometry(), P = [x0, y, z1, x1, y, z1, x1, y, z0, x0, y, z1, x1, y, z0, x0, y, z0];
  g.setAttribute("position", new THREE.Float32BufferAttribute(P, 3));
  const uv: number[] = []; for (let i = 0; i < 6; i++) uv.push(P[i * 3] / s, P[i * 3 + 2] / s);
  g.setAttribute("uv", new THREE.Float32BufferAttribute(uv, 2)); g.computeVertexNormals(); return g;
};
/** an open-fronted room: floor, back + side walls (painted), optional ceiling; returns the batch to add furniture to */
const room = (parent: THREE.Object3D, cx: number, cz: number, w: number, d: number, h: number, floor: THREE.Material, wall: THREE.Material, ceil?: THREE.Material) => {
  const b = new Batch(), x0 = cx - w / 2, x1 = cx + w / 2, z0 = cz - d / 2, z1 = cz + d / 2;
  b.add(floorQ(x0, x1, z0, z1, 0, 2), floor);
  b.add(quad(V(x0, 0, z0), V(x1, 0, z0), V(x1, h, z0), V(x0, h, z0), w / 2.5, h / 2.5), wall);
  b.add(quad(V(x0, 0, z1), V(x0, 0, z0), V(x0, h, z0), V(x0, h, z1), d / 2.5, h / 2.5), wall);
  b.add(quad(V(x1, 0, z0), V(x1, 0, z1), V(x1, h, z1), V(x1, h, z0), d / 2.5, h / 2.5), wall);
  if (ceil) b.add(quad(V(x0, h, z0), V(x1, h, z0), V(x1, h, z1), V(x0, h, z1), w / 3, d / 3), ceil);
  b.build(parent, false);
};

// ---------------- painted textures ----------------
const labWall = () => ctex("labWall", 512, 512, (g) => {
  g.fillStyle = "#cfdcc4"; g.fillRect(0, 0, 512, 512);
  g.fillStyle = "#8fa889"; g.fillRect(0, 300, 512, 212);
  g.fillStyle = "#6e8a6a"; g.fillRect(0, 296, 512, 10);
});
const blackboard = () => ctex("blackboard", 1024, 512, (g) => {
  g.fillStyle = "#2f4a3c"; g.fillRect(0, 0, 1024, 512);
  g.strokeStyle = "rgba(240,240,225,0.85)"; g.lineWidth = 6; g.lineCap = "round";
  // a circuit sketch: battery, wavy input, a triangle (the amplifier), an arrow; plus a sine growing bigger
  g.beginPath(); g.moveTo(80, 300); g.lineTo(220, 300); g.moveTo(220, 260); g.lineTo(220, 340); g.moveTo(245, 280); g.lineTo(245, 320); g.moveTo(245, 300); g.lineTo(360, 300); g.stroke();
  g.beginPath(); g.moveTo(360, 230); g.lineTo(480, 300); g.lineTo(360, 370); g.closePath(); g.stroke();
  g.beginPath(); g.moveTo(480, 300); g.lineTo(560, 300); g.stroke();
  g.beginPath(); for (let x = 0; x < 120; x++) g.lineTo(600 + x * 3, 300 - Math.sin(x / 6) * (10 + x * 0.6)); g.stroke();
  g.beginPath(); for (let x = 0; x < 60; x++) g.lineTo(80 + x * 3, 140 - Math.sin(x / 6) * 14); g.stroke();
  g.beginPath(); g.arc(800, 120, 50, 0, TAU); g.moveTo(760, 120); g.lineTo(840, 120); g.stroke();
});
const kitchenWall = () => ctex("kitWall", 512, 512, (g) => {
  g.fillStyle = "#f2e2b8"; g.fillRect(0, 0, 512, 512);
  g.fillStyle = "rgba(200,120,90,0.35)"; for (let y = 32; y < 512; y += 64) for (let x = (y / 64) % 2 ? 32 : 0; x < 512; x += 64) { g.beginPath(); g.arc(x, y, 8, 0, TAU); g.fill(); }
  g.fillStyle = "#ffffff"; g.fillRect(0, 330, 512, 182);
  g.strokeStyle = "rgba(120,140,160,0.5)"; g.lineWidth = 3; for (let x = 0; x <= 512; x += 64) { g.beginPath(); g.moveTo(x, 330); g.lineTo(x, 512); g.stroke(); } for (let y = 330; y <= 512; y += 46) { g.beginPath(); g.moveTo(0, y); g.lineTo(512, y); g.stroke(); }
});
const checkerFloor = () => ctex("checkerFloor", 512, 512, (g) => {
  for (let y = 0; y < 4; y++) for (let x = 0; x < 4; x++) { g.fillStyle = (x + y) % 2 ? "#e9e2d2" : "#c0353a"; g.fillRect(x * 128, y * 128, 128, 128); }
});
const sandTex = () => ctex("sand", 512, 512, (g, r) => {
  g.fillStyle = "#ecd39a"; g.fillRect(0, 0, 512, 512);
  for (let i = 0; i < 1400; i++) { g.fillStyle = r() < 0.5 ? "rgba(200,160,100,0.35)" : "rgba(255,240,200,0.4)"; g.fillRect(r() * 512, r() * 512, 2 + r() * 3, 2 + r() * 3); }
  g.strokeStyle = "rgba(190,150,95,0.35)"; g.lineWidth = 3; for (let y = 40; y < 512; y += 90) { g.beginPath(); for (let x = 0; x <= 512; x += 16) g.lineTo(x, y + Math.sin(x / 40) * 8); g.stroke(); }
});
const seaTex = () => ctex("seaFlat", 512, 512, (g, r) => {
  g.fillStyle = "#2fa6c9"; g.fillRect(0, 0, 512, 512);
  g.strokeStyle = "rgba(255,255,255,0.55)"; g.lineWidth = 4; for (let i = 0; i < 40; i++) { const x = r() * 512, y = r() * 512; g.beginPath(); g.moveTo(x, y); g.quadraticCurveTo(x + 14, y - 6, x + 28, y); g.stroke(); }
});
const mirrorTex = () => ctex("mirrorSky", 512, 512, (g) => {
  const gr = g.createLinearGradient(0, 0, 512, 512); gr.addColorStop(0, "#9cc8ff"); gr.addColorStop(0.5, "#4f8fe0"); gr.addColorStop(1, "#b8dcff");
  g.fillStyle = gr; g.fillRect(0, 0, 512, 512);
  g.fillStyle = "rgba(255,255,255,0.7)"; for (const [x, y, w] of [[60, 120, 160], [280, 300, 200], [120, 420, 120]]) { g.save(); g.translate(x, y); g.rotate(-0.5); g.fillRect(0, 0, w, 14); g.fillRect(20, 26, w * 0.6, 8); g.restore(); }
});
/** the mask: dark chrome plate with a bright chip-layout cut-out (alpha) */
const maskTex = () => ctex("maskPlate", 512, 512, (g) => {
  g.fillStyle = "#2a3150"; g.fillRect(0, 0, 512, 512);
  g.fillStyle = "#e8f0ff";
  for (let y = 0; y < 6; y++) for (let x = 0; x < 6; x++) {
    const x0 = 36 + x * 76, y0 = 36 + y * 76;
    g.fillRect(x0 + 4, y0 + 4, 24, 24); g.fillRect(x0 + 36, y0 + 4, 20, 52); g.fillRect(x0 + 4, y0 + 38, 24, 6); g.fillRect(x0 + 4, y0 + 50, 24, 6);
  }
});
const patternTex = () => ctex("waferPattern", 512, 512, (g) => {
  g.clearRect(0, 0, 512, 512);
  const cols = ["#ff7ad0", "#7ad8ff", "#ffe07a", "#9aff9a"];
  for (let y = 0; y < 8; y++) for (let x = 0; x < 8; x++) {
    const cx = 32 + x * 64, cy = 32 + y * 64; if (Math.hypot(cx - 256, cy - 256) > 236) continue;
    g.fillStyle = cols[(x + y) % 4]; g.globalAlpha = 0.85; g.fillRect(cx - 26, cy - 26, 52, 52);
    g.globalAlpha = 1; g.fillStyle = "rgba(40,40,80,0.6)"; g.fillRect(cx - 20, cy - 3, 40, 6); g.fillRect(cx - 3, cy - 20, 6, 40);
  }
});

const glowTex = () => ctex("softGlow", 128, 128, (g) => {
  const gr = g.createRadialGradient(64, 64, 2, 64, 64, 64); gr.addColorStop(0, "rgba(255,255,255,0.9)"); gr.addColorStop(1, "rgba(255,255,255,0)");
  g.fillStyle = gr; g.fillRect(0, 0, 128, 128);
});

// ---------------- 1947: the lab ----------------
export class Lab {
  root = new THREE.Group();
  private tubes: THREE.MeshBasicMaterial[] = [];
  private scope: THREE.MeshBasicMaterial;
  constructor(parent: THREE.Object3D) {
    parent.add(this.root);
    const L = LAB, W = 12, D = 9, H = 4;
    room(this.root, L.x, L.z, W, D, H, lam("labFloor", () => ({ map: rw(planksHD()) })), lam("labWall", () => ({ map: rw(labWall()) })));
    const wood = lam("labWood", () => ({ color: "#8a5a36" })), top = lam("labTop", () => ({ color: "#3a3a40" })), metal = lam("labMetal", () => ({ color: "#8d949c" }));
    const b = new Batch();
    // the bench across the room, a shelf of bottles behind, the blackboard, a window with blinds
    b.add(box(L.x - 3.2, L.x + 3.2, 0, 0.88, L.z - 2.2, L.z - 1.0), wood);
    b.add(box(L.x - 3.3, L.x + 3.3, 0.88, 0.94, L.z - 2.25, L.z - 0.95), top);
    for (const y of [1.6, 2.2]) b.add(box(L.x - 3.2, L.x + 3.2, y, y + 0.05, L.z - D / 2, L.z - D / 2 + 0.35), wood);
    const glassCols = ["#7ac8d8", "#e8913a", "#c9e07a", "#b38aff", "#f2c230"];
    for (let k = 0; k < 18; k++) {
      const x = L.x - 3.0 + k * 0.34, y = k % 2 ? 1.65 : 2.25;
      b.add(cylY(0.07, y, y + 0.22 + 0.06 * (k % 3), x, L.z - D / 2 + 0.18, 12), lam("labGlass" + (k % 5), () => ({ color: glassCols[k % 5] })));
    }
    const bb = lam("blackboard", () => ({ map: blackboard() }));
    b.add(quad(V(L.x + 1.0, 1.2, L.z - D / 2 + 0.02), V(L.x + 5.4, 1.2, L.z - D / 2 + 0.02), V(L.x + 5.4, 3.3, L.z - D / 2 + 0.02), V(L.x + 1.0, 3.3, L.z - D / 2 + 0.02)), bb);
    b.add(box(L.x + 0.95, L.x + 5.45, 1.12, 1.2, L.z - D / 2, L.z - D / 2 + 0.12), wood);
    b.build(this.root);
    const win = new THREE.Mesh(new THREE.PlaneGeometry(2.4, 1.8), new THREE.MeshBasicMaterial({ color: new THREE.Color(1.5, 1.45, 1.3) }));
    win.position.set(L.x - 3.6, 2.3, L.z - D / 2 + 0.03); win.layers.set(NOINK); this.root.add(win);
    for (let k = 0; k < 9; k++) add(box(L.x - 4.8, L.x - 2.4, 1.45 + k * 0.2, 1.49 + k * 0.2, L.z - D / 2 + 0.04, L.z - D / 2 + 0.08), lam("blind", () => ({ color: "#e8dcc0" })), this.root, false);
    // the oscilloscope (green screen), the radio with glowing tubes, a desk lamp
    add(box(L.x + 1.4, L.x + 2.0, 0.94, 1.38, L.z - 1.9, L.z - 1.4), lam("scopeBox", () => ({ color: "#4a5262" })), this.root);
    this.scope = hdr(0.4, 2.4, 0.8);
    const sc = new THREE.Mesh(new THREE.CircleGeometry(0.15, 28), this.scope); sc.position.set(L.x + 1.7, 1.17, L.z - 1.39); sc.layers.set(NOINK); this.root.add(sc);
    add(box(L.x - 2.8, L.x - 1.9, 0.94, 1.5, L.z - 2.15, L.z - 1.55), lam("radioWood", () => ({ color: "#a8724a" })), this.root);
    for (let k = 0; k < 4; k++) {
      const m = hdr(3.0, 1.4, 0.4); this.tubes.push(m);
      const t = new THREE.Mesh(new THREE.CapsuleGeometry(0.045, 0.14, 6, 12), m); t.position.set(L.x - 2.7 + k * 0.22, 1.62, L.z - 1.85); t.layers.set(NOINK); this.root.add(t);
      add(cylY(0.05, 1.5, 1.54, L.x - 2.7 + k * 0.22, L.z - 1.85, 12), metal, this.root);
    }
    add(cylY(0.1, 0.94, 0.98, L.x - 0.9, L.z - 1.9, 16), metal, this.root);
    add(cylY(0.015, 0.98, 1.5, L.x - 0.9, L.z - 1.9, 8), metal, this.root);
    add(new THREE.ConeGeometry(0.16, 0.2, 18, 1, true).translate(L.x - 0.75, 1.45, L.z - 1.7), lam("lampShade", () => ({ color: "#3f6a4a", side: THREE.DoubleSide })), this.root);
    // the transistor itself, big on a stand on the bench: germanium block on a metal base, a plastic wedge pressed
    // into it by a bent spring, gold foil over the wedge tip (cartoon-enlarged: the real one was a quarter inch tall)
    const T = new THREE.Group(); T.position.set(L.x, 0.94, L.z - 1.45); this.root.add(T);
    add(box(-0.14, 0.14, 0, 0.04, -0.1, 0.1), metal, T);
    add(new THREE.DodecahedronGeometry(0.075, 0).scale(1.2, 0.55, 0.9).translate(0, 0.075, 0), lam("germanium", () => ({ color: "#4a5262" })), T);
    const wedge = new THREE.Shape([new THREE.Vector2(-0.05, 0.3), new THREE.Vector2(0.05, 0.3), new THREE.Vector2(0, 0.115)]);
    const wg = new THREE.ExtrudeGeometry(wedge, { depth: 0.04, bevelEnabled: false }).translate(0, 0, -0.02);
    add(wg, lam("wedge", () => ({ color: "#e8d9a8" })), T);
    const foil = new THREE.Shape([new THREE.Vector2(-0.056, 0.25), new THREE.Vector2(-0.003, 0.118), new THREE.Vector2(0.003, 0.118), new THREE.Vector2(0.056, 0.25), new THREE.Vector2(0.045, 0.26), new THREE.Vector2(0, 0.14), new THREE.Vector2(-0.045, 0.26)]);
    add(new THREE.ExtrudeGeometry(foil, { depth: 0.046, bevelEnabled: false }).translate(0, 0, -0.023), lam("goldFoil", () => ({ color: "#e8b83a" })), T);
    // the bent spring from a bracket pushing the wedge down
    add(box(0.12, 0.15, 0.04, 0.4, -0.02, 0.02), metal, T);
    const pts: THREE.Vector3[] = []; for (let i = 0; i <= 60; i++) { const u = i / 60; pts.push(V(0.135 - 0.135 * u + 0.018 * Math.sin(u * TAU * 4), 0.39 - 0.09 * u + 0.05 * Math.sin(u * Math.PI), 0.018 * Math.cos(u * TAU * 4))); }
    add(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), 160, 0.01, 8), lam("spring", () => ({ color: "#d9dde2" })), T);
    // two wires to the scope
    for (const s of [-1, 1]) { const w: THREE.Vector3[] = [V(s * 0.05, 0.2, 0.02), V(s * 0.2, 0.12, 0.1), V(0.6 + s * 0.05, 0.05, 0.0), V(1.7, 0.1, -0.15)]; add(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(w), 40, 0.006, 6), lam("wireRed" + s, () => ({ color: s > 0 ? "#c0353a" : "#3a3a40" })), T, false); }
  }
  update(t: number) {
    this.tubes.forEach((m, k) => m.color.setRGB(3.0 + 0.4 * Math.sin(t * 7 + k), 1.4, 0.4));
    this.scope.color.setRGB(0.4, 2.2 + 0.4 * Math.sin(t * 5), 0.8);
  }
}

// ---------------- 1948: breakfast and the radio column ----------------
export class Kitchen {
  root = new THREE.Group();
  constructor(parent: THREE.Object3D) {
    parent.add(this.root);
    const K = KITCHEN, W = 8, D = 6, H = 3.2;
    room(this.root, K.x, K.z, W, D, H, lam("kitFloor", () => ({ map: rw(checkerFloor()) })), lam("kitWall", () => ({ map: rw(kitchenWall()) })));
    const b = new Batch(), wood = lam("kitWood", () => ({ color: "#c98a52" })), cloth = lam("kitCloth", () => ({ color: "#f4f1ea" }));
    b.add(cylY(0.6, 0.72, 0.76, K.x, K.z, 32), cloth);
    b.add(cylY(0.06, 0, 0.72, K.x, K.z, 12), wood);
    b.add(box(K.x - 3.8, K.x + 3.8, 0, 0.9, K.z - D / 2, K.z - D / 2 + 0.6), lam("kitCounter", () => ({ color: "#5a8fc2" })));
    b.add(box(K.x - 3.8, K.x + 3.8, 0.9, 0.95, K.z - D / 2, K.z - D / 2 + 0.62), lam("kitTop", () => ({ color: "#efe3c8" })));
    // the radio on the counter (the column the story ended up in)
    const rz = K.z - D / 2 + 0.45, rx = K.x + 1.75;
    b.add(box(rx - 0.42, rx + 0.42, 0.95, 1.5, rz - 0.36, rz), lam("kitRadio", () => ({ color: "#a8603a" })));
    b.add(box(rx - 0.44, rx + 0.44, 1.48, 1.54, rz - 0.38, rz + 0.02), lam("kitRadioTop", () => ({ color: "#7a3f22" })));
    b.add(box(rx - 0.34, rx + 0.06, 1.03, 1.42, rz, rz + 0.012), lam("kitRadioCloth", () => ({ color: "#f2dfa8" })));
    for (let k = 0; k < 5; k++) b.add(box(rx - 0.33, rx + 0.05, 1.07 + k * 0.075, 1.09 + k * 0.075, rz + 0.012, rz + 0.03), lam("kitRadioBar", () => ({ color: "#7a3f22" })));
    b.add(box(rx + 0.12, rx + 0.36, 1.32, 1.42, rz, rz + 0.012), lam("kitRadioDial", () => ({ color: "#fff2c8" })));
    for (const dx of [0.17, 0.31]) b.add(new THREE.CylinderGeometry(0.045, 0.045, 0.05, 18).rotateX(Math.PI / 2).translate(rx + dx, 1.14, rz + 0.025), lam("kitKnob", () => ({ color: "#3a2a22" })));
    b.add(new THREE.CylinderGeometry(0.008, 0.008, 0.6, 6).rotateZ(-0.35).translate(rx + 0.3, 1.82, rz - 0.18), lam("kitAntenna", () => ({ color: "#c9ccd2" })));
    b.add(cylY(0.05, 0.76, 0.86, K.x + 0.25, K.z + 0.1, 14), lam("cup", () => ({ color: "#ffffff" })));
    b.build(this.root);
    const win = new THREE.Mesh(new THREE.PlaneGeometry(2.0, 1.4), new THREE.MeshBasicMaterial({ color: new THREE.Color(2.0, 1.5, 0.9) }));
    win.position.set(K.x - 1.6, 1.9, K.z - D / 2 + 0.02); win.layers.set(NOINK); this.root.add(win);
    add(box(K.x - 2.65, K.x - 0.55, 1.15, 1.2, K.z - D / 2, K.z - D / 2 + 0.1), lam("kitSill", () => ({ color: "#ffffff" })), this.root);
  }
}

// ---------------- a town street: the phone shots and the one factory ----------------
export class Street {
  root = new THREE.Group();
  constructor(parent: THREE.Object3D, kit: Kit) {
    parent.add(this.root);
    const S = STREET, b = new Batch();
    b.add(floorQ(S.x - 120, S.x + 120, S.z - 120, S.z + 120, 0, 2), lam("streetPave", () => ({ map: rw(grassHD()) })));
    b.add(floorQ(S.x - 60, S.x + 60, S.z - 9, S.z + 9, 0.01, 2), lam("streetStone", () => ({ color: "#d8cfbe" })));
    let x = S.x - 48;
    for (let i = 0; x < S.x + 44; i++) { const w = [7, 9][i % 2]; if (Math.abs(x + w / 2 - S.x - 18) > 9) house(b, x + w / 2, S.z - 14, 0, w, 8, [8.4, 9.8, 7][i % 3], i * 3 + 1, 0); x += w + 0.4; }
    // the one factory: a long white hall with a sawtooth roof and a big door
    const F = { x: S.x + 18, z: S.z - 17, w: 16, d: 12, h: 7 };
    b.add(box(F.x - F.w / 2, F.x + F.w / 2, 0, F.h, F.z - F.d / 2, F.z + F.d / 2), lam("factory", () => ({ color: "#eef0f3" })));
    for (let k = 0; k < 5; k++) {
      const x0 = F.x - F.w / 2 + k * (F.w / 5), x1 = x0 + F.w / 5;
      const sh = new THREE.Shape([new THREE.Vector2(x0, F.h), new THREE.Vector2(x1, F.h), new THREE.Vector2(x1, F.h + 1.6)]);
      b.add(new THREE.ExtrudeGeometry(sh, { depth: F.d, bevelEnabled: false }).translate(0, 0, F.z - F.d / 2), lam("factoryRoof", () => ({ color: "#4f6fd8" })));
    }
    b.add(box(F.x - 2.2, F.x + 2.2, 0, 4.2, F.z + F.d / 2, F.z + F.d / 2 + 0.05), lam("factoryDoor", () => ({ color: "#5d6574" })));
    b.add(box(F.x - F.w / 2, F.x + F.w / 2, 4.8, 5.3, F.z + F.d / 2, F.z + F.d / 2 + 0.06), lam("factoryBand", () => ({ color: "#4f6fd8" })));
    for (const [n, px, pz, h] of [["tree_oak", -24, 6, 7], ["tree_default", -8, 7.5, 6.5], ["lantern", -14, 5, 3], ["tree-high-round", 6, 7, 7.5], ["lantern", 2, -6, 3]] as const)
      prop(b, kit, n, S.x + px, 0, S.z + pz, h, px);
    b.build(this.root);
    void facadeHD;
  }
}

// ---------------- the beach + the silicon lattice ----------------
export class Beach {
  root = new THREE.Group();
  private atoms: THREE.InstancedMesh; private odd: THREE.Mesh; private n = 0;
  private m4 = new THREE.Matrix4();
  constructor(parent: THREE.Object3D) {
    parent.add(this.root);
    const B = BEACH, b = new Batch();
    b.add(floorQ(B.x - 200, B.x + 200, B.z - 200, B.z + 12, 0, 3), lam("sand", () => ({ map: rw(sandTex()) })));
    b.add(floorQ(B.x - 400, B.x + 400, B.z + 12, B.z + 500, -0.05, 6), lam("seaFlat", () => ({ map: rw(seaTex()) })));
    // a sand pile with a spade, two dunes, a parasol
    b.add(new THREE.ConeGeometry(1.1, 1.1, 32).translate(B.x - 1.4, 0.55, B.z - 1.3), lam("sandPile", () => ({ color: "#e6c98a" })));
    b.add(new THREE.SphereGeometry(9, 32, 16, 0, TAU, 0, Math.PI / 2).scale(1.6, 0.35, 1).translate(B.x - 18, 0, B.z - 20), lam("dune", () => ({ color: "#ecd39a" })));
    b.add(new THREE.SphereGeometry(9, 32, 16, 0, TAU, 0, Math.PI / 2).scale(1.4, 0.3, 1).translate(B.x + 16, 0, B.z - 24), lam("dune", () => ({ color: "#ecd39a" })));
    b.add(cylY(0.03, 0, 2.2, B.x + 2.8, B.z - 2.4, 8), lam("pole", () => ({ color: "#f4f1ea" })));
    b.add(new THREE.ConeGeometry(1.3, 0.45, 12).translate(B.x + 2.8, 2.3, B.z - 2.4), lam("parasol", () => ({ color: "#e2453c" })));
    b.add(box(B.x - 0.55, B.x - 0.5, 0.2, 0.95, B.z - 0.6, B.z - 0.55).rotateZ(0.2), lam("spade", () => ({ color: "#7a4b2a" })));
    b.build(this.root);
    // the lattice: 9 x 7 x 3 silicon atoms, one odd atom
    const pos: [number, number, number][] = [];
    for (let k = 0; k < 3; k++) for (let j = 0; j < 7; j++) for (let i = 0; i < 9; i++) pos.push([B.x + (i - 4) * 0.55 + (k % 2) * 0.27, 1.6 + j * 0.5, B.z - 1.5 - k * 0.5]);
    this.n = pos.length;
    this.atoms = new THREE.InstancedMesh(new THREE.SphereGeometry(0.2, 20, 14), lam("silicon", () => ({ color: "#8fa8e6" })), this.n);
    pos.forEach((p, i) => { this.m4.makeTranslation(...p); this.atoms.setMatrixAt(i, this.m4); });
    this.atoms.castShadow = false; this.root.add(this.atoms);
    this.odd = add(new THREE.SphereGeometry(0.27, 20, 14), lam("oddAtom", () => ({ color: "#e2453c" })), this.root, false);
    this.odd.position.set(B.x + 1 * 0.55, 1.6 + 4 * 0.5, B.z - 1.5 + 0.02);
  }
  /** lattice 0..1 grows in (scale), odd 0..1 pops the odd atom */
  update(t: number, lattice: number, odd: number) {
    this.atoms.visible = lattice > 0.01; this.odd.visible = lattice > 0.01;
    const s = lattice < 1 ? lattice * (1 + 0.15 * Math.sin(lattice * Math.PI)) : 1;
    this.atoms.scale.setScalar(1); this.atoms.position.set(0, 0, 0);
    const B = BEACH, c = new THREE.Vector3(B.x, 3.1, B.z - 2);
    this.atoms.position.copy(c).multiplyScalar(1 - s); this.atoms.scale.setScalar(s);
    this.odd.scale.setScalar(s * (1 + 0.35 * odd * (0.5 + 0.5 * Math.sin(t * 9))));
    this.odd.position.set((B.x + 0.55 + 0.27) * s + c.x * (1 - s), (1.6 + 2.0) * s + c.y * (1 - s), (B.z - 2.55) * s + c.z * (1 - s));
  }
}

// ---------------- the crystal puller, the wire saw, wafers ----------------
export class Puller {
  root = new THREE.Group();
  private ingot: THREE.Mesh; private melt: THREE.MeshBasicMaterial; private cable: THREE.Mesh;
  private slices: THREE.Mesh[] = []; private bar: THREE.Mesh;
  constructor(parent: THREE.Object3D, floor: THREE.Material, wall: THREE.Material, ceil: THREE.Material) {
    parent.add(this.root);
    const P = PULLER;
    room(this.root, P.x, P.z, 16, 12, 6, floor, wall, ceil);
    const steel = lam("pullSteel", () => ({ color: "#c9d0dc" })), dark = lam("pullDark", () => ({ color: "#4a5262" })), blue = lam("pullBlue", () => ({ color: "#4f6fd8" }));
    // the furnace: a squat drum (front half cut away so the melt shows), the tall pull tower above, its top box
    const drum = new THREE.CylinderGeometry(1.2, 1.2, 1.6, 40, 1, true, -Math.PI / 2, Math.PI).rotateY(Math.PI).translate(P.x - 3, 0.8 + 0.3, P.z);
    add(drum, new THREE.MeshLambertMaterial({ color: "#c9d0dc", side: THREE.DoubleSide }), this.root);
    add(cylY(1.25, 0, 0.3, P.x - 3, P.z, 40), dark, this.root);
    add(cylY(0.7, 0.3, 0.8, P.x - 3, P.z, 32, 0.8), lam("crucible", () => ({ color: "#d9c9b0" })), this.root);
    this.melt = hdr(4.0, 1.6, 0.3);
    const ring = new THREE.Mesh(new THREE.TorusGeometry(0.5, 0.06, 10, 40).rotateX(Math.PI / 2), this.melt); ring.position.set(P.x - 3, 0.82, P.z); ring.layers.set(NOINK); this.root.add(ring);
    const glow = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTex(), color: new THREE.Color(2.2, 0.9, 0.25), transparent: true, depthWrite: false, blending: THREE.AdditiveBlending }));
    glow.position.set(P.x - 3, 1.0, P.z + 0.3); glow.scale.set(2.4, 1.4, 1); glow.layers.set(NOINK); this.root.add(glow);
    const mm = new THREE.Mesh(new THREE.CircleGeometry(0.68, 40).rotateX(-Math.PI / 2), this.melt); mm.position.set(P.x - 3, 0.79, P.z); mm.layers.set(NOINK); this.root.add(mm);
    add(cylY(0.32, 1.9, 4.9, P.x - 3, P.z - 1.0, 24), steel, this.root);
    add(box(P.x - 3.7, P.x - 2.3, 4.9, 5.6, P.z - 1.6, P.z - 0.4), blue, this.root);
    add(box(P.x - 3.05, P.x - 2.95, 1.9, 5.0, P.z - 0.7, P.z - 0.6), dark, this.root);
    add(box(P.x - 3.6, P.x - 2.4, 5.0, 5.2, P.z - 1.0, P.z + 0.1), dark, this.root);
    this.cable = add(cylY(0.03, 0, 1, 0, 0, 8), steel, this.root, false);
    // the ingot: a silver crystal with a cone shoulder at the top (grown downward from the seed as it is pulled up)
    const prof: THREE.Vector2[] = [new THREE.Vector2(0.01, 1), new THREE.Vector2(0.04, 0.98), new THREE.Vector2(0.4, 0.86), new THREE.Vector2(0.42, 0.8), new THREE.Vector2(0.42, 0.04), new THREE.Vector2(0.3, 0), new THREE.Vector2(0.0, 0)];
    this.ingot = add(new THREE.LatheGeometry(prof.reverse(), 10), lam("ingotFacet", () => ({ color: "#8d99ad", flatShading: true })), this.root);
    // the wire saw: a horizontal ingot on a cradle, slices standing off its end, a stack of finished wafers
    const sx = P.x + 3.2;
    add(box(sx - 1.6, sx + 1.6, 0, 0.9, P.z - 0.6, P.z + 0.6), dark, this.root);
    for (const x of [sx - 0.5, sx, sx + 0.5]) add(box(x - 0.02, x + 0.02, 0.9, 2.0, P.z - 0.7, P.z + 0.7), steel, this.root, false);
    this.bar = add(new THREE.CylinderGeometry(0.42, 0.42, 1, 40).rotateZ(Math.PI / 2), lam("ingot", () => ({ color: "#b9c4d6" })), this.root);
    const wf = lam("waferMirror", () => ({ color: "#c9d6f2" }));
    for (let k = 0; k < 12; k++) { const m = add(new THREE.CylinderGeometry(0.42, 0.42, 0.012, 40).rotateZ(Math.PI / 2), wf, this.root); this.slices.push(m); }
    for (let k = 0; k < 10; k++) add(new THREE.CylinderGeometry(0.42, 0.42, 0.012, 40).translate(sx + 2.4, 0.92 + k * 0.016, P.z + 0.9), wf, this.root);
    add(box(sx + 1.9, sx + 2.9, 0, 0.92, P.z + 0.4, P.z + 1.4), blue, this.root);
  }
  /** grow 0..1 = ingot length pulled; slice 0..1 = progress of the saw */
  update(t: number, grow: number, slice: number) {
    const P = PULLER, L = 0.3 + 2.4 * grow, top = 0.8 + L;
    this.ingot.scale.set(1, L, 1); this.ingot.position.set(P.x - 3, 0.8, P.z); this.ingot.rotation.y = t * 0.8;
    this.cable.scale.set(1, 5.0 - top, 1); this.cable.position.set(P.x - 3, top, P.z);
    this.melt.color.setRGB(4.0 + 0.3 * Math.sin(t * 6), 1.6, 0.3);
    const sx = P.x + 3.2, n = Math.floor(slice * this.slices.length), len = 2.2 - 0.12 * n;
    this.bar.scale.set(1, Math.max(0.2, len), 1); this.bar.position.set(sx - 1.1 + len / 2, 1.35, P.z);
    this.slices.forEach((m, k) => { m.visible = k < n; m.position.set(sx - 1.1 + len + 0.04 + (n - k) * 0.06, 1.35, P.z); });
  }
}

// ---------------- the stencil: light through a mask onto a wafer, layers stacking ----------------
export class Stencil {
  root = new THREE.Group();
  private cone: THREE.Mesh; private coneMat: THREE.MeshBasicMaterial; private pattern: THREE.MeshBasicMaterial;
  private layers: THREE.Mesh[] = [];
  constructor(parent: THREE.Object3D, floor: THREE.Material, wall: THREE.Material, ceil: THREE.Material) {
    parent.add(this.root);
    const S = STENCIL;
    room(this.root, S.x, S.z, 10, 8, 5, floor, wall, ceil);
    const steel = lam("stSteel", () => ({ color: "#c9d0dc" })), dark = lam("stDark", () => ({ color: "#4a5262" }));
    // the lamp head, the mask plate in its frame, the wafer chuck on a table
    add(box(S.x - 0.7, S.x + 0.7, 3.4, 4.2, S.z - 0.7, S.z + 0.7), lam("stLamp", () => ({ color: "#4f6fd8" })), this.root);
    const bulb = new THREE.Mesh(new THREE.CircleGeometry(0.45, 32).rotateX(Math.PI / 2), hdr(3.0, 3.0, 3.4)); bulb.position.set(S.x, 3.39, S.z); bulb.layers.set(NOINK); this.root.add(bulb);
    add(box(S.x - 1.0, S.x + 1.0, 2.55, 2.62, S.z - 1.0, S.z + 1.0), dark, this.root);
    const mask = new THREE.Mesh(new THREE.PlaneGeometry(1.6, 1.6).rotateX(-Math.PI / 2), lam("maskPlate", () => ({ map: maskTex() })));
    mask.position.set(S.x, 2.63, S.z); this.root.add(mask);
    for (const [dx, dz] of [[-0.95, -0.95], [0.95, -0.95], [-0.95, 0.95], [0.95, 0.95]]) add(cylY(0.04, 0.9, 2.55, S.x + dx, S.z + dz, 10), steel, this.root);
    add(box(S.x - 1.3, S.x + 1.3, 0, 0.85, S.z - 1.3, S.z + 1.3), dark, this.root);
    add(new THREE.CylinderGeometry(0.62, 0.62, 0.05, 48).translate(S.x, 0.9, S.z), lam("stWafer", () => ({ color: "#6f7fd0" })), this.root);
    this.pattern = new THREE.MeshBasicMaterial({ map: patternTex(), transparent: true, opacity: 0, depthWrite: false });
    const pm = new THREE.Mesh(new THREE.CircleGeometry(0.6, 48).rotateX(-Math.PI / 2), this.pattern); pm.position.set(S.x, 0.93, S.z); pm.layers.set(NOINK); this.root.add(pm);
    // stacked layers that rise one by one (each a thin coloured disc)
    const cols = ["#ff7ad0", "#7ad8ff", "#ffe07a", "#9aff9a", "#b38aff", "#ff9a3c"];
    for (let k = 0; k < 6; k++) { const m = add(new THREE.CylinderGeometry(0.6, 0.6, 0.035, 48), lam("stLayer" + k, () => ({ color: cols[k] })), this.root, false); m.position.set(S.x, 0.95 + k * 0.045, S.z); this.layers.push(m); }
    // the light cone from the lamp through the mask down to the wafer
    this.coneMat = new THREE.MeshBasicMaterial({ color: new THREE.Color(1.2, 1.2, 1.5), transparent: true, opacity: 0.25, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide });
    this.cone = new THREE.Mesh(new THREE.CylinderGeometry(0.45, 0.62, 2.45, 40, 1, true).translate(S.x, 0.93 + 1.225, S.z), this.coneMat); this.cone.layers.set(NOINK); this.root.add(this.cone);
  }
  /** light 0..1, print 0..1 (pattern appears), layers 0..6 */
  update(t: number, light: number, print: number, layers: number) {
    this.coneMat.opacity = 0.28 * light * (0.85 + 0.15 * Math.sin(t * 8)); this.cone.visible = light > 0.01;
    this.pattern.opacity = Math.min(1, print);
    this.layers.forEach((m, k) => { const u = Math.max(0, Math.min(1, layers - k)); m.visible = u > 0; m.scale.set(1, u, 1); m.position.y = 0.97 + k * 0.045 + 0.4 * (1 - u); });
  }
}

// ---------------- a mirror the size of Germany ----------------
export class MirrorLand {
  root = new THREE.Group();
  constructor(parent: THREE.Object3D, kit: Kit) {
    parent.add(this.root);
    const M = MIRROR, b = new Batch();
    b.add(floorQ(M.x - 700, M.x + 700, M.z - 700, M.z + 700, 0, 4), lam("mirrorGrass", () => ({ map: rw(grassHD()) })));
    const sh = new THREE.Shape(GERMANY.map(([x, z]) => new THREE.Vector2(M.x + x, -(M.z + z))));
    const g = new THREE.ShapeGeometry(sh, 4).rotateX(-Math.PI / 2);
    g.computeVertexNormals();
    const pos = g.attributes.position as THREE.BufferAttribute, uv = g.attributes.uv as THREE.BufferAttribute;
    for (let i = 0; i < pos.count; i++) { pos.setY(i, 0.06); uv.setXY(i, pos.getX(i) / 60, pos.getZ(i) / 60); }
    b.add(g, lam("mirrorSky", () => ({ map: rw(mirrorTex()) })));
    // a low rim round the mirror (its frame)
    for (let i = 0; i < GERMANY.length; i++) {
      const [ax, az] = GERMANY[i], [bx, bz] = GERMANY[(i + 1) % GERMANY.length], L = Math.hypot(bx - ax, bz - az);
      b.add(new THREE.BoxGeometry(L + 1.6, 0.8, 1.6).translate(0, 0.4, 0).rotateY(-Math.atan2(bz - az, bx - ax)).translate(M.x + (ax + bx) / 2, 0, M.z + (az + bz) / 2), lam("mirrorRim", () => ({ color: "#5d6574" })));
    }
    for (let i = 0; i < 70; i++) { const a = (i / 70) * TAU, d = 130 + (i % 5) * 18; prop(b, kit, ["tree_cone", "tree_default", "tree_oak"][i % 3], M.x + Math.cos(a) * d, 0, M.z + Math.sin(a) * d * 1.2, 9 + (i % 4) * 2, i); }
    b.build(this.root);
    // the tiny bump: a 5 cm dome next to the person with the magnifier
    add(new THREE.SphereGeometry(0.09, 16, 10, 0, TAU, 0, Math.PI / 2).translate(M.x + BUMP[0], 0.06, M.z + BUMP[1]), lam("bump", () => ({ color: "#e8f4ff" })), this.root, false);
    const ring = new THREE.Mesh(new THREE.TorusGeometry(0.2, 0.014, 8, 40).rotateX(Math.PI / 2), hdr(3.0, 0.8, 0.6)); ring.position.set(M.x + BUMP[0], 0.08, M.z + BUMP[1]); ring.layers.set(NOINK); this.root.add(ring);
  }
}

// ---------------- three cargo jumbo jets over the clouds ----------------
export class Jets {
  root = new THREE.Group();
  private planes: THREE.Group[] = [];
  private clouds: THREE.Mesh[] = [];
  constructor(parent: THREE.Object3D) {
    parent.add(this.root);
    const white = lam("jetWhite", () => ({ color: "#f4f6fa" })), blue = lam("jetBlue", () => ({ color: "#4f6fd8" })), grey = lam("jetGrey", () => ({ color: "#9aa2b0" }));
    const glass = lam("jetGlass", () => ({ color: "#2f3a5a" }));
    const make = () => {
      const g = new THREE.Group();
      const L = 16, R = 1.0;
      g.add(new THREE.Mesh(new THREE.CylinderGeometry(R, R, L, 28).rotateZ(Math.PI / 2), white));
      g.add(new THREE.Mesh(new THREE.SphereGeometry(R, 28, 16).scale(1.8, 1, 1).translate(L / 2, 0, 0), white));
      g.add(new THREE.Mesh(new THREE.CylinderGeometry(R, 0.25, 5, 28).rotateZ(Math.PI / 2).translate(-L / 2 - 2.5, 0.35, 0), white));
      g.add(new THREE.Mesh(new THREE.SphereGeometry(0.75, 20, 12).scale(3.4, 0.9, 0.9).translate(L / 2 - 2.6, 0.75, 0), white)); // upper deck hump
      g.add(new THREE.Mesh(new THREE.BoxGeometry(0.5, 0.18, 0.9).translate(L / 2 + 1.2, 0.35, 0), glass));
      g.add(new THREE.Mesh(new THREE.BoxGeometry(L + 6, 0.22, 2.05).translate(-1.5, -0.1, 0), blue)); // cheat line
      const wing = new THREE.Shape([new THREE.Vector2(2.5, 0), new THREE.Vector2(-1.0, 0), new THREE.Vector2(-5.5, 9.5), new THREE.Vector2(-3.8, 9.5)]);
      for (const s of [-1, 1]) {
        const w = new THREE.ExtrudeGeometry(wing, { depth: 0.22, bevelEnabled: false }).rotateX(Math.PI / 2).translate(0, -0.35, 0);
        if (s < 0) w.scale(1, 1, -1);
        g.add(new THREE.Mesh(w, white));
        for (const k of [3.2, 6.4]) g.add(new THREE.Mesh(new THREE.CylinderGeometry(0.42, 0.42, 2.0, 18).rotateZ(Math.PI / 2).translate(1.0 - k * 0.45, -0.95, s * k), grey));
        const tail = new THREE.Shape([new THREE.Vector2(-L / 2 - 3.4, 0), new THREE.Vector2(-L / 2 - 1.2, 0), new THREE.Vector2(-L / 2 - 4.2, 3.6), new THREE.Vector2(-L / 2 - 5.2, 3.6)]);
        g.add(new THREE.Mesh(new THREE.ExtrudeGeometry(tail, { depth: 0.18, bevelEnabled: false }).rotateX(Math.PI / 2).translate(0, 0.3, 0).scale(1, 1, s), white));
      }
      const fin = new THREE.Shape([new THREE.Vector2(-L / 2 - 1.2, 0.6), new THREE.Vector2(-L / 2 - 3.6, 0.6), new THREE.Vector2(-L / 2 - 5.4, 5.0), new THREE.Vector2(-L / 2 - 4.0, 5.0)]);
      g.add(new THREE.Mesh(new THREE.ExtrudeGeometry(fin, { depth: 0.2, bevelEnabled: false }).translate(0, 0, -0.1), blue));
      g.traverse((o) => { const m = o as THREE.Mesh; if (m.isMesh) { m.castShadow = true; m.receiveShadow = true; } });
      return g;
    };
    for (let i = 0; i < 3; i++) { const p = make(); this.root.add(p); this.planes.push(p); }
    const maps = [0, 1, 2, 3].map((k) => cloudHD(k + 4));
    for (let i = 0; i < 26; i++) {
      const m = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), new THREE.MeshBasicMaterial({ map: maps[i % 4], transparent: true, depthWrite: false, color: new THREE.Color(1.15, 1.05, 1.0) }));
      m.layers.set(NOINK); this.root.add(m); this.clouds.push(m);
    }
  }
  /** tl = seconds since the shot began */
  update(tl: number, cam: THREE.Camera) {
    const S = SKY, v = 9, t = tl; // m/s (cartoon-slow, the camera flies with them)
    this.planes.forEach((p, i) => {
      const x = S.x + v * t - 34 * i, z = S.z + [0, -30, 28][i], y = S.y + [0, 5, -4][i] + 0.6 * Math.sin(t * 0.9 + i);
      p.position.set(x, y, z); p.rotation.set(0.02 * Math.sin(t + i), 0, 0.03 * Math.sin(t * 0.7 + i));
    });
    this.clouds.forEach((m, i) => {
      const a = i * 2.39996, r = 40 + (i % 7) * 60;
      m.position.set(S.x + Math.cos(a) * r * 1.6 + (i % 2 ? 60 : -40), S.y - 26 - (i % 4) * 8, S.z + Math.sin(a) * r);
      m.scale.set(120 + (i % 3) * 40, 60 + (i % 3) * 20, 1); m.lookAt(cam.position.x, m.position.y, cam.position.z);
    });
  }
}
export { mergeGeometries };
