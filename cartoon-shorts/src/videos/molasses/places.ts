// Pure geometry constants of the molasses-flood film.
/** Commercial Street, Boston's North End, 1919. The street runs along z (the tank end at -z, toward the camera +z).
 *  Brick rowhouses line the west side (x < -8). The elevated railway runs over the east lane (posts at x = 8.2).
 *  The molasses tank stands in its yard east of the street (centre x 24, z -30, 27 m wide, 15 m tall). The harbor is
 *  the water east of x 14 for z > -8 and east of x 42 everywhere. */
export const STREET = { x0: -8, x1: 14 };
export const TANK = { x: 30, z: -30, r: 13.5, h: 15 };
export const EL = { x: 8.2, y: 6.2 };
export const WHARF_X = 14;
/** interiors, far apart */
export const OFFICE = { x: -2000, z: 0 };
export const COURT = { x: -2300, z: 0 };
export const SUBWAY = { x: -2600, z: 0 };
/** stray constants the shared files (farm.ts, beach.ts) still import */
export const BLOCK = { x: 0, z: 0 }; export const BARN = { x: -13, z: -14 }; export const HOUSE = { x: 13, z: -15 }; export const SCALE = { x: 4.5, z: 3.5 };
export const KITCHEN = { x: -5000, z: 0 }; export const DESK = { x: -5300, z: 0 }; export const SHOW = { x: 5000, z: 0 }; export const MOTEL = { x: -5600, z: 0 };
export const FEST = { x: 6000, z: 0 }; export const COPY = { x: 5700, z: 0 };
export const SHORE = -400; export const WHALE = { x: 0, z: -5, len: 14, h: 3.0 }; export const LOT = { x0: 8, x1: 70, z0: 50, z1: 66 };
export const CAR = { x: 46, z: 60 }; export const PLUNGER = { x: 24, z: 52 }; export const SIGN = { x: -12, z: 7 }; export const HTRUCK = { x: -24, z: 10 };
export const BUS = { x: -1, z: 4.0 }; export const DYN = { x: 0.2, z: -2.8 }; export const PARK = { x: 1500, z: 0 }; export const DEALER = { x: 3600, z: 0 };
