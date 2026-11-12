// Pure geometry of "The Man Who Took a Hoover Van Hostage" (three.js coords: y up; Blender converts (x, y, z) -> (x, -z, y)).
// DRIVE (x 0): Dave's semi in Workington. House front wall at z -6 (x -7..7), front door at x -1.5. The driveway runs
//   x 1.8..5.4 from the house (z -6) to the pavement (z 6.6); a low brick wall along z 6.5 with a gap for the drive.
//   Pavement z 6.6..8, road z 8..15 (along x), the far pavement 15..16.4, houses opposite from z 24 facing -z.
//   The Hoover van parks on the drive nose to the house (centre z -1.3); the horse truck stands across the drive mouth
//   on the road (centre x 3.0, z 9.4, cab to -x).
// SHOP (x 2000): a 1992 electrical shop. Glass front at z 0 facing +z, interior z -14..0 (x 1992..2008), counter at
//   z -8, street outside z 0..14.
// FACTORY (x 4000): a hall x 3982..4018, z -32..8, the conveyor along z at x 4000 (belt top 0.95 m).
// OFFICE (x 6000): Hoover's office x 5995..6005, z -6..4, desk at z -2, window wall at z -6.
// KITCHEN (x 8000): Dave's kitchen x 7996..8004, z -4..4; the washing machine at (8001.6, z -3.3) against the back
//   wall (front to +z); the front door in the west wall (x 7996) at z 1.5.
export const DRIVE = { x: 0, z: 0 };
export const HOUSE_Z = -6;
export const DRV = { x0: 1.8, x1: 5.4, cx: 3.6 };
export const WALL_Z = 6.5;
export const ROAD = { z0: 8, z1: 15 };
export const VAN_PARK = { x: 3.6, z: -1.3 };
export const TRUCK_PARK = { x: 3.0, z: 9.4 };
export const SHOP = { x: 2000, z: 0, counterZ: -8 };
export const FACT = { x: 4000, z: 0, belt: 0.95 };
export const OFFICE = { x: 6000, z: 0, deskZ: -2 };
export const KITCHEN = { x: 8000, z: 0 };
export const WASHER = { x: 8001.6, z: -3.3 };
export const FRONT_DOOR = { x: 7996, z: 1.5 };
