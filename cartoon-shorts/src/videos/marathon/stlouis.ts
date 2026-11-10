// The 1904 Olympic marathon film's sets (two-tone lam() geometry, outlined by the world ink).
// Flicker rules (whale, Mike and molasses films): no two surfaces closer than 5 cm unless exactly flush, every painted
// sign on the DEFAULT layer, one ground plane per set, roofs DoubleSide, fine patterns low-contrast.
//  Road: a dusty country road outside St. Louis, August 1904: rail fences, telegraph poles, dry fields, trees, the only
//    water well (with its sign), the MILE 9 and MILE 19 posts, an apple orchard, a farm, and the Boston 1905 banner.
//  Stadium: Francis Field: cinder track, a wooden grandstand full of people, the FINISH banner, the World's Fair dome.
//  Car: a 1904 open touring car (posed per frame), red for Lorz's ride, green for the officials.
import * as THREE from "three";
import { lam, Batch, V, quad, Kit, kitClone, prop } from "./build";
import { ctex, rep } from "./paint";
import { box, cylY, panel, signTex, hh } from "./boston";
import { ROAD, WELL, MILE9, MILE19, ORCHARD, DOGF, BOSTON, STAD, HICKS } from "./places";

const TAU = Math.PI * 2;
const add = (g: THREE.BufferGeometry, m: THREE.Material | THREE.Material[], parent: THREE.Object3D, cast = true) => {
  const mesh = new THREE.Mesh(g, m); mesh.castShadow = cast; mesh.receiveShadow = true; parent.add(mesh); return mesh;
};
const floorQ = (x0: number, x1: number, z0: number, z1: number, y: number, s: number) => {
  const g = new THREE.BufferGeometry(), P = [x0, y, z1, x1, y, z1, x1, y, z0, x0, y, z1, x1, y, z0, x0, y, z0];
  g.setAttribute("position", new THREE.Float32BufferAttribute(P, 3));
  const uv: number[] = []; for (let i = 0; i < 6; i++) uv.push(P[i * 3] / s, P[i * 3 + 2] / s);
  g.setAttribute("uv", new THREE.Float32BufferAttribute(uv, 2)); g.computeVertexNormals(); return g;
};

