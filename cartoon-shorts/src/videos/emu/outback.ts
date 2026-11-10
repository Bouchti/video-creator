// The Emu War film's sets (two-tone lam() geometry, outlined by the world ink):
//  Farm (red-dirt farmyard, the golden wheat field behind a wire fence, weatherboard homestead with a corrugated-iron
//  roof and veranda, a windmill with a turning wheel, a water tank, gum trees, the army camp: tent, crates, flagpole),
//  Dam (a round farm dam with an earth wall), the open plain with scrub, LewisGun / MovieCamera / Truck props,
//  Office (the minister's office: desk, blue ensign, a map of Australia), Parliament (green benches),
//  Floor (floorboards + the dropped bag of marbles), Brass (a pile of spent cartridge cases).
import * as THREE from "three";
import { lam, Batch, V, quad } from "./build";
import { ctex } from "./paint";
import { NOINK } from "./ink";
import { FIELD, FENCE_Z, HOUSE, MILL, TANK, CAMP, DAM, OFFICE, PARL, FLOOR } from "./places";

const TAU = Math.PI * 2;
export const box = (x0: number, x1: number, y0: number, y1: number, z0: number, z1: number) =>
  new THREE.BoxGeometry(x1 - x0, y1 - y0, z1 - z0).translate((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2);
export const cylY = (r: number, y0: number, y1: number, x: number, z: number, seg = 24, r2 = r) =>
  new THREE.CylinderGeometry(r2, r, y1 - y0, seg).translate(x, (y0 + y1) / 2, z);
const add = (g: THREE.BufferGeometry, m: THREE.Material, parent: THREE.Object3D, cast = true) => {
  const mesh = new THREE.Mesh(g, m); mesh.castShadow = cast; mesh.receiveShadow = true; parent.add(mesh); return mesh;
};
const hdr = (r: number, g: number, b: number) => new THREE.MeshBasicMaterial({ color: new THREE.Color(r, g, b), fog: false });
const floorQ = (x0: number, x1: number, z0: number, z1: number, y: number, s: number) => {
  const g = new THREE.BufferGeometry(), P = [x0, y, z1, x1, y, z1, x1, y, z0, x0, y, z1, x1, y, z0, x0, y, z0];
  g.setAttribute("position", new THREE.Float32BufferAttribute(P, 3));
  const uv: number[] = []; for (let i = 0; i < 6; i++) uv.push(P[i * 3] / s, P[i * 3 + 2] / s);
  g.setAttribute("uv", new THREE.Float32BufferAttribute(uv, 2)); g.computeVertexNormals(); return g;
};
/** a beam (box) from a to b with a square section t */
const beam = (a: THREE.Vector3, b: THREE.Vector3, t: number) => {
  const d = b.clone().sub(a), L = d.length();
  const g = new THREE.BoxGeometry(t, t, L);
  const m = new THREE.Matrix4().lookAt(V(0, 0, 0), d, Math.abs(d.y / L) > 0.99 ? V(1, 0, 0) : V(0, 1, 0));
  m.setPosition(a.clone().add(b).multiplyScalar(0.5));
  return g.applyMatrix4(m);
};
/** a round limb from a to b, radius ra at a and rb at b */
const limb = (a: THREE.Vector3, b: THREE.Vector3, ra: number, rb: number, seg = 8) => {
  const d = b.clone().sub(a), L = d.length();
  const g = new THREE.CylinderGeometry(rb, ra, L, seg);
  g.translate(0, L / 2, 0);
  const q = new THREE.Quaternion().setFromUnitVectors(V(0, 1, 0), d.normalize());
  return g.applyQuaternion(q).translate(a.x, a.y, a.z);
};
/** an open-fronted room (+z open): floor, back + side walls, ceiling */
const room = (parent: THREE.Object3D, cx: number, cz: number, w: number, d: number, h: number, floor: THREE.Material, wall: THREE.Material, ceil?: THREE.Material) => {
  const b = new Batch(), x0 = cx - w / 2, x1 = cx + w / 2, z0 = cz - d / 2, z1 = cz + d / 2;
  b.add(floorQ(x0, x1, z0, z1 + 6, 0, 2), floor);
  b.add(quad(V(x0, 0, z0), V(x1, 0, z0), V(x1, h, z0), V(x0, h, z0), w / 4, 1), wall);
  b.add(quad(V(x0, 0, z1), V(x0, 0, z0), V(x0, h, z0), V(x0, h, z1), d / 4, 1), wall);
  b.add(quad(V(x1, 0, z0), V(x1, 0, z1), V(x1, h, z1), V(x1, h, z0), d / 4, 1), wall);
  if (ceil) b.add(quad(V(x0, h, z0), V(x1, h, z0), V(x1, h, z1), V(x0, h, z1), w / 3, d / 3), ceil);
  b.build(parent, false);
};
const hh = (i: number, s = 0) => { const v = Math.sin(i * 127.1 + s * 311.7) * 43758.5453; return v - Math.floor(v); };

// ---------------- painted textures ----------------
/** red-ochre farmyard dirt: soft blotches, pebbles, dry grass tufts (8 m tile) */
const dirtTex = () => ctex("dirtOz", 1024, 1024, (g, r) => {
  g.fillStyle = "#c98a5c"; g.fillRect(0, 0, 1024, 1024);
  for (let i = 0; i < 420; i++) { const x = r() * 1024, y = r() * 1024, s = 30 + r() * 120; const gr = g.createRadialGradient(x, y, 1, x, y, s);
    const c = r() < 0.5 ? "rgba(214,150,104," : "rgba(172,104,66,"; gr.addColorStop(0, c + "0.45)"); gr.addColorStop(1, c + "0)"); g.fillStyle = gr; g.fillRect(x - s, y - s, 2 * s, 2 * s); }
  for (let i = 0; i < 900; i++) { g.fillStyle = r() < 0.5 ? "rgba(120,72,48,0.55)" : "rgba(236,196,150,0.6)"; g.beginPath(); g.ellipse(r() * 1024, r() * 1024, 2 + r() * 5, 1.5 + r() * 3, r() * 3, 0, TAU); g.fill(); }
  g.lineCap = "round";
  for (let i = 0; i < 160; i++) { const x = r() * 1024, y = r() * 1024; g.strokeStyle = r() < 0.5 ? "rgba(214,190,120,0.8)" : "rgba(170,150,90,0.8)"; g.lineWidth = 2.5;
    for (let k = 0; k < 6; k++) { g.beginPath(); g.moveTo(x + k * 3 - 8, y); g.lineTo(x + k * 5 - 14 + r() * 6, y - 14 - r() * 12); g.stroke(); } }
});
/** the wheat field seen from a distance: golden rows of ears, darker gaps (6 m tile) */
const wheatTex = () => ctex("wheatField", 1024, 1024, (g, r) => {
  g.fillStyle = "#d9a948"; g.fillRect(0, 0, 1024, 1024);
  for (let i = 0; i < 260; i++) { const x = r() * 1024, y = r() * 1024, s = 40 + r() * 140; const gr = g.createRadialGradient(x, y, 1, x, y, s);
    const c = r() < 0.5 ? "rgba(240,196,98," : "rgba(186,134,52,"; gr.addColorStop(0, c + "0.5)"); gr.addColorStop(1, c + "0)"); g.fillStyle = gr; g.fillRect(x - s, y - s, 2 * s, 2 * s); }
  g.lineCap = "round";
  for (let i = 0; i < 5200; i++) { const x = r() * 1024, y = r() * 1024; g.strokeStyle = r() < 0.55 ? "rgba(246,214,128,0.85)" : "rgba(160,112,44,0.7)"; g.lineWidth = 3 + r() * 2;
    g.beginPath(); g.moveTo(x, y); g.lineTo(x + 2 - r() * 4, y - 10 - r() * 8); g.stroke(); }
});
/** an alpha card of wheat stalks with ears (near-camera tufts) */
const tuftTex = () => ctex("wheatTuft", 512, 512, (g, r) => {
  g.clearRect(0, 0, 512, 512); g.lineCap = "round";
  for (let i = 0; i < 30; i++) {
    const x0 = 30 + r() * 452, lean = (r() - 0.5) * 70, top = 90 + r() * 150, xt = x0 + lean;
    g.strokeStyle = r() < 0.5 ? "#e8bf62" : "#d8ac50"; g.lineWidth = 5;
    g.beginPath(); g.moveTo(x0, 512); g.quadraticCurveTo(x0 + lean * 0.3, 300, xt, top); g.stroke();
    // the ear: a plait of grains + whiskers
    g.fillStyle = r() < 0.5 ? "#ffe08a" : "#f6d070"; g.strokeStyle = "rgba(150,100,40,0.8)"; g.lineWidth = 2;
    for (let k = 0; k < 6; k++) { const y = top - k * 12, x = xt + lean * 0.004 * k + (k % 2 ? 5 : -5); g.beginPath(); g.ellipse(x, y, 8, 11, (k % 2 ? 0.4 : -0.4), 0, TAU); g.fill(); g.stroke(); }
    g.strokeStyle = "rgba(240,214,150,0.9)"; g.lineWidth = 1.6;
    for (let k = 0; k < 5; k++) { g.beginPath(); g.moveTo(xt, top - k * 12); g.lineTo(xt + (k % 2 ? 22 : -22), top - k * 12 - 26); g.stroke(); }
  }
});
const weatherboard = () => ctex("weatherboard", 512, 512, (g) => {
  g.fillStyle = "#efe2c2"; g.fillRect(0, 0, 512, 512);
  for (let y = 0; y < 512; y += 32) { g.fillStyle = "rgba(150,120,80,0.45)"; g.fillRect(0, y + 26, 512, 6); g.fillStyle = "rgba(255,255,255,0.35)"; g.fillRect(0, y, 512, 4); }
});
const corrugated = () => ctex("corrugated", 512, 512, (g) => {
  for (let x = 0; x < 512; x += 16) { const gr = g.createLinearGradient(x, 0, x + 16, 0); gr.addColorStop(0, "#9aa1a8"); gr.addColorStop(0.5, "#c9ced3"); gr.addColorStop(1, "#8a9198"); g.fillStyle = gr; g.fillRect(x, 0, 16, 512); }
  g.fillStyle = "rgba(170,90,50,0.25)"; for (let i = 0; i < 30; i++) g.fillRect((i * 97) % 512, (i * 53) % 512, 30, 60);
});
const canvasTex = () => ctex("tentCanvas", 512, 512, (g, r) => {
  g.fillStyle = "#c2b07c"; g.fillRect(0, 0, 512, 512);
  for (let i = 0; i < 400; i++) { g.fillStyle = r() < 0.5 ? "rgba(255,250,220,0.12)" : "rgba(120,100,60,0.12)"; g.fillRect(r() * 512, r() * 512, 3 + r() * 30, 2); }
  g.fillStyle = "rgba(110,92,58,0.5)"; for (let x = 0; x < 512; x += 128) g.fillRect(x, 0, 4, 512);
});
/** a wooden ammunition crate face: planks, rope handles, a stencil */
const crateTex = () => ctex("ammoCrate", 512, 256, (g) => {
  g.fillStyle = "#8a6a3e"; g.fillRect(0, 0, 512, 256);
  for (let y = 0; y < 256; y += 64) { g.fillStyle = "rgba(60,40,20,0.6)"; g.fillRect(0, y, 512, 5); }
  g.fillStyle = "#6a4e2c"; g.fillRect(0, 0, 40, 256); g.fillRect(472, 0, 40, 256);
  g.fillStyle = "#f2e6c8"; g.font = "bold 78px sans-serif"; g.textAlign = "center"; g.textBaseline = "middle"; g.fillText(".303", 256, 112);
  g.font = "bold 40px sans-serif"; g.fillText("1000 RDS", 256, 190);
});
const boardsTex = () => ctex("floorboards", 512, 512, (g, r) => {
  for (let x = 0; x < 512; x += 64) { g.fillStyle = ["#b07a4a", "#a8703f", "#ba8556", "#a26c40"][(x / 64) % 4]; g.fillRect(x, 0, 64, 512); g.fillStyle = "rgba(60,36,20,0.7)"; g.fillRect(x, 0, 4, 512);
    for (let y = (r() * 512) | 0, k = 0; k < 2; k++, y = (y + 256) % 512) g.fillRect(x, y, 64, 3); }
  for (let i = 0; i < 80; i++) { g.strokeStyle = "rgba(90,56,30,0.25)"; g.lineWidth = 2; const x = r() * 512; g.beginPath(); g.moveTo(x, r() * 512); g.lineTo(x + 4, r() * 512); g.stroke(); }
});
const panelTex = () => ctex("woodPanel", 512, 512, (g) => {
  g.fillStyle = "#7a5034"; g.fillRect(0, 0, 512, 512);
  for (let x = 0; x < 512; x += 128) { g.fillStyle = "#6a4228"; g.fillRect(x + 14, 60, 100, 300); g.fillStyle = "rgba(255,230,190,0.15)"; g.fillRect(x + 14, 60, 100, 6); g.fillStyle = "rgba(30,15,5,0.4)"; g.fillRect(x + 14, 354, 100, 6); }
  g.fillStyle = "#5a3820"; g.fillRect(0, 380, 512, 132);
});
const officeWall = () => ctex("ozOfficeWall", 512, 512, (g) => {
  g.fillStyle = "#e9dcbc"; g.fillRect(0, 0, 512, 512);
  g.fillStyle = "#7a5034"; g.fillRect(0, 380, 512, 132); g.fillStyle = "#5a3820"; g.fillRect(0, 376, 512, 8);
  for (let x = 0; x < 512; x += 64) { g.fillStyle = "rgba(150,120,80,0.12)"; g.fillRect(x, 0, 30, 376); }
});
/** the Australian (blue) ensign: Union Jack canton, the Commonwealth star under it, the Southern Cross on the fly */
export const ensignTex = () => ctex("ensign", 512, 256, (g) => {
  g.fillStyle = "#1f2f7a"; g.fillRect(0, 0, 512, 256);
  const W = 256, H = 128;
  g.save(); g.beginPath(); g.rect(0, 0, W, H); g.clip();
  g.strokeStyle = "#ffffff"; g.lineWidth = 26; g.beginPath(); g.moveTo(0, 0); g.lineTo(W, H); g.moveTo(W, 0); g.lineTo(0, H); g.stroke();
  g.strokeStyle = "#c8202f"; g.lineWidth = 9; g.beginPath(); g.moveTo(0, 0); g.lineTo(W, H); g.moveTo(W, 0); g.lineTo(0, H); g.stroke();
  g.fillStyle = "#ffffff"; g.fillRect(W / 2 - 22, 0, 44, H); g.fillRect(0, H / 2 - 22, W, 44);
  g.fillStyle = "#c8202f"; g.fillRect(W / 2 - 13, 0, 26, H); g.fillRect(0, H / 2 - 13, W, 26);
  g.restore();
  const star = (cx: number, cy: number, r: number, n: number) => { g.fillStyle = "#ffffff"; g.beginPath(); for (let k = 0; k < 2 * n; k++) { const a = (k * Math.PI) / n - Math.PI / 2, rr = k % 2 ? r * 0.45 : r; g.lineTo(cx + rr * Math.cos(a), cy + rr * Math.sin(a)); } g.closePath(); g.fill(); };
  star(128, 196, 34, 7);
  star(384, 210, 18, 7); star(320, 120, 18, 7); star(384, 44, 18, 7); star(436, 104, 18, 7); star(408, 140, 9, 5);
});
/** a framed map of Australia on parchment */
const mapTex = () => ctex("ausMap", 512, 400, (g) => {
  g.fillStyle = "#6a4426"; g.fillRect(0, 0, 512, 400); g.fillStyle = "#efe2bf"; g.fillRect(18, 18, 476, 364);
  g.fillStyle = "#bcd6e0"; g.fillRect(30, 30, 452, 340);
  const pts = [[0.05, 0.42], [0.1, 0.33], [0.2, 0.27], [0.3, 0.18], [0.38, 0.15], [0.44, 0.08], [0.5, 0.12], [0.55, 0.2], [0.62, 0.22], [0.66, 0.07], [0.72, 0.15], [0.76, 0.28],
    [0.86, 0.38], [0.92, 0.52], [0.9, 0.64], [0.84, 0.76], [0.76, 0.84], [0.66, 0.86], [0.6, 0.78], [0.54, 0.68], [0.46, 0.66], [0.36, 0.7], [0.24, 0.74], [0.12, 0.76], [0.06, 0.66], [0.04, 0.54]];
  g.fillStyle = "#e0b46a"; g.strokeStyle = "#6a4426"; g.lineWidth = 4; g.beginPath();
  pts.forEach(([x, y], i) => { const X = 50 + x * 410, Y = 40 + y * 320; if (i) g.lineTo(X, Y); else g.moveTo(X, Y); }); g.closePath(); g.fill(); g.stroke();
  g.beginPath(); g.ellipse(50 + 0.78 * 410, 40 + 0.98 * 320, 22, 14, 0, 0, TAU); g.fill(); g.stroke(); // Tasmania
  // the wheat belt of the west, circled in red
  g.strokeStyle = "#c0353a"; g.lineWidth = 6; g.beginPath(); g.ellipse(50 + 0.14 * 410, 40 + 0.6 * 320, 34, 26, -0.2, 0, TAU); g.stroke();
});
const leatherTex = () => ctex("greenLeather", 256, 256, (g) => {
  g.fillStyle = "#3f7454"; g.fillRect(0, 0, 256, 256);
  for (let y = 0; y < 256; y += 64) for (let x = (y / 64) % 2 ? 32 : 0; x < 256; x += 64) { g.fillStyle = "#2f5a40"; g.beginPath(); g.arc(x, y, 5, 0, TAU); g.fill(); }
});
const windowTex = () => ctex("ozWindow", 256, 384, (g) => {
  const gr = g.createLinearGradient(0, 0, 0, 384); gr.addColorStop(0, "#7fb0e6"); gr.addColorStop(1, "#d8e8f4"); g.fillStyle = gr; g.fillRect(0, 0, 256, 384);
  g.fillStyle = "#6f8a52"; g.beginPath(); g.ellipse(70, 300, 80, 50, 0, 0, TAU); g.fill(); g.beginPath(); g.ellipse(200, 310, 70, 44, 0, 0, TAU); g.fill();
  g.fillStyle = "#e9dcbc"; g.fillRect(0, 330, 256, 54);
  g.fillStyle = "#f4efe2"; g.fillRect(124, 0, 8, 384); g.fillRect(0, 186, 256, 8); g.lineWidth = 16; g.strokeStyle = "#f4efe2"; g.strokeRect(0, 0, 256, 384);
});

// ---------------- gum trees + scrub ----------------
const BARK = "#d9d2c2", LEAVES = ["#7f9358", "#6f8550", "#8c9c62"];
/** a eucalypt: a pale crooked trunk forking into 3 limbs, loose clumps of olive leaves */
export const gumTree = (b: Batch, x: number, z: number, h: number, seed: number) => {
  const bark = lam("gumBark", () => ({ color: BARK })), lean = (hh(seed, 1) - 0.5) * 0.25;
  const top = V(x + lean * h, 0.45 * h, z + (hh(seed, 2) - 0.5) * 0.2 * h);
  b.add(limb(V(x, 0, z), top, 0.045 * h, 0.03 * h), bark);
  for (let k = 0; k < 3; k++) {
    const a = seed + k * 2.1, end = V(top.x + Math.cos(a) * 0.22 * h, top.y + (0.28 + 0.1 * hh(seed, k + 3)) * h, top.z + Math.sin(a) * 0.22 * h);
    b.add(limb(top, end, 0.025 * h, 0.012 * h, 6), bark);
    for (let c = 0; c < 2; c++) {
      const g = new THREE.IcosahedronGeometry(0.17 * h * (0.8 + 0.4 * hh(seed, k * 7 + c)), 1).scale(1.3, 0.62, 1.15);
      g.translate(end.x + (c - 0.5) * 0.16 * h, end.y + 0.04 * h * c, end.z + (hh(seed, c + k) - 0.5) * 0.15 * h);
      b.add(g, lam("gumLeaf" + ((seed + k + c) % 3), () => ({ color: LEAVES[(seed + k + c) % 3] })));
    }
  }
};
const scrub = (b: Batch, x: number, z: number, s: number, seed: number) => {
  for (let c = 0; c < 3; c++) {
    const g = new THREE.IcosahedronGeometry(s * (0.55 + 0.3 * hh(seed, c)), 1).scale(1.2, 0.7, 1.1);
    g.translate(x + (c - 1) * 0.5 * s, 0.35 * s, z + (hh(seed, c + 5) - 0.5) * 0.6 * s);
    b.add(g, lam("scrub" + (c % 2), () => ({ color: c % 2 ? "#8a9a5c" : "#9aa868" })));
  }
};

// ---------------- the farm ----------------
export class Farm {
  root = new THREE.Group();
  private wheel = new THREE.Group();
  constructor(parent: THREE.Object3D) {
    parent.add(this.root);
    const b = new Batch();
    // ground: dirt everywhere, the wheat field over it
    b.add(floorQ(-1400, 1600, -1400, 900, 0, 8), lam("dirt", () => ({ map: dirtTex() })));
    b.add(floorQ(FIELD.x0, FIELD.x1, FIELD.z0, FIELD.z1, 0.02, 6), lam("wheat", () => ({ map: wheatTex() })));
    // a second paddock of wheat beyond, and stubble-gold strips far off (the wheat belt)
    b.add(floorQ(-700, -200, -700, -60, 0.02, 6), lam("wheat", () => ({ map: wheatTex() })));
    b.add(floorQ(200, 900, -900, -420, 0.02, 6), lam("wheat", () => ({ map: wheatTex() })));
    // the fence: posts and three wires along the field edge
    const post = lam("post", () => ({ color: "#8a6a48" })), wire = lam("wire", () => ({ color: "#6f7478" }));
    for (let x = FIELD.x0; x <= FIELD.x1; x += 3.2) b.add(cylY(0.06, 0, 1.15, x, FENCE_Z, 6), post);
    for (const y of [0.45, 0.75, 1.05]) b.add(box(FIELD.x0, FIELD.x1, y - 0.006, y + 0.006, FENCE_Z - 0.006, FENCE_Z + 0.006), wire);
    // the homestead: weatherboard box, hipped corrugated roof, a veranda on posts, a chimney
    const H = HOUSE, wb = lam("weatherboard", () => ({ map: weatherboard() })), roof = lam("corrugated", () => ({ map: corrugated(), side: THREE.DoubleSide }));
    b.add(box(H.x - 6, H.x + 6, 0, 3.2, H.z - 4, H.z + 4), wb);
    const rg = new THREE.ConeGeometry(9.2, 2.6, 4, 1).rotateY(Math.PI / 4).scale(1.0, 1, 0.68).translate(H.x, 3.2 + 1.3, H.z);
    b.add(rg, roof);
    b.add(box(H.x - 6.5, H.x + 6.5, 2.7, 2.85, H.z - 6.4, H.z - 4), roof);
    for (let x = H.x - 6.2; x <= H.x + 6.3; x += 2.08) b.add(box(x - 0.07, x + 0.07, 0, 2.7, H.z - 6.3, H.z - 6.16), lam("verandaPost", () => ({ color: "#f2ead8" })));
    b.add(box(H.x + 3, H.x + 3.8, 3.5, 5.4, H.z, H.z + 0.8), lam("chimney", () => ({ color: "#a8583a" })));
    b.add(box(H.x - 0.6, H.x + 0.6, 0, 2.1, H.z - 4.03, H.z - 3.98), lam("door", () => ({ color: "#3f6a4a" })));
    for (const dx of [-3.6, 3.6]) { b.add(box(H.x + dx - 0.6, H.x + dx + 0.6, 1.0, 2.2, H.z - 4.03, H.z - 3.98), lam("winOz", () => ({ color: "#5a7a96" }))); }
    // the water tank: a corrugated drum on a stand
    b.add(cylY(1.5, 2.2, 4.6, TANK.x, TANK.z, 28), lam("tankIron", () => ({ map: corrugated() })));
    b.add(cylY(1.55, 4.6, 4.9, TANK.x, TANK.z, 28, 0.2), roof);
    for (const [dx, dz] of [[-1, -1], [1, -1], [-1, 1], [1, 1]]) b.add(box(TANK.x + dx * 1.1 - 0.08, TANK.x + dx * 1.1 + 0.08, 0, 2.2, TANK.z + dz * 1.1 - 0.08, TANK.z + dz * 1.1 + 0.08), post);
    // the windmill tower (the wheel turns: built apart)
    const steel = lam("millSteel", () => ({ color: "#8d949c" }));
    for (const [dx, dz] of [[-1, -1], [1, -1], [-1, 1], [1, 1]]) b.add(beam(V(MILL.x + dx * 1.3, 0, MILL.z + dz * 1.3), V(MILL.x + dx * 0.18, 9, MILL.z + dz * 0.18), 0.1), steel);
    for (let y = 2; y < 9; y += 2.2) { const w = 1.3 - (y / 9) * 1.12; b.add(box(MILL.x - w, MILL.x + w, y - 0.04, y + 0.04, MILL.z - w, MILL.z - w + 0.08), steel); b.add(box(MILL.x - w, MILL.x - w + 0.08, y - 0.04, y + 0.04, MILL.z - w, MILL.z + w), steel); }
    b.add(box(MILL.x - 0.3, MILL.x + 0.3, 9, 9.5, MILL.z - 0.3, MILL.z + 0.6), steel);
    b.add(box(MILL.x - 0.05, MILL.x + 0.05, 9.0, 10.2, MILL.z + 0.6, MILL.z + 2.6), lam("millVane", () => ({ color: "#c9ccd2" })));
    // gum trees around the yard and along the field, scrub on the dirt, a far bush line on the horizon
    const trees: [number, number, number][] = [[-40, 30, 13], [-34, 40, 11], [8, 34, 12], [40, 26, 14], [52, 8, 10], [-52, 6, 12], [-70, 20, 11], [70, 30, 13], [-12, 46, 10], [28, 48, 12],
      [180, -10, 12], [200, -70, 14], [262, -66, 11], [282, -20, 12], [210, -10, 9], [300, -48, 13], [340, -90, 11], [520, -160, 12], [600, -250, 10], [700, -190, 13]];
    trees.forEach(([x, z, h], i) => gumTree(b, x, z, h, i + 1));
    for (let i = 0; i < 70; i++) { const a = hh(i, 3) * TAU, d = 220 + hh(i, 4) * 500; gumTree(b, 300 + Math.cos(a) * d, -100 + Math.sin(a) * d, 10 + hh(i, 5) * 6, 40 + i); }
    for (let i = 0; i < 260; i++) {
      const x = -300 + hh(i, 7) * 1300, z = -500 + hh(i, 8) * 700;
      const inField = x > FIELD.x0 - 2 && x < FIELD.x1 + 2 && z > FIELD.z0 - 2 && z < FIELD.z1 + 4;
      const inYard = x > -60 && x < 60 && z > -6 && z < 60;
      const inDam = Math.hypot(x - DAM.x, z - DAM.z) < 26;
      if (inField || inYard || inDam) continue;
      scrub(b, x, z, 0.6 + hh(i, 9) * 0.8, i);
    }
    for (let i = 0; i < 40; i++) { const a = (i / 40) * TAU, d = 1050 + (i % 3) * 60; b.add(new THREE.SphereGeometry(70 + (i % 4) * 25, 14, 8, 0, TAU, 0, Math.PI / 2).scale(2.2, 0.32, 1).rotateY(a).translate(300 + Math.cos(a) * d, 0, -150 + Math.sin(a) * d), lam("bushLine", () => ({ color: "#7d8a60" }))); }
    // the army camp: a ridge tent, a flagpole with the ensign, ammo crates
    const C = CAMP, cv = lam("tentCanvas", () => ({ map: canvasTex(), side: THREE.DoubleSide }));
    const tent = new THREE.CylinderGeometry(2.0, 2.0, 4.4, 3, 1, false).rotateZ(Math.PI / 2).rotateX(Math.PI).translate(C.x + 9, 1.0, C.z + 8);
    b.add(tent, cv);
    b.add(cylY(0.05, 0, 6.5, C.x - 4, C.z + 4, 8), lam("flagPole", () => ({ color: "#f2ead8" })));
    b.build(this.root, true);
    const flag = new THREE.Mesh(new THREE.PlaneGeometry(1.6, 0.8), new THREE.MeshLambertMaterial({ map: ensignTex(), side: THREE.DoubleSide }));
    flag.position.set(C.x - 4 + 0.82, 6.0, C.z + 4); flag.layers.set(NOINK); this.root.add(flag);
    // the windmill wheel: 14 blades on a hub, facing +z
    const blade = lam("millBlade", () => ({ color: "#d9dde2" }));
    for (let k = 0; k < 14; k++) { const m = add(box(-0.12, 0.12, 0.25, 1.45, -0.02, 0.02), blade, this.wheel); m.rotation.z = (k / 14) * TAU; }
    add(new THREE.TorusGeometry(1.25, 0.04, 6, 32), steel, this.wheel);
    this.wheel.position.set(MILL.x, 9.25, MILL.z - 0.45); this.root.add(this.wheel);
    // the dam: water, a mud rim, the earth wall on the west side, a dead tree standing in the water
    const D = DAM;
    const water = new THREE.Mesh(new THREE.CircleGeometry(D.r, 48).rotateX(-Math.PI / 2).translate(D.x, 0.06, D.z), lam("damWater", () => ({ color: "#7aa6a8" })));
    water.receiveShadow = true; this.root.add(water);
    const rim = new THREE.Mesh(new THREE.RingGeometry(D.r, D.r + 2.6, 48).rotateX(-Math.PI / 2).translate(D.x, 0.04, D.z), lam("damMud", () => ({ color: "#a8744a" })));
    rim.receiveShadow = true; this.root.add(rim);
    const wall = new THREE.Mesh(new THREE.CylinderGeometry(1, 1, 30, 20, 1, false, 0, Math.PI).rotateZ(Math.PI / 2).rotateY(Math.PI / 2).scale(2.2, D.wallH, 1).translate(D.wallX, 0, D.z),
      lam("damWall", () => ({ color: "#9a5f3a" })));
    wall.castShadow = wall.receiveShadow = true; this.root.add(wall);
    const db = new Batch(), dead = lam("deadWood", () => ({ color: "#9a8f80" }));
    const bag = lam("sandbag", () => ({ color: "#c9b27a" }));
    for (let r = 0; r < 2; r++) for (let k = 0; k < 9; k++) {
      const z = D.z - 3.2 + k * 0.72 + (r ? 0.36 : 0), x = D.wallX + 0.95;
      db.add(new THREE.SphereGeometry(0.36, 14, 8).scale(0.55, 0.42, 1).translate(x, D.wallH * 0.86 + r * 0.26, z), bag);
    }
    db.add(limb(V(D.x + 3, 0, D.z - 3), V(D.x + 3.5, 4.5, D.z - 3.2), 0.18, 0.1), dead);
    db.add(limb(V(D.x + 3.4, 3.2, D.z - 3.1), V(D.x + 5, 5.4, D.z - 3.4), 0.08, 0.03), dead);
    db.add(limb(V(D.x + 3.4, 3.8, D.z - 3.1), V(D.x + 2, 5.8, D.z - 3), 0.07, 0.03), dead);
    db.build(this.root, true);
  }
  update(f: number) { this.wheel.rotation.z = -f * 0.06; }
}

/** wheat tufts near the cameras: alpha cards in crossed pairs (NOINK: the world ink would hatch every stalk) */
export class Wheat {
  root = new THREE.Group();
  constructor(parent: THREE.Object3D, zones: [number, number, number, number][]) {
    parent.add(this.root);
    const pos: number[] = [], uv: number[] = [], nrm: number[] = [];
    let i = 0;
    for (const [x0, x1, z0, z1] of zones) {
      const n = Math.round(((x1 - x0) * (z1 - z0)) / 1.1);
      for (let k = 0; k < n; k++, i++) {
        const x = x0 + hh(i, 1) * (x1 - x0), z = z0 + hh(i, 2) * (z1 - z0), h = 0.5 + 0.2 * hh(i, 3), w = 0.9, a = hh(i, 4) * Math.PI;
        for (const da of [0, Math.PI / 2]) {
          const c = Math.cos(a + da) * w / 2, s = Math.sin(a + da) * w / 2;
          const P = [[x - c, 0, z - s], [x + c, 0, z + s], [x + c, h, z + s], [x - c, h, z - s]];
          for (const t of [0, 1, 2, 0, 2, 3]) { pos.push(...P[t]); uv.push(t === 1 || t === 2 ? 1 : 0, t >= 2 ? 1 : 0); nrm.push(0, 1, 0); }
        }
      }
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3)); g.setAttribute("uv", new THREE.Float32BufferAttribute(uv, 2)); g.setAttribute("normal", new THREE.Float32BufferAttribute(nrm, 3));
    const m = new THREE.Mesh(g, lam("wheatTuftMat", () => ({ map: tuftTex(), alphaTest: 0.5, side: THREE.DoubleSide })));
    m.layers.set(NOINK); m.receiveShadow = true; this.root.add(m);
  }
}

