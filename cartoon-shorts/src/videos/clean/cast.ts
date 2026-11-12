// The clean-toon cast (look-dev sheet v17c, 12 Nov 2026): one Spec per Hoover character, shared by the sheet and the
// Blender exporter (scripts/export_hoover.ts --clean).
import type { Spec } from "./cleantoon";
export const CLEAN_CAST: Record<string, Spec> = {
  dave: { hat: "flatcap", hatCol: "#7a6448", outfit: "jacket", base: "#3f8a4a", trim: "#5a3a22", mustache: "#4a3020", neckerchief: "#c0353a", hair: "messy", hairCol: "#7a4a22" },
  repair: { hat: "cap", hatCol: "#1f4fa0", hatGloss: true, outfit: "overalls", base: "#2f56a8", shirt: "#f4f1ea", hair: "messy", hairCol: "#2a1c18" },
  boss: { hair: "combover", hairCol: "#9a9a9a", outfit: "suit", base: "#5a3a6a", pattern: "dots", tie: "#d8262e", chain: true, build: "stout" },
  bailiff: { hat: "bowler", hatCol: "#2a2a30", hatGloss: true, outfit: "suit", base: "#24222c", tie: "#f4f4f2", mustache: "#6a6a6a", suspenders: "#7a2a32", hair: "slick", hairCol: "#6a6a6a" },
};
