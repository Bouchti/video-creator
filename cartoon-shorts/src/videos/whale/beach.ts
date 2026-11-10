// The exploding-whale film's sets (two-tone lam() geometry, outlined by the world ink):
//  Beach (the Oregon coast at Florence: sand, wet sand, the sea with moving surf, dunes with beach grass, driftwood,
//  conifer headlands, sea stacks, the parking strip), the Whale (a sperm whale; also torn into halves after the blast),
//  Chunks (ballistic blubber, a pure function of time since the blast), Car (a 1970 sedan, crushable), Bus, HwyTruck,
//  dynamite cases, the plunger, the highway sign, Kitchen (the jelly), Park (the memorial sign), Dealer (the lot).
import * as THREE from "three";
import { lam, Batch, V, quad } from "./build";
import { ctex } from "./paint";
import { NOINK } from "./ink";
import { SHORE, WHALE, LOT, SIGN, KITCHEN, PARK, DEALER } from "./places";

const TAU = Math.PI * 2;
export const box = (x0: number, x1: number, y0: number, y1: number, z0: number, z1: number) =>
  new THREE.BoxGeometry(x1 - x0, y1 - y0, z1 - z0).translate((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2);
export const cylY = (r: number, y0: number, y1: number, x: number, z: number, seg = 24, r2 = r) =>
  new THREE.CylinderGeometry(r2, r, y1 - y0, seg).translate(x, (y0 + y1) / 2, z);
const add = (g: THREE.BufferGeometry, m: THREE.Material | THREE.Material[], parent: THREE.Object3D, cast = true) => {
  const mesh = new THREE.Mesh(g, m); mesh.castShadow = cast; mesh.receiveShadow = true; parent.add(mesh); return mesh;
};
const hdr = (r: number, g: number, b: number) => new THREE.MeshBasicMaterial({ color: new THREE.Color(r, g, b), fog: false });
const floorQ = (x0: number, x1: number, z0: number, z1: number, y: number, s: number) => {
  const g = new THREE.BufferGeometry(), P = [x0, y, z1, x1, y, z1, x1, y, z0, x0, y, z1, x1, y, z0, x0, y, z0];
  g.setAttribute("position", new THREE.Float32BufferAttribute(P, 3));
  const uv: number[] = []; for (let i = 0; i < 6; i++) uv.push(P[i * 3] / s, P[i * 3 + 2] / s);
  g.setAttribute("uv", new THREE.Float32BufferAttribute(uv, 2)); g.computeVertexNormals(); return g;
};
const limb = (a: THREE.Vector3, b: THREE.Vector3, ra: number, rb: number, seg = 8) => {
  const d = b.clone().sub(a), L = d.length();
  const g = new THREE.CylinderGeometry(rb, ra, L, seg);
  g.translate(0, L / 2, 0);
  const q = new THREE.Quaternion().setFromUnitVectors(V(0, 1, 0), d.normalize());
  return g.applyQuaternion(q).translate(a.x, a.y, a.z);
};
const room = (parent: THREE.Object3D, cx: number, cz: number, w: number, d: number, h: number, floor: THREE.Material, wall: THREE.Material, ceil?: THREE.Material) => {
  const b = new Batch(), x0 = cx - w / 2, x1 = cx + w / 2, z0 = cz - d / 2, z1 = cz + d / 2;
  b.add(floorQ(x0, x1, z0, z1 + 6, 0, 2), floor);
  b.add(quad(V(x0, 0, z0), V(x1, 0, z0), V(x1, h, z0), V(x0, h, z0), w / 4, 1), wall);
  b.add(quad(V(x0, 0, z1), V(x0, 0, z0), V(x0, h, z0), V(x0, h, z1), d / 4, 1), wall);
  b.add(quad(V(x1, 0, z0), V(x1, 0, z1), V(x1, h, z1), V(x1, h, z0), d / 4, 1), wall);
  if (ceil) b.add(quad(V(x0, h, z0), V(x1, h, z0), V(x1, h, z1), V(x0, h, z1), w / 3, d / 3), ceil);
  b.build(parent, false);
};
export const hh = (i: number, s = 0) => { const v = Math.sin(i * 127.1 + s * 311.7) * 43758.5453; return v - Math.floor(v); };

// ---------------- painted textures ----------------
/** dry beach sand: pale warm blotches, flecks, footprints and wind ripples (8 m tile) */
const sandTex = () => ctex("sandOr", 1024, 1024, (g, r) => {
  g.fillStyle = "#e3cfa6"; g.fillRect(0, 0, 1024, 1024);
  for (let i = 0; i < 380; i++) { const x = r() * 1024, y = r() * 1024, s = 40 + r() * 140; const gr = g.createRadialGradient(x, y, 1, x, y, s);
    const c = r() < 0.5 ? "rgba(240,224,190," : "rgba(200,176,132,"; gr.addColorStop(0, c + "0.5)"); gr.addColorStop(1, c + "0)"); g.fillStyle = gr; g.fillRect(x - s, y - s, 2 * s, 2 * s); }
  g.strokeStyle = "rgba(186,160,118,0.35)"; g.lineWidth = 3;
  for (let i = 0; i < 70; i++) { const y = r() * 1024, x = r() * 1024; g.beginPath(); g.moveTo(x, y); g.bezierCurveTo(x + 60, y - 10, x + 120, y + 12, x + 190, y); g.stroke(); }
  for (let i = 0; i < 1400; i++) { g.fillStyle = r() < 0.5 ? "rgba(150,124,92,0.5)" : "rgba(255,248,230,0.6)"; g.fillRect(r() * 1024, r() * 1024, 2 + r() * 3, 2 + r() * 2); }
});
/** wet sand at the waterline: darker, glossy streaks (8 m tile) */
const wetTex = () => ctex("wetSand", 1024, 1024, (g, r) => {
  g.fillStyle = "#b9a17c"; g.fillRect(0, 0, 1024, 1024);
  for (let i = 0; i < 220; i++) { const x = r() * 1024, y = r() * 1024, s = 60 + r() * 160; const gr = g.createRadialGradient(x, y, 1, x, y, s);
    gr.addColorStop(0, r() < 0.5 ? "rgba(214,200,170,0.45)" : "rgba(160,138,104,0.45)"); gr.addColorStop(1, "rgba(0,0,0,0)"); g.fillStyle = gr; g.fillRect(x - s, y - s, 2 * s, 2 * s); }
  g.strokeStyle = "rgba(235,232,220,0.4)"; g.lineWidth = 4;
  for (let i = 0; i < 40; i++) { const y = r() * 1024; g.beginPath(); g.moveTo(0, y); g.bezierCurveTo(300, y + 20, 700, y - 20, 1024, y); g.stroke(); }
});
/** the Pacific: deep teal with lighter crest strokes (20 m tile) */
const seaTex = () => ctex("seaOr", 1024, 1024, (g, r) => {
  g.fillStyle = "#4a8aa4"; g.fillRect(0, 0, 1024, 1024);
  for (let i = 0; i < 260; i++) { const x = r() * 1024, y = r() * 1024, s = 50 + r() * 150; const gr = g.createRadialGradient(x, y, 1, x, y, s);
    gr.addColorStop(0, r() < 0.5 ? "rgba(90,160,180,0.25)" : "rgba(40,96,122,0.25)"); gr.addColorStop(1, "rgba(0,0,0,0)"); g.fillStyle = gr; g.fillRect(x - s, y - s, 2 * s, 2 * s); }
  g.lineCap = "round";
  for (let i = 0; i < 160; i++) { const x = r() * 1024, y = r() * 1024, l = 20 + r() * 70; g.strokeStyle = r() < 0.7 ? "rgba(220,240,244,0.3)" : "rgba(150,200,212,0.3)"; g.lineWidth = 3 + r() * 3;
    g.beginPath(); g.moveTo(x, y); g.quadraticCurveTo(x + l / 2, y - 6, x + l, y); g.stroke(); }
});
/** a band of surf foam (alpha): white lacy front, bubbles behind */
const foamTex = () => ctex("foam", 1024, 128, (g, r) => {
  g.clearRect(0, 0, 1024, 128);
  g.fillStyle = "rgba(255,255,255,0.95)";
  g.beginPath(); g.moveTo(0, 128); for (let x = 0; x <= 1024; x += 16) g.lineTo(x, 50 + 14 * Math.sin(x * 0.03) + 10 * r()); g.lineTo(1024, 128); g.closePath(); g.fill();
  g.fillStyle = "rgba(220,238,242,0.9)";
  for (let i = 0; i < 260; i++) { g.beginPath(); g.ellipse(r() * 1024, 20 + r() * 40, 3 + r() * 9, 2 + r() * 4, 0, 0, TAU); g.fill(); }
});
/** the whale's skin along its length: slate grey with long wrinkle furrows and pale scars (u along the body) */
const whaleTex = () => ctex("whaleSkin", 2048, 512, (g0, r) => {
  const g = g0; g.canvas.width = 4096; g.canvas.height = 1024; g.scale(2, 2);
  g.fillStyle = "#9a9ea6"; g.fillRect(0, 0, 2048, 512);
  for (let i = 0; i < 110; i++) { g.fillStyle = r() < 0.5 ? "rgba(170,174,182,0.5)" : "rgba(128,131,140,0.45)"; g.beginPath(); g.ellipse(r() * 2048, r() * 512, 30 + r() * 60, 14 + r() * 24, r() * 0.4, 0, TAU); g.fill(); }
  g.lineCap = "round";
  for (let i = 0; i < 160; i++) { const x = r() * 2048, y = r() * 512, l = 40 + r() * 120; g.strokeStyle = r() < 0.6 ? "rgba(100,102,112,0.3)" : "rgba(196,198,204,0.18)"; g.lineWidth = 2 + r() * 2;
    g.beginPath(); g.moveTo(x, y); g.bezierCurveTo(x + l * 0.3, y + 8 * (r() - 0.5), x + l * 0.7, y + 8 * (r() - 0.5), x + l, y + 4 * (r() - 0.5)); g.stroke(); }
  for (let i = 0; i < 90; i++) { g.fillStyle = r() < 0.5 ? "rgba(214,212,206,0.35)" : "rgba(110,112,122,0.3)"; g.beginPath(); g.ellipse(r() * 2048, r() * 512, 6 + r() * 14, 4 + r() * 8, r() * 3, 0, TAU); g.fill(); }
  for (let i = 0; i < 6; i++) { g.strokeStyle = "rgba(230,228,222,0.35)"; g.lineWidth = 3; const x = r() * 2048, y = r() * 512; g.beginPath(); g.moveTo(x, y); g.lineTo(x + 30 + r() * 40, y + (r() - 0.5) * 30); g.stroke(); }
});
/** torn blubber: pink-white fat with red-brown streaks */
const meatTex = () => ctex("blubberMeat", 512, 512, (g, r) => {
  g.fillStyle = "#f2b49c"; g.fillRect(0, 0, 512, 512);
  for (let i = 0; i < 160; i++) { const x = r() * 512, y = r() * 512, s = 20 + r() * 60; const gr = g.createRadialGradient(x, y, 1, x, y, s);
    gr.addColorStop(0, r() < 0.5 ? "rgba(200,110,100,0.5)" : "rgba(250,226,214,0.6)"); gr.addColorStop(1, "rgba(0,0,0,0)"); g.fillStyle = gr; g.fillRect(x - s, y - s, 2 * s, 2 * s); }
});
/** beach grass tufts (alpha card) */
const grassTuftTex = () => ctex("beachGrass", 512, 512, (g, r) => {
  g.clearRect(0, 0, 512, 512); g.lineCap = "round";
  for (let i = 0; i < 46; i++) {
    const x = 120 + r() * 270, lean = (r() - 0.5) * 220, h = 260 + r() * 220;
    g.strokeStyle = r() < 0.5 ? "#8fa05a" : r() < 0.5 ? "#a8b26a" : "#6f8a4a"; g.lineWidth = 7 + r() * 5;
    g.beginPath(); g.moveTo(x, 512); g.quadraticCurveTo(x + lean * 0.3, 512 - h * 0.6, x + lean, 512 - h); g.stroke();
  }
});
const stripeTex = (key: string, a: string, b: string, n: number) => ctex(key, 256, 256, (g) => {
  for (let i = 0; i < n; i++) { g.fillStyle = i % 2 ? b : a; g.fillRect((i * 256) / n, 0, 256 / n + 1, 256); }
});
/** a road sign panel with text lines (unlit: painted signs under a side sun go grey and unreadable) */
const signTex = (key: string, w: number, h: number, bg: string, fg: string, lines: [string, number][], border = true, extra?: (g: CanvasRenderingContext2D) => void) =>
  ctex(key, w, h, (g) => {
    g.fillStyle = bg; g.fillRect(0, 0, w, h);
    if (border) { g.strokeStyle = fg; g.lineWidth = Math.round(h * 0.035); const m = h * 0.05; g.beginPath(); g.roundRect(m, m, w - 2 * m, h - 2 * m, h * 0.06); g.stroke(); }
    extra?.(g);
    g.fillStyle = fg; g.textAlign = "center"; g.textBaseline = "middle";
    const tot = lines.reduce((s, [, sz]) => s + sz * 1.15, 0);
    let y = h / 2 - tot / 2;
    for (const [t, sz] of lines) { g.font = `900 ${sz}px Arial, sans-serif`; y += sz * 0.575; g.fillText(t, w / 2, y, w * 0.86); y += sz * 0.575; }
  });
const whaleIcon = (g: CanvasRenderingContext2D, x: number, y: number, s: number, col = "#4f5a6a", smile = true) => {
  g.save(); g.translate(x, y); g.scale(s, s);
  g.fillStyle = col; g.strokeStyle = "#1d1a22"; g.lineWidth = 6;
  g.beginPath(); g.moveTo(-90, 10); g.quadraticCurveTo(-100, -50, -30, -55); g.lineTo(80, -50); g.quadraticCurveTo(110, -45, 110, 0); g.quadraticCurveTo(105, 40, 40, 42); g.lineTo(-60, 40);
  g.lineTo(-120, 70); g.lineTo(-115, 20); g.lineTo(-140, -20); g.closePath(); g.fill(); g.stroke();
  g.fillStyle = "#ffffff"; g.beginPath(); g.arc(70, -18, 9, 0, TAU); g.fill(); g.fillStyle = "#1d1a22"; g.beginPath(); g.arc(72, -17, 4.5, 0, TAU); g.fill();
  if (smile) { g.beginPath(); g.arc(70, 8, 22, 0.2, 1.4); g.stroke(); }
  // the spout
  g.strokeStyle = "#5fb0e0"; g.lineWidth = 7; g.beginPath(); g.moveTo(40, -58); g.quadraticCurveTo(30, -100, 0, -110); g.moveTo(40, -58); g.quadraticCurveTo(60, -100, 85, -108); g.stroke();
  g.restore();
};
export const hwySignTex = () => signTex("hwySign", 768, 512, "#1f6b45", "#ffffff", [["OREGON", 120], ["STATE HIGHWAY", 92]]);
export const parkSignTex = () => ctex("parkSign", 1024, 640, (g) => {
  g.fillStyle = "#7a4e2c"; g.fillRect(0, 0, 1024, 640);
  for (let y = 0; y < 640; y += 80) { g.fillStyle = y % 160 ? "#83552f" : "#6f4526"; g.fillRect(0, y, 1024, 76); g.fillStyle = "#4a2e18"; g.fillRect(0, y + 76, 1024, 4); }
  g.strokeStyle = "#f2e2b8"; g.lineWidth = 14; g.strokeRect(28, 28, 968, 584);
  whaleIcon(g, 512, 200, 1.25, "#f2e2b8", true);
  g.fillStyle = "#f6e8c0"; g.textAlign = "center"; g.textBaseline = "middle";
  g.font = "900 96px Georgia, serif"; g.fillText("EXPLODING WHALE", 512, 380, 900);
  g.font = "900 80px Georgia, serif"; g.fillText("MEMORIAL PARK", 512, 495, 860);
});
export const bannerTex = () => ctex("dealBanner", 2048, 512, (g) => {
  g.fillStyle = "#f6d23a"; g.fillRect(0, 0, 2048, 512);
  g.fillStyle = "#d9382e"; g.fillRect(0, 0, 2048, 44); g.fillRect(0, 468, 2048, 44);
  for (let x = 0; x < 2048; x += 64) { g.fillStyle = "#ffffff"; g.beginPath(); g.arc(x + 32, 22, 9, 0, TAU); g.arc(x + 32, 490, 9, 0, TAU); g.fill(); }
  whaleIcon(g, 250, 270, 1.6);
  whaleIcon(g, 1800, 270, 1.6);
  g.fillStyle = "#d9382e"; g.strokeStyle = "#ffffff"; g.lineWidth = 14; g.textAlign = "center"; g.textBaseline = "middle";
  g.font = "italic 900 132px Arial, sans-serif"; g.strokeText("GET A WHALE", 1024, 180); g.fillText("GET A WHALE", 1024, 180);
  g.font = "italic 900 150px Arial, sans-serif"; g.strokeText("OF A DEAL!", 1024, 345); g.fillText("OF A DEAL!", 1024, 345);
});
const dynTex = () => signTex("dynCase", 512, 320, "#c9a06a", "#b8231e", [["DYNAMITE", 92], ["HIGH EXPLOSIVES", 44]], true, (g) => {
  g.fillStyle = "rgba(120,80,40,0.25)"; for (let y = 0; y < 320; y += 64) g.fillRect(0, y, 512, 4);
});
const tvTex = () => ctex("tvLogo", 256, 128, (g) => { g.fillStyle = "#e9ecef"; g.fillRect(0, 0, 256, 128); g.fillStyle = "#1f2a44"; g.font = "900 78px Arial"; g.textAlign = "center"; g.textBaseline = "middle"; g.fillText("TV 2", 128, 68); });
const wallpaperTex = () => ctex("kitchenPaper", 512, 512, (g) => {
  g.fillStyle = "#f2e2a8"; g.fillRect(0, 0, 512, 512);
  for (let y = 0; y < 512; y += 64) for (let x = (y / 64) % 2 ? 32 : 0; x < 512; x += 64) { g.fillStyle = "#e48a3a"; g.beginPath(); g.arc(x, y, 12, 0, TAU); g.fill(); g.fillStyle = "#7aa64a"; g.beginPath(); g.ellipse(x + 16, y + 10, 9, 5, 0.6, 0, TAU); g.fill(); }
  g.fillStyle = "#c86a3a"; g.fillRect(0, 380, 512, 132); g.fillStyle = "#f6f0e0"; g.fillRect(0, 376, 512, 8);
});
const checkTex = () => ctex("checkCloth", 256, 256, (g) => {
  g.fillStyle = "#ffffff"; g.fillRect(0, 0, 256, 256);
  for (let i = 0; i < 8; i++) { g.fillStyle = "rgba(210,54,48,0.55)"; g.fillRect(i * 32, 0, 16, 256); g.fillRect(0, i * 32, 256, 16); }
});
const lino = () => ctex("lino", 512, 512, (g) => {
  for (let y = 0; y < 8; y++) for (let x = 0; x < 8; x++) { g.fillStyle = (x + y) % 2 ? "#f2efe6" : "#3a5a7a"; g.fillRect(x * 64, y * 64, 64, 64); }
});
const showroomTex = () => ctex("showroom", 1024, 512, (g) => {
  g.fillStyle = "#f2efe6"; g.fillRect(0, 0, 1024, 512);
  for (let x = 40; x < 1024; x += 240) { const gr = g.createLinearGradient(0, 120, 0, 480); gr.addColorStop(0, "#9fc4e0"); gr.addColorStop(1, "#dcecf6"); g.fillStyle = gr; g.fillRect(x, 140, 200, 340);
    g.fillStyle = "#3a5a7a"; g.fillRect(x + 30, 380, 140, 60); g.fillStyle = "#1d1a22"; g.beginPath(); g.arc(x + 60, 440, 16, 0, TAU); g.arc(x + 140, 440, 16, 0, TAU); g.fill(); }
  g.fillStyle = "#d9382e"; g.fillRect(0, 0, 1024, 100);
  
});

// ---------------- the beach ----------------
const conifer = (b: Batch, x: number, z: number, h: number, seed: number, y = 0) => {
  const trunk = lam("coniferTrunk", () => ({ color: "#6a4a34" }));
  b.add(cylY(0.05 * h, y, y + 0.35 * h, x, z, 6), trunk);
  for (let k = 0; k < 3; k++) {
    const r = (0.32 - k * 0.07) * h, y0 = y + (0.22 + k * 0.22) * h;
    b.add(new THREE.ConeGeometry(r, 0.42 * h, 9).translate(x + (hh(seed, k) - 0.5) * 0.05 * h, y0 + 0.21 * h, z), lam("conifer" + ((seed + k) % 3), () => ({ color: ["#3f6a48", "#4a7a52", "#355e40"][(seed + k) % 3] })));
  }
};
const driftwood = (b: Batch, x: number, z: number, L: number, yaw: number, r: number) => {
  const g = new THREE.CylinderGeometry(r * 0.85, r, L, 10).rotateZ(Math.PI / 2).rotateY(yaw).translate(x, r * 0.8, z);
  b.add(g, lam("driftwood", () => ({ color: "#a89a88" })));
  b.add(limb(V(x + Math.cos(yaw) * L * 0.4, r, z - Math.sin(yaw) * L * 0.4), V(x + Math.cos(yaw) * L * 0.5, r * 3.5, z - Math.sin(yaw) * L * 0.5 + 0.4), r * 0.4, r * 0.15, 6), lam("driftwood", () => ({ color: "#a89a88" })));
};
export class Beach {
  root = new THREE.Group();
  private foam: THREE.Mesh[] = [];
  private seaMap: THREE.Texture;
  constructor(parent: THREE.Object3D) {
    parent.add(this.root);
    const b = new Batch();
    b.add(floorQ(-900, 900, SHORE + 7, 600, 0, 8), lam("sand", () => ({ map: sandTex() })));
    b.add(floorQ(-900, 900, SHORE - 1, SHORE + 7, 0, 8), lam("wetSand", () => ({ map: wetTex() })));
    // dunes: long low mounds behind the parking strip and at the sides, conifers on top
    const duneM = lam("dune", () => ({ map: sandTex() }));
    for (let i = 0; i < 26; i++) {
      const x = -260 + i * 22 + hh(i, 1) * 8, z = LOT.z1 + 14 + hh(i, 2) * 12, s = 9 + hh(i, 3) * 8;
      b.add(new THREE.SphereGeometry(s, 18, 10, 0, TAU, 0, Math.PI / 2).scale(1.6, 0.45, 1).translate(x, 0, z), duneM);
      if (i % 2 === 0) conifer(b, x + 2, z + 4, 9 + hh(i, 4) * 6, i, s * 0.3);
    }
    for (let i = 0; i < 18; i++) { const x = -180 + hh(i, 5) * 360, z = LOT.z1 + 40 + hh(i, 6) * 120; if (Math.abs(x - 30) < 10 && z < LOT.z1 + 50) continue; conifer(b, x, z, 12 + hh(i, 7) * 10, i + 40, 3); }
    for (let i = 0; i < 60; i++) { const a = (i / 60) * Math.PI + Math.PI * 0.02, d = 420 + (i % 3) * 30; conifer(b, Math.cos(a) * d * 1.4, 70 + Math.sin(a) * 160, 16 + (i % 4) * 4, i + 80, 6); }
    // headlands: big green bluffs reaching into the sea, both ends of the beach
    const bluff = lam("bluff", () => ({ color: "#5a7a4a" })), rock = lam("rockOr", () => ({ color: "#5d5650" }));
    for (const [x, z, s] of [[-330, -40, 60], [-420, -110, 80], [360, -60, 70], [470, -140, 90]] as const) {
      b.add(new THREE.SphereGeometry(s, 20, 12, 0, TAU, 0, Math.PI / 2).scale(1.3, 0.75, 1).translate(x, -2, z), bluff);
      b.add(new THREE.CylinderGeometry(s * 1.15, s * 1.25, 10, 20).translate(x, 2, z), rock);
    }
    for (const [x, z, s] of [[-140, -150, 9], [-120, -170, 6], [190, -210, 12], [230, -190, 7], [90, -300, 10]] as const) b.add(new THREE.DodecahedronGeometry(s, 0).scale(0.8, 1.4, 0.8).translate(x, s * 0.6, z), rock);
    // driftwood logs along the high tide line and at the lot edge
    for (let i = 0; i < 22; i++) driftwood(b, -120 + i * 12 + hh(i, 8) * 6, 28 + hh(i, 9) * 8, 4 + hh(i, 10) * 4, hh(i, 11) * 0.6 - 0.3, 0.22 + hh(i, 12) * 0.12);
    for (let x = LOT.x0; x < LOT.x1; x += 4.6) driftwood(b, x, LOT.z0 - 1.6, 4.2, 0, 0.2);
    b.build(this.root, true);
    // the sea + moving foam bands
    this.seaMap = seaTex(); this.seaMap.repeat.set(1, 1);
    const sea = new THREE.Mesh(floorQ(-1200, 1200, -1200, SHORE - 1, 0, 20), lam("sea", () => ({ map: this.seaMap })));
    sea.receiveShadow = true; this.root.add(sea);
    for (let k = 0; k < 3; k++) {
      const m = new THREE.Mesh(new THREE.PlaneGeometry(1600, 3 + k).rotateX(-Math.PI / 2), new THREE.MeshLambertMaterial({ map: foamTex(), transparent: true, depthWrite: false }));
      (m.material as THREE.MeshLambertMaterial).map!.repeat.set(30, 1);
      m.layers.set(NOINK); m.position.set(0, 0.03 + k * 0.004, SHORE - 2 - k * 7); this.foam.push(m); this.root.add(m);
    }
    // beach grass on the dunes and along the lot
    const pos: number[] = [], uv: number[] = [], nrm: number[] = [];
    for (let i = 0; i < 900; i++) {
      const x = -200 + hh(i, 21) * 400, z = LOT.z1 + 4 + hh(i, 22) * 40;
      const h = 0.7 + 0.5 * hh(i, 23), w = 1.0, a = hh(i, 24) * Math.PI, y = Math.max(0, 0.3 * (z - LOT.z1 - 4));
      for (const da of [0, Math.PI / 2]) {
        const c = Math.cos(a + da) * w / 2, s = Math.sin(a + da) * w / 2;
        const P = [[x - c, y - 0.1, z - s], [x + c, y - 0.1, z + s], [x + c, y + h, z + s], [x - c, y + h, z - s]];
        for (const t of [0, 1, 2, 0, 2, 3]) { pos.push(...P[t]); uv.push(t === 1 || t === 2 ? 1 : 0, t >= 2 ? 1 : 0); nrm.push(0, 1, 0); }
      }
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3)); g.setAttribute("uv", new THREE.Float32BufferAttribute(uv, 2)); g.setAttribute("normal", new THREE.Float32BufferAttribute(nrm, 3));
    const gm = new THREE.Mesh(g, lam("beachGrassMat", () => ({ map: grassTuftTex(), alphaTest: 0.5, side: THREE.DoubleSide })));
    gm.layers.set(NOINK); gm.receiveShadow = true; this.root.add(gm);
    // the highway sign
    const sb = new Batch(), steel = lam("signPost", () => ({ color: "#9aa0a8" }));
    for (const dx of [-0.7, 0.7]) sb.add(cylY(0.05, 0, 2.6, SIGN.x + dx, SIGN.z, 8), steel);
    sb.build(this.root, true);
    const sign = new THREE.Mesh(new THREE.PlaneGeometry(2.4, 1.6), new THREE.MeshBasicMaterial({ map: hwySignTex(), side: THREE.DoubleSide }));
    sign.position.set(SIGN.x, 2.55, SIGN.z + 0.1); this.root.add(sign);
    const back = new THREE.Mesh(box(SIGN.x - 1.22, SIGN.x + 1.22, 1.73, 3.37, SIGN.z - 0.03, SIGN.z + 0.03), steel); back.castShadow = true; this.root.add(back);
  }
  update(t: number) {
    this.seaMap.offset.set(t * 0.004, t * 0.01);
    this.foam.forEach((m, k) => { m.position.z = SHORE - 1.5 - k * 6 + 2.2 * Math.sin(t * 0.7 + k * 1.9); (m.material as THREE.MeshLambertMaterial).map!.offset.x = t * 0.01 * (k % 2 ? 1 : -1); });
  }
}

