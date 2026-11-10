// Pure geometry constants of the Eiffel film (no imports: story.ts, cast.ts and the sets all read them).
/** the tower: centre of its square base, base half-width (corner of a leg to the centre), height (1925: ~312 m) */
export const TOWER = { x: 0, z: -100, half: 62.5, h: 300 };
/** the four leg feet (outer corners) and where each leg's foot centre sits */
export const LEG = (i: number): [number, number] => { const sx = i & 1 ? 1 : -1, sz = i & 2 ? 1 : -1; return [TOWER.x + sx * 52, TOWER.z + sz * 52]; };
/** the Champ de Mars lawn in front of the tower (+z), the avenue the limousine drives along (x = 0) */
export const CHAMP = { x: 0, z: 60 };
/** the café street on the tower's axis: buildings at x = +-CAFE.half from z0 to z1, café terrace on the west side */
export const CAFE = { x: 0, z0: 170, z1: 620, half: 13, terraceZ: 430 };
/** interiors, far apart (fog + walls keep them out of each other's shots) */
export const HOTEL = { x: -900, z: 0 };
export const HOME = { x: -1000, z: 0 };
export const OFFICE = { x: -1100, z: 0 };
/** the countryside with the railway to Austria (track along x at z = TRAIN.z) */
export const COUNTRY = { x: 2000, z: 0 };
/** the girder the con man knocks on (beside the front-right leg), the east café tables (the Austrian morning) */
export const KNOCK_GIRDER: [number, number, number] = [41.05, 0.6, -34.85];
export const EAST_TABLES: [number, number][] = [[11.0, 476], [9.8, 480.5], [11.1, 485]];
/** the road across the front of the tower (the limousine), along x */
export const ROAD_Z = 14;
