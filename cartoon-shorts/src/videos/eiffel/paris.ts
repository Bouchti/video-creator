// The Eiffel film's sets (two-tone lam() geometry, outlined by the world ink):
//  Tower (the 1925 Eiffel Tower: four curved lattice legs, the arches, two platforms, the shaft, the antenna),
//  Champ (the lawn and avenue in front of it, Haussmann blocks, trees, lamps), CafeStreet (the café street on the
//  tower's axis: terrace, awning, tables; a far dome for the Austrian morning), Limo (a 1920s limousine), Hotel (the
//  grand salon: chandelier, long table, tall windows on Paris), Home (Poisson's parlour), Office (a ministry hall of
//  clerks' desks), Country (fields, hills, the Alps and the railway with a moving train).
import * as THREE from "three";
import { lam, Batch, V, quad, prop, Kit } from "./build";
import { ctex, grassHD, cobbleHD } from "./paint";
import { NOINK } from "./ink";
import { TOWER, CHAMP, CAFE, HOTEL, HOME, OFFICE, COUNTRY, KNOCK_GIRDER, EAST_TABLES } from "./places";

const TAU = Math.PI * 2;
export const box = (x0: number, x1: number, y0: number, y1: number, z0: number, z1: number) =>
  new THREE.BoxGeometry(x1 - x0, y1 - y0, z1 - z0).translate((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2);
const cylY = (r: number, y0: number, y1: number, x: number, z: number, seg = 24, r2 = r) =>
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
/** an open-fronted room (+z open): floor, back + side walls, ceiling */
const room = (parent: THREE.Object3D, cx: number, cz: number, w: number, d: number, h: number, floor: THREE.Material, wall: THREE.Material, ceil?: THREE.Material, sideWall?: THREE.Material) => {
  const b = new Batch(), x0 = cx - w / 2, x1 = cx + w / 2, z0 = cz - d / 2, z1 = cz + d / 2, sw = sideWall ?? wall;
  b.add(floorQ(x0, x1, z0, z1 + 6, 0, 2), floor);
  b.add(quad(V(x0, 0, z0), V(x1, 0, z0), V(x1, h, z0), V(x0, h, z0), w / 4, 1), wall);
  b.add(quad(V(x0, 0, z1), V(x0, 0, z0), V(x0, h, z0), V(x0, h, z1), d / 4, 1), sw);
  b.add(quad(V(x1, 0, z0), V(x1, 0, z1), V(x1, h, z1), V(x1, h, z0), d / 4, 1), sw);
  if (ceil) b.add(quad(V(x0, h, z0), V(x1, h, z0), V(x1, h, z1), V(x0, h, z1), w / 3, d / 3), ceil);
  b.build(parent, false);
};

// ---------------- painted textures ----------------
const IRON = "#9a6b3e", IRON_D = "#6f4a2a";
/** tower lattice panel: a frame + St Andrew's crosses + a smaller second lattice, rust blotches when rust > 0 (alpha cut) */
const latticeTex = (rust: number) => ctex("lattice" + rust, 512, 512, (g, r) => {
  g.clearRect(0, 0, 512, 512);
  g.strokeStyle = IRON; g.lineCap = "square";
  g.lineWidth = 34; g.strokeRect(17, 17, 478, 478);
  g.lineWidth = 22; g.beginPath(); g.moveTo(17, 17); g.lineTo(495, 495); g.moveTo(495, 17); g.lineTo(17, 495); g.stroke();
  g.lineWidth = 9; g.beginPath();
  for (const k of [128, 256, 384]) { g.moveTo(17, k); g.lineTo(k, 17); g.moveTo(495, 512 - k); g.lineTo(512 - k, 495); g.moveTo(17, 512 - k); g.lineTo(k, 495); g.moveTo(495, k); g.lineTo(512 - k, 17); }
  g.stroke();
  g.lineWidth = 12; g.beginPath(); g.moveTo(256, 17); g.lineTo(256, 495); g.stroke();
  // dark rivet dots along the frame + a darker lower edge on every bar (painted shade)
  g.fillStyle = IRON_D; for (let k = 34; k < 500; k += 26) for (const [x, y] of [[k, 10], [k, 502], [10, k], [502, k]]) { g.beginPath(); g.arc(x, y, 3, 0, TAU); g.fill(); }
  if (rust) {
    g.globalCompositeOperation = "source-atop";
    for (let i = 0; i < 70 * rust; i++) { const x = r() * 512, y = r() * 512, s = 18 + r() * 46; const gr = g.createRadialGradient(x, y, 1, x, y, s); gr.addColorStop(0, "rgba(214,86,24,1)"); gr.addColorStop(0.6, "rgba(190,70,20,0.85)"); gr.addColorStop(1, "rgba(190,70,20,0)"); g.fillStyle = gr; g.fillRect(x - s, y - s, 2 * s, 2 * s); }
    g.globalCompositeOperation = "source-over";
  }
});
/** the first-floor frieze: a band of small arches */
const friezeTex = () => ctex("frieze", 1024, 128, (g) => {
  g.fillStyle = IRON; g.fillRect(0, 0, 1024, 128);
  g.fillStyle = "#3b2a1e"; for (let x = 0; x < 1024; x += 64) { g.beginPath(); g.moveTo(x + 10, 118); g.lineTo(x + 10, 60); g.arc(x + 32, 60, 22, Math.PI, 0); g.lineTo(x + 54, 118); g.fill(); }
  g.fillStyle = "#c4904e"; g.fillRect(0, 0, 1024, 12); g.fillRect(0, 116, 1024, 12);
});
/** Haussmann facade: cream stone courses, tall windows with pediments, iron balconies on floors 2 and 5, shop arches */
const haussTex = (key: string, wm: number, floors: number, shop: string) => ctex("haus" + key, Math.round(wm * 40), floors * 128 + 40, (g, r) => {
  const W = Math.round(wm * 40), H = floors * 128 + 40, fh = 128;
  g.fillStyle = "#efe0c2"; g.fillRect(0, 0, W, H);
  g.strokeStyle = "rgba(160,130,95,0.35)"; g.lineWidth = 2;
  for (let y = 16; y < H; y += 16) { g.beginPath(); g.moveTo(0, y); g.lineTo(W, y); g.stroke(); }
  for (let i = 0; i < W * H / 4000; i++) { g.fillStyle = r() < 0.5 ? "rgba(255,255,255,0.12)" : "rgba(140,110,80,0.08)"; g.fillRect(r() * W, r() * H, 20 + r() * 60, 6 + r() * 14); }
  const nw = Math.max(2, Math.floor(wm / 3.2)), cw = W / nw;
  for (let fl = 0; fl < floors; fl++) {
    const y0 = H - (fl + 1) * fh;
    for (let i = 0; i < nw; i++) {
      const cx = (i + 0.5) * cw;
      if (fl === 0) { // shop front: dark arch, coloured fascia
        g.fillStyle = shop; g.fillRect(cx - cw * 0.46, y0 + 14, cw * 0.92, 18);
        g.fillStyle = "#2e3442"; g.beginPath(); g.moveTo(cx - cw * 0.38, y0 + fh); g.lineTo(cx - cw * 0.38, y0 + 52); g.arc(cx, y0 + 52, cw * 0.38, Math.PI, 0); g.lineTo(cx + cw * 0.38, y0 + fh); g.fill();
        g.fillStyle = "rgba(255,226,160,0.55)"; g.fillRect(cx - cw * 0.3, y0 + 58, cw * 0.6, 40);
        continue;
      }
      const ww = cw * 0.42, wh = fh * 0.62, wy = y0 + fh * 0.22;
      g.fillStyle = "#3a4458"; g.fillRect(cx - ww / 2, wy, ww, wh);
      g.fillStyle = "rgba(170,200,235,0.55)"; g.fillRect(cx - ww / 2 + 4, wy + 4, ww / 2 - 6, wh * 0.45); g.fillRect(cx + 2, wy + 4, ww / 2 - 6, wh * 0.45);
      g.strokeStyle = "#f6ecd6"; g.lineWidth = 3; g.beginPath(); g.moveTo(cx, wy); g.lineTo(cx, wy + wh); g.stroke();
      g.fillStyle = "#d9c39c"; g.fillRect(cx - ww / 2 - 6, wy - 10, ww + 12, 8); // lintel
      if (fl === 2 || fl === 5) g.fillRect(cx - ww / 2 - 8, wy - 22, ww + 16, 6);
      // balcony rail
      const by = wy + wh - 4, full = fl === 2 || fl === 5;
      g.strokeStyle = "#232430"; g.lineWidth = 3;
      const bx0 = full ? 0 : cx - ww / 2 - 6, bx1 = full ? W : cx + ww / 2 + 6;
      g.beginPath(); g.moveTo(bx0, by - 20); g.lineTo(bx1, by - 20); g.moveTo(bx0, by + 2); g.lineTo(bx1, by + 2); g.stroke();
      g.lineWidth = 2; for (let x = bx0 + 4; x < bx1; x += 7) { g.beginPath(); g.moveTo(x, by - 20); g.lineTo(x, by + 2); g.stroke(); }
    }
    if (fl === 1) { g.fillStyle = "#d9c39c"; g.fillRect(0, y0 + fh - 8, W, 8); }
  }
  g.fillStyle = "#cdb48a"; g.fillRect(0, 0, W, 22); // cornice
});
const slateTex = () => ctex("slateParis", 512, 512, (g, r) => {
  g.fillStyle = "#6f7d92"; g.fillRect(0, 0, 512, 512);
  for (let y = 0; y < 512; y += 24) for (let x = (y / 24) % 2 ? -16 : 0; x < 512; x += 32) { g.fillStyle = `rgba(${r() < 0.5 ? "40,50,70" : "200,210,230"},${0.08 + r() * 0.1})`; g.fillRect(x + 1, y + 1, 30, 22); }
  g.strokeStyle = "rgba(30,36,50,0.5)"; g.lineWidth = 2; for (let y = 0; y < 512; y += 24) { g.beginPath(); g.moveTo(0, y); g.lineTo(512, y); g.stroke(); }
});
const awningTex = (a: string, b: string) => ctex("awning" + a, 256, 256, (g) => {
  for (let x = 0; x < 8; x++) { g.fillStyle = x % 2 ? a : b; g.fillRect(x * 32, 0, 32, 256); }
  g.fillStyle = "rgba(0,0,0,0.12)"; g.fillRect(0, 220, 256, 36);
});
const austriaTex = () => ctex("austria", 256, 170, (g) => {
  g.fillStyle = "#c8102e"; g.fillRect(0, 0, 256, 170); g.fillStyle = "#ffffff"; g.fillRect(0, 57, 256, 56);
});
const franceTex = () => ctex("france", 255, 170, (g) => {
  g.fillStyle = "#1f3c88"; g.fillRect(0, 0, 85, 170); g.fillStyle = "#ffffff"; g.fillRect(85, 0, 85, 170); g.fillStyle = "#c8102e"; g.fillRect(170, 0, 85, 170);
});
const gravelTex = () => ctex("gravel", 512, 512, (g, r) => {
  g.fillStyle = "#e2cfa3"; g.fillRect(0, 0, 512, 512);
  for (let i = 0; i < 2600; i++) { g.fillStyle = r() < 0.5 ? "rgba(170,140,95,0.35)" : "rgba(255,246,220,0.4)"; g.fillRect(r() * 512, r() * 512, 2 + r() * 3, 2 + r() * 3); }
});
const salonWall = () => ctex("salonWall", 1024, 512, (g) => {
  g.fillStyle = "#f3e6cc"; g.fillRect(0, 0, 1024, 512);
  g.fillStyle = "#e5d2ac"; g.fillRect(0, 380, 1024, 132);
  g.strokeStyle = "#c9a24a"; g.lineWidth = 8;
  for (const x of [40, 552]) { g.strokeRect(x, 60, 432, 290); g.lineWidth = 3; g.strokeRect(x + 18, 78, 396, 254); g.lineWidth = 8; }
  for (const x of [40, 552]) g.strokeRect(x, 400, 432, 90);
  g.fillStyle = "#c9a24a"; g.fillRect(0, 370, 1024, 10); g.fillRect(0, 0, 1024, 20);
});
const carpetTex = () => ctex("salonCarpet", 512, 512, (g) => {
  g.fillStyle = "#9c2a2e"; g.fillRect(0, 0, 512, 512);
  g.strokeStyle = "#d9a64a"; g.lineWidth = 6; g.strokeRect(20, 20, 472, 472);
  g.fillStyle = "rgba(240,190,90,0.5)";
  for (let y = 64; y < 512; y += 128) for (let x = 64; x < 512; x += 128) { g.beginPath(); g.moveTo(x, y - 30); g.lineTo(x + 30, y); g.lineTo(x, y + 30); g.lineTo(x - 30, y); g.fill(); }
});
/** the view out of the hotel windows: sky, Paris roofs and the tower */
const viewTex = () => ctex("parisView", 512, 1024, (g) => {
  const gr = g.createLinearGradient(0, 0, 0, 1024); gr.addColorStop(0, "#5e93d9"); gr.addColorStop(1, "#cfe0f2");
  g.fillStyle = gr; g.fillRect(0, 0, 512, 1024);
  g.fillStyle = "#8a6a4a"; g.beginPath(); g.moveTo(300, 140); g.lineTo(312, 140); g.lineTo(380, 860); g.lineTo(232, 860); g.fill();
  g.fillStyle = "#cfe0f2"; g.beginPath(); g.moveTo(262, 860); g.quadraticCurveTo(306, 760, 350, 860); g.fill();
  g.fillStyle = "#8a6a4a"; g.fillRect(262, 600, 88, 12); g.fillRect(278, 420, 56, 10);
  g.fillStyle = "#8f9fb6"; for (let x = 0; x < 512; x += 70) g.fillRect(x, 840 - (x % 3) * 18, 64, 200);
  g.fillStyle = "#a9b6c8"; for (let x = 30; x < 512; x += 90) g.fillRect(x, 900, 70, 140);
});
const wallpaper = () => ctex("homePaper", 512, 512, (g) => {
  g.fillStyle = "#6f9a7a"; g.fillRect(0, 0, 512, 512);
  g.fillStyle = "#84ad8c"; for (let x = 0; x < 512; x += 64) g.fillRect(x, 0, 24, 512);
  g.fillStyle = "rgba(255,240,200,0.35)"; for (let y = 32; y < 512; y += 64) for (let x = 44; x < 512; x += 64) { g.beginPath(); g.arc(x, y, 6, 0, TAU); g.fill(); }
  g.fillStyle = "#5a3b2a"; g.fillRect(0, 400, 512, 112);
});
const officeWall = () => ctex("officeWall", 512, 512, (g) => {
  g.fillStyle = "#c9d6c2"; g.fillRect(0, 0, 512, 512);
  g.fillStyle = "#7f9a86"; g.fillRect(0, 330, 512, 182); g.fillStyle = "#5f7a66"; g.fillRect(0, 324, 512, 10);
});
const parquet = () => ctex("parquet", 512, 512, (g, r) => {
  for (let y = 0; y < 8; y++) for (let x = 0; x < 8; x++) {
    const v = 0.85 + r() * 0.2; g.fillStyle = `rgb(${Math.round(176 * v)},${Math.round(118 * v)},${Math.round(70 * v)})`;
    if ((x + y) % 2) g.fillRect(x * 64, y * 64, 64, 64); else { g.fillRect(x * 64, y * 64, 64, 64); g.strokeStyle = "rgba(80,50,30,0.35)"; g.lineWidth = 2; for (let k = 16; k < 64; k += 16) { g.beginPath(); g.moveTo(x * 64 + k, y * 64); g.lineTo(x * 64 + k, y * 64 + 64); g.stroke(); } }
    g.strokeStyle = "rgba(60,36,20,0.6)"; g.lineWidth = 2; g.strokeRect(x * 64, y * 64, 64, 64);
  }
});
const fieldTex = () => ctex("fields", 1024, 1024, (g, r) => {
  const cols = ["#8cc25a", "#a9cf62", "#d9c25a", "#7ab24e", "#c4d870", "#9ac65c"];
  for (let y = 0; y < 4; y++) for (let x = 0; x < 4; x++) {
    g.fillStyle = cols[Math.floor(r() * cols.length)]; g.fillRect(x * 256, y * 256, 256, 256);
    g.strokeStyle = "rgba(255,255,255,0.18)"; g.lineWidth = 3; for (let k = 0; k < 256; k += 18) { g.beginPath(); g.moveTo(x * 256, y * 256 + k); g.lineTo(x * 256 + 256, y * 256 + k); g.stroke(); }
    g.strokeStyle = "#5d8a3a"; g.lineWidth = 6; g.strokeRect(x * 256, y * 256, 256, 256);
  }
});
const carriageTex = () => ctex("carriage", 1024, 256, (g) => {
  g.fillStyle = "#2f6a4a"; g.fillRect(0, 0, 1024, 256);
  g.fillStyle = "#e8c45a"; g.fillRect(0, 186, 1024, 8); g.fillRect(0, 34, 1024, 6);
  for (let x = 40; x < 1000; x += 120) { g.fillStyle = "#f2d590"; g.fillRect(x, 60, 80, 90); g.fillStyle = "#c9a24a"; g.fillRect(x, 102, 80, 4); g.strokeStyle = "#1f3a2a"; g.lineWidth = 6; g.strokeRect(x, 60, 80, 90); }
});

// ---------------- the tower ----------------
/** leg centre offset from the axis and leg half-width at height y (y <= 115), the shaft half-width above */
const legC = (y: number) => 13 + 39 * Math.pow(1 - Math.min(1, y / 115), 1.7);
const legW = (y: number) => 5.5 + 7.5 * Math.pow(1 - Math.min(1, y / 115), 1.1);
const shaftW = (y: number) => 2.2 + 16.8 * Math.pow(1 - (y - 115) / (276 - 115), 1.6);
export class Tower {
  root = new THREE.Group();
  constructor(parent: THREE.Object3D) {
    parent.add(this.root);
    const T = TOWER, b = new Batch();
    const solid = lam("towerIron", () => ({ color: IRON })), dark = lam("towerIronD", () => ({ color: IRON_D }));
    const lat = (rust: number, rep: number) => lam("towerLat" + rust + rep, () => {
      const t = latticeTex(rust).clone(); t.repeat.set(1, rep); t.needsUpdate = true;
      return { map: t, alphaTest: 0.5, side: THREE.DoubleSide };
    });
    const latR = lat(1, 1), latC = lat(0, 1);
    const stone = lam("towerPier", () => ({ map: cobbleHD() }));
    /** one square frustum section from (c0, w0, y0) to (c1, w1, y1) around the axis offset (sx, sz) */
    const section = (sx: number, sz: number, y0: number, y1: number, c0: number, c1: number, w0: number, w1: number, mat: THREE.Material, edge: number) => {
      const P = (c: number, w: number, y: number, ex: number, ez: number) => V(T.x + sx * c + ex * w, y, T.z + sz * c + ez * w);
      const corners: [number, number][] = [[-1, -1], [1, -1], [1, 1], [-1, 1]];
      for (let k = 0; k < 4; k++) {
        const [ax, az] = corners[k], [bx, bz] = corners[(k + 1) % 4];
        b.add(quad(P(c0, w0, y0, ax, az), P(c0, w0, y0, bx, bz), P(c1, w1, y1, bx, bz), P(c1, w1, y1, ax, az), 1, 1), mat);
        b.add(beam(P(c0, w0, y0, ax, az), P(c1, w1, y1, ax, az), edge), solid);
      }
    };
    // ---- four legs from the masonry piers to the second platform ----
    const NL = 9;
    for (const [sx, sz] of [[-1, -1], [1, -1], [1, 1], [-1, 1]] as [number, number][]) {
      for (let i = 0; i < NL; i++) {
        const y0 = (115 * i) / NL, y1 = (115 * (i + 1)) / NL;
        section(sx, sz, y0, y1, legC(y0), legC(y1), legW(y0), legW(y1), i < 3 ? latR : latC, 1.3);
      }
      // the masonry pier under each leg
      const c = legC(0);
      b.add(box(T.x + sx * c - 14, T.x + sx * c + 14, -0.2, 0.6, T.z + sz * c - 14, T.z + sz * c + 14), stone);
    }
    // ---- the shaft from the second platform to the top ----
    const NS = 10;
    for (let i = 0; i < NS; i++) {
      const y0 = 115 + ((276 - 115) * i) / NS, y1 = 115 + ((276 - 115) * (i + 1)) / NS;
      section(0, 0, y0, y1, 0, 0, shaftW(y0), shaftW(y1), latC, 0.9);
    }
    // ---- the platforms ----
    const p1 = legC(57) + legW(57) + 2, p2 = shaftW(115) + 4;
    b.add(box(T.x - p1, T.x + p1, 55, 58.5, T.z - p1, T.z + p1), dark);
    const fr = lam("towerFrieze", () => ({ map: friezeTex() }));
    for (const [ax, az, bx, bz] of [[-1, 1, 1, 1], [1, -1, -1, -1], [-1, -1, -1, 1], [1, 1, 1, -1]] as number[][])
      b.add(quad(V(T.x + ax * p1, 58.5, T.z + az * p1), V(T.x + bx * p1, 58.5, T.z + bz * p1), V(T.x + bx * p1, 64, T.z + bz * p1), V(T.x + ax * p1, 64, T.z + az * p1), 8, 1), fr);
    b.add(box(T.x - p1 - 0.6, T.x + p1 + 0.6, 64, 65, T.z - p1 - 0.6, T.z + p1 + 0.6), solid);
    b.add(box(T.x - p2, T.x + p2, 114, 116.5, T.z - p2, T.z + p2), dark);
    b.add(box(T.x - p2 - 0.4, T.x + p2 + 0.4, 116.5, 119.5, T.z - p2 - 0.4, T.z + p2 + 0.4), solid);
    // ---- the top: the campanile, the lantern, the flagpole / antenna ----
    b.add(box(T.x - 5.5, T.x + 5.5, 274, 281, T.z - 5.5, T.z + 5.5), dark);
    b.add(cylY(3.8, 281, 287, T.x, T.z, 16, 2.4), solid);
    b.add(cylY(1.2, 287, 292, T.x, T.z, 12, 0.8), dark);
    b.add(cylY(0.25, 292, 312, T.x, T.z, 8, 0.12), dark);
    // ---- the great arches between the legs under the first platform ----
    const arch = (axis: "x" | "z", s: number) => {
      const pts: THREE.Vector3[] = [], c = legC(4), R = c - legW(4) - 0.5, apex = 50;
      for (let i = 0; i <= 40; i++) {
        const a = Math.PI * (i / 40), u = -Math.cos(a) * R, y = 6 + Math.sin(a) * (apex - 6);
        pts.push(axis === "x" ? V(T.x + u, y, T.z + s * (legC(y) + legW(y) * 0.4)) : V(T.x + s * (legC(y) + legW(y) * 0.4), y, T.z + u));
      }
      const curve = new THREE.CatmullRomCurve3(pts);
      b.add(new THREE.TubeGeometry(curve, 80, 1.1, 8), solid);
      const pts2 = pts.map((p) => V(p.x, p.y + 3.2, p.z));
      b.add(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts2), 80, 0.7, 8), solid);
      for (let i = 2; i < 40; i += 3) b.add(beam(pts[i], pts2[i], 0.5), solid);
    };
    arch("x", 1); arch("x", -1); arch("z", 1); arch("z", -1);
    // a riveted iron girder at the knock spot (the con man knocks on it)
    b.add(box(KNOCK_GIRDER[0] - 0.14, KNOCK_GIRDER[0] + 0.14, 0.6, 3.4, KNOCK_GIRDER[2] - 0.1, KNOCK_GIRDER[2] + 0.1), solid);
    for (const s of [-1, 1]) b.add(box(KNOCK_GIRDER[0] - 0.24, KNOCK_GIRDER[0] + 0.24, 0.6, 3.4, KNOCK_GIRDER[2] + s * 0.1 - 0.03, KNOCK_GIRDER[2] + s * 0.1 + 0.03), dark);
    b.add(beam(V(KNOCK_GIRDER[0], 3.4, KNOCK_GIRDER[2]), V(KNOCK_GIRDER[0] - 1.2, 9, KNOCK_GIRDER[2] - 1.4), 0.3), solid);
    b.build(this.root, true);
    // lamps on the platforms (warm dots, read at golden hour)
    const lampM = hdr(2.4, 1.6, 0.7);
    for (const [y, r] of [[65.4, p1 + 0.3], [119.9, p2 + 0.2]] as [number, number][])
      for (let k = 0; k < 16; k++) { const a = (k / 16) * TAU; const m = new THREE.Mesh(new THREE.SphereGeometry(0.45, 8, 6), lampM); m.position.set(T.x + Math.cos(a) * r * 1.1, y, T.z + Math.sin(a) * r * 1.1); m.layers.set(NOINK); this.root.add(m); }
  }
}

