import test from 'node:test';
import assert from 'node:assert/strict';
import { normalizePhoton, photonUrl, findPlaces, type GeocodingOptions } from '../lib/geocoding.ts';
import { coordinatePlace, mapsSearchUrl, normalizePlaceQuery, placeZoom } from '../lib/places.ts';
import { navigationUrl } from '../lib/domain.ts';
import { TestDatabase } from './sqlite-adapter.ts';
import { Store } from '../lib/store.ts';
import { handleApi } from '../lib/service.ts';

// Synthetic provider fixtures are only test data, never a shipped place catalogue.
const now=Date.parse('2026-10-19T00:00:00Z');
const feature=(properties:Record<string,unknown>={},coordinates:unknown[]=[76.94,28.39])=>({type:'Feature',geometry:{type:'Point',coordinates},properties:{countrycode:'IN',osm_type:'R',osm_id:12345,name:'Test village',state:'Haryana',county:'Gurugram',osm_value:'village',...properties}});
const collection=(features:unknown[]= [feature()])=>({type:'FeatureCollection',features});
const success:typeof fetch=async()=>Response.json(collection());
async function fixture(){const db=new TestDatabase(),store=new Store(db);await store.seed();return{db,store};}

test('India geocoder maps coordinates in longitude, latitude order and preserves provenance',()=>{
  const [p]=normalizePhoton(collection());assert.deepEqual(p.point,{lat:28.39,lng:76.94});assert.equal(p.sourceUrl,'https://www.openstreetmap.org/relation/12345');assert.equal(p.subtitle,'Gurugram · Haryana · India');assert.equal(p.kind,'village');
});
test('Country code filtering rejects foreign or missing-country results inside India bounding box',()=>{
  assert.equal(normalizePhoton(collection([feature({countrycode:'NP'}),feature({countrycode:undefined})])).length,0);
});
test('Malformed and out-of-region coordinates are discarded',()=>{
  assert.equal(normalizePhoton(collection([feature({},[NaN,28]),feature({},['77',28]),feature({},[200,28]),feature({},[77,0])])).length,0);
});
test('Provider source URLs are constructed from validated OSM identities',()=>{
  assert.equal(normalizePhoton(collection([feature({osm_type:'javascript:'}),feature({osm_id:-1}),feature({osm_id:'1'}),feature({osm_id:1.5})])).length,0);
});
test('Duplicates are removed and provider results are bounded',()=>{
  const all=Array.from({length:30},(_,i)=>feature({osm_id:i+1}));assert.equal(normalizePhoton(collection([all[0],...all])).length,8);
});
test('Unicode names survive without fabricated transliteration',()=>{
  assert.equal(normalizePhoton(collection([feature({name:'परीक्षण गाँव'})]))[0].name,'परीक्षण गाँव');
});
test('A house address without a name retains its street and house number',()=>{
  assert.equal(normalizePhoton(collection([feature({name:undefined,street:'Test Road',housenumber:'42'})]))[0].name,'42 Test Road');
});
test('Non-GeoJSON responses fail explicitly instead of inventing places',()=>{
  assert.throws(()=>normalizePhoton({results:[]}),/unreadable/);assert.throws(()=>normalizePhoton({type:'FeatureCollection',features:null}),/unreadable/);
});
test('Photon request uses India country filter and supported response language',()=>{
  const url=photonUrl(undefined,'  मुंबई   ');assert.equal(url.origin,'https://photon.komoot.io');assert.equal(url.searchParams.get('countrycode'),'IN');assert.equal(url.searchParams.get('lang'),'en');assert.equal(url.searchParams.get('q'),'मुंबई');assert.equal(url.searchParams.get('limit'),'8');
});
test('Provider configuration rejects insecure and credential-bearing URLs',()=>{
  for(const base of ['http://example.test','https://user:secret@example.test','https://example.test?q=private','invalid'])assert.throws(()=>photonUrl(base,'Delhi'));
  assert.equal(photonUrl('https://example.test/geocoder','Delhi').pathname,'/geocoder/api/');
});
test('Manual coordinates support mainland and island locations without treating place text as coordinates',()=>{
  assert.deepEqual(coordinatePlace('11.67, 92.74')?.point,{lat:11.67,lng:92.74});assert.equal(coordinatePlace(' , '),null);assert.equal(coordinatePlace('Delhi, India'),null);assert.equal(coordinatePlace('77, 28'),null);assert.equal(coordinatePlace('NaN,77'),null);
});
test('Search normalization handles whitespace and compatibility characters',()=>{
  assert.equal(normalizePlaceQuery('  Ｄｅｌｈｉ   India  '),'Delhi India');
});
test('Google Maps directions use the exact selected origin/destination and requested travel mode',()=>{
  const url=new URL(navigationUrl({lat:11.67,lng:92.74},'driving',{lat:28.39,lng:76.94}));assert.equal(url.searchParams.get('destination'),'11.67,92.74');assert.equal(url.searchParams.get('origin'),'28.39,76.94');assert.equal(url.searchParams.get('travelmode'),'driving');assert.equal(new URL(navigationUrl({lat:28,lng:77},'walking')).searchParams.has('origin'),false);
});
test('Unresolved place fallback escapes query delimiters instead of injecting URL options',()=>{
  const url=new URL(mapsSearchUrl('Delhi & api=bad'));assert.equal(url.searchParams.get('api'),'1');assert.equal(url.searchParams.get('query'),'Delhi & api=bad, India');
});
test('Map zoom adapts from state to village to exact point',()=>{
  assert.ok(placeZoom('state')<placeZoom('village'));assert.ok(placeZoom('village')<placeZoom('point'));
});
test('Public result cache avoids repeated upstream calls and does not store query text',async()=>{
  const {db,store}=await fixture();let calls=0;const fetcher:typeof fetch=async()=>{calls++;return Response.json(collection());};
  const first=await findPlaces(store,'Private query example',now,{fetcher});const second=await findPlaces(store,'Private query example',now+1,{fetcher});assert.equal(first.cached,false);assert.equal(second.cached,true);assert.equal(calls,1);
  const rows=db.raw.prepare('SELECT * FROM geocode_cache').all();assert.equal(JSON.stringify(rows).includes('Private query example'),false);assert.equal(String(rows[0].key).length,64);db.close();
});
test('Distinct provider requests share an atomic spacing gate',async()=>{
  const {db,store}=await fixture();await findPlaces(store,'First place',now,{fetcher:success});await assert.rejects(findPlaces(store,'Second place',now+500,{fetcher:success}),/Wait a moment/);assert.equal((await findPlaces(store,'Second place',now+1200,{fetcher:success})).places.length,1);db.close();
});
test('Expired place cache is fetched again; empty results have a shorter cache',async()=>{
  const {db,store}=await fixture();let calls=0;const fetcher:typeof fetch=async()=>{calls++;return Response.json(collection([]));};await findPlaces(store,'No such place',now,{fetcher});await findPlaces(store,'No such place',now+1000,{fetcher});await findPlaces(store,'No such place',now+300001,{fetcher});assert.equal(calls,2);db.close();
});
test('Provider HTTP failure is sanitized and not cached',async()=>{
  const {db,store}=await fixture();await assert.rejects(findPlaces(store,'Address',now,{fetcher:async()=>new Response('secret upstream error',{status:500})}),/could not connect/);assert.equal(db.raw.prepare('SELECT count(*) n FROM geocode_cache').get()?.n,0);db.close();
});
test('Provider throttling returns a recoverable message without endpoint leakage',async()=>{
  const {db,store}=await fixture();await assert.rejects(findPlaces(store,'Address',now,{fetcher:async()=>new Response('',{status:429})}),/provider is busy/);db.close();
});
test('Timeout aborts provider lookup and leaves catalogue search independent',async()=>{
  const {db,store}=await fixture();const fetcher:typeof fetch=async(_url,options)=>new Promise((_resolve,reject)=>options?.signal?.addEventListener('abort',()=>reject(new Error('timeout'))));await assert.rejects(findPlaces(store,'Address',now,{fetcher,timeoutMs:5}),/could not connect/);assert.equal((await store.facilities()).length,5);db.close();
});
test('Oversized provider body is rejected before JSON parsing',async()=>{
  const {db,store}=await fixture();await assert.rejects(findPlaces(store,'Address',now,{fetcher:async()=>new Response('x',{headers:{'content-length':'600000'}})}),/could not connect/);db.close();
});
test('Geocoding API enforces same-origin, strict input and caller rate limit',async()=>{
  const {db}=await fixture();let calls=0;const geocoding:GeocodingOptions={fetcher:async()=>{calls++;return Response.json(collection());}};
  const call=async(body:unknown,origin='https://park.test')=>handleApi(new Request('https://park.test/api/v1/places/search',{method:'POST',headers:{Origin:origin,'Content-Type':'application/json'},body:JSON.stringify(body)}),{db,identity:null,allowBootstrap:false,rateKey:'test',now,geocoding});
  assert.equal((await call({query:'Delhi'},'https://foreign.test')).status,403);assert.equal((await call({query:'a'})).status,400);assert.equal((await call({query:'Delhi',provider:'https://bad.test'})).status,400);
  for(let i=0;i<20;i++)assert.equal((await call({query:'Delhi'})).status,200);assert.equal((await call({query:'Delhi'})).status,429);assert.equal(calls,1);db.close();
});
test('Cache pruning removes expired public lookups',async()=>{
  const {db,store}=await fixture();await findPlaces(store,'Address',now,{fetcher:success});await store.prune(now+8*86400000);assert.equal(db.raw.prepare('SELECT count(*) n FROM geocode_cache').get()?.n,0);db.close();
});