// ---------------- the whale ----------------
/** section half-sizes along the body, u = 0 at the fluke stock, 1 at the blunt snout: [half height, half width, squareness] */
const SEC = (u: number): [number, number, number] => {
  const body = u < 0.62 ? 0.18 + 1.25 * Math.sin(Math.min(1, u / 0.62) * Math.PI / 2) ** 1.4 : 1.43;
  const hy = u > 0.94 ? 1.43 * Math.sqrt(Math.max(0, 1 - ((u - 0.94) / 0.06) ** 2)) * 0.98 + 0.02 : body;
  const hz = hy * (u > 0.62 ? 0.82 : 0.92);
  const n = u > 0.6 ? 4.2 : 2.2;
  return [hy, hz, n];
};
const sePt = (a: number, hy: number, hz: number, n: number): [number, number] => {
  const c = Math.cos(a), s = Math.sin(a);
  return [hz * Math.sign(c) * Math.abs(c) ** (2 / n), hy * Math.sign(s) * Math.abs(s) ** (2 / n)];
};
/** tube from u0 to u1 (length L along +x centred at 0), the belly flattened into the sand */
const whaleTube = (u0: number, u1: number, L = WHALE.len, nu = 70, na = 40) => {
  const P: number[] = [], UV: number[] = [], I: number[] = [];
  for (let i = 0; i <= nu; i++) {
    const u = u0 + (u1 - u0) * (i / nu), [hy, hz, n] = SEC(u), x = -L / 2 + u * L;
    for (let j = 0; j <= na; j++) {
      const a = (j / na) * TAU, [z, y0] = sePt(a, hy, hz, n);
      const y = Math.max(y0, -hy * 0.55) + hy * 0.75; // sunk: the flat belly sits in the sand
      P.push(x, y, z); UV.push(u, j / na);
    }
  }
  for (let i = 0; i < nu; i++) for (let j = 0; j < na; j++) { const a = i * (na + 1) + j, b = a + na + 1; I.push(a, b, a + 1, b, b + 1, a + 1); }
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute(P, 3)); g.setAttribute("uv", new THREE.Float32BufferAttribute(UV, 2)); g.setIndex(I); g.computeVertexNormals();
  return g;
};
/** a torn end cap at u: a ragged disc of pink blubber */
const tornCap = (u: number, dir: number, L = WHALE.len) => {
  const [hy, hz, n] = SEC(u), x = -L / 2 + u * L, pts: THREE.Vector2[] = [];
  for (let j = 0; j < 30; j++) { const a = (j / 30) * TAU, [z, y0] = sePt(a, hy, hz, n), r = 0.82 + 0.18 * hh(j, 3); pts.push(new THREE.Vector2(z * r, (Math.max(y0, -hy * 0.55) + hy * 0.75) * r)); }
  const g = new THREE.ShapeGeometry(new THREE.Shape(pts)).rotateY(dir > 0 ? Math.PI / 2 : -Math.PI / 2).translate(x, 0, 0);
  return g;
};
export class Whale {
  root = new THREE.Group();
  whole = new THREE.Group();
  /** after the blast: the tail half pushed back, the head lump, a scorched crater */
  remains = new THREE.Group();
  flyer = new THREE.Group();
  constructor(parent: THREE.Object3D) {
    parent.add(this.root); this.root.add(this.whole, this.remains, this.flyer);
    this.root.position.set(WHALE.x, 0, WHALE.z);
    const skin = lam("whaleSkin", () => ({ map: whaleTex() })), skin2 = lam("whaleSkin2", () => ({ map: whaleTex(), side: THREE.DoubleSide })), belly = lam("whaleBelly", () => ({ color: "#c9c4bc" })), meat = lam("blubberMeat", () => ({ map: meatTex(), side: THREE.DoubleSide, emissive: new THREE.Color("#7a3020") }));
    const W = this.whole;
    add(whaleTube(0, 1), skin, W);
    // the narrow underslung jaw: a pale rod under the front of the head, teeth along it
    add(new THREE.CylinderGeometry(0.22, 0.32, 4.6, 12).rotateZ(Math.PI / 2).scale(1, 0.7, 1).translate(WHALE.len / 2 - 2.5, 0.25, 0.85), belly, W);
    for (let k = 0; k < 9; k++) add(new THREE.ConeGeometry(0.05, 0.14, 6).translate(WHALE.len / 2 - 0.6 - k * 0.42, 0.48, 0.85), lam("tooth", () => ({ color: "#f4efe2" })), W);
    // the small eye just above the corner of the mouth, a fin, the flukes
    for (const s of [-1, 1]) { W.add(new THREE.Mesh(new THREE.SphereGeometry(0.2, 14, 10).scale(1, 1, 0.5).translate(WHALE.len / 2 - 4.4, 1.0, s * 1.2), lam("whaleEyeW", () => ({ color: "#f4f1ea" }))));
      W.add(new THREE.Mesh(new THREE.SphereGeometry(0.1, 12, 8).scale(1, 1, 0.5).translate(WHALE.len / 2 - 4.33, 1.0, s * 1.29), lam("whaleEye", () => ({ color: "#1d1a22" })))); }
    // the long mouth line along the underside of the head
    for (const s of [-1, 1]) add(new THREE.CylinderGeometry(0.035, 0.035, 4.2, 6).rotateZ(Math.PI / 2 - 0.04).translate(WHALE.len / 2 - 2.4, 0.62, s * 1.17), lam("mouthLine", () => ({ color: "#3a3540" })), W);
    add(new THREE.SphereGeometry(0.7, 12, 8).scale(1, 0.25, 0.5).rotateY(0.4).translate(WHALE.len / 2 - 5.6, 0.5, 1.25), skin, W);
    const fl = new THREE.Shape([new THREE.Vector2(0, 0), new THREE.Vector2(-1.2, 2.3), new THREE.Vector2(-0.5, 2.4), new THREE.Vector2(0.45, 0.2), new THREE.Vector2(0.45, -0.2), new THREE.Vector2(-0.5, -2.4), new THREE.Vector2(-1.2, -2.3)]);
    add(new THREE.ExtrudeGeometry(fl, { depth: 0.18, bevelEnabled: false }).rotateX(Math.PI / 2).translate(-WHALE.len / 2 - 0.1, 0.42, 0), skin2, W);
    // the dorsal hump ridge (sperm whales have knuckles instead of a tall fin)
    for (let k = 0; k < 4; k++) add(new THREE.SphereGeometry(0.28 - k * 0.04, 10, 6).scale(1.4, 0.6, 0.8).translate(-1.6 - k * 0.9, SEC(0.38 - k * 0.064)[0] * 1.75 - 0.05, 0), skin, W);
    // remains: the tail half thrown back and rolled, the head lump, both torn open; a dark crater between
    const R = this.remains;
    const tail = new THREE.Group(); add(whaleTube(0, 0.42), skin, tail); add(tornCap(0.42, 1), meat, tail);
    add(new THREE.ExtrudeGeometry(fl, { depth: 0.18, bevelEnabled: false }).rotateX(Math.PI / 2).translate(-WHALE.len / 2 - 0.1, 0.42, 0), skin2, tail);
    this.flyer.visible = false;
    tail.position.set(-2.4, -0.15, -0.8); tail.rotation.set(0.25, 0.25, 0.05); R.add(tail); this.tailH = tail;
    const headL = new THREE.Group(); add(whaleTube(0.74, 1), skin, headL); add(tornCap(0.74, -1), meat, headL);
    headL.position.set(2.2, -0.35, 1.0); headL.rotation.set(-0.35, -0.3, -0.08); R.add(headL); this.headH = headL;
    for (let k = 0; k < 4; k++) { const e = new THREE.Mesh(new THREE.SphereGeometry(k % 2 ? 0.1 : 0.2, 12, 8).scale(1, 1, 0.5).translate(WHALE.len / 2 - (k % 2 ? 2.93 : 3.0), 1.0, (k < 2 ? 1 : -1) * (k % 2 ? 1.29 : 1.2)), lam(k % 2 ? "whaleEye" : "whaleEyeW", () => ({ color: k % 2 ? "#1d1a22" : "#f4efe2" }))); headL.add(e); }
    const crater = new THREE.Mesh(new THREE.CircleGeometry(4.2, 32).rotateX(-Math.PI / 2).translate(0.2, 0.04, 0), lam("crater", () => ({ color: "#7a6450" })));
    crater.receiveShadow = true; R.add(crater);
    for (let k = 0; k < 14; k++) { const a = hh(k, 5) * TAU, d = 2.5 + hh(k, 6) * 4; add(new THREE.DodecahedronGeometry(0.3 + hh(k, 7) * 0.5, 0).scale(1.3, 0.6, 1).translate(Math.cos(a) * d, 0.15, Math.sin(a) * d), k % 3 ? meat : skin, R); }
    R.visible = false;
  }
  /** the flukes + tail stock thrown out of the blast (s = seconds since the blast) */
  fly(s: number, visible: boolean) {
    const F = this.flyer; F.visible = false && visible && s > 0;
    if (!F.visible) return;
    const tl = (14 + Math.sqrt(14 * 14 + 2 * 9.8 * 1.5)) / 9.8, k = Math.min(s, tl);
    F.position.set(-4 + 5.5 * k, Math.max(0.6, 2 + 14 * k - 4.9 * k * k), 1 + 9 * k);
    F.rotation.order = "ZYX"; F.rotation.set(Math.PI / 2, 0.35 * Math.sin(k * 3), 2.6 * k); F.scale.setScalar(2.1);
  }
  private tailH!: THREE.Group; private headH!: THREE.Group;
  /** the blast: the two halves are thrown up and apart in big arcs and land where the remains lie (s seconds) */
  burst(s: number) {
    this.remains.visible = true;
    const u = Math.min(1, Math.max(0, s / 2.6)), arc = 4 * u * (1 - u);
    this.tailH.position.set(-2.4 * u - 1.5 * arc, -0.15 * u + 9 * arc, -0.8 * u + 3 * arc); this.tailH.rotation.set(0.25 * u, 0.25 * u, 0.05 * u + Math.PI * 2 * u);
    this.headH.position.set(2.2 * u + 2.0 * arc, -0.35 * u + 11 * arc, 1.0 * u + 4 * arc); this.headH.rotation.set(-0.35 * u, -0.3 * u, -0.08 * u - Math.PI * 2 * u);
  }
  set(state: "whole" | "gone" | "remains") {
    this.whole.visible = state === "whole"; this.remains.visible = state === "remains";
    if (state === "remains") { this.tailH.position.set(-2.4, -0.15, -0.8); this.tailH.rotation.set(0.25, 0.25, 0.05); this.headH.position.set(2.2, -0.35, 1.0); this.headH.rotation.set(-0.35, -0.3, -0.08); }
  }
}

