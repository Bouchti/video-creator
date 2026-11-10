// The whole Emu War film as one three.js scene: sky, the wheat farm with the army camp and the dam, the open plain,
// the minister's office, parliament and the floorboards of the marbles.
// update(id, f, camera) poses everything for shot `id` at frame f (a pure function of id + f).
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { staticFile } from "remotion";
import { V, Kit, kitClone } from "./build";
import { cloudHD, ctex } from "./paint";
import { LIGHTS, LOOK, LightPreset } from "./lights";
import { TONE, CHAR, untone } from "./shade";
import { NOINK } from "./ink";
import { Pool, Actor, Fx, stage, WIDE, BODY } from "./cast";
import { FPS, SHOTS, camAt, V3, FOREGROUND, ShotDef, truckAt, HOOK_GUN, LINE, LINE_Z, CAMERA_AT, DAM_GUN, BRASS, BRASS_H, DESK_AT, DROP_AT, smooth, LOOKOUT } from "./story";
import { Farm, Wheat, Office, Parliament, Floor, Truck, lewisGun, movieCamera, crates, brassPile, box } from "./outback";
import { lam } from "./build";

// ---------------- assets ----------------
const KENNEY = ["tree_oak", "tree_default", "tree_detailed", "tree_fat", "tree_cone", "tree-high-round", "tree", "plant_bushLarge", "plant_bushDetailed",
  "plant_bush", "hedge", "flower_redA", "flower_yellowA", "flower_purpleA", "lantern", "stall-bench", "banner-red", "banner-green", "stall-red", "stall-green"];
let kitP: Promise<Kit> | null = null;
export const loadKit = () => {
  if (!kitP) {
    const loader = new GLTFLoader();
    kitP = Promise.all(KENNEY.map((n) => loader.loadAsync(staticFile(`bridge/kenney/${n}.glb`)).then((g) => [n, g.scene] as const).catch(() => [n, null] as const)))
      .then((list) => Object.fromEntries(list.filter((e) => e[1]).map(([n, s]) => [n, s!])) as Kit);
  }
  return kitP;
};

const discTex = () => ctex("sunDisc", 128, 128, (g) => {
  const gr = g.createRadialGradient(64, 64, 58, 64, 64, 64); gr.addColorStop(0, "rgba(255,255,255,1)"); gr.addColorStop(1, "rgba(255,255,255,0)");
  g.fillStyle = gr; g.fillRect(0, 0, 128, 128);
});
const haloTex = () => ctex("sunHalo", 256, 256, (g) => {
  const im = g.createImageData(256, 256);
  for (let y = 0; y < 256; y++) for (let x = 0; x < 256; x++) {
    const u = Math.hypot(x - 127.5, y - 127.5) / 128;
    const a = (0.55 * Math.exp(-((u / 0.25) ** 2)) + 0.35 * Math.exp(-((u / 0.6) ** 2))) * (1 - Math.min(1, Math.max(0, (u - 0.8) / 0.2)));
    const i = (y * 256 + x) * 4; im.data[i] = im.data[i + 1] = im.data[i + 2] = 255; im.data[i + 3] = Math.round(255 * Math.min(1, a));
  }
  g.putImageData(im, 0, 0);
});

type Mats = Record<string, THREE.Material>;

export class World {
  root = new THREE.Group();
  private pool = new Pool();
  private actors: Actor[] = [];
  private fxs: Fx[] = [];
  private hemi: THREE.HemisphereLight; private sun: THREE.DirectionalLight; private fill: THREE.DirectionalLight;
  private sky: THREE.Mesh; private skyMat: THREE.ShaderMaterial;
  private fog = new THREE.Fog("#bccbec", 25, 420);
  private sunDisc: THREE.Sprite; private sunHalo: THREE.Sprite;
  private sunCache = new Map<number, THREE.Vector3>();
  private shadowCache = new Map<number, number>();
  private cloudMaps: Record<string, THREE.Texture[]>;
  private fgs: { o: THREE.Object3D; a: number; b: number }[] = [];
  private clouds: THREE.Mesh[] = [];
  private cloudHome: THREE.Vector3[] = [];
  private farm: Farm; private truck: Truck; private floor: Floor;
  private hookGun = lewisGun(true); private lineGuns = new THREE.Group(); private crates = crates(8); private damGun = lewisGun(true, 1.0);
  private brass = new THREE.Group(); private cam = movieCamera(); private table = new THREE.Group();
  private frustum = new THREE.Frustum();
  private m4 = new THREE.Matrix4(); private v = new THREE.Vector3(); private sph = new THREE.Sphere();

