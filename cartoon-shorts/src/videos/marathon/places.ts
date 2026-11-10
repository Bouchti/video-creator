// Pure geometry constants of the 1904 Olympic marathon film.
/** The country road outside St. Louis runs along z (x = 0 is its centre, 7 m wide). The runners go toward -z.
 *  Spots along it: the hook (z 0), the only water well (z -60), the MILE 9 post (z -110), the MILE 19 breakdown
 *  (z -170), Hicks (z -220), the orchard east of the road (z -300), the dog field west of it (z -350) and the
 *  Boston finish banner (z -430). Fields lie 7 cm above the road (no coplanar surfaces). */
export const ROAD = { half: 3.5, field: 0.07 };
export const WELL = { x: -6.2, z: -60 };
export const MILE9 = { x: 4.1, z: -110 };
export const MILE19 = { x: 4.1, z: -164 }; // v2: 6 m back up the road, out of the breakdown lens
export const HICKS = { x: 0, z: -220 };
export const ORCHARD = { x: 9, z: -300 };
export const DOGF = { x: -14, z: -350 };
export const BOSTON = { z: -430 };
/** the stadium (Francis Field), far away: the track runs along z through the finish line at z 0, the grandstand is
 *  west of it (x < -7) facing +x */
export const STAD = { x: -2000, z: 0 };
/** stray constants shared files still import */
export const STREET = { x0: -8, x1: 14 };
export const TANK = { x: 30, z: -30, r: 13.5, h: 15 };
export const EL = { x: 8.2, y: 6.2 };
export const WHARF_X = 14;
export const OFFICE = { x: -2000, z: 0 };
export const COURT = { x: -2300, z: 0 };
export const SUBWAY = { x: -2600, z: 0 };
export const BLOCK = { x: 0, z: 0 }; export const BARN = { x: -13, z: -14 }; export const HOUSE = { x: 13, z: -15 }; export const SCALE = { x: 4.5, z: 3.5 };
export const KITCHEN = { x: -5000, z: 0 }; export const DESK = { x: -5300, z: 0 }; export const SHOW = { x: 5000, z: 0 }; export const MOTEL = { x: -5600, z: 0 };
export const FEST = { x: 6000, z: 0 }; export const COPY = { x: 5700, z: 0 };
export const SHORE = -400; export const WHALE = { x: 0, z: -5, len: 14, h: 3.0 }; export const LOT = { x0: 8, x1: 70, z0: 50, z1: 66 };
export const CAR = { x: 46, z: 60 }; export const PLUNGER = { x: 24, z: 52 }; export const SIGN = { x: -12, z: 7 }; export const HTRUCK = { x: -24, z: 10 };
export const BUS = { x: -1, z: 4.0 }; export const DYN = { x: 0.2, z: -2.8 }; export const PARK = { x: 1500, z: 0 }; export const DEALER = { x: 3600, z: 0 };
