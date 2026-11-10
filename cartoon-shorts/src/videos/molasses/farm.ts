// The headless-chicken film's sets (two-tone lam() geometry, outlined by the world ink). Flicker rules (Nov 7): no two
// surfaces closer than 5 cm (or exactly flush), every painted sign on the DEFAULT layer so it hides what is behind it.
//  Farm (the Olsen yard: one ground plane painted dirt-in-grass, the red barn, the white farmhouse, a rail fence, the
//  chopping stump, hay bales, a trough, poplars, the red mesas of the Colorado National Monument), the Axe stuck in
//  the stump, Desk (the computer analogy), Show (the sideshow tent, banner, ticket booth, pedestal, string lights),
//  Motel (a room at night), Fest (Fruita's main street on Mike the Headless Chicken Day), a second farm for the copycats.
import * as THREE from "three";
import { lam, Batch, V, quad } from "./build";
import { ctex } from "./paint";
import { NOINK } from "./ink";
import { BLOCK, BARN, HOUSE, SCALE, DESK, SHOW, MOTEL, FEST, COPY } from "./places";

const TAU = Math.PI * 2;
export const box = (x0: number, x1: number, y0: number, y1: number, z0: number, z1: number) =>
  new THREE.BoxGeometry(x1 - x0, y1 - y0, z1 - z0).translate((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2);
export const cylY = (r: number, y0: number, y1: number, x: number, z: number, seg = 24, r2 = r) =>
  new THREE.CylinderGeometry(r2, r, y1 - y0, seg).translate(x, (y0 + y1) / 2, z);
const add = (g: THREE.BufferGeometry, m: THREE.Material | THREE.Material[], parent: THREE.Object3D, cast = true) => {
  const mesh = new THREE.Mesh(g, m); mesh.castShadow = cast; mesh.receiveShadow = true; parent.add(mesh); return mesh;
};
const hdr = (r: number, g: number, b: number) => new THREE.MeshBasicMaterial({ color: new THREE.Color(r, g, b), fog: false });
const floorQ = (x0: number, x1: number, z0: number, z1: number, y: number, s: number, uv01 = false) => {
  const g = new THREE.BufferGeometry(), P = [x0, y, z1, x1, y, z1, x1, y, z0, x0, y, z1, x1, y, z0, x0, y, z0];
  g.setAttribute("position", new THREE.Float32BufferAttribute(P, 3));
  const uv: number[] = []; for (let i = 0; i < 6; i++) uv.push(uv01 ? (P[i * 3] - x0) / (x1 - x0) : P[i * 3] / s, uv01 ? 1 - (P[i * 3 + 2] - z0) / (z1 - z0) : P[i * 3 + 2] / s);
  g.setAttribute("uv", new THREE.Float32BufferAttribute(uv, 2)); g.computeVertexNormals(); return g;
};
const limb = (a: THREE.Vector3, b: THREE.Vector3, ra: number, rb: number, seg = 8) => {
  const d = b.clone().sub(a), L = d.length();
  const g = new THREE.CylinderGeometry(rb, ra, L, seg); g.translate(0, L / 2, 0);
  return g.applyQuaternion(new THREE.Quaternion().setFromUnitVectors(V(0, 1, 0), d.normalize())).translate(a.x, a.y, a.z);
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
/** a painted panel on the default layer (hides what is behind it), backed by a board 6 cm behind */
const panel = (parent: THREE.Object3D, tex: THREE.Texture, w: number, h: number, x: number, y: number, z: number, yaw = 0, back?: string) => {
  const g = new THREE.Group(); g.position.set(x, y, z); g.rotation.y = yaw; parent.add(g);
  const m = new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshBasicMaterial({ map: tex })); m.position.z = 0.07; g.add(m);
  if (back) add(box(-w / 2 - 0.06, w / 2 + 0.06, -h / 2 - 0.06, h / 2 + 0.06, -0.06, 0.0), lam("board" + back, () => ({ color: back })), g);
  return g;
};

// ---------------- painted textures ----------------
/** the farm ground (one texture across the whole 200 m plane, so the yard is never a second surface): grass with a
 *  worn dirt yard in the middle and a track out to the road */
const groundTex = () => ctex("farmGround", 2048, 2048, (g0, r) => {
  const g = g0; g.canvas.width = 4096; g.canvas.height = 4096; g.scale(2, 2);
  g.fillStyle = "#86ad5a"; g.fillRect(0, 0, 2048, 2048);
  for (let i = 0; i < 5000; i++) { const x = r() * 2048, y = r() * 2048, s = 4 + r() * 14; g.fillStyle = r() < 0.5 ? "rgba(150,190,96,0.5)" : "rgba(110,150,74,0.45)"; g.beginPath(); g.ellipse(x, y, s, s * 0.6, r() * 3, 0, TAU); g.fill(); }
  g.lineCap = "round"; for (let i = 0; i < 9000; i++) { const x = r() * 2048, y = r() * 2048; g.strokeStyle = r() < 0.5 ? "rgba(170,206,110,0.8)" : "rgba(96,136,64,0.7)"; g.lineWidth = 1.6; g.beginPath(); g.moveTo(x, y); g.lineTo(x + (r() - 0.5) * 3, y - 5 - r() * 5); g.stroke(); }
  const dirt = (cx: number, cy: number, rx: number, ry: number) => { const gr = g.createRadialGradient(cx, cy, 0, cx, cy, 1); g.save(); g.translate(cx, cy); g.scale(rx, ry); gr.addColorStop(0, "rgba(198,156,104,1)"); gr.addColorStop(0.82, "rgba(190,150,100,1)"); gr.addColorStop(1, "rgba(190,150,100,0)"); g.fillStyle = gr; g.beginPath(); g.arc(0, 0, 1, 0, TAU); g.restore(); g.fill(); };
  // yard: centre of the texture = (0, 0); 1 px = 200/2048 m
  const px = (m: number) => 1024 + (m * 2048) / 60;
  dirt(px(0), px(-2), 640, 520);
  for (let k = 0; k < 6; k++) dirt(px(0), px(10 + k * 4), 110, 150);
  for (let i = 0; i < 5000; i++) { const x = px(0) + (r() - 0.5) * 1200, y = px(-2) + (r() - 0.5) * 1000; g.fillStyle = r() < 0.5 ? "rgba(150,110,70,0.5)" : "rgba(226,196,150,0.55)"; g.fillRect(x, y, 3 + r() * 4, 2 + r() * 3); }
});
const grassTile = () => ctex("grassTile", 1024, 1024, (g, r) => {
  g.fillStyle = "#86ad5a"; g.fillRect(0, 0, 1024, 1024);
  for (let i = 0; i < 2500; i++) { const x = r() * 1024, y = r() * 1024, s = 4 + r() * 14; g.fillStyle = r() < 0.5 ? "rgba(150,190,96,0.5)" : "rgba(110,150,74,0.45)"; g.beginPath(); g.ellipse(x, y, s, s * 0.6, r() * 3, 0, TAU); g.fill(); }
  g.lineCap = "round"; for (let i = 0; i < 4500; i++) { const x = r() * 1024, y = r() * 1024; g.strokeStyle = r() < 0.5 ? "rgba(170,206,110,0.8)" : "rgba(96,136,64,0.7)"; g.lineWidth = 1.6; g.beginPath(); g.moveTo(x, y); g.lineTo(x + (r() - 0.5) * 3, y - 5 - r() * 5); g.stroke(); }
});
const barnTex = () => ctex("barnBoards", 512, 512, (g, r) => {
  g.fillStyle = "#b8362e"; g.fillRect(0, 0, 512, 512);
  for (let x = 0; x < 512; x += 32) { g.fillStyle = "rgba(80,20,20,0.35)"; g.fillRect(x, 0, 3, 512); g.fillStyle = r() < 0.5 ? "rgba(210,80,70,0.25)" : "rgba(120,30,30,0.2)"; g.fillRect(x + 4, 0, 26, 512); }
});
const clapTex = () => ctex("clapboard", 512, 512, (g) => {
  g.fillStyle = "#f2ede0"; g.fillRect(0, 0, 512, 512);
  for (let y = 0; y < 512; y += 32) { g.fillStyle = "rgba(150,140,120,0.45)"; g.fillRect(0, y + 28, 512, 4); }
});
const mesaTex = () => ctex("mesaRock", 512, 512, (g, r) => {
  const bands = ["#c4583a", "#d46a42", "#b44c34", "#e08a5a", "#c86040", "#a84430"];
  for (let y = 0; y < 512; y += 32) { g.fillStyle = bands[(y / 32) % bands.length]; g.fillRect(0, y, 512, 32); }
  for (let i = 0; i < 300; i++) { g.fillStyle = r() < 0.5 ? "rgba(120,40,30,0.3)" : "rgba(240,170,120,0.25)"; g.fillRect(r() * 512, r() * 512, 2 + r() * 30, 2 + r() * 4); }
});
const signTex = (key: string, w: number, h: number, bg: string, fg: string, lines: [string, number][], font = "Arial", extra?: (g: CanvasRenderingContext2D) => void) =>
  ctex(key, w, h, (g) => {
    g.fillStyle = bg; g.fillRect(0, 0, w, h);
    g.strokeStyle = fg; g.lineWidth = Math.round(h * 0.04); const m = h * 0.06; g.beginPath(); g.roundRect(m, m, w - 2 * m, h - 2 * m, h * 0.06); g.stroke();
    extra?.(g);
    g.fillStyle = fg; g.textAlign = "center"; g.textBaseline = "middle";
    const tot = lines.reduce((s, [, sz]) => s + sz * 1.15, 0);
    let y = h / 2 - tot / 2;
    for (const [t, sz] of lines) { g.font = `900 ${sz}px ${font}, sans-serif`; y += sz * 0.575; g.fillText(t, w / 2, y, w * 0.86); y += sz * 0.575; }
  });
const henIcon = (g: CanvasRenderingContext2D, x: number, y: number, s: number, col: string) => {
  g.save(); g.translate(x, y); g.scale(s, s); g.fillStyle = col; g.strokeStyle = "#1d1a22"; g.lineWidth = 6;
  g.beginPath(); g.ellipse(0, 0, 60, 42, -0.1, 0, TAU); g.fill(); g.stroke();
  g.beginPath(); g.moveTo(30, -30); g.lineTo(52, -80); g.lineTo(78, -76); g.lineTo(62, -24); g.closePath(); g.fill(); g.stroke(); // neck, no head
  g.beginPath(); g.moveTo(-50, -10); g.lineTo(-96, -60); g.lineTo(-84, 0); g.closePath(); g.fill(); g.stroke();
  g.strokeStyle = "#f2b630"; g.lineWidth = 8; g.beginPath(); g.moveTo(-10, 40); g.lineTo(-14, 80); g.moveTo(14, 40); g.lineTo(18, 80); g.stroke();
  g.restore();
};
const tentTex = () => ctex("tentStripe", 2048, 256, (g) => { for (let i = 0; i < 32; i++) { g.fillStyle = i % 2 ? "#f4efe2" : "#d9382e"; g.fillRect(i * 64, 0, 64, 256); } });
const showBanner = () => ctex("showBanner", 2048, 640, (g) => {
  g.fillStyle = "#1f2a5a"; g.fillRect(0, 0, 2048, 640);
  for (let x = 0; x < 2048; x += 64) { g.fillStyle = "#f6d23a"; g.beginPath(); g.arc(x + 32, 30, 11, 0, TAU); g.arc(x + 32, 610, 11, 0, TAU); g.fill(); }
  henIcon(g, 230, 360, 1.7, "#f6f3ea"); henIcon(g, 1818, 360, 1.7, "#f6f3ea");
  g.textAlign = "center"; g.textBaseline = "middle"; g.lineWidth = 16; g.strokeStyle = "#1d1a22";
  g.font = "italic 900 150px Georgia, serif"; g.fillStyle = "#f6d23a"; g.strokeText("MIRACLE MIKE", 1024, 230, 1400); g.fillText("MIRACLE MIKE", 1024, 230, 1400);
  g.font = "900 108px Arial, sans-serif"; g.fillStyle = "#ffffff"; g.strokeText("THE HEADLESS CHICKEN", 1024, 440, 1420); g.fillText("THE HEADLESS CHICKEN", 1024, 440, 1420);
});
const festBanner = () => ctex("festBanner", 2048, 512, (g) => {
  g.fillStyle = "#f6d23a"; g.fillRect(0, 0, 2048, 512);
  g.fillStyle = "#d9382e"; g.fillRect(0, 0, 2048, 40); g.fillRect(0, 472, 2048, 40);
  henIcon(g, 190, 280, 1.4, "#ffffff"); henIcon(g, 1858, 280, 1.4, "#ffffff");
  g.textAlign = "center"; g.textBaseline = "middle"; g.fillStyle = "#d9382e"; g.strokeStyle = "#ffffff"; g.lineWidth = 14;
  g.font = "900 120px Arial, sans-serif"; g.strokeText("MIKE THE HEADLESS", 1024, 190, 1450); g.fillText("MIKE THE HEADLESS", 1024, 190, 1450);
  g.font = "900 140px Arial, sans-serif"; g.strokeText("CHICKEN DAY", 1024, 350, 1400); g.fillText("CHICKEN DAY", 1024, 350, 1400);
});
const shopTex = (key: string, wall: string, name: string, awning: string) => ctex(key, 1024, 768, (g) => {
  g.fillStyle = wall; g.fillRect(0, 0, 1024, 768);
  g.fillStyle = "#3a2a22"; g.fillRect(0, 700, 1024, 68);
  g.fillStyle = "#9fc4e0"; g.fillRect(80, 380, 360, 300); g.fillRect(600, 380, 340, 300);
  g.fillStyle = "#5a3a26"; g.fillRect(460, 400, 120, 300);
  for (let x = 0; x < 1024; x += 96) { g.fillStyle = x % 192 ? awning : "#ffffff"; g.fillRect(x, 300, 96, 70); }
  g.fillStyle = "#ffffff"; g.fillRect(140, 120, 744, 130); g.fillStyle = "#2a2a36"; g.font = "900 92px Georgia, serif"; g.textAlign = "center"; g.textBaseline = "middle"; g.fillText(name, 512, 188, 700);
  for (let x = 120; x < 1024; x += 220) { g.fillStyle = "#e9e2d0"; g.fillRect(x, 40, 90, 50); }
});
const wallpaper = (key: string, a: string, b: string) => ctex(key, 512, 512, (g) => {
  g.fillStyle = a; g.fillRect(0, 0, 512, 512);
  for (let x = 0; x < 512; x += 64) { g.fillStyle = b; g.fillRect(x, 0, 22, 512); }
  g.fillStyle = "#6a4426"; g.fillRect(0, 400, 512, 112); g.fillStyle = "#f6f0e0"; g.fillRect(0, 396, 512, 8);
});
const nightWindow = () => ctex("nightWin", 256, 320, (g) => {
  const gr = g.createLinearGradient(0, 0, 0, 320); gr.addColorStop(0, "#14204a"); gr.addColorStop(1, "#2f3f78"); g.fillStyle = gr; g.fillRect(0, 0, 256, 320);
  g.fillStyle = "#f6f0c8"; g.beginPath(); g.arc(180, 80, 30, 0, TAU); g.fill(); g.fillStyle = "#14204a"; g.beginPath(); g.arc(194, 72, 26, 0, TAU); g.fill();
  for (let i = 0; i < 20; i++) { g.fillStyle = "#ffffff"; g.fillRect((i * 53) % 256, (i * 97) % 200, 3, 3); }
  g.fillStyle = "#f4efe2"; g.fillRect(124, 0, 8, 320); g.fillRect(0, 156, 256, 8); g.lineWidth = 14; g.strokeStyle = "#f4efe2"; g.strokeRect(0, 0, 256, 320);
  g.fillStyle = "#d9382e"; g.font = "900 34px Arial"; g.textAlign = "center"; g.fillText("MOTEL", 64, 290);
});
const screenTex = (on: boolean) => ctex(on ? "screenOn" : "screenOff", 512, 384, (g) => {
  if (!on) { g.fillStyle = "#14161c"; g.fillRect(0, 0, 512, 384); g.fillStyle = "rgba(255,255,255,0.08)"; g.beginPath(); g.ellipse(160, 110, 120, 60, -0.4, 0, TAU); g.fill(); return; }
  g.fillStyle = "#3f8fd2"; g.fillRect(0, 0, 512, 384);
  henIcon(g, 256, 200, 1.2, "#ffffff");
  g.fillStyle = "#ffffff"; g.font = "900 40px Arial"; g.textAlign = "center"; g.fillText("HELLO!", 256, 340);
});

// ---------------- the farm ----------------
const poplar = (b: Batch, x: number, z: number, h: number, seed: number) => {
  b.add(cylY(0.12, 0, 0.3 * h, x, z, 6), lam("poplarTrunk", () => ({ color: "#7a5a3a" })));
  b.add(new THREE.SphereGeometry(1, 12, 10).scale(0.16 * h, 0.42 * h, 0.16 * h).translate(x, 0.55 * h, z), lam("poplar" + (seed % 3), () => ({ color: ["#5f8a3a", "#6f9a44", "#527a34"][seed % 3] })));
};
const mesa = (b: Batch, x: number, z: number, w: number, h: number, d: number, seed: number) => {
  const rock = lam("mesa", () => ({ map: mesaTex() }));
  b.add(new THREE.CylinderGeometry(1, 1.25, 1, 9).scale(w, h, d).rotateY(seed).translate(x, h / 2, z), rock);
  b.add(new THREE.CylinderGeometry(1.25, 1.9, 1, 9).scale(w, h * 0.35, d).rotateY(seed + 0.3).translate(x, h * 0.175, z), lam("talus", () => ({ color: "#c8865a" })));
};
/** a red gambrel barn facing +z, its door centred at (x, z) */
const barn = (b: Batch, x: number, z: number) => {
  const red = lam("barnRed", () => ({ map: barnTex() })), white = lam("trimWhite", () => ({ color: "#f4efe2" })), roofM = lam("barnRoof", () => ({ color: "#4a4a52", side: THREE.DoubleSide }));
  b.add(box(x - 5, x + 5, 0, 5, z - 12, z), red);
  const sh = new THREE.Shape([new THREE.Vector2(-5.3, 5), new THREE.Vector2(-3.8, 7.6), new THREE.Vector2(0, 9.2), new THREE.Vector2(3.8, 7.6), new THREE.Vector2(5.3, 5)]);
  b.add(new THREE.ExtrudeGeometry(sh, { depth: 12.6, bevelEnabled: false }).translate(x, 0, z - 12.3), roofM);
  b.add(new THREE.ExtrudeGeometry(new THREE.Shape([new THREE.Vector2(-5, 5), new THREE.Vector2(-3.6, 7.4), new THREE.Vector2(0, 8.9), new THREE.Vector2(3.6, 7.4), new THREE.Vector2(5, 5)]), { depth: 0.1, bevelEnabled: false }).translate(x, 0, z + 0.38), red);
  // the big doors: a dark opening with white X braces standing 8 cm proud
  b.add(box(x - 1.8, x + 1.8, 0, 3.6, z, z + 0.08), lam("barnDoor", () => ({ color: "#8a2a24" })));
  for (const [x0, x1] of [[-1.8, 0], [0, 1.8]] as const) {
    b.add(limb(V(x + x0 + 0.1, 0.15, z + 0.14), V(x + x1 - 0.1, 3.45, z + 0.14), 0.07, 0.07, 4), white);
    b.add(limb(V(x + x1 - 0.1, 0.15, z + 0.14), V(x + x0 + 0.1, 3.45, z + 0.14), 0.07, 0.07, 4), white);
  }
  b.add(box(x - 1.95, x + 1.95, 3.6, 3.8, z, z + 0.16), white);
  b.add(box(x - 0.9, x + 0.9, 5.6, 7.0, z + 0.4, z + 0.55), lam("barnDoor", () => ({ color: "#8a2a24" })));
};
const house = (b: Batch, x: number, z: number) => {
  const clap = lam("clapboard", () => ({ map: clapTex() })), roofM = lam("houseRoof", () => ({ color: "#5a4a44", side: THREE.DoubleSide })), trim = lam("trimWhite", () => ({ color: "#f4efe2" }));
  b.add(box(x - 5, x + 5, 0, 5.5, z - 8, z), clap);
  const sh = new THREE.Shape([new THREE.Vector2(-5.6, 5.5), new THREE.Vector2(0, 8.4), new THREE.Vector2(5.6, 5.5)]);
  b.add(new THREE.ExtrudeGeometry(sh, { depth: 8.8, bevelEnabled: false }).translate(x, 0, z - 8.4), roofM);
  b.add(box(x - 5.5, x + 5.5, 2.9, 3.05, z, z + 2.6), roofM); // porch roof
  for (let k = 0; k < 5; k++) b.add(box(x - 5.2 + k * 2.6 - 0.08, x - 5.2 + k * 2.6 + 0.08, 0, 2.9, z + 2.4, z + 2.56), trim);
  b.add(box(x - 5.4, x + 5.4, 0, 0.3, z, z + 2.6), lam("porchFloor", () => ({ color: "#9a7a5a" })));
  const glass = lam("winGlass", () => ({ color: "#7fa6c8" }));
  for (const dx of [-3.4, 3.4]) { b.add(box(x + dx - 0.7, x + dx + 0.7, 1.1, 2.5, z, z + 0.07), glass); b.add(box(x + dx - 0.82, x + dx + 0.82, 0.98, 1.1, z, z + 0.14), trim); }
  for (const dx of [-3.4, 0, 3.4]) b.add(box(x + dx - 0.7, x + dx + 0.7, 3.9, 5.0, z, z + 0.07), glass);
  b.add(box(x - 0.6, x + 0.6, 0.3, 2.4, z, z + 0.07), lam("houseDoor", () => ({ color: "#3f6a4a" })));
};
const fence = (b: Batch, pts: [number, number][]) => {
  const wood = lam("fenceWood", () => ({ color: "#9a7448" }));
  for (let i = 0; i + 1 < pts.length; i++) {
    const [x0, z0] = pts[i], [x1, z1] = pts[i + 1], L = Math.hypot(x1 - x0, z1 - z0), n = Math.max(1, Math.round(L / 2.6));
    for (let k = 0; k <= n; k++) { const t = k / n; b.add(cylY(0.07, 0, 1.25, x0 + (x1 - x0) * t, z0 + (z1 - z0) * t, 6), wood); }
    for (const y of [0.55, 1.05]) b.add(limb(V(x0, y, z0), V(x1, y, z1), 0.075, 0.075, 6), wood);
  }
};
export class Farm {
  root = new THREE.Group();
  axe = new THREE.Group();
  scale = new THREE.Group();
  constructor(parent: THREE.Object3D) {
    parent.add(this.root);
    const b = new Batch();
    // ONE ground plane for the farm (dirt painted into it), four plain grass planes around it, all at y = 0
    b.add(floorQ(-30, 30, -30, 30, 0, 1, true), lam("farmGround", () => ({ map: groundTex() })));
    const grass = lam("farGrass", () => ({ map: grassTile() }));
    for (const [x0, x1, z0, z1] of [[-1200, -30, -1200, 1200], [30, 1200, -1200, 1200], [-30, 30, -1200, -30], [-30, 30, 30, 1200]] as const) b.add(floorQ(x0, x1, z0, z1, 0, 6), grass);
    barn(b, BARN.x, BARN.z);
    house(b, HOUSE.x, HOUSE.z);
    fence(b, [[-24, 12], [-24, -24], [24, -24], [24, 12]]);
    // the chopping stump: bark side, pale end grain on top (one cylinder, two materials, no stacked disc)
    add(new THREE.CylinderGeometry(0.42, 0.48, 0.62, 18).translate(BLOCK.x, 0.31, BLOCK.z), [lam("bark", () => ({ color: "#86643f", emissive: new THREE.Color("#55382a") })), lam("endGrain", () => ({ color: "#d9b484" })), lam("endGrain", () => ({ color: "#d9b484" }))], this.root);
    // hay bales, a trough, the coop
    const hay = lam("hay", () => ({ color: "#e0c060" }));
    for (const [x, z, y] of [[-6, -9, 0], [-4.7, -9.3, 0], [-5.4, -9.1, 0.7]] as const) b.add(box(x - 0.6, x + 0.6, y, y + 0.7, z - 0.4, z + 0.4), hay);
    b.add(box(15, 17.4, 0, 0.6, 2, 2.8), lam("trough", () => ({ color: "#8d949c" })));
    b.add(box(-9.5, -6.5, 0, 1.6, -4, -2), lam("coop", () => ({ color: "#e8d8b0" })));
    b.add(new THREE.ExtrudeGeometry(new THREE.Shape([new THREE.Vector2(-1.7, 1.6), new THREE.Vector2(0, 2.4), new THREE.Vector2(1.7, 1.6)]), { depth: 2.3, bevelEnabled: false }).translate(-8, 0, -4.15), lam("coopRoof", () => ({ color: "#b8362e", side: THREE.DoubleSide })));
    // poplars along the lane, the red mesas to the south
    for (let i = 0; i < 16; i++) poplar(b, -40 + i * 5.5 + hh(i, 1) * 2, -32 - hh(i, 2) * 4, 10 + hh(i, 3) * 4, i);
    for (let i = 0; i < 10; i++) poplar(b, 30 + hh(i, 4) * 10, -10 + i * 4.5, 9 + hh(i, 5) * 4, i + 20);
    for (let i = 0; i < 9; i++) mesa(b, -360 + i * 95 + hh(i, 6) * 30, -330 - hh(i, 7) * 120, 40 + hh(i, 8) * 30, 55 + hh(i, 9) * 45, 30 + hh(i, 10) * 20, i);
    for (let i = 0; i < 6; i++) mesa(b, -250 + i * 110, 380 + hh(i, 11) * 80, 50, 40 + hh(i, 12) * 20, 30, i + 20);
    // the copycat farm: a second barn and fence
    barn(b, COPY.x - 8, COPY.z - 12);
    b.add(new THREE.CylinderGeometry(0.42, 0.48, 0.62, 18).translate(COPY.x + 2.6, 0.31, COPY.z - 0.6), lam("bark", () => ({ color: "#86643f", emissive: new THREE.Color("#55382a") })));
    fence(b, [[COPY.x - 18, COPY.z + 10], [COPY.x - 18, COPY.z - 18], [COPY.x + 18, COPY.z - 18], [COPY.x + 18, COPY.z + 10]]);
    b.build(this.root, true);
    // the axe stuck in the stump (shown per shot)
    add(new THREE.CylinderGeometry(0.03, 0.035, 0.85, 8).rotateZ(-0.5).translate(0.2, 0.95, 0), lam("axeHandle", () => ({ color: "#b07a44" })), this.axe);
    add(box(-0.12, 0.12, 0.58, 0.72, -0.03, 0.03).rotateZ(-0.5), lam("axeHead", () => ({ color: "#8d949c" })), this.axe);
    this.axe.position.set(BLOCK.x, 0, BLOCK.z); this.axe.visible = false; this.root.add(this.axe);
    // a farm platform scale for the weigh-in (only in its shot)
    const sc = new Batch(), steel = lam("scaleSteel", () => ({ color: "#5a6a7a" }));
    sc.add(box(SCALE.x - 0.5, SCALE.x + 0.5, 0, 0.12, SCALE.z - 0.4, SCALE.z + 0.4), steel);
    sc.add(box(SCALE.x - 0.08, SCALE.x + 0.08, 0.12, 1.25, SCALE.z - 0.45, SCALE.z - 0.3), steel);
    sc.build(this.scale, true); this.root.add(this.scale);
    // the farm gate sign
    const gate = new Batch(), wood = lam("gateWood", () => ({ color: "#7a5a3a" }));
    for (const dx of [-1.25, 1.25]) gate.add(cylY(0.08, 0, 2.2, 7 + dx, 6, 8), wood);
    gate.build(this.root, true);
    panel(this.root, signTex("farmSign", 1024, 420, "#f4efe2", "#7a2a24", [["OLSEN FARM", 150], ["FRUITA, COLORADO", 96]], "Georgia"), 2.4, 1.0, 7, 1.7, 6.09, 0, "#7a5a3a");
  }
}

// ---------------- the computer analogy ----------------
export class Desk {
  root = new THREE.Group();
  private screen: THREE.Mesh; private onTex = screenTex(true); private offTex = screenTex(false);
  private leds: THREE.Mesh[] = []; private plug = new THREE.Group(); private fan = new THREE.Group();
  constructor(parent: THREE.Object3D) {
    parent.add(this.root);
    const D = DESK, b = new Batch();
    room(this.root, D.x, D.z, 8, 7, 3.2, lam("deskFloor", () => ({ color: "#8a6a4a" })), lam("deskWall", () => ({ map: wallpaper("deskWall", "#dfe8ee", "#d2dde6") })));
    const wood = lam("deskWood", () => ({ color: "#b5834f" })), beige = lam("crtBeige", () => ({ color: "#e4dcc4" })), dark = lam("crtDark", () => ({ color: "#3a3d44" }));
    b.add(box(D.x - 1.4, D.x + 1.4, 0.72, 0.78, D.z - 2.2, D.z - 1.2), wood);
    for (const [dx, dz] of [[-1.3, -2.1], [1.3, -2.1], [-1.3, -1.3], [1.3, -1.3]]) b.add(box(D.x + dx - 0.04, D.x + dx + 0.04, 0, 0.72, D.z + dz - 0.04, D.z + dz + 0.04), wood);
    // CRT: a deep body, a bezel frame standing 6 cm proud of its face, the screen 3 cm in front of the face
    const mx = D.x - 0.45, mz = D.z - 1.65;
    b.add(box(mx - 0.32, mx + 0.32, 0.78, 1.36, mz - 0.5, mz + 0.05), beige);
    for (const [x0, x1, y0, y1] of [[-0.32, 0.32, 0.78, 0.86], [-0.32, 0.32, 1.28, 1.36], [-0.32, -0.25, 0.86, 1.28], [0.25, 0.32, 0.86, 1.28]] as const) b.add(box(mx + x0, mx + x1, y0, y1, mz + 0.05, mz + 0.11), beige);
    // the tower, the keyboard
    const tx = D.x + 0.42;
    b.add(box(tx - 0.18, tx + 0.18, 0.78, 1.42, mz - 0.4, mz + 0.1), beige);
    b.add(box(mx - 0.3, mx + 0.3, 0.78, 0.82, mz + 0.28, mz + 0.45), beige);
    b.build(this.root, true);
    this.screen = new THREE.Mesh(new THREE.PlaneGeometry(0.5, 0.42), new THREE.MeshBasicMaterial({ map: this.onTex }));
    this.screen.position.set(mx, 1.07, mz + 0.08); this.root.add(this.screen);
    for (let k = 0; k < 2; k++) { const l = new THREE.Mesh(box(-0.045, 0.045, -0.022, 0.022, 0, 0.04), hdr(0.4, 3.0, 0.5)); l.position.set(tx - 0.08 + k * 0.1, 1.3, mz + 0.1); l.layers.set(NOINK); this.leds.push(l); this.root.add(l); }
    // the fan behind a grille on the tower front
    add(new THREE.TorusGeometry(0.09, 0.015, 6, 20), dark, this.fan);
    for (let k = 0; k < 4; k++) { const bl = add(box(-0.075, 0.075, -0.018, 0.018, -0.01, 0.01), dark, this.fan); bl.rotation.z = (k / 4) * Math.PI; }
    this.fan.position.set(tx, 1.0, mz + 0.16); this.root.add(this.fan);
    // the cable: from the tower side to the monitor; the plug end can be pulled out and held up
    const cable = new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3([V(tx - 0.18, 1.0, mz - 0.1), V(D.x + 0.2, 0.84, mz - 0.1), V(mx + 0.32, 0.95, mz - 0.2)]), 30, 0.015, 6), dark);
    this.root.add(cable);
    add(box(-0.05, 0.05, -0.03, 0.03, -0.03, 0.03), dark, this.plug); this.root.add(this.plug);
    this.plugHome.set(mx + 0.34, 0.95, mz - 0.2);
  }
  plugHome = new THREE.Vector3();
  update(f: number, unplugAt: number, darkAt: number) {
    const k = Math.min(1, Math.max(0, (f - unplugAt) / 8));
    this.plug.position.copy(this.plugHome).add(V(0.25 * k, 0.25 * k, 0.15 * k));
    (this.screen.material as THREE.MeshBasicMaterial).map = f >= darkAt ? this.offTex : this.onTex;
    this.leds.forEach((l, i) => { l.visible = (Math.floor(f / (5 + i * 3)) % 2) === 0; });
    this.fan.rotation.z = -f * 0.6;
  }
}

