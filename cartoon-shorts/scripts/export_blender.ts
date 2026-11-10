// Export a story short's per-frame state for the Blender renderer (Nov 9: story shorts move from three.js to Blender).
// Runs the SAME story.ts (cameras, cars) and cast.ts (who stands where, which drawing) as the Remotion film, and writes:
//   <out>/frames.json : per frame {f, id, cam {pos, look, fov, roll}, cars [...], places [...], fx [...]} in three.js
//                       coordinates (y up); the Blender side converts (x, y, z) -> (x, -z, y)
//   <out>/sprites/<hash>.png : every distinct character / effect drawing, drawn once with the toon.ts Pen at high res
// Usage (bundled with esbuild):  node scripts/export_blender.mjs <outDir> <f0> <f1>
import { createCanvas } from "@napi-rs/canvas";
import * as fs from "node:fs";
import * as path from "node:path";
import * as crypto from "node:crypto";

// cast.ts / paint.ts create canvases at import time: give them node canvases
(globalThis as unknown as { document: unknown }).document = { createElement: () => createCanvas(2, 2) };

import * as THREE from "three";
import { Pen } from "../src/videos/marathon/toon";
import { stage } from "../src/videos/marathon/cast";
import { SHOTS, camAt, carAt, offCarAt, FPS, shotAt, dofAt, focusAt } from "../src/videos/marathon/story";

const [outDir, a0, a1] = process.argv.slice(2);
const F0 = Number(a0 ?? 0), F1 = Number(a1 ?? SHOTS[SHOTS.length - 1].b);
const NOSPR = process.argv.includes("--nospr");   // 3D rigs only need the pose data, not the character sprites
const SPR = path.join(outDir, "sprites");
fs.mkdirSync(SPR, { recursive: true });
const SUN = new THREE.Vector3(0.5, 0.75, -0.4).normalize(); // toward the sun (matches the Blender sun lamp)

const done = new Set<string>(fs.readdirSync(SPR).map((n) => n.replace(/\.png$/, "")));
const sprite = (key: string, w: number, h: number, k: number, draw: (p: Pen) => void) => {
  const id = crypto.createHash("md5").update(`${w}x${h}|${key}`).digest("hex").slice(0, 16);
  if (!done.has(id)) {
    const cv = createCanvas(w, h), g = cv.getContext("2d");
    g.setTransform(k, 0, 0, k, 0, 0);
    draw(new Pen(g as unknown as CanvasRenderingContext2D));
    fs.writeFileSync(path.join(SPR, id + ".png"), cv.toBuffer("image/png"));
    done.add(id);
  }
  return id;
};
const r4 = (v: number) => Math.round(v * 1e4) / 1e4;
const cam = new THREE.PerspectiveCamera(40, 1080 / 1920, 0.1, 2000);
const frames: unknown[] = [];
for (let f = F0; f < F1; f++) {
  const id = shotAt(f).id, t = f / FPS, c = camAt(id, f);
  cam.fov = c.fov; cam.updateProjectionMatrix();
  cam.position.set(...c.pos); cam.up.set(0, 1, 0); cam.lookAt(...c.look); cam.rotateZ(c.roll); cam.updateMatrixWorld(true);
  const right = new THREE.Vector3().setFromMatrixColumn(cam.matrixWorld, 0);
  const st = stage(id, t, f, { pos: cam.position, right, sun: SUN });
  const places = st.places.map((p) => {
    const wide = p.geo === "wide";
    // one high-res tier for every card (Blender renders 1440x2560; close-ups fill the frame)
    const [w, h, k] = wide ? [2000, 2000, 2] : [1200, 2000, 2];
    const yaw = p.yaw ?? Math.atan2(cam.position.x - p.x, cam.position.z - p.z);
    const okey = p.key.split("|")[1] ?? p.key;
    // pose data for 3D rigs (make-short v3 engine): the FrontOpts / SideOpts JSON is the tail of the person key
    let opt: unknown = null; try { opt = JSON.parse(p.key.split("|").slice(2).join("|")); } catch { opt = null; }
    return { s: NOSPR ? "" : sprite(p.key, w, h, k, p.draw), o: okey, side: p.key.startsWith("S|") ? 1 : 0, opt, x: r4(p.x), y: r4(p.y), z: r4(p.z), sc: r4(p.scale ?? 1), m: p.mirror ? 1 : 0, yaw: r4(yaw), roll: r4(p.roll ?? 0), wide: wide ? 1 : 0 };
  });
  const fx = st.fx.filter((p) => !p.key.includes("|blob|") && !p.key.startsWith("blob")).map((p) => {
    const K = Math.max(1, Math.min(3, Math.round(900 / Math.max(p.cw, p.ch))));
    const mode = p.flat ? "flat" : p.upright ? "upright" : "face";
    const yaw = Math.atan2(cam.position.x - p.x, cam.position.z - p.z);
    return { s: sprite(`fx|${p.key}`, p.cw * K, p.ch * K, K, p.draw), o: p.key.split("|")[0], x: r4(p.x), y: r4(p.y), z: r4(p.z), w: r4(p.w), h: r4(p.h), mode, rot: r4(p.rot ?? 0), yaw: r4(yaw), soft: p.soft ? 1 : 0 };
  });
  const car = (s: ReturnType<typeof carAt>) => (s.on ? { x: r4(s.x), z: r4(s.z), yaw: r4(s.yaw), d: r4(s.d) } : null);
  const d = dofAt(id, f);
  frames.push({ f, id, cam: { pos: c.pos.map(r4), look: c.look.map(r4), fov: c.fov, roll: r4(c.roll) }, dof: { c: d.cInf, focus: focusAt(id, f).map(r4) },
    cars: { lorz: car(carAt(id, f)), off: car(offCarAt(id, f)) }, places, fx });
  if (f % 30 === 0) console.log(`frame ${f}: ${places.length} cards, ${fx.length} fx, ${done.size} sprites`);
}
fs.writeFileSync(path.join(outDir, "frames.json"), JSON.stringify({ fps: FPS, f0: F0, f1: F1, sun: SUN.toArray(), frames }));
console.log(`wrote ${frames.length} frames, ${done.size} sprites -> ${outDir}`);
