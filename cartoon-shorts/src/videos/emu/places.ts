// Pure geometry constants of the Emu War film (no imports: story.ts, cast.ts and the sets all read them).
/** the wheat farm (Campion district, WA): the field north of the fence (z < FIELD.z1), the farmyard south of it */
export const FIELD = { x0: -160, x1: 160, z0: -340, z1: -6 };
export const FENCE_Z = -5;
export const HOUSE = { x: -24, z: 24 };
export const MILL = { x: -11, z: 27 };
export const TANK = { x: -17.5, z: 30 };
/** the army camp in the farmyard: tent, parked truck, crates, the newsreel camera */
export const CAMP = { x: 16, z: 14 };
/** the farm dam: a round pond; an earth wall on its WEST side, the guns on top pointing east (+x) across the water */
export const DAM = { x: 240, z: -40, r: 10, wallX: 226, wallH: 1.1 };
/** the open plain of the truck chase: the truck drives along +x at z = CHASE.z */
export const CHASE = { x: 420, z: -220 };
/** the plain where the flock bursts apart (high shots) */
export const BURST = { x: 640, z: 40 };
/** interiors, far apart (fog + walls keep them out of each other's shots) */
export const OFFICE = { x: -2000, z: 0 };
export const PARL = { x: -2100, z: 0 };
export const FLOOR = { x: -2200, z: 0 };
