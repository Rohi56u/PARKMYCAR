import type { Database, Statement, SqlResult } from './store';
import { initialFacilities, CATALOGUE_VERSION } from './catalogue';

export type CameraRecord = {
  id: string;
  facilityId: string;
  name: string;
  feedType: 'USB' | 'IP_RTSP' | 'VIDEO_FILE' | 'SIMULATION';
  streamUrl: string | null;
  gateType: 'ENTRY' | 'EXIT' | 'BIDIRECTIONAL';
  status: 'ONLINE' | 'DEGRADED' | 'OFFLINE' | 'SIMULATING';
  lastHeartbeatAt: string | null;
  fps: number | null;
  config: string | null;
  createdAt: string;
  updatedAt: string;
};

export type VehicleRecord = {
  plateNumber: string;
  stateCode: string | null;
  vehicleClass: 'CAR' | 'TWO_WHEELER' | 'COMMERCIAL' | 'UNKNOWN';
  firstSeenAt: string;
  lastSeenAt: string;
  totalSessions: number;
  createdAt: string;
};

export type VehicleSessionRecord = {
  id: string;
  facilityId: string;
  plateNumber: string;
  status: 'INSIDE' | 'EXITED' | 'OVERSTAY' | 'NEEDS_REVIEW' | 'CANCELLED';
  entryEventId: string | null;
  entryCameraId: string | null;
  entryTime: string;
  exitEventId: string | null;
  exitCameraId: string | null;
  exitTime: string | null;
  durationSeconds: number | null;
  calculatedTariff: number | null;
  reviewStatus: 'VERIFIED' | 'NEEDS_REVIEW' | 'MANUALLY_CORRECTED' | 'REJECTED' | null;
  operatorNotes: string | null;
  createdAt: string;
  updatedAt: string;
};

export type AnprEventRecord = {
  id: string;
  facilityId: string;
  cameraId: string;
  gateType: 'ENTRY' | 'EXIT';
  plateNumber: string;
  confidence: number;
  plateCropUrl: string | null;
  fullFrameUrl: string | null;
  processingTimeMs: number | null;
  status: 'ACCEPTED' | 'COOLDOWN_IGNORED' | 'NEEDS_REVIEW' | 'MANUALLY_RESOLVED' | 'UNMATCHED_EXIT' | 'REJECTED';
  reviewReason: string | null;
  sessionId: string | null;
  detectedAt: string;
  createdAt: string;
};

function formatCamera(c: CameraRecord) {
  return {
    id: c.id,
    facility_id: c.facilityId,
    facilityId: c.facilityId,
    name: c.name,
    feed_type: c.feedType,
    feedType: c.feedType,
    stream_url: c.streamUrl,
    streamUrl: c.streamUrl,
    gate_type: c.gateType,
    gateType: c.gateType,
    status: c.status,
    last_heartbeat_at: c.lastHeartbeatAt,
    lastHeartbeatAt: c.lastHeartbeatAt,
    fps: c.fps,
    config: c.config,
    created_at: c.createdAt,
    createdAt: c.createdAt,
    updated_at: c.updatedAt,
    updatedAt: c.updatedAt
  };
}

function formatVehicle(v: VehicleRecord) {
  return {
    plate_number: v.plateNumber,
    plateNumber: v.plateNumber,
    state_code: v.stateCode,
    stateCode: v.stateCode,
    vehicle_class: v.vehicleClass,
    vehicleClass: v.vehicleClass,
    first_seen_at: v.firstSeenAt,
    firstSeenAt: v.firstSeenAt,
    last_seen_at: v.lastSeenAt,
    lastSeenAt: v.lastSeenAt,
    total_sessions: v.totalSessions,
    totalSessions: v.totalSessions,
    created_at: v.createdAt,
    createdAt: v.createdAt
  };
}

function formatSession(s: VehicleSessionRecord) {
  return {
    id: s.id,
    facility_id: s.facilityId,
    facilityId: s.facilityId,
    plate_number: s.plateNumber,
    plateNumber: s.plateNumber,
    status: s.status,
    entry_event_id: s.entryEventId,
    entryEventId: s.entryEventId,
    entry_camera_id: s.entryCameraId,
    entryCameraId: s.entryCameraId,
    entry_time: s.entryTime,
    entryTime: s.entryTime,
    exit_event_id: s.exitEventId,
    exitEventId: s.exitEventId,
    exit_camera_id: s.exitCameraId,
    exitCameraId: s.exitCameraId,
    exit_time: s.exitTime,
    exitTime: s.exitTime,
    duration_seconds: s.durationSeconds,
    durationSeconds: s.durationSeconds,
    calculated_tariff: s.calculatedTariff,
    calculatedTariff: s.calculatedTariff,
    review_status: s.reviewStatus,
    reviewStatus: s.reviewStatus,
    operator_notes: s.operatorNotes,
    operatorNotes: s.operatorNotes,
    created_at: s.createdAt,
    createdAt: s.createdAt,
    updated_at: s.updatedAt,
    updatedAt: s.updatedAt
  };
}

function formatAnprEvent(e: AnprEventRecord) {
  return {
    id: e.id,
    facility_id: e.facilityId,
    facilityId: e.facilityId,
    camera_id: e.cameraId,
    cameraId: e.cameraId,
    gate_type: e.gateType,
    gateType: e.gateType,
    plate_number: e.plateNumber,
    plateNumber: e.plateNumber,
    confidence: e.confidence,
    plate_crop_url: e.plateCropUrl,
    plateCropUrl: e.plateCropUrl,
    full_frame_url: e.fullFrameUrl,
    fullFrameUrl: e.fullFrameUrl,
    processing_time_ms: e.processingTimeMs,
    processingTimeMs: e.processingTimeMs,
    status: e.status,
    review_reason: e.reviewReason,
    reviewReason: e.reviewReason,
    session_id: e.sessionId,
    sessionId: e.sessionId,
    detected_at: e.detectedAt,
    detectedAt: e.detectedAt,
    created_at: e.createdAt,
    createdAt: e.createdAt
  };
}

