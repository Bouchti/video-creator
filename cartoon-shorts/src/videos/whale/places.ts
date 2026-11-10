// Pure geometry constants of the exploding-whale film (no imports: story.ts, cast.ts and the sets all read them).
/** the beach at Florence, Oregon: the sea north (z < SHORE), sand to the south, a flat parking strip behind a low
 *  dune line, conifer dunes beyond. The whale lies along x, head to +x. */
export const SHORE = -19;
export const WHALE = { x: 0, z: -5, len: 14, h: 3.0 };
/** the parking strip and the crowd's spot after "steps way back" (~60 m from the whale) */
export const LOT = { x0: 8, x1: 70, z0: 50, z1: 66 };
export const CAR = { x: 46, z: 60 };
/** the blaster's plunger at the front of the crowd */
export const PLUNGER = { x: 24, z: 52 };
/** the highway sign stuck in the sand; the highway truck parked on the beach */
export const SIGN = { x: -12, z: 7 };
export const HTRUCK = { x: -24, z: 10 };
/** the bus parked along the whale in the "longer than a bus" shot */
export const BUS = { x: -1, z: 4.0 };
/** the dynamite stacked against the whale's landward side */
export const DYN = { x: 0.2, z: -5 + 2.2 };
/** interiors / other places far apart (fog keeps them out of each other's shots) */
export const KITCHEN = { x: -2000, z: 0 };
export const PARK = { x: 1500, z: 0 };
export const DEALER = { x: 3000, z: 0 };
