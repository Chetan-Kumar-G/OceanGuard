import type { GeoJSONPolygon } from "../api/types";

const KM_PER_DEG_LAT = 111.32;

/** Approximate a geodesic circle as a GeoJSON polygon (good enough at AOI scale). */
export function circlePolygon(centerLon: number, centerLat: number, radiusKm: number, steps = 64): GeoJSONPolygon {
  const kmPerDegLon = KM_PER_DEG_LAT * Math.cos((centerLat * Math.PI) / 180);
  const ring: number[][] = [];
  for (let i = 0; i <= steps; i++) {
    const theta = (i / steps) * 2 * Math.PI;
    const dLat = (radiusKm * Math.sin(theta)) / KM_PER_DEG_LAT;
    const dLon = (radiusKm * Math.cos(theta)) / kmPerDegLon;
    ring.push([centerLon + dLon, centerLat + dLat]);
  }
  return { type: "Polygon", coordinates: [ring] };
}

/** Flatten a Polygon/MultiPolygon's coordinates into a flat [lon, lat][] list, for bbox fitting. */
export function flattenCoords(geom: GeoJSONPolygon | null | undefined): [number, number][] {
  if (!geom || !geom.coordinates || geom.coordinates.length === 0) return [];
  const rings: number[][][] = geom.type === "MultiPolygon" ? (geom.coordinates as number[][][][]).flat() : (geom.coordinates as number[][][]);
  return rings.flat() as [number, number][];
}

export function boundsOf(points: [number, number][]): [[number, number], [number, number]] | null {
  if (points.length === 0) return null;
  let minLon = Infinity;
  let minLat = Infinity;
  let maxLon = -Infinity;
  let maxLat = -Infinity;
  for (const [lon, lat] of points) {
    if (lon < minLon) minLon = lon;
    if (lon > maxLon) maxLon = lon;
    if (lat < minLat) minLat = lat;
    if (lat > maxLat) maxLat = lat;
  }
  return [
    [minLon, minLat],
    [maxLon, maxLat],
  ];
}