// ---------------- Paris: lawn, avenue, Haussmann blocks ----------------
/** one Haussmann block: facade box (front = +z after yaw), mansard roof with dormers, chimneys */
const haus = (b: Batch, x: number, z: number, w: number, d: number, floors: number, yaw: number, seed: number) => {
  const h = floors * 3.2, shops = ["#2f5f6a", "#8c3b4a", "#3f6fb5", "#5d7a3a", "#b5653f"];
  const fac = lam(`haus${w}_${floors}_${seed % 5}`, () => ({ map: haussTex(`${w}_${floors}_${seed % 5}`, w, floors, shops[seed % 5]) }));
  const side = lam("hausSide", () => ({ color: "#e6d3ad" }));
  const m = new THREE.Matrix4().makeRotationY(yaw).setPosition(x, 0, z);
  const hw = w / 2, hd = d / 2;
  b.add(quad(V(-hw, 0, hd), V(hw, 0, hd), V(hw, h, hd), V(-hw, h, hd)), fac, m);
  b.add(quad(V(hw, 0, -hd), V(-hw, 0, -hd), V(-hw, h, -hd), V(hw, h, -hd)), side, m);
  b.add(quad(V(-hw, 0, -hd), V(-hw, 0, hd), V(-hw, h, hd), V(-hw, h, -hd)), side, m);
  b.add(quad(V(hw, 0, hd), V(hw, 0, -hd), V(hw, h, -hd), V(hw, h, hd)), side, m);
  const sl = lam("slate", () => ({ map: slateTex() })), tr = lam("hausTrim", () => ({ color: "#d9c39c" }));
  b.add(box(-hw - 0.3, hw + 0.3, h - 0.1, h + 0.5, -hd - 0.3, hd + 0.3), tr, m); // cornice
  const rh = 3.4, inset = 1.6;
  const R = (px: number, py: number, pz: number) => V(px, py, pz);
  b.add(quad(R(-hw, h + 0.5, hd), R(hw, h + 0.5, hd), R(hw - inset, h + rh, hd - inset), R(-hw + inset, h + rh, hd - inset), w / 4, 1), sl, m);
  b.add(quad(R(hw, h + 0.5, -hd), R(-hw, h + 0.5, -hd), R(-hw + inset, h + rh, -hd + inset), R(hw - inset, h + rh, -hd + inset), w / 4, 1), sl, m);
  b.add(quad(R(-hw, h + 0.5, -hd), R(-hw, h + 0.5, hd), R(-hw + inset, h + rh, hd - inset), R(-hw + inset, h + rh, -hd + inset), d / 4, 1), sl, m);
  b.add(quad(R(hw, h + 0.5, hd), R(hw, h + 0.5, -hd), R(hw - inset, h + rh, -hd + inset), R(hw - inset, h + rh, hd - inset), d / 4, 1), sl, m);
  b.add(quad(R(-hw + inset, h + rh, hd - inset), R(hw - inset, h + rh, hd - inset), R(hw - inset, h + rh, -hd + inset), R(-hw + inset, h + rh, -hd + inset), 1, 1), sl, m);
  const nd = Math.max(1, Math.floor(w / 3.2));
  for (let i = 0; i < nd; i++) { // dormers
    const cx = -hw + (i + 0.5) * (w / nd);
    b.add(box(cx - 0.6, cx + 0.6, h + 0.9, h + 2.5, hd - 1.2, hd - 0.4), tr, m);
    b.add(box(cx - 0.4, cx + 0.4, h + 1.1, h + 2.2, hd - 0.42, hd - 0.38), lam("dormerGlass", () => ({ color: "#3a4458" })), m);
  }
  for (const cx of [-hw + 1.5, hw - 2]) b.add(box(cx, cx + 0.9, h + rh - 0.4, h + rh + 1.4, -1, 0.6), lam("chimParis", () => ({ color: "#c88a64" })), m);
};
const streetLamp = (b: Batch, x: number, z: number, glow: THREE.Material[], parent: THREE.Object3D) => {
  const iron = lam("lampIron", () => ({ color: "#2b3a34" }));
  b.add(cylY(0.09, 0, 3.6, x, z, 10, 0.06), iron);
  b.add(cylY(0.22, 0, 0.5, x, z, 10, 0.16), iron);
  b.add(new THREE.ConeGeometry(0.28, 0.3, 6).translate(x, 4.2, z), iron);
  const m = new THREE.Mesh(new THREE.BoxGeometry(0.34, 0.45, 0.34).translate(x, 3.85, z), glow[0]); m.layers.set(NOINK); parent.add(m);
};
export class Champ {
  root = new THREE.Group();
  constructor(parent: THREE.Object3D, kit: Kit) {
    parent.add(this.root);
    const b = new Batch(), T = TOWER;
    b.add(floorQ(-700, 700, -700, 700, -0.02, 3), lam("parisGrass", () => ({ map: grassHD() })));
    // gravel: around the tower and the central avenue + two side alleys down the Champ de Mars
    b.add(floorQ(T.x - 110, T.x + 110, T.z - 110, T.z + 110, 0.0, 4), lam("gravel", () => ({ map: gravelTex() })));
    b.add(floorQ(-9, 9, T.z + 100, CAFE.z0 + 2, 0.01, 4), lam("gravel", () => ({ map: gravelTex() })));
    for (const s of [-1, 1]) b.add(floorQ(s * 44 - 4, s * 44 + 4, T.z + 100, CAFE.z0, 0.01, 4), lam("gravel", () => ({ map: gravelTex() })));
    // flower beds and hedges along the lawn, rows of trees
    for (const s of [-1, 1]) for (let z = T.z + 125; z < CAFE.z0 - 10; z += 14) {
      prop(b, kit, "tree_oak", s * 58, 0, z, 9, z);
      prop(b, kit, "tree_default", s * 30, 0, z + 7, 7, z * 2);
      prop(b, kit, "hedge", s * 13, 0, z + 3, 1.0, Math.PI / 2);
    }
    for (const s of [-1, 1]) for (let z = T.z + 120; z < CAFE.z0 - 10; z += 9) prop(b, kit, z % 2 ? "flower_redA" : "flower_yellowA", s * 11, 0, z, 0.6, z);
    // Haussmann blocks framing the lawn (both sides) and behind the tower across the river
    let k = 0;
    for (const s of [-1, 1]) for (let z = T.z - 40; z < CAFE.z0 - 20; z += 34, k++) haus(b, s * 92, z, 30, 18, 6, s > 0 ? -Math.PI / 2 : Math.PI / 2, k);
    for (let x = -240; x < 240; x += 34, k++) haus(b, x, T.z - 320, 30, 18, 6, 0, k);
    const glow = [hdr(2.6, 1.9, 1.0)];
    for (const s of [-1, 1]) for (let z = T.z + 118; z < CAFE.z0; z += 22) streetLamp(b, s * 10, z, glow, this.root);
    b.build(this.root, true);
    void CHAMP;
  }
}

