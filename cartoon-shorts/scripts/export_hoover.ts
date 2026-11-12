// Export a story short's per-frame state for the Blender renderer (Nov 9: story shorts move from three.js to Blender).
// Runs the SAME story.ts (cameras, cars) and cast.ts (who stands where, which drawing) as the Remotion film, and writes:
//   <out>/frames.json : per frame {f, id, cam {pos, look, fov, roll}, cars [...], places [...], fx [...]} in three.js
//                       coordinates (y up); the Blender side converts (x, y, z) -> (x, -z, y)
//   <out>/sprites/<hash>.png : every distinct character / effect drawing, drawn once with the toon.ts Pen at high res
// Usage (bundled with esbuild):  node scripts/export_blender.mjs <outDir> <f0> <f1>
import { createCanvas, loadImage } from "@napi-rs/canvas";
import * as fs from "node:fs";
import * as path from "node:path";
import * as crypto from "node:crypto";

// cast.ts / paint.ts create canvases at import time: give them node canvases
(globalThis as unknown as { document: unknown }).document = { createElement: () => createCanvas(2, 2) };

import * as THREE from "three";
import { Pen } from "../src/videos/marathon/toon";
import { stage } from "../src/videos/hoover/cast";
import { drawClean, type Expr as CExpr } from "../src/videos/clean/cleantoon";
import { CLEAN_CAST } from "../src/videos/clean/cast";
import { SHOTS, camAt, vehiclesAt, FPS, shotAt, dofAt, focusAt } from "../src/videos/hoover/story";

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
// --anime: swap the toon cards of the painted cast for their anime sprite kit (out/anime/kit/<name>/body_<expr>.png),
// same card frame: 600 x 1000 units, soles at y = 975, the character's height kept from the toon drawing
const ANIME = process.argv.includes("--anime");
const KIT = path.resolve("out", "anime", "kit");   // export_hoover.sh runs from cartoon-shorts/
const ANAME: Record<string, [string, number]> = { dave: ["dave", 788], repair: ["repairman", 760], bailiff: ["bailiff", 800], boss: ["boss", 760], worker: ["worker", 800], assistant: ["assistant", 740] };
const AEXPR: Record<string, string> = {
  neutral: "neutral", smile: "neutral", smile_closed: "smirk", smug: "smirk", smug_talk: "smirk_talk", talk: "talk", grin: "excited", stern: "suspicious",
  nervous: "panic", shock: "shock", pained: "sad", sad: "sad", angry: "angry", yell: "yell", laugh: "laugh", cheeky: "smirk", worried: "panic",
};
const kitImg = new Map<string, Awaited<ReturnType<typeof loadImage>> | null>();
const kitGet = async (name: string, e: string) => {
  const k = `${name}/${e}`;
  if (!kitImg.has(k)) { const f = path.join(KIT, name, `body_${e}.png`); kitImg.set(k, fs.existsSync(f) ? await loadImage(f) : null); }
  return kitImg.get(k)!;
};
const kitBox = new Map<string, number[]>();
const animeCard = async (o: string, opt: { expr?: string; blink?: number } | null) => {
  const [name, hUnits] = ANAME[o];
  let e = AEXPR[opt?.expr ?? "neutral"] ?? "neutral";
  if ((opt?.blink ?? 0) >= 0.9 && (e === "neutral" || e === "smirk")) e = "blink";
  let img = await kitGet(name, e);
  if (!img) { console.log(`  anime: no ${name}/${e}, using neutral`); e = "neutral"; img = await kitGet(name, "neutral"); }
  if (!kitBox.has(name)) kitBox.set(name, JSON.parse(fs.readFileSync(path.join(KIT, name, "meta.json"), "utf8")).body);
  const [x0, y0, x1, y1] = kitBox.get(name)!;
  const id = crypto.createHash("md5").update(`anime|${name}|${e}|${hUnits}|${process.env.ANIME_SAT ?? 0.72}|${process.env.ANIME_GAM ?? 1.12}`).digest("hex").slice(0, 16);
  if (!done.has(id)) {
    const cv = createCanvas(1200, 2000), g = cv.getContext("2d"), k = (hUnits * 2) / (y1 - y0);
    const w = (x1 - x0) * k, top = (975 - hUnits) * 2;
    g.drawImage(img!, x0, y0, x1 - x0, y1 - y0, 600 - w / 2, top, w, hUnits * 2);
    // pre-compensate the film's vivid grade (AgX punchy, exposure 1.25, comp saturation x1.25): painted art is already
    // saturated, so take saturation down and darken the mids a touch, or browns turn orange and greens go neon
    const id2 = g.getImageData(0, 0, 1200, 2000), d = id2.data, SAT = Number(process.env.ANIME_SAT ?? 0.72), GAM = Number(process.env.ANIME_GAM ?? 1.12);
    for (let i = 0; i < d.length; i += 4) {
      if (!d[i + 3]) continue;
      const r = d[i] / 255, gg = d[i + 1] / 255, b = d[i + 2] / 255, l = 0.2126 * r + 0.7152 * gg + 0.0722 * b;
      d[i] = 255 * Math.pow(l + (r - l) * SAT, GAM); d[i + 1] = 255 * Math.pow(l + (gg - l) * SAT, GAM); d[i + 2] = 255 * Math.pow(l + (b - l) * SAT, GAM);
    }
    g.putImageData(id2, 0, 0);
    fs.writeFileSync(path.join(SPR, id + ".png"), cv.toBuffer("image/png")); done.add(id);
  }
  return id;
};
// --clean: draw the Hoover cast with the clean-toon kit (look-dev v17c) on the same card frame (600 x 1000 units, soles at
// y = 975, height kept from the toon card). The film's acting maps onto clean-toon poses: toon expression -> clean
// expression, blink, look -> head turn toward the other character, prop -> arm angle, tilt.
const CLEAN = process.argv.includes("--clean");
const CLEAN_H: Record<string, number> = { dave: 788, repair: 760, boss: 760, bailiff: 800 };
const CEXPR: Record<string, CExpr> = {
  neutral: "neutral", smile: "smile", smile_closed: "smirk", smug: "smirk", smug_talk: "talk", talk: "talk", grin: "smile", stern: "deadpan",
  nervous: "worried", worried: "worried", shock: "shock", pained: "grimace", angry: "angry", yell: "angry", cheeky: "smirk", laugh: "smile", sad: "worried",
};
const CARM: Record<string, [number, number]> = { point: [6, 95], palm: [6, 60], facepalm: [150, 150], crossed: [28, 28], scratch: [6, 150] };
const cleanCard = (o: string, opt: Record<string, unknown> | null) => {
  const s = CLEAN_CAST[o], hU = CLEAN_H[o];
  const e = CEXPR[(opt?.expr as string) ?? "neutral"] ?? "neutral";
  const blink = Number(opt?.blink ?? 0) >= 0.9 ? 1 : 0, look = Number(opt?.look ?? 0), tilt = Number(opt?.tilt ?? 0);
  const prop = Array.isArray(opt?.prop) ? (opt!.prop as unknown[])[0] as string : (opt?.prop as string | null) ?? null;
  const [armL, armR] = prop && CARM[prop] ? CARM[prop] : [6, 6];
  const pose = { expr: e, blink, yaw: 0.35 * look, look: [0.6 * look, 0] as [number, number], armL, armR, tilt: tilt * 0.6, sweat: e === "worried" };
  const id = crypto.createHash("md5").update(`clean|v17c|${o}|${JSON.stringify(pose)}|${hU}|${process.env.CLEAN_GAM ?? 1.35}|${process.env.CLEAN_SAT ?? 0.95}`).digest("hex").slice(0, 16);
  if (!done.has(id)) {
    // clean-toon design box 1000 x 1600, feet at y 1560, head-top (hat) about y 80: scale the figure to the toon height
    const cv = createCanvas(1200, 2000), g = cv.getContext("2d"), k = (hU * 2) / (1560 - 80);
    g.translate(600, 975 * 2); g.scale(k, k); g.translate(-500, -1560);
    drawClean(g as unknown as CanvasRenderingContext2D, s, pose);
    // pre-compensate the vivid film grade (AgX punchy, exposure 1.25): darken the mids so ink stays near-black and the
    // outfits keep their sheet colours instead of going pastel
    const im = g.getImageData(0, 0, 1200, 2000), d = im.data, GAM = Number(process.env.CLEAN_GAM ?? 1.35), SAT = Number(process.env.CLEAN_SAT ?? 0.95);
    for (let i = 0; i < d.length; i += 4) {
      if (!d[i + 3]) continue;
      const r = d[i] / 255, gg = d[i + 1] / 255, b = d[i + 2] / 255, l = 0.2126 * r + 0.7152 * gg + 0.0722 * b;
      d[i] = 255 * Math.pow(Math.max(0, l + (r - l) * SAT), GAM); d[i + 1] = 255 * Math.pow(Math.max(0, l + (gg - l) * SAT), GAM); d[i + 2] = 255 * Math.pow(Math.max(0, l + (b - l) * SAT), GAM);
    }
    g.putImageData(im, 0, 0);
    fs.writeFileSync(path.join(SPR, id + ".png"), cv.toBuffer("image/png")); done.add(id);
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
  const places0 = st.places.map((p) => {
    const wide = p.geo === "wide";
    // one high-res tier for every card (Blender renders 1440x2560; close-ups fill the frame)
    const [w, h, k] = wide ? [2000, 2000, 2] : [1200, 2000, 2];
    const yaw = p.yaw ?? Math.atan2(cam.position.x - p.x, cam.position.z - p.z);
    const okey = p.key.split("|")[1] ?? p.key;
    // pose data for 3D rigs (make-short v3 engine): the FrontOpts / SideOpts JSON is the tail of the person key
    let opt: unknown = null; try { opt = JSON.parse(p.key.split("|").slice(2).join("|")); } catch { opt = null; }
    if (CLEAN && CLEAN_CAST[okey] && !wide) return { s: cleanCard(okey, opt as Record<string, unknown> | null), o: okey, side: 0, opt, x: r4(p.x), y: r4(p.y), z: r4(p.z), sc: r4(p.scale ?? 1), m: p.mirror ? 1 : 0, yaw: r4(yaw), roll: r4(p.roll ?? 0), wide: 0 };
    if (ANIME && ANAME[okey] && !wide) return { anime: okey, opt, s: "", o: okey, side: 0, x: r4(p.x), y: r4(p.y), z: r4(p.z), sc: r4(p.scale ?? 1), m: p.mirror ? 1 : 0, yaw: r4(yaw), roll: r4(p.roll ?? 0), wide: 0 } as Record<string, unknown>;
    return { s: NOSPR ? "" : sprite(p.key, w, h, k, p.draw), o: okey, side: p.key.startsWith("S|") ? 1 : 0, opt, x: r4(p.x), y: r4(p.y), z: r4(p.z), sc: r4(p.scale ?? 1), m: p.mirror ? 1 : 0, yaw: r4(yaw), roll: r4(p.roll ?? 0), wide: wide ? 1 : 0 };
  });
  const places = [];
  for (const p of places0) { if (p.anime) { p.s = await animeCard(p.anime as string, p.opt as { expr?: string; blink?: number }); delete p.anime; } places.push(p); }
  const fx = st.fx.filter((p) => !p.key.includes("|blob|") && !p.key.startsWith("blob")).map((p) => {
    const K = Math.max(1, Math.min(3, Math.round(900 / Math.max(p.cw, p.ch))));
    const mode = p.flat ? "flat" : p.upright ? "upright" : "face";
    const yaw = Math.atan2(cam.position.x - p.x, cam.position.z - p.z);
    return { s: sprite(`fx|${p.key}`, p.cw * K, p.ch * K, K, p.draw), o: p.key.split("|")[0], x: r4(p.x), y: r4(p.y), z: r4(p.z), w: r4(p.w), h: r4(p.h), mode, rot: r4(p.rot ?? 0), yaw: r4(yaw), soft: p.soft ? 1 : 0 };
  });
  const vs = vehiclesAt(id, f), cars: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(vs)) cars[k] = v ? { x: r4(v.x), z: r4(v.z), yaw: r4(v.yaw), d: r4(v.d), y: r4(v.y ?? 0), roll: r4(v.roll ?? 0), pitch: r4(v.pitch ?? 0) } : null;
  const d = dofAt(id, f);
  const props = st.props.map((p) => ({ k: p.k, x: r4(p.x), y: r4(p.y), z: r4(p.z), yaw: r4(p.yaw), s: r4(p.s), pitch: r4(p.pitch), roll: r4(p.roll) }));
  const ov = st.ov.map((o) => {
    const v = new THREE.Vector3(o.x, o.y, o.z).project(cam), behind = v.z > 1;
    return { t: o.t, text: o.text, bg: o.bg ?? null, rot: o.rot ?? 0, wob: o.wob ?? 0, k: r4(o.k), w: r4(o.w), sx: behind ? 0.5 : r4((v.x + 1) / 2), sy: behind ? 0.25 : r4((1 - v.y) / 2) };
  });
  frames.push({ f, id, set: shotAt(f).set, props, ov, cam: { pos: c.pos.map(r4), look: c.look.map(r4), fov: c.fov, roll: r4(c.roll) }, dof: { c: d.cInf, focus: focusAt(id, f).map(r4) }, cars, places, fx });
  if (f % 30 === 0) console.log(`frame ${f}: ${places.length} cards, ${fx.length} fx, ${done.size} sprites`);
}
fs.writeFileSync(path.join(outDir, "frames.json"), JSON.stringify({ fps: FPS, f0: F0, f1: F1, sun: SUN.toArray(), frames }));
console.log(`wrote ${frames.length} frames, ${done.size} sprites -> ${outDir}`);
