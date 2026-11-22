import test from 'node:test';
import assert from 'node:assert/strict';
import { handleApi } from '../lib/service';
import { Store } from '../lib/store';
import { TestDatabase } from './sqlite-adapter';
import { coordinatePlace, mapsSearchUrl, normalizePlaceQuery, placeZoom } from '../lib/places';
import { findPlaces, normalizePhoton } from '../lib/geocoding';

const now = Date.parse('2026-10-31T20:50:00Z');

function createEnv() {
  const db = new TestDatabase();
  const call = async (path: string, body?: unknown, method = body ? 'POST' : 'GET', origin = 'https://park.test') => {
    const request = new Request(`https://park.test/api/v1/${path}`, {
      method,
      headers: {
        'Content-Type': 'application/json',
        Origin: origin,
        'User-Agent': 'Challenger-Stress-Harness'
      },
      body: body ? JSON.stringify(body) : undefined
    });
    const response = await handleApi(request, {
      db,
      identity: null,
      allowBootstrap: true,
      rateKey: 'challenger-test',
      now
    });
    let data: any = null;
    try {
      data = await response.json();
    } catch {
      data = await response.text();
    }
    return { status: response.status, data };
  };
  return { db, call };
}

test('Challenger Stress 1: GET /api/v1/facilities with lat=28.353, lng=76.938, radius=1000', async () => {
  const { db, call } = createEnv();
  const res = await call('facilities?lat=28.353&lng=76.938&radius=1000');
  assert.equal(res.status, 200);
  assert.ok(Array.isArray(res.data.facilities));
  assert.ok(Array.isArray(res.data.results));
  assert.ok(res.data.facilities.length >= 3);
  assert.ok(res.data.results.length >= 3);
  assert.ok(res.data.facilities.some((f: any) => f.name.includes('Car Park') || f.name.includes('Parking')));
  db.close();
});

test('Challenger Stress 2: GET /api/v1/facilities handles missing/partial params gracefully', async () => {
  const { db, call } = createEnv();
  // No params -> returns catalogue facilities
  const resNoParams = await call('facilities');
  assert.equal(resNoParams.status, 200);
  assert.equal(resNoParams.data.facilities.length, 5);
  assert.deepEqual(resNoParams.data.results, []);

  // Missing lat (only lng) -> fallback to catalogue
  const resMissingLat = await call('facilities?lng=76.938');
  assert.equal(resMissingLat.status, 200);
  assert.equal(resMissingLat.data.facilities.length, 5);

  // Missing lng (only lat) -> fallback to catalogue
  const resMissingLng = await call('facilities?lat=28.353');
  assert.equal(resMissingLng.status, 200);
  assert.equal(resMissingLng.data.facilities.length, 5);
  db.close();
});

test('Challenger Stress 3: GET /api/v1/facilities rejects out of India and adversarial coordinates', async () => {
  const { db, call } = createEnv();
  // 50, 10 (Europe)
  assert.equal((await call('facilities?lat=50&lng=10&radius=1000')).status, 400);
  // 99, 99
  assert.equal((await call('facilities?lat=99&lng=99')).status, 400);
  // -10, 77
  assert.equal((await call('facilities?lat=-10&lng=77')).status, 400);
  // Non-numeric
  assert.equal((await call('facilities?lat=foo&lng=bar')).status, 400);
  // Below south border (5.9)
  assert.equal((await call('facilities?lat=5.9&lng=77')).status, 400);
  // Above north border (38.1)
  assert.equal((await call('facilities?lat=38.1&lng=77')).status, 400);
  // West of border (67.9)
  assert.equal((await call('facilities?lat=23&lng=67.9')).status, 400);
  // East of border (98.1)
  assert.equal((await call('facilities?lat=27&lng=98.1')).status, 400);
  db.close();
});