// ---------------- props ----------------
/** a Lewis gun: fat finned barrel shroud, the round pan magazine on top, a wooden stock, on a bipod; points along +x.
 *  Origin = the bipod feet; muzzle at about (1.0, 0.42, 0). */
export const lewisGun = (tripod = false, hgt?: number) => {
  const g = new THREE.Group();
  const dark = lam("gunSteel", () => ({ color: "#3a3d44" })), wood = lam("gunWood", () => ({ color: "#8a5a34" })), pan = lam("gunPan", () => ({ color: "#4a4e56" }));
  const y = hgt ?? (tripod ? 1.1 : 0.42);
  add(new THREE.CylinderGeometry(0.075, 0.075, 0.82, 16).rotateZ(Math.PI / 2).translate(0.38, y, 0), dark, g);        // the shroud
  add(new THREE.CylinderGeometry(0.03, 0.03, 0.22, 10).rotateZ(Math.PI / 2).translate(0.88, y, 0), dark, g);          // muzzle
  add(box(-0.28, 0.0, y - 0.07, y + 0.06, -0.05, 0.05), dark, g);                                                     // receiver
  add(new THREE.CylinderGeometry(0.2, 0.2, 0.06, 24).translate(-0.1, y + 0.1, 0), pan, g);                            // pan magazine
  add(box(-0.17, -0.03, y + 0.13, y + 0.15, -0.02, 0.02), dark, g);
  add(box(-0.72, -0.28, y - 0.08, y + 0.02, -0.04, 0.04).translate(0, 0, 0), wood, g);                                // stock
  add(box(-0.3, -0.24, y - 0.22, y - 0.06, -0.03, 0.03), wood, g);                                                    // grip
  if (tripod) for (const [dx, dz] of [[0.35, -0.3], [0.35, 0.3], [-0.4, 0]]) add(limb(V(0.05, y - 0.06, 0), V(dx, 0, dz), 0.025, 0.02, 6), dark, g);
  else for (const s of [-1, 1]) add(limb(V(0.6, y - 0.05, 0), V(0.66, 0, s * 0.18), 0.015, 0.012, 6), dark, g);
  return g;
};
/** a hand-cranked newsreel camera on a wooden tripod: a box body, two film reels on top, a lens, the crank; lens +x */
export const movieCamera = () => {
  const g = new THREE.Group();
  const body = lam("camBody", () => ({ color: "#3a3330" })), wood = lam("camWood", () => ({ color: "#9a6a42" })), brass = lam("brassOz", () => ({ color: "#d9b45a" }));
  for (const [dx, dz] of [[0.4, 0], [-0.25, 0.34], [-0.25, -0.34]]) add(limb(V(0, 1.2, 0), V(dx, 0, dz), 0.03, 0.025, 6), wood, g);
  add(box(-0.22, 0.22, 1.2, 1.55, -0.13, 0.13), body, g);
  for (const dx of [-0.13, 0.13]) add(new THREE.CylinderGeometry(0.17, 0.17, 0.06, 24).rotateX(Math.PI / 2).translate(dx, 1.75, 0), body, g);
  add(new THREE.CylinderGeometry(0.06, 0.07, 0.14, 14).rotateZ(Math.PI / 2).translate(0.29, 1.4, 0), brass, g);
  add(box(-0.02, 0.02, 1.3, 1.42, 0.13, 0.2), brass, g);
  return g;
};
/** a stack of ammunition crates (n boxes, 0.7 x 0.35 x 0.4) */
export const crates = (n: number) => {
  const g = new THREE.Group(), side = lam("crateFace", () => ({ map: crateTex() })), wood = lam("crateWood", () => ({ color: "#8a6a3e" }));
  for (let i = 0; i < n; i++) {
    const m = new THREE.Mesh(new THREE.BoxGeometry(0.7, 0.36, 0.42), [wood, wood, wood, wood, side, side]);
    m.position.set((i % 2) * 0.74 - 0.37, 0.18 + Math.floor(i / 2) * 0.37, 0); m.castShadow = m.receiveShadow = true;
    m.name = "crate" + i; g.add(m);
  }
  return g;
};
/** a 1930s flatbed truck: bonnet + radiator, a cab with a canvas roof, separate mudguards, spoked wheels, a wooden tray.
 *  Points along +x; origin = ground under the middle of the tray. */