// ---------------- the flying blubber ----------------
/** a lumpy rounded blob (unit radius) with a fixed bumpy surface */
export const blobGeo = (r = 1, seed = 1) => {
  const g = new THREE.SphereGeometry(r, 14, 10), P = g.attributes.position as THREE.BufferAttribute, v = new THREE.Vector3();
  for (let i = 0; i < P.count; i++) {
    v.fromBufferAttribute(P, i);
    const n = 1 + 0.16 * Math.sin(v.x * 3.1 + seed) * Math.cos(v.y * 2.7 + seed * 2) + 0.1 * Math.sin(v.z * 4.3 + seed * 3);
    v.multiplyScalar(n); P.setXYZ(i, v.x, v.y, v.z);
  }
  g.computeVertexNormals(); return g;
};
export type ChunkDef = { v: [number, number, number]; s: number; spin: [number, number, number]; skin: boolean; delay: number };
const G = 9.8;
/** ballistic chunks thrown from the whale at the blast; their landing spots are fixed (rest on the sand afterwards) */
export class Chunks {
  mesh: THREE.InstancedMesh; skinMesh: THREE.InstancedMesh;
  defs: ChunkDef[] = [];
  private m = new THREE.Matrix4(); private q = new THREE.Quaternion(); private e = new THREE.Euler();
  constructor(parent: THREE.Object3D, defs: ChunkDef[]) {
    this.defs = defs;
    const geo = blobGeo(1, 3).scale(1.25, 0.8, 1);
    this.mesh = new THREE.InstancedMesh(geo, lam("blubberMeat", () => ({ map: meatTex(), side: THREE.DoubleSide, emissive: new THREE.Color("#7a3020") })), defs.length);
    this.skinMesh = new THREE.InstancedMesh(geo, lam("whaleSkin", () => ({ map: whaleTex() })), defs.length);
    for (const im of [this.mesh, this.skinMesh]) { im.castShadow = true; im.receiveShadow = true; im.frustumCulled = false; parent.add(im); }
  }
  /** position of chunk i at time s after the blast (null before it leaves) */
  static at(d: ChunkDef, s: number): [number, number, number] {
    const u = s - d.delay;
    const o = [WHALE.x, 1.6, WHALE.z];
    if (u <= 0) return [o[0], o[1], o[2]];
    const tl = (d.v[1] + Math.sqrt(d.v[1] * d.v[1] + 2 * G * (o[1] - d.s * 0.4))) / G, k = Math.min(u, tl);
    return [o[0] + d.v[0] * k, Math.max(d.s * 0.4, o[1] + d.v[1] * k - 0.5 * G * k * k), o[2] + d.v[2] * k];
  }
  static landT(d: ChunkDef) { return d.delay + (d.v[1] + Math.sqrt(d.v[1] * d.v[1] + 2 * G * (1.6 - d.s * 0.4))) / G; }
  update(s: number, visible: boolean, scale = 1, cam?: THREE.Vector3) {
    let a = 0, b = 0;
    for (const d of this.defs) {
      const p = Chunks.at(d, s);
      if (cam && Math.hypot(p[0] - cam.x, p[1] - cam.y, p[2] - cam.z) < 3.5 + 2 * d.s) continue;
      const flying = s < Chunks.landT(d), sp = flying ? Math.max(0, s - d.delay) : Chunks.landT(d) - d.delay;
      this.e.set(d.spin[0] * sp, d.spin[1] * sp, d.spin[2] * sp); this.q.setFromEuler(this.e);
      const sq = flying ? 1 : 0.7;
      this.m.compose(V(p[0], p[1] - (flying ? 0 : d.s * 0.12), p[2]), this.q, V(d.s * scale, d.s * scale * sq, d.s * scale));
      if (d.skin) this.skinMesh.setMatrixAt(b++, this.m); else this.mesh.setMatrixAt(a++, this.m);
    }
    this.mesh.count = a; this.skinMesh.count = b;
    this.mesh.instanceMatrix.needsUpdate = this.skinMesh.instanceMatrix.needsUpdate = true;
    this.mesh.visible = this.skinMesh.visible = visible && s > 0;
  }
}

