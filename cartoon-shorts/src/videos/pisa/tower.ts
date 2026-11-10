// The bell tower of Pisa as a stack of storeys (ground floor with a blind arcade, six open galleries, the smaller
// belfry), posed every frame from story.ts towerAt(): storeys built (the working one grows), the lean about the
// high-side foot, the post-1272 storeys turned back (the banana), the timber scaffold, the weeds of the abandoned
// century, and the props around the foot: the soil slump, the wet ring, the 1990 barrier, the lead ingots, the
// extraction rig and its spoil heaps. Everything is two-tone lam() geometry, so the world ink outlines it.
import * as THREE from "three";
import { lam, boxGeo, V, Kit, kitClone } from "./build";
import { ctex, stoneHD, rep } from "./paint";
import { twoTone } from "./shade";
import { TOWER, TR, GAL_H, BELL_R, CURVE, D0, storeyH, TowerState, DRILL, BORE } from "./story";

const TAU = Math.PI * 2;
const GAL_COLS = 16;
/** marble: warm white courses (the shade term turns the shaded side a cool lilac-grey, so the albedo stays warm) */
const marble = () => lam("marbleHD", () => ({ map: rep(stoneHD("marbleHD", ["#f2ebdc", "#ece3d2", "#f6f0e4", "#e7ddca"], "#cbbfa9"), 3, 1) }));
const marbleIn = () => lam("marbleIn", () => ({ color: "#cfc3ae" }));
const trim = () => lam("marbleTrim", () => ({ color: "#f6efe2" }));
const floorM = () => lam("galleryFloor", () => ({ color: "#bfb29b" }));

/** arcade band: marble with round-headed openings cut out (alphaTest), one arch per tile */
const archTex = (key: string, open = true) => ctex(key, 256, 256, (g) => {
  g.fillStyle = "#f1e9da"; g.fillRect(0, 0, 256, 256);
  g.fillStyle = "rgba(120,100,80,0.18)"; g.fillRect(0, 0, 256, 10);
  // the arch: round head + jambs; open arches are cut through, blind ones painted as a shallow recess
  g.save();
  g.beginPath(); g.moveTo(44, 256); g.lineTo(44, 120); g.arc(128, 120, 84, Math.PI, 0); g.lineTo(212, 256); g.closePath();
  // open arches are painted as the shadowed gallery behind (solid: cut-out alpha edges crawled frame to frame)
  g.fillStyle = open ? "#5d566c" : "#d9cdb8"; g.fill();
  g.restore();
  // arch moulding: a darker voussoir ring
  g.strokeStyle = "rgba(90,72,58,0.55)"; g.lineWidth = 7;
  g.beginPath(); g.arc(128, 120, 90, Math.PI, 0); g.stroke();
  g.strokeStyle = "rgba(255,250,240,0.6)"; g.lineWidth = 3;
  g.beginPath(); g.arc(128, 120, 96, Math.PI, 0); g.stroke();
});
const archMat = (key: string, n: number, open: boolean) => {
  const m = lam(key, () => ({ map: rep(archTex(key + "T", open), n, 1), side: THREE.DoubleSide }));
  return m;
};

/** open-ended cylinder shell (outward normals), uv u = around, v = up */
const shell = (r: number, y0: number, y1: number, seg = 64) => {
  const g = new THREE.CylinderGeometry(r, r, y1 - y0, seg, 1, true);
  g.translate(0, (y0 + y1) / 2, 0);
  return g;
};
const ring = (r0: number, r1: number, y: number, seg = 64) => {
  const g = new THREE.RingGeometry(r0, r1, seg, 1); g.rotateX(-Math.PI / 2); g.translate(0, y, 0); return g;
};
const disk = (r: number, y: number, seg = 64) => { const g = new THREE.CircleGeometry(r, seg); g.rotateX(-Math.PI / 2); g.translate(0, y, 0); return g; };