// ---------------- the café street (Paris; and, looking the other way, the Austrian morning) ----------------
export class CafeStreet {
  root = new THREE.Group();
  constructor(parent: THREE.Object3D, kit: Kit) {
    parent.add(this.root);
    const C = CAFE, b = new Batch();
    b.add(floorQ(-C.half, C.half, C.z0, C.z1 + 80, 0.02, 2), lam("cafeCobble", () => ({ map: cobbleHD() })));
    for (const s of [-1, 1]) b.add(box(s * C.half - (s > 0 ? 3.2 : 0), s * C.half + (s > 0 ? 0 : 3.2), 0, 0.16, C.z0, C.z1 + 80), lam("kerb", () => ({ color: "#d9cfbe" })));
    let k = 3;
    for (const s of [-1, 1]) for (let z = C.z0 + 8; z < C.z1 + 60; z += 24, k++) haus(b, s * (C.half + 9), z, 22, 18, 6 + (k % 2), s > 0 ? -Math.PI / 2 : Math.PI / 2, k);
    // the far end (+z): a square with a green baroque dome (the Austrian morning looks this way)
    const D = { x: 0, z: C.z1 + 130 };
    b.add(box(D.x - 22, D.x + 22, 0, 22, D.z - 12, D.z + 12), lam("domeHall", () => ({ color: "#efe0c2" })));
    b.add(cylY(12, 22, 30, D.x, D.z, 32), lam("domeDrum", () => ({ color: "#e6d3ad" })));
    b.add(new THREE.SphereGeometry(12, 32, 16, 0, TAU, 0, Math.PI / 2).translate(D.x, 30, D.z), lam("domeCopper", () => ({ color: "#5fae96" })));
    b.add(cylY(1.4, 41, 46, D.x, D.z, 12, 0.8), lam("domeCopper", () => ({ color: "#5fae96" })));
    for (const s of [-1, 1]) b.add(cylY(2.6, 0, 34, D.x + s * 30, D.z + 6, 16, 2.2), lam("domeHall", () => ({ color: "#efe0c2" })));
    // the café terrace on the west side (x < 0): awning, tables, chairs, plants
    const tz = C.terraceZ, ax = -C.half;
    const awn = lam("awningRed", () => ({ map: awningTex("#c0353a", "#f4f1ea"), side: THREE.DoubleSide }));
    const awn2 = lam("awningGreen", () => ({ map: awningTex("#2f6a4a", "#f4f1ea"), side: THREE.DoubleSide }));
    b.add(quad(V(ax, 3.6, tz - 9), V(ax, 3.6, tz + 9), V(ax + 3.6, 2.7, tz + 9), V(ax + 3.6, 2.7, tz - 9), 6, 1), awn);
    b.add(quad(V(ax + 3.6, 2.7, tz - 9), V(ax + 3.6, 2.7, tz + 9), V(ax + 3.6, 2.3, tz + 9), V(ax + 3.6, 2.3, tz - 9), 6, 0.2), awn);
    b.add(quad(V(-ax, 3.6, tz + 60), V(-ax, 3.6, tz + 44), V(-ax - 3.6, 2.7, tz + 44), V(-ax - 3.6, 2.7, tz + 60), 6, 1), awn2);
    const wood = lam("cafeWood", () => ({ color: "#7a4b2a" })), top = lam("cafeTop", () => ({ color: "#efe8da" })), chair = lam("cafeChair", () => ({ color: "#3f6a4a" }));
    for (const [dx, dz] of [[1.4, -6], [2.6, -2.5], [1.3, 1.2], [2.7, 4.6], [1.5, 7.6], [-0, 0]] as [number, number][]) {
      if (dx === 0) continue;
      const x = ax + dx, z = tz + dz;
      b.add(cylY(0.38, 0.72, 0.76, x, z, 20), top);
      b.add(cylY(0.04, 0, 0.72, x, z, 8), wood);
      for (const a of [0.6, 3.6]) {
        const cx = x + Math.cos(a) * 0.62, cz = z + Math.sin(a) * 0.62;
        b.add(box(cx - 0.2, cx + 0.2, 0.44, 0.48, cz - 0.2, cz + 0.2), chair);
        b.add(box(cx - 0.2, cx + 0.2, 0.48, 0.95, cz - 0.02 + Math.sin(a) * 0.18, cz + 0.02 + Math.sin(a) * 0.18), chair);
        for (const [ox, oz] of [[-0.17, -0.17], [0.17, -0.17], [-0.17, 0.17], [0.17, 0.17]]) b.add(cylY(0.018, 0, 0.44, cx + ox, cz + oz, 6), chair);
      }
    }
    for (const z of [tz - 10, tz + 10]) prop(b, kit, "plant_bushLarge", ax + 0.6, 0, z, 1.3, z);
    const top2 = lam("cafeTop2", () => ({ color: "#f4f1ea" })), chair2 = lam("cafeChair2", () => ({ color: "#b8332e" }));
    for (const [x, z] of EAST_TABLES) {
      b.add(cylY(0.38, 0.72, 0.76, x, z, 20), top2);
      b.add(cylY(0.04, 0, 0.72, x, z, 8), wood);
      for (const a of [0.6, 3.6]) {
        const cx = x + Math.cos(a) * 0.62, cz = z + Math.sin(a) * 0.62;
        b.add(box(cx - 0.2, cx + 0.2, 0.44, 0.48, cz - 0.2, cz + 0.2), chair2);
        b.add(box(cx - 0.2, cx + 0.2, 0.48, 0.95, cz - 0.02 + Math.sin(a) * 0.18, cz + 0.02 + Math.sin(a) * 0.18), chair2);
      }
    }
    // Austrian red-white-red flags on poles along the far (+z) end of the street
    const flag = new THREE.MeshBasicMaterial({ map: austriaTex(), side: THREE.DoubleSide, fog: false });
    for (const [x, z] of [[-C.half + 0.6, tz + 70], [C.half - 0.6, tz + 82], [-C.half + 0.6, tz + 100], [C.half - 0.6, tz + 118]] as [number, number][]) {
      b.add(cylY(0.06, 0, 8.5, x, z, 8), lam("flagPole", () => ({ color: "#e8e4da" })));
      const fm = new THREE.Mesh(new THREE.PlaneGeometry(2.6, 1.7), flag); fm.position.set(x + (x < 0 ? 1.3 : -1.3), 7.5, z); fm.layers.set(NOINK); this.root.add(fm);
    }
    const glow = [hdr(2.6, 1.9, 1.0)];
    for (let z = C.z0 + 20; z < C.z1 + 50; z += 26) { streetLamp(b, -C.half + 0.6 + 2.6, z + 13, glow, this.root); streetLamp(b, C.half - 0.6 - 2.6, z, glow, this.root); }
    for (let z = C.z0 + 30; z < C.z1 + 50; z += 26) prop(b, kit, "tree_default", C.half - 1.8, 0, z + 6, 7, z);
    b.build(this.root, true);
  }
}