export class Truck {
  root = new THREE.Group();
  body = new THREE.Group();
  private wheels: THREE.Mesh[] = [];
  gun: THREE.Group;
  constructor(parent: THREE.Object3D, withGun: boolean) {
    parent.add(this.root); this.root.add(this.body);
    const g = this.body, paint = lam("truckGreen", () => ({ color: "#4f5a3a" })), black = lam("truckBlack", () => ({ color: "#26262c" })), tray = lam("truckTray", () => ({ color: "#9a7a52" }));
    const chrome = lam("truckChrome", () => ({ color: "#c9ccd2" }));
    add(box(-2.0, 3.2, 0.62, 0.78, -0.55, 0.55), black, g);                       // chassis rails
    add(box(1.9, 3.15, 0.78, 1.45, -0.5, 0.5), paint, g);                          // bonnet
    add(box(3.15, 3.25, 0.75, 1.5, -0.48, 0.48), chrome, g);                       // radiator
    add(box(0.9, 1.9, 0.78, 2.1, -0.7, 0.7), paint, g);                            // cab
    add(box(0.85, 2.0, 2.1, 2.2, -0.78, 0.78), black, g);                          // roof
    add(box(1.88, 1.92, 1.5, 2.05, -0.62, 0.62), lam("truckGlass", () => ({ color: "#8fb0c8" })), g);
    add(box(-2.1, 0.85, 0.8, 0.95, -0.9, 0.9), tray, g);                           // tray floor
    for (const s of [-1, 1]) add(box(-2.1, 0.85, 0.95, 1.25, s * 0.9 - 0.04, s * 0.9 + 0.04), tray, g); // tray sides
    add(box(-2.14, -2.06, 0.95, 1.25, -0.9, 0.9), tray, g);
    for (const s of [-1, 1]) {
      const hl = new THREE.Mesh(new THREE.SphereGeometry(0.11, 12, 8).translate(3.2, 1.55, s * 0.4), hdr(2.2, 2.0, 1.5)); hl.layers.set(NOINK); g.add(hl);
      add(new THREE.SphereGeometry(0.5, 16, 8, 0, Math.PI, 0, Math.PI).rotateY(Math.PI / 2).rotateX(-Math.PI / 2).scale(1.3, 0.55, 0.45).translate(2.55, 0.6, s * 0.78), paint, g); // front guards
      add(box(0.7, 1.95, 0.48, 0.54, s * 0.78 - 0.14, s * 0.78 + 0.14), black, g); // running boards
    }
    const wg = new THREE.CylinderGeometry(0.45, 0.45, 0.22, 20).rotateX(Math.PI / 2), tyre = lam("truckTyre", () => ({ color: "#1d1d22" })), hub = lam("truckHub", () => ({ color: "#b8332e" }));
    for (const [x, z] of [[2.55, -0.82], [2.55, 0.82], [-1.2, -0.82], [-1.2, 0.82]]) {
      const w = add(wg.clone(), tyre, this.root); w.position.set(x, 0.45, z); this.wheels.push(w);
      for (let k = 0; k < 6; k++) { const sp = add(box(-0.025, 0.025, -0.36, 0.36, -0.12, 0.12), hub, w); sp.rotation.z = (k / 6) * Math.PI; }
    }
    this.gun = lewisGun(true); this.gun.position.set(-0.9, 0.95, 0); this.gun.visible = withGun; g.add(this.gun);
  }
  /** truck at (x, z) heading yaw (0 = +x), travelled distance s, bounce (m) and pitch (rad) of the body on its springs */
  update(x: number, z: number, yaw: number, s: number, bounce: number, pitch: number, visible: boolean) {
    this.root.visible = visible;
    this.root.position.set(x, 0, z); this.root.rotation.y = yaw;
    this.body.position.y = bounce; this.body.rotation.z = pitch;
    for (const w of this.wheels) w.rotation.z = -s / 0.45;
  }
}

