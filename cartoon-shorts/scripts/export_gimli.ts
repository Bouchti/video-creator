// Export the Gimli Glider short's per-frame state for the Blender renderer (blender/toonrender.py --set gimli):
//   <out>/frames.json : per frame {f, id, set, cam, dof, cars, places (clean-toon cards), fx, ov} in three.js coordinates
//   <out>/sprites/<hash>.png : every distinct character pose / effect, drawn once
// Usage (bundled by export_gimli.sh):  node scripts/export_gimli.mjs <outDir> <f0> <f1>
import { createCanvas } from "@napi-rs/canvas";
import * as fs from "node:fs";
import * as path from "node:path";
import * as crypto from "node:crypto";
import * as THREE from "three";
import { drawClean } from "../src/videos/clean/cleantoon";
import { stage } from "../src/videos/gimli/cast";
import { SHOTS, TOTAL, camAt, vehiclesAt, FPS, shotAt, dofAt, focusAt } from "../src/videos/gimli/story";

const [outDir, a0, a1] = process.argv.slice(2);
const F0 = Number(a0 ?? 0), F1 = Number(a1 ?? TOTAL);
const SPR = path.join(outDir, "sprites");
fs.mkdirSync(SPR, { recursive: true });
const SUN = new THREE.Vector3(0.5, 0.75, -0.4).normalize();
const done = new Set<string>(fs.readdirSync(SPR).map((n) => n.replace(/\.png$/, "")));
const r4 = (v: number) => Math.round(v * 1e4) / 1e4;
// the film's vivid grade (AgX punchy, exposure 1.25) washes flat colours out: darken the mids before it
const GAM = Number(process.env.CLEAN_GAM ?? 1.35), SAT = Number(process.env.CLEAN_SAT ?? 0.95);
const grade = (g: CanvasRenderingContext2D, w: number, h: number) => {
  const im = g.getImageData(0, 0, w, h), d = im.data;
  for (let i = 0; i < d.length; i += 4) {
    if (!d[i + 3]) continue;
    const r = d[i] / 255, gg = d[i + 1] / 255, b = d[i + 2] / 255, l = 0.2126 * r + 0.7152 * gg + 0.0722 * b;
    d[i] = 255 * Math.pow(Math.max(0, l + (r - l) * SAT), GAM); d[i + 1] = 255 * Math.pow(Math.max(0, l + (gg - l) * SAT), GAM); d[i + 2] = 255 * Math.pow(Math.max(0, l + (b - l) * SAT), GAM);
  }
  g.putImageData(im, 0, 0);
};
const cardSprite = (c: ReturnType<typeof stage>["cards"][number]) => {
  const id = crypto.createHash("md5").update(`gimli-card|v18|${JSON.stringify(c.spec)}|${JSON.stringify(c.pose)}|${c.h}|${GAM}|${SAT}`).digest("hex").slice(0, 16);
  if (!done.has(id)) {
    // WIDE card: 1000 x 1000 units at 2 px/unit, soles at y = 975; the clean-toon box (1000 x 1600, feet 1560, head top ~80)
    const cv = createCanvas(2000, 2000), g = cv.getContext("2d") as unknown as CanvasRenderingContext2D, k = (c.h * 2) / (1560 - 80);
    g.translate(1000, 975 * 2); g.scale(k, k); g.translate(-500, -1560);
    drawClean(g, c.spec, c.pose);
    grade(g, 2000, 2000);
    fs.writeFileSync(path.join(SPR, id + ".png"), (cv as unknown as { toBuffer: (m: string) => Buffer }).toBuffer("image/png")); done.add(id);
  }
  return id;
};
const fxSprite = (key: string, w: number, h: number, K: number, draw: (g: CanvasRenderingContext2D) => void) => {
  const id = crypto.createHash("md5").update(`gimli-fx|${w}x${h}|${key}`).digest("hex").slice(0, 16);
  if (!done.has(id)) {
    const cv = createCanvas(w * K, h * K), g = cv.getContext("2d") as unknown as CanvasRenderingContext2D; g.setTransform(K, 0, 0, K, 0, 0); draw(g);
    fs.writeFileSync(path.join(SPR, id + ".png"), (cv as unknown as { toBuffer: (m: string) => Buffer }).toBuffer("image/png")); done.add(id);
  }
  return id;
};
const cam = new THREE.PerspectiveCamera(40, 1080 / 1920, 0.1, 4000);
const frames: unknown[] = [];
// layout report (measured, before any render): per shot and card, how often the card is on screen and how tall it is
type Lay = { n: number; on: number; hsum: number; xs: number[] };
const LAY: Record<string, Record<string, Lay>> = {};
for (let f = F0; f < F1; f++) {
  const id = shotAt(f).id, c = camAt(id, f);
  cam.fov = c.fov; cam.updateProjectionMatrix();
  cam.position.set(...c.pos); cam.up.set(0, 1, 0); cam.lookAt(...c.look); cam.rotateZ(c.roll); cam.updateMatrixWorld(true);
  const st = stage(id, f);
  for (const p of st.cards) {
    const hM = (p.h / 1480) * 1.7 * (p.scale ?? 1), foot = new THREE.Vector3(p.x, p.y, p.z).project(cam), head = new THREE.Vector3(p.x, p.y + hM, p.z).project(cam);
    const L = ((LAY[id] ??= {})[p.o] ??= { n: 0, on: 0, hsum: 0, xs: [] }), cx = (foot.x + head.x) / 2, inFront = foot.z < 1 && head.z < 1;
    L.n++; if (inFront && Math.abs(cx) < 0.92 && Math.min(foot.y, head.y) < 0.95 && Math.max(foot.y, head.y) > -0.95) { L.on++; L.hsum += Math.abs(head.y - foot.y) / 2; } L.xs.push(Math.round(cx * 100) / 100);
  }
  const places = st.cards.map((p) => ({ s: cardSprite(p), o: p.o, side: 0, opt: null, x: r4(p.x), y: r4(p.y), z: r4(p.z), sc: r4(p.scale ?? 1), m: p.mirror ? 1 : 0,
    yaw: r4(Math.atan2(cam.position.x - p.x, cam.position.z - p.z)), roll: r4(p.roll ?? 0), wide: 1 }));
  const fx = st.fx.map((p) => {
    const K = Math.max(1, Math.min(4, Math.round(512 / Math.max(p.cw, p.ch))));
    const mode = p.flat ? "flat" : p.upright ? "upright" : "face";
    return { s: fxSprite(p.key, p.cw, p.ch, K, p.draw), o: p.key.split("|")[0], x: r4(p.x), y: r4(p.y), z: r4(p.z), w: r4(p.w), h: r4(p.h), mode, rot: r4(p.rot ?? 0),
      yaw: r4(Math.atan2(cam.position.x - p.x, cam.position.z - p.z)), soft: p.soft ? 1 : 0 };
  });
  const vs = vehiclesAt(id, f), cars: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(vs)) cars[k] = v ? { x: r4(v.x), z: r4(v.z), yaw: r4(v.yaw), d: r4(v.d), y: r4(v.y ?? 0), roll: r4(v.roll ?? 0), pitch: r4(v.pitch ?? 0) } : null;
  const d = dofAt(id, f);
  const ov = st.ov.map((o) => {
    const v = new THREE.Vector3(o.x, o.y, o.z).project(cam), behind = v.z > 1;
    return { t: o.t, text: o.text, bg: o.bg ?? null, rot: o.rot ?? 0, wob: o.wob ?? 0, k: r4(o.k), w: r4(o.w), sx: behind ? 0.5 : r4((v.x + 1) / 2), sy: behind ? 0.25 : r4((1 - v.y) / 2) };
  });
  frames.push({ f, id, set: shotAt(f).set, props: [], ov, cam: { pos: c.pos.map(r4), look: c.look.map(r4), fov: c.fov, roll: r4(c.roll) }, dof: { c: d.cInf, focus: focusAt(id, f).map(r4) }, cars, places, fx });
  if (f % 60 === 0) console.log(`frame ${f} (shot ${id}): ${places.length} cards, ${fx.length} fx, ${done.size} sprites`);
}
const rep: string[] = [];
for (const [sid, cards] of Object.entries(LAY)) for (const [o, L] of Object.entries(cards)) {
  const vis = L.on / L.n, hgt = L.on ? L.hsum / L.on : 0, flag = vis < 0.6 ? "  <-- OFF-SCREEN" : hgt < 0.12 ? "  <-- TINY" : "";
  rep.push(`shot ${sid.padStart(2)} ${o.padEnd(8)} on-screen ${(vis * 100).toFixed(0).padStart(3)}%  height ${(hgt * 100).toFixed(0).padStart(3)}% of frame  x ${Math.min(...L.xs).toFixed(2)}..${Math.max(...L.xs).toFixed(2)}${flag}`);
}
const NL = String.fromCharCode(10);
fs.writeFileSync(path.join(outDir, "layout.txt"), rep.join(NL) + NL); console.log(rep.filter((r) => r.includes("<--")).join(NL) || "layout: all cards on screen");
fs.writeFileSync(path.join(outDir, "frames.json"), JSON.stringify({ fps: FPS, f0: F0, f1: F1, sun: SUN.toArray(), frames }));
console.log(`wrote ${frames.length} frames, ${done.size} sprites -> ${outDir}`);