// ---------------- the limousine ----------------
export class Limo {
  root = new THREE.Group();
  private wheels: THREE.Mesh[] = [];
  constructor(parent: THREE.Object3D) {
    parent.add(this.root);
    const g = this.root, body = lam("limoBody", () => ({ color: "#1f2330" })), trim = lam("limoTrim", () => ({ color: "#c9ccd2" })), glass = lam("limoGlass", () => ({ color: "#6f8fb5" }));
    const red = lam("limoRed", () => ({ color: "#8c2a32" }));
    // the car points along +z: long bonnet in front, cabin behind, running boards, separate round fenders
    add(box(-0.85, 0.85, 0.55, 1.25, -2.6, 2.4), body, g);                 // chassis + body
    add(box(-0.72, 0.72, 1.25, 1.55, 0.9, 2.4), body, g);                  // bonnet
    add(box(-0.82, 0.82, 2.17, 2.33, -2.45, 0.8), body, g);                // roof
    add(box(-0.8, 0.8, 1.25, 2.2, -2.45, -2.3), body, g);                  // back panel
    for (const z of [-2.38, -0.85, 0.72]) for (const x of [-0.76, 0.76]) add(box(x - 0.05, x + 0.05, 1.25, 2.2, z - 0.06, z + 0.06), body, g); // pillars
    for (const z of [-1.75, -0.2]) add(box(-0.7, 0.7, 1.25, 1.75, z - 0.12, z + 0.12), red, g); // seat backs
    for (const s of [-1, 1]) {
      add(box(s * 0.86 - 0.12, s * 0.86 + 0.12, 0.42, 0.48, -1.9, 1.6), trim, g); // running board
      add(box(s * 0.86 - 0.02, s * 0.86 + 0.02, 0.9, 1.0, -2.6, 2.4), red, g);    // coachline
    }
    add(box(-0.74, 0.74, 2.0, 2.17, 0.7, 0.78), body, g);                 // windscreen header
    void glass;
    add(box(-0.7, 0.7, 0.62, 1.5, 2.4, 2.5), trim, g);                     // radiator
    for (const s of [-1, 1]) {
      const hl = new THREE.Mesh(new THREE.SphereGeometry(0.17, 14, 10).translate(s * 0.55, 1.45, 2.55), hdr(2.4, 2.2, 1.6)); hl.layers.set(NOINK); g.add(hl);
      add(cylY(0.2, 1.3, 1.6, s * 0.55, 2.5, 14), trim, g);
    }
    const wg = new THREE.CylinderGeometry(0.48, 0.48, 0.26, 24).rotateZ(Math.PI / 2), wm = lam("limoTyre", () => ({ color: "#1b1b20" })), hub = lam("limoHub", () => ({ color: "#e8e4da" }));
    for (const [x, z] of [[-0.9, 1.75], [0.9, 1.75], [-0.9, -1.85], [0.9, -1.85]]) {
      const w = add(wg.clone(), wm, g); w.position.set(x, 0.48, z); this.wheels.push(w);
      const h = add(new THREE.CylinderGeometry(0.24, 0.24, 0.28, 12).rotateZ(Math.PI / 2), hub, w); h.position.set(0, 0, 0);
      add(new THREE.SphereGeometry(0.62, 18, 10, 0, Math.PI, 0, Math.PI).rotateY(Math.PI / 2).scale(0.42, 0.62, 1.05).translate(x, 0.55, z), body, g); // fender
    }
    add(box(-0.5, 0.5, 2.33, 2.5, -2.3, -1.4), lam("limoTrunk", () => ({ color: "#3a2a22" })), g); // luggage on the roof
  }
  /** car at (x, z) heading along +z, travelled distance s (wheel spin) */
  update(x: number, z: number, yaw: number, s: number, visible: boolean) {
    this.root.visible = visible;
    this.root.position.set(x, 0, z); this.root.rotation.y = yaw;
    for (const w of this.wheels) w.rotation.x = s / 0.48;
  }
}