/** a heap of spent brass cartridge cases (instanced little cylinders) at (x, z), radius r, height h */
export const brassPile = (x: number, z: number, r: number, h: number, n: number) => {
  const g = new THREE.CylinderGeometry(0.012, 0.012, 0.056, 6);
  const mesh = new THREE.InstancedMesh(g, lam("brassCase", () => ({ color: "#d9a640" })), n);
  const m = new THREE.Matrix4(), q = new THREE.Quaternion(), e = new THREE.Euler();
  for (let i = 0; i < n; i++) {
    const a = hh(i, 1) * TAU, d = Math.sqrt(hh(i, 2)) * r, y = h * (1 - (d / r) ** 1.6) * hh(i, 3) ** 0.4;
    e.set(hh(i, 4) * 3, hh(i, 5) * 3, hh(i, 6) * 3); q.setFromEuler(e);
    m.compose(V(x + Math.cos(a) * d, y + 0.012, z + Math.sin(a) * d), q, V(1, 1, 1)); mesh.setMatrixAt(i, m);
  }
  mesh.castShadow = false; mesh.receiveShadow = true;
  const cone = new THREE.Mesh(new THREE.ConeGeometry(r, h * 0.92, 28).translate(x, h * 0.46, z), lam("brassCone", () => ({ color: "#c99636" })));
  cone.receiveShadow = true;
  const grp = new THREE.Group(); grp.add(cone, mesh);
  return grp;
};