/**
 * Universal in-memory database engine implementing the Database interface.
 * Zero native C++ or external binary dependencies.
 * Ensures zero-configuration deployment on Netlify, Vercel, Node 18/20/22+, Docker, and Serverless.
 */
export class MemoryDatabase implements Database {
  private facilities = new Map<string, {
    id: string;
    name: string;
    lat: number;
    lng: number;
    active: number;
    version: number;
    payload: string;
  }>();

  private settings = new Map<string, string>();
  private observations = new Map<string, {
    id: string;
    facilityId: string;
    state: string;
    evidenceClass: string;
    source: string;
    observedAt: string;
    expiresAt: string;
  }>();

  private reports = new Map<string, {
    id: string;
    facilityId: string;
    category: string;
    observedAt: string;
    createdAt: string;
    status: string;
    dedupKey: string;
  }>();

  private members = new Map<string, {
    userId: string;
    role: 'ADMIN' | 'OPERATOR' | 'REVIEWER';
    displayName: string;
    facilityIds: string; // JSON string
  }>();

  private auditEvents: Array<{
    id: string;
    actorId: string;
    action: string;
    entityId: string;
    fields: string;
    createdAt: string;
  }> = [];

  private listingChanges = new Map<string, {
    id: string;
    facilityId: string;
    actorId: string;
    payload: string;
    status: string;
    createdAt: string;
  }>();

  private requestLimits = new Map<string, {
    key: string;
    count: number;
    expiresAt: number;
  }>();

  private geocodeCache = new Map<string, {
    key: string;
    payload: string;
    retrievedAt: string;
    expiresAt: number;
  }>();

  // ANPR collections
  private cameras = new Map<string, CameraRecord>();
  private vehicles = new Map<string, VehicleRecord>();
  private vehicleSessions = new Map<string, VehicleSessionRecord>();
  private anprEvents = new Map<string, AnprEventRecord>();

  constructor() {
    this.seedDefaults();
  }

  private seedDefaults() {
    if (this.settings.has('catalogue_version')) return;
    for (const f of initialFacilities) {
      this.facilities.set(f.id, {
        id: f.id,
        name: f.name,
        lat: f.point.lat,
        lng: f.point.lng,
        active: 1,
        version: 1,
        payload: JSON.stringify(f)
      });
    }
    this.settings.set('catalogue_version', CATALOGUE_VERSION);
    this.members.set('admin-rohit', {
      userId: 'admin-rohit',
      role: 'ADMIN',
      displayName: 'Rohit Choudhary (Admin / Site Owner)',
      facilityIds: '[]'
    });
    this.settings.set('owner', 'admin-rohit');

    // Seed default cameras for Palika facility
    if (!this.cameras.has('palika-entry-1')) {
      const now = new Date().toISOString();
      this.cameras.set('palika-entry-1', {
        id: 'palika-entry-1',
        facilityId: 'palika',
        name: 'Palika Gate 1 (Entry)',
        feedType: 'SIMULATION',
        streamUrl: null,
        gateType: 'ENTRY',
        status: 'ONLINE',
        lastHeartbeatAt: now,
        fps: 25.0,
        config: JSON.stringify({ simulatedIntervalMs: 5000 }),
        createdAt: now,
        updatedAt: now
      });
      this.cameras.set('palika-exit-1', {
        id: 'palika-exit-1',
        facilityId: 'palika',
        name: 'Palika Gate 2 (Exit)',
        feedType: 'SIMULATION',
        streamUrl: null,
        gateType: 'EXIT',
        status: 'ONLINE',
        lastHeartbeatAt: now,
        fps: 25.0,
        config: JSON.stringify({ simulatedIntervalMs: 7000 }),
        createdAt: now,
        updatedAt: now
      });
    }
  }

  prepare(sql: string): Statement {
    let boundValues: unknown[] = [];
    const normalized = sql.trim().replace(/\s+/g, ' ');

    const statement: Statement = {
      bind: (...args: unknown[]) => {
        boundValues = args;
        return statement;
      },

      first: async <T = Record<string, unknown>>(column?: string): Promise<T | null> => {
        const result = await statement.all<T>();
        if (!result.results || result.results.length === 0) return null;
        const row = result.results[0];
        if (column && typeof row === 'object' && row !== null) {
          return ((row as Record<string, unknown>)[column] ?? null) as T | null;
        }
        return row;
      },

      all: async <T = Record<string, unknown>>(): Promise<SqlResult<T>> => {
        const results = this.executeSelect<T>(normalized, boundValues);
        return { results };
      },

      run: async (): Promise<SqlResult<never>> => {
        const changes = this.executeMutation(normalized, boundValues);
        return { results: [], meta: { changes } };
      }
    };

    return statement;
  }

  async batch<T = unknown>(statements: Statement[]): Promise<SqlResult<T>[]> {
    const results: SqlResult<T>[] = [];
    for (const stmt of statements) {
      const res = await stmt.run();
      results.push(res as unknown as SqlResult<T>);
    }
    return results;
  }