// ---------------- the hotel salon ----------------
export const SALON = { w: 14, d: 10, h: 5.2 };
/** chairs: [x from the room centre, z, back side (-1 = away from the camera toward -z, 0 = no back)] */
export const SALON_CHAIRS: [number, number, number][] = [[-2.0, -2.25, -1], [-1.2, -0.15, 0], [-0.4, -2.25, -1], [0.4, -0.15, 0], [1.2, -2.25, -1]];
export class Hotel {
  root = new THREE.Group();
  constructor(parent: THREE.Object3D) {
    parent.add(this.root);
    const H = HOTEL, S = SALON, b = new Batch();
    room(this.root, H.x, H.z, S.w, S.d, S.h, lam("salonCarpet", () => ({ map: carpetTex() })), lam("salonWall", () => ({ map: salonWall() })), lam("salonCeil", () => ({ color: "#f6ecd8" })));
    const z0 = H.z - S.d / 2, gold = lam("salonGold", () => ({ color: "#d9a64a" })), wood = lam("salonWood", () => ({ color: "#5a3424" }));
    // two tall windows on the back wall with the view of the tower, red drapes, gold pelmets
    const view = new THREE.MeshBasicMaterial({ map: viewTex(), fog: false });
    for (const wx of [-3.6, 3.6]) {
      const m = new THREE.Mesh(new THREE.PlaneGeometry(2.2, 3.6), view); m.position.set(H.x + wx, 2.4, z0 + 0.03); m.layers.set(NOINK); this.root.add(m);
      b.add(box(H.x + wx - 1.2, H.x + wx + 1.2, 0.5, 0.6, z0, z0 + 0.12), lam("salonSill", () => ({ color: "#f6ecd8" })));
      b.add(box(H.x + wx - 0.04, H.x + wx + 0.04, 0.6, 4.2, z0 + 0.03, z0 + 0.08), lam("salonMullion", () => ({ color: "#f6ecd8" })));
      b.add(box(H.x + wx - 1.1, H.x + wx + 1.1, 2.9, 2.96, z0 + 0.03, z0 + 0.08), lam("salonMullion", () => ({ color: "#f6ecd8" })));
      for (const s of [-1, 1]) b.add(box(H.x + wx + s * 1.25 - 0.32, H.x + wx + s * 1.25 + 0.32, 0, 4.6, z0 + 0.05, z0 + 0.4), lam("salonDrape", () => ({ color: "#9c2a2e" })));
      b.add(box(H.x + wx - 1.75, H.x + wx + 1.75, 4.4, 4.75, z0 + 0.05, z0 + 0.45), gold);
    }
    // a portrait in a gold frame between the windows
    b.add(box(H.x - 0.9, H.x + 0.9, 1.8, 3.6, z0 + 0.02, z0 + 0.12), gold);
    b.add(quad(V(H.x - 0.75, 1.95, z0 + 0.13), V(H.x + 0.75, 1.95, z0 + 0.13), V(H.x + 0.75, 3.45, z0 + 0.13), V(H.x - 0.75, 3.45, z0 + 0.13)), lam("salonPainting", () => ({ color: "#4f6f5a" })));
    // the long table with a green cloth, six chairs, papers and the fake letterhead
    const tz = H.z - 1.2;
    b.add(box(H.x - 2.8, H.x + 2.8, 0.74, 0.8, tz - 0.75, tz + 0.75), lam("salonCloth", () => ({ color: "#2f6a4a" })));
    b.add(box(H.x - 2.7, H.x + 2.7, 0.62, 0.74, tz - 0.7, tz + 0.7), wood);
    for (const [x, z] of [[-2.5, -0.55], [2.5, -0.55], [-2.5, 0.55], [2.5, 0.55]]) b.add(box(H.x + x - 0.07, H.x + x + 0.07, 0, 0.62, tz + z - 0.07, tz + z + 0.07), wood);
    for (let i = 0; i < 4; i++) b.add(box(H.x - 2 + i * 1.3, H.x - 1.5 + i * 1.3, 0.8, 0.805, tz - 0.3 + (i % 2) * 0.2, tz + 0.05 + (i % 2) * 0.2), lam("salonPaper", () => ({ color: "#f7f1e1" })));
    const chairM = lam("salonChair", () => ({ color: "#7a3a2a" }));
    for (const [x, z, back] of SALON_CHAIRS) {
      b.add(box(H.x + x - 0.24, H.x + x + 0.24, 0.42, 0.48, z - 0.24, z + 0.24), chairM);
      for (const [ox, oz] of [[-0.2, -0.2], [0.2, -0.2], [-0.2, 0.2], [0.2, 0.2]]) b.add(box(H.x + x + ox - 0.025, H.x + x + ox + 0.025, 0, 0.42, z + oz - 0.025, z + oz + 0.025), wood);
      if (back) b.add(box(H.x + x - 0.24, H.x + x + 0.24, 0.48, 1.05, z + back * 0.21 - 0.03, z + back * 0.21 + 0.03), chairM);
    }
    b.build(this.root, true);
    // chandelier: gold rings, HDR bulbs
    const ch = new THREE.Group(); ch.position.set(H.x, S.h, tz); this.root.add(ch);
    add(cylY(0.03, -1.3, 0, 0, 0, 6), gold, ch, false);
    add(new THREE.TorusGeometry(0.75, 0.05, 8, 32).rotateX(Math.PI / 2).translate(0, -1.4, 0), gold, ch, false);
    add(new THREE.TorusGeometry(0.42, 0.04, 8, 24).rotateX(Math.PI / 2).translate(0, -1.15, 0), gold, ch, false);
    const bulb = hdr(3.2, 2.4, 1.3);
    for (let k = 0; k < 10; k++) { const a = (k / 10) * TAU, r = k % 2 ? 0.42 : 0.75; const m = new THREE.Mesh(new THREE.SphereGeometry(0.07, 10, 8), bulb); m.position.set(Math.cos(a) * r, k % 2 ? -1.07 : -1.32, Math.sin(a) * r); m.layers.set(NOINK); ch.add(m); }
  }
}

