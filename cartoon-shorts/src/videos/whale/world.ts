// The whole exploding-whale film as one three.js scene: sky, the Oregon beach with the whale, the lot and the crowd,
// the kitchen of the jelly, the memorial park and the car dealer's lot.
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
import { FPS, SHOTS, camAt, V3, FOREGROUND, ShotDef, blastS, whaleState, beachCarX, BEACH_CAR_Z, hwyTruckX, casesAt, carX, lumpAt, HAMMER_AT, TV_AT, DEAL_CAR, smooth } from "./story";
import { Beach, Whale, Chunks, Car, bus, hwyTruck, dynamite, Plunger, tvCamera, Kitchen, Park, Dealer } from "./beach";
import { CHUNKS } from "./chunks";
import { CAR, PLUNGER, HTRUCK, DYN, BUS, LOT, WHALE } from "./places";

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
  private beach: Beach; private whale: Whale; private chunks: Chunks; private car: Car; private beachCar: Car; private dealCar: Car;
  private parked: Car[] = []; private bus = bus(); private truck = hwyTruck(); private cases = dynamite(20); private plunger: Plunger;
  private tv = tvCamera(); private kitchen: Kitchen;
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
    this.beach = new Beach(R);
    this.whale = new Whale(R);
    this.chunks = new Chunks(R, CHUNKS);
    this.car = new Car(R, "#3fa7a0", "walter");
    this.beachCar = new Car(R, "#c0353a", "beachRed");
    this.dealCar = new Car(R, "#3fa7a0", "walter");
    ["#f2c230", "#5a6a8a", "#e8e2d2"].forEach((c, i) => { const k = new Car(R, c, "parked" + i); k.set(54 + i * 6.5, 62 + (i % 2) * 0.6, Math.PI / 2 + 0.1 * (i - 1)); this.parked.push(k); });
    this.bus.position.set(BUS.x, 0, BUS.z); R.add(this.bus);
    this.truck.position.set(HTRUCK.x, 0, HTRUCK.z); R.add(this.truck);
    this.cases.position.set(DYN.x, 0, DYN.z); R.add(this.cases);
    this.plunger = new Plunger(R, V(WHALE.x - PLUNGER.x, 0.05, WHALE.z + 1.6 - PLUNGER.z));
    this.tv.position.set(TV_AT[0] + 0.6, 0, TV_AT[2] - 0.1); this.tv.rotation.y = Math.PI / 2 + 0.35; R.add(this.tv);
    this.kitchen = new Kitchen(R);
    new Park(R);
    new Dealer(R);
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
    this.beach.update(t);
    this.whale.set(whaleState(id, f));
    if (whaleState(id, f) === "gone" && blastS(id, f) > 0) this.whale.burst(blastS(id, f));
    const bs = blastS(id, f);
    this.chunks.update(bs, bs > 0, 1, cam.position);
    this.whale.fly(bs, id <= 2 || id === 19 || id === 20 || id === 22);
    const L2 = lumpAt(id, f);
    this.car.set(carX(id, f), CAR.z, Math.PI, L2.crush, false, L2.fall);
    this.car.root.visible = id >= 14 && id !== 22 && id !== 31;
    this.beachCar.set(beachCarX(f), BEACH_CAR_Z, 0); this.beachCar.root.visible = id === 6;
    this.dealCar.set(DEAL_CAR[0], DEAL_CAR[2], Math.PI / 2 - 0.5, 0, true); this.dealCar.root.visible = id === 31;
    this.bus.visible = id === 4;
    this.truck.visible = id >= 7 && id <= 13 || id === 25;
    this.truck.position.x = hwyTruckX(id, f);
    const n = casesAt(id, f);
    this.cases.visible = n > 0;
    this.cases.children.forEach((c, i) => { c.visible = i < n; const a0 = 622 + i * 2.1, k = id > 11 ? 1 : smooth((f - a0) / 4); c.position.y = 0.16 + Math.floor(i / 5) * 0.33 + 2.2 * (1 - k); });
    const press = id === 18 ? smooth((f - 1008) / 6) : id > 18 && id <= 20 ? 1 : 0;
    this.plunger.set(PLUNGER.x, PLUNGER.z, press, id >= 15 && id <= 20 || id === 2);
    this.tv.visible = id >= 15 && id <= 21 || id <= 2;
    this.kitchen.update(f, HAMMER_AT);
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
      else if (p.upright) ef.mesh.rotation.set(0, Math.atan2(cam.position.x - p.x, cam.position.z - p.z), p.rot ?? 0);
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