// ---------------- vehicles + props ----------------
/** a 1970 full-size sedan: long hood and trunk, a low greenhouse, chrome bumpers, whitewalls. Points +x; origin = the
 *  ground under its middle. crush(k): the roof caved by k (0..1) under a lump of blubber. */
export class Car {
  root = new THREE.Group();
  private front = new THREE.Group(); private rear = new THREE.Group();
  private roof = new THREE.Group();
  private lump: THREE.Mesh;
  private bow: THREE.Group;
  constructor(parent: THREE.Object3D, col: string, key: string) {
    parent.add(this.root);
    const paint = lam("car" + key, () => ({ color: col })), chrome = lam("chrome", () => ({ color: "#d6dade" })), glass = lam("carGlass", () => ({ color: "#8fb0c8" }));
    const black = lam("carBlack", () => ({ color: "#26262c" })), white = lam("whitewall", () => ({ color: "#f2efe6" }));
    // two halves hinged at the middle (x = 0, y = 0.4): a crushed car folds into a V
    for (const h of [this.front, this.rear]) { h.position.set(0, 0.4, 0); this.root.add(h); }
    const F = (g: THREE.BufferGeometry) => g.translate(0, -0.4, 0);
    for (const [hg, x0, x1] of [[this.front, 0, 2.85], [this.rear, -2.85, 0]] as const) {
      add(F(box(x0, x1, 0.38, 0.95, -0.98, 0.98)), paint, hg);
      for (const s2 of [-1, 1]) add(F(box(x0, x1, 0.6, 0.64, s2 * 1.0 - 0.03, s2 * 1.0 + 0.03)), chrome, hg);
    }
    add(F(box(2.85, 2.97, 0.4, 0.62, -0.98, 0.98)), chrome, this.front); add(F(box(-2.95, -2.85, 0.4, 0.62, -0.98, 0.98)), chrome, this.rear);
    add(F(box(2.9, 2.93, 0.62, 0.9, -0.7, 0.7)), chrome, this.front); // grille
    for (const s2 of [-1, 1]) {
      const hl = new THREE.Mesh(F(new THREE.CylinderGeometry(0.1, 0.1, 0.04, 14).rotateZ(Math.PI / 2).translate(2.95, 0.76, s2 * 0.75)), hdr(1.6, 1.55, 1.3)); hl.layers.set(NOINK); this.front.add(hl);
      this.rear.add(new THREE.Mesh(F(box(-2.9, -2.86, 0.66, 0.84, s2 * 0.62 - 0.22, s2 * 0.62 + 0.22)), lam("tailLight", () => ({ color: "#c0353a" }))));
    }
    // the greenhouse (flattens when crushed)
    this.roof.position.set(-0.3, 0.95, 0); this.root.add(this.roof);
    add(new THREE.CylinderGeometry(0.6, 0.85, 1.0, 4, 1).rotateY(Math.PI / 4).scale(1.75, 0.5, 1.15).translate(0, 0.25, 0), glass, this.roof);
    add(box(-0.85, 0.75, 0.5, 0.56, -0.68, 0.68), lam("vinylRoof", () => ({ color: "#f2efe6" })), this.roof);
    const wg = new THREE.CylinderGeometry(0.38, 0.38, 0.26, 20).rotateX(Math.PI / 2);
    for (const [x, z] of [[1.8, -0.86], [1.8, 0.86], [-1.8, -0.86], [-1.8, 0.86]]) {
      const hg = x > 0 ? this.front : this.rear;
      add(F(wg.clone().translate(x, 0.38, z)), black, hg); add(F(new THREE.CylinderGeometry(0.24, 0.24, 0.4, 18).rotateX(Math.PI / 2).translate(x, 0.38, z)), white, hg); add(F(new THREE.CylinderGeometry(0.14, 0.14, 0.58, 14).rotateX(Math.PI / 2).translate(x, 0.38, z)), chrome, hg);
    }
    this.lump = add(blobGeo(1.0, 7).scale(1.35, 0.8, 1.1), lam("blubberMeat", () => ({ map: meatTex(), side: THREE.DoubleSide, emissive: new THREE.Color("#7a3020") })), this.root);
    this.lump.visible = false;
    // the dealer's red bow on the roof
    this.bow = new THREE.Group();
    const red = lam("bowRed", () => ({ color: "#d9382e" }));
    for (const s2 of [-1, 1]) add(new THREE.TorusGeometry(0.22, 0.07, 8, 16).scale(1, 0.7, 1).translate(s2 * 0.22, 0.2, 0), red, this.bow);
    add(box(-0.06, 0.06, 0, 0.3, -0.7, 0.7), red, this.bow); add(box(-0.8, 0.8, 0, 0.05, -0.06, 0.06), red, this.bow);
    this.bow.position.set(-0.3, 1.52, 0); this.bow.visible = false; this.root.add(this.bow);
  }
  set(x: number, z: number, yaw: number, crush = 0, bow = false, lumpFall = -1) {
    this.root.position.set(x, 0, z); this.root.rotation.y = yaw;
    this.roof.scale.set(1 + 0.15 * crush, 1 - 0.88 * crush, 1 + 0.12 * crush); this.roof.position.y = 0.95 - 0.12 * crush;
    this.front.rotation.z = 0.34 * crush; this.rear.rotation.z = -0.34 * crush;
    this.front.position.y = this.rear.position.y = 0.4 - 0.12 * crush;
    this.lump.visible = lumpFall >= 0;
    if (lumpFall >= 0) this.lump.position.set(-0.3, 1.0 + 0.9 * (1 - crush * 0.7) + Math.max(0, lumpFall) * 24, 0);
    this.bow.visible = bow;
  }
}
/** a 1970 school bus: yellow box body, black rub rails, a row of windows, a short bonnet. Points +x. */
export const bus = () => {
  const g = new THREE.Group(), y = lam("busYellow", () => ({ color: "#f2b81e" })), blk = lam("busBlack", () => ({ color: "#26262c" })), glass = lam("busGlass", () => ({ color: "#9fbfd4" }));
  add(box(-5.2, 3.6, 0.55, 3.05, -1.2, 1.2), y, g);
  add(box(3.6, 5.2, 0.55, 1.75, -1.0, 1.0), y, g);
  add(box(5.2, 5.3, 0.6, 1.6, -0.9, 0.9), lam("chrome", () => ({ color: "#d6dade" })), g);
  for (const s of [-1, 1]) { for (const yy of [1.1, 1.55]) add(box(-5.2, 5.2, yy - 0.05, yy + 0.05, s * 1.2 - 0.04, s * 1.2 + 0.04), blk, g);
    for (let k = 0; k < 9; k++) add(box(-4.6 + k * 0.92, -4.0 + k * 0.92, 1.85, 2.65, s * 1.2 - 0.03, s * 1.2 + 0.03), glass, g); }
  add(box(3.58, 3.62, 1.8, 2.7, -1.1, 1.1), glass, g);
  add(box(-5.25, 3.65, 3.05, 3.15, -1.15, 1.15), lam("busRoof", () => ({ color: "#f6f2e6" })), g);
  const wg = new THREE.CylinderGeometry(0.5, 0.5, 0.32, 20).rotateX(Math.PI / 2);
  for (const [x, z] of [[3.3, -1.05], [3.3, 1.05], [-3.4, -1.05], [-3.4, 1.05]]) add(wg.clone().translate(x, 0.5, z), blk, g);
  return g;
};
/** the Highway Division dump truck: orange cab, a steel dump bed. Points +x. */
export const hwyTruck = () => {
  const g = new THREE.Group(), o = lam("hwyOrange", () => ({ color: "#e8812a" })), blk = lam("truckBlack", () => ({ color: "#26262c" })), steel = lam("bedSteel", () => ({ color: "#9aa0a8" }));
  add(box(-3.0, 2.9, 0.62, 0.85, -0.95, 0.95), blk, g);
  add(box(1.7, 2.9, 0.85, 1.75, -0.95, 0.95), o, g);
  add(box(0.4, 1.7, 0.85, 2.55, -1.05, 1.05), o, g);
  add(box(1.68, 1.72, 1.75, 2.4, -0.9, 0.9), lam("truckGlass", () => ({ color: "#8fb0c8" })), g);
  add(box(-3.1, 0.3, 0.9, 2.1, -1.1, 1.1), steel, g);
  add(box(-3.0, 0.2, 1.4, 2.12, -1.0, 1.0), lam("bedSand", () => ({ color: "#c9b48a" })), g);
  add(box(2.9, 3.0, 0.85, 1.6, -0.8, 0.8), lam("chrome", () => ({ color: "#d6dade" })), g);
  const wg = new THREE.CylinderGeometry(0.5, 0.5, 0.3, 20).rotateX(Math.PI / 2);
  for (const [x, z] of [[2.2, -1.0], [2.2, 1.0], [-1.9, -1.0], [-1.9, 1.0]]) add(wg.clone().translate(x, 0.5, z), blk, g);
  for (const s of [-1, 1]) { const d = new THREE.Mesh(new THREE.PlaneGeometry(0.9, 0.45), new THREE.MeshBasicMaterial({ map: signTex("hwyDoor", 256, 128, "#e8812a", "#1d1a22", [["STATE HWY", 44]], false) }));
    d.position.set(1.05, 1.5, s * 1.06); d.rotation.y = s > 0 ? 0 : Math.PI; d.layers.set(NOINK); g.add(d); }
  return g;
};
/** n cases of dynamite stacked in columns (0.55 x 0.32 x 0.38 each) */
export const dynamite = (n: number, cols = 5) => {
  const g = new THREE.Group(), face = lam("dynFace", () => ({ map: dynTex() })), wood = lam("dynWood", () => ({ color: "#b8925e" }));
  for (let i = 0; i < n; i++) {
    const m = new THREE.Mesh(new THREE.BoxGeometry(0.55, 0.32, 0.38), [wood, wood, wood, wood, face, face]);
    m.position.set((i % cols) * 0.58 - ((cols - 1) * 0.58) / 2, 0.16 + Math.floor(i / cols) * 0.33, (Math.floor(i / cols) % 2) * 0.03); m.castShadow = m.receiveShadow = true;
    g.add(m);
  }
  return g;
};
/** the blaster's plunger box with its T-handle (handle travel 0..1) and the wire */
export class Plunger {
  root = new THREE.Group();
  private handle = new THREE.Group();
  constructor(parent: THREE.Object3D, wireTo: THREE.Vector3) {
    parent.add(this.root);
    const wood = lam("plungerWood", () => ({ color: "#a8743e" })), steel = lam("gunSteel", () => ({ color: "#3a3d44" }));
    add(box(-0.18, 0.18, 0, 0.36, -0.14, 0.14), wood, this.root);
    add(box(-0.32, 0.32, -0.6, 0, -0.26, 0.26), lam("plungerCrate", () => ({ color: "#8a6a3e" })), this.root);
    add(new THREE.CylinderGeometry(0.02, 0.02, 0.4, 8).translate(0, 0.2, 0), steel, this.handle);
    add(new THREE.CylinderGeometry(0.03, 0.03, 0.42, 8).rotateX(Math.PI / 2).translate(0, 0.4, 0), steel, this.handle);
    this.handle.position.y = 0.3; this.root.add(this.handle);
    const pts = [V(0.2, 0.05, 0), V(0.5, -0.55, -0.6), V(1.2, -0.58, -2), wireTo.clone().setY(-0.55)];
    const wire = new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), 40, 0.012, 5), lam("wireRed", () => ({ color: "#c0353a" })));
    this.root.add(wire);
  }
  set(x: number, z: number, press: number, visible = true) { this.root.position.set(x, 0.6, z); this.handle.position.y = 0.3 - 0.24 * press; this.root.visible = visible; }
}
/** the TV news camera on a tripod (lens +x) */
export const tvCamera = () => {
  const g = new THREE.Group(), body = lam("tvBody", () => ({ color: "#d9dde0" })), dark = lam("gunSteel", () => ({ color: "#3a3d44" }));
  for (const [dx, dz] of [[0.35, 0], [-0.22, 0.3], [-0.22, -0.3]]) add(limb(V(0, 1.25, 0), V(dx, 0, dz), 0.025, 0.02, 6), dark, g);
  add(box(-0.3, 0.25, 1.25, 1.6, -0.14, 0.14), body, g);
  add(new THREE.CylinderGeometry(0.09, 0.11, 0.3, 14).rotateZ(Math.PI / 2).translate(0.4, 1.42, 0), dark, g);
  const logo = new THREE.Mesh(new THREE.PlaneGeometry(0.3, 0.15), new THREE.MeshBasicMaterial({ map: tvTex() })); logo.position.set(-0.03, 1.43, 0.145); logo.layers.set(NOINK); g.add(logo);
  return g;
};