// ---------------- painted textures (low contrast) ----------------
const dirtTile = () => ctex("dirt1904", 1024, 1024, (g, r) => {
  g.fillStyle = "#c9a878"; g.fillRect(0, 0, 1024, 1024);
  for (let i = 0; i < 900; i++) { const c = r() < 0.5 ? "rgba(150,115,75,0.16)" : "rgba(225,200,160,0.18)"; g.fillStyle = c; g.beginPath(); g.ellipse(r() * 1024, r() * 1024, 6 + r() * 26, 4 + r() * 14, r() * 3, 0, TAU); g.fill(); }
  // wheel ruts along the road (v direction)
  g.fillStyle = "rgba(140,105,70,0.14)"; for (const x of [300, 420, 600, 720]) g.fillRect(x, 0, 34, 1024);
});
const fieldTile = () => ctex("field1904", 1024, 1024, (g, r) => {
  // v2: summer-green meadow with dry straw patches (the lemon-yellow field read flat after the punchier grade)
  // v2 round 3 (gate: "acid yellow-green stripes"): muted mid-green meadow with soft painted clumps, no blade strokes
  g.fillStyle = "#6f8a4c"; g.fillRect(0, 0, 1024, 1024);
  for (let i = 0; i < 40; i++) { g.fillStyle = r() < 0.5 ? "rgba(150,150,85,0.22)" : "rgba(85,120,60,0.25)"; g.beginPath(); g.ellipse(r() * 1024, r() * 1024, 70 + r() * 150, 40 + r() * 80, r() * 3, 0, TAU); g.fill(); }
  for (let i = 0; i < 700; i++) { const x = r() * 1024, y = r() * 1024, rr = 6 + r() * 14; g.fillStyle = "rgba(60,95,45,0.28)"; g.beginPath(); g.ellipse(x, y + rr * 0.3, rr, rr * 0.55, 0, 0, TAU); g.fill(); g.fillStyle = "rgba(140,170,95,0.3)"; g.beginPath(); g.ellipse(x - rr * 0.2, y - rr * 0.1, rr * 0.7, rr * 0.4, 0, 0, TAU); g.fill(); }
});
const strawTile = () => ctex("straw1904", 512, 256, (g, r) => {
  g.fillStyle = "#e0bd62"; g.fillRect(0, 0, 512, 256);
  for (let i = 0; i < 900; i++) { g.strokeStyle = r() < 0.5 ? "rgba(170,130,50,0.35)" : "rgba(250,225,140,0.4)"; g.lineWidth = 1 + r() * 2; const x = r() * 512, y = r() * 256; g.beginPath(); g.moveTo(x, y); g.lineTo(x + 30 + r() * 40, y + (r() - 0.5) * 6); g.stroke(); }
  for (let y = 0; y < 256; y += 64) { g.fillStyle = "rgba(150,110,40,0.35)"; g.fillRect(0, y, 512, 4); }
});
const usFlagTex = () => ctex("usflag1904", 320, 200, (g) => {
  for (let i = 0; i < 13; i++) { g.fillStyle = i % 2 ? "#f4f1ea" : "#c8352f"; g.fillRect(0, i * 200 / 13, 320, 200 / 13 + 1); }
  g.fillStyle = "#2a3f7a"; g.fillRect(0, 0, 140, 108);
  g.fillStyle = "#f4f1ea"; for (let r = 0; r < 5; r++) for (let c = 0; c < 6; c++) { g.beginPath(); g.arc(14 + c * 22 + (r % 2) * 6, 12 + r * 21, 4, 0, Math.PI * 2); g.fill(); }
});
const cinderTile = () => ctex("cinder1904", 512, 512, (g, r) => {
  g.fillStyle = "#b8705a"; g.fillRect(0, 0, 512, 512);
  for (let i = 0; i < 500; i++) { g.fillStyle = r() < 0.5 ? "rgba(140,80,60,0.18)" : "rgba(210,150,120,0.18)"; g.fillRect(r() * 512, r() * 512, 3 + r() * 9, 3 + r() * 9); }
});
const grassTile = () => ctex("infield1904", 512, 512, (g, r) => {
  g.fillStyle = "#7fa64a"; g.fillRect(0, 0, 512, 512);
  for (let i = 0; i < 500; i++) { g.fillStyle = r() < 0.5 ? "rgba(90,130,50,0.2)" : "rgba(160,190,90,0.2)"; g.fillRect(r() * 512, r() * 512, 4 + r() * 10, 3 + r() * 6); }
});
const stoneTile = () => ctex("well1904", 512, 256, (g, r) => {
  g.fillStyle = "#9a958a"; g.fillRect(0, 0, 512, 256);
  for (let y = 0; y < 256; y += 42) for (let x = (y / 42) % 2 ? 0 : 40; x < 560; x += 80) { const c = 150 + Math.floor(r() * 30); g.fillStyle = `rgb(${c},${c - 4},${c - 14})`; g.fillRect(x + 3, y + 3, 74, 36); }
});
/** a painted crowd for the grandstand (rows of heads, hats and shirts), 2048 x 1024 */
const crowdTex = () => ctex("crowd1904", 2048, 1024, (g, r) => {
  g.fillStyle = "#6a5444"; g.fillRect(0, 0, 2048, 1024);
  const shirts = ["#f4f1ea", "#d9d4c8", "#3f4f6a", "#8c3b4a", "#5d7a3a", "#e8c45a", "#f2efe6", "#4a4552"];
  const hats = ["#2e2a36", "#e8dcc0", "#f4f1ea", "#3a3346", "#c9a06a"];
  for (let row = 0; row < 8; row++) {
    const y = 80 + row * 122;
    for (let x = 20 + (row % 2) * 30; x < 2048; x += 60 + r() * 10) {
      g.fillStyle = shirts[Math.floor(r() * shirts.length)]; g.beginPath(); g.ellipse(x, y + 56, 26, 36, 0, 0, TAU); g.fill();
      g.fillStyle = ["#f5c9a0", "#e0b48a", "#ffe2c2"][Math.floor(r() * 3)]; g.beginPath(); g.ellipse(x, y, 19, 21, 0, 0, TAU); g.fill();
      g.fillStyle = hats[Math.floor(r() * hats.length)]; g.fillRect(x - 25, y - 22, 50, 8); g.fillRect(x - 15, y - 40, 30, 20);
      g.strokeStyle = "rgba(40,30,30,0.6)"; g.lineWidth = 3; g.beginPath(); g.ellipse(x, y, 19, 21, 0, 0, TAU); g.stroke();
    }
  }
});
const brickFront = (key: string, base: string) => ctex(key, 512, 512, (g, r) => {
  g.fillStyle = base; g.fillRect(0, 0, 512, 512);
  for (let y = 0; y < 512; y += 16) for (let x = (y / 16) % 2 ? 0 : 16; x < 512; x += 32) { g.fillStyle = `rgba(${r() < 0.5 ? "110,40,30" : "205,115,85"},0.12)`; g.fillRect(x + 1, y + 1, 30, 14); }
  for (let fl = 0; fl < 3; fl++) for (let i = 0; i < 4; i++) { g.fillStyle = "#2c3a52"; g.fillRect(40 + i * 120, 60 + fl * 150, 60, 90); g.fillStyle = "#efe3c8"; g.fillRect(34 + i * 120, 150 + fl * 150, 72, 10); }
});