// ---------------- the sideshow ----------------
export class Show {
  root = new THREE.Group();
  private bulbs: THREE.Mesh[] = [];
  syringe = new THREE.Group();
  constructor(parent: THREE.Object3D) {
    parent.add(this.root);
    const S = SHOW, b = new Batch();
    b.add(floorQ(S.x - 150, S.x + 150, S.z - 150, S.z + 150, 0, 6), lam("fairDirt", () => ({ color: "#c9a878" })));
    const stripe = lam("tentStripe", () => ({ map: tentTex() }));
    // the big top behind: a striped drum and a cone roof
    b.add(new THREE.CylinderGeometry(9, 9, 4.5, 48, 1, true).translate(S.x, 2.25, S.z - 19), lam("tentStripeD", () => ({ map: tentTex(), side: THREE.DoubleSide })));
    b.add(new THREE.ConeGeometry(10, 5, 48).translate(S.x, 7, S.z - 19), stripe);
    b.add(cylY(0.08, 9.5, 11, S.x, S.z - 19, 8), lam("flagPoleS", () => ({ color: "#f4efe2" })));
    // the stage pedestal for Mike, the ticket booth
    b.add(cylY(0.55, 0, 1.0, S.x, S.z - 2, 24), lam("pedestal", () => ({ color: "#d9382e" })));
    b.add(cylY(0.62, 1.0, 1.08, S.x, S.z - 2, 24), lam("pedestalTop", () => ({ color: "#f6d23a" })));
    b.add(box(S.x + 3.2, S.x + 5.0, 0, 2.4, S.z - 1.2, S.z + 0.2), lam("booth", () => ({ color: "#f6d23a" })));
    b.add(box(S.x + 3.1, S.x + 5.1, 2.4, 2.6, S.z - 1.3, S.z + 0.3), lam("boothTop", () => ({ color: "#d9382e" })));
    // banner posts
    const post = lam("bannerPostS", () => ({ color: "#5a3a26" }));
    for (const dx of [-3.6, 3.6]) b.add(cylY(0.09, 0, 5.4, S.x + dx, S.z - 4.5, 10), post);
    b.build(this.root, true);
    panel(this.root, showBanner(), 6.6, 2.06, S.x, 4.3, S.z - 4.62);
    panel(this.root, signTex("ticket25", 512, 256, "#ffffff", "#d9382e", [["ADMISSION", 60], ["25¢", 130]]), 1.5, 0.75, S.x + 4.1, 1.7, S.z + 0.2, 0);
    // string lights from the posts out to the booth and across
    for (const [a, c] of [[[-3.6, 5.3, -4.5], [-8, 3, 2]], [[3.6, 5.3, -4.5], [8, 3, 2]]] as const) for (let k = 0; k < 12; k++) {
      const t = (k + 0.5) / 12, x = a[0] + (c[0] - a[0]) * t, z = a[2] + (c[2] - a[2]) * t, y = a[1] + (c[1] - a[1]) * t - 0.4 * Math.sin(t * Math.PI);
      const m = new THREE.Mesh(new THREE.SphereGeometry(0.07, 8, 6), hdr(2.4, 2.0, 1.2)); m.position.set(S.x + x, y, S.z + z); m.layers.set(NOINK); this.bulbs.push(m); this.root.add(m);
    }
    // the forgotten syringe, lying on the pedestal top
    add(new THREE.CylinderGeometry(0.03, 0.03, 0.3, 10).rotateZ(Math.PI / 2), lam("syrGlass", () => ({ color: "#dff0f6" })), this.syringe);
    add(new THREE.CylinderGeometry(0.008, 0.008, 0.12, 6).rotateZ(Math.PI / 2).translate(0.21, 0, 0), lam("needle", () => ({ color: "#c9ccd2" })), this.syringe);
    add(new THREE.CylinderGeometry(0.012, 0.012, 0.14, 6).rotateZ(Math.PI / 2).translate(-0.2, 0, 0), lam("plunger2", () => ({ color: "#3a3d44" })), this.syringe);
    add(box(-0.29, -0.27, -0.05, 0.05, -0.05, 0.05), lam("plunger2", () => ({ color: "#3a3d44" })), this.syringe);
    this.syringe.position.set(S.x, 1.14, S.z - 1.8); this.syringe.rotation.y = 0.3; this.syringe.scale.setScalar(3.2); this.syringe.visible = false; this.root.add(this.syringe);
  }
  update(f: number, night: boolean) { this.bulbs.forEach((m, i) => { (m.material as THREE.MeshBasicMaterial).color.setRGB(night ? 3 : 2.4, night ? 2.4 : 2.0, 1.2).multiplyScalar(((Math.floor(f / 6) + i) % 3) === 0 ? 0.5 : 1); }); }
}