const mesh = (g: THREE.BufferGeometry, m: THREE.Material, parent: THREE.Object3D) => {
  const x = new THREE.Mesh(g, m); x.castShadow = true; x.receiveShadow = true; parent.add(x); return x;
};

/** one storey's geometry in its own group (origin = centre of the storey's floor) */
const storey = (k: number) => {
  const g = new THREE.Group(), h = storeyH(k);
  if (k === 0) {
    mesh(shell(TR - 0.35, 0, h), marble(), g);
    mesh(new THREE.CylinderGeometry(TR + 0.55, TR + 0.7, 0.9, 64).translate(0, 0.45, 0), trim(), g); // plinth
    mesh(shell(TR - 0.05, 1.6, h - 0.9), archMat("blindArch", 15, false), g);                         // blind arcade
    for (let i = 0; i < 15; i++) {                                                                     // half columns
      const a = (i / 15) * TAU;
      mesh(new THREE.CylinderGeometry(0.32, 0.36, h - 2.4, 12).translate(Math.cos(a) * (TR - 0.05), 0.9 + (h - 2.4) / 2, Math.sin(a) * (TR - 0.05)), trim(), g);
    }
  } else if (k < 7) {
    mesh(shell(TR - 1.7, 0, h), marbleIn(), g);                     // inner wall seen through the arches
    mesh(ring(TR - 1.7, TR + 0.1, 0.02), floorM(), g);             // gallery floor
    // 16 stout columns per gallery (the real tower has 30): at a distance 30 thin ones were 2-3 px wide and their ink
    // outlines broke into dashes that changed every frame
    mesh(shell(TR + 0.02, h - 1.55, h - 0.35), archMat("galArch", GAL_COLS, true), g); // arch band
    for (let i = 0; i < GAL_COLS; i++) {                           // columns
      const a = ((i + 0.5) / GAL_COLS) * TAU;
      mesh(new THREE.CylinderGeometry(0.36, 0.42, h - 1.5, 14).translate(Math.cos(a) * (TR - 0.2), 0.1 + (h - 1.5) / 2, Math.sin(a) * (TR - 0.2)), trim(), g);
    }
    mesh(new THREE.CylinderGeometry(TR - 0.2, TR - 0.2, 0.22, 64).translate(0, 0.11, 0), trim(), g); // base course
  } else {
    mesh(shell(BELL_R - 1.0, 0, h), marbleIn(), g);
    mesh(ring(BELL_R - 1.0, BELL_R + 0.1, 0.02), floorM(), g);
    mesh(shell(BELL_R + 0.02, 1.0, h - 0.6), archMat("bellArch", 12, true), g);
    for (let i = 0; i < 12; i++) {
      const a = ((i + 0.5) / 12) * TAU;
      mesh(new THREE.CylinderGeometry(0.22, 0.26, h - 0.8, 10).translate(Math.cos(a) * (BELL_R - 0.1), 0.2 + (h - 0.8) / 2, Math.sin(a) * (BELL_R - 0.1)), trim(), g);
    }
    mesh(new THREE.CylinderGeometry(BELL_R + 0.35, BELL_R + 0.35, 0.5, 48).translate(0, h, 0), trim(), g); // cap
    mesh(disk(BELL_R + 0.35, h + 0.26), floorM(), g);
  }
  // cornice: the projecting course at the top of every storey (the belfry has its cap)
  if (k < 7) mesh(new THREE.CylinderGeometry(TR + 0.38, TR + 0.3, 0.45, 64).translate(0, h - 0.22, 0), trim(), g);
  if (k === 6) mesh(disk(TR + 0.38, h + 0.01), floorM(), g); // the terrace round the belfry
  return g;
};