// ---------------- the car ----------------
export type CarRig = { g: THREE.Group; wheels: THREE.Group[] };
/** a 1904 open touring car, 3.5 m long, local +z forward; seats: driver at (-0.35, 0.62, 0.05), back bench at z -0.95 */
export const makeCar = (key: string, body: string): CarRig => {
  const g = new THREE.Group(), b = new Batch();
  const paint = new THREE.MeshLambertMaterial({ color: body, emissive: new THREE.Color(body).multiplyScalar(0.18) }), dark = lam("carBlack", () => ({ color: "#24222a" })), brass = lam("carBrass", () => ({ color: "#d8a83a" }));
  const leather = lam("carLeather", () => ({ color: "#5a3424" }));
  b.add(box(-0.72, 0.72, 0.55, 1.0, -1.45, 0.55), paint);           // tub
  b.add(new THREE.CylinderGeometry(0.72, 0.72, 0.45, 20, 1, false, Math.PI / 2, Math.PI).translate(0, 0.775, -1.45), paint); // rounded rear
  b.add(box(-0.42, 0.42, 0.6, 0.98, 0.55, 1.45), paint);            // hood
  b.add(box(-0.46, 0.46, 0.52, 1.08, 1.45, 1.56), brass);           // radiator
  b.add(box(-0.36, 0.36, 0.6, 1.0, 1.56, 1.58), lam("carGrille", () => ({ color: "#7a6a4a" }))); // radiator core
  // v2: rounded, button-tufted leather seat backs (gate: "cuboid seats")
  const tuft = lam("carTuft", () => ({ color: "#3a2016" }));
  for (const [z, y] of [[-1.5, 1.14], [-0.14, 1.1]] as const) {
    b.add(new THREE.CylinderGeometry(0.15, 0.15, 1.32, 16).rotateZ(Math.PI / 2).translate(0, y, z), leather);
    b.add(box(-0.66, 0.66, 0.98, y, z - 0.08, z + 0.08), leather);
    for (let k = 0; k < 6; k++) b.add(new THREE.SphereGeometry(0.025, 6, 4).translate(-0.5 + k * 0.2, y + 0.02, z + (z < -1 ? 0.15 : -0.15)), tuft);
  }
  b.add(box(-0.86, 0.86, 0.5, 0.56, -1.0, 0.9), dark);              // running boards
  for (const s of [-1, 1]) for (const z of [1.15, -1.15])           // curved mudguards over the wheels
    b.add(new THREE.CylinderGeometry(0.52, 0.52, 0.22, 16, 1, true, -Math.PI / 2, Math.PI).rotateZ(Math.PI / 2).translate(s * 0.8, 0.45, z), lam("carGuard", () => ({ color: "#24222a", side: THREE.DoubleSide })));
  b.add(cylY(0.03, 1.0, 1.42, 0.35, 0.42, 6), dark);                // steering column
  b.add(new THREE.TorusGeometry(0.17, 0.025, 6, 16).rotateX(-1.1).translate(0.35, 1.42, 0.36), dark);
  // v2 (gate: "plain boxes"): big brass headlamps with glass, a gold pinstripe, carriage lamps on the dash, a bulb horn, a spare tyre
  const glass = lam("carGlass", () => ({ color: "#fff6d8", emissive: new THREE.Color("#7a6a3a") }));
  for (const s of [-1, 1]) {
    b.add(new THREE.CylinderGeometry(0.15, 0.13, 0.24, 16).rotateX(Math.PI / 2).translate(s * 0.58, 1.05, 1.52), brass);
    b.add(new THREE.CircleGeometry(0.12, 16).translate(s * 0.58, 1.05, 1.645), glass);
    b.add(box(s * 0.58 - 0.03, s * 0.58 + 0.03, 0.85, 0.95, 1.4, 1.46), brass);
    b.add(box(s * 0.725, s * 0.735, 0.88, 0.92, -1.45, 0.55), brass);                 // pinstripe
  }
  b.add(new THREE.TorusGeometry(0.36, 0.08, 8, 20).translate(0, 0.9, -2.2), dark);    // spare tyre on the back
  // big brass bulb horns on both sides by the back seat (they sit in the hook lens), a brass-framed windscreen
  for (const s of [-1, 1]) {
    b.add(new THREE.CylinderGeometry(0.03, 0.17, 0.62, 14).rotateX(Math.PI / 2).translate(s * 0.86, 1.18, -0.2), brass);
    b.add(new THREE.TorusGeometry(0.17, 0.025, 6, 16).translate(s * 0.86, 1.18, 0.11), brass);
    b.add(new THREE.SphereGeometry(0.11, 12, 8).translate(s * 0.86, 1.18, -0.6), lam("hornBulb", () => ({ color: "#2a2228" })));
    b.add(box(s * 0.62 - 0.025, s * 0.62 + 0.025, 1.0, 1.78, 0.52, 0.56), brass);
  }
  b.add(box(-0.64, 0.64, 1.74, 1.79, 0.52, 0.56), brass); b.add(box(-0.64, 0.64, 1.38, 1.41, 0.52, 0.56), brass);
  b.build(g, true);
  const wheels: THREE.Group[] = [];
  for (const [x, z] of [[-0.8, 1.15], [0.8, 1.15], [-0.8, -1.15], [0.8, -1.15]] as const) {
    const w = new THREE.Group(); w.position.set(x, 0.45, z); g.add(w);
    add(new THREE.TorusGeometry(0.4, 0.06, 8, 20).rotateY(Math.PI / 2), dark, w);
    for (let k = 0; k < 6; k++) add(box(-0.025, 0.025, -0.38, 0.38, -0.02, 0.02).rotateX((k / 6) * Math.PI), lam("spoke", () => ({ color: "#e8d9b0" })), w, false);
    add(new THREE.CylinderGeometry(0.08, 0.08, 0.14, 10).rotateZ(Math.PI / 2), brass, w, false);
    wheels.push(w);
  }
  return { g, wheels };
};