  private executeSelect<T>(sql: string, params: unknown[]): T[] {
    // 1. SELECT value FROM settings WHERE key = ?
    if (/SELECT value FROM settings WHERE key\s*=\s*\?/i.test(sql)) {
      const key = String(params[0]);
      const value = this.settings.get(key);
      return (value !== undefined ? [{ value }] : []) as T[];
    }

    // 2. SELECT payload,version,active FROM facilities WHERE active=1 AND lat BETWEEN ...
    if (/SELECT payload,version,active FROM facilities WHERE active=1 AND lat BETWEEN/i.test(sql)) {
      const [minLat, maxLat, minLng, maxLng] = params as number[];
      const matched: unknown[] = [];
      for (const f of this.facilities.values()) {
        if (f.active === 1 && f.lat >= minLat && f.lat <= maxLat && f.lng >= minLng && f.lng <= maxLng) {
          matched.push({ payload: f.payload, version: f.version, active: f.active });
          if (matched.length >= 200) break;
        }
      }
      return matched as T[];
    }

    // 3. SELECT payload,version,active FROM facilities ORDER BY name LIMIT 200
    if (/SELECT payload,version,active FROM facilities ORDER BY name/i.test(sql)) {
      const sorted = Array.from(this.facilities.values())
        .sort((a, b) => a.name.localeCompare(b.name))
        .slice(0, 200)
        .map(f => ({ payload: f.payload, version: f.version, active: f.active }));
      return sorted as T[];
    }

    // 4. SELECT payload,version,active FROM facilities WHERE id=?
    if (/SELECT payload,version,active FROM facilities WHERE id\s*=\s*\?/i.test(sql)) {
      const id = String(params[0]);
      const f = this.facilities.get(id);
      return (f ? [{ payload: f.payload, version: f.version, active: f.active }] : []) as T[];
    }

    // 5. SELECT id,facility_id as facilityId,state,evidence_class as evidenceClass,source,observed_at as observedAt,expires_at as expiresAt FROM observations WHERE expires_at>?
    if (/FROM observations WHERE expires_at\s*>\s*\?/i.test(sql)) {
      const now = String(params[0]);
      const matched = Array.from(this.observations.values())
        .filter(o => o.expiresAt > now)
        .sort((a, b) => b.observedAt.localeCompare(a.observedAt))
        .slice(0, 1000);
      return matched as T[];
    }

    // 6. SELECT user_id,role,display_name,facility_ids FROM members WHERE user_id=?
    if (/FROM members WHERE user_id\s*=\s*\?/i.test(sql)) {
      const userId = String(params[0]);
      const m = this.members.get(userId);
      return (m ? [{
        user_id: m.userId,
        role: m.role,
        display_name: m.displayName,
        facility_ids: m.facilityIds
      }] : []) as T[];
    }

    // 7. SELECT user_id,role,display_name,facility_ids FROM members ORDER BY role,display_name
    if (/FROM members ORDER BY role/i.test(sql)) {
      const list = Array.from(this.members.values()).map(m => ({
        user_id: m.userId,
        role: m.role,
        display_name: m.displayName,
        facility_ids: m.facilityIds
      }));
      return list as T[];
    }

    // 8. SELECT id,facility_id,category,observed_at,created_at,status FROM reports ORDER BY created_at
    if (/FROM reports ORDER BY created_at/i.test(sql)) {
      const list = Array.from(this.reports.values())
        .sort((a, b) => b.createdAt.localeCompare(a.createdAt))
        .slice(0, 100)
        .map(r => ({
          id: r.id,
          facility_id: r.facilityId,
          category: r.category,
          observed_at: r.observedAt,
          created_at: r.createdAt,
          status: r.status
        }));
      return list as T[];
    }

    // 9. SELECT * FROM reports WHERE id=?
    if (/FROM reports WHERE id\s*=\s*\?/i.test(sql)) {
      const id = String(params[0]);
      const r = this.reports.get(id);
      return (r ? [{
        id: r.id,
        facility_id: r.facilityId,
        category: r.category,
        observed_at: r.observedAt,
        created_at: r.createdAt,
        status: r.status
      }] : []) as T[];
    }

    // 10. SELECT payload,retrieved_at FROM geocode_cache WHERE key=? AND expires_at>?
    if (/FROM geocode_cache WHERE key\s*=\s*\?\s*AND expires_at\s*>\s*\?/i.test(sql)) {
      const [key, now] = params as [string, number];
      const cached = this.geocodeCache.get(key);
      if (cached && cached.expiresAt > now) {
        return [{ payload: cached.payload, retrieved_at: cached.retrievedAt }] as T[];
      }
      return [];
    }

    // 11. SELECT id,facility_id,actor_id,payload,status,created_at FROM listing_changes
    if (/FROM listing_changes ORDER BY created_at/i.test(sql)) {
      const list = Array.from(this.listingChanges.values())
        .sort((a, b) => b.createdAt.localeCompare(a.createdAt))
        .slice(0, 100);
      return list as T[];
    }

    // 12. SELECT action,entity_id,fields,created_at FROM audit_events
    if (/FROM audit_events ORDER BY created_at/i.test(sql)) {
      const list = this.auditEvents
        .slice()
        .sort((a, b) => b.createdAt.localeCompare(a.createdAt))
        .slice(0, 100);
      return list as T[];
    }

    // ==========================================
    // ANPR SELECT QUERIES
    // ==========================================

    // 13. Live occupancy count: SELECT COUNT(*) as count FROM vehicle_sessions WHERE facility_id = ? AND status = 'INSIDE'
    if (/SELECT COUNT\(\*\)(?:\s+as\s+[a-z0-9_]+)?\s+FROM vehicle_sessions/i.test(sql)) {
      if (/facility_id\s*=\s*\?\s*AND status\s*=\s*('INSIDE'|\?)/i.test(sql)) {
        const facilityId = String(params[0]);
        const targetStatus = /'INSIDE'/.test(sql) ? 'INSIDE' : String(params[1]);
        let count = 0;
        for (const s of this.vehicleSessions.values()) {
          if (s.facilityId === facilityId && s.status === targetStatus) {
            count++;
          }
        }
        return [{ count, 'COUNT(*)': count, live: count }] as T[];
      }
      // General count on vehicle_sessions
      const count = this.vehicleSessions.size;
      return [{ count, 'COUNT(*)': count, live: count }] as T[];
    }

    // 14. Active session lookup: SELECT * FROM vehicle_sessions WHERE facility_id = ? AND plate_number = ? AND status = 'INSIDE'
    if (/FROM vehicle_sessions WHERE facility_id\s*=\s*\?\s*AND plate_number\s*=\s*\?\s*AND status\s*=\s*('INSIDE'|\?)/i.test(sql)) {
      const facilityId = String(params[0]);
      const plateNumber = String(params[1]).trim().toUpperCase();
      const targetStatus = /'INSIDE'/.test(sql) ? 'INSIDE' : String(params[2]);
      for (const s of this.vehicleSessions.values()) {
        if (s.facilityId === facilityId && s.plateNumber.toUpperCase() === plateNumber && s.status === targetStatus) {
          return [formatSession(s)] as T[];
        }
      }
      return [] as T[];
    }

    // 15. Vehicle session by ID: SELECT * FROM vehicle_sessions WHERE id = ?
    if (/FROM vehicle_sessions WHERE id\s*=\s*\?/i.test(sql)) {
      const id = String(params[0]);
      const s = this.vehicleSessions.get(id);
      return (s ? [formatSession(s)] : []) as T[];
    }

    // 16. Session list: SELECT * FROM vehicle_sessions WHERE facility_id = ? ORDER BY entry_time DESC LIMIT ?
    if (/FROM vehicle_sessions WHERE facility_id\s*=\s*\?/i.test(sql)) {
      const facilityId = String(params[0]);
      const limit = typeof params[1] === 'number' ? params[1] : 100;
      const matched = Array.from(this.vehicleSessions.values())
        .filter(s => s.facilityId === facilityId)
        .sort((a, b) => b.entryTime.localeCompare(a.entryTime))
        .slice(0, limit)
        .map(formatSession);
      return matched as T[];
    }

    // 17. Vehicle session by plate: SELECT * FROM vehicle_sessions WHERE plate_number = ?
    if (/FROM vehicle_sessions WHERE plate_number\s*=\s*\?/i.test(sql)) {
      const plate = String(params[0]).trim().toUpperCase();
      const matched = Array.from(this.vehicleSessions.values())
        .filter(s => s.plateNumber.toUpperCase() === plate)
        .sort((a, b) => b.entryTime.localeCompare(a.entryTime))
        .map(formatSession);
      return matched as T[];
    }

    // 18. Parking camera by ID: SELECT * FROM parking_cameras WHERE id = ?
    if (/FROM parking_cameras WHERE id\s*=\s*\?/i.test(sql)) {
      const id = String(params[0]);
      const c = this.cameras.get(id);
      return (c ? [formatCamera(c)] : []) as T[];
    }

    // 19. Parking cameras by facility: SELECT * FROM parking_cameras WHERE facility_id = ?
    if (/FROM parking_cameras WHERE facility_id\s*=\s*\?/i.test(sql)) {
      const facilityId = String(params[0]);
      const matched = Array.from(this.cameras.values())
        .filter(c => c.facilityId === facilityId)
        .sort((a, b) => a.name.localeCompare(b.name))
        .map(formatCamera);
      return matched as T[];
    }

    // 20. All parking cameras: SELECT * FROM parking_cameras
    if (/FROM parking_cameras/i.test(sql)) {
      const all = Array.from(this.cameras.values())
        .sort((a, b) => a.facilityId.localeCompare(b.facilityId) || a.name.localeCompare(b.name))
        .map(formatCamera);
      return all as T[];
    }

    // 21. Vehicle by plate: SELECT * FROM vehicles WHERE plate_number = ?
    if (/FROM vehicles WHERE plate_number\s*=\s*\?/i.test(sql)) {
      const plate = String(params[0]).trim().toUpperCase();
      const v = this.vehicles.get(plate);
      return (v ? [formatVehicle(v)] : []) as T[];
    }

    // 22. ANPR review queue: SELECT * FROM anpr_events WHERE facility_id = ? AND status IN ('NEEDS_REVIEW', 'UNMATCHED_EXIT') ORDER BY detected_at DESC
    if (/FROM anpr_events WHERE facility_id\s*=\s*\?\s*AND status IN \('NEEDS_REVIEW',\s*'UNMATCHED_EXIT'\)/i.test(sql)) {
      const facilityId = String(params[0]);
      const matched = Array.from(this.anprEvents.values())
        .filter(e => e.facilityId === facilityId && (e.status === 'NEEDS_REVIEW' || e.status === 'UNMATCHED_EXIT'))
        .sort((a, b) => b.detectedAt.localeCompare(a.detectedAt))
        .map(formatAnprEvent);
      return matched as T[];
    }

    // 23. ANPR cooldown check: SELECT * FROM anpr_events WHERE camera_id = ? AND plate_number = ? AND detected_at > ?
    if (/FROM anpr_events WHERE camera_id\s*=\s*\?\s*AND plate_number\s*=\s*\?\s*AND detected_at\s*>\s*\?/i.test(sql)) {
      const cameraId = String(params[0]);
      const plateNumber = String(params[1]).trim().toUpperCase();
      const threshold = String(params[2]);
      const matched = Array.from(this.anprEvents.values())
        .filter(e => e.cameraId === cameraId && e.plateNumber.toUpperCase() === plateNumber && e.detectedAt > threshold)
        .sort((a, b) => b.detectedAt.localeCompare(a.detectedAt))
        .map(formatAnprEvent);
      return matched as T[];
    }

    // 24. ANPR event by ID: SELECT * FROM anpr_events WHERE id = ?
    if (/FROM anpr_events WHERE id\s*=\s*\?/i.test(sql)) {
      const id = String(params[0]);
      const e = this.anprEvents.get(id);
      return (e ? [formatAnprEvent(e)] : []) as T[];
    }

    // 25. ANPR events by facility: SELECT * FROM anpr_events WHERE facility_id = ?
    if (/FROM anpr_events WHERE facility_id\s*=\s*\?/i.test(sql)) {
      const facilityId = String(params[0]);
      const matched = Array.from(this.anprEvents.values())
        .filter(e => e.facilityId === facilityId)
        .sort((a, b) => b.detectedAt.localeCompare(a.detectedAt))
        .map(formatAnprEvent);
      return matched as T[];
    }

    // 26. INSERT INTO request_limits ... RETURNING count
    if (/INSERT INTO request_limits/i.test(sql) && /RETURNING count/i.test(sql)) {
      const [key, expiresAt] = params as [string, number];
      const existing = this.requestLimits.get(key);
      if (existing) {
        existing.count += 1;
        existing.expiresAt = expiresAt;
        return [{ count: existing.count }] as T[];
      }
      this.requestLimits.set(key, { key, count: 1, expiresAt });
      return [{ count: 1 }] as T[];
    }

    // 27. INSERT INTO request_limits ... RETURNING expires_at
    if (/INSERT INTO request_limits/i.test(sql) && /RETURNING expires_at/i.test(sql)) {
      const [key, nextExpiresAt, currentNow] = params as [string, number, number];
      const existing = this.requestLimits.get(key);
      if (!existing || existing.expiresAt <= (currentNow ?? 0)) {
        this.requestLimits.set(key, { key, count: 1, expiresAt: nextExpiresAt });
        return [{ expires_at: nextExpiresAt }] as T[];
      }
      return [] as T[];
    }

    return [];
  }