/** timber scaffold round the working storey (rebuilt in place per frame by visibility only) */
const scaffold = () => {
  const g = new THREE.Group(), wood = lam("scaffoldWood", () => ({ color: "#9a6a42" }));
  for (let i = 0; i < 18; i++) {
    const a = (i / 18) * TAU, r = TR + 1.3;
    mesh(boxGeo(V(Math.cos(a) * r - 0.09, -1.5, Math.sin(a) * r - 0.09), V(Math.cos(a) * r + 0.09, 7.5, Math.sin(a) * r + 0.09)), wood, g);
  }
  for (const y of [1.6, 4.6]) mesh(new THREE.TorusGeometry(TR + 1.3, 0.08, 6, 54).rotateX(Math.PI / 2).translate(0, y, 0), wood, g);
  mesh(ring(TR + 0.3, TR + 1.5, 4.6, 54), lam("planksScaffold", () => ({ color: "#b98455", side: THREE.DoubleSide })), g);
  return g;
};

export class Tower {
  root = new THREE.Group();       // positioned at the pivot (high-side foot), turned by the lean
  private st: THREE.Group[] = [];
  private scaf: THREE.Group;
  private weeds: THREE.Object3D[] = [];
  private slump: THREE.Mesh; private wetRing: THREE.Mesh;
  private fence = new THREE.Group();
  private lead: THREE.InstancedMesh;
  private collar: THREE.Mesh;
  private rig = new THREE.Group(); private auger: THREE.Mesh; private augerTex: THREE.Texture;
  private spoil: THREE.Mesh[] = [];
  static LEAD_N = 60;