test('Challenger Stress 4: GET /api/v1/facilities works across Indian geographical boundaries', async () => {
  const { db, call } = createEnv();
  const regions = [
    { name: 'Kanyakumari', lat: 8.08, lng: 77.53, radius: 2000 },
    { name: 'Srinagar', lat: 34.08, lng: 74.79, radius: 2000 },
    { name: 'Ahmedabad', lat: 23.02, lng: 72.57, radius: 2000 },
    { name: 'Itanagar', lat: 27.10, lng: 93.61, radius: 2000 },
    { name: 'Panaji (Goa)', lat: 15.4989, lng: 73.8278, radius: 2000 },
    { name: 'Koramangala (Bengaluru)', lat: 12.935, lng: 77.624, radius: 2000 },
    { name: 'Manesar (Haryana)', lat: 28.353, lng: 76.938, radius: 1000 },
    { name: 'Chandni Chowk (Delhi) at default 1km', lat: 28.6507, lng: 77.2334, radius: 1000 },
  ];
  for (const r of regions) {
    const res = await call(`facilities?lat=${r.lat}&lng=${r.lng}&radius=${r.radius}`);
    assert.equal(res.status, 200, `Failed for ${r.name}`);
    assert.ok(res.data.facilities.length >= 3, `Expected facilities in ${r.name}, got ${res.data.facilities.length}`);
    assert.ok(res.data.results.length >= 3, `Expected results in ${r.name}, got ${res.data.results.length}`);
  }
  db.close();
});

test('Challenger Stress 4b: Transition zone near Connaught Place perimeter', async () => {
  const { db, call } = createEnv();
  // When Chandni Chowk (28.6507, 77.2334) is queried with radius=2000, Connaught Place facilities
  // lie in the corner of the rectangular SQL bounding box (~2.3km away).
  // The endpoint returns HTTP 200 OK with the bounding box facilities.
  const res = await call('facilities?lat=28.6507&lng=77.2334&radius=2000');
  assert.equal(res.status, 200);
  assert.ok(Array.isArray(res.data.facilities));
  assert.ok(Array.isArray(res.data.results));
  // Documenting the boundary behavior:
  // 2 facilities returned in the outer bounding box corner
  assert.equal(res.data.facilities.length, 2);
  // Results are 0 because haversine distance (2.3km) strictly enforces the 2000m circle limit
  assert.equal(res.data.results.length, 0);
  db.close();
});

test('Challenger Stress 5: coordinatePlace parses valid Indian coords and rejects adversarial/out-of-bound coords', () => {
  // Valid queries
  const valid = [
    '28.35, 76.93',
    ' 28.353 , 76.938 ',
    '+28.35, +76.93',
    '12.9716, 77.5946',
    '15.4989, 73.8278',
    '28.6507, 77.2334',
    '8.08, 77.53',
    '34.08, 74.79'
  ];
  for (const v of valid) {
    const p = coordinatePlace(v);
    assert.ok(p, `Failed to parse valid coord ${v}`);
    assert.equal(p.kind, 'point');
    assert.ok(p.point.lat >= 6 && p.point.lat <= 38);
    assert.ok(p.point.lng >= 68 && p.point.lng <= 98);
  }

  // Invalid queries
  const invalid = [
    '99, 99',
    '-10, 77',
    '5.99, 77.0',
    '38.01, 77.0',
    '28.0, 67.99',
    '28.0, 98.01',
    '28.35, 120.0',
    'abc, def',
    '28.35',
    '28.35, 76.93, 100',
    'NaN, NaN',
    '28.35, Infinity',
    '',
    '  ',
    'manesar',
    'connaught place',
    'asdfxyz123',
    '28.35; 76.93',
    '28.35 / 76.93'
  ];
  for (const inv of invalid) {
    assert.equal(coordinatePlace(inv), null, `Expected null for invalid coord: ${inv}`);
  }
});