  private executeMutation(sql: string, params: unknown[]): number {
    // 1. INSERT OR IGNORE INTO facilities
    if (/INSERT OR IGNORE INTO facilities/i.test(sql)) {
      const [id, name, lat, lng, active, version, payload] = params as [string, string, number, number, number, number, string];
      if (this.facilities.has(id)) return 0;
      this.facilities.set(id, { id, name, lat, lng, active, version, payload });
      return 1;
    }

    // 2. INSERT INTO facilities
    if (/INSERT INTO facilities/i.test(sql)) {
      const [id, name, lat, lng, active, version, payload] = params as [string, string, number, number, number, number, string];
      this.facilities.set(id, { id, name, lat, lng, active, version, payload });
      return 1;
    }

    // 3. UPDATE facilities SET name=?,active=?,version=version+1,payload=? WHERE id=? AND version=?
    if (/UPDATE facilities SET/i.test(sql)) {
      const [name, active, payload, id, expectedVersion] = params as [string, number, string, string, number];
      const existing = this.facilities.get(id);
      if (!existing || existing.version !== expectedVersion) return 0;
      existing.name = name;
      existing.active = active;
      existing.version += 1;
      existing.payload = payload;
      return 1;
    }

    // 4. INSERT OR IGNORE INTO settings
    if (/INSERT OR IGNORE INTO settings/i.test(sql)) {
      const [key, value] = params as [string, string];
      if (this.settings.has(key)) return 0;
      this.settings.set(key, value);
      return 1;
    }

    // 5. INSERT INTO settings ... ON CONFLICT
    if (/INSERT INTO settings/i.test(sql)) {
      const [key, value] = params as [string, string];
      this.settings.set(key, value);
      return 1;
    }

    // 6. INSERT INTO request_limits ... ON CONFLICT DO UPDATE SET count=count+1 RETURNING count
    if (/INSERT INTO request_limits/i.test(sql) && /count=count\+1/i.test(sql)) {
      const [key, expiresAt] = params as [string, number];
      const existing = this.requestLimits.get(key);
      if (existing) {
        existing.count += 1;
        return 1;
      }
      this.requestLimits.set(key, { key, count: 1, expiresAt });
      return 1;
    }

    // 7. Rate gate admissions: INSERT INTO request_limits ... WHERE request_limits.expires_at<=?
    if (/INSERT INTO request_limits/i.test(sql)) {
      const [key, expiresAt] = params as [string, number];
      this.requestLimits.set(key, { key, count: 1, expiresAt });
      return 1;
    }

    // 8. INSERT OR IGNORE INTO reports
    if (/INSERT OR IGNORE INTO reports/i.test(sql)) {
      const [id, facilityId, category, observedAt, createdAt, status, dedupKey] = params as [string, string, string, string, string, string, string];
      for (const r of this.reports.values()) {
        if (r.dedupKey === dedupKey) return 0;
      }
      this.reports.set(id, { id, facilityId, category, observedAt, createdAt, status, dedupKey });
      return 1;
    }

    // 9. UPDATE reports SET status=? WHERE id=?
    if (/UPDATE reports SET status\s*=\s*\?/i.test(sql)) {
      const [status, id] = params as [string, string];
      const r = this.reports.get(id);
      if (!r) return 0;
      r.status = status;
      return 1;
    }

    // 10. INSERT INTO observations
    if (/INSERT INTO observations|INSERT OR IGNORE INTO observations/i.test(sql)) {
      const [id, facilityId, state, evidenceClass, source, observedAt, expiresAt] = params as [string, string, string, string, string, string, string];
      this.observations.set(id, { id, facilityId, state, evidenceClass, source, observedAt, expiresAt });
      return 1;
    }

    // 11. INSERT INTO audit_events
    if (/INSERT INTO audit_events/i.test(sql)) {
      const [id, actorId, action, entityId, fields, createdAt] = params as [string, string, string, string, string, string];
      this.auditEvents.push({ id, actorId, action, entityId, fields, createdAt });
      return 1;
    }

    // 12. INSERT INTO members
    if (/INSERT INTO members|INSERT OR IGNORE INTO members/i.test(sql)) {
      const [userId, role, displayName, facilityIds] = params as [string, 'ADMIN' | 'OPERATOR' | 'REVIEWER', string, string];
      this.members.set(userId, { userId, role, displayName, facilityIds });
      return 1;
    }

    // 13. DELETE FROM members WHERE user_id=?
    if (/DELETE FROM members WHERE user_id\s*=\s*\?/i.test(sql)) {
      const userId = String(params[0]);
      return this.members.delete(userId) ? 1 : 0;
    }

    // 14. INSERT INTO geocode_cache
    if (/INSERT INTO geocode_cache/i.test(sql)) {
      const [key, payload, retrievedAt, expiresAt] = params as [string, string, string, number];
      this.geocodeCache.set(key, { key, payload, retrievedAt, expiresAt });
      return 1;
    }

    // 15. INSERT INTO listing_changes
    if (/INSERT INTO listing_changes/i.test(sql)) {
      const [id, facilityId, actorId, payload, status, createdAt] = params as [string, string, string, string, string, string];
      this.listingChanges.set(id, { id, facilityId, actorId, payload, status, createdAt });
      return 1;
    }

    // 16. UPDATE listing_changes SET status=? WHERE id=?
    if (/UPDATE listing_changes SET status\s*=\s*\?/i.test(sql)) {
      const [status, id] = params as [string, string];
      const lc = this.listingChanges.get(id);
      if (!lc) return 0;
      lc.status = status;
      return 1;
    }

    // ==========================================
    // ANPR MUTATIONS
    // ==========================================

    // 17. INSERT INTO vehicle_sessions (Enforce Partial Unique Index)
    if (/INSERT\s+(?:OR\s+IGNORE\s+)?INTO\s+vehicle_sessions/i.test(sql)) {
      const colMatch = sql.match(/INSERT\s+(?:OR\s+IGNORE\s+)?INTO\s+vehicle_sessions\s*\(([^)]+)\)\s*VALUES/i);
      let session: VehicleSessionRecord;
      if (colMatch) {
        const colNames = colMatch[1].split(',').map(c => c.trim().replace(/[`"]/g, ''));
        const record: Record<string, unknown> = {};
        colNames.forEach((col, idx) => {
          const camelKey = col.replace(/_([a-z])/g, (_, g) => g.toUpperCase());
          record[camelKey] = params[idx];
        });
        session = {
          id: String(record.id),
          facilityId: String(record.facilityId),
          plateNumber: String(record.plateNumber).trim().toUpperCase(),
          status: record.status as VehicleSessionRecord['status'],
          entryEventId: (record.entryEventId as string) ?? null,
          entryCameraId: (record.entryCameraId as string) ?? null,
          entryTime: String(record.entryTime),
          exitEventId: (record.exitEventId as string) ?? null,
          exitCameraId: (record.exitCameraId as string) ?? null,
          exitTime: (record.exitTime as string) ?? null,
          durationSeconds: typeof record.durationSeconds === 'number' ? record.durationSeconds : null,
          calculatedTariff: typeof record.calculatedTariff === 'number' ? record.calculatedTariff : null,
          reviewStatus: (record.reviewStatus as VehicleSessionRecord['reviewStatus']) ?? null,
          operatorNotes: (record.operatorNotes as string) ?? null,
          createdAt: String(record.createdAt ?? new Date().toISOString()),
          updatedAt: String(record.updatedAt ?? new Date().toISOString())
        };
      } else {
        const [
          id, facilityId, plateNumber, status,
          entryEventId, entryCameraId, entryTime,
          exitEventId, exitCameraId, exitTime,
          durationSeconds, calculatedTariff, reviewStatus, operatorNotes,
          createdAt, updatedAt
        ] = params as [
          string, string, string, VehicleSessionRecord['status'],
          string | null, string | null, string,
          string | null, string | null, string | null,
          number | null, number | null, VehicleSessionRecord['reviewStatus'], string | null,
          string, string
        ];
        session = {
          id, facilityId, plateNumber: plateNumber.trim().toUpperCase(), status,
          entryEventId: entryEventId ?? null, entryCameraId: entryCameraId ?? null, entryTime,
          exitEventId: exitEventId ?? null, exitCameraId: exitCameraId ?? null, exitTime: exitTime ?? null,
          durationSeconds: durationSeconds ?? null, calculatedTariff: calculatedTariff ?? null,
          reviewStatus: reviewStatus ?? null, operatorNotes: operatorNotes ?? null,
          createdAt, updatedAt
        };
      }

      // STRICTLY enforce partial unique constraint:
      // CREATE UNIQUE INDEX unique_active_vehicle_session ON vehicle_sessions(facility_id, plate_number) WHERE status = 'INSIDE';
      if (session.status === 'INSIDE') {
        for (const existing of this.vehicleSessions.values()) {
          if (existing.facilityId === session.facilityId &&
              existing.plateNumber.toUpperCase() === session.plateNumber.toUpperCase() &&
              existing.status === 'INSIDE') {
            if (/INSERT\s+OR\s+IGNORE/i.test(sql)) {
              return 0;
            }
            throw new Error('SQLITE_CONSTRAINT: UNIQUE constraint failed: vehicle_sessions.facility_id, vehicle_sessions.plate_number');
          }
        }
      }

      this.vehicleSessions.set(session.id, session);
      return 1;
    }

    // 18. UPDATE vehicle_sessions SET status = 'EXITED' ... WHERE id = ? AND status = 'INSIDE'
    if (/UPDATE vehicle_sessions SET/i.test(sql)) {
      const requiresInside = /WHERE.*status\s*=\s*['"]INSIDE['"]/i.test(sql);
      let targetSession: VehicleSessionRecord | undefined;
      for (let i = params.length - 1; i >= 0; i--) {
        const val = String(params[i]);
        if (this.vehicleSessions.has(val)) {
          targetSession = this.vehicleSessions.get(val);
          break;
        }
      }
      if (!targetSession) return 0;
      if (requiresInside && targetSession.status !== 'INSIDE') {
        return 0;
      }

      const setPart = sql.substring(sql.toUpperCase().indexOf('SET') + 3, sql.toUpperCase().indexOf('WHERE')).trim();
      const assignments = setPart.split(',').map(a => a.trim());
      let pIdx = 0;
      for (const assign of assignments) {
        const [col, expr] = assign.split('=').map(s => s.trim().replace(/[`"]/g, ''));
        if (expr === '?') {
          const val = params[pIdx++];
          if (/exit_event_id/i.test(col)) targetSession.exitEventId = val as string;
          else if (/exit_camera_id/i.test(col)) targetSession.exitCameraId = val as string;
          else if (/exit_time/i.test(col)) targetSession.exitTime = val as string;
          else if (/duration_seconds/i.test(col)) targetSession.durationSeconds = Number(val);
          else if (/calculated_tariff/i.test(col)) targetSession.calculatedTariff = Number(val);
          else if (/review_status/i.test(col)) targetSession.reviewStatus = val as VehicleSessionRecord['reviewStatus'];
          else if (/operator_notes/i.test(col)) targetSession.operatorNotes = val as string;
          else if (/status/i.test(col)) targetSession.status = val as VehicleSessionRecord['status'];
          else if (/updated_at/i.test(col)) targetSession.updatedAt = val as string;
        } else {
          const literal = expr.replace(/['"]/g, '');
          if (/status/i.test(col)) targetSession.status = literal as VehicleSessionRecord['status'];
        }
      }
      return 1;
    }

    // 19. INSERT INTO vehicles ... ON CONFLICT(plate_number) DO UPDATE ...
    if (/INSERT\s+(?:OR\s+IGNORE\s+)?INTO\s+vehicles/i.test(sql)) {
      const colMatch = sql.match(/INSERT\s+(?:OR\s+IGNORE\s+)?INTO\s+vehicles\s*\(([^)]+)\)\s*VALUES/i);
      let vPlate = '';
      let vState: string | null = null;
      let vClass: VehicleRecord['vehicleClass'] = 'CAR';
      let vFirstSeen = new Date().toISOString();
      let vLastSeen = new Date().toISOString();
      let vTotalSessions = 1;
      let vCreatedAt = new Date().toISOString();

      if (colMatch) {
        const colNames = colMatch[1].split(',').map(c => c.trim().replace(/[`"]/g, ''));
        colNames.forEach((col, idx) => {
          const val = params[idx];
          if (/plate_number/i.test(col)) vPlate = String(val).trim().toUpperCase();
          else if (/state_code/i.test(col)) vState = val ? String(val) : null;
          else if (/vehicle_class/i.test(col)) vClass = val as VehicleRecord['vehicleClass'];
          else if (/first_seen_at/i.test(col)) vFirstSeen = String(val);
          else if (/last_seen_at/i.test(col)) vLastSeen = String(val);
          else if (/total_sessions/i.test(col)) vTotalSessions = Number(val);
          else if (/created_at/i.test(col)) vCreatedAt = String(val);
        });
      } else {
        const [plate, state, vcls, first, last, total, created] = params as [string, string | null, VehicleRecord['vehicleClass'], string, string, number, string];
        vPlate = plate.trim().toUpperCase();
        vState = state ?? null;
        vClass = vcls ?? 'CAR';
        vFirstSeen = first;
        vLastSeen = last;
        vTotalSessions = total ?? 1;
        vCreatedAt = created;
      }

      const existing = this.vehicles.get(vPlate);
      if (existing) {
        if (/ON CONFLICT/i.test(sql)) {
          existing.lastSeenAt = vLastSeen;
          existing.totalSessions += 1;
          if (vState) existing.stateCode = vState;
          return 1;
        }
        if (/INSERT\s+OR\s+IGNORE/i.test(sql)) {
          return 0;
        }
        existing.lastSeenAt = vLastSeen;
        existing.totalSessions += 1;
        return 1;
      }

      this.vehicles.set(vPlate, {
        plateNumber: vPlate,
        stateCode: vState,
        vehicleClass: vClass,
        firstSeenAt: vFirstSeen,
        lastSeenAt: vLastSeen,
        totalSessions: vTotalSessions,
        createdAt: vCreatedAt
      });
      return 1;
    }

    // 20. INSERT INTO anpr_events ...
    if (/INSERT\s+(?:OR\s+IGNORE\s+)?INTO\s+anpr_events/i.test(sql)) {
      const colMatch = sql.match(/INSERT\s+(?:OR\s+IGNORE\s+)?INTO\s+anpr_events\s*\(([^)]+)\)\s*VALUES/i);
      let event: AnprEventRecord;
      if (colMatch) {
        const colNames = colMatch[1].split(',').map(c => c.trim().replace(/[`"]/g, ''));
        const record: Record<string, unknown> = {};
        colNames.forEach((col, idx) => {
          const camelKey = col.replace(/_([a-z])/g, (_, g) => g.toUpperCase());
          record[camelKey] = params[idx];
        });
        event = {
          id: String(record.id),
          facilityId: String(record.facilityId),
          cameraId: String(record.cameraId),
          gateType: record.gateType as AnprEventRecord['gateType'],
          plateNumber: String(record.plateNumber).trim().toUpperCase(),
          confidence: Number(record.confidence),
          plateCropUrl: (record.plateCropUrl as string) ?? null,
          fullFrameUrl: (record.fullFrameUrl as string) ?? null,
          processingTimeMs: typeof record.processingTimeMs === 'number' ? record.processingTimeMs : null,
          status: record.status as AnprEventRecord['status'],
          reviewReason: (record.reviewReason as string) ?? null,
          sessionId: (record.sessionId as string) ?? null,
          detectedAt: String(record.detectedAt),
          createdAt: String(record.createdAt ?? new Date().toISOString())
        };
      } else {
        const [
          id, facilityId, cameraId, gateType, plateNumber, confidence,
          plateCropUrl, fullFrameUrl, processingTimeMs, status, reviewReason,
          sessionId, detectedAt, createdAt
        ] = params as [
          string, string, string, AnprEventRecord['gateType'], string, number,
          string | null, string | null, number | null, AnprEventRecord['status'], string | null,
          string | null, string, string
        ];
        event = {
          id, facilityId, cameraId, gateType, plateNumber: plateNumber.trim().toUpperCase(), confidence,
          plateCropUrl: plateCropUrl ?? null, fullFrameUrl: fullFrameUrl ?? null, processingTimeMs: processingTimeMs ?? null,
          status, reviewReason: reviewReason ?? null, sessionId: sessionId ?? null,
          detectedAt, createdAt
        };
      }

      this.anprEvents.set(event.id, event);
      return 1;
    }

    // 21. UPDATE anpr_events SET status = ?, review_reason = ?, session_id = ?, plate_number = ? WHERE id = ?
    if (/UPDATE anpr_events SET/i.test(sql)) {
      let targetEvent: AnprEventRecord | undefined;
      for (let i = params.length - 1; i >= 0; i--) {
        const val = String(params[i]);
        if (this.anprEvents.has(val)) {
          targetEvent = this.anprEvents.get(val);
          break;
        }
      }
      if (!targetEvent) return 0;
      const setPart = sql.substring(sql.toUpperCase().indexOf('SET') + 3, sql.toUpperCase().indexOf('WHERE')).trim();
      const assignments = setPart.split(',').map(a => a.trim());
      let pIdx = 0;
      for (const assign of assignments) {
        const [col, expr] = assign.split('=').map(s => s.trim().replace(/[`"]/g, ''));
        if (expr === '?') {
          const val = params[pIdx++];
          if (/status/i.test(col)) targetEvent.status = val as AnprEventRecord['status'];
          else if (/review_reason/i.test(col)) targetEvent.reviewReason = val as string;
          else if (/session_id/i.test(col)) targetEvent.sessionId = val as string;
          else if (/plate_number/i.test(col)) targetEvent.plateNumber = String(val).trim().toUpperCase();
        }
      }
      return 1;
    }

    // 22. INSERT INTO parking_cameras
    if (/INSERT\s+(?:OR\s+IGNORE\s+)?INTO\s+parking_cameras/i.test(sql)) {
      const colMatch = sql.match(/INSERT\s+(?:OR\s+IGNORE\s+)?INTO\s+parking_cameras\s*\(([^)]+)\)\s*VALUES/i);
      let camera: CameraRecord;
      if (colMatch) {
        const colNames = colMatch[1].split(',').map(c => c.trim().replace(/[`"]/g, ''));
        const record: Record<string, unknown> = {};
        colNames.forEach((col, idx) => {
          const camelKey = col.replace(/_([a-z])/g, (_, g) => g.toUpperCase());
          record[camelKey] = params[idx];
        });
        camera = {
          id: String(record.id),
          facilityId: String(record.facilityId),
          name: String(record.name),
          feedType: record.feedType as CameraRecord['feedType'],
          streamUrl: (record.streamUrl as string) ?? null,
          gateType: record.gateType as CameraRecord['gateType'],
          status: (record.status as CameraRecord['status']) ?? 'OFFLINE',
          lastHeartbeatAt: (record.lastHeartbeatAt as string) ?? null,
          fps: typeof record.fps === 'number' ? record.fps : null,
          config: (record.config as string) ?? null,
          createdAt: String(record.createdAt ?? new Date().toISOString()),
          updatedAt: String(record.updatedAt ?? new Date().toISOString())
        };
      } else {
        const [id, facilityId, name, feedType, streamUrl, gateType, status, lastHeartbeatAt, fps, config, createdAt, updatedAt] = params as [
          string, string, string, CameraRecord['feedType'], string | null, CameraRecord['gateType'],
          CameraRecord['status'], string | null, number | null, string | null, string, string
        ];
        camera = {
          id, facilityId, name, feedType, streamUrl: streamUrl ?? null, gateType,
          status: status ?? 'OFFLINE', lastHeartbeatAt: lastHeartbeatAt ?? null, fps: fps ?? null, config: config ?? null,
          createdAt, updatedAt
        };
      }

      if (/INSERT\s+OR\s+IGNORE/i.test(sql) && this.cameras.has(camera.id)) {
        return 0;
      }
      this.cameras.set(camera.id, camera);
      return 1;
    }

    // 23. UPDATE parking_cameras SET status=?, fps=?, last_heartbeat_at=?, updated_at=? WHERE id=?
    if (/UPDATE parking_cameras SET/i.test(sql)) {
      let targetCamera: CameraRecord | undefined;
      for (let i = params.length - 1; i >= 0; i--) {
        const val = String(params[i]);
        if (this.cameras.has(val)) {
          targetCamera = this.cameras.get(val);
          break;
        }
      }
      if (!targetCamera) return 0;
      const setPart = sql.substring(sql.toUpperCase().indexOf('SET') + 3, sql.toUpperCase().indexOf('WHERE')).trim();
      const assignments = setPart.split(',').map(a => a.trim());
      let pIdx = 0;
      for (const assign of assignments) {
        const [col, expr] = assign.split('=').map(s => s.trim().replace(/[`"]/g, ''));
        if (expr === '?') {
          const val = params[pIdx++];
          if (/status/i.test(col)) targetCamera.status = val as CameraRecord['status'];
          else if (/fps/i.test(col)) targetCamera.fps = Number(val);
          else if (/last_heartbeat_at/i.test(col)) targetCamera.lastHeartbeatAt = val as string;
          else if (/updated_at/i.test(col)) targetCamera.updatedAt = val as string;
        }
      }
      return 1;
    }

    // 24. Pruning DELETES
    if (/DELETE FROM request_limits WHERE expires_at\s*<\s*\?/i.test(sql)) {
      const now = Number(params[0]);
      let removed = 0;
      for (const [k, v] of this.requestLimits.entries()) {
        if (v.expiresAt < now) { this.requestLimits.delete(k); removed++; }
      }
      return removed;
    }

    if (/DELETE FROM geocode_cache WHERE expires_at\s*<\s*\?/i.test(sql)) {
      const now = Number(params[0]);
      let removed = 0;
      for (const [k, v] of this.geocodeCache.entries()) {
        if (v.expiresAt < now) { this.geocodeCache.delete(k); removed++; }
      }
      return removed;
    }

    if (/DELETE FROM reports WHERE created_at\s*<\s*\?/i.test(sql)) {
      const boundary = String(params[0]);
      let removed = 0;
      for (const [k, v] of this.reports.entries()) {
        if (v.createdAt < boundary) { this.reports.delete(k); removed++; }
      }
      return removed;
    }

    if (/DELETE FROM observations WHERE expires_at\s*<\s*\?/i.test(sql)) {
      const boundary = String(params[0]);
      let removed = 0;
      for (const [k, v] of this.observations.entries()) {
        if (v.expiresAt < boundary) { this.observations.delete(k); removed++; }
      }
      return removed;
    }

    return 1;
  }
}

// Global singleton instance so state persists across requests within the process lifecycle
let memoryDbInstance: MemoryDatabase | null = null;

/**
 * Universal Database Provider
 * Returns Cloudflare D1 if present, otherwise returns resilient in-memory database.
 */
export async function getDatabase(d1Binding?: unknown): Promise<Database> {
  if (d1Binding && typeof (d1Binding as Database).prepare === 'function') {
    return d1Binding as Database;
  }

  if (!memoryDbInstance) {
    memoryDbInstance = new MemoryDatabase();
  }

  return memoryDbInstance;
}
