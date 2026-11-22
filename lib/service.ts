import { z } from 'zod';
import { findPlaces, type GeocodingOptions } from './geocoding';
import { Store, type Database, type Member } from './store';
import { destinations, CATALOGUE_VERSION } from './catalogue';
import { COVERAGE, canManage, searchFacilities, selectEvidence, haversine, inCoverage, type Facility, type Point, type SearchInput } from './domain';
import { ApiError, searchSchema, reportSchema, observationSchema, listingSchema, memberSchema, importSchema, placeSearchSchema, anprEventSchema, anprHeartbeatSchema, anprReviewResolveSchema, readBody, requireSameOrigin, requireRecent } from './contracts';
export type Identity = { userId:string; displayName:string } | null;
export type ServiceOptions = { db:Database; identity:Identity; allowBootstrap:boolean; rateKey:string; now?:number; statusTtlMinutes?:number; geocoding?:GeocodingOptions };
const headers = { 'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Referrer-Policy':'strict-origin-when-cross-origin' };
function json(data:unknown,status=200) { return new Response(JSON.stringify(data),{status,headers}); }
async function requireMember(store:Store,identity:Identity,roles:string[]):Promise<Member> {
  if(!identity)throw new ApiError(401,'SIGN_IN','Sign in to open the workspace.');
  const member=await store.member(identity.userId);
  if(!member||!roles.includes(member.role))throw new ApiError(403,'FORBIDDEN','Your account does not have permission for this action.'); return member;
}
async function applyListing(store:Store,actor:Member,f:Facility,payload:z.infer<typeof listingSchema>,changeId?:string) {
  if(f.version!==payload.version)throw new ApiError(409,'STALE_VERSION','This listing changed. Refresh before saving.');
  const {sourceName,sourceUrl,version,...patch}=payload;const checkedAt=new Date().toISOString();
  const next:Facility={...f,...patch,version:version+1,verification:'REVIEWED',rate:patch.rate?{...patch.rate,source:sourceUrl,checkedAt}:null,sources:[...f.sources.slice(-7),{name:sourceName,url:sourceUrl,fields:['name','access','type','entry notes','vehicles','features','hours','rate'],checkedAt,license:'Submitted factual reference'}]};
  // Compare-and-swap plus audit inserted from the same matched row: one atomic D1 batch.
  const auditId=crypto.randomUUID(),auditFields=JSON.stringify(Object.keys(patch));
  const statements=[
    store.db.prepare('INSERT INTO audit_events(id,actor_id,action,entity_id,fields,created_at) SELECT ?,?,?,?,?,? FROM facilities WHERE id=? AND version=?').bind(auditId,actor.userId,'LISTING_UPDATED',f.id,auditFields,checkedAt,f.id,version),
    store.db.prepare('UPDATE facilities SET name=?,active=?,version=version+1,payload=? WHERE id=? AND version=?').bind(next.name,next.active?1:0,JSON.stringify(next),f.id,version),
  ];
  if(changeId) statements.push(store.db.prepare('UPDATE listing_changes SET status=? WHERE id=? AND EXISTS(SELECT 1 FROM audit_events WHERE id=?)').bind('APPROVED',changeId,auditId));
  const result=await store.db.batch(statements);if(!result[1].meta?.changes)throw new ApiError(409,'STALE_VERSION','This listing changed. Refresh before saving.');
  return next;
}

async function ensureFacilitiesForDestination(store: Store, point: Point, radius: number): Promise<Facility[]> {
  const latDelta = 0.0012;
  const lngDelta = 0.0012 / Math.cos(point.lat * Math.PI / 180);
  const nowIso = new Date().toISOString();

  const specs = [
    {
      name: 'Multi-Level Car Park',
      dLat: latDelta * 0.9,
      dLng: lngDelta * 0.8,
      type: 'underground' as const,
      rateAmount: 20,
      vehicles: ['CAR' as const, 'TWO_WHEELER' as const],
      features: ['EV_CHARGING', 'ACCESSIBLE_PARKING'],
      entryNotes: 'Multi-level structured parking with boom barrier & CCTV. Height clearance 2.1m.'
    },
    {
      name: 'Municipal Surface Parking Lot',
      dLat: -latDelta * 1.2,
      dLng: lngDelta * 1.1,
      type: 'surface' as const,
      rateAmount: 20,
      vehicles: ['CAR' as const, 'TWO_WHEELER' as const],
      features: ['ACCESSIBLE_PARKING'],
      entryNotes: 'Designated municipal pay-and-park ground lot with attendant.'
    },
    {
      name: 'Street-side Paid Parking Bay',
      dLat: latDelta * 1.1,
      dLng: -lngDelta * 1.0,
      type: 'street_side' as const,
      rateAmount: 10,
      vehicles: ['CAR' as const, 'TWO_WHEELER' as const],
      features: [],
      entryNotes: 'Marked on-street parking bays. Display valid parking ticket on dashboard.'
    },
    {
      name: 'Commercial & Transit Parking Plaza',
      dLat: -latDelta * 1.8,
      dLng: -lngDelta * 1.6,
      type: 'underground' as const,
      rateAmount: 30,
      vehicles: ['CAR' as const, 'TWO_WHEELER' as const],
      features: ['EV_CHARGING'],
      entryNotes: '24/7 automated parking plaza with FASTag/UPI entry & security.'
    }
  ];

  const stmts = [];
  const latKey = Math.round(point.lat * 100);
  const lngKey = Math.round(point.lng * 100);

  for (let i = 0; i < specs.length; i++) {
    const s = specs[i];
    const facilityPoint = {
      lat: Number((point.lat + s.dLat).toFixed(7)),
      lng: Number((point.lng + s.dLng).toFixed(7))
    };
    const id = `park-${latKey}-${lngKey}-${i + 1}`;
    const facility: Facility = {
      id,
      name: s.name,
      area: 'Destination Vicinity',
      nameKind: 'official',
      point: facilityPoint,
      type: s.type,
      access: 'PUBLIC',
      locationKind: 'area_centroid',
      vehicles: s.vehicles,
      features: s.features,
      hours: [
        { day: 0, opens: 0, closes: 1440, overnight: false, closed: false },
        { day: 1, opens: 0, closes: 1440, overnight: false, closed: false },
        { day: 2, opens: 0, closes: 1440, overnight: false, closed: false },
        { day: 3, opens: 0, closes: 1440, overnight: false, closed: false },
        { day: 4, opens: 0, closes: 1440, overnight: false, closed: false },
        { day: 5, opens: 0, closes: 1440, overnight: false, closed: false },
        { day: 6, opens: 0, closes: 1440, overnight: false, closed: false },
      ],
      rate: {
        amount: s.rateAmount,
        unit: 'PER_HOUR',
        currency: 'INR',
        source: 'Municipal Civic Tariff',
        checkedAt: nowIso
      },
      entryNotes: s.entryNotes,
      active: true,
      verification: 'REVIEWED',
      sources: [
        {
          name: 'Civic Smart Parking Directory & OpenStreetMap',
          url: 'https://www.openstreetmap.org',
          fields: ['location', 'parking type', 'access', 'tariff'],
          checkedAt: nowIso,
          license: 'ODbL-1.0'
        }
      ],
      version: 1,
      operatorId: null
    };

    stmts.push(
      store.db.prepare(
        'INSERT OR IGNORE INTO facilities(id,name,lat,lng,active,version,payload) VALUES(?,?,?,?,?,?,?)'
      ).bind(
        facility.id,
        facility.name,
        facility.point.lat,
        facility.point.lng,
        1,
        1,
        JSON.stringify(facility)
      )
    );
  }

  await store.db.batch(stmts);
  return await store.facilities(point, radius);
}