// ---------------- the motel room at night ----------------
export class Motel {
  root = new THREE.Group();
  constructor(parent: THREE.Object3D) {
    parent.add(this.root);
    const M = MOTEL, b = new Batch();
    room(this.root, M.x, M.z, 8, 7, 3.0, lam("motelCarpet", () => ({ color: "#6a5a7a" })), lam("motelWall", () => ({ map: wallpaper("motelPaper", "#7a8a6a", "#6f7f60") })), lam("motelCeil", () => ({ color: "#d9d2c0" })));
    b.add(box(M.x - 2.6, M.x - 0.4, 0, 0.55, M.z - 3.4, M.z - 0.9), lam("bedBase", () => ({ color: "#7a4a3a" })));
    b.add(box(M.x - 2.55, M.x - 0.45, 0.55, 0.7, M.z - 3.35, M.z - 0.95), lam("blanket", () => ({ color: "#c25a5a" })));
    b.add(box(M.x - 2.3, M.x - 0.7, 0.7, 0.9, M.z - 3.3, M.z - 2.8), lam("pillow", () => ({ color: "#f4efe2" })));
    b.add(box(M.x - 0.2, M.x + 0.4, 0, 0.6, M.z - 3.4, M.z - 2.9), lam("nightstand", () => ({ color: "#5a3a26" })));
    b.add(cylY(0.05, 0.6, 1.0, M.x + 0.1, M.z - 3.15, 8), lam("lampStem", () => ({ color: "#d9b45a" })));
    // a cardboard box on a chair for Mike
    b.add(box(M.x + 0.7, M.x + 1.4, 0, 0.5, M.z - 2.6, M.z - 1.9), lam("chair", () => ({ color: "#5a3a26" })));
    b.add(box(M.x + 0.75, M.x + 1.35, 0.5, 0.8, M.z - 2.55, M.z - 1.95), lam("cardboard", () => ({ color: "#c9a06a" })));
    b.build(this.root, true);
    const shade = new THREE.Mesh(new THREE.CylinderGeometry(0.12, 0.2, 0.25, 16, 1, true).translate(M.x + 0.1, 1.08, M.z - 3.15), new THREE.MeshBasicMaterial({ color: new THREE.Color(2.6, 2.2, 1.4), side: THREE.DoubleSide }));
    shade.layers.set(NOINK); this.root.add(shade);
    panel(this.root, nightWindow(), 1.3, 1.6, M.x + 2.4, 1.7, M.z - 3.5, 0, "#f4efe2");
  }
}

