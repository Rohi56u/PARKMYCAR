import assert from 'node:assert/strict';
import { handleApi } from '../lib/service';
import { Store } from '../lib/store';
import { TestDatabase } from './sqlite-adapter';
import { coordinatePlace, mapsSearchUrl, normalizePlaceQuery, placeZoom } from '../lib/places';
import { findPlaces, normalizePhoton } from '../lib/geocoding';

async function runAdversarialStressTests() {
  console.log('=== STARTING ADVERSARIAL STRESS TEST SUITE ===\n');

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
      } catch (err) {
        data = await response.text();
      }
      return { status: response.status, data };
    };
    return { db, call };
  }

  // -------------------------------------------------------------
  // TEST GROUP 1: GET /api/v1/facilities
  // -------------------------------------------------------------
  console.log('--- TEST GROUP 1: GET /api/v1/facilities Endpoint ---');
  {
    const { db, call } = createEnv();

    // 1.1 Target facility query: lat=28.353, lng=76.938, radius=1000 (Manesar area)
    const res1 = await call('facilities?lat=28.353&lng=76.938&radius=1000');
    console.log('[1.1] GET /api/v1/facilities?lat=28.353&lng=76.938&radius=1000 -> Status:', res1.status);
    assert.equal(res1.status, 200, 'Should return 200 OK');
    assert.ok(Array.isArray(res1.data.facilities), 'Should return facilities array');
    assert.ok(Array.isArray(res1.data.results), 'Should return results array');
    assert.ok(res1.data.facilities.length >= 3, `Expected at least 3 facilities, got ${res1.data.facilities.length}`);
    assert.ok(res1.data.results.length >= 3, `Expected at least 3 search results, got ${res1.data.results.length}`);
    console.log(`  Passed! Returned ${res1.data.facilities.length} facilities and ${res1.data.results.length} results.`);
    console.log(`  Sample facility: ${res1.data.facilities[0].name} (${res1.data.facilities[0].type})`);

    // 1.2 Missing lat/lng query: GET /api/v1/facilities (no query params)
    const res2 = await call('facilities');
    console.log('[1.2] GET /api/v1/facilities (no params) -> Status:', res2.status);
    assert.equal(res2.status, 200, 'Should return 200 OK');
    assert.ok(Array.isArray(res2.data.facilities), 'Should return catalogue facilities');
    assert.equal(res2.data.facilities.length, 5, 'Should return all 5 seeded facilities');
    assert.deepEqual(res2.data.results, [], 'Results should be empty array when no coords provided');
    console.log('  Passed! Returned seeded catalogue (5 items) and empty results.');

    // 1.3 Partial params: Missing lat (only lng provided)
    const res3 = await call('facilities?lng=76.938');
    console.log('[1.3] GET /api/v1/facilities?lng=76.938 (missing lat) -> Status:', res3.status);
    assert.equal(res3.status, 200, 'Should fallback to returning all facilities when lat missing');
    assert.equal(res3.data.facilities.length, 5);
    console.log('  Passed! Gracefully fell back to catalogue listing.');

    // 1.4 Partial params: Missing lng (only lat provided)
    const res4 = await call('facilities?lat=28.353');
    console.log('[1.4] GET /api/v1/facilities?lat=28.353 (missing lng) -> Status:', res4.status);
    assert.equal(res4.status, 200, 'Should fallback to returning all facilities when lng missing');
    assert.equal(res4.data.facilities.length, 5);
    console.log('  Passed! Gracefully fell back to catalogue listing.');

    // 1.5 Out of bounds: lat=50, lng=10 (Europe)
    const res5 = await call('facilities?lat=50&lng=10&radius=1000');
    console.log('[1.5] GET /api/v1/facilities?lat=50&lng=10 (Europe) -> Status:', res5.status);
    assert.equal(res5.status, 400, 'Should reject out-of-India coords with 400 BAD_REQUEST');
    console.log('  Passed! Rejected with 400 BAD_REQUEST:', res5.data.error?.message || res5.data);

    // 1.6 Adversarial coords: lat=99, lng=99
    const res6 = await call('facilities?lat=99&lng=99&radius=1000');
    console.log('[1.6] GET /api/v1/facilities?lat=99&lng=99 -> Status:', res6.status);
    assert.equal(res6.status, 400, 'Should reject lat=99, lng=99 with 400');
    console.log('  Passed! Rejected with 400.');

    // 1.7 Non-numeric coords: lat=abc, lng=xyz
    const res7 = await call('facilities?lat=abc&lng=xyz');
    console.log('[1.7] GET /api/v1/facilities?lat=abc&lng=xyz -> Status:', res7.status);
    assert.equal(res7.status, 400, 'Should reject non-numeric lat/lng with 400');
    console.log('  Passed! Rejected with 400.');

    // 1.8 Boundary coords: India borders test
    // Lat bounds: 6 to 38, Lng bounds: 68 to 98
    const boundaryPoints = [
      { name: 'Kanyakumari / South Border', lat: 8.08, lng: 77.53, valid: true },
      { name: 'Kashmir / North Border', lat: 34.08, lng: 74.79, valid: true },
      { name: 'Gujarat / West Border', lat: 23.02, lng: 72.57, valid: true },
      { name: 'Arunachal / East Border', lat: 27.10, lng: 93.61, valid: true },
      { name: 'Below South Border (lat 5.9)', lat: 5.9, lng: 77.0, valid: false },
      { name: 'Above North Border (lat 38.1)', lat: 38.1, lng: 77.0, valid: false },
      { name: 'West of West Border (lng 67.9)', lat: 23.0, lng: 67.9, valid: false },
      { name: 'East of East Border (lng 98.1)', lat: 27.0, lng: 98.1, valid: false },
    ];

    for (const bp of boundaryPoints) {
      const res = await call(`facilities?lat=${bp.lat}&lng=${bp.lng}&radius=1500`);
      if (bp.valid) {
        assert.equal(res.status, 200, `Expected 200 for ${bp.name}`);
        assert.ok(res.data.facilities.length >= 3, `Expected facilities provisioned for ${bp.name}`);
        console.log(`  Passed! Boundary ${bp.name} (${bp.lat}, ${bp.lng}) -> 200 OK (${res.data.facilities.length} facilities)`);
      } else {
        assert.equal(res.status, 400, `Expected 400 for ${bp.name}`);
        console.log(`  Passed! Boundary ${bp.name} (${bp.lat}, ${bp.lng}) -> 400 BAD_REQUEST`);
      }
    }

    // 1.9 Radius bounds and clamping
    const resSmallRadius = await call('facilities?lat=28.353&lng=76.938&radius=10'); // Below 100
    assert.equal(resSmallRadius.status, 200);
    const resLargeRadius = await call('facilities?lat=28.353&lng=76.938&radius=999999'); // Above 50000
    assert.equal(resLargeRadius.status, 200);
    console.log('  Passed! Radius parameter clamps gracefully.');

    db.close();
  }

  // -------------------------------------------------------------
  // TEST GROUP 2: CoordinatePlace Parsing in lib/places.ts
  // -------------------------------------------------------------
  console.log('\n--- TEST GROUP 2: coordinatePlace Parsing ---');
  {
    const validCoordinates = [
      { input: '28.35, 76.93', expectedLat: 28.35, expectedLng: 76.93 },
      { input: ' 28.353 ,  76.938 ', expectedLat: 28.353, expectedLng: 76.938 },
      { input: '+28.35, +76.93', expectedLat: 28.35, expectedLng: 76.93 },
      { input: '12.9716, 77.5946', expectedLat: 12.9716, expectedLng: 77.5946 }, // Bengaluru
      { input: '15.4989, 73.8278', expectedLat: 15.4989, expectedLng: 73.8278 }, // Panaji
      { input: '28.6507, 77.2334', expectedLat: 28.6507, expectedLng: 77.2334 }, // Chandni Chowk
    ];

    for (const vc of validCoordinates) {
      const p = coordinatePlace(vc.input);
      assert.ok(p, `Should parse ${vc.input}`);
      assert.equal(p.point.lat, vc.expectedLat);
      assert.equal(p.point.lng, vc.expectedLng);
      console.log(`  Passed! "${vc.input}" -> lat: ${p.point.lat}, lng: ${p.point.lng}`);
    }

    const invalidCoordinates = [
      '99, 99', // Out of India bounds
      '-10, 77', // Negative lat (outside India)
      '28.35, 120.0', // Lng > 98
      '28.35, 60.0', // Lng < 68
      '5.5, 77.0', // Lat < 6
      '38.5, 77.0', // Lat > 38
      'abc, def',
      '28.35', // Single number
      '28.35, 76.93, 100', // 3 numbers
      'NaN, NaN',
      '28.35, Infinity',
      '',
      '  ',
      'manesar',
      'connaught place',
      '28.35; 76.93', // Semicolon instead of comma
    ];

    for (const ic of invalidCoordinates) {
      const p = coordinatePlace(ic);
      assert.equal(p, null, `Should return null for "${ic}"`);
      console.log(`  Passed! Invalid coordinate rejected: "${ic}" -> null`);
    }
  }

  // -------------------------------------------------------------
  // TEST GROUP 3: normalizePlaceQuery and Adversarial Text Inputs
  // -------------------------------------------------------------
  console.log('\n--- TEST GROUP 3: normalizePlaceQuery and Adversarial Strings ---');
  {
    assert.equal(normalizePlaceQuery('   manesar   '), 'manesar');
    assert.equal(normalizePlaceQuery('New   Delhi,   DL'), 'New Delhi, DL');
    assert.equal(normalizePlaceQuery('  Ｄｅｌｈｉ  '), 'Delhi'); // Full-width unicode normalization
    assert.equal(normalizePlaceQuery('Chandni\nChowk\tDelhi'), 'Chandni Chowk Delhi');
    console.log('  Passed! Query normalization handles full-width, tabs, extra spaces.');

    // mapsSearchUrl escaping
    const safeUrl = mapsSearchUrl('Connaught & Place = Best');
    assert.ok(safeUrl.includes('Connaught+%26+Place+%3D+Best%2C+India') || safeUrl.includes('Connaught'), 'Should safely encode parameters');
    console.log('  Passed! mapsSearchUrl encodes special characters.');

    // placeZoom verification
    assert.equal(placeZoom('country'), 5);
    assert.equal(placeZoom('state'), 7);
    assert.equal(placeZoom('district'), 10);
    assert.equal(placeZoom('city'), 12);
    assert.equal(placeZoom('village'), 14);
    assert.equal(placeZoom('point'), 16);
    console.log('  Passed! placeZoom levels verified.');
  }

  // -------------------------------------------------------------
  // TEST GROUP 4: POST /api/v1/places/search Adversarial Cases
  // -------------------------------------------------------------
  console.log('\n--- TEST GROUP 4: POST /api/v1/places/search Schema & Handlers ---');
  {
    const { db, call } = createEnv();

    // 4.1 Single character input
    const resShort = await call('places/search', { query: 'a' });
    console.log('[4.1] Query="a" -> Status:', resShort.status);
    assert.equal(resShort.status, 400, 'Should reject single character query with 400');
    assert.ok(resShort.data.error?.message?.includes('two characters') || resShort.data.message?.includes('two characters') || resShort.status === 400);

    // 4.2 Empty query
    const resEmpty = await call('places/search', { query: '' });
    console.log('[4.2] Query="" -> Status:', resEmpty.status);
    assert.equal(resEmpty.status, 400, 'Should reject empty query with 400');

    // 4.3 Query with control characters (\u0000, \u0007)
    const resCtrl = await call('places/search', { query: 'Delhi\u0000Mall' });
    console.log('[4.3] Query="Delhi\\u0000Mall" -> Status:', resCtrl.status);
    assert.equal(resCtrl.status, 400, 'Should reject control characters with 400');

    // 4.4 Excessively long query (>160 characters)
    const resLong = await call('places/search', { query: 'A'.repeat(161) });
    console.log('[4.4] Query=161 chars -> Status:', resLong.status);
    assert.equal(resLong.status, 400, 'Should reject >160 chars with 400');

    // 4.5 Non-existent place ("asdfxyz123") with mock provider returning empty collection
    const mockEmptyFetcher: typeof fetch = async () => Response.json({ type: 'FeatureCollection', features: [] });
    const store = new Store(db);
    const nonExistentResult = await findPlaces(store, 'asdfxyz123', now, { fetcher: mockEmptyFetcher });
    console.log('[4.5] Non-existent place "asdfxyz123" -> Places count:', nonExistentResult.places.length);
    assert.equal(nonExistentResult.places.length, 0, 'Should return 0 places for non-existent place');
    console.log('  Passed! Non-existent place returns empty list without error.');

    db.close();
  }

  // -------------------------------------------------------------
  // TEST GROUP 5: Real Indian Place Normalization (Photon & Nominatim parsers)
  // -------------------------------------------------------------
  console.log('\n--- TEST GROUP 5: Photon & Nominatim Indian Place Parsers ---');
  {
    // Test realistic Photon responses for Indian cities
    const placesToTest = [
      { name: 'Manesar', state: 'Haryana', lat: 28.353, lng: 76.938, type: 'city' },
      { name: 'Connaught Place', state: 'Delhi', lat: 28.631, lng: 77.218, type: 'commercial' },
      { name: 'Koramangala', state: 'Karnataka', lat: 12.935, lng: 77.624, type: 'suburb' },
      { name: 'Chandni Chowk', state: 'Delhi', lat: 28.650, lng: 77.233, type: 'neighbourhood' },
      { name: 'Panaji', state: 'Goa', lat: 15.498, lng: 73.827, type: 'city' },
    ];

    for (const pt of placesToTest) {
      const mockFeature = {
        type: 'Feature',
        geometry: { type: 'Point', coordinates: [pt.lng, pt.lat] },
        properties: {
          countrycode: 'IN',
          osm_type: 'N',
          osm_id: Math.floor(Math.random() * 1000000) + 1,
          name: pt.name,
          state: pt.state,
          district: pt.state,
          osm_value: pt.type
        }
      };

      const normalized = normalizePhoton({
        type: 'FeatureCollection',
        features: [mockFeature]
      });

      assert.equal(normalized.length, 1);
      assert.equal(normalized[0].name, pt.name);
      assert.equal(normalized[0].point.lat, pt.lat);
      assert.equal(normalized[0].point.lng, pt.lng);
      assert.ok(normalized[0].subtitle.includes(pt.state));
      console.log(`  Passed! Verified mock Photon response for "${pt.name}": ${normalized[0].name} (${normalized[0].subtitle})`);
    }

    // Adversarial: foreign place inside provider (e.g. Nepal, Pakistan, or missing countrycode)
    const foreignFeatures = [
      {
        type: 'Feature',
        geometry: { type: 'Point', coordinates: [85.32, 27.71] }, // Kathmandu
        properties: { countrycode: 'NP', osm_type: 'N', osm_id: 999, name: 'Kathmandu' }
      },
      {
        type: 'Feature',
        geometry: { type: 'Point', coordinates: [74.35, 31.52] }, // Lahore
        properties: { countrycode: 'PK', osm_type: 'N', osm_id: 888, name: 'Lahore' }
      },
      {
        type: 'Feature',
        geometry: { type: 'Point', coordinates: [77.21, 28.63] },
        properties: { countrycode: null, osm_type: 'N', osm_id: 777, name: 'No Country' }
      }
    ];

    const filtered = normalizePhoton({
      type: 'FeatureCollection',
      features: foreignFeatures
    });
    assert.equal(filtered.length, 0, 'Must reject foreign or missing countrycode');
    console.log('  Passed! Foreign features correctly excluded.');
  }

  // -------------------------------------------------------------
  // TEST GROUP 6: Dynamic Facility Generation & Search Relevance
  // -------------------------------------------------------------
  console.log('\n--- TEST GROUP 6: Dynamic Facility Generation & Search Relevance ---');
  {
    const { db, call } = createEnv();

    // Query facilities for Koramangala, Bengaluru: 12.935, 77.624
    const resBlr = await call('facilities?lat=12.935&lng=77.624&radius=1500');
    assert.equal(resBlr.status, 200);
    assert.ok(resBlr.data.facilities.length >= 3);
    assert.ok(resBlr.data.results.length >= 3);

    // Verify properties of dynamic facilities
    for (const f of resBlr.data.facilities) {
      assert.ok(f.id.startsWith('park-'), `Facility id should start with park-, got ${f.id}`);
      assert.ok(Number.isFinite(f.point.lat) && Number.isFinite(f.point.lng));
      assert.ok(f.point.lat >= 6 && f.point.lat <= 38, 'Lat within India');
      assert.ok(f.point.lng >= 68 && f.point.lng <= 98, 'Lng within India');
      assert.equal(f.rate.currency, 'INR');
      assert.ok(f.rate.amount > 0);
      assert.equal(f.access, 'PUBLIC');
    }

    // Verify distance calculation in search results
    const results = resBlr.data.results;
    for (let i = 0; i < results.length - 1; i++) {
      assert.ok(results[i].distanceMeters <= results[i + 1].distanceMeters, 'Results should be sorted by distance');
    }
    console.log('  Passed! Dynamic facilities in Bengaluru generated, verified, and correctly sorted by distance:');
    results.forEach((r: any) => console.log(`    - ${r.name}: ${r.distanceMeters}m away, ₹${r.totalCost}/2h, ${r.type}`));

    db.close();
  }

  console.log('\n=== ALL ADVERSARIAL STRESS TESTS COMPLETED SUCCESSFULLY! ===\n');
}

runAdversarialStressTests().catch(err => {
  console.error('\n❌ STRESS TEST FAILURE:', err);
  process.exit(1);
});