// ---------------- the road ----------------
export class Road {
  root = new THREE.Group();
  constructor(parent: THREE.Object3D, kit: Kit) {
    parent.add(this.root);
    const b = new Batch();
    // ONE ground plane = the dirt road; the fields are separate planes 7 cm higher
    b.add(floorQ(-700, 700, -800, 400, 0, 7), lam("dirt1904", () => ({ map: dirtTile() })));
    const fld = lam("field1904", () => ({ map: fieldTile() }));
    b.add(floorQ(-700, -ROAD.half, -800, 400, ROAD.field, 9), fld);
    b.add(floorQ(ROAD.half, 700, -800, 400, ROAD.field, 9), fld);
    // rail fences along both sides (gaps at the well and the orchard)
    const wood = lam("fence1904", () => ({ color: "#9a7a54" })), woodD = lam("fenceD1904", () => ({ color: "#7a5a3a" }));
    for (const s of [-1, 1]) {
      const x = s * 4.6;
      for (let z = -470; z < 120; z += 3.2) {
        if (s < 0 && z > WELL.z - 5 && z < WELL.z + 5) continue;
        if (s > 0 && z > ORCHARD.z - 30 && z < ORCHARD.z + 12) continue;
        if (s < 0 && z > DOGF.z - 25 && z < DOGF.z + 25) continue;
        b.add(box(x - 0.07, x + 0.07, 0, 1.2, z - 0.07, z + 0.07), woodD);
        for (const y of [0.55, 1.0]) b.add(box(x - 0.04, x + 0.04, y - 0.05, y + 0.05, z, z + 3.2), wood);
      }
    }
    // telegraph poles on the west side
    for (let z = -460; z < 120; z += 34) { b.add(cylY(0.12, 0, 7.5, -6.4, z, 8), woodD); b.add(box(-7.4, -5.4, 6.8, 6.95, z - 0.07, z + 0.07), woodD); }
    // the well: stone ring, two posts, a little roof, a bucket
    const stoneM = lam("well1904", () => ({ map: rep(stoneTile(), 2, 1) }));
    b.add(new THREE.CylinderGeometry(0.95, 1.0, 0.9, 20, 1, true).translate(WELL.x, 0.45 + ROAD.field, WELL.z), stoneM);
    b.add(new THREE.RingGeometry(0.75, 0.95, 20).rotateX(-Math.PI / 2).translate(WELL.x, 0.9 + ROAD.field, WELL.z), stoneM);
    b.add(new THREE.CircleGeometry(0.75, 20).rotateX(-Math.PI / 2).translate(WELL.x, 0.6 + ROAD.field, WELL.z), lam("wellWater", () => ({ color: "#2f4f6a" })));
    for (const s of [-1, 1]) b.add(box(WELL.x + s * 0.95 - 0.08, WELL.x + s * 0.95 + 0.08, 0, 2.3, WELL.z - 0.08, WELL.z + 0.08), woodD);
    const roofW = lam("wellRoof", () => ({ color: "#8c3b2a", side: THREE.DoubleSide }));
    b.add(quad(V(WELL.x - 1.3, 2.2, WELL.z + 0.9), V(WELL.x + 1.3, 2.2, WELL.z + 0.9), V(WELL.x + 1.3, 2.75, WELL.z), V(WELL.x - 1.3, 2.75, WELL.z)), roofW);
    b.add(quad(V(WELL.x + 1.3, 2.2, WELL.z - 0.9), V(WELL.x - 1.3, 2.2, WELL.z - 0.9), V(WELL.x - 1.3, 2.75, WELL.z), V(WELL.x + 1.3, 2.75, WELL.z)), roofW);
    b.add(cylY(0.05, 1.7, 1.75, WELL.x, WELL.z, 6).rotateZ(0), woodD);
    b.add(new THREE.CylinderGeometry(0.16, 0.13, 0.3, 10).translate(WELL.x + 0.6, 1.08, WELL.z + 0.2), lam("bucketTin", () => ({ color: "#9aa3ab" })));
    // a farm across the fields, a barn on the west
    b.add(box(36, 46, ROAD.field, 6, -50, -42), lam("farmWhite", () => ({ color: "#efe7d6" })));
    b.add(new THREE.CylinderGeometry(0.01, 6.6, 3.2, 4, 1).rotateY(Math.PI / 4).scale(1.08, 1, 0.62).translate(41, 7.6, -46), lam("farmRoof", () => ({ color: "#5a5058", side: THREE.DoubleSide })));
    b.add(box(-52, -40, ROAD.field, 7, -262, -248), lam("barnRed", () => ({ color: "#a8402e" })));
    b.add(new THREE.CylinderGeometry(0.01, 8.6, 3.6, 4, 1).rotateY(Math.PI / 4).scale(0.98, 1, 0.82).translate(-46, 8.8, -255), lam("farmRoof", () => ({ color: "#5a5058", side: THREE.DoubleSide })));
    // low hills on the horizon
    const hill = lam("hill1904", () => ({ color: "#a9a868" }));
    for (let i = 0; i < 14; i++) { const a = (i / 14) * TAU, d = 260 + 60 * hh(i, 3); b.add(new THREE.SphereGeometry(1, 16, 8, 0, TAU, 0, Math.PI / 2).scale(70 + 40 * hh(i, 1), 16 + 14 * hh(i, 2), 50).translate(Math.cos(a) * d, 0, Math.sin(a) * d - 150), hill); }
    // the Boston 1905 finish: two poles and a banner over the road, brick blocks behind
    const pole = lam("pole1905", () => ({ color: "#4a4552" }));
    for (const s of [-1, 1]) b.add(cylY(0.1, 0, 4.7, s * 2.4, BOSTON.z, 8), pole);
    for (let k = 0; k < 5; k++) { const x0 = -26 + k * 10.5, h = 11 + (k % 2) * 3, key = `bos1905_${k}`; b.add(box(x0, x0 + 10, 0, h, BOSTON.z - 32, BOSTON.z - 22), lam(key, () => ({ map: brickFront(key, ["#b5573f", "#a24a36", "#c9744f"][k % 3]) }))); }
    b.build(this.root, true);
    panel(this.root, signTex("bostonBanner", 1500, 400, "#f4f1ea", "#1f2a44", [["BOSTON MARATHON", 118], ["1905", 120]]), 4.6, 1.23, 0, 4.0, BOSTON.z, 0, "#f4f1ea");
    // the signs: WATER STOP 1 OF 1 (faces the road, +x), MILE 9 / MILE 19 (face the road, -x)
    const post = (x: number, z: number, h: number) => add(box(x - 0.07, x + 0.07, 0, h, z - 0.07, z + 0.07), woodD, this.root);
    post(WELL.x + 2.1, WELL.z + 1.8, 1.9);
    panel(this.root, signTex("waterSign", 800, 520, "#f4f1ea", "#1f2a44", [["WATER STOP", 96], ["1 OF 1", 170]]), 1.5, 0.98, WELL.x + 2.1, 2.0, WELL.z + 1.8, Math.PI / 2 - 0.35, "#9a7a54");
    for (const [m, n] of [[MILE9, "MILE 9"], [MILE19, "MILE 19"]] as const) {
      post(m.x, m.z, 1.6);
      panel(this.root, signTex(`mile${n}`, 640, 360, "#f4f1ea", "#1f2a44", [[n, 150]]), 1.0, 0.56, m.x, 1.75, m.z, -Math.PI / 2 + 0.5, "#9a7a54");
    }
    // trees: scattered, never on the road; the orchard rows east of the road
    const tree = (name: string, x: number, z: number, h: number, yaw: number) => { const o = kitClone(kit, name, h); if (!o) return; o.position.set(x, ROAD.field, z); o.rotation.y = yaw; this.root.add(o); };
    for (let i = 0; i < 70; i++) {
      const s = i % 2 ? 1 : -1, x = s * (14 + 70 * hh(i, 1)), z = -470 + 560 * hh(i, 2);
      if (Math.abs(z - ORCHARD.z) < 30 && s > 0) continue;
      tree(["tree_oak", "tree_default", "tree_fat", "tree-high-round"][i % 4], x, z, 6 + 5 * hh(i, 3), hh(i, 4) * TAU);
    }
    for (let r = 0; r < 4; r++) for (let c = 0; c < 4; c++) tree("tree_fat", ORCHARD.x + 2 + c * 5.5, ORCHARD.z + 8 - r * 6 + (c % 2) * 1.5, 4.2 + 0.4 * hh(r * 4 + c, 5), hh(r, c) * TAU);
    // ---- v2 set density (reference Short, 9 Nov): verges thick with tall grass, flowers and bushes, rocks and pebbles,
    // textured trees close in, hay bales, carts, a windmill and a fruit stall. Quaternius Stylized Nature MegaKit (CC0).
    const v = new Batch(), vt = new Batch();
    const P = (bb: Batch, name: string, x: number, z: number, h: number, yaw: number, y = ROAD.field) => prop(bb, kit, name, x, y, z, h, yaw);
    // keep the acted spots clear: the well and its man, the orchard nap, the dog field, Hicks' trainers
    const clear = (x: number, z: number) => (x < 0 && Math.abs(z - WELL.z) < 7 && x > -10) || (x > 0 && z > ORCHARD.z - 30 && z < ORCHARD.z + 12 && x < 16)
      || (x < 0 && Math.abs(z - DOGF.z) < 4 && x > -32) || (Math.abs(z - HICKS.z) < 1.5 && Math.abs(x) < 4.4)
      // the verge lenses ride along (hook, officials' car, the ride, the peach stall): no bush in front of the glass
      || (x > 3 && x < 6.2 && ((z > -26 && z < 2) || (z > 12 && z < 48) || (z > -142 && z < -98) || (z > -282 && z < -266)));
    for (let i = 0; i < 2400; i++) {
      const sd = i % 2 ? 1 : -1, z = -470 + 590 * hh(i, 11), x = sd * (3.75 + 10 * hh(i, 12) ** 2);
      if (clear(x, z)) continue;
      const q = hh(i, 13), name = q < 0.42 ? "Grass_Common_Tall" : q < 0.6 ? "Grass_Wispy_Tall" : q < 0.72 ? "Flower_3_Group" : q < 0.82 ? "Flower_4_Group" : q < 0.88 ? "Bush_Common_Flowers" : "Bush_Common";
      const h = name.startsWith("Bush") ? 0.65 + 0.5 * hh(i, 14) : name.startsWith("Flower") ? 0.4 + 0.3 * hh(i, 14) : 0.7 + 0.6 * hh(i, 14);
      P(v, name, x, z, h, hh(i, 15) * TAU);
    }
    for (let i = 0; i < 320; i++) { const x = -3.3 + 6.6 * hh(i, 21), z = -470 + 590 * hh(i, 22); P(v, i % 2 ? "Pebble_Round_1" : "Pebble_Round_3", x, z, 0.05 + 0.05 * hh(i, 23), hh(i, 24) * TAU, -0.01); }
    for (let i = 0; i < 70; i++) { const sd = i % 2 ? 1 : -1, x = sd * (5.2 + 12 * hh(i, 31)), z = -470 + 590 * hh(i, 32); if (clear(x, z)) continue; P(v, i % 3 ? "Rock_Medium_1" : "Rock_Medium_2", x, z, 0.3 + 0.45 * hh(i, 33), hh(i, 34) * TAU); }
    for (let i = 0; i < 110; i++) { const sd = i % 2 ? 1 : -1, x = sd * (7.5 + 10 * hh(i, 41)), z = -470 + 590 * hh(i, 42); if (clear(x, z)) continue; P(vt, `CommonTree_${1 + (i % 4)}`, x, z, 5.5 + 4 * hh(i, 43), hh(i, 44) * TAU); }
    // hay bales in the fields, a cart here and there, a windmill on the farm, a fruit stall by the road (the peaches)
    const straw = lam("straw1904", () => ({ map: rep(strawTile(), 2, 1) })), strawEnd = lam("strawEnd1904", () => ({ color: "#d9b45a" }));
    for (let i = 0; i < 46; i++) {
      const sd = i % 2 ? 1 : -1, x = sd * (9 + 26 * hh(i, 51)), z = -470 + 590 * hh(i, 52); if (clear(x, z)) continue;
      const yaw = hh(i, 53) * TAU, g = new THREE.CylinderGeometry(0.75, 0.75, 1.3, 18, 1, true).rotateZ(Math.PI / 2).rotateY(yaw).translate(x, ROAD.field + 0.75, z);
      v.add(g, straw);
      for (const e of [-1, 1]) v.add(new THREE.CircleGeometry(0.75, 18).rotateY(e * Math.PI / 2).rotateY(yaw).translate(x + e * 0.65 * Math.cos(yaw), ROAD.field + 0.75, z - e * 0.65 * Math.sin(yaw)), strawEnd);
    }
    for (let i = 0; i < 10; i++) { const sd = i % 2 ? 1 : -1; P(vt, "cart", sd * (6.5 + 6 * hh(i, 61)), -440 + 520 * hh(i, 62), 1.3, hh(i, 63) * TAU); }
    P(vt, "windmill", 30, -60, 11, 0.6); P(vt, "windmill", -34, -230, 12, 2.2); P(vt, "windmill", 26, -330, 10, 4.0);
    P(vt, "stall-red", 5.6, -275, 2.6, -Math.PI / 2);
    v.build(this.root, false); vt.build(this.root, true);
  }
}