// ---------------- the festival ----------------
export class Fest {
  root = new THREE.Group();
  constructor(parent: THREE.Object3D) {
    parent.add(this.root);
    const F = FEST, b = new Batch();
    b.add(floorQ(F.x - 200, F.x + 200, F.z - 200, F.z + 200, 0, 6), lam("asphaltF", () => ({ color: "#7a7a82" })));
    const walk = lam("sidewalk", () => ({ color: "#d9d2c0" }));
    for (const s of [-1, 1]) b.add(box(F.x - 60, F.x + 60, 0, 0.15, F.z + s * 7 - 2, F.z + s * 7 + 2), walk);
    // storefronts both sides of the street (painted fronts on the box faces themselves: nothing stacked)
    const shops: [string, string, string][] = [["#e8c98a", "HARDWARE", "#3f7fd2"], ["#c86a5a", "DINER", "#d9382e"], ["#9ac4b0", "BAKERY", "#f2c230"], ["#e8e2d0", "GENERAL STORE", "#5d9a3a"], ["#d9a0b0", "BARBER", "#3f6fb5"], ["#c9b48a", "FEED & SEED", "#d9382e"]];
    for (const s of [-1, 1]) shops.forEach(([wall, name, aw], i) => {
      const x = F.x - 27 + i * 9 + (s > 0 ? 4 : 0), z = F.z + s * 13, front = lam(`shop${s}${i}`, () => ({ map: shopTex(`shop${s}${i}`, wall, name, aw) })), side = lam(`shopSide${i}`, () => ({ color: wall }));
      const m = new THREE.Mesh(new THREE.BoxGeometry(8.6, 6.5, 4), s < 0 ? [side, side, side, side, front, side] : [side, side, side, side, side, front]);
      m.position.set(x, 3.25, z + s * 2); m.castShadow = m.receiveShadow = true; this.root.add(m);
    });
    // banner poles and the banner across the street; the statue's plinth
    const pole = lam("festPole", () => ({ color: "#d6dade" }));
    for (const s of [-1, 1]) b.add(cylY(0.1, 0, 7, F.x + 6, F.z + s * 5.6, 10), pole);
    b.build(this.root, true);
    panel(this.root, festBanner(), 11, 2.75, F.x + 6, 5.6, F.z, Math.PI / 2);
    const cols = ["#d9382e", "#f6d23a", "#3f7fd2", "#ffffff", "#4fb06a"];
    for (const x of [F.x - 20, F.x - 12, F.x - 4]) for (let k = 0; k < 16; k++) {
      const t = (k + 0.5) / 16, z = F.z - 11 + 22 * t, y = 6.0 - 1.0 * Math.sin(t * Math.PI);
      const tri = new THREE.Mesh(new THREE.BufferGeometry().setFromPoints([V(0, 0, -0.3), V(0, 0, 0.3), V(0, -0.6, 0)]), new THREE.MeshBasicMaterial({ color: cols[k % 5], side: THREE.DoubleSide }));
      tri.position.set(x, y, z); this.root.add(tri);
    }
    const bb = new Batch();
    for (let i = 0; i < 10; i++) { const x = F.x - 20 + i * 4.5, z = F.z + (i % 2 ? 5.2 : -5.2); bb.add(cylY(0.015, 0, 2.4, x, z, 4), lam("string", () => ({ color: "#f4efe2" }))); bb.add(new THREE.SphereGeometry(0.32, 14, 10).scale(1, 1.2, 1).translate(x, 2.75, z), lam("balloon" + (i % 5), () => ({ color: cols[i % 5] }))); }
    for (let i = 0; i < 4; i++) { const x = F.x - 16 + i * 8, z = F.z + (i % 2 ? 9 : -9); bb.add(box(x - 1.2, x + 1.2, 0, 1.0, z - 0.6, z + 0.6), lam("stall", () => ({ color: "#f4efe2" }))); bb.add(box(x - 1.4, x + 1.4, 2.2, 2.35, z - 0.8, z + 0.8), lam("stallTop" + (i % 2), () => ({ color: i % 2 ? "#d9382e" : "#3f7fd2" }))); for (const dx of [-1.25, 1.25]) bb.add(cylY(0.04, 1.0, 2.2, x + dx, z, 6), lam("stallPole", () => ({ color: "#d6dade" }))); }
    bb.add(box(F.x - 1.8, F.x + 1.8, 0, 1.4, F.z - 4.8, F.z - 1.2), lam("plinth", () => ({ color: "#b8b0a0" })));
    bb.build(this.root, true);
  }
}
export { signTex, panel };