// ---------------- the minister's office ----------------
export class Office {
  root = new THREE.Group();
  constructor(parent: THREE.Object3D) {
    parent.add(this.root);
    const O = OFFICE, b = new Batch(), W = 9, D = 9, Ht = 4.0;
    room(this.root, O.x, O.z, W, D, Ht, lam("ozCarpet", () => ({ color: "#7a2e32" })), lam("ozOfficeWall", () => ({ map: officeWall() })), lam("ozCeil", () => ({ color: "#efe3c8" })));
    const wood = lam("deskWoodOz", () => ({ color: "#5a3620" })), top = lam("deskTopOz", () => ({ color: "#3f6a4a" }));
    const dz = O.z - 1.6;
    b.add(box(O.x - 1.3, O.x + 1.3, 0, 0.78, dz - 0.5, dz + 0.5), wood);
    b.add(box(O.x - 1.26, O.x + 1.26, 0.78, 0.8, dz - 0.46, dz + 0.46), top);
    b.add(box(O.x - 0.5, O.x + 0.5, 0.8, 0.84, dz - 0.15, dz + 0.25), lam("ozPaper", () => ({ color: "#f7f1e1" })));
    b.add(cylY(0.08, 0.8, 0.9, O.x + 0.8, dz, 12), lam("inkwellOz", () => ({ color: "#2e2a36" })));
    b.add(cylY(0.05, 0, 3.0, O.x + 2.2, O.z - 3.6, 8), lam("flagPoleOz", () => ({ color: "#d9b45a" })));
    b.add(box(O.x - 2.6, O.x - 1.9, 0, 2.2, O.z - 4.5, O.z - 3.9), wood); // bookcase
    for (let k = 0; k < 4; k++) b.add(box(O.x - 2.55, O.x - 1.95, 0.3 + k * 0.5, 0.62 + k * 0.5, O.z - 3.95, O.z - 3.9), lam("books" + (k % 2), () => ({ color: k % 2 ? "#8c3b4a" : "#3f5f8a" })));
    b.build(this.root, true);
    const z0 = O.z - D / 2;
    const map = new THREE.Mesh(new THREE.PlaneGeometry(1.9, 1.48), new THREE.MeshBasicMaterial({ map: mapTex() })); map.position.set(O.x - 0.1, 2.35, z0 + 0.03); map.layers.set(NOINK); this.root.add(map);
    const win = new THREE.Mesh(new THREE.PlaneGeometry(1.4, 2.1), new THREE.MeshBasicMaterial({ map: windowTex(), fog: false })); win.position.set(O.x + 3.2, 1.9, z0 + 0.03); win.layers.set(NOINK); this.root.add(win);
    const flag = new THREE.Mesh(new THREE.PlaneGeometry(1.3, 0.65), new THREE.MeshLambertMaterial({ map: ensignTex(), side: THREE.DoubleSide }));
    flag.position.set(O.x + 2.2 - 0.67, 2.55, O.z - 3.6); flag.rotation.y = 0.25; flag.layers.set(NOINK); this.root.add(flag);
  }
}