// ---------------- Poisson's parlour ----------------
export class Home {
  root = new THREE.Group();
  constructor(parent: THREE.Object3D) {
    parent.add(this.root);
    const H = HOME, b = new Batch(), W = 9, D = 7, Ht = 3.4;
    room(this.root, H.x, H.z, W, D, Ht, lam("homeFloor", () => ({ map: parquet() })), lam("homePaper", () => ({ map: wallpaper() })), lam("homeCeil", () => ({ color: "#efe3c8" })));
    const z0 = H.z - D / 2;
    // fireplace with a mirror, a sofa, a lamp, a window
    b.add(box(H.x - 1.0, H.x + 1.0, 0, 1.2, z0, z0 + 0.45), lam("homeMarble", () => ({ color: "#f0ebe2" })));
    b.add(box(H.x - 0.55, H.x + 0.55, 0, 0.8, z0 + 0.44, z0 + 0.46), lam("homeHearth", () => ({ color: "#2e2a2a" })));
    b.add(box(H.x - 0.7, H.x + 0.7, 1.4, 2.6, z0 + 0.01, z0 + 0.06), lam("homeMirror", () => ({ color: "#b8cde0" })));
    b.add(box(H.x - 0.78, H.x + 0.78, 1.34, 2.68, z0, z0 + 0.04), lam("salonGold", () => ({ color: "#d9a64a" })));
    const sofa = lam("homeSofa", () => ({ color: "#b5653f" }));
    b.add(box(H.x + 1.6, H.x + 3.8, 0, 0.48, z0 + 1.0, z0 + 1.9), sofa);
    b.add(box(H.x + 1.6, H.x + 3.8, 0.48, 1.05, z0 + 0.8, z0 + 1.1), sofa);
    for (const x of [1.5, 3.7]) b.add(box(H.x + x, H.x + x + 0.2, 0, 0.75, z0 + 0.8, z0 + 1.9), sofa);
    b.add(cylY(0.03, 0, 1.6, H.x - 2.8, z0 + 0.8, 8), lam("lampIron", () => ({ color: "#2b3a34" })));
    b.add(new THREE.ConeGeometry(0.32, 0.38, 16, 1, true).translate(H.x - 2.8, 1.72, z0 + 0.8), lam("homeShade", () => ({ color: "#f2d590", side: THREE.DoubleSide })));
    b.add(box(H.x - 4.0, H.x - 2.0, 0, 0.05, z0 + 2.0, z0 + 4.5), lam("homeRug", () => ({ color: "#3f6fb5" })));
    b.build(this.root, true);
    const lamp = new THREE.Mesh(new THREE.SphereGeometry(0.1, 10, 8), hdr(3.0, 2.3, 1.2)); lamp.position.set(H.x - 2.8, 1.62, z0 + 0.8); lamp.layers.set(NOINK); this.root.add(lamp);
    const win = new THREE.Mesh(new THREE.PlaneGeometry(1.6, 2.0), new THREE.MeshBasicMaterial({ map: viewTex(), fog: false })); win.position.set(H.x - 2.9, 1.9, z0 + 0.02); win.layers.set(NOINK); this.root.add(win);
  }
}

