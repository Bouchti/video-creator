import { camAt, shotAt, HOOK_GUN, HOOK_GUNNER, HOOK_LOADER, HOOK_MAJOR, WON_EMU, FENCE_FARMER, MINISTER_AT, FARMERS_AT, LINE, LINE_Z, CAMERA_AT, POSE_MAJOR,
  DAM_GUN, DAM_GUNNER, DAM_LOADER, DAM_MAJOR, truckAt, TRUCK_PARK, MP_ASK, BRASS, BRASS_H, DESK_AT, PARADE_MAJOR, PARADE_Z, paradeX, LEAD_STOP, LOOKOUT, TEN_EMU, V3 } from "../../src/videos/emu/story";
import { CAMP, DAM, BURST, FENCE_Z, CHASE } from "../../src/videos/emu/places";
type P = [string, V3];
const pts = (f: number, id: number): P[] => {
  const tr = truckAt(f, id);
  const tray: V3 = [tr.x + Math.cos(tr.yaw) * -1.65, 0.95 + tr.bounce, tr.z - Math.sin(tr.yaw) * -1.65];
  const M: Record<number, P[]> = {
    1: [["gunner", HOOK_GUNNER], ["loader", HOOK_LOADER], ["major", HOOK_MAJOR], ["gun", HOOK_GUN], ["emuNear", [0, 0, -24]], ["emuFar", [0, 0, -60]]],
    2: [["emu", WON_EMU], ["gunner", [WON_EMU[0] + 1, 0, WON_EMU[2] + 0.5]]],
    4: [["farmer", FENCE_FARMER], ["emu1", [6.6, 0, -7.2]], ["emu2", [9.6, 0, -8.4]], ["emu3", [5.4, 0, -10.8]]],
    5: [["minister", MINISTER_AT], ...FARMERS_AT.map((p, i) => ["farmer" + i, p] as P)],
    7: [["cameraman", [CAMERA_AT[0] - 0.55, 0, CAMERA_AT[2]]], ["camera", CAMERA_AT], ["major", POSE_MAJOR], ["g0", [POSE_MAJOR[0] + 1, 0, POSE_MAJOR[2] - 0.8]]],
    8: [["g1", [LINE.g2, 0, LINE_Z]], ["g0", [LINE.g2 - 1.1, 0, LINE_Z - 0.9]]],
    9: [["gunner", DAM_GUNNER], ["loader", DAM_LOADER], ["major", DAM_MAJOR], ["gun", DAM_GUN], ["emuA", [DAM.x + 18, 0, DAM.z]], ["emuB", [DAM.x + 50, 0, DAM.z - 20]]],
    10: [["gunner", DAM_GUNNER], ["loader", DAM_LOADER], ["major", DAM_MAJOR], ["gun", DAM_GUN], ["emuA", [DAM.x + 15, 0, DAM.z]]],
    11: [["tray", tray], ["major", [TRUCK_PARK[0] - 1.4, 0, TRUCK_PARK[2] + 1.9]], ["truckNose", [tr.x + 3.2, 1, tr.z]]],
    12: [["tray", tray], ["truckNose", [tr.x + 3.2, 1, tr.z]], ["emu0", [CHASE.x - 16 + 14 * ((f - 923) / 30), 0, CHASE.z - 4]], ["emu7", [CHASE.x - 16 + 14 * ((f - 923) / 30) + 7 * 3.1, 0, CHASE.z - 7.2]]],
    13: [["tray", tray], ["emu7", [CHASE.x - 16 + 14 * ((f - 923) / 30) + 7 * 3.1, 0, CHASE.z - 7.2]]],
    19: [["truck", [tr.x, 1, tr.z]], ["emu0", [CAMP.x - 2, 0, FENCE_Z - 1.2]], ["emu8", [CAMP.x - 2 + 8 * 1.7, 0, FENCE_Z - 1.2]]],
    20: [["mp", MP_ASK]],
    21: [["gunner", [BRASS[0] - 0.2, BRASS_H - 0.32, BRASS[2]]], ["emuWalk", [BRASS[0] + 2, 0, BRASS[2] + 2.6]]],
    22: [["emu", TEN_EMU]],
    23: [["major", DESK_AT]],
    24: [["major", PARADE_MAJOR], ["col0", [paradeX(f), 0, PARADE_Z]], ["lead", [paradeX(Math.min(f, LEAD_STOP)) + 7.75, 0, PARADE_Z]], ["back", [paradeX(f), 0, PARADE_Z - 3.75]]],
    18: [["lookout", LOOKOUT]],
    14: [["major", DAM_MAJOR]],
  };
  return M[id] ?? [];
};
const fr = process.argv.slice(2).map(Number);
for (const f of fr) {
  const id = shotAt(f).id, c = camAt(id, f);
  const fw = [c.look[0] - c.pos[0], c.look[1] - c.pos[1], c.look[2] - c.pos[2]], n = Math.hypot(...fw); const F = fw.map((v) => v / n);
  let R = [F[1] * 0 - F[2] * 1, F[2] * 0 - F[0] * 0, F[0] * 1 - F[1] * 0]; const rn = Math.hypot(...R); R = R.map((v) => v / rn);
  const U = [R[1] * F[2] - R[2] * F[1], R[2] * F[0] - R[0] * F[2], R[0] * F[1] - R[1] * F[0]];
  const ty = Math.tan((c.fov * Math.PI) / 360), tx = ty * 9 / 16;
  const out: string[] = [];
  for (const [name, p] of pts(f, id)) {
    for (const [lab, dy] of [["ft", 0], ["hd", 1.75]] as const) {
      const d = [p[0] - c.pos[0], p[1] + dy - c.pos[1], p[2] - c.pos[2]], z = d[0] * F[0] + d[1] * F[1] + d[2] * F[2];
      const sx = 0.5 + (d[0] * R[0] + d[1] * R[1] + d[2] * R[2]) / z / tx / 2, sy = 0.5 - (d[0] * U[0] + d[1] * U[1] + d[2] * U[2]) / z / ty / 2;
      if (lab === "ft") out.push(`${name}: x${sx.toFixed(2)} ft${sy.toFixed(2)}`); else out[out.length - 1] += ` hd${sy.toFixed(2)} z${z.toFixed(1)}`;
    }
  }
  console.log(`f${f} s${id}  ` + out.join(" | "));
}