  constructor(parent: THREE.Object3D, kit: Kit) {
    const pivot = V(TOWER[0] + TR, D0, TOWER[2]);
    this.root.position.copy(pivot);
    parent.add(this.root);
    let prev: THREE.Object3D = this.root;
    for (let k = 0; k < 8; k++) {
      const s = storey(k);
      if (k === 0) s.position.set(-TR, 0, 0); else s.position.set(0, storeyH(k - 1), 0);
      prev.add(s); this.st.push(s); prev = s;
    }
    this.scaf = scaffold(); this.root.add(this.scaf);
    // weeds and a sapling on the abandoned stub (top of storey 2)
    const top = this.st[2];
    for (const [name, x, z, h] of [["grass_large", 6.2, 1.5, 0.9], ["grass_large", -5.5, 3.6, 0.8], ["flower_yellowA", 4.6, -4.8, 0.6], ["flower_redA", -3.2, -6.0, 0.6],
      ["grass", 0.8, 6.9, 0.7], ["flower_purpleA", -6.6, -1.4, 0.6], ["tree_default", 5.2, 4.4, 3.4], ["plant_bush", -4.5, 5.6, 1.1]] as const) {
      const o = kitClone(kit, name, h);
      if (!o) continue;
      o.position.set(x, GAL_H + 0.25, z); top.add(o); this.weeds.push(o);
    }
    // the low side's soil slump (dark mud pushed up round the sunken foot) and the wet ring of the squeezed clay
    const mud = lam("mudSlump", () => ({ color: "#7a5a40" }));
    this.slump = new THREE.Mesh(new THREE.SphereGeometry(1, 32, 12, 0, TAU, 0, Math.PI / 2), mud);
    this.slump.position.set(TOWER[0] - TR + 0.4, D0 - 0.05, TOWER[2]); this.slump.receiveShadow = true;
    parent.add(this.slump);
    const wetM = twoTone(new THREE.MeshLambertMaterial({ color: "#6d6f6a", transparent: true, opacity: 0, depthWrite: false }));
    this.wetRing = new THREE.Mesh(new THREE.RingGeometry(TR + 0.6, TR + 6.5, 64, 1).rotateX(-Math.PI / 2), wetM);
    this.wetRing.position.set(TOWER[0], D0 + 0.03, TOWER[2]); this.wetRing.renderOrder = 0.4;
    parent.add(this.wetRing);
    // 1990 barrier: posts and red/white tape round the foot
    const post = lam("fencePost", () => ({ color: "#e9e4da" }));
    const tape = lam("tape", () => ({ map: ctex("tapeTex", 256, 32, (g) => { for (let i = 0; i < 8; i++) { g.fillStyle = i % 2 ? "#f4f1ea" : "#d23b3b"; g.fillRect(i * 32, 0, 32, 32); } }), side: THREE.DoubleSide }));
    const FR = TR + 4.6;
    for (let i = 0; i < 22; i++) {
      const a = (i / 22) * TAU;
      mesh(new THREE.CylinderGeometry(0.06, 0.07, 1.15, 8).translate(Math.cos(a) * FR, 0.575, Math.sin(a) * FR), post, this.fence);
    }
    for (const y of [0.72, 1.05]) {
      const t = shell(FR, y - 0.05, y + 0.05, 88);
      const uv = t.attributes.uv as THREE.BufferAttribute; for (let i = 0; i < uv.count; i++) uv.setX(i, uv.getX(i) * 40);
      mesh(t, tape, this.fence);
    }
    this.fence.position.set(TOWER[0], D0, TOWER[2]);
    parent.add(this.fence);
    // lead ingots: 5 layers of 3 x 4 on a concrete collar at the high side's foot
    const leadM = twoTone(new THREE.MeshPhongMaterial({ color: "#5c6170", specular: "#9aa0ad", shininess: 40 }), 0.15);
    this.lead = new THREE.InstancedMesh(new THREE.BoxGeometry(0.95, 0.42, 0.62), leadM, Tower.LEAD_N);
    this.lead.castShadow = true; this.lead.receiveShadow = true; this.lead.frustumCulled = false;
    parent.add(this.lead);
    this.collar = new THREE.Mesh(new THREE.BoxGeometry(4.4, 0.35, 4.2), lam("concrete", () => ({ color: "#c9c5bd" })));
    this.collar.position.set(TOWER[0] + TR + 2.6, D0 + 0.17, TOWER[2]); this.collar.castShadow = true; this.collar.receiveShadow = true;
    parent.add(this.collar);
    // extraction rig: tracked yellow base, an inclined mast and the auger boring under the high side
    const yel = lam("rigYellow", () => ({ color: "#e8b02e" })), dark = lam("rigDark", () => ({ color: "#3d414c" }));
    mesh(boxGeo(V(-1.4, 0.0, -1.0), V(1.4, 0.55, 1.0)), dark, this.rig);
    mesh(boxGeo(V(-1.2, 0.55, -0.85), V(1.2, 1.9, 0.85)), yel, this.rig);
    mesh(boxGeo(V(0.2, 1.9, -0.6), V(1.1, 2.7, 0.6)), lam("rigCab", () => ({ color: "#8fb7d6" })), this.rig);
    // the mast leans away from the tower so the auger bores down and in, under the high side's foot
    const mast = new THREE.Group(); mast.position.set(-1.4, 1.2, 0); mast.rotation.z = -0.55; this.rig.add(mast);
    mesh(boxGeo(V(-0.18, -0.2, -0.18), V(0.18, 5.2, 0.18)), yel, mast);
    this.augerTex = ctex("augerTex", 64, 256, (g) => {
      g.fillStyle = "#9aa0aa"; g.fillRect(0, 0, 64, 256);
      g.strokeStyle = "#4a4f5a"; g.lineWidth = 10;
      for (let i = -2; i < 8; i++) { g.beginPath(); g.moveTo(0, i * 40); g.lineTo(64, i * 40 + 32); g.stroke(); }
    });
    const augM = twoTone(new THREE.MeshLambertMaterial({ map: rep(this.augerTex, 1, 6) }));
    this.auger = mesh(new THREE.CylinderGeometry(0.17, 0.17, 6.4, 16).translate(0, -1.6, 0), augM, mast);
    this.auger.position.set(0.35, 0, 0);
    this.rig.position.set(DRILL[0], D0, DRILL[2]); this.rig.rotation.y = -0.42;
    const hole = new THREE.Mesh(new THREE.CircleGeometry(0.55, 24).rotateX(-Math.PI / 2), lam("boreHole", () => ({ color: "#2e2420" })));
    hole.position.set(BORE[0], D0 + 0.03, BORE[2]); this.rig.userData.hole = hole; parent.add(hole);
    parent.add(this.rig);
    const soil = lam("spoil", () => ({ color: "#8a6748" }));
    for (const [x, z, s] of [[BORE[0] - TOWER[0] + 1.1, BORE[2] - TOWER[2] - 1.5, 1.7], [BORE[0] - TOWER[0] + 2.6, BORE[2] - TOWER[2] + 0.4, 1.3], [BORE[0] - TOWER[0] - 0.6, BORE[2] - TOWER[2] + 2.0, 1.1]] as const) {
      const c = new THREE.Mesh(new THREE.ConeGeometry(1.3 * s, 1.1 * s, 20), soil);
      c.position.set(TOWER[0] + x, D0, TOWER[2] + z); c.castShadow = true; c.receiveShadow = true;
      parent.add(c); this.spoil.push(c);
    }
  }