// ---------------- the stadium ----------------
export class Stadium {
  root = new THREE.Group();
  constructor(parent: THREE.Object3D, kit: Kit) {
    parent.add(this.root);
    const X = STAD.x, Z = STAD.z, b = new Batch();
    b.add(floorQ(X - 300, X + 300, Z - 300, Z + 300, 0, 4), lam("cinder1904", () => ({ map: cinderTile() })));
    b.add(floorQ(X + 4.6, X + 300, Z - 300, Z + 300, 0.07, 5), lam("infield1904", () => ({ map: grassTile() })));
    // the finish line: a white strip 6 cm proud of the cinders
    b.add(box(X - 4.4, X + 4.4, 0, 0.06, Z - 0.15, Z + 0.15), lam("chalk", () => ({ color: "#f4f1ea" })));
    // grandstand west of the track: a low wall, a sloped bank of painted crowd, a roof on posts
    const wood = lam("stand1904", () => ({ color: "#8a6a4a" })), woodL = lam("standL1904", () => ({ color: "#c9a878" }));
    b.add(box(X - 7.2, X - 6.9, 0, 1.2, Z - 70, Z + 70), woodL);
    const crowdM = lam("crowd1904", () => ({ map: rep(crowdTex(), 6, 1) }));
    b.add(quad(V(X - 7.6, 1.2, Z + 70), V(X - 7.6, 1.2, Z - 70), V(X - 19, 8.6, Z - 70), V(X - 19, 8.6, Z + 70)), crowdM);
    b.add(box(X - 19.6, X - 19, 0, 11.5, Z - 70, Z + 70), wood);
    for (let z = -68; z <= 68; z += 8) b.add(box(X - 7.8, X - 7.55, 1.2, 11, Z + z - 0.12, Z + z + 0.12), wood);
    b.add(quad(V(X - 7.0, 11, Z - 70), V(X - 7.0, 11, Z + 70), V(X - 20, 11.8, Z + 70), V(X - 20, 11.8, Z - 70)), lam("standRoof", () => ({ color: "#5a5058", side: THREE.DoubleSide })));
    // finish posts
    for (const s of [-1, 1]) b.add(cylY(0.12, 0, 4.8, X + s * 4.6, Z, 8), lam("pole1904", () => ({ color: "#f4f1ea" })));
    // the World's Fair across the infield: a white palace with a dome
    const white = lam("palace", () => ({ color: "#f2efe6" }));
    b.add(box(X + 50, X + 110, 0.07, 14, Z - 160, Z - 120), white);
    b.add(new THREE.SphereGeometry(14, 24, 12, 0, TAU, 0, Math.PI / 2).translate(X + 80, 14, Z - 140), white);
    b.add(cylY(2, 28, 34, X + 80, Z - 140, 12), white);
    // v2 density: red / white / blue pennant bunting swagged along the stand front and across the finish posts, flags on the roof
    const pen = [lam("penR", () => ({ color: "#d23a32", side: THREE.DoubleSide })), lam("penW", () => ({ color: "#f4f1ea", side: THREE.DoubleSide })), lam("penB", () => ({ color: "#2f5aa8", side: THREE.DoubleSide }))];
    const bunting = (x0: number, y0: number, z0: number, x1: number, y1: number, z1: number, n: number, sag: number, sz = 0.32) => {
      for (let i = 0; i < n; i++) {
        const u = (i + 0.5) / n, x = x0 + (x1 - x0) * u, z = z0 + (z1 - z0) * u, y = y0 + (y1 - y0) * u - sag * 4 * u * (1 - u);
        const dx = (x1 - x0) / n * 0.42, dz = (z1 - z0) / n * 0.42;
        const tg = new THREE.BufferGeometry().setFromPoints([V(x - dx, y, z - dz), V(x + dx, y, z + dz), V(x, y - sz, z)]);
        tg.setAttribute("uv", new THREE.Float32BufferAttribute([0, 0, 1, 0, 0.5, 1], 2)); tg.computeVertexNormals(); b.add(tg, pen[i % 3]);
      }
    };
    for (let z = -70; z < 70; z += 10) bunting(X - 7.6, 10.6, Z + z, X - 7.6, 10.6, Z + z + 10, 16, 0.9);
    bunting(X - 4.6, 4.75, Z + 0.15, X + 4.6, 4.75, Z + 0.15, 22, 0.5, 0.26);
    bunting(X - 7.6, 6.0, Z - 6, X - 4.6, 4.6, Z - 1, 10, 0.3, 0.26);
    for (let z = -64; z <= 64; z += 16) { b.add(cylY(0.05, 11.6, 15, X - 13, Z + z, 6), lam("flagpole", () => ({ color: "#f4f1ea" })));
      b.add(new THREE.PlaneGeometry(1.6, 1.0).translate(0.8, 0, 0).rotateY(0.4 + 0.3 * hh(z, 2)).translate(X - 13, 14.4, Z + z), lam("usflag", () => ({ map: usFlagTex(), side: THREE.DoubleSide }))); }
    b.build(this.root, true);
    // one readable face per side, 30 cm apart, an opaque board between (the back of one face showed through mirrored)
    for (const yaw of [0, Math.PI]) panel(this.root, signTex("finish1904", 1200, 260, "#f4f1ea", "#c0353a", [["FINISH", 170]]), 8.8, 1.3, X, 4.2, Z + (yaw ? -0.15 : 0.15), yaw, "#f4f1ea");
    add(box(X - 4.45, X + 4.45, 4.2 - 0.7, 4.2 + 0.7, Z - 0.1, Z + 0.1), lam("finishBoard", () => ({ color: "#f4f1ea" })), this.root);
    panel(this.root, signTex("games1904", 2400, 260, "#1f2a44", "#f2c230", [["OLYMPIC GAMES  ST. LOUIS 1904", 150]]), 22, 1.6, X - 6.95, 2.2, Z - 12, Math.PI / 2, "#1f2a44");
    const tree = (name: string, x: number, z: number, h: number) => { const o = kitClone(kit, name, h); if (!o) return; o.position.set(x, 0.07, z); this.root.add(o); };
    for (let i = 0; i < 16; i++) tree(["tree_oak", "tree_default", "tree-high-round"][i % 3], X + 24 + 40 * hh(i, 1), Z - 100 + 200 * hh(i, 2), 7 + 4 * hh(i, 3));
  }
}