// ---------------- parliament: two banks of green benches facing across the floor, the table, the Speaker's chair ----------------
export const BENCH_ROWS = 3;
export class Parliament {
  root = new THREE.Group();
  constructor(parent: THREE.Object3D) {
    parent.add(this.root);
    const P = PARL, b = new Batch(), W = 16, D = 18, Ht = 7;
    room(this.root, P.x, P.z, W, D, Ht, lam("parlFloor", () => ({ color: "#5a3a26" })), lam("woodPanel", () => ({ map: panelTex() })), lam("parlCeil", () => ({ color: "#d9cfb5" })));
    const green = lam("greenLeather", () => ({ map: leatherTex() })), wood = lam("benchWood", () => ({ color: "#4a2e1c" }));
    // benches run along z (the chamber's long axis), on both sides of the floor (x = P.x +- 2.2 ...)
    for (const s of [-1, 1]) for (let r = 0; r < BENCH_ROWS; r++) {
      const x = P.x + s * (2.3 + r * 1.05), y0 = r * 0.35, z0 = P.z - 7, z1 = P.z + 6;
      b.add(box(x - 0.45, x + 0.45, 0, y0 + 0.45, z0, z1), wood);
      b.add(box(x - 0.42, x + 0.42, y0 + 0.45, y0 + 0.55, z0, z1), green);
      b.add(box(x + s * 0.38, x + s * 0.48, y0 + 0.45, y0 + 1.05, z0, z1), green);
    }
    b.add(box(P.x - 0.9, P.x + 0.9, 0, 0.8, P.z - 4, P.z + 1), wood);                // the table
    b.add(box(P.x - 0.85, P.x + 0.85, 0.8, 0.83, P.z - 3.95, P.z + 0.95), green);
    b.add(box(P.x - 0.8, P.x + 0.8, 0, 2.8, P.z - 8.6, P.z - 7.8), wood);           // the Speaker's chair
    b.add(box(P.x - 0.6, P.x + 0.6, 0.5, 0.7, P.z - 7.8, P.z - 7.2), green);
    b.add(box(P.x - 1.0, P.x + 1.0, 2.8, 3.3, P.z - 8.7, P.z - 7.6), wood);
    b.build(this.root, true);
    const mace = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.05, 1.3, 10).rotateX(Math.PI / 2).translate(P.x, 0.9, P.z - 1.5), lam("maceGold", () => ({ color: "#d9b45a" })));
    mace.castShadow = true; this.root.add(mace);
  }
}