// ---------------- the kitchen (the jelly) ----------------
export class Kitchen {
  root = new THREE.Group();
  jelly: THREE.Mesh;
  constructor(parent: THREE.Object3D) {
    parent.add(this.root);
    const K = KITCHEN, b = new Batch();
    room(this.root, K.x, K.z, 8, 8, 3.2, lam("lino", () => ({ map: lino() })), lam("kitchenPaper", () => ({ map: wallpaperTex() })), lam("kitchenCeil", () => ({ color: "#f6f0e0" })));
    const cloth = lam("checkCloth", () => ({ map: checkTex() })), wood = lam("tableWood", () => ({ color: "#9a6a42" }));
    b.add(box(K.x - 1.0, K.x + 1.0, 0.72, 0.78, K.z - 1.9, K.z - 0.7), cloth);
    b.add(box(K.x - 1.03, K.x + 1.03, 0.45, 0.78, K.z - 1.93, K.z - 1.9), cloth); b.add(box(K.x - 1.03, K.x + 1.03, 0.45, 0.78, K.z - 0.7, K.z - 0.67), cloth);
    for (const [dx, dz] of [[-0.9, -1.8], [0.9, -1.8], [-0.9, -0.8], [0.9, -0.8]]) b.add(box(K.x + dx - 0.04, K.x + dx + 0.04, 0, 0.72, K.z + dz - 0.04, K.z + dz + 0.04), wood);
    b.add(new THREE.CylinderGeometry(0.26, 0.16, 0.08, 24).translate(K.x, 0.82, K.z - 1.3), lam("plate", () => ({ color: "#f4f1ea" })));
    // a fridge and a counter at the back
    b.add(box(K.x + 2.2, K.x + 3.0, 0, 1.75, K.z - 3.9, K.z - 3.2), lam("fridge", () => ({ color: "#9ad1b8" })));
    b.add(box(K.x - 3.8, K.x + 2.0, 0, 0.9, K.z - 3.95, K.z - 3.35), lam("counter", () => ({ color: "#e48a3a" })));
    b.add(box(K.x - 3.8, K.x + 2.0, 0.9, 0.95, K.z - 4.0, K.z - 3.3), lam("counterTop", () => ({ color: "#f2efe6" })));
    b.build(this.root, true);
    // the jelly: a ridged green dome on the plate (wobbles via scale)
    const pts: THREE.Vector2[] = [];
    for (let i = 0; i <= 16; i++) { const t = i / 16, r = 0.2 * (1 - t * t * 0.55) + 0.012 * Math.cos(t * 30); pts.push(new THREE.Vector2(Math.max(0.001, r * (t < 0.98 ? 1 : 0.3)), t * 0.24)); }
    this.jelly = new THREE.Mesh(new THREE.LatheGeometry(pts, 32), lam("jelly", () => ({ color: "#57c24a", emissive: new THREE.Color("#0f3a0c") })));
    this.jelly.position.set(K.x, 0.86, K.z - 1.3); this.jelly.castShadow = true; this.root.add(this.jelly);
    const win = new THREE.Mesh(new THREE.PlaneGeometry(1.4, 1.1), new THREE.MeshBasicMaterial({ color: "#bfe0f4", fog: false })); win.position.set(K.x - 1.2, 1.9, K.z - 3.98); win.layers.set(NOINK); this.root.add(win);
  }
  update(f: number, hitAt: number) {
    const s = (f - hitAt) / 30;
    this.jelly.visible = s < 0;
    const w = s < 0 ? 0.03 * Math.sin(f * 0.5) : 0;
    this.jelly.scale.set(1 + w, 1 - w, 1 + w);
  }
}