  constructor(kit: Kit) {
    const R = this.root;
    // ---- sky + light ----
    this.skyMat = new THREE.ShaderMaterial({
      uniforms: { c0: { value: new THREE.Color() }, c1: { value: new THREE.Color() }, c2: { value: new THREE.Color() },
        c3: { value: new THREE.Color() }, c4: { value: new THREE.Color() }, e: { value: new THREE.Vector4() } },
      vertexShader: "varying vec3 vP; void main(){ vP = normalize(position); gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }",
      fragmentShader: `uniform vec3 c0, c1, c2, c3, c4; uniform vec4 e; varying vec3 vP;
        void main(){ float el = asin(clamp(normalize(vP).y, -1.0, 1.0));
          vec3 c = mix(c0, c1, smoothstep(0.0, e.x, el));
          c = mix(c, c2, smoothstep(e.x, e.y, el));
          c = mix(c, c3, smoothstep(e.y, e.z, el));
          c = mix(c, c4, smoothstep(e.z, e.w, el));
          gl_FragColor = vec4(c, 1.0); }`,
      side: THREE.BackSide, depthWrite: false, fog: false,
    });
    this.sky = new THREE.Mesh(new THREE.SphereGeometry(1100, 48, 24), this.skyMat);
    this.sky.renderOrder = -1; this.sky.frustumCulled = false; this.sky.layers.set(NOINK);
    R.add(this.sky);
    this.sunDisc = new THREE.Sprite(new THREE.SpriteMaterial({ map: discTex(), color: new THREE.Color(6.0, 4.4, 2.4), fog: false, depthWrite: false }));
    this.sunHalo = new THREE.Sprite(new THREE.SpriteMaterial({ map: haloTex(), color: new THREE.Color(1, 1, 1), fog: false, depthWrite: false, depthTest: true,
      transparent: true, blending: THREE.AdditiveBlending }));
    this.sunDisc.renderOrder = -0.5; this.sunHalo.renderOrder = 5;
    for (const m of [this.sunDisc, this.sunHalo]) { m.frustumCulled = false; m.layers.set(NOINK); R.add(m); }
    this.hemi = new THREE.HemisphereLight("#cfe6ff", "#6c5c8c", 1.1);
    this.sun = new THREE.DirectionalLight("#fff0d6", 2.6);
    this.sun.castShadow = true;
    this.sun.shadow.mapSize.set(4096, 4096);
    this.fill = new THREE.DirectionalLight("#9fb8ff", 0.35);
    R.add(this.hemi, this.sun, this.sun.target, this.fill, this.fill.target);
    const dayC = [0, 1, 2, 3].map((k) => cloudHD(k, LOOK.day.cloud));
    this.cloudMaps = { day: dayC, yellow: dayC, lab: dayC, night: dayC, golden: [0, 1, 2, 3].map((k) => cloudHD(k, LOOK.golden.cloud)) };
    for (let i = 0; i < 9; i++) {
      const a = (i / 9) * Math.PI * 2 + 0.3, d = 620 + (i % 3) * 60;
      const m = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), new THREE.MeshBasicMaterial({ map: this.cloudMaps.day[i % 4], color: new THREE.Color(1.1, 1.1, 1.1), transparent: true, depthWrite: false, fog: false }));
      const w = 130 + (i % 4) * 30;
      m.position.set(Math.cos(a) * d, 120 + (i % 4) * 38, Math.sin(a) * d); m.scale.set(w, w / 2, 1);
      m.layers.set(NOINK);
      this.clouds.push(m); this.cloudHome.push(m.position.clone()); R.add(m);
    }

    // ---- the sets ----
    this.farm = new Farm(R);
    new Wheat(R, [[-20, 20, -34, -6.3], [LOOKOUT[0] - 14, LOOKOUT[0] + 12, LOOKOUT[2] - 16, LOOKOUT[2] + 8]]);
    new Office(R);
    new Parliament(R);
    this.floor = new Floor(R);
    this.truck = new Truck(R, true);
    // the props, shown per shot
    this.hookGun.position.set(...HOOK_GUN); this.hookGun.rotation.y = Math.PI / 2; R.add(this.hookGun);
    for (const dx of [-0.35, 0.35]) { const g = lewisGun(false); g.position.set(LINE.guns + dx, 0, LINE_Z + 0.1); g.rotation.y = Math.PI / 2 - 0.2; g.scale.setScalar(1.5); this.lineGuns.add(g); }
    R.add(this.lineGuns);
    this.crates.position.set(LINE.crates, 0, LINE_Z - 0.1); R.add(this.crates);
    this.damGun.position.set(...DAM_GUN); R.add(this.damGun);
    this.brass.add(brassPile(BRASS[0], BRASS[2], 2.6, BRASS_H, 2600));
    const bg = lewisGun(false); bg.position.set(BRASS[0] + 0.25, BRASS_H - 0.12, BRASS[2]); this.brass.add(bg); R.add(this.brass);
    this.cam.position.set(...CAMERA_AT); this.cam.rotation.y = -0.15; R.add(this.cam);
    const wood = lam("campTable", () => ({ color: "#9a7048" }));
    const tb = new THREE.Mesh(box(DESK_AT[0] - 0.6, DESK_AT[0] + 0.6, 0.72, 0.77, DESK_AT[2] - 0.4, DESK_AT[2] + 0.3), wood); tb.castShadow = tb.receiveShadow = true; this.table.add(tb);
    for (const [dx, dz] of [[-0.55, -0.35], [0.55, -0.35], [-0.55, 0.25], [0.55, 0.25]]) this.table.add(new THREE.Mesh(box(DESK_AT[0] + dx - 0.03, DESK_AT[0] + dx + 0.03, 0, 0.72, DESK_AT[2] + dz - 0.03, DESK_AT[2] + dz + 0.03), wood));
    const lamp = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.09, 0.25, 12).translate(DESK_AT[0] - 0.4, 0.9, DESK_AT[2] - 0.1), lam("hurricane", () => ({ color: "#b8332e" })));
    this.table.add(lamp); R.add(this.table);
    for (const fg of FOREGROUND) {
      const o = kitClone(kit, fg.kit, fg.s ?? 1);
      if (!o) continue;
      o.position.set(...fg.pos); o.rotation.y = fg.yaw ?? 0; o.visible = false;
      this.fgs.push({ o, a: fg.a, b: fg.b }); R.add(o);
    }
  }

  /** camera-relative sun, frozen per shot: the shot's mean view direction turned by az toward screen right, lifted by el */
  private shotSun(id: number, s: ShotDef, L: LightPreset) {
    let v = this.sunCache.get(id);
    if (v) return v;
    let fx = 0, fz = 0;
    for (let f = s.a; f < s.b; f += 3) {
      const c = camAt(id, f), x = c.look[0] - c.pos[0], z = c.look[2] - c.pos[2], n = Math.hypot(x, z) || 1;
      fx += x / n; fz += z / n;
    }
    const n = Math.hypot(fx, fz) || 1; fx /= n; fz /= n;
    const az = THREE.MathUtils.degToRad(s.sunAz ?? L.az), el = THREE.MathUtils.degToRad(s.sunEl ?? L.el);
    const hx = fx * Math.cos(az) - fz * Math.sin(az), hz = fz * Math.cos(az) + fx * Math.sin(az);
    v = new THREE.Vector3(hx * Math.cos(el), Math.sin(el), hz * Math.cos(el)).normalize();
    this.sunCache.set(id, v);
    return v;
  }
  private shadowR(id: number, s: ShotDef) {
    let r = this.shadowCache.get(id);
    if (r === undefined) {
      r = 12;
      for (let f = s.a; f < s.b; f += 2) {
        const c = camAt(id, f), d = Math.hypot(c.look[0] - c.pos[0], c.look[1] - c.pos[1], c.look[2] - c.pos[2]);
        r = Math.max(r, THREE.MathUtils.clamp(d * 1.15 + 7, 12, 95));
      }
      this.shadowCache.set(id, r);
    }
    return r;
  }
  private actor(i: number) { while (this.actors.length <= i) this.actors.push(new Actor(this.root)); return this.actors[i]; }
  private fx(i: number) { while (this.fxs.length <= i) this.fxs.push(new Fx(this.root)); return this.fxs[i]; }

  update(id: number, f: number, cam: THREE.PerspectiveCamera, scene: THREE.Scene) {
    const t = f / FPS, s = SHOTS[id - 1], L = LIGHTS[s.light];
    const c = camAt(id, f);
    cam.position.set(...c.pos); cam.up.set(0, 1, 0); cam.lookAt(...c.look); cam.rotateZ(c.roll);
    cam.fov = c.fov; cam.near = THREE.MathUtils.clamp(0.09 * Math.hypot(c.look[0] - c.pos[0], c.look[1] - c.pos[1], c.look[2] - c.pos[2]), 0.05, 1.0); cam.far = 1500; cam.updateProjectionMatrix(); cam.updateMatrixWorld();
    const focus = V(...c.look);
    cam.layers.enable(NOINK);
    // ---- light rig: camera-relative sun frozen per shot, two-tone uniforms, shadow fit ----
    const K = LOOK[s.light], sunDir = this.shotSun(id, s, L);
    this.hemi.color.set(L.sky); this.hemi.groundColor.set(L.ground); this.hemi.intensity = L.hemiI;
    this.sun.color.set(L.sunCol); this.sun.intensity = L.sunI;
    let Rr = this.shadowR(id, s);
    if (s.light === "golden") Rr = Math.max(Rr, 30);
    const texel = (2 * Rr) / this.sun.shadow.mapSize.x;
    const lr = this.v.set(0, 1, 0).cross(sunDir).normalize().clone(), lu = sunDir.clone().cross(lr).normalize();
    const fr2 = Math.round(focus.dot(lr) / texel) * texel, fu = Math.round(focus.dot(lu) / texel) * texel, fd = focus.dot(sunDir);
    const snapped = lr.multiplyScalar(fr2).addScaledVector(lu, fu).addScaledVector(sunDir, fd);
    this.sun.position.copy(snapped).addScaledVector(sunDir, 220); this.sun.target.position.copy(snapped);
    const sc = this.sun.shadow.camera;
    sc.left = -Rr; sc.right = Rr; sc.top = Rr; sc.bottom = -Rr; sc.near = 20; sc.far = 480; sc.updateProjectionMatrix();
    this.sun.shadow.bias = L.bias; this.sun.shadow.normalBias = L.normalBias * (Rr / 12);
    this.fill.intensity = 0;
    TONE.uLitCol.value.set(...L.lit); TONE.uShadeCol.value.set(...L.shade); TONE.uShadeLift.value.set(...L.lift);
    TONE.uLambert.value = L.lambert; TONE.uSideK.value = L.sideK; TONE.uTerm.value = L.term; TONE.uBounce.value.set(...LOOK[s.light].bounce); TONE.uSat.value = LOOK[s.light].sat;
    CHAR.uCharTint.value.set(...L.charTint); CHAR.uCharShade.value = L.charShade; CHAR.uGrad.value = L.charGrad;
    CHAR.uBodyGrad.value = L.bodyGrad; CHAR.uSideTint.value.set(...L.sideTint);
    // ---- sky, fog, sun disc + halo, clouds ----
    const su = this.skyMat.uniforms;
    K.sky.c.forEach((hx, i) => untone(hx, su["c" + i].value));
    const e = K.sky.e.map((deg) => THREE.MathUtils.degToRad(deg));
    su.e.value.set(e[1], e[2], e[3], e[4]);
    this.sky.position.copy(cam.position);
    untone(L.fog, this.fog.color); this.fog.near = L.fogNear; this.fog.far = L.fogFar;
    if (s.fog) { this.fog.near = s.fog[0]; this.fog.far = s.fog[1]; }
    scene.fog = this.fog; scene.background = null;
    const showSun = s.light === "golden";
    this.sunDisc.visible = this.sunHalo.visible = showSun;
    if (showSun) {
      this.sunDisc.position.copy(cam.position).addScaledVector(sunDir, 900);
      this.sunDisc.scale.setScalar(2 * 900 * Math.tan(THREE.MathUtils.degToRad(1.7)));
      this.sunHalo.position.copy(this.sunDisc.position); this.sunHalo.scale.setScalar(2 * 900 * Math.tan(THREE.MathUtils.degToRad(24)));
      (this.sunHalo.material as THREE.SpriteMaterial).color.set(L.sunDisc).multiplyScalar(1.3);
    }
    for (let i = 0; i < this.clouds.length; i++) {
      const m = this.clouds[i], mat = m.material as THREE.MeshBasicMaterial, hm = this.cloudHome[i], a = Math.atan2(hm.z, hm.x) + t * 0.6 * 0.004;
      const dd = Math.hypot(hm.x, hm.z);
      m.position.set(Math.cos(a) * dd, hm.y, Math.sin(a) * dd);
      m.lookAt(cam.position.x, m.position.y, cam.position.z);
      mat.map = this.cloudMaps[s.light][i % 4];
    }
    for (const g of this.fgs) g.o.visible = f >= g.a && f < g.b && g.a < s.b && g.b > s.a;
    // ---- moving props ----
    this.farm.update(f);
    const tr = truckAt(f, id); this.truck.update(tr.x, tr.z, tr.yaw, tr.s, tr.bounce, tr.pitch, true);
    this.truck.gun.visible = id >= 11 && id <= 13;
    this.hookGun.visible = id <= 2;
    this.hookGun.rotation.set(id === 2 ? 0.0 : 0, Math.PI / 2, id === 2 ? -1.3 : 0);
    this.hookGun.position.set(HOOK_GUN[0] + (id === 2 ? 0.9 : 0), 0, HOOK_GUN[2] + (id === 2 ? -0.4 : 0));
    this.lineGuns.visible = id === 6 ? f >= 457 : id >= 7 && id <= 8;
    this.crates.visible = id >= 6 && id <= 8 && (id > 6 || f >= 486);
    this.crates.children.forEach((c, i) => { const a0 = 486 + (i % 2) * 3 + Math.floor(i / 2) * 3, k = id > 6 ? 1 : smooth((f - a0) / 6); c.visible = id > 6 || f >= a0; c.position.y = 0.18 + Math.floor(i / 2) * 0.37 + 3.0 * (1 - k); });
    this.damGun.visible = id === 9 || id === 10 || id === 14;
    { const j = id === 10 && f >= 826 && f < 834 ? (f % 2 ? 1 : -1) * 0.06 * (1 - (f - 826) / 8) : 0; this.damGun.rotation.z = j; }
    this.brass.visible = id === 21 || id === 22;
    this.cam.visible = id >= 6 && id <= 8;
    this.table.visible = id === 23;
    this.floor.update((f - DROP_AT) / FPS, id === 17);
    // ---- cast + effects ----
    const right = V(0, 0, 0).setFromMatrixColumn(cam.matrixWorld, 0);
    const st = stage(id, t, f, { pos: cam.position, right });
    this.frustum.setFromProjectionMatrix(this.m4.multiplyMatrices(cam.projectionMatrix, cam.matrixWorldInverse));
    const tint = s.light === "golden" ? "#ffcf9e" : "#ffffff";
    let ai = 0;
    const used: Actor[] = [];
    for (const p of st.places) {
      const sc2 = p.scale ?? 1;
      if (!this.frustum.intersectsSphere(this.sph.set(this.v.set(p.x, p.y + 1.1 * sc2, p.z), 3.5))) continue;
      const a = this.actor(ai++);
      const [w, hgt, k] = p.size ?? [300, 500, 0.5];
      a.r = this.pool.req(p.key, w, hgt, k, p.draw);
      a.mesh.visible = true;
      a.mesh.geometry = p.geo === "wide" ? WIDE : BODY;
      a.mesh.position.set(p.x, p.y, p.z);
      a.mesh.rotation.set(0, p.yaw ?? Math.atan2(cam.position.x - p.x, cam.position.z - p.z), p.roll ?? 0);
      a.mesh.scale.set(p.mirror ? -sc2 : sc2, sc2, sc2);
      if (a.mat.emissiveMap) a.mat.emissive.set(tint);
      a.mesh.castShadow = L.actorShadow;
      used.push(a);
    }
    for (let i = ai; i < this.actors.length; i++) this.actors[i].mesh.visible = false;
    let fi = 0;
    const fused: Fx[] = [];
    for (const p of st.fx) {
      if (!this.frustum.intersectsSphere(this.sph.set(this.v.set(p.x, p.y, p.z), Math.max(p.w, p.h)))) continue;
      const ef = this.fx(fi++);
      ef.r = this.pool.req(p.key, p.cw, p.ch, 1, p.draw);
      ef.use(!!p.soft);
      ef.mesh.visible = true;
      ef.mesh.position.set(p.x, p.y, p.z);
      if (p.flat) ef.mesh.rotation.set(-Math.PI / 2, 0, p.rot ?? 0);
      else { ef.mesh.quaternion.copy(cam.quaternion); ef.mesh.rotateZ(p.rot ?? 0); }
      ef.mesh.scale.set(p.w, p.h, 1);
      fused.push(ef);
    }
    for (let i = fi; i < this.fxs.length; i++) this.fxs[i].mesh.visible = false;
    this.pool.flush();
    for (const a of used) a.bind();
    for (const ef of fused) ef.bind();
    return focus;
  }
}

export { V3 };