// ---------------- the floorboards and the bag of marbles ----------------
const MARBLE_COLS = ["#e2453c", "#3f8fd2", "#f2c230", "#4fb06a", "#9a5ac9", "#f08a2c", "#2fb4b0", "#e85a9a"];
export const MARBLES = 46;
export class Floor {
  root = new THREE.Group();
  private balls: THREE.Mesh[] = [];
  private bag: THREE.Group;
  private dir: [number, number, number][] = [];
  constructor(parent: THREE.Object3D) {
    parent.add(this.root);
    const F = FLOOR;
    room(this.root, F.x, F.z, 10, 10, 4, lam("floorboards", () => ({ map: boardsTex() })), lam("ozOfficeWall", () => ({ map: officeWall() })));
    for (let i = 0; i < MARBLES; i++) {
      const m = new THREE.Mesh(new THREE.SphereGeometry(0.035, 16, 12), lam("marble" + (i % 8), () => ({ color: MARBLE_COLS[i % 8] })));
      m.castShadow = true; this.root.add(m); this.balls.push(m);
      const a = hh(i, 1) * TAU, sp = 0.6 + 1.6 * hh(i, 2);
      this.dir.push([Math.cos(a) * sp, Math.sin(a) * sp, hh(i, 3)]);
    }
    // the cloth bag: a sack with a drawstring neck
    this.bag = new THREE.Group();
    const cloth = lam("bagCloth", () => ({ color: "#b5834f" }));
    // a slumped burlap sack lying on its side: a fat body, folds, a gathered neck tied with a red drawstring, the open mouth
    add(new THREE.SphereGeometry(0.13, 20, 14).scale(1.2, 0.62, 1.0).translate(-0.03, 0, 0), cloth, this.bag);
    for (const [x, r] of [[-0.06, 0.12], [0.03, 0.11]] as const) add(new THREE.TorusGeometry(r, 0.008, 6, 24).rotateY(Math.PI / 2).scale(1, 0.62, 1).translate(x, 0, 0), lam("bagFold", () => ({ color: "#9a6a3e" })), this.bag);
    add(new THREE.CylinderGeometry(0.035, 0.08, 0.1, 14).rotateZ(Math.PI / 2).translate(0.15, 0.0, 0), cloth, this.bag);
    add(new THREE.TorusGeometry(0.038, 0.011, 6, 16).rotateY(Math.PI / 2).translate(0.13, 0.0, 0), lam("bagString", () => ({ color: "#c0353a" })), this.bag);
    add(new THREE.CylinderGeometry(0.075, 0.04, 0.07, 14, 1, true).rotateZ(Math.PI / 2).translate(0.23, 0.0, 0), lam("bagMouth", () => ({ color: "#b5834f", side: THREE.DoubleSide })), this.bag);
    add(new THREE.CylinderGeometry(0.004, 0.004, 0.16, 5).rotateZ(0.5).translate(0.16, -0.05, 0.03), lam("bagString", () => ({ color: "#c0353a" })), this.bag);
    this.root.add(this.bag);
  }
  /** t = seconds since the drop (negative = still falling in from above) */
  update(t: number, visible: boolean) {
    this.root.visible = visible;
    if (!visible) return;
    const F = FLOOR, cx = F.x, cz = F.z - 1.2;
    const fall = Math.min(0, t);
    this.bag.position.set(cx - 0.12, 0.09 + Math.max(0, -fall) * 3.2, cz); this.bag.rotation.set(0, 0.6, t > 0 ? -0.25 : 0.9);
    this.bag.scale.set(1 + (t > 0 && t < 0.15 ? 0.15 : 0), t > 0 && t < 0.15 ? 0.8 : 1, 1 + (t > 0 && t < 0.15 ? 0.15 : 0));
    this.balls.forEach((m, i) => {
      const [vx, vz, d] = this.dir[i], tt = Math.max(0, t - 0.03 * d);
      const k = (1 - Math.exp(-1.4 * tt)) / 1.4; // rolling with friction
      m.visible = t > 0;
      const bounce = tt < 0.4 ? Math.abs(Math.sin(tt * 18)) * 0.06 * (1 - tt / 0.4) : 0;
      m.position.set(cx + vx * k * 1.6, 0.035 + bounce, cz + vz * k * 1.6);
      m.rotation.set(vz * k * 40, 0, -vx * k * 40);
    });
  }
}
