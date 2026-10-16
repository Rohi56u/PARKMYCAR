import { ApiError } from './contracts.ts';
import { normalizePlaceQuery, type Place } from './places.ts';
import type { Store } from './store.ts';

const DEFAULT_PROVIDER = 'https://photon.komoot.io';
const CACHE_TTL = 7 * 86400000;
const MAX_RESPONSE_BYTES = 512 * 1024;
const MAX_RESULTS = 8;
type RecordValue = Record<string, unknown>;
const record = (value: unknown): RecordValue => value && typeof value === 'object' && !Array.isArray(value) ? value as RecordValue : {};
const text = (value: unknown, max = 160): string => typeof value === 'string' ? value.replace(/[\u0000-\u001f\u007f]/gu, '').trim().slice(0, max) : '';

/** Treat provider data as untrusted. Never infer that a place is a parking facility. */
export function normalizePhoton(value: unknown): Place[] {
  const data = record(value);
  if (data.type !== 'FeatureCollection' || !Array.isArray(data.features)) throw new ApiError(502, 'PLACES_RESPONSE', 'Place search returned an unreadable response. Please try again.');
  const seen = new Set<string>();
  const places: Place[] = [];
  for (const item of data.features.slice(0, 50)) {
    const feature = record(item), p = record(feature.properties), g = record(feature.geometry);
    if (text(p.countrycode).toUpperCase() !== 'IN' || g.type !== 'Point' || !Array.isArray(g.coordinates)) continue;
    const [lng, lat] = g.coordinates;
    if (typeof lat !== 'number' || typeof lng !== 'number' || !Number.isFinite(lat) || !Number.isFinite(lng) || lat < 6 || lat > 38 || lng < 68 || lng > 98) continue;
    const osmType = ({ N: 'node', W: 'way', R: 'relation' } as Record<string, string>)[text(p.osm_type).toUpperCase()];
    const osmId = p.osm_id;
    if (!osmType || typeof osmId !== 'number' || !Number.isSafeInteger(osmId) || osmId <= 0) continue;
    const name = text(p.name) || [text(p.housenumber), text(p.street)].filter(Boolean).join(' ') || text(p.city) || text(p.district);
    if (!name) continue;
    const id = `osm-${osmType}-${osmId}`;
    if (seen.has(id)) continue;
    seen.add(id);
    const address = [text(p.housenumber) && text(p.street) ? `${text(p.housenumber)} ${text(p.street)}` : text(p.street), text(p.locality), text(p.district), text(p.city), text(p.county), text(p.state), text(p.postcode), 'India'];
    const parts = [...new Set(address.filter(s => s && s.toLocaleLowerCase() !== name.toLocaleLowerCase()))];
    places.push({ id, name, subtitle: parts.join(' · '), point: { lat, lng }, sourceUrl: `https://www.openstreetmap.org/${osmType}/${osmId}`, kind: text(p.osm_value) || text(p.type) || 'place' });
    if (places.length === MAX_RESULTS) break;
  }
  return places;
}

export function photonUrl(base: string | undefined, query: string): URL {
  let url: URL;
  try { url = new URL(base || DEFAULT_PROVIDER); } catch { throw new ApiError(503, 'PLACES_CONFIG', 'Place search is temporarily unavailable.'); }
  if (url.protocol !== 'https:' || url.username || url.password || url.search || url.hash) throw new ApiError(503, 'PLACES_CONFIG', 'Place search is temporarily unavailable.');
  url.pathname = `${url.pathname.replace(/\/$/u, '')}/api/`;
  url.search = new URLSearchParams({ q: normalizePlaceQuery(query), countrycode: 'IN', lang: 'en', limit: String(MAX_RESULTS) }).toString();
  return url;
}

async function readProvider(response: Response): Promise<unknown> {
  if (Number(response.headers.get('content-length')) > MAX_RESPONSE_BYTES) { await response.body?.cancel(); throw new Error('provider_size'); }
  const reader = response.body?.getReader();
  if (!reader) throw new Error('provider_body');
  let size = 0;
  const chunks: Uint8Array[] = [];
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    size += value.byteLength;
    if (size > MAX_RESPONSE_BYTES) { await reader.cancel(); throw new Error('provider_size'); }
    chunks.push(value);
  }
  const bytes = new Uint8Array(size);
  let offset = 0;
  for (const part of chunks) { bytes.set(part, offset); offset += part.byteLength; }
  return JSON.parse(new TextDecoder().decode(bytes));
}

export type GeocodingOptions = { baseUrl?: string; fetcher?: typeof fetch; timeoutMs?: number };
export async function findPlaces(store: Store, query: string, now: number, options: GeocodingOptions = {}): Promise<{ places: Place[]; cached: boolean; retrievedAt: string; provider: string }> {
  const url = photonUrl(options.baseUrl, query);
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(url.toString().toLowerCase()));
  const cacheKey = Array.from(new Uint8Array(digest)).map(n => n.toString(16).padStart(2, '0')).join('');
  const cached = await store.db.prepare('SELECT payload,retrieved_at FROM geocode_cache WHERE key=? AND expires_at>?').bind(cacheKey, now).first<{ payload: string; retrieved_at: string }>();
  if (cached) return { places: JSON.parse(cached.payload) as Place[], cached: true, retrievedAt: cached.retrieved_at, provider: 'Photon / OpenStreetMap' };

  // Shared SQL gate works across Worker isolates. No keystroke requests or bulk enumeration.
  const admitted = await store.db.prepare('INSERT INTO request_limits(key,count,expires_at) VALUES(?,1,?) ON CONFLICT(key) DO UPDATE SET count=1,expires_at=excluded.expires_at WHERE request_limits.expires_at<=? RETURNING expires_at').bind('geocoder:next-request', now + 1200, now).first();
  if (!admitted) throw new ApiError(429, 'PLACES_BUSY', 'Place search is busy. Wait a moment, then search again.');
  await store.limit('geocoder:daily', 1000, 86400, now);

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), options.timeoutMs ?? 8000);
  let places: Place[];
  try {
    const response = await (options.fetcher ?? fetch)(url, { signal: controller.signal, redirect: 'error', headers: { Accept: 'application/json', 'User-Agent': 'ParkMyCar/1.1 (India place search)' } });
    if (response.status === 429) { await response.body?.cancel(); throw new ApiError(503, 'PLACES_BUSY', 'The place provider is busy. Try again shortly or choose a map point.'); }
    if (!response.ok) { await response.body?.cancel(); throw new Error('provider_http'); }
    places = normalizePhoton(await readProvider(response));
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError(503, 'PLACES_UNAVAILABLE', 'Place search could not connect. Try again or choose a point on the map.');
  } finally { clearTimeout(timer); }
  const retrievedAt = new Date(now).toISOString();
  // Store public results, not raw search terms or a user's origin/destination history.
  await store.db.prepare('INSERT INTO geocode_cache(key,payload,retrieved_at,expires_at) VALUES(?,?,?,?) ON CONFLICT(key) DO UPDATE SET payload=excluded.payload,retrieved_at=excluded.retrieved_at,expires_at=excluded.expires_at').bind(cacheKey, JSON.stringify(places), retrievedAt, now + (places.length ? CACHE_TTL : 300000)).run();
  return { places, cached: false, retrievedAt, provider: 'Photon / OpenStreetMap' };
}
