// The molasses-flood film's sets (two-tone lam() geometry, outlined by the world ink).
// Flicker rules (learned on the whale and Mike films): no two surfaces closer than 5 cm unless exactly flush, every
// painted sign or panel on the DEFAULT layer (it hides what is behind it), one ground plane per set, roofs DoubleSide,
// fine patterns low-contrast.
//  Street: Commercial Street, North End, 1919. Brick rowhouses on the west side, the elevated railway over the east
//    lane, streetcar rails, the molasses tank in its yard, the wharf edge and the harbor. The wave and the flood
//    sheet are posed per frame.
//  Office: the company treasurer's office (desk, ledger, adding machine, window).
//  Court: a wood-panelled courtroom (judge's bench, witness rail).
//  Subway: a tiled station with a wooden bench and a payphone booth.
import * as THREE from "three";
import { lam, Batch, V, quad } from "./build";
import { ctex, rep } from "./paint";
import { STREET, TANK, EL, WHARF_X, OFFICE, COURT, SUBWAY } from "./places";

const TAU = Math.PI * 2;
export const box = (x0: number, x1: number, y0: number, y1: number, z0: number, z1: number) =>
  new THREE.BoxGeometry(x1 - x0, y1 - y0, z1 - z0).translate((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2);
export const cylY = (r: number, y0: number, y1: number, x: number, z: number, seg = 24, r2 = r) =>
  new THREE.CylinderGeometry(r2, r, y1 - y0, seg).translate(x, (y0 + y1) / 2, z);
const add = (g: THREE.BufferGeometry, m: THREE.Material | THREE.Material[], parent: THREE.Object3D, cast = true) => {
  const mesh = new THREE.Mesh(g, m); mesh.castShadow = cast; mesh.receiveShadow = true; parent.add(mesh); return mesh;
};
const floorQ = (x0: number, x1: number, z0: number, z1: number, y: number, s: number, uv01 = false) => {
  const g = new THREE.BufferGeometry(), P = [x0, y, z1, x1, y, z1, x1, y, z0, x0, y, z1, x1, y, z0, x0, y, z0];
  g.setAttribute("position", new THREE.Float32BufferAttribute(P, 3));
  const uv: number[] = []; for (let i = 0; i < 6; i++) uv.push(uv01 ? (P[i * 3] - x0) / (x1 - x0) : P[i * 3] / s, uv01 ? 1 - (P[i * 3 + 2] - z0) / (z1 - z0) : P[i * 3 + 2] / s);
  g.setAttribute("uv", new THREE.Float32BufferAttribute(uv, 2)); g.computeVertexNormals(); return g;
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
export const panel = (parent: THREE.Object3D, tex: THREE.Texture, w: number, h: number, x: number, y: number, z: number, yaw = 0, back?: string) => {
  const g = new THREE.Group(); g.position.set(x, y, z); g.rotation.y = yaw; parent.add(g);
  const m = new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshBasicMaterial({ map: tex })); m.position.z = 0.07; g.add(m);
  if (back) add(box(-w / 2 - 0.06, w / 2 + 0.06, -h / 2 - 0.06, h / 2 + 0.06, -0.06, 0.0), lam("board" + back, () => ({ color: back })), g);
  return g;
};
export const signTex = (key: string, w: number, h: number, bg: string, fg: string, lines: [string, number][], font = "Arial Black, Arial") => ctex(key, w, h, (g) => {
  g.fillStyle = bg; g.fillRect(0, 0, w, h);
  g.strokeStyle = fg; g.lineWidth = Math.max(8, h * 0.04); g.strokeRect(g.lineWidth, g.lineWidth, w - 2 * g.lineWidth, h - 2 * g.lineWidth);
  g.fillStyle = fg; g.textAlign = "center"; g.textBaseline = "middle";
  const tot = lines.reduce((s, l) => s + l[1] * 1.15, 0); let y = h / 2 - tot / 2;
  for (const [t, px] of lines) { g.font = `900 ${px}px ${font}`; y += px * 0.575; g.fillText(t, w / 2, y); y += px * 0.575; }
});

// ---------------- painted textures (low contrast: fine high-contrast patterns shimmer) ----------------
const cobbleTile = () => ctex("bosCobble", 1024, 1024, (g, r) => {
  g.fillStyle = "#a59a8c"; g.fillRect(0, 0, 1024, 1024);
  for (let y = 0; y < 1024; y += 64) for (let x = (y / 64) % 2 ? 32 : 0; x < 1024 + 64; x += 64) {
    const c = 150 + Math.floor(r() * 26); g.fillStyle = `rgb(${c + 14},${c + 6},${c - 6})`;
    g.beginPath(); g.ellipse(x, y + 32, 28, 27, 0, 0, TAU); g.fill();
  }
});
const brickTile = (key: string, base: string) => ctex(key, 512, 512, (g, r) => {
  g.fillStyle = base; g.fillRect(0, 0, 512, 512);
  for (let y = 0; y < 512; y += 32) for (let x = (y / 32) % 2 ? 0 : 32; x < 512; x += 64) {
    g.fillStyle = `rgba(${r() < 0.5 ? "120,40,30" : "200,110,80"},${(0.12 + r() * 0.1).toFixed(2)})`; g.fillRect(x + 2, y + 2, 60, 28);
  }
  g.fillStyle = "rgba(230,210,190,0.35)"; for (let y = 0; y < 512; y += 32) g.fillRect(0, y, 512, 3);
});
/** a rowhouse front: brick, window rows with white sills and green shutters, a shop front at street level */
const rowFront = (key: string, w: number, h: number, base: string, shop: string) => ctex(key, 1024, Math.round(1024 * h / w), (g, r) => {
  const W = 1024, H = Math.round(1024 * h / w), px = W / w;
  g.fillStyle = base; g.fillRect(0, 0, W, H);
  for (let y = 0; y < H; y += 0.25 * px) for (let x = (Math.round(y / (0.25 * px)) % 2) ? 0 : 0.25 * px; x < W; x += 0.5 * px) {
    g.fillStyle = `rgba(${r() < 0.5 ? "110,35,28" : "205,115,85"},${(0.1 + r() * 0.08).toFixed(2)})`; g.fillRect(x, y, 0.48 * px, 0.23 * px);
  }
  const floors = Math.floor((h - 1) / 3), n = Math.max(2, Math.floor(w / 2.2));
  for (let fl = 1; fl <= floors; fl++) for (let i = 0; i < n; i++) {
    const cx = ((i + 0.5) / n) * W, yb = H - (fl * 3 + 0.4) * px, ww = 0.9 * px, wh = 1.6 * px;
    g.fillStyle = "#2c3a52"; g.fillRect(cx - ww / 2, yb - wh, ww, wh);
    g.fillStyle = "rgba(170,200,230,0.55)"; g.fillRect(cx - ww / 2 + 6, yb - wh + 6, ww / 2 - 9, wh / 2 - 9);
    g.strokeStyle = "#f2ead8"; g.lineWidth = 7; g.strokeRect(cx - ww / 2, yb - wh, ww, wh);
    g.fillStyle = "#f2ead8"; g.fillRect(cx - ww / 2 - 8, yb, ww + 16, 12); g.fillRect(cx - ww / 2 - 8, yb - wh - 14, ww + 16, 14);
  }
  // shop front: an awning-coloured band, a big window and a door
  g.fillStyle = shop; g.fillRect(0, H - 3.0 * px, W, 0.55 * px);
  g.fillStyle = "#2c3a52"; g.fillRect(0.08 * W, H - 2.3 * px, 0.55 * W, 1.7 * px);
  g.fillStyle = "rgba(170,200,230,0.5)"; g.fillRect(0.08 * W + 10, H - 2.3 * px + 10, 0.25 * W, 0.7 * px);
  g.fillStyle = "#5a3a2a"; g.fillRect(0.72 * W, H - 2.4 * px, 0.16 * W, 2.4 * px);
  g.strokeStyle = "#f2ead8"; g.lineWidth = 8; g.strokeRect(0.08 * W, H - 2.3 * px, 0.55 * W, 1.7 * px);
});
/** the tank wall: riveted steel plates (seams + rivet dots, soft); variant grey / leaky grey / brown */
export type TankLook = "grey" | "leak" | "brown";
const tankTex = (look: TankLook) => ctex("tank_" + look, 1024, 1024, (g, r) => {
  const base = look === "brown" ? "#6e4426" : "#9aa3ab";
  g.fillStyle = base; g.fillRect(0, 0, 1024, 1024);
  for (let i = 0; i < 4; i++) { g.fillStyle = look === "brown" ? `rgba(90,52,28,${0.25 + 0.1 * (i % 2)})` : `rgba(${i % 2 ? "150,158,166" : "170,178,186"},0.5)`; g.fillRect(0, i * 256, 1024, 256); }
  const seam = look === "brown" ? "rgba(40,22,12,0.5)" : "rgba(70,78,88,0.45)", dot = look === "brown" ? "rgba(40,22,12,0.55)" : "rgba(60,66,76,0.55)";
  g.fillStyle = seam; for (let y = 0; y <= 1024; y += 256) g.fillRect(0, y - 3, 1024, 6);
  for (let x = 0; x < 1024; x += 256) g.fillRect(x - 3, 0, 6, 1024);
  g.fillStyle = dot; for (let y = 0; y <= 1024; y += 256) for (let x = 8; x < 1024; x += 24) { g.beginPath(); g.arc(x, y - 12, 4, 0, TAU); g.fill(); g.beginPath(); g.arc(x, y + 12, 4, 0, TAU); g.fill(); }
  if (look !== "grey") for (let i = 0; i < 9; i++) {
    const x = 60 + i * 110 + r() * 40, y0 = (Math.floor(r() * 4)) * 256 + 10, len = 200 + r() * 500;
    const gr = g.createLinearGradient(0, y0, 0, y0 + len);
    gr.addColorStop(0, look === "brown" ? "rgba(70,40,20,0.55)" : "rgba(120,70,30,0.95)"); gr.addColorStop(1, "rgba(120,70,30,0)");
    g.fillStyle = gr; g.beginPath(); g.moveTo(x - 6, y0); g.lineTo(x + 6, y0); g.lineTo(x + 10 + r() * 6, y0 + len); g.lineTo(x - 10, y0 + len); g.closePath(); g.fill();
  }
});
/** the molasses surface: dark amber with soft lighter swirls and a glossy band near the top of the uv */
export const syrupTex = () => ctex("syrup", 512, 512, (g, r) => {
  // canvas y 0 = the back of the wave (v 1), y ~220 = the crest, y 512 = the front foot (v 0)
  const gr = g.createLinearGradient(0, 0, 0, 512);
  gr.addColorStop(0, "#5a2a0e"); gr.addColorStop(0.28, "#7a3a14"); gr.addColorStop(0.36, "#b8722e"); gr.addColorStop(0.4, "#f0c07a");
  gr.addColorStop(0.43, "#a8642a"); gr.addColorStop(0.6, "#743812"); gr.addColorStop(1, "#4e240c");
  g.fillStyle = gr; g.fillRect(0, 0, 512, 512);
  for (let i = 0; i < 26; i++) { const x = r() * 512, y0 = 250 + r() * 60, len = 80 + r() * 170; const gg = g.createLinearGradient(0, y0, 0, y0 + len);
    gg.addColorStop(0, "rgba(90,40,14,0)"); gg.addColorStop(0.3, "rgba(90,40,14,0.28)"); gg.addColorStop(1, "rgba(90,40,14,0)"); g.fillStyle = gg; g.fillRect(x, y0, 8 + r() * 10, len); }
  for (let i = 0; i < 14; i++) { const x = r() * 512; g.fillStyle = "rgba(255,226,170,0.35)"; g.fillRect(x, 205 + r() * 20, 30 + r() * 50, 5); }
});
const syrupFlatTex = () => ctex("syrupFlat", 512, 512, (g, r) => {
  g.fillStyle = "#7a3e16"; g.fillRect(0, 0, 512, 512);
  for (let i = 0; i < 22; i++) { g.fillStyle = `rgba(${r() < 0.5 ? "200,130,64" : "90,44,14"},${(0.14 + r() * 0.1).toFixed(2)})`;
    g.beginPath(); g.ellipse(r() * 512, r() * 512, 40 + r() * 70, 10 + r() * 14, 0, 0, TAU); g.fill(); }
});
const harborTex = (brown: boolean) => ctex(brown ? "harborBrown" : "harborBlue", 512, 512, (g, r) => {
  g.fillStyle = brown ? "#6a3c1a" : "#3f7fae"; g.fillRect(0, 0, 512, 512);
  for (let i = 0; i < (brown ? 110 : 60); i++) { g.strokeStyle = brown ? "rgba(200,140,80,0.45)" : "rgba(170,215,240,0.35)"; g.lineWidth = 3 + r() * 3;
    const x = r() * 512, y = r() * 512; g.beginPath(); g.moveTo(x, y); g.quadraticCurveTo(x + 15, y - 6, x + 30, y); g.stroke(); }
});
const wallpaper = (key: string, a: string, b2: string) => ctex(key, 512, 512, (g) => {
  g.fillStyle = a; g.fillRect(0, 0, 512, 512); g.fillStyle = b2; for (let x = 0; x < 512; x += 64) g.fillRect(x, 0, 26, 512);
});
const tileTex = () => ctex("subwayTile", 512, 512, (g) => {
  g.fillStyle = "#efe9da"; g.fillRect(0, 0, 512, 512);
  g.fillStyle = "rgba(160,150,130,0.35)"; for (let y = 0; y < 512; y += 32) g.fillRect(0, y, 512, 3);
  for (let y = 0; y < 512; y += 32) for (let x = (y / 32) % 2 ? 0 : 32; x < 512; x += 64) g.fillRect(x, y, 3, 32);
  g.fillStyle = "#2f6a5a"; g.fillRect(0, 300, 512, 40);
});
const panelWood = () => ctex("courtWood", 512, 512, (g) => {
  g.fillStyle = "#8a5a36"; g.fillRect(0, 0, 512, 512);
  g.fillStyle = "rgba(60,35,20,0.35)"; for (let x = 0; x < 512; x += 128) g.fillRect(x, 0, 6, 512);
  g.strokeStyle = "rgba(60,35,20,0.35)"; g.lineWidth = 6; for (let x = 0; x < 512; x += 128) g.strokeRect(x + 20, 40, 88, 200);
});
const windowTex = () => ctex("officeWindow", 512, 640, (g) => {
  const gr = g.createLinearGradient(0, 0, 0, 640); gr.addColorStop(0, "#7fb0e0"); gr.addColorStop(1, "#cfe2f2");
  g.fillStyle = gr; g.fillRect(0, 0, 512, 640);
  g.fillStyle = "#6e4426"; g.fillRect(150, 300, 300, 340); g.fillStyle = "#5a3418"; g.beginPath(); g.ellipse(300, 300, 150, 30, 0, 0, TAU); g.fill();
  g.fillStyle = "#b8643f"; g.fillRect(0, 420, 120, 220);
  g.strokeStyle = "#f4efe2"; g.lineWidth = 22; g.strokeRect(11, 11, 490, 618); g.beginPath(); g.moveTo(256, 0); g.lineTo(256, 640); g.moveTo(0, 320); g.lineTo(512, 320); g.stroke();
});

// ---------------- the street ----------------
/** a run of brick rowhouses along the west side (fronts facing +x at x = STREET.x0), flat roofs with a cornice */
const rowhouses = (b: Batch, z0: number, z1: number, seed: number) => {
  let z = z0, i = seed;
  const bases = ["#b5573f", "#a24a36", "#c06a4a", "#9a4434"], shops = ["#2f6a43", "#8c3b4a", "#3f6fb5", "#d9a441"];
  while (z < z1) {
    const w = 7 + hh(i, 1) * 3, h = 10 + Math.floor(hh(i, 2) * 3) * 3, x = STREET.x0;
    const k = `row${i % 6}_${Math.round(w)}_${h}`;
    const front = lam(k, () => ({ map: rowFront(k, Math.round(w), h, bases[i % 4], shops[i % 4]) }));
    b.add(quad(V(x, 0, z + w), V(x, 0, z), V(x, h, z), V(x, h, z + w)), front);
    b.add(box(x - 12, x, h - 0.01, h, z, z + w), lam("roofTar", () => ({ color: "#5a5058" })));
    b.add(box(x - 0.01, x + 0.35, h - 0.6, h - 0.2, z, z + w), lam("cornice", () => ({ color: "#efe3c8" })));
    b.add(quad(V(x - 12, 0, z), V(x - 12, 0, z + w), V(x - 12, h, z + w), V(x - 12, h, z)), lam("brickBack", () => ({ map: rep(brickTile("brickB", "#a8503a"), 3, 3) })));
    z += w; i++;
  }
};

export class Street {
  root = new THREE.Group();
  /** the tank: 32 wall plates hinged at their feet (they fall open when it bursts), a shallow cone roof */
  private plates: THREE.Mesh[] = [];
  private roof: THREE.Mesh;
  private tankMats: Record<TankLook, THREE.Material>;
  wave = new THREE.Group();
  private debris: THREE.Group[] = [];
  private waveMesh: THREE.Mesh;
  flood: THREE.Mesh;
  private harbor: THREE.Mesh; private harborBlue: THREE.Material; private harborBrown: THREE.Material;
  streetcar = new THREE.Group();
  truck = new THREE.Group();
  ladder = new THREE.Group();
  board = new THREE.Group();
  geyser: THREE.Mesh;
  curl: THREE.Mesh;
  boat = new THREE.Group();
  constructor(parent: THREE.Object3D) {
    parent.add(this.root);
    const b = new Batch();
    // ONE ground plane for the land (street + tank yard), the harbor water 1.2 m below the wharf edge
    const cob = lam("bosCobble", () => ({ map: cobbleTile() }));
    const g0 = floorQ(-400, WHARF_X, -400, 400, 0, 4); b.add(g0, cob);
    b.add(floorQ(WHARF_X, 48, -400, -8, 0, 4), cob);
    // the wharf edge: a timber face down to the water
    const timber = lam("wharfTimber", () => ({ color: "#6a5040" }));
    b.add(quad(V(WHARF_X, -1.2, 400), V(WHARF_X, -1.2, -8), V(WHARF_X, 0, -8), V(WHARF_X, 0, 400)), timber);
    b.add(quad(V(WHARF_X, -1.2, -8), V(48, -1.2, -8), V(48, 0, -8), V(WHARF_X, 0, -8)), timber);
    b.add(quad(V(48, -1.2, -8), V(48, -1.2, -400), V(48, 0, -400), V(48, 0, -8)), timber);
    for (let z = -6; z < 120; z += 4) b.add(cylY(0.22, -1.2, 0.5, WHARF_X + 0.3, z, 8), timber);
    this.harborBlue = lam("harborBlue", () => ({ map: rep(harborTex(false), 20, 20) }));
    this.harborBrown = lam("harborBrown", () => ({ map: rep(harborTex(true), 20, 20) }));
    this.harbor = add(floorQ(WHARF_X - 0.5, 900, -900, 900, -1.2, 1, true), this.harborBlue, this.root, false);
    // rowhouses on the west side, a block closing the far end, a church spire beyond
    rowhouses(b, -90, 140, 0);
    for (let k = 0; k < 4; k++) { const x0 = -8 + k * 9, h = 12 + (k % 2) * 3, key = `rowEnd${k}`;
      const front = lam(key, () => ({ map: rowFront(key, 9, h, ["#b5573f", "#a24a36"][k % 2], ["#2f6a43", "#8c3b4a"][k % 2]) }));
      b.add(quad(V(x0, 0, -95), V(x0 + 9, 0, -95), V(x0 + 9, h, -95), V(x0, h, -95)), front);
      b.add(box(x0, x0 + 9, h - 0.01, h, -107, -95), lam("roofTar", () => ({ color: "#5a5058" }))); }
    const spire = lam("spire", () => ({ color: "#efe3c8" }));
    b.add(box(-38, -32, 0, 22, -150, -144), lam("churchBrick", () => ({ color: "#a8503a" })));
    b.add(box(-37, -33, 22, 30, -149, -145), spire);
    b.add(new THREE.ConeGeometry(2.4, 12, 8).translate(-35, 36, -147), lam("spireRoof", () => ({ color: "#4f6a5a" })));
    // the elevated railway: two rows of posts, cross beams, a deep girder deck over the east lane
    const steel = lam("elSteel", () => ({ color: "#4a5560" })), steelD = lam("elSteelD", () => ({ color: "#3a434c" }));
    for (let z = -90; z <= 140; z += 9) {
      for (const x of [EL.x, EL.x + 5.4]) b.add(box(x - 0.22, x + 0.22, 0, EL.y, z - 0.22, z + 0.22), steel);
      b.add(box(EL.x - 0.4, EL.x + 5.8, EL.y - 0.5, EL.y, z - 0.25, z + 0.25), steelD);
    }
    for (const x of [EL.x + 0.2, EL.x + 5.2]) b.add(box(x - 0.25, x + 0.25, EL.y, EL.y + 1.0, -90, 140), steel);
    b.add(box(EL.x, EL.x + 5.4, EL.y + 0.3, EL.y + 0.4, -90, 140), lam("elDeck", () => ({ color: "#5a4a40" })));
    // streetcar rails (raised 4 cm, wide enough not to alias), a lamp post or two
    const rail = lam("rail", () => ({ color: "#5a5a60" }));
    for (const x of [-2.75, -1.25]) b.add(box(x - 0.06, x + 0.06, 0, 0.04, -90, 140), rail);
    for (let z = -60; z < 140; z += 18) { b.add(cylY(0.09, 0, 4.2, -6.6, z, 8), steelD); b.add(box(-6.9, -6.3, 4.2, 4.6, z - 0.3, z + 0.3), lam("lampHead", () => ({ color: "#e8d9a0" }))); }
    // snow banks along the curb (it was a cold January), low and soft
    const snow = lam("snow", () => ({ color: "#f2f4f8" }));
    for (let z = -50; z < 120; z += 7) b.add(new THREE.SphereGeometry(1, 10, 6).scale(1.4 + hh(z, 1), 0.35, 2.6).translate(-7.0, 0, z + hh(z, 2) * 3), snow);
    // the tank yard: a low fence along the street side, a pump house
    b.add(box(15.5, 19, 0, 3.2, -15, -10), lam("pumpHouse", () => ({ map: rep(brickTile("brickP", "#b5573f"), 1, 1) })));
    b.add(box(15.2, 19.3, 3.2, 3.4, -15.3, -9.7), lam("roofTar", () => ({ color: "#5a5058" })));
    b.build(this.root, true);

    // the tank (posed per frame): plates hinge outward at their feet
    const plateM = (look: TankLook) => new THREE.MeshLambertMaterial({ map: rep(tankTex(look), 1, 1), emissive: new THREE.Color(look === "brown" ? "#2a1408" : "#30343a") });
    this.tankMats = { grey: plateM("grey"), leak: plateM("leak"), brown: plateM("brown") };
    for (const m of Object.values(this.tankMats)) m.side = THREE.DoubleSide;
    const N = 32, dth = TAU / N;
    for (let i = 0; i < N; i++) {
      const g = new THREE.CylinderGeometry(TANK.r, TANK.r, TANK.h, 3, 1, true, i * dth, dth);
      g.translate(0, TANK.h / 2, 0);
      // pivot = the plate's foot on the circle: move the plate so its foot centre is the group origin
      const a = i * dth + dth / 2, fx = Math.sin(a) * TANK.r, fz = Math.cos(a) * TANK.r;
      g.translate(-fx, 0, -fz);
      const piv = new THREE.Group(); piv.position.set(TANK.x + fx, 0, TANK.z + fz); piv.userData.a = a;
      const m = new THREE.Mesh(g, this.tankMats.grey); m.castShadow = true; m.receiveShadow = true;
      piv.add(m); this.root.add(piv); this.plates.push(m);
    }
    this.roof = add(new THREE.ConeGeometry(TANK.r + 0.3, 2.2, 48, 1, false).translate(TANK.x, TANK.h + 1.1, TANK.z), lam("tankRoof", () => ({ color: "#7c858e", side: THREE.DoubleSide })), this.root);

    // the wave: a ribbon of the cross-section swept across the street; local +z = direction of travel, front foot at z 0
    const prof: [number, number][] = [[-16, 0.9], [-11, 1.4], [-7, 2.6], [-4, 4.4], [-2, 6.0], [-0.4, 7.1], [1.0, 7.5], [2.4, 7.1], [3.3, 6.2], [3.4, 5.2], [2.9, 4.6], [2.2, 4.9], [1.6, 4.2], [1.1, 2.6], [0.8, 1.1], [0.5, 0]];
    const W = STREET.x1 - STREET.x0 + 0.4, nx = 24, pos: number[] = [], uv: number[] = [], idx: number[] = [];
    for (let i = 0; i < prof.length; i++) for (let j = 0; j <= nx; j++) {
      const x = -W / 2 + (W * j) / nx, wob = (0.45 * Math.sin(j * 0.55 + 0.8) + 0.15 * Math.sin(j * 1.7)) * (i > 3 && i < 12 ? 1 : 0.3);
      const hk = i > 2 ? 0.82 + 0.18 * Math.cos(((j / nx) - 0.45) * Math.PI * 1.3) : 1;
      const lump = i >= 11 ? 0.55 * Math.sin(j * 1.1 + i * 1.3) * Math.sin((i - 10) * 0.9) : 0;
      pos.push(x, prof[i][1] * hk + (i > 4 && i < 10 ? wob : 0), prof[i][0] + wob * 0.6 + lump); uv.push((j / nx) * 3, 1 - i / (prof.length - 1));
    }
    for (let i = 0; i < prof.length - 1; i++) for (let j = 0; j < nx; j++) { const a = i * (nx + 1) + j, c = a + nx + 1; idx.push(a, c, a + 1, a + 1, c, c + 1); }
    const wg = new THREE.BufferGeometry(); wg.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
    void 0; wg.setAttribute("uv", new THREE.Float32BufferAttribute(uv, 2)); wg.setIndex(idx); wg.computeVertexNormals();
    this.waveMesh = new THREE.Mesh(wg, new THREE.MeshPhongMaterial({ map: syrupTex(), side: THREE.DoubleSide, emissive: new THREE.Color("#3a1a06"), specular: new THREE.Color("#ffd9a0"), shininess: 70 }));
    this.waveMesh.castShadow = true; this.waveMesh.receiveShadow = false;
    this.wave.add(this.waveMesh); this.wave.visible = false; this.root.add(this.wave);
    // debris tumbling in the wave: barrels, crates, planks (children of the wave, spun per frame)
    const barrelM = lam("barrel", () => ({ color: "#a8784a" })), hoopM = lam("hoop", () => ({ color: "#4a4552" })), crateM = lam("crate", () => ({ color: "#c9a06a" })), plankM = lam("plank", () => ({ color: "#9a6a3e" }));
    const spots: [number, number, number, number][] = [[-7, 6.9, 1.6, 0], [-2.5, 5.6, 2.6, 1], [3.5, 7.3, 1.2, 2], [7.5, 5.0, 2.4, 0], [0.5, 3.2, 1.6, 2], [-5.0, 2.6, 1.3, 1], [9.0, 7.0, 0.8, 1]];
    for (const [x, y, z, kind] of spots) {
      const d = new THREE.Group(); d.position.set(x, y, z); d.userData.spin = 0.6 + Math.abs(x) * 0.05;
      if (kind === 0) { add(new THREE.CylinderGeometry(0.42, 0.42, 1.1, 14), barrelM, d); add(new THREE.CylinderGeometry(0.45, 0.45, 0.12, 14).translate(0, 0.3, 0), hoopM, d); add(new THREE.CylinderGeometry(0.45, 0.45, 0.12, 14).translate(0, -0.3, 0), hoopM, d); }
      else if (kind === 1) add(box(-0.5, 0.5, -0.5, 0.5, -0.5, 0.5), crateM, d);
      else add(box(-1.4, 1.4, -0.08, 0.08, -0.22, 0.22), plankM, d);
      this.debris.push(d); this.wave.add(d);
    }
    // the flood sheet behind the wave (unit square, scaled per frame), 0.9 m deep
    this.flood = new THREE.Mesh(new THREE.PlaneGeometry(1, 1).rotateX(-Math.PI / 2), new THREE.MeshLambertMaterial({ map: rep(syrupFlatTex(), 6, 6), emissive: new THREE.Color("#3a1a08") }));
    this.flood.receiveShadow = true; this.flood.visible = false; this.root.add(this.flood);

    // the streetcar (a long box body with windows painted, a clerestory roof) and the truck
    const car = new Batch(), green = lam("carGreen", () => ({ map: carTex() })), cream = lam("carCream", () => ({ color: "#efe3c8" })), dark = lam("carDark", () => ({ color: "#2e3038" }));
    car.add(box(-1.25, 1.25, 0.5, 3.2, -6, 6), green);
    car.add(box(-1.35, 1.35, 3.2, 3.45, -6.2, 6.2), cream);
    car.add(box(-0.7, 0.7, 3.45, 3.8, -5, 5), cream);
    for (const z of [-4.2, 4.2]) car.add(box(-1.1, 1.1, 0.1, 0.5, z - 1, z + 1), dark);
    car.add(cylY(0.03, 3.8, 6.0, 0, 2, 6), dark);
    car.build(this.streetcar, true); this.root.add(this.streetcar);
    const tr = new Batch(), red = lam("truckRed", () => ({ color: "#b8362e" })), wood = lam("truckWood", () => ({ color: "#a8784a" }));
    tr.add(box(-1, 1, 0.6, 2.2, 1.0, 2.8), red);
    tr.add(box(-1.05, 1.05, 0.6, 1.4, -2.6, 1.0), wood);
    tr.add(box(-0.95, 0.95, 0.6, 1.3, 2.8, 3.8), red);
    for (const [x, z] of [[-1.05, 2.9], [1.05, 2.9], [-1.05, -1.6], [1.05, -1.6]] as const) tr.add(new THREE.CylinderGeometry(0.5, 0.5, 0.25, 14).rotateZ(Math.PI / 2).translate(x, 0.5, z), dark);
    tr.build(this.truck, true); this.root.add(this.truck);
    // a wooden ladder leaning on the tank's street side: foot 1.2 m out, top against the wall at 6 m
    const lw = lam("ladderWood", () => ({ color: "#b5834f" })), dx = -0.45, dz = 0.893, tx = -dz, tz = dx;
    const foot = V(TANK.x + (TANK.r + 1.2) * dx, 0, TANK.z + (TANK.r + 1.2) * dz), top = V(TANK.x + (TANK.r + 0.15) * dx, 6.2, TANK.z + (TANK.r + 0.15) * dz);
    const lb = new Batch(), rod = (a: THREE.Vector3, c: THREE.Vector3, r: number) => { const d = c.clone().sub(a), L = d.length(); const g = new THREE.CylinderGeometry(r, r, L, 6); g.translate(0, L / 2, 0); g.applyQuaternion(new THREE.Quaternion().setFromUnitVectors(V(0, 1, 0), d.normalize())); g.translate(a.x, a.y, a.z); return g; };
    for (const s of [-0.3, 0.3]) lb.add(rod(foot.clone().add(V(tx * s, 0, tz * s)), top.clone().add(V(tx * s, 0, tz * s)), 0.05), lw);
    for (let k = 1; k < 12; k++) { const p = foot.clone().lerp(top, k / 12); lb.add(rod(p.clone().add(V(-tx * 0.3, 0, -tz * 0.3)), p.clone().add(V(tx * 0.3, 0, tz * 0.3)), 0.035), lw); }
    lb.build(this.ladder, true); this.ladder.visible = false; this.root.add(this.ladder);
    const gp: THREE.Vector2[] = [[0, 0], [8, 0], [6.5, 0.3], [5.0, 0.6], [4.4, 0.8], [5.5, 0.9], [7.5, 0.96], [6.0, 1.02], [0, 1.06]].map(([r, y]) => new THREE.Vector2(r, y));
    this.geyser = new THREE.Mesh(new THREE.LatheGeometry(gp, 28), new THREE.MeshPhongMaterial({ map: syrupTex(), emissive: new THREE.Color("#3a1a06"), specular: new THREE.Color("#ffd9a0"), shininess: 60, side: THREE.DoubleSide }));
    this.curl = new THREE.Mesh(new THREE.TorusGeometry(2.2, 0.75, 12, 28, Math.PI * 1.2).rotateY(Math.PI / 2),
      new THREE.MeshPhongMaterial({ map: syrupTex(), emissive: new THREE.Color("#3a1a06"), specular: new THREE.Color("#ffd9a0"), shininess: 70, side: THREE.DoubleSide }));
    this.curl.visible = false; this.curl.castShadow = true; this.wave.add(this.curl);
    this.geyser.position.set(TANK.x, 0, TANK.z); this.geyser.visible = false; this.geyser.castShadow = true; this.root.add(this.geyser);
    add(box(-1.0, 1.0, -0.06, 0.06, -0.26, 0.26), lam("boardWood", () => ({ color: "#c98a4a" })), this.board); this.board.visible = false; this.root.add(this.board);
    const hull = new THREE.CylinderGeometry(1.0, 0.7, 4.2, 12, 1, false, 0, Math.PI).rotateZ(Math.PI / 2).rotateY(Math.PI / 2).scale(1, 0.55, 1);
    add(hull, lam("boatHull", () => ({ color: "#3f6fb5", side: THREE.DoubleSide })), this.boat);
    add(box(-0.9, 0.9, -0.05, 0.05, -0.2, 0.2).translate(0, 0.05, 0.4), lam("boatSeat", () => ({ color: "#c9a06a" })), this.boat);
    this.boat.visible = false; this.root.add(this.boat);
  }
  /** paint progress 0..1 turns the plates brown one by one, starting from the plate facing +x+z (the street side) */
  tank(look: TankLook, paint: number, burst: number, wobble: number) {
    const N = this.plates.length;
    this.plates.forEach((m, i) => {
      const order = (i - 28 + N) % N, painted = look === "brown" || (paint > 0 && order < Math.round(paint * N));
      m.material = painted ? this.tankMats.brown : this.tankMats[look];
      const piv = m.parent!, a = piv.userData.a as number, open = burst * (0.7 + 0.5 * hh(i, 3)) * (i % 3 === 0 ? 1.4 : 1);
      // fall outward about the tangent axis at the foot
      piv.rotation.set(0, 0, 0);
      piv.rotateOnWorldAxis(new THREE.Vector3(Math.cos(a), 0, -Math.sin(a)), open);
      void wobble;
    });
    this.roof.visible = burst < 0.05;
    this.roof.position.y = 0;
  }
  harborBrownOn(on: boolean) { this.harbor.material = on ? this.harborBrown : this.harborBlue; }
  /** the wave front at (x centre of the street, z) moving along +z (dir 1) or -z (dir -1), scaled in height */
  setWave(on: boolean, z = 0, dir = 1, hk = 1, xc = (STREET.x0 + STREET.x1) / 2, wx = 1, f = 0) {
    this.wave.visible = on;
    if (!on) return;
    this.debris.forEach((d, i) => { const a = f * 0.05 * d.userData.spin; d.rotation.set(a * (i % 2 ? 1 : -1), a * 0.6, a * 0.8 + i); });
    this.wave.position.set(xc, 0, z);
    this.wave.rotation.y = dir > 0 ? 0 : Math.PI;
    this.wave.scale.set(wx, hk, 1);
  }
  /** the flood sheet from z0 to z1 over the street (and the yard), at depth y */
  setFlood(on: boolean, z0 = 0, z1 = 0, y = 0.9) {
    this.flood.visible = on;
    if (!on) return;
    const x0 = STREET.x0 - 0.2, x1 = WHARF_X + 0.2;
    this.flood.position.set((x0 + x1) / 2, y, (z0 + z1) / 2); this.flood.scale.set(x1 - x0, 1, Math.abs(z1 - z0));
  }
}
const carTex = () => ctex("streetcar", 512, 256, (g) => {
  g.fillStyle = "#3f7a4a"; g.fillRect(0, 0, 512, 256);
  g.fillStyle = "#efe3c8"; g.fillRect(0, 40, 512, 90);
  for (let x = 16; x < 512; x += 62) { g.fillStyle = "#2c3a52"; g.fillRect(x, 50, 46, 70); g.fillStyle = "rgba(170,200,230,0.5)"; g.fillRect(x + 4, 54, 18, 30); }
  g.fillStyle = "#e8c45a"; g.fillRect(0, 180, 512, 10);
});

// ---------------- interiors ----------------
export class Office {
  root = new THREE.Group();
  constructor(parent: THREE.Object3D) {
    parent.add(this.root);
    const O = OFFICE, b = new Batch();
    room(this.root, O.x, O.z, 8, 7, 3.4, lam("offFloor", () => ({ color: "#8a6a4a" })), lam("offWall", () => ({ map: wallpaper("offWall", "#e6dcc0", "#dccfae") })));
    const wood = lam("offDesk", () => ({ color: "#7a4f33" })), green = lam("blotter", () => ({ color: "#3f6a4a" })), ledger = lam("ledger", () => ({ color: "#8c3b4a" }));
    b.add(box(O.x - 1.3, O.x + 1.3, 0, 0.78, O.z - 1.9, O.z - 1.1), wood);
    b.add(box(O.x - 0.6, O.x + 0.6, 0.78, 0.8, O.z - 1.75, O.z - 1.2), green);
    b.add(box(O.x + 0.65, O.x + 1.15, 0.78, 0.86, O.z - 1.7, O.z - 1.3), ledger);
    b.add(box(O.x - 1.2, O.x - 0.7, 0.78, 1.0, O.z - 1.8, O.z - 1.35), lam("adder", () => ({ color: "#2e3038" })));
    b.add(box(O.x - 1.15, O.x - 0.75, 1.0, 1.08, O.z - 1.7, O.z - 1.5), lam("adderKeys", () => ({ color: "#e8e0c8" })));
    // a file cabinet, a coat stand
    b.add(box(O.x + 2.4, O.x + 3.2, 0, 1.4, O.z - 3.4, O.z - 2.8), lam("cabinet", () => ({ color: "#5a6a5a" })));
    b.add(cylY(0.05, 0, 1.9, O.x - 2.8, O.z - 2.9, 8), wood);
    b.build(this.root, true);
    panel(this.root, windowTex(), 1.6, 2.0, O.x - 2.2, 1.75, O.z - 3.5, 0);
  }
}
export class Court {
  root = new THREE.Group();
  constructor(parent: THREE.Object3D) {
    parent.add(this.root);
    const C = COURT, b = new Batch();
    room(this.root, C.x, C.z, 10, 9, 4.2, lam("courtFloor", () => ({ color: "#7a5a3e" })), lam("courtWall", () => ({ map: rep(panelWood(), 1, 1) })));
    const wood = lam("benchWood", () => ({ color: "#6a3e26" })), trim = lam("benchTrim", () => ({ color: "#8a5a36" }));
    // the judge's bench: a raised box, the judge stands on a platform behind it
    b.add(box(C.x - 2.2, C.x + 2.2, 0, 1.45, C.z - 3.2, C.z - 2.4), wood);
    b.add(box(C.x - 2.3, C.x + 2.3, 1.45, 1.55, C.z - 3.3, C.z - 2.3), trim);
    b.add(box(C.x - 2.2, C.x + 2.2, 0, 0.5, C.z - 4.4, C.z - 3.2), wood);
    // the defendant's table on the right
    b.add(box(C.x + 1.0, C.x + 3.4, 0.72, 0.78, C.z - 0.3, C.z + 0.5), trim);
    for (const [dx, dz] of [[1.1, -0.2], [3.3, -0.2], [1.1, 0.4], [3.3, 0.4]]) b.add(box(C.x + dx - 0.04, C.x + dx + 0.04, 0, 0.72, C.z + dz - 0.04, C.z + dz + 0.04), trim);
    b.build(this.root, true);
    panel(this.root, signTex("courtSeal", 512, 512, "#e8c45a", "#6a3e26", [["COURT", 96], ["OF", 60], ["BOSTON", 80]], "Georgia"), 1.3, 1.3, C.x, 3.0, C.z - 4.5, 0, "#6a3e26");
  }
}
export class Subway {
  root = new THREE.Group();
  constructor(parent: THREE.Object3D) {
    parent.add(this.root);
    const S = SUBWAY, b = new Batch();
    room(this.root, S.x, S.z, 10, 7, 3.4, lam("subFloor", () => ({ color: "#b8ad98" })), lam("subTile", () => ({ map: rep(tileTex(), 1, 1) })), lam("subCeil", () => ({ color: "#d9d2c0" })));
    const wood = lam("subBench", () => ({ color: "#9a6a3e" })), iron = lam("subIron", () => ({ color: "#3a3d44" }));
    // a slatted wooden bench (seat + back) on iron legs
    b.add(box(S.x - 2.6, S.x + 0.2, 0.45, 0.52, S.z - 3.0, S.z - 2.55), wood);
    b.add(box(S.x - 2.6, S.x + 0.2, 0.55, 1.0, S.z - 3.12, S.z - 3.04), wood);
    for (const x of [-2.4, 0.0]) b.add(box(S.x + x - 0.05, S.x + x + 0.05, 0, 0.45, S.z - 2.9, S.z - 2.7), iron);
    // the payphone booth on the right: a wooden box with a window
    b.add(box(S.x + 1.8, S.x + 3.0, 0, 2.4, S.z - 3.5, S.z - 3.4), wood);
    b.add(box(S.x + 1.8, S.x + 1.9, 0, 2.4, S.z - 3.4, S.z - 2.4), wood);
    b.add(box(S.x + 2.9, S.x + 3.0, 0, 2.4, S.z - 3.4, S.z - 2.4), wood);
    b.add(box(S.x + 1.8, S.x + 3.0, 2.4, 2.55, S.z - 3.5, S.z - 2.3), iron);
    b.add(box(S.x + 2.2, S.x + 2.6, 1.3, 1.8, S.z - 3.4, S.z - 3.25), lam("phoneBox", () => ({ color: "#2e3038" })));
    b.build(this.root, true);
    panel(this.root, signTex("subSign", 1024, 256, "#2f6a5a", "#f4efe2", [["SCOLLAY SQUARE", 120]], "Georgia"), 3.2, 0.8, S.x - 1.2, 2.4, S.z - 3.45, 0);
  }
}
export { TAU };