// ---------------- the ministry hall: clerks at desks ----------------
export const DESKS_Z = [1.6, -0.6, -2.8];
export class Office {
  root = new THREE.Group();
  constructor(parent: THREE.Object3D) {
    parent.add(this.root);
    const O = OFFICE, b = new Batch(), W = 8, D = 10, Ht = 4.2;
    room(this.root, O.x, O.z, W, D, Ht, lam("officeFloor", () => ({ map: parquet() })), lam("officeWall", () => ({ map: officeWall() })), lam("homeCeil", () => ({ color: "#efe3c8" })));
    const x0 = O.x - W / 2, wood = lam("deskWood", () => ({ color: "#6a4228" })), green = lam("deskLeather", () => ({ color: "#3f6a4a" }));
    for (const dz of DESKS_Z) {
      const x = O.x - 0.9, z = O.z + dz;
      b.add(box(x - 0.45, x + 0.45, 0, 0.78, z - 0.8, z + 0.8), wood);
      b.add(box(x - 0.42, x + 0.42, 0.78, 0.8, z - 0.76, z + 0.76), green);
      for (let k = 0; k < 4; k++) b.add(box(x - 0.3, x + 0.1, 0.8 + k * 0.05, 0.85 + k * 0.05, z - 0.6 + (k % 2) * 0.1, z - 0.2 + (k % 2) * 0.1), lam("salonPaper", () => ({ color: "#f7f1e1" })));
      b.add(cylY(0.07, 0.8, 0.9, x + 0.1, z + 0.5, 12), lam("inkwell", () => ({ color: "#2e2a36" })));
      // a pigeonhole cabinet on the left wall behind each clerk
      b.add(box(x0, x0 + 0.5, 0, 2.6, z - 0.9, z + 0.9), wood);
      for (let r = 0; r < 4; r++) for (let c = 0; c < 4; c++) b.add(box(x0 + 0.49, x0 + 0.51, 0.8 + r * 0.44, 1.14 + r * 0.44, z - 0.8 + c * 0.42, z - 0.42 + c * 0.42), lam("pigeon", () => ({ color: "#3a2418" })));
    }
    // a wall clock on the back wall
    const z0 = O.z - D / 2;
    b.add(new THREE.CylinderGeometry(0.55, 0.55, 0.1, 32).rotateX(Math.PI / 2).translate(O.x + 0.6, 3.2, z0 + 0.05), wood);
    b.build(this.root, true);
    const face = new THREE.Mesh(new THREE.CircleGeometry(0.48, 32), lam("clockFace", () => ({ color: "#f7f1e1" }))); face.position.set(O.x + 0.6, 3.2, z0 + 0.11); this.root.add(face);
    const hand = new THREE.Mesh(box(-0.02, 0.02, 0, 0.36, 0, 0.02), lam("clockHand", () => ({ color: "#2e2a36" }))); hand.position.set(O.x + 0.6, 3.2, z0 + 0.12); hand.rotation.z = -0.8; this.root.add(hand);
    const win = new THREE.Mesh(new THREE.PlaneGeometry(1.6, 2.2), new THREE.MeshBasicMaterial({ map: viewTex(), fog: false })); win.position.set(O.x + 2.4, 2.1, z0 + 0.02); win.layers.set(NOINK); this.root.add(win);
    const fl = new THREE.Mesh(new THREE.PlaneGeometry(1.5, 1.0), lam("franceFlag", () => ({ map: franceTex() }))); fl.position.set(O.x - 1.2, 2.9, z0 + 0.03); this.root.add(fl);
  }
}

