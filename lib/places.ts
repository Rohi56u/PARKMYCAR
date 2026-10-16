import type { Point } from './domain.ts';

export type Place = {
  id: string;
  name: string;
  subtitle: string;
  point: Point;
  sourceUrl: string;
  kind?: string;
};

export function normalizePlaceQuery(value: string): string {
  return value.normalize('NFKC').replace(/\s+/gu, ' ').trim();
}

export function coordinatePlace(value: string): Place | null {
  const match = value.match(/^\s*([+-]?(?:\d+(?:\.\d+)?|\.\d+))\s*,\s*([+-]?(?:\d+(?:\.\d+)?|\.\d+))\s*$/u);
  if (!match) return null;
  const lat = Number(match[1]), lng = Number(match[2]);
  if (!Number.isFinite(lat) || !Number.isFinite(lng) || lat < 6 || lat > 38 || lng < 68 || lng > 98) return null;
  return { id: `point-${lat}-${lng}`, name: `${lat}, ${lng}`, subtitle: 'Selected coordinates', point: { lat, lng }, sourceUrl: '', kind: 'point' };
}

export function mapsSearchUrl(query: string): string {
  return `https://www.google.com/maps/search/?${new URLSearchParams({ api: '1', query: `${normalizePlaceQuery(query)}, India` })}`;
}

export function placeZoom(kind?: string): number {
  if (kind === 'country') return 5;
  if (kind === 'state') return 7;
  if (kind === 'county' || kind === 'district') return 10;
  if (kind === 'city' || kind === 'town') return 12;
  if (kind === 'village' || kind === 'locality') return 14;
  return 16;
}