// ---------------- the park ----------------
export class Park {
  root = new THREE.Group();
  constructor(parent: THREE.Object3D) {
    parent.add(this.root);
    const P = PARK, b = new Batch();
    b.add(floorQ(P.x - 120, P.x + 120, P.z - 140, P.z + 60, 0.01, 6), lam("parkGrass", () => ({ color: "#7fae58" })));
    const post = lam("parkPost", () => ({ color: "#5a3820" }));
    for (const dx of [-1.6, 1.6]) b.add(box(P.x + dx - 0.12, P.x + dx + 0.12, 0, 2.3, P.z - 0.12, P.z + 0.12), post);
    b.add(box(P.x - 1.9, P.x + 1.9, 2.3, 2.42, P.z - 0.2, P.z + 0.2), post);
    // picnic tables, a path, conifers, a far sea strip
    for (const [x, z] of [[-6, -6], [5, -9], [-3, -16]] as const) {
      b.add(box(P.x + x - 0.9, P.x + x + 0.9, 0.72, 0.78, P.z + z - 0.4, P.z + z + 0.4), lam("picnic", () => ({ color: "#a8743e" })));
      for (const dz of [-0.65, 0.65]) b.add(box(P.x + x - 0.9, P.x + x + 0.9, 0.42, 0.47, P.z + z + dz - 0.14, P.z + z + dz + 0.14), lam("picnic", () => ({ color: "#a8743e" })));
    }
    for (let i = 0; i < 40; i++) { const x = P.x - 60 + hh(i, 31) * 120, z = P.z - 20 - hh(i, 32) * 100; if (Math.abs(x - P.x) < 12 && z > P.z - 26) continue; conifer(b, x, z, 9 + hh(i, 33) * 8, i + 200); }
    b.add(floorQ(P.x - 2, P.x + 2, P.z - 30, P.z + 30, 0.05, 4), lam("parkPath", () => ({ color: "#d9c49a" })));
    b.build(this.root, true);
    const sign = new THREE.Mesh(new THREE.PlaneGeometry(3.2, 2.0), new THREE.MeshBasicMaterial({ map: parkSignTex(), side: THREE.DoubleSide }));
    sign.position.set(P.x, 1.25, P.z + 0.2); this.root.add(sign);
    const bk = new THREE.Mesh(box(P.x - 1.62, P.x + 1.62, 0.23, 2.27, P.z - 0.1, P.z + 0.11), lam("parkBoard", () => ({ color: "#6f4526" }))); bk.castShadow = true; this.root.add(bk);
  }
}