// ---------------- the countryside, the Alps and the train to Austria ----------------
export const TRACK_Z = COUNTRY.z;
export const TRAIN_V = 14; // m/s
export class Country {
  root = new THREE.Group();
  private train = new THREE.Group();
  private wheels: THREE.Mesh[] = [];
  constructor(parent: THREE.Object3D, kit: Kit) {
    parent.add(this.root);
    const C = COUNTRY, b = new Batch();
    b.add(floorQ(C.x - 900, C.x + 900, C.z - 900, C.z + 400, 0, 40), lam("fields", () => ({ map: fieldTex() })));
    // gentle hills, then the Alps with snow
    for (let i = 0; i < 9; i++) b.add(new THREE.SphereGeometry(60 + (i % 3) * 25, 24, 12, 0, TAU, 0, Math.PI / 2).scale(1.8, 0.35, 1).translate(C.x - 600 + i * 150, 0, C.z - 220 - (i % 2) * 90), lam("hill", () => ({ color: "#7ab24e" })));
    for (let i = 0; i < 11; i++) {
      const x = C.x - 800 + i * 160, z = C.z - 620 - (i % 3) * 60, h = 220 + ((i * 37) % 90), r = 150 + (i % 2) * 40;
      b.add(new THREE.ConeGeometry(r, h, 7).translate(x, h / 2 - 5, z), lam("alp", () => ({ color: "#7f8fb3" })));
      b.add(new THREE.ConeGeometry(r * 0.34, h * 0.34, 7).translate(x, h - 5 - h * 0.17 + 0.5, z), lam("snow", () => ({ color: "#f4f6fb" })));
    }
    // the railway: ballast, two rails, sleepers; telegraph poles beside it
    b.add(box(C.x - 900, C.x + 900, 0, 0.18, C.z - 1.6, C.z + 1.6), lam("ballast", () => ({ color: "#a89a86" })));
    for (const s of [-0.72, 0.72]) b.add(box(C.x - 900, C.x + 900, 0.28, 0.38, C.z + s - 0.04, C.z + s + 0.04), lam("rail", () => ({ color: "#8d949c" })));
    const sl = lam("sleeper", () => ({ color: "#6a4a32" }));
    for (let x = C.x - 900; x < C.x + 900; x += 0.9) b.add(box(x - 0.12, x + 0.12, 0.18, 0.28, C.z - 1.25, C.z + 1.25), sl);
    const pole = lam("pole", () => ({ color: "#7a5a3a" }));
    for (let x = C.x - 880; x < C.x + 880; x += 40) { b.add(cylY(0.12, 0, 7, x, C.z - 5, 8), pole); b.add(box(x - 0.08, x + 0.08, 6.4, 6.55, C.z - 6, C.z - 4), pole); }
    for (let i = 0; i < 40; i++) prop(b, kit, i % 3 ? "tree_default" : "tree_oak", C.x - 800 + ((i * 97) % 1600), 0, C.z - 30 - ((i * 53) % 160), 7 + (i % 4), i);
    for (let i = 0; i < 16; i++) prop(b, kit, "tree_fat", C.x - 800 + ((i * 131) % 1600), 0, C.z + 25 + ((i * 41) % 80), 6 + (i % 3), i);
    b.build(this.root, true);
    // ---- the train (points along +x): locomotive, tender, two carriages, an open rear platform ----
    this.root.add(this.train);
    const T = this.train, black = lam("loco", () => ({ color: "#26262e" })), redW = lam("locoRed", () => ({ color: "#b8332e" })), brass = lam("brass", () => ({ color: "#e8c45a" }));
    const car = lam("carriage", () => ({ map: carriageTex() })), carRoof = lam("carRoof", () => ({ color: "#3a3a40" })), carEnd = lam("carEnd", () => ({ color: "#2f6a4a" }));
    add(new THREE.CylinderGeometry(0.95, 0.95, 7.5, 20).rotateZ(Math.PI / 2).translate(3.6, 2.15, 0), black, T); // boiler
    add(cylY(0.32, 3.0, 4.2, 6.6, 0, 14, 0.42), black, T);              // chimney
    add(cylY(0.36, 3.0, 3.6, 4.4, 0, 14, 0.3), brass, T);               // dome
    add(box(-1.4, 0.6, 1.0, 4.0, -1.25, 1.25), black, T);               // cab
    add(box(-1.6, 0.8, 4.0, 4.2, -1.4, 1.4), redW, T);                  // cab roof
    add(new THREE.ConeGeometry(1.0, 1.0, 4).rotateZ(-Math.PI / 2).rotateX(Math.PI / 4).translate(7.6, 0.75, 0), redW, T); // cowcatcher
    const lamp = new THREE.Mesh(new THREE.SphereGeometry(0.22, 12, 8).translate(7.35, 2.5, 0), hdr(3, 2.6, 1.6)); lamp.layers.set(NOINK); T.add(lamp);
    add(box(-5.6, -1.6, 0.8, 2.9, -1.3, 1.3), black, T);                // tender
    const wg = new THREE.CylinderGeometry(0.62, 0.62, 0.2, 20).rotateX(Math.PI / 2);
    for (const x of [1.4, 3.0, 4.6]) for (const z of [-1.0, 1.0]) { const w = add(wg.clone(), redW, T); w.position.set(x, 0.85, z); this.wheels.push(w); }
    for (const x of [6.4, -2.4, -4.8]) for (const z of [-1.0, 1.0]) { const w = add(new THREE.CylinderGeometry(0.42, 0.42, 0.2, 16).rotateX(Math.PI / 2), redW, T); w.position.set(x, 0.62, z); this.wheels.push(w); }
    for (let c = 0; c < 2; c++) {
      const x1 = -6.4 - c * 13.2, x0 = x1 - 12.4;
      add(box(x0, x1, 1.0, 3.6, -1.4, 1.4), carEnd, T);
      for (const s of [-1, 1]) { const q = add(quad(s > 0 ? V(x0, 1.0, 1.41) : V(x1, 1.0, -1.41), s > 0 ? V(x1, 1.0, 1.41) : V(x0, 1.0, -1.41), s > 0 ? V(x1, 3.6, 1.41) : V(x0, 3.6, -1.41), s > 0 ? V(x0, 3.6, 1.41) : V(x1, 3.6, -1.41)), car, T); q.castShadow = false; }
      add(box(x0 - 0.2, x1 + 0.2, 3.6, 3.85, -1.5, 1.5), carRoof, T);
      for (const x of [x0 + 1.6, x0 + 3.0, x1 - 3.0, x1 - 1.6]) for (const z of [-1.0, 1.0]) { const w = add(new THREE.CylinderGeometry(0.45, 0.45, 0.2, 16).rotateX(Math.PI / 2), black, T); w.position.set(x, 0.65, z); this.wheels.push(w); }
    }
    // the open rear platform of the last carriage (where the con man stands): floor, railing, posts, a little roof
    const xr = -6.4 - 13.2 - 12.4;
    add(box(xr - 1.8, xr, 1.0, 1.14, -1.4, 1.4), black, T);
    for (const z of [-1.35, 1.35]) add(box(xr - 1.8, xr, 1.95, 2.0, z - 0.03, z + 0.03), brass, T);
    add(box(xr - 1.83, xr - 1.77, 1.14, 2.0, -1.4, 1.4), brass, T);
    for (const z of [-1.35, 0, 1.35]) add(box(xr - 1.82, xr - 1.76, 1.14, 3.7, z - 0.04, z + 0.04), black, T);
    add(box(xr - 1.9, xr, 3.7, 3.82, -1.5, 1.5), carRoof, T);
  }
  /** train nose at x (world), z = track */
  update(x: number, visible: boolean) {
    this.train.visible = visible;
    this.train.position.set(x, 0.2, TRACK_Z);
    for (const w of this.wheels) w.rotation.z = -x / 0.6;
  }
  /** world position of the rear platform floor centre for a train nose at x */
  static rear(x: number): [number, number, number] { return [x - 6.4 - 13.2 - 12.4 - 0.9, 1.34, TRACK_Z]; }
}
