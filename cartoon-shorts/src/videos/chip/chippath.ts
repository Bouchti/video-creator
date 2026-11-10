// Pure geometry constants of the chip film (no imports: story.ts and sets.ts both read them).
type XY = [number, number];
/** centre of the plasma (where the laser meets the tin) and the optical path (polyline in the z = 0 plane) */
export const PLASMA: XY = [-5.35, 1.45];
export const BEAM: XY[] = [PLASMA, [-6.05, 1.45], [-4.25, 1.75], [-2.7, 2.55], [-1.25, 1.55], [0.2, 2.86], [1.05, 1.7], [2.05, 2.5], [2.75, 1.55], [1.75, 0.98]];
export const WAFER: [number, number, number] = [1.75, 0.95, 0];
export const NOZZLE: XY = [-5.35, 2.5];
export const EUV = { x0: -4.25, x1: 3.6, y1: 3.3, z: 1.55, sx0: -6.6, sx1: -4.25, sy1: 2.9 };
export const CITY = { x: 2000, z: 0, nx: 60, nz: 46, px: 2.4, pz: 6.4 };
/** the open square in the middle of the chip city (cells skipped): columns i0..i1-1, rows j0..j1-1 */
export const SQUARE = { i0: 25, i1: 35, j0: 23, j1: 26 };
export const CR = { x0: -15, x1: 15, z0: -10, z1: 9, h: 4.8 };
/** the far-apart places of the film (fog keeps them out of each other's shots) */
export const LAB = { x: -400, z: 0 };
export const KITCHEN = { x: -460, z: 0 };
export const STREET = { x: 400, z: 0 };
export const BEACH = { x: 0, z: 600 };
export const PULLER = { x: 0, z: -600 };
export const STENCIL = { x: 60, z: -600 };
export const MIRROR = { x: -1200, z: 0 };
export const SKY = { x: 0, y: 400, z: 1500 };
/** Germany's outline (simplified from lon/lat, 25 m per degree of latitude), xz around MIRROR, north = -z */
export const GERMANY: [number, number][] = [[-53.6, -60.0], [-28.4, -67.5], [-22.1, -90.0], [-7.9, -90.0], [9.4, -80.0], [33.1, -82.5], [59.8, -67.5], [63.0, -52.5], [66.1, -35.0], [67.7, -10.0], [72.4, 2.5], [61.4, 5.0], [34.6, 20.0], [26.8, 22.5], [40.9, 45.0], [53.6, 60.0], [40.9, 72.5], [40.9, 90.0], [28.3, 87.5], [1.6, 92.5], [-12.6, 90.0], [-28.4, 87.5], [-44.1, 90.0], [-44.1, 77.5], [-34.7, 55.0], [-63.0, 42.5], [-67.7, 27.5], [-69.3, 10.0], [-70.9, -15.0], [-56.7, -17.5], [-53.6, -25.0], [-58.3, -35.0], [-50.4, -50.0]];
/** where the tiny bump sits (near the south-west edge, xz relative to MIRROR) */
export const BUMP: [number, number] = [-30, 60];