// ---------------- the car dealer ----------------
export class Dealer {
  root = new THREE.Group();
  constructor(parent: THREE.Object3D) {
    parent.add(this.root);
    const D = DEALER, b = new Batch();
    b.add(floorQ(D.x - 200, D.x + 200, D.z - 200, D.z + 80, 0, 6), lam("asphalt", () => ({ color: "#8a8a90" })));
    for (let x = -12; x <= 12; x += 3.2) b.add(box(D.x + x - 0.05, D.x + x + 0.05, 0.0, 0.03, D.z - 6, D.z + 1), lam("lotLine", () => ({ color: "#f2efe6" })));
    // the showroom behind the lot
    b.add(box(D.x - 14, D.x + 14, 0, 6, D.z - 16, D.z - 9), lam("showroomWall", () => ({ color: "#f2efe6" })));
    b.add(box(D.x - 14.4, D.x + 14.4, 6, 6.6, D.z - 16.4, D.z - 8.6), lam("showroomRoof", () => ({ color: "#d9382e" })));
    // banner poles
    const pole = lam("bannerPole", () => ({ color: "#d6dade" }));
    for (const dx of [-3.3, 3.3]) b.add(cylY(0.08, 0, 4.8, D.x + dx, D.z - 7, 10), pole);
    for (let x = -14; x < 14; x += 20) for (let k = 0; k < 10; k++) b.add(box(0, 0, 0, 0, 0, 0), pole);
    for (let i = 0; i < 30; i++) { const a = -Math.PI + (i / 30) * Math.PI, x = D.x + Math.cos(a) * 60, z = D.z - 30 + Math.sin(a) * 30; conifer(b, x, z, 12 + hh(i, 41) * 6, i + 300); }
    b.build(this.root, true);
    const front = new THREE.Mesh(new THREE.PlaneGeometry(28, 6), new THREE.MeshBasicMaterial({ map: showroomTex() })); front.position.set(D.x, 3, D.z - 8.93); this.root.add(front);
    const ban = new THREE.Mesh(new THREE.PlaneGeometry(6.4, 1.6), new THREE.MeshBasicMaterial({ map: bannerTex(), side: THREE.DoubleSide })); ban.position.set(D.x, 3.9, D.z - 6.95); this.root.add(ban);
    // pennant strings from the poles out to the lot corners
    const flagCols = ["#d9382e", "#f6d23a", "#3f7fd2", "#ffffff", "#4fb06a"];
    for (const [a, c] of [[[-5.2, 5.3, -7], [-14, 3.2, 2]], [[5.2, 5.3, -7], [14, 3.2, 2]], [[-5.2, 5.3, -7], [5.2, 5.3, -7]]] as const) {
      const n = 14;
      for (let k = 0; k < n; k++) {
        const t = (k + 0.5) / n, x = a[0] + (c[0] - a[0]) * t, z = a[2] + (c[2] - a[2]) * t, y = a[1] + (c[1] - a[1]) * t - 0.5 * Math.sin(t * Math.PI);
        const tri = new THREE.Mesh(new THREE.BufferGeometry().setFromPoints([V(-0.2, 0, 0), V(0.2, 0, 0), V(0, -0.45, 0)]), new THREE.MeshBasicMaterial({ color: flagCols[k % 5], side: THREE.DoubleSide }));
        tri.position.set(D.x + x, y, D.z + z); tri.rotation.y = Math.atan2(c[2] - a[2], c[0] - a[0]) * -1; tri.layers.set(NOINK); this.root.add(tri);
      }
    }
  }
}
export { stripeTex };