  update(s: TowerState, t: number) {
    this.root.rotation.z = ((s.lean + s.topple) * Math.PI) / 180;
    const n = Math.max(0, s.storeys);
    for (let k = 0; k < 8; k++) {
      const g = this.st[k], frac = Math.min(1, Math.max(0, n - k));
      g.visible = frac > 0.001;
      g.scale.y = Math.max(0.001, frac);
      if (k > 0) g.position.y = storeyH(k - 1);
      g.rotation.z = s.curve && k >= 3 ? -(CURVE * Math.PI) / 180 : 0;
    }
    // a growing storey squashes only itself: the storeys above it are hidden until it is complete
    // the scaffold rides on the working storey
    const work = Math.min(7, Math.floor(n));
    this.scaf.visible = s.scaffold && n < 8;
    if (this.scaf.visible) {
      let y = 0; for (let k = 0; k < work; k++) y += storeyH(k);
      this.scaf.position.set(-TR, y, 0);
      this.scaf.scale.set(1, 1, 1);
    }
    this.weeds.forEach((o, i) => { const w = Math.max(0, Math.min(1, s.weeds * 1.3 - i * 0.06)); o.visible = w > 0.02 && n >= 3 && n < 3.01; o.scale.setScalar(Math.max(0.001, w)); });
    this.slump.visible = s.sink > 0.01 && s.topple === 0;
    this.slump.scale.set(3.2 * s.sink, 0.55 * s.sink, 5.2 * s.sink);
    (this.wetRing.material as THREE.MeshLambertMaterial).opacity = 0.55 * s.wet;
    this.wetRing.visible = s.wet > 0.01;
    this.fence.visible = s.fence > 0.5;
    // lead: bottom layer first, 3 across x 4 along z per layer
    const nb = Math.round(s.lead * Tower.LEAD_N), m4 = new THREE.Matrix4(), q = new THREE.Quaternion();
    for (let i = 0; i < Tower.LEAD_N; i++) {
      const layer = Math.floor(i / 12), j = i % 12, ix = j % 3, iz = Math.floor(j / 3);
      const on = i < nb, sc = on ? 1 : 0.0001;
      m4.compose(V(TOWER[0] + TR + 1.4 + ix * 1.0, D0 + 0.35 + 0.21 + layer * 0.43, TOWER[2] - 1.0 + iz * 0.66 - 0.0), q, V(sc, sc, sc));
      this.lead.setMatrixAt(i, m4);
    }
    this.lead.instanceMatrix.needsUpdate = true;
    this.lead.visible = s.lead > 0.001;
    this.collar.visible = s.lead > 0.001 || s.fence > 0.5;
    this.rig.visible = s.spoil > 0.001 || s.drill > 0.5;
    (this.rig.userData.hole as THREE.Mesh).visible = this.rig.visible;
    this.auger.rotation.y = s.drill > 0.5 ? t * 9 : 0;
    this.augerTex.offset.y = s.drill > 0.5 ? -t * 1.5 : 0;
    this.spoil.forEach((c, i) => { const k = Math.max(0, Math.min(1, s.spoil * 1.4 - i * 0.2)); c.visible = k > 0.01; c.scale.setScalar(Math.max(0.001, k)); });
  }
}