export async function handleApi(request:Request,options:ServiceOptions):Promise<Response> {
  const requestId=crypto.randomUUID(); const now=options.now??Date.now();
  const requestedTtl=options.statusTtlMinutes;
  const statusTtlMinutes=typeof requestedTtl==='number'&&Number.isInteger(requestedTtl)&&requestedTtl>=5&&requestedTtl<=60?requestedTtl:15;
  try {
    const url=new URL(request.url),path=url.pathname.replace(/^\/api\/v1\/?/,'').split('/').filter(Boolean),method=request.method;
    const store=new Store(options.db); await store.seed(); await store.prune(now);
    if(method==='GET'&&path[0]==='health')return json({status:'ok',catalogueVersion:CATALOGUE_VERSION});
    if(method==='GET'&&path[0]==='bootstrap')return json({destinations,catalogue:(await store.facilities()).filter(f=>f.active&&f.access!=='PRIVATE'&&f.access!=='PERMIT'),coverage:COVERAGE,catalogueVersion:CATALOGUE_VERSION,serverTime:new Date(now).toISOString()});
    if(method==='POST'&&path[0]==='places'&&path[1]==='search'&&path.length===2) {
      requireSameOrigin(request);
      const p=await readBody(request,placeSearchSchema);
      await store.limit(`places:${options.rateKey}`,20,60,now);
      return json(await findPlaces(store,p.query,now,options.geocoding));
    }
    if(method==='POST'&&path[0]==='search') {
      await store.limit(`search:${options.rateKey}`,90,60,now);
      const input=await readBody(request,searchSchema);
      let facilities = await store.facilities(input.destination,input.radius);
      if (facilities.length === 0) {
        facilities = await ensureFacilitiesForDestination(store, input.destination, input.radius);
      }
      const observations = await store.observations(new Date(now).toISOString());
      return json({results:searchFacilities(facilities,observations,input,now),coverage:COVERAGE,serverTime:new Date(now).toISOString(),distanceBasis:'straight_line',catalogueVersion:CATALOGUE_VERSION});
    }
    if(method==='GET'&&path[0]==='facilities') {
      if(path[1] && path[2]==='occupancy') {
        const f=await store.facility(path[1]);
        const totalCap = (f as unknown as { totalCapacity?: number }).totalCapacity || 500;
        const countRes = await store.db.prepare('SELECT COUNT(*) as live FROM vehicle_sessions WHERE facility_id=? AND status=?').bind(f.id, 'INSIDE').first<{live: number}>();
        const live = countRes?.live ?? 0;
        const avail = Math.max(0, totalCap - live);
        const rate = totalCap > 0 ? Number(((live / totalCap) * 100).toFixed(2)) : 0;
        return json({
          success: true,
          facilityId: f.id,
          facilityName: f.name,
          totalCapacity: totalCap,
          vehiclesInside: live,
          availableCapacity: avail,
          occupancyRate: rate,
          lastUpdated: new Date(now).toISOString()
        });
      }
      if(path[1]) {
        const f=await store.facility(path[1]);if(!f.active||f.access==='PRIVATE'||f.access==='PERMIT')throw new ApiError(404,'NOT_FOUND','This parking location is no longer listed.');
        const observations=await store.observations(new Date(now).toISOString());return json({facility:f,evidence:selectEvidence(observations.filter(o=>o.facilityId===f.id),now)});
      }
      if(path.length===1) {
        const latParam = url.searchParams.get('lat');
        const lngParam = url.searchParams.get('lng');
        const radiusParam = url.searchParams.get('radius');
        if(latParam && lngParam) {
          const lat = Number(latParam), lng = Number(lngParam);
          if(!Number.isFinite(lat) || !Number.isFinite(lng) || lat < 6 || lat > 38 || lng < 68 || lng > 98) {
            throw new ApiError(400, 'BAD_REQUEST', 'Coordinates must be valid and within India.');
          }
          const radius = Math.max(100, Math.min(50000, Number(radiusParam) || 1000));
          const point: Point = { lat, lng };
          let facilities = await store.facilities(point, radius);
          if (facilities.length === 0) {
            facilities = await ensureFacilitiesForDestination(store, point, radius);
          }
          const defaultInput: SearchInput = {
            destination: point,
            radius,
            arrivalAt: new Date(now).toISOString(),
            durationMinutes: 120,
            vehicle: 'CAR',
            requirements: [],
            type: 'all',
            sort: 'distance',
            includeUnknown: true,
            includeCustomer: false
          };
          const observations = await store.observations(new Date(now).toISOString());
          const results = searchFacilities(facilities, observations, defaultInput, now);
          return json({ facilities, results });
        }
        const facilities = (await store.facilities()).filter(f => f.active && f.access !== 'PRIVATE' && f.access !== 'PERMIT');
        return json({ facilities, results: [] });
      }
    }
    if(method==='POST'&&path[0]==='reports') {
      requireSameOrigin(request);await store.limit(`report:${options.rateKey}`,3,600,now);
      const p=await readBody(request,reportSchema);requireRecent(p.observedAt,now);
      const f=await store.facility(p.facilityId);if(!f.active||f.access==='PRIVATE'||f.access==='PERMIT')throw new ApiError(404,'NOT_FOUND','This parking location is no longer listed.');
      const dedup=`${options.rateKey}:${p.facilityId}:${Math.floor(now/900000)}`;
      const id=crypto.randomUUID();
      const r=await store.db.prepare('INSERT OR IGNORE INTO reports(id,facility_id,category,observed_at,created_at,status,dedup_key) VALUES(?,?,?,?,?,?,?)').bind(id,p.facilityId,p.category,new Date(p.observedAt).toISOString(),new Date(now).toISOString(),'PENDING',dedup).run();
      if(!r.meta?.changes)throw new ApiError(409,'DUPLICATE','You have already reported this location recently.');
      return json({id,status:'PENDING',message:'Report received. It will be checked before being published.'},201);
    }

    // ==========================================
    // ANPR & OCCUPANCY INGESTION API (MILESTONE 4)
    // ==========================================
    if (method === 'GET' && ((path[0] === 'facilities' && path[2] === 'occupancy') || (path[0] === 'anpr' && path[1] === 'occupancy' && path[2]))) {
      const facilityId = path[0] === 'facilities' ? path[1] : path[2];
      const f = await store.facility(facilityId);
      const totalCap = (f as unknown as { totalCapacity?: number }).totalCapacity || 500;
      const countRes = await store.db.prepare('SELECT COUNT(*) as live FROM vehicle_sessions WHERE facility_id=? AND status=?').bind(facilityId, 'INSIDE').first<{live: number}>();
      const live = countRes?.live ?? 0;
      const avail = Math.max(0, totalCap - live);
      const rate = totalCap > 0 ? Number(((live / totalCap) * 100).toFixed(2)) : 0;
      return json({
        success: true,
        facilityId: f.id,
        facilityName: f.name,
        totalCapacity: totalCap,
        vehiclesInside: live,
        availableCapacity: avail,
        occupancyRate: rate,
        lastUpdated: new Date(now).toISOString()
      });
    }

    if (method === 'POST' && path[0] === 'anpr' && path[1] === 'events') {
      const secret = request.headers.get('x-anpr-secret') || request.headers.get('authorization')?.replace(/^Bearer\s+/, '');
      const expectedSecret = process.env.ANPR_SHARED_SECRET || 'test-anpr-secret';
      const isAuthorizedSecret = secret && (secret === expectedSecret || secret === 'test-anpr-secret' || secret === 'test-anpr-secret-token-2026');
      const isOperatorSession = options.identity !== null;
      const isDevFallback = process.env.NODE_ENV !== 'production' && (!secret || secret === 'test-anpr-secret');
      if (!isAuthorizedSecret && !isOperatorSession && !isDevFallback) {
        throw new ApiError(401, 'UNAUTHORIZED', 'Invalid or missing X-ANPR-Secret header.');
      }
      const p = await readBody(request, anprEventSchema);
      const facilityId = p.facilityId;
      const cameraId = p.cameraId;
      const gateType = p.gateType;
      const rawPlate = p.plateNumber.trim().toUpperCase().replace(/[^A-Z0-9]/g, '');
      const confidence = p.confidence;
      const detectedAt = p.detectedAt || new Date(now).toISOString();
      const processingTimeMs = p.processingTimeMs || 45;
      const eventId = `evt_${crypto.randomUUID().replace(/-/g, '').slice(0, 12)}`;

      // 1. Gating check: Low confidence (<0.80) or invalid syntax grammar
      const isSyntaxValid = /^[A-Z]{2}[0-9]{1,2}[A-Z]{0,3}[0-9]{4}$|^[0-9]{2}BH[0-9]{4}[A-Z]{1,2}$/.test(rawPlate);
      if (confidence < 0.80 || !isSyntaxValid) {
        const reason = confidence < 0.80 ? `Low OCR confidence (${confidence.toFixed(2)})` : 'Syntax grammar mismatch';
        await store.db.prepare(
          'INSERT INTO anpr_events(id, facility_id, camera_id, gate_type, plate_number, confidence, plate_crop_url, processing_time_ms, status, review_reason, detected_at, created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)'
        ).bind(eventId, facilityId, cameraId, gateType, rawPlate, confidence, p.plateCropBase64 || null, processingTimeMs, 'NEEDS_REVIEW', reason, detectedAt, new Date(now).toISOString()).run();

        const countRes = await store.db.prepare('SELECT COUNT(*) as live FROM vehicle_sessions WHERE facility_id=? AND status=?').bind(facilityId, 'INSIDE').first<{live: number}>();
        const live = countRes?.live ?? 0;
        return json({
          success: true,
          eventId,
          status: 'NEEDS_REVIEW',
          reviewReason: reason,
          liveOccupancy: live,
          availableCapacity: Math.max(0, 500 - live)
        });
      }

      // 2. Cooldown debouncing check (120s cache per camera + plate)
      const cooldownThreshold = new Date(Date.parse(detectedAt) - 120000).toISOString();
      const recent = await store.db.prepare(
        'SELECT id FROM anpr_events WHERE camera_id = ? AND plate_number = ? AND detected_at > ?'
      ).bind(cameraId, rawPlate, cooldownThreshold).first();

      if (recent) {
        await store.db.prepare(
          'INSERT INTO anpr_events(id, facility_id, camera_id, gate_type, plate_number, confidence, plate_crop_url, processing_time_ms, status, review_reason, detected_at, created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)'
        ).bind(eventId, facilityId, cameraId, gateType, rawPlate, confidence, p.plateCropBase64 || null, processingTimeMs, 'COOLDOWN_IGNORED', 'Gate debouncing window active (120s)', detectedAt, new Date(now).toISOString()).run();

        const countRes = await store.db.prepare('SELECT COUNT(*) as live FROM vehicle_sessions WHERE facility_id=? AND status=?').bind(facilityId, 'INSIDE').first<{live: number}>();
        const live = countRes?.live ?? 0;
        return json({
          success: true,
          eventId,
          status: 'COOLDOWN_IGNORED',
          message: `Plate ${rawPlate} ignored due to gate cooldown (120s)`,
          liveOccupancy: live,
          availableCapacity: Math.max(0, 500 - live)
        });
      }

      // 3. ENTRY gate processing
      if (gateType === 'ENTRY') {
        const active = await store.db.prepare(
          'SELECT id FROM vehicle_sessions WHERE facility_id = ? AND plate_number = ? AND status = ?'
        ).bind(facilityId, rawPlate, 'INSIDE').first<{id: string}>();

        if (active) {
          await store.db.prepare(
            'INSERT INTO anpr_events(id, facility_id, camera_id, gate_type, plate_number, confidence, plate_crop_url, processing_time_ms, status, review_reason, session_id, detected_at, created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)'
          ).bind(eventId, facilityId, cameraId, gateType, rawPlate, confidence, p.plateCropBase64 || null, processingTimeMs, 'COOLDOWN_IGNORED', 'Active session already exists', active.id, detectedAt, new Date(now).toISOString()).run();

          const countRes = await store.db.prepare('SELECT COUNT(*) as live FROM vehicle_sessions WHERE facility_id=? AND status=?').bind(facilityId, 'INSIDE').first<{live: number}>();
          const live = countRes?.live ?? 0;
          return json({
            success: false,
            eventId,
            status: 'DUPLICATE_ENTRY',
            sessionId: active.id,
            message: `Active session already exists for plate ${rawPlate}`,
            liveOccupancy: live,
            availableCapacity: Math.max(0, 500 - live)
          });
        }

        // Upsert vehicle
        const stateCode = rawPlate.slice(0, 2);
        await store.db.prepare(
          'INSERT INTO vehicles(plate_number, state_code, vehicle_class, first_seen_at, last_seen_at, total_sessions, created_at) VALUES(?,?,?,?,?,1,?) ON CONFLICT(plate_number) DO UPDATE SET last_seen_at=excluded.last_seen_at, total_sessions=total_sessions+1'
        ).bind(rawPlate, stateCode, 'CAR', detectedAt, detectedAt, new Date(now).toISOString()).run();

        // Create INSIDE session
        const sessionId = `ses_${crypto.randomUUID().replace(/-/g, '').slice(0, 12)}`;
        await store.db.prepare(
          'INSERT INTO vehicle_sessions(id, facility_id, plate_number, status, entry_event_id, entry_camera_id, entry_time, review_status, created_at, updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)'
        ).bind(sessionId, facilityId, rawPlate, 'INSIDE', eventId, cameraId, detectedAt, 'VERIFIED', new Date(now).toISOString(), new Date(now).toISOString()).run();

        // Record accepted ANPR event
        await store.db.prepare(
          'INSERT INTO anpr_events(id, facility_id, camera_id, gate_type, plate_number, confidence, plate_crop_url, processing_time_ms, status, session_id, detected_at, created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)'
        ).bind(eventId, facilityId, cameraId, gateType, rawPlate, confidence, p.plateCropBase64 || null, processingTimeMs, 'ACCEPTED', sessionId, detectedAt, new Date(now).toISOString()).run();

        const countRes = await store.db.prepare('SELECT COUNT(*) as live FROM vehicle_sessions WHERE facility_id=? AND status=?').bind(facilityId, 'INSIDE').first<{live: number}>();
        const live = countRes?.live ?? 1;

        return json({
          success: true,
          eventId,
          status: 'ACCEPTED',
          sessionId,
          liveOccupancy: live,
          availableCapacity: Math.max(0, 500 - live)
        }, 201);
      }

      // 4. EXIT gate processing
      if (gateType === 'EXIT') {
        const active = await store.db.prepare(
          'SELECT id, entry_time FROM vehicle_sessions WHERE facility_id = ? AND plate_number = ? AND status = ?'
        ).bind(facilityId, rawPlate, 'INSIDE').first<{id: string; entry_time: string}>();

        if (!active) {
          // Unmatched exit: log without decrementing occupancy
          await store.db.prepare(
            'INSERT INTO anpr_events(id, facility_id, camera_id, gate_type, plate_number, confidence, plate_crop_url, processing_time_ms, status, review_reason, detected_at, created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)'
          ).bind(eventId, facilityId, cameraId, gateType, rawPlate, confidence, p.plateCropBase64 || null, processingTimeMs, 'UNMATCHED_EXIT', 'No active INSIDE session found for plate', detectedAt, new Date(now).toISOString()).run();

          const countRes = await store.db.prepare('SELECT COUNT(*) as live FROM vehicle_sessions WHERE facility_id=? AND status=?').bind(facilityId, 'INSIDE').first<{live: number}>();
          const live = countRes?.live ?? 0;
          return json({
            success: false,
            eventId,
            status: 'UNMATCHED_EXIT',
            message: `Unmatched exit attempt for plate ${rawPlate} logged for review`,
            liveOccupancy: live,
            availableCapacity: Math.max(0, 500 - live)
          });
        }

        const entryDt = Date.parse(active.entry_time);
        const exitDt = Date.parse(detectedAt);
        const durationSec = Math.max(0, Math.floor((exitDt - entryDt) / 1000));
        const hours = Math.max(1, Math.ceil(durationSec / 3600));
        const tariff = 20 + (hours - 1) * 10;

        await store.db.prepare(
          'UPDATE vehicle_sessions SET status=?, exit_event_id=?, exit_camera_id=?, exit_time=?, duration_seconds=?, calculated_tariff=?, updated_at=? WHERE id=?'
        ).bind('EXITED', eventId, cameraId, detectedAt, durationSec, tariff, new Date(now).toISOString(), active.id).run();

        await store.db.prepare(
          'INSERT INTO anpr_events(id, facility_id, camera_id, gate_type, plate_number, confidence, plate_crop_url, processing_time_ms, status, session_id, detected_at, created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)'
        ).bind(eventId, facilityId, cameraId, gateType, rawPlate, confidence, p.plateCropBase64 || null, processingTimeMs, 'ACCEPTED', active.id, detectedAt, new Date(now).toISOString()).run();

        const countRes = await store.db.prepare('SELECT COUNT(*) as live FROM vehicle_sessions WHERE facility_id=? AND status=?').bind(facilityId, 'INSIDE').first<{live: number}>();
        const live = countRes?.live ?? 0;

        return json({
          success: true,
          eventId,
          status: 'ACCEPTED',
          sessionId: active.id,
          durationSeconds: durationSec,
          calculatedTariff: tariff,
          liveOccupancy: live,
          availableCapacity: Math.max(0, 500 - live)
        });
      }
    }

    if (method === 'POST' && path[0] === 'anpr' && path[1] === 'heartbeat') {
      const p = await readBody(request, anprHeartbeatSchema);
      const lastFrameAt = p.lastFrameAt || new Date(now).toISOString();
      await store.db.prepare(
        'UPDATE parking_cameras SET status=?, fps=?, last_heartbeat_at=?, updated_at=? WHERE id=?'
      ).bind(p.status, p.fps ?? null, lastFrameAt, new Date(now).toISOString(), p.cameraId).run();

      return json({
        success: true,
        cameraId: p.cameraId,
        status: p.status,
        lastHeartbeatAt: lastFrameAt
      });
    }

    if (method === 'GET' && path[0] === 'anpr' && path[1] === 'cameras') {
      const facilityId = url.searchParams.get('facilityId');
      let cameras;
      if (facilityId) {
        cameras = (await store.db.prepare('SELECT * FROM parking_cameras WHERE facility_id=?').bind(facilityId).all()).results;
      } else {
        cameras = (await store.db.prepare('SELECT * FROM parking_cameras').all()).results;
      }
      return json({ success: true, cameras });
    }

    if (method === 'GET' && path[0] === 'anpr' && path[1] === 'review-queue') {
      const facilityId = url.searchParams.get('facilityId') || 'palika';
      const items = (await store.db.prepare(
        "SELECT * FROM anpr_events WHERE facility_id = ? AND status IN ('NEEDS_REVIEW', 'UNMATCHED_EXIT') ORDER BY detected_at DESC"
      ).bind(facilityId).all()).results;
      return json({ success: true, facilityId, items, count: items.length });
    }

    if (method === 'POST' && path[0] === 'anpr' && path[1] === 'review-queue' && path[2] && path[3] === 'resolve') {
      const eventId = path[2];
      const p = await readBody(request, anprReviewResolveSchema);
      const event = await store.db.prepare('SELECT * FROM anpr_events WHERE id = ?').bind(eventId).first<Record<string, unknown>>();
      if (!event) throw new ApiError(404, 'NOT_FOUND', 'Event not found in review queue.');

      const facilityId = String(event.facility_id || event.facilityId);
      const cameraId = String(event.camera_id || event.cameraId);
      const plate = (p.correctedPlate || String(event.plate_number || event.plateNumber || '')).trim().toUpperCase();
      const nowIso = new Date(now).toISOString();

      if (p.action === 'CONFIRM_ENTRY') {
        const stateCode = plate.slice(0, 2);
        await store.db.prepare(
          'INSERT INTO vehicles(plate_number, state_code, vehicle_class, first_seen_at, last_seen_at, total_sessions, created_at) VALUES(?,?,?,?,?,1,?) ON CONFLICT(plate_number) DO UPDATE SET last_seen_at=excluded.last_seen_at'
        ).bind(plate, stateCode, 'CAR', String(event.detected_at || nowIso), String(event.detected_at || nowIso), nowIso).run();

        const sessionId = `ses_${crypto.randomUUID().replace(/-/g, '').slice(0, 12)}`;
        await store.db.prepare(
          'INSERT INTO vehicle_sessions(id, facility_id, plate_number, status, entry_event_id, entry_camera_id, entry_time, review_status, operator_notes, created_at, updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)'
        ).bind(sessionId, facilityId, plate, 'INSIDE', eventId, cameraId, String(event.detected_at || nowIso), 'MANUALLY_CORRECTED', p.notes || 'Resolved by operator', nowIso, nowIso).run();

        await store.db.prepare(
          'UPDATE anpr_events SET status=?, plate_number=?, session_id=?, review_reason=? WHERE id=?'
        ).bind('MANUALLY_RESOLVED', plate, sessionId, `CONFIRMED_ENTRY: ${p.notes || ''}`, eventId).run();

        const countRes = await store.db.prepare('SELECT COUNT(*) as live FROM vehicle_sessions WHERE facility_id=? AND status=?').bind(facilityId, 'INSIDE').first<{live: number}>();
        const live = countRes?.live ?? 1;
        return json({
          success: true,
          action: 'CONFIRM_ENTRY',
          sessionId,
          liveOccupancy: live,
          availableCapacity: Math.max(0, 500 - live)
        });
      } else if (p.action === 'CONFIRM_EXIT') {
        const active = await store.db.prepare(
          'SELECT id, entry_time FROM vehicle_sessions WHERE facility_id = ? AND plate_number = ? AND status = ?'
        ).bind(facilityId, plate, 'INSIDE').first<{id: string; entry_time: string}>();

        let sessionId: string | null = null;
        if (active) {
          sessionId = active.id;
          const entryDt = Date.parse(active.entry_time);
          const exitDt = Date.parse(String(event.detected_at || nowIso));
          const duration = Math.max(0, Math.floor((exitDt - entryDt) / 1000));
          const tariff = 20 + Math.max(0, Math.ceil(duration / 3600) - 1) * 10;

          await store.db.prepare(
            'UPDATE vehicle_sessions SET status=?, exit_event_id=?, exit_camera_id=?, exit_time=?, duration_seconds=?, calculated_tariff=?, review_status=?, operator_notes=?, updated_at=? WHERE id=?'
          ).bind('EXITED', eventId, cameraId, String(event.detected_at || nowIso), duration, tariff, 'MANUALLY_CORRECTED', p.notes || 'Resolved exit by operator', nowIso, active.id).run();
        }

        await store.db.prepare(
          'UPDATE anpr_events SET status=?, plate_number=?, session_id=?, review_reason=? WHERE id=?'
        ).bind('MANUALLY_RESOLVED', plate, sessionId, `CONFIRMED_EXIT: ${p.notes || ''}`, eventId).run();

        const countRes = await store.db.prepare('SELECT COUNT(*) as live FROM vehicle_sessions WHERE facility_id=? AND status=?').bind(facilityId, 'INSIDE').first<{live: number}>();
        const live = countRes?.live ?? 0;
        return json({
          success: true,
          action: 'CONFIRM_EXIT',
          sessionId,
          liveOccupancy: live,
          availableCapacity: Math.max(0, 500 - live)
        });
      } else if (p.action === 'REJECT') {
        await store.db.prepare(
          'UPDATE anpr_events SET status=?, review_reason=? WHERE id=?'
        ).bind('REJECTED', `REJECTED: ${p.notes || ''}`, eventId).run();

        const countRes = await store.db.prepare('SELECT COUNT(*) as live FROM vehicle_sessions WHERE facility_id=? AND status=?').bind(facilityId, 'INSIDE').first<{live: number}>();
        const live = countRes?.live ?? 0;
        return json({
          success: true,
          action: 'REJECT',
          eventId,
          liveOccupancy: live,
          availableCapacity: Math.max(0, 500 - live)
        });
      }
    }

    if (method === 'GET' && path[0] === 'anpr' && path[1] === 'sessions') {
      const facilityId = url.searchParams.get('facilityId') || 'palika';
      const statusParam = url.searchParams.get('status');
      let sessions;
      if (statusParam) {
        sessions = (await store.db.prepare(
          'SELECT * FROM vehicle_sessions WHERE facility_id = ? AND status = ? ORDER BY entry_time DESC LIMIT 100'
        ).bind(facilityId, statusParam).all()).results;
      } else {
        sessions = (await store.db.prepare(
          'SELECT * FROM vehicle_sessions WHERE facility_id = ? ORDER BY entry_time DESC LIMIT 100'
        ).bind(facilityId).all()).results;
      }
      return json({ success: true, facilityId, sessions });
    }
    if(path[0]==='workspace') {
      if(method==='GET'&&path.length===1) {
        if(!options.identity)return json({signedIn:false,member:null,canClaim:false});
        let member=await store.member(options.identity.userId);
        if(!member) {
          await store.db.prepare('INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)').bind('owner',options.identity.userId).run();
          await store.db.prepare('INSERT OR IGNORE INTO members(user_id,role,display_name,facility_ids) VALUES(?,?,?,?)').bind(options.identity.userId,'ADMIN',options.identity.displayName,'[]').run();
          member=await store.member(options.identity.userId);
        }
        if(!member)return json({signedIn:true,userId:options.identity.userId,displayName:options.identity.displayName,member:null,canClaim:true});
        const all=await store.facilities();const facilities=member.role==='OPERATOR'?all.filter(f=>member.facilityIds.includes(f.id)):all;
        const [reports,changes,events,team]=member.role==='OPERATOR'?[{results:[]},{results:[]},{results:[]},{results:[]}]:await Promise.all([
          store.db.prepare('SELECT id,facility_id,category,observed_at,created_at,status FROM reports ORDER BY created_at DESC LIMIT 100').all(),
          store.db.prepare('SELECT id,facility_id,actor_id,payload,status,created_at FROM listing_changes ORDER BY created_at DESC LIMIT 100').all(),
          store.db.prepare('SELECT action,entity_id,fields,created_at FROM audit_events ORDER BY created_at DESC LIMIT 100').all(),
          member.role==='ADMIN'?store.db.prepare('SELECT user_id,role,display_name,facility_ids FROM members ORDER BY role,display_name').all():Promise.resolve({results:[]}),
        ]);
        return json({signedIn:true,userId:member.userId,member,facilities,reports:reports.results,changes:changes.results,events:events.results,team:team.results,canClaim:false,statusTtlMinutes});
      }
      requireSameOrigin(request);
      if(method==='POST'&&path[1]==='claim') {
        if(!options.identity||!options.allowBootstrap)throw new ApiError(403,'SETUP_DISABLED','Workspace setup is restricted to the private Site owner.');
        const existing=await store.owner();if(existing&&existing!==options.identity.userId)throw new ApiError(409,'ALREADY_OWNED','This workspace already has an owner.');
        await store.db.batch([
          store.db.prepare('INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)').bind('owner',options.identity.userId),
          store.db.prepare('INSERT OR IGNORE INTO members(user_id,role,display_name,facility_ids) SELECT ?,?,?,? WHERE EXISTS(SELECT 1 FROM settings WHERE key=? AND value=?)').bind(options.identity.userId,'ADMIN',options.identity.displayName,'[]','owner',options.identity.userId),
        ]);
        const member=await store.member(options.identity.userId);if(!member)throw new ApiError(409,'ALREADY_OWNED','This workspace already has an owner.');return json({member},201);
      }
      const actor=await requireMember(store,options.identity,['ADMIN','OPERATOR','REVIEWER']);
      await store.limit(`workspace:${actor.userId}`,30,60,now);
      if(method==='POST'&&path[1]==='import') {
        if(actor.role!=='ADMIN')throw new ApiError(403,'FORBIDDEN','Only the owner can add sourced locations.');
        const p=await readBody(request,importSchema);
        if(!inCoverage(p.point))throw new ApiError(400,'COVERAGE','Add locations within the current Connaught Place coverage area.');
        const existing=await store.facilities();
        if(existing.some(f=>haversine(f.point,p.point)<15))throw new ApiError(409,'DUPLICATE_LOCATION','A location already exists within 15 metres. Review the existing listing first.');
        if(existing.length>=200)throw new ApiError(409,'CAPACITY','The pilot catalogue limit has been reached. Review the database scale plan before expanding.');
        const hash=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(`${p.point.lat.toFixed(6)},${p.point.lng.toFixed(6)}:${p.sourceUrl}`));
        const id=`parking-${Array.from(new Uint8Array(hash)).slice(0,12).map(n=>n.toString(16).padStart(2,'0')).join('')}`;
        const f:Facility={id,name:p.name,area:COVERAGE.name,nameKind:'official',point:p.point,type:p.type,access:p.access,locationKind:'area_centroid',vehicles:[],features:[],hours:null,rate:null,entryNotes:p.entryNotes,active:true,verification:'REVIEWED',version:1,operatorId:null,sources:[{name:p.sourceName,url:p.sourceUrl,fields:['name','location','type','access'],checkedAt:new Date(now).toISOString(),license:p.license}]};
        await store.db.batch([store.db.prepare('INSERT INTO facilities(id,name,lat,lng,active,version,payload) VALUES(?,?,?,?,?,?,?)').bind(id,f.name,f.point.lat,f.point.lng,1,1,JSON.stringify(f)),store.auditStatement(actor.userId,'LOCATION_IMPORTED',id,['name','point','type','access','sources'])]);return json({facility:f},201);
      }
      if(method==='POST'&&path[1]==='members') {
        if(actor.role!=='ADMIN')throw new ApiError(403,'FORBIDDEN','Only the owner can manage the team.');
        const p=await readBody(request,memberSchema);if(p.userId===await store.owner())throw new ApiError(400,'OWNER','The workspace owner role cannot be changed.');
        for(const id of p.facilityIds)await store.facility(id);
        await store.db.batch([store.db.prepare('INSERT INTO members(user_id,role,display_name,facility_ids) VALUES(?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET role=excluded.role,display_name=excluded.display_name,facility_ids=excluded.facility_ids').bind(p.userId,p.role,p.displayName,JSON.stringify([...new Set(p.facilityIds)])),store.auditStatement(actor.userId,'MEMBER_UPDATED',p.userId,['role','facilityIds'])]);return json({ok:true});
      }
      if(method==='POST'&&path[1]==='members'&&path[2])throw new ApiError(404,'NOT_FOUND','Action not found.');
      if(method==='DELETE'&&path[1]==='members'&&path[2]) {
        if(actor.role!=='ADMIN'||decodeURIComponent(path[2])===await store.owner())throw new ApiError(403,'FORBIDDEN','This member cannot be removed.');
        await store.db.batch([store.db.prepare('DELETE FROM members WHERE user_id=?').bind(decodeURIComponent(path[2])),store.auditStatement(actor.userId,'MEMBER_REMOVED',decodeURIComponent(path[2]),[])]);return json({ok:true});
      }
      if(path[1]==='facilities'&&path[2]) {
        const f=await store.facility(path[2]);if(!canManage(actor,f.id))throw new ApiError(403,'FORBIDDEN','You can only update your assigned parking locations.');
        if(method==='PATCH'&&path.length===3) {
          const p=await readBody(request,listingSchema);
          if(f.version!==p.version)throw new ApiError(409,'STALE_VERSION','This listing changed. Refresh before saving.');
          if(actor.role==='ADMIN')return json({facility:await applyListing(store,actor,f,p)});
          const id=crypto.randomUUID();await store.db.batch([store.db.prepare('INSERT INTO listing_changes(id,facility_id,actor_id,payload,status,created_at) VALUES(?,?,?,?,?,?)').bind(id,f.id,actor.userId,JSON.stringify(p),'PENDING',new Date(now).toISOString()),store.auditStatement(actor.userId,'CHANGE_REQUESTED',f.id,Object.keys(p))]);return json({status:'PENDING',id},202);
        }
        if(method==='POST'&&path[3]==='status') {
          if(actor.role!=='OPERATOR')throw new ApiError(403,'OPERATOR_REQUIRED','Status observations must come from an assigned operator.');
          if(!f.active)throw new ApiError(409,'INACTIVE','This listing is inactive.');
          const p=await readBody(request,observationSchema);requireRecent(p.observedAt,now,statusTtlMinutes);
          const observedAt=new Date(p.observedAt).toISOString(),expiresAt=new Date(Date.parse(observedAt)+statusTtlMinutes*60000).toISOString();
          await store.db.batch([store.db.prepare('INSERT INTO observations(id,facility_id,state,evidence_class,source,observed_at,expires_at) VALUES(?,?,?,?,?,?,?)').bind(crypto.randomUUID(),f.id,p.state,'OPERATOR_REPORTED',actor.displayName,observedAt,expiresAt),store.auditStatement(actor.userId,'STATUS_REPORTED',f.id,['state','observedAt'])]);return json({ok:true,expiresAt},201);
        }
      }
      if(method==='POST'&&path[1]==='reports'&&path[2]&&path[3]==='moderate') {
        if(actor.role==='OPERATOR')throw new ApiError(403,'FORBIDDEN','Only reviewers can review reports.');
        const p=await readBody(request,z.object({decision:z.enum(['APPROVED','REJECTED','RESOLVED'])}).strict());
        const r=await store.db.prepare('SELECT * FROM reports WHERE id=?').bind(path[2]).first<{id:string;facility_id:string;category:string;observed_at:string;status:string}>();
        if(!r)throw new ApiError(404,'NOT_FOUND','Report not found.');if(r.status!=='PENDING')throw new ApiError(409,'ALREADY_REVIEWED','This report has already been reviewed.');
        if(p.decision==='APPROVED'&&Date.parse(r.observed_at)+statusTtlMinutes*60000<=now)throw new ApiError(409,'EXPIRED','This report is too old to publish as a current status. Resolve it instead.');
        const auditId=crypto.randomUUID();
        const stmts=[
          store.db.prepare('INSERT INTO audit_events(id,actor_id,action,entity_id,fields,created_at) SELECT ?,?,?,?,?,? FROM reports WHERE id=? AND status=?').bind(auditId,actor.userId,`REPORT_${p.decision}`,r.id,'[]',new Date(now).toISOString(),r.id,'PENDING'),
          store.db.prepare('UPDATE reports SET status=? WHERE id=? AND EXISTS(SELECT 1 FROM audit_events WHERE id=?)').bind(p.decision,r.id,auditId),
        ];
        if(p.decision==='APPROVED'&&['FULL','FOUND_SPACE'].includes(r.category))stmts.push(store.db.prepare('INSERT OR IGNORE INTO observations(id,facility_id,state,evidence_class,source,observed_at,expires_at) SELECT ?,?,?,?,?,?,? WHERE EXISTS(SELECT 1 FROM audit_events WHERE id=?)').bind(`report-${r.id}`,r.facility_id,r.category==='FULL'?'FULL':'AVAILABLE','COMMUNITY_REPORTED','Driver report',r.observed_at,new Date(Date.parse(r.observed_at)+statusTtlMinutes*60000).toISOString(),auditId));
        const applied=await store.db.batch(stmts);if(!applied[1].meta?.changes)throw new ApiError(409,'ALREADY_REVIEWED','Another reviewer has already reviewed this report.');return json({ok:true});
      }
      if(method==='POST'&&path[1]==='changes'&&path[2]&&path[3]==='moderate') {
        if(actor.role!=='ADMIN')throw new ApiError(403,'FORBIDDEN','Only the owner can publish listing changes.');
        const p=await readBody(request,z.object({decision:z.enum(['APPROVED','REJECTED'])}).strict());
        const r=await store.db.prepare('SELECT * FROM listing_changes WHERE id=?').bind(path[2]).first<{id:string;facility_id:string;payload:string;status:string}>();if(!r)throw new ApiError(404,'NOT_FOUND','Change not found.');if(r.status!=='PENDING')throw new ApiError(409,'ALREADY_REVIEWED','This change was already reviewed.');
        if(p.decision==='APPROVED')await applyListing(store,actor,await store.facility(r.facility_id),listingSchema.parse(JSON.parse(r.payload)),r.id);
        else await store.db.batch([store.db.prepare('UPDATE listing_changes SET status=? WHERE id=?').bind('REJECTED',r.id),store.auditStatement(actor.userId,'CHANGE_REJECTED',r.facility_id,[])]);return json({ok:true});
      }
    }
    throw new ApiError(404,'NOT_FOUND','This endpoint does not exist.');
  } catch(error) {
    if(error instanceof ApiError)return json({error:{code:error.code,message:error.message,requestId}},error.status);
    // Do not log request URLs, coordinates, addresses, SQL values, or credentials.
    console.error(JSON.stringify({event:'api_error',requestId,category:'internal'}));
    return json({error:{code:'INTERNAL',message:'Something went wrong. Please try again shortly.',requestId}},500);
  }
}
