// The modern escalator (steps on two chains, two wheel tracks, combs, glass balustrades, rubber handrails, the truss,
// the drive) and the 1898 Harrods leather belt. Everything is two-tone lam() geometry so the world ink outlines it;
// steps, chain links and drive-chain links are InstancedMeshes posed every frame from escpath.ts. `cut` = cutaway mode:
// the near-side cladding, ground and deck are hidden by world.ts, the far cladding becomes the back wall of the section.
import * as THREE from "three";
import { mergeGeometries } from "three/examples/jsm/utils/BufferGeometryUtils.js";
import { lam } from "./build";
import { ctex, rep } from "./paint";
import { NOINK } from "./ink";
import {
  RISE, HC, R, NSTEP, PITCH, LOOP, SPEED, X0, XB, XT, XS1, h, poseAt, onStep, stepS, SPROCKET_TOP, SPROCKET_BOT, REAR, RW_FRONT, RW_REAR,
  Z_FRONT, Z_REAR, Z_CHAIN, HR_Z, NEWEL_R, XA_RAIL, XB_RAIL, railY, HR_UP, sprocketAngle, HB, beltY,
} from "./escpath";

const TAU = Math.PI * 2;
type XY = [number, number];
const box = (x0: number, x1: number, y0: number, y1: number, z0: number, z1: number) =>
  new THREE.BoxGeometry(x1 - x0, y1 - y0, z1 - z0).translate((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2);
const cylZ = (r: number, z0: number, z1: number, x: number, y: number, seg = 24) =>
  new THREE.CylinderGeometry(r, r, z1 - z0, seg).rotateX(Math.PI / 2).translate(x, y, (z0 + z1) / 2);
/** 2D outline (xy) extruded across z0..z1 */
const extrudeXY = (pts0: XY[], z0: number, z1: number) => {
  const v = pts0.map(([x, y]) => new THREE.Vector2(x, y));
  if (THREE.ShapeUtils.isClockWise(v)) v.reverse();
  const s = new THREE.Shape(v);
  return new THREE.ExtrudeGeometry(s, { depth: z1 - z0, bevelEnabled: false, curveSegments: 6 }).translate(0, 0, z0);
};
/** a rail: a rectangular bar under the polyline, w across z, hgt below the line */
const railAlong = (line: XY[], z: number, w: number, hgt: number) => {
  const parts: THREE.BufferGeometry[] = [];
  for (let i = 0; i + 1 < line.length; i++) {
    const [ax, ay] = line[i], [bx, by] = line[i + 1], L = Math.hypot(bx - ax, by - ay), a = Math.atan2(by - ay, bx - ax);
    const g = new THREE.BoxGeometry(L + 0.004, hgt, w);
    g.translate(0, -hgt / 2, 0).rotateZ(a).translate((ax + bx) / 2, (ay + by) / 2, z);
    parts.push(g);
  }
  return mergeGeometries(parts, false);
};
/** vertical band between a top and a bottom profile, at plane z (normal +z or -z) */
const bandXY = (xs: number[], top: (x: number) => number, bot: (x: number) => number, z: number, facePlus: boolean, vScale = 1) => {
  const pos: number[] = [], uv: number[] = [], nz = facePlus ? 1 : -1;
  for (let i = 0; i + 1 < xs.length; i++) {
    const a = xs[i], b = xs[i + 1];
    const A = [a, bot(a), z], B = [b, bot(b), z], C = [b, top(b), z], D = [a, top(a), z];
    const quadP = facePlus ? [A, B, C, A, C, D] : [B, A, D, B, D, C];
    for (const p of quadP) { pos.push(...p); uv.push(p[0] / vScale, p[1] / vScale); }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute("normal", new THREE.Float32BufferAttribute(pos.map((_, i) => (i % 3 === 2 ? nz : 0)), 3));
  g.setAttribute("uv", new THREE.Float32BufferAttribute(uv, 2));
  return g;
};
/** horizontal-ish strip following a profile y(x), from z0 to z1, facing up */
const stripXY = (xs: number[], y: (x: number) => number, z0: number, z1: number) => {
  const pos: number[] = [], uv: number[] = [];
  for (let i = 0; i + 1 < xs.length; i++) {
    const a = xs[i], b = xs[i + 1];
    const P = [[a, y(a), z1], [b, y(b), z1], [b, y(b), z0], [a, y(a), z1], [b, y(b), z0], [a, y(a), z0]];
    for (const p of P) { pos.push(...p); uv.push(p[0], p[2]); }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute("uv", new THREE.Float32BufferAttribute(uv, 2));
  g.computeVertexNormals();
  return g;
};
const range = (a: number, b: number, n: number) => Array.from({ length: n + 1 }, (_, i) => a + ((b - a) * i) / n);
/** a gear / sprocket: a disc + n tooth blocks round pitch radius r (tooth depth d), across z0..z1, centred at the
 *  origin; `hub` > 0 adds a raised hub and four spoke bosses so the turning reads */
const gearGeo = (n: number, r: number, d: number, z0: number, z1: number, hub = 0) => {
  const zc = (z0 + z1) / 2, dz = z1 - z0, parts: THREE.BufferGeometry[] = [];
  parts.push(new THREE.CylinderGeometry(r - d * 0.4, r - d * 0.4, dz, Math.max(24, n * 3)).rotateX(Math.PI / 2).translate(0, 0, zc));
  for (let i = 0; i < n; i++) {
    const a = (i / n) * TAU, tw = ((TAU * r) / n) * 0.45;
    parts.push(new THREE.BoxGeometry(d * 1.1, tw, dz).translate(r + d * 0.1, 0, zc).rotateZ(a).toNonIndexed());
  }
  if (hub > 0) {
    parts.push(new THREE.CylinderGeometry(r * 0.22, r * 0.22, dz * 2.2, 18).rotateX(Math.PI / 2).translate(0, 0, zc));
    for (let k = 0; k < 4; k++) {
      const a = (k / 4) * TAU + 0.4;
      parts.push(new THREE.CylinderGeometry(r * 0.12, r * 0.12, dz * 1.6, 12).rotateX(Math.PI / 2).translate(Math.cos(a) * r * 0.58, Math.sin(a) * r * 0.58, zc));
    }
  }
  return mergeGeometries(parts.map((g) => (g.index ? g.toNonIndexed() : g)), false);
};

// ---------------- painted textures ----------------
const checkerPlate = () => ctex("checkerPlate", 512, 512, (g) => {
  g.fillStyle = "#b8bcc4"; g.fillRect(0, 0, 512, 512);
  for (let y = 0; y < 8; y++) for (let x = 0; x < 8; x++) {
    const cx = x * 64 + (y % 2) * 32 + 16, cy = y * 64 + 32;
    g.save(); g.translate(cx, cy); g.rotate((y + x) % 2 ? 0.8 : -0.8);
    g.fillStyle = "#d9dce2"; g.fillRect(-16, -4, 32, 8); g.fillStyle = "#8c9099"; g.fillRect(-16, 3, 32, 2);
    g.restore();
  }
  g.strokeStyle = "rgba(60,60,70,0.5)"; g.lineWidth = 6; g.strokeRect(3, 3, 506, 506);
});
const handrailTex = () => ctex("handrailTex", 256, 32, (g) => {
  g.fillStyle = "#26232b"; g.fillRect(0, 0, 256, 32);
  g.fillStyle = "#3d3944"; g.fillRect(0, 4, 256, 6);
  g.fillStyle = "#5b5563"; g.fillRect(120, 0, 16, 32); // one seam per tile: shows the rail moving
});
const leatherTex = () => ctex("leatherBelt", 512, 256, (g, r) => {
  // woven leather belt: 4 linked pieces per tile (columns = across the belt), rivets, a dark seam between pieces
  g.fillStyle = "#8a5232"; g.fillRect(0, 0, 512, 256);
  for (let i = 0; i < 4; i++) {
    const x = i * 128;
    g.fillStyle = i % 2 ? "#93593a" : "#7f4a2c"; g.fillRect(x + 6, 0, 116, 256);
    g.fillStyle = "rgba(255,220,170,0.16)"; g.fillRect(x + 12, 0, 10, 256);
    g.fillStyle = "#3a2216"; g.fillRect(x, 0, 6, 256);
    for (let k = 0; k < 6; k++) { g.fillStyle = "#d9b26a"; g.beginPath(); g.arc(x + 64, 22 + k * 42, 5, 0, TAU); g.fill(); }
    for (let k = 0; k < 40; k++) { g.fillStyle = `rgba(40,20,10,${0.08 + r() * 0.08})`; g.fillRect(x + 10 + r() * 110, r() * 256, 2, 2 + r() * 10); }
  }
});
const mahoganyTex = () => ctex("mahogany", 512, 256, (g, r) => {
  g.fillStyle = "#7a3a22"; g.fillRect(0, 0, 512, 256);
  for (let i = 0; i < 70; i++) { g.strokeStyle = `rgba(${40 + r() * 30},${15 + r() * 10},8,${0.25 + r() * 0.25})`; g.lineWidth = 1 + r() * 3;
    const y = r() * 256; g.beginPath(); g.moveTo(0, y); g.bezierCurveTo(170, y + (r() - 0.5) * 30, 340, y + (r() - 0.5) * 30, 512, y + (r() - 0.5) * 20); g.stroke(); }
  // raised panels
  g.strokeStyle = "rgba(30,10,4,0.75)"; g.lineWidth = 7;
  for (let k = 0; k < 2; k++) g.strokeRect(18 + k * 256, 28, 220, 200);
  g.strokeStyle = "rgba(255,190,140,0.25)"; g.lineWidth = 3;
  for (let k = 0; k < 2; k++) g.strokeRect(26 + k * 256, 36, 204, 184);
});

// ---------------- the modern escalator ----------------
export type EscFlags = { cut: boolean; glowFront: number; glowRear: number; glowTracks: number; glowRail: number; glowChain: number; glowMotor: number; noTopPlate: boolean };
const NR = 12; // tread ridges (22 thin ones inked solid black at grazing views)

export class Escalator {
  root = new THREE.Group();
  /** near-side pieces world.ts hides in cutaway shots */
  near = new THREE.Group();
  private parts: THREE.InstancedMesh[] = [];
  private links: THREE.InstancedMesh; private linkMat!: THREE.MeshLambertMaterial;
  private dlinks: THREE.InstancedMesh; private dMat!: THREE.MeshLambertMaterial;
  private sprTop: THREE.Object3D[] = []; private sprBot: THREE.Object3D[] = []; private bigGear: THREE.Object3D; private motorSpr: THREE.Object3D;
  private hrWheels: THREE.Object3D[] = [];
  private rails: THREE.MeshLambertMaterial[] = [];
  private front: THREE.MeshLambertMaterial; private rear: THREE.MeshLambertMaterial;
  private hrBelt = new THREE.Group();
  private hrTex: THREE.Texture[] = []; private hrLen = 1; private hrMats: THREE.MeshLambertMaterial[] = [];
  private topPlate: THREE.Object3D;
  private drive: { c1: XY; r1: number; c2: XY; r2: number; path: { p: XY[]; s: number[]; L: number } };
  private m4 = new THREE.Matrix4(); private q = new THREE.Quaternion(); private e = new THREE.Euler(); private v3 = new THREE.Vector3(); private one = new THREE.Vector3(1, 1, 1);

  constructor(parent: THREE.Object3D) {
    parent.add(this.root);
    this.root.add(this.near);
    const M = {
      tread: lam("escTread", () => ({ color: "#a9aeb8" })),
      yellow: lam("escYellow", () => ({ color: "#f2c230" })),
      riser: lam("escRiser", () => ({ color: "#8c919c" })),
      yoke: lam("escYoke", () => ({ color: "#4b505c" })),
      steel: lam("escSteel", () => ({ color: "#6f7581" })),
      chain: lam("escChain", () => ({ color: "#3d414c" })),
      skirt: lam("escSkirt", () => ({ color: "#c9ccd3" })),
      clad: lam("escClad", () => ({ color: "#d8d4cc" })),
      cladIn: lam("escCladIn", () => ({ color: "#ece4d4", side: THREE.DoubleSide })),
      plate: lam("escPlate", () => ({ map: rep(checkerPlate(), 4, 1.2) })),
      comb: lam("escComb", () => ({ color: "#e0b43a" })),
      motor: lam("escMotor", () => ({ color: "#3f9d6a" })),
      gear: lam("escGear", () => ({ color: "#c8823a" })),
      pit: lam("escPit", () => ({ color: "#a7a49c", side: THREE.DoubleSide })),
    };
    this.front = lam("escFrontWheel", () => ({ color: "#f08a2c" })) as THREE.MeshLambertMaterial;
    this.rear = lam("escRearWheel", () => ({ color: "#3f8fd5" })) as THREE.MeshLambertMaterial;
    const frontRail = lam("escFrontRail", () => ({ color: "#d9792a" })) as THREE.MeshLambertMaterial;
    const rearRail = lam("escRearRail", () => ({ color: "#3a7fc2" })) as THREE.MeshLambertMaterial;
    this.rails = [frontRail, rearRail];

    // ---- one step, in its local frame (front axle at the origin, x forward, tread top at y = HC) ----
    const T0 = -0.395, T1 = -0.008, TY = HC;
    const treadG: THREE.BufferGeometry[] = [box(T0, T1, TY - 0.045, TY - 0.012, -0.5, 0.5)];
    const yelG: THREE.BufferGeometry[] = [];
    for (let i = 0; i < NR; i++) {
      const zc = -0.5 + ((i + 0.5) / NR), w = 0.048;
      const edge = i === 0 || i === NR - 1;
      if (edge) yelG.push(box(T0, T1, TY - 0.012, TY, zc - w / 2, zc + w / 2));
      else { treadG.push(box(T0, T1 - 0.055, TY - 0.012, TY, zc - w / 2, zc + w / 2)); yelG.push(box(T1 - 0.055, T1, TY - 0.012, TY, zc - w / 2, zc + w / 2)); }
    }
    yelG.push(box(T0, T0 + 0.03, TY - 0.012, TY - 0.002, -0.5, 0.5)); // yellow back edge line
    const riserG = [box(-0.41, -0.392, TY - 0.235, TY - 0.012, -0.49, 0.49)];
    for (let i = 0; i < 12; i++) { const zc = -0.46 + (i * 0.92) / 11; riserG.push(box(-0.418, -0.408, TY - 0.23, TY - 0.02, zc - 0.012, zc + 0.012)); }
    const yokePts: XY[] = [[T0 + 0.01, TY - 0.045], [T1, TY - 0.045], [0.03, 0.02], [0.0, -0.04], [REAR[0] - 0.03, REAR[1] - 0.03], [REAR[0] - 0.05, REAR[1] + 0.04]];
    const yokeG = [extrudeXY(yokePts, -0.5, -0.47), extrudeXY(yokePts, 0.47, 0.5)];
    const axleG = [cylZ(0.022, -Z_CHAIN, Z_CHAIN, 0, 0, 10), cylZ(0.018, -Z_REAR, -0.47, REAR[0], REAR[1], 8), cylZ(0.018, 0.47, Z_REAR, REAR[0], REAR[1], 8)];
    const frontW = [cylZ(RW_FRONT, Z_FRONT - 0.024, Z_FRONT + 0.024, 0, 0, 20), cylZ(RW_FRONT, -Z_FRONT - 0.024, -Z_FRONT + 0.024, 0, 0, 20)];
    const rearW = [cylZ(RW_REAR, Z_REAR - 0.022, Z_REAR + 0.022, REAR[0], REAR[1], 20), cylZ(RW_REAR, -Z_REAR - 0.022, -Z_REAR + 0.022, REAR[0], REAR[1], 20)];
    const hubs = [cylZ(0.022, Z_FRONT + 0.024, Z_FRONT + 0.03, 0, 0, 10), cylZ(0.022, -Z_FRONT - 0.03, -Z_FRONT - 0.024, 0, 0, 10),
      cylZ(0.02, Z_REAR + 0.022, Z_REAR + 0.028, REAR[0], REAR[1], 10), cylZ(0.02, -Z_REAR - 0.028, -Z_REAR - 0.022, REAR[0], REAR[1], 10)];
    for (const [geos, mat] of [[treadG, M.tread], [yelG, M.yellow], [riserG, M.riser], [yokeG, M.yoke], [axleG, M.steel], [frontW, this.front], [rearW, this.rear], [hubs, M.chain]] as const) {
      const g = mergeGeometries(geos.map((x) => (x.index ? x.toNonIndexed() : x)), false);
      const im = new THREE.InstancedMesh(g, mat, NSTEP);
      im.castShadow = true; im.receiveShadow = true; im.frustumCulled = false;
      this.root.add(im); this.parts.push(im);
    }
    // ---- step chains: one link per step gap on each side ----
    this.linkMat = lam("escStepChain", () => ({ color: "#5a6070" })) as THREE.MeshLambertMaterial;
    this.links = new THREE.InstancedMesh(new THREE.BoxGeometry(1, 0.075, 0.04), this.linkMat, NSTEP * 2);
    this.links.castShadow = true; this.links.receiveShadow = true; this.links.frustumCulled = false;
    this.root.add(this.links);

    // ---- static: tracks, sprockets, combs, landings, skirts, decking, glass, cladding, the pit ----
    const add = (g: THREE.BufferGeometry, m: THREE.Material, parent: THREE.Object3D = this.root, cast = true) => {
      const x = new THREE.Mesh(g, m); x.castShadow = cast; x.receiveShadow = true; parent.add(x); return x;
    };
    const xsTop = range(X0 + 0.35, XS1 - 0.25, 260);
    for (const side of [-1, 1]) {
      // front-wheel track (upper + return), rear-wheel track (upper + return)
      add(railAlong(xsTop.map((x) => [x, h(x) - HC - RW_FRONT] as XY), side * Z_FRONT, 0.05, 0.03), frontRail);
      add(railAlong(xsTop.map((x) => [x, h(x) - HC - 2 * R - RW_FRONT] as XY), side * Z_FRONT, 0.05, 0.03), frontRail);
      add(railAlong(xsTop.map((x) => [x + REAR[0], h(x) - HC + REAR[1] - RW_REAR] as XY), side * Z_REAR, 0.045, 0.03), rearRail);
      add(railAlong(xsTop.map((x) => [x - REAR[0], h(x) - HC - 2 * R - REAR[1] - RW_REAR] as XY), side * Z_REAR, 0.045, 0.03), rearRail);
    }
    // sprockets (8 teeth round R) + shafts
    for (const [c, list] of [[SPROCKET_TOP, this.sprTop], [SPROCKET_BOT, this.sprBot]] as const) {
      for (const side of [-1, 1]) {
        const g = new THREE.Mesh(gearGeo(10, R, 0.09, -0.02, 0.02, 1), M.gear);
        g.position.set(c.x, c.y, side * Z_FRONT); g.castShadow = true; g.receiveShadow = true;
        (side > 0 ? this.near : this.root).add(g); list.push(g);
      }
      add(cylZ(0.055, -0.8, 0.6, c.x, c.y, 16), M.steel, this.root, false);
    }
    // the drive: motor + gearbox + small sprocket, a drive chain up to the big gear on the main shaft
    const C1: XY = [SPROCKET_TOP.x, SPROCKET_TOP.y], R1 = 0.36, C2: XY = [XS1 + 1.15, RISE - 1.3], R2 = 0.14, ZD = -0.74;
    this.bigGear = new THREE.Mesh(gearGeo(18, R1, 0.05, ZD - 0.025, ZD + 0.025, 1), M.motor);
    this.bigGear.position.set(C1[0], C1[1], 0); this.bigGear.castShadow = true; this.root.add(this.bigGear);
    this.motorSpr = new THREE.Mesh(gearGeo(9, R2, 0.04, ZD - 0.025, ZD + 0.025), M.gear);
    this.motorSpr.position.set(C2[0], C2[1], 0); this.root.add(this.motorSpr);
    add(new THREE.CylinderGeometry(0.24, 0.24, 0.62, 28).rotateZ(Math.PI / 2).translate(C2[0] + 0.45, C2[1], -0.5), M.motor);
    for (let i = 0; i < 5; i++) add(new THREE.CylinderGeometry(0.255, 0.255, 0.03, 28).rotateZ(Math.PI / 2).translate(C2[0] + 0.25 + i * 0.11, C2[1], -0.5), M.yoke); // cooling ribs
    add(box(C2[0] - 0.24, C2[0] + 0.24, C2[1] - 0.2, C2[1] + 0.2, -0.72, -0.3), M.steel); // gearbox
    add(cylZ(0.04, ZD - 0.04, -0.7, C2[0], C2[1], 12), M.steel);
    add(box(C2[0] - 0.35, C2[0] + 0.35, RISE - 2.03, C2[1] - 0.22, -0.76, -0.24), M.yoke); // motor bed
    this.drive = { c1: C1, r1: R1, c2: C2, r2: R2, path: beltPath(C1, R1, C2, R2) };
    const nd = Math.round(this.drive.path.L / 0.06);
    this.dMat = lam("escDriveChain", () => ({ color: "#5a6070" })) as THREE.MeshLambertMaterial;
    this.dlinks = new THREE.InstancedMesh(new THREE.BoxGeometry(0.06, 0.05, 0.04), this.dMat, nd);
    this.dlinks.frustumCulled = false; this.dlinks.castShadow = true; this.root.add(this.dlinks);
    {
      const HW: XY = [XT - 0.6, RISE - 0.75 - 0.18], z = -HR_Z;
      const w = new THREE.Mesh(gearGeo(14, 0.13, 0.03, -0.035, 0.035, 1), M.motor);
      w.position.set(HW[0], HW[1], z); this.root.add(w); this.hrWheels.push(w);
      const pul = new THREE.Mesh(gearGeo(10, 0.13, 0.03, -0.03, 0.03, 0), M.motor);
      pul.position.set(C1[0], C1[1], z); this.root.add(pul); this.hrWheels.push(pul);
      add(railAlong([[HW[0], HW[1] + 0.13], [C1[0], C1[1] + 0.13]], z, 0.04, 0.035), M.motor);
      add(railAlong([[HW[0], HW[1] - 0.1], [C1[0], C1[1] - 0.1]], z, 0.04, 0.035), M.motor);
      add(cylZ(0.03, z - 0.06, z + 0.06, HW[0], HW[1], 10), M.steel, this.root, false);
    }
    // combs: a base plate + teeth that reach into the tread grooves (bottom teeth point +x, top teeth point -x)
    for (const [xc, dir, y] of [[XB, 1, 0], [XT, -1, RISE]] as const) {
      const g: THREE.BufferGeometry[] = [dir > 0 ? box(xc - 0.3, xc - 0.12, y + 0.002, y + 0.03, -0.5, 0.5) : box(xc + 0.12, xc + 0.3, y + 0.002, y + 0.03, -0.5, 0.5)];
      for (let i = 0; i < NR - 1; i++) {
        const zc = -0.5 + (i + 1) / NR;
        const tooth = extrudeXY(dir > 0
          ? [[xc - 0.12, y + 0.03], [xc + 0.05, y - 0.004], [xc + 0.05, y - 0.01], [xc - 0.12, y + 0.004]]
          : [[xc + 0.12, y + 0.03], [xc + 0.12, y + 0.004], [xc - 0.05, y - 0.01], [xc - 0.05, y - 0.004]], zc - 0.012, zc + 0.012);
        g.push(tooth.index ? tooth.toNonIndexed() : tooth);
      }
      add(mergeGeometries(g.map((x) => (x.index ? x.toNonIndexed() : x)), false), M.comb);
    }
    // landing plates (the floor over each sprocket pit)
    add(box(X0 - 0.9, XB - 0.3, -0.04, 0.03, -0.79, 0.79), M.plate);
    this.topPlate = add(box(XT + 0.3, XS1 + 2.1, RISE - 0.04, RISE + 0.03, -0.79, 0.79), M.plate);
    // skirts, decking, glass, cladding
    const xsVis = range(XB - 0.25, XT + 0.25, 240), xsDeck = range(XA_RAIL, XB_RAIL, 260);
    for (const side of [-1, 1]) {
      const zs = side * 0.515;
      add(bandXY(xsVis, (x) => h(x) + 0.1, (x) => h(x) - 0.08, zs, side < 0), M.skirt, side > 0 ? this.near : this.root);
      add(stripXY(xsDeck, (x) => h(Math.max(XB, Math.min(XT, x))) + 0.1, side > 0 ? 0.515 : -0.79, side > 0 ? 0.79 : -0.515), M.skirt, side > 0 ? this.near : this.root);
    }
    const xsClad = range(X0 - 0.9, XS1 + 2.1, 300);
    const cladTop = (x: number) => (x < XA_RAIL || x > XB_RAIL ? h(Math.max(XB, Math.min(XT, x))) + 0.03 : h(Math.max(XB, Math.min(XT, x))) + 0.1);
    const cladBot = (x: number) => h(Math.max(XB, Math.min(XT + 2, x))) - 2.05;
    add(bandXY(xsClad, cladTop, cladBot, 0.79, true), M.clad, this.near);
    add(bandXY(xsClad, cladTop, cladBot, -0.79, false), M.cladIn);
    add(stripXY(xsClad, (x) => cladBot(x), -0.79, 0.79).scale(1, 1, 1), M.cladIn);
    add(box(XS1 + 2.08, XS1 + 2.1, RISE - 2.05, RISE, -0.79, 0.79), M.cladIn);
    add(box(X0 - 0.92, X0 - 0.9, -2.05, 0.0, -0.79, 0.79), M.cladIn);
    // glass balustrades (no ink, see-through) + their base channel
    const glass = new THREE.MeshBasicMaterial({ color: "#d8f0f4", transparent: true, opacity: 0.1, depthWrite: false, side: THREE.DoubleSide });
    for (const side of [-1, 1]) {
      const gm = new THREE.Mesh(bandXY(xsDeck, (x) => railY(x) - 0.03, (x) => h(Math.max(XB, Math.min(XT, x))) + 0.1, side * HR_Z, true), glass);
      gm.layers.set(NOINK); gm.renderOrder = 2; (side > 0 ? this.near : this.root).add(gm);
      add(railAlong(xsDeck.map((x) => [x, h(Math.max(XB, Math.min(XT, x))) + 0.16] as XY), side * HR_Z, 0.05, 0.06), M.steel, side > 0 ? this.near : this.root);
    }
    // handrails: one closed rubber loop per side (top run, round the newels, back through the truss)
    const loop = handrailLoop();
    this.hrLen = loop.length;
    const curve = new THREE.CatmullRomCurve3(loop.pts.map(([x, y]) => new THREE.Vector3(x, y, 0)), true, "centripetal");
    for (const side of [-1, 1]) {
      const t = rep(handrailTex(), Math.round(this.hrLen / 0.9), 1);
      this.hrTex.push(t);
      const m = lam("handrail" + side, () => ({ map: t })) as THREE.MeshLambertMaterial;
      this.hrMats.push(m);
      const tube = new THREE.Mesh(new THREE.TubeGeometry(curve, 900, 0.045, 10, true), m);
      tube.position.z = side * HR_Z; tube.castShadow = true; tube.receiveShadow = true;
      (side > 0 ? this.near : this.root).add(tube);
    }
    // the bottom pit (seen in cutaway): far wall, floor, end wall
    const pitX0 = X0 - 0.95, pitX1 = 5.2;
    add(new THREE.PlaneGeometry(pitX1 - pitX0, 2.3).translate((pitX0 + pitX1) / 2, -1.15, -0.8), M.pit, this.root, false);
    add(box(pitX0, 1.6, -2.3, -2.25, -0.8, 0.8), M.pit, this.root, false);
    add(box(pitX0 - 0.02, pitX0, -2.3, 0, -0.8, 0.8), M.pit, this.root, false);
    const slopeXs = range(1.6, pitX1, 40);
    add(stripXY(slopeXs, (x) => Math.min(0, h(x) - 2.25), -0.8, 0.8), M.pit, this.root, false);
  }

  update(t: number, fl: EscFlags) {
    // steps
    for (let k = 0; k < NSTEP; k++) {
      const p = poseAt(stepS(k, t));
      this.m4.makeRotationZ(p.th).setPosition(p.x, p.y, 0);
      for (const im of this.parts) im.setMatrixAt(k, this.m4);
    }
    for (const im of this.parts) im.instanceMatrix.needsUpdate = true;
    // step chain links between neighbouring axles
    for (let k = 0; k < NSTEP; k++) {
      const a = poseAt(stepS(k, t)), b = poseAt(stepS(k + 1, t));
      const L = Math.hypot(b.x - a.x, b.y - a.y), ang = Math.atan2(b.y - a.y, b.x - a.x);
      this.q.setFromEuler(this.e.set(0, 0, ang));
      for (const side of [0, 1]) {
        this.m4.compose(this.v3.set((a.x + b.x) / 2, (a.y + b.y) / 2, side ? Z_CHAIN : -Z_CHAIN), this.q, new THREE.Vector3(L, 1, 1));
        this.links.setMatrixAt(k * 2 + side, this.m4);
      }
    }
    this.links.instanceMatrix.needsUpdate = true;
    // sprockets turn with the chain; the drive gear with them, the motor sprocket faster
    const a = sprocketAngle(t) + 0.17;
    for (const g of [...this.sprTop, ...this.sprBot]) g.rotation.z = a;
    this.bigGear.rotation.z = a;
    this.motorSpr.rotation.z = a * (this.drive.r1 / this.drive.r2);
    // drive chain links ride round the belt path
    const P = this.drive.path, n = this.dlinks.count, off = ((SPEED / R) * this.drive.r1 * t) % P.L;
    for (let i = 0; i < n; i++) {
      const s = (((i / n) * P.L - off) % P.L + P.L) % P.L;
      const [x, y, ang] = alongPath(P, s);
      this.q.setFromEuler(this.e.set(0, 0, ang));
      this.m4.compose(this.v3.set(x, y, -0.74), this.q, this.one);
      this.dlinks.setMatrixAt(i, this.m4);
    }
    this.dlinks.instanceMatrix.needsUpdate = true;
    // handrails move with the steps
    for (const tx of this.hrTex) tx.offset.x = -(SPEED * t) / 0.9;
    // highlights (story beats): emissive pulses on the wheels and their tracks
    const glow = (m: THREE.MeshLambertMaterial, k: number, col: string) => m.emissive.set(col).multiplyScalar(Math.max(0, k) * 1.6);
    const fk = Math.max(0, fl.glowFront), rk = Math.max(0, fl.glowRear);
    this.front.color.set(fk > 0 ? "#ff7a00" : "#f08a2c").multiplyScalar(1 - 0.78 * Math.sqrt(rk)); this.rear.color.set(rk > 0 ? "#1f8fff" : "#3f8fd5").multiplyScalar(1 - 0.78 * Math.sqrt(fk));
    this.front.emissive.set("#ff5a00").multiplyScalar(0.45 * fk); this.rear.emissive.set("#0050ff").multiplyScalar(0.45 * rk);
    this.linkMat.emissive.set("#ffb020").multiplyScalar(Math.max(0, fl.glowChain) * 2.2); glow(lam("escMotor", () => ({})) as THREE.MeshLambertMaterial, fl.glowMotor, "#7dffb0");
    this.rails[0].emissive.set("#ff5a00").multiplyScalar(0.4 * Math.max(fl.glowTracks, fk * 0.6)); this.rails[1].emissive.set("#0050ff").multiplyScalar(0.4 * Math.max(fl.glowTracks, rk * 0.6));
    this.dMat.emissive.set("#ffb020").multiplyScalar(Math.max(0, fl.glowMotor) * 1.8);
    for (const m of this.hrMats) glow(m, Math.max(fl.glowRail, fl.glowMotor), "#ff5a3c");
    this.hrBelt.rotation.z = 0;
    for (const w of this.hrWheels) w.rotation.z = (SPEED * t) / 0.13;
    this.near.visible = !fl.cut;
    this.topPlate.visible = !fl.noTopPlate;
  }
}

/** closed belt round two circles (outer tangents), sampled; s = arc length */
function beltPath(c1: XY, r1: number, c2: XY, r2: number) {
  const dx = c2[0] - c1[0], dy = c2[1] - c1[1], d = Math.hypot(dx, dy), base = Math.atan2(dy, dx), al = Math.acos((r1 - r2) / d);
  const p: XY[] = [];
  // round circle 1 from (base + al) to (base - al) the long way (clockwise), then circle 2 the short way
  const a1s = base + al, a1e = base - al + TAU;
  for (let i = 0; i <= 80; i++) { const a = a1s + ((a1e - a1s) * i) / 80; p.push([c1[0] + r1 * Math.cos(a), c1[1] + r1 * Math.sin(a)]); }
  const a2s = base - al, a2e = base + al;
  for (let i = 0; i <= 30; i++) { const a = a2s + ((a2e - a2s) * i) / 30; p.push([c2[0] + r2 * Math.cos(a), c2[1] + r2 * Math.sin(a)]); }
  p.push(p[0]);
  const s = [0];
  for (let i = 1; i < p.length; i++) s.push(s[i - 1] + Math.hypot(p[i][0] - p[i - 1][0], p[i][1] - p[i - 1][1]));
  return { p, s, L: s[s.length - 1] };
}
function alongPath(P: { p: XY[]; s: number[]; L: number }, s: number): [number, number, number] {
  let i = 1; while (i < P.s.length - 1 && P.s[i] < s) i++;
  const a = P.p[i - 1], b = P.p[i], k = (s - P.s[i - 1]) / Math.max(1e-6, P.s[i] - P.s[i - 1]);
  return [a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k, Math.atan2(b[1] - a[1], b[0] - a[0])];
}
/** the handrail centre line: top run, round the top newel, down into the truss, back, round the bottom newel */
export function handrailLoop() {
  const pts: XY[] = [];
  for (const x of range(XA_RAIL, XB_RAIL, 160)) pts.push([x, railY(x)]);
  const ct: XY = [XB_RAIL, RISE + HR_UP - NEWEL_R];
  for (let i = 1; i < 16; i++) { const a = Math.PI / 2 - (i / 16) * Math.PI; pts.push([ct[0] + NEWEL_R * Math.cos(a), ct[1] + NEWEL_R * Math.sin(a)]); }
  pts.push([XB_RAIL, RISE + HR_UP - 2 * NEWEL_R]);
  const yr = (x: number) => h(x) - 0.75;
  pts.push([XB_RAIL - 0.35, RISE + 0.05]);
  for (const x of range(XT + 0.35, XB + 0.45, 120)) pts.push([x, yr(x)]);
  pts.push([XA_RAIL + 0.35, 0.05]);
  pts.push([XA_RAIL, HR_UP - 2 * NEWEL_R]);
  const cb: XY = [XA_RAIL, HR_UP - NEWEL_R];
  for (let i = 1; i < 16; i++) { const a = -Math.PI / 2 - (i / 16) * Math.PI; pts.push([cb[0] + NEWEL_R * Math.cos(a), cb[1] + NEWEL_R * Math.sin(a)]); }
  let L = 0; for (let i = 0; i < pts.length; i++) { const b = pts[(i + 1) % pts.length]; L += Math.hypot(b[0] - pts[i][0], b[1] - pts[i][1]); }
  return { pts, length: L };
}

// ---------------- 1898: the Harrods leather belt ----------------
export class Belt {
  root = new THREE.Group();
  private tex: THREE.Texture;
  private drums: THREE.Mesh[] = [];
  constructor(parent: THREE.Object3D) {
    parent.add(this.root);
    const ang = Math.atan2(HB.rise - 0.22, HB.x1 - HB.x0), len = Math.hypot(HB.x1 - HB.x0, HB.rise - 0.22);
    this.tex = rep(leatherTex(), len / 1.2, 1);
    this.tex.wrapS = this.tex.wrapT = THREE.RepeatWrapping;
    const belt = new THREE.Mesh(new THREE.PlaneGeometry(len, HB.w).rotateX(-Math.PI / 2), lam("leather", () => ({ map: this.tex })));
    belt.rotation.z = ang; belt.position.set((HB.x0 + HB.x1) / 2, (0.22 + HB.rise) / 2 + 0.004, HB.z);
    belt.receiveShadow = true; this.root.add(belt);
    const wood = lam("mahoganyHB", () => ({ map: rep(mahoganyTex(), 6, 1) }));
    const woodPlain = lam("mahoganyPlain", () => ({ color: "#6e3320" }));
    const brass = lam("brass", () => ({ color: "#d9a845" }));
    const add = (g: THREE.BufferGeometry, m: THREE.Material) => { const x = new THREE.Mesh(g, m); x.castShadow = true; x.receiveShadow = true; this.root.add(x); return x; };
    // the base under the belt: a solid wedge of mahogany panelling
    const zA = HB.z - HB.w / 2, zB = HB.z + HB.w / 2;
    add(extrudeXY([[HB.x0 - 0.3, 0], [HB.x1 + 0.2, 0], [HB.x1 + 0.2, HB.rise - 0.02], [HB.x1, HB.rise - 0.02], [HB.x0, 0.2], [HB.x0 - 0.3, 0.2]], zA - 0.02, zB + 0.02), woodPlain);
    // balustrades: panelled side walls rising with the belt, a brass rail on top, newel posts with brass knobs
    for (const z of [zA - 0.09, zB + 0.09]) {
      const top = (x: number) => beltY(x) + 0.95, bot = (x: number) => beltY(x) - 0.06;
      const xs = range(HB.x0 - 0.6, HB.x1 + 0.25, 40);
      const bx = (x: number) => Math.max(HB.x0, Math.min(HB.x1, x));
      add(extrudeXY([...xs.map((x) => [x, top(bx(x))] as XY), ...xs.slice().reverse().map((x) => [x, bot(bx(x)) - (x < HB.x0 ? 0.16 : 0)] as XY)], z - 0.08, z + 0.08), wood);
      const rail = range(HB.x0 - 0.65, HB.x1 + 0.3, 40).map((x) => new THREE.Vector3(x, top(bx(x)) + 0.05, z));
      add(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(rail), 80, 0.06, 10, false), brass);
      for (const x of [HB.x0 - 0.65, HB.x1 + 0.3]) {
        const y = top(bx(x));
        add(box(x - 0.12, x + 0.12, bot(bx(x)) - 0.25, y + 0.1, z - 0.12, z + 0.12), woodPlain);
        add(new THREE.SphereGeometry(0.11, 16, 10).translate(x, y + 0.2, z), brass);
      }
    }
    // the end drums the belt wraps round
    for (const [x, y] of [[HB.x0, 0.22], [HB.x1, HB.rise]] as const) {
      const d = add(cylZ(0.11, zA, zB, x, y - 0.11, 20), lam("drum", () => ({ color: "#4a3426" })));
      this.drums.push(d);
    }
  }
  update(t: number) {
    this.tex.offset.x = -(HB.speed * t) / 1.2;
  }
}
