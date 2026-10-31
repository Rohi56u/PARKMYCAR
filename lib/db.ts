import type { Database, Statement, SqlResult } from './store';
import { initialFacilities, CATALOGUE_VERSION } from './catalogue';

/**
 * Universal in-memory database engine implementing the Database interface.
 * Zero native C++ or external binary dependencies.
 * Ensures zero-configuration deployment on Netlify, Vercel, Node 18/20/22+, Docker, and Serverless.
 */
class MemoryDatabase implements Database {
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

    // 13. INSERT INTO request_limits ... RETURNING count
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

    // 14. INSERT INTO request_limits ... RETURNING expires_at
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

    // 17. Pruning DELETES
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
