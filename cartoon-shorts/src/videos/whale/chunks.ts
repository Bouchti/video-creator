// The blubber thrown by the blast: one fixed list of ballistic chunks (beach.ts Chunks draws them). Most fly in every
// direction; 26 are aimed into the parking lot (they "land on the crowd"), 7 come straight at the hook camera, one
// lands beside Thornton at the plunger in shot 2.
import type { ChunkDef } from "./beach";
import { WHALE } from "./places";

const hh = (i: number, s = 0) => { const v = Math.sin(i * 127.1 + s * 311.7) * 43758.5453; return v - Math.floor(v); };
const G = 9.8, OY = 1.6;
/** a chunk that leaves at `delay` and lands on (tx, tz) T seconds later */
const aimed = (tx: number, tz: number, T: number, s: number, skin: boolean, i: number, delay = 0): ChunkDef => ({
  v: [(tx - WHALE.x) / T, (s * 0.4 - OY + 0.5 * G * T * T) / T, (tz - WHALE.z) / T], s, skin, delay,
  spin: [(hh(i, 1) - 0.5) * 8, (hh(i, 2) - 0.5) * 8, (hh(i, 3) - 0.5) * 8],
});
export const CHUNKS: ChunkDef[] = [];
for (let i = 0; i < 115; i++) {
  const az = hh(i, 4) * Math.PI * 2, el = (35 + 40 * hh(i, 5)) * Math.PI / 180, sp = 9 + 18 * hh(i, 6) ** 0.7, s = 0.3 + 0.8 * hh(i, 7) ** 2;
  CHUNKS.push({ v: [Math.cos(az) * Math.cos(el) * sp, Math.sin(el) * sp, Math.sin(az) * Math.cos(el) * sp], s, skin: hh(i, 8) < 0.15, delay: 0.04 * hh(i, 9),
    spin: [(hh(i, 1) - 0.5) * 10, (hh(i, 2) - 0.5) * 10, (hh(i, 3) - 0.5) * 10] });
}
/** landing spots in the lot, and when (seconds after the blast) */
export const LOT_HITS: { x: number; z: number; t: number; s: number }[] = [];
for (let i = 0; i < 26; i++) {
  const x = 12 + hh(i, 11) * 50, z = 45 + hh(i, 12) * 20, T = 3.3 + 1.3 * hh(i, 13), s = 0.35 + 0.5 * hh(i, 14);
  CHUNKS.push(aimed(x, z, T, s, hh(i, 15) < 0.35, 200 + i));
  LOT_HITS.push({ x, z, t: T, s });
}
for (let i = 0; i < 9; i++) CHUNKS.push(aimed(22 + hh(i, 21) * 16, 72 + hh(i, 22) * 10, 2.4 + 1.0 * hh(i, 23), 0.8 + 0.6 * hh(i, 24), i % 4 === 0, 300 + i));
// five fast flat ones straight at the hook camera (they pass the lens during the first second)
for (let i = 0; i < 0; i++) CHUNKS.push(aimed(27 + hh(i, 31) * 6, 70 + hh(i, 32) * 6, 1.25 + 0.4 * hh(i, 33), 0.75 + 0.35 * hh(i, 34), false, 320 + i));
/** the one that lands right beside a fleeing man in the rain shot (person 4 of the lot crowd) */
const p4 = (() => {
  const i = 4, x0 = 13 + (i % 9) * 5.2 + hh(i, 1) * 2.2, z0 = 50.5 + Math.floor(i / 9) * 2.4 + hh(i, 2) * 1.2, T = 3.6;
  const go = T - 0.85 - 0.25 * hh(i, 3), v = 4.2 + 1.2 * hh(i, 4);
  return { x: x0 + (hh(i, 6) - 0.5) * 1.2 * go + 1.7, z: z0 + v * go - 1.3, t: T, s: 0.95 };
})();
export const NEAR_HIT = p4;
CHUNKS.push(aimed(p4.x, p4.z, p4.t, p4.s, false, 410));
/** the one beside Thornton in shot 2 (lands at s = 1.87 s = frame 46 of the hook timeline) */
export const THORNTON_HIT = { x: 25.6, z: 50.6, t: 2.27, s: 0.75 };
CHUNKS.push(aimed(THORNTON_HIT.x, THORNTON_HIT.z, THORNTON_HIT.t, THORNTON_HIT.s, false, 400));