test('Challenger Stress 6: Adversarial place query strings and normalization', () => {
  assert.equal(normalizePlaceQuery('   manesar   '), 'manesar');
  assert.equal(normalizePlaceQuery('New   Delhi,   DL'), 'New Delhi, DL');
  assert.equal(normalizePlaceQuery('  Ｄｅｌｈｉ  '), 'Delhi'); // Full-width
  assert.equal(normalizePlaceQuery('Chandni\nChowk\tDelhi'), 'Chandni Chowk Delhi');
  assert.equal(normalizePlaceQuery(''), '');
  assert.equal(normalizePlaceQuery('a'), 'a');

  // mapsSearchUrl safe escaping
  const url1 = mapsSearchUrl('Connaught & Place = Best');
  assert.ok(url1.startsWith('https://www.google.com/maps/search/?'));
  assert.ok(url1.includes('api=1'));
  assert.ok(!url1.includes('\n'));
});

test('Challenger Stress 7: POST /api/v1/places/search validation and non-existent places', async () => {
  const { db, call } = createEnv();

  // Single character
  assert.equal((await call('places/search', { query: 'a' })).status, 400);
  assert.equal((await call('places/search', { query: '1' })).status, 400);

  // Empty string
  assert.equal((await call('places/search', { query: '' })).status, 400);

  // Control characters
  assert.equal((await call('places/search', { query: 'Bad\u0000String' })).status, 400);
  assert.equal((await call('places/search', { query: 'Bad\u0007Bell' })).status, 400);

  // Too long (>160)
  assert.equal((await call('places/search', { query: 'x'.repeat(161) })).status, 400);

  // Non-existent place query handled gracefully
  const store = new Store(db);
  const mockEmpty: typeof fetch = async () => Response.json({ type: 'FeatureCollection', features: [] });
  const resNonExistent = await findPlaces(store, 'asdfxyz123', now, { fetcher: mockEmpty });
  assert.equal(resNonExistent.places.length, 0);

  db.close();
});

test('Challenger Stress 8: Real Indian locations correctly parsed and foreign/corrupted places rejected', () => {
  const indianCities = [
    { name: 'Manesar', state: 'Haryana', lat: 28.353, lng: 76.938 },
    { name: 'Connaught Place', state: 'Delhi', lat: 28.631, lng: 77.218 },
    { name: 'Koramangala', state: 'Karnataka', lat: 12.935, lng: 77.624 },
    { name: 'Chandni Chowk', state: 'Delhi', lat: 28.650, lng: 77.233 },
    { name: 'Panaji', state: 'Goa', lat: 15.498, lng: 73.827 },
  ];

  for (const c of indianCities) {
    const raw = {
      type: 'FeatureCollection',
      features: [{
        type: 'Feature',
        geometry: { type: 'Point', coordinates: [c.lng, c.lat] },
        properties: {
          countrycode: 'IN',
          osm_type: 'N',
          osm_id: 1001,
          name: c.name,
          state: c.state,
          district: c.state,
          osm_value: 'place'
        }
      }]
    };
    const parsed = normalizePhoton(raw);
    assert.equal(parsed.length, 1);
    assert.equal(parsed[0].name, c.name);
    assert.equal(parsed[0].point.lat, c.lat);
    assert.equal(parsed[0].point.lng, c.lng);
  }

  // Corrupted / adversarial OSM items
  const corrupted = {
    type: 'FeatureCollection',
    features: [
      { type: 'Feature', geometry: { type: 'Point', coordinates: ['bad', 28.6] }, properties: { countrycode: 'IN', osm_type: 'N', osm_id: 1, name: 'Bad Coords' } },
      { type: 'Feature', geometry: { type: 'Point', coordinates: [77.2, 28.6] }, properties: { countrycode: 'US', osm_type: 'N', osm_id: 2, name: 'US in India bbox' } },
      { type: 'Feature', geometry: { type: 'Point', coordinates: [77.2, 28.6] }, properties: { countrycode: 'IN', osm_type: 'N', osm_id: -5, name: 'Negative OSM ID' } },
      { type: 'Feature', geometry: { type: 'Polygon', coordinates: [] }, properties: { countrycode: 'IN', osm_type: 'N', osm_id: 3, name: 'Polygon not Point' } },
    ]
  };
  const parsedCorrupted = normalizePhoton(corrupted);
  assert.equal(parsedCorrupted.length, 0);
});
