import test from 'node:test';
import assert from 'node:assert/strict';
import { execSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { MemoryDatabase } from '../lib/db';
import type {
  ParkingCamera,
  Vehicle,
  VehicleSession,
  AnprEvent
} from '../db/schema';

test('M1: MemoryDatabase seeds default cameras for palika facility', async () => {
  const db = new MemoryDatabase();

  const entryCam = await db.prepare('SELECT * FROM parking_cameras WHERE id = ?')
    .bind('palika-entry-1')
    .first<ParkingCamera>();
  assert.ok(entryCam, 'palika-entry-1 should be seeded');
  assert.equal(entryCam.facilityId, 'palika');
  assert.equal(entryCam.gateType, 'ENTRY');
  assert.equal(entryCam.status, 'ONLINE');

  const exitCam = await db.prepare('SELECT * FROM parking_cameras WHERE id = ?')
    .bind('palika-exit-1')
    .first<ParkingCamera>();
  assert.ok(exitCam, 'palika-exit-1 should be seeded');
  assert.equal(exitCam.facilityId, 'palika');
  assert.equal(exitCam.gateType, 'EXIT');
  assert.equal(exitCam.status, 'ONLINE');

  const facilityCams = await db.prepare('SELECT * FROM parking_cameras WHERE facility_id = ?')
    .bind('palika')
    .all<ParkingCamera>();
  assert.ok(facilityCams.results.length >= 2, 'Should find at least 2 cameras for palika');
});

test('M1: Camera updates and heartbeats', async () => {
  const db = new MemoryDatabase();
  const now = new Date().toISOString();

  const updateRes = await db.prepare('UPDATE parking_cameras SET status=?, fps=?, last_heartbeat_at=?, updated_at=? WHERE id=?')
    .bind('DEGRADED', 14.2, now, now, 'palika-entry-1')
    .run();
  assert.equal(updateRes.meta?.changes, 1);

  const updated = await db.prepare('SELECT * FROM parking_cameras WHERE id = ?')
    .bind('palika-entry-1')
    .first<ParkingCamera>();
  assert.ok(updated);
  assert.equal(updated.status, 'DEGRADED');
  assert.equal(updated.fps, 14.2);
});

test('M1: Vehicle upsert and total sessions counter', async () => {
  const db = new MemoryDatabase();
  const now = new Date().toISOString();

  // First insertion
  const res1 = await db.prepare(
    'INSERT INTO vehicles (plate_number, state_code, vehicle_class, first_seen_at, last_seen_at, total_sessions, created_at) VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(plate_number) DO UPDATE SET last_seen_at=excluded.last_seen_at, total_sessions=vehicles.total_sessions+1'
  ).bind('DL01AB1234', 'DL', 'CAR', now, now, 1, now).run();
  assert.equal(res1.meta?.changes, 1);

  let vehicle = await db.prepare('SELECT * FROM vehicles WHERE plate_number = ?')
    .bind('DL01AB1234')
    .first<Vehicle>();
  assert.ok(vehicle);
  assert.equal(vehicle.totalSessions, 1);

  // Subsequent upsert (second session)
  const later = new Date(Date.now() + 3600000).toISOString();
  const res2 = await db.prepare(
    'INSERT INTO vehicles (plate_number, state_code, vehicle_class, first_seen_at, last_seen_at, total_sessions, created_at) VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(plate_number) DO UPDATE SET last_seen_at=excluded.last_seen_at, total_sessions=vehicles.total_sessions+1'
  ).bind('DL01AB1234', 'DL', 'CAR', now, later, 1, now).run();
  assert.equal(res2.meta?.changes, 1);

  vehicle = await db.prepare('SELECT * FROM vehicles WHERE plate_number = ?')
    .bind('DL01AB1234')
    .first<Vehicle>();
  assert.ok(vehicle);
  assert.equal(vehicle.totalSessions, 2);
  assert.equal(vehicle.lastSeenAt, later);
});

test('M1: Strict partial unique index enforcement on vehicle_sessions (MemoryDatabase)', async () => {
  const db = new MemoryDatabase();
  const t0 = new Date().toISOString();

  // 1. Initial occupancy is 0
  const occ0 = await db.prepare("SELECT COUNT(*) as count FROM vehicle_sessions WHERE facility_id = ? AND status = 'INSIDE'")
    .bind('palika')
    .first<{ count: number }>();
  assert.equal(occ0?.count, 0);

  // 2. Insert first active INSIDE session
  const res1 = await db.prepare(
    'INSERT INTO vehicle_sessions (id, facility_id, plate_number, status, entry_camera_id, entry_time, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)'
  ).bind('ses-001', 'palika', 'DL01AB1234', 'INSIDE', 'palika-entry-1', t0, t0, t0).run();
  assert.equal(res1.meta?.changes, 1);

  // Live occupancy becomes 1
  const occ1 = await db.prepare("SELECT COUNT(*) as count FROM vehicle_sessions WHERE facility_id = ? AND status = 'INSIDE'")
    .bind('palika')
    .first<{ count: number }>();
  assert.equal(occ1?.count, 1);

  // Active session lookup works
  const activeSession = await db.prepare("SELECT * FROM vehicle_sessions WHERE facility_id = ? AND plate_number = ? AND status = 'INSIDE'")
    .bind('palika', 'DL01AB1234')
    .first<VehicleSession>();
  assert.ok(activeSession);
  assert.equal(activeSession.id, 'ses-001');

  // 3. Attempting to insert a duplicate active session for DL01AB1234 in palika MUST throw
  await assert.rejects(
    async () => {
      await db.prepare(
        'INSERT INTO vehicle_sessions (id, facility_id, plate_number, status, entry_camera_id, entry_time, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)'
      ).bind('ses-002', 'palika', 'DL01AB1234', 'INSIDE', 'palika-entry-1', t0, t0, t0).run();
    },
    (err: Error) => {
      assert.ok(err.message.includes('SQLITE_CONSTRAINT: UNIQUE constraint failed'));
      return true;
    }
  );

  // 4. INSERT OR IGNORE returns 0 changes on collision without throwing
  const ignoreRes = await db.prepare(
    'INSERT OR IGNORE INTO vehicle_sessions (id, facility_id, plate_number, status, entry_camera_id, entry_time, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)'
  ).bind('ses-002', 'palika', 'DL01AB1234', 'INSIDE', 'palika-entry-1', t0, t0, t0).run();
  assert.equal(ignoreRes.meta?.changes, 0);

  // 5. Active session for DIFFERENT facility (e.g. cp-block-a) is allowed
  const diffFacilityRes = await db.prepare(
    'INSERT INTO vehicle_sessions (id, facility_id, plate_number, status, entry_camera_id, entry_time, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)'
  ).bind('ses-diff', 'cp-block-a', 'DL01AB1234', 'INSIDE', 'cp-entry-1', t0, t0, t0).run();
  assert.equal(diffFacilityRes.meta?.changes, 1);

  // 6. Exit transition decrements occupancy
  const tExit = new Date(Date.now() + 3600000).toISOString();
  const exitRes = await db.prepare(
    "UPDATE vehicle_sessions SET status = 'EXITED', exit_event_id = ?, exit_camera_id = ?, exit_time = ?, duration_seconds = ?, calculated_tariff = ?, updated_at = ? WHERE id = ? AND status = 'INSIDE'"
  ).bind('evt-exit-1', 'palika-exit-1', tExit, 3600, 40.0, tExit, 'ses-001').run();
  assert.equal(exitRes.meta?.changes, 1);

  // Palika live occupancy transitions back to 0
  const occAfterExit = await db.prepare("SELECT COUNT(*) as count FROM vehicle_sessions WHERE facility_id = ? AND status = 'INSIDE'")
    .bind('palika')
    .first<{ count: number }>();
  assert.equal(occAfterExit?.count, 0);

  // 7. Subsequent new entry for DL01AB1234 is now permitted (historic EXITED records do not block it)
  const tReentry = new Date(Date.now() + 7200000).toISOString();
  const reentryRes = await db.prepare(
    'INSERT INTO vehicle_sessions (id, facility_id, plate_number, status, entry_camera_id, entry_time, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)'
  ).bind('ses-003', 'palika', 'DL01AB1234', 'INSIDE', 'palika-entry-1', tReentry, tReentry, tReentry).run();
  assert.equal(reentryRes.meta?.changes, 1);

  const occReentry = await db.prepare("SELECT COUNT(*) as count FROM vehicle_sessions WHERE facility_id = ? AND status = 'INSIDE'")
    .bind('palika')
    .first<{ count: number }>();
  assert.equal(occReentry?.count, 1);
});

test('M1: ANPR Events review queue and cooldown check', async () => {
  const db = new MemoryDatabase();
  const t0 = new Date(Date.now() - 60000).toISOString();
  const t1 = new Date(Date.now() - 30000).toISOString();
  const t2 = new Date(Date.now() - 10000).toISOString();

  // Ingest 3 events: one accepted, one needs review, one unmatched exit
  await db.prepare(
    'INSERT INTO anpr_events (id, facility_id, camera_id, gate_type, plate_number, confidence, processing_time_ms, status, review_reason, detected_at, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'
  ).bind('evt-1', 'palika', 'palika-entry-1', 'ENTRY', 'DL01AB1234', 0.95, 45, 'ACCEPTED', null, t0, t0).run();

  await db.prepare(
    'INSERT INTO anpr_events (id, facility_id, camera_id, gate_type, plate_number, confidence, processing_time_ms, status, review_reason, detected_at, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'
  ).bind('evt-2', 'palika', 'palika-entry-1', 'ENTRY', 'HR26DK8392', 0.65, 50, 'NEEDS_REVIEW', 'LOW_CONFIDENCE', t1, t1).run();

  await db.prepare(
    'INSERT INTO anpr_events (id, facility_id, camera_id, gate_type, plate_number, confidence, processing_time_ms, status, review_reason, detected_at, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'
  ).bind('evt-3', 'palika', 'palika-exit-1', 'EXIT', 'UP16AB9999', 0.92, 40, 'UNMATCHED_EXIT', 'NO_ACTIVE_SESSION', t2, t2).run();

  // Review queue query: status IN ('NEEDS_REVIEW', 'UNMATCHED_EXIT')
  const reviewQueue = await db.prepare(
    "SELECT * FROM anpr_events WHERE facility_id = ? AND status IN ('NEEDS_REVIEW', 'UNMATCHED_EXIT') ORDER BY detected_at DESC"
  ).bind('palika').all<AnprEvent>();

  assert.equal(reviewQueue.results.length, 2);
  assert.equal(reviewQueue.results[0].id, 'evt-3');
  assert.equal(reviewQueue.results[1].id, 'evt-2');

  // Cooldown query: events within last 45 seconds for camera palika-entry-1 and plate HR26DK8392
  const thresholdTime = new Date(Date.now() - 45000).toISOString();
  const recentEvents = await db.prepare(
    'SELECT * FROM anpr_events WHERE camera_id = ? AND plate_number = ? AND detected_at > ?'
  ).bind('palika-entry-1', 'HR26DK8392', thresholdTime).all<AnprEvent>();

  assert.equal(recentEvents.results.length, 1);
  assert.equal(recentEvents.results[0].id, 'evt-2');

  // Cooldown query before threshold returns empty
  const oldThreshold = new Date().toISOString();
  const noRecentEvents = await db.prepare(
    'SELECT * FROM anpr_events WHERE camera_id = ? AND plate_number = ? AND detected_at > ?'
  ).bind('palika-entry-1', 'HR26DK8392', oldThreshold).all<AnprEvent>();

  assert.equal(noRecentEvents.results.length, 0);
});

test('M1: SQLite DDL Migration and Partial Unique Index Verification', () => {
  // Execute migrations against real SQLite to verify compatibility of DDL and partial unique index
  const pyScript = `
import sqlite3

conn = sqlite3.connect(':memory:')
conn.execute('PRAGMA foreign_keys = ON;')

files = ['drizzle/0000_smart_prima.sql', 'drizzle/0001_panoramic_edwin_jarvis.sql', 'drizzle/0002_anpr_tables.sql']
for fpath in files:
    with open(fpath, 'r', encoding='utf-8') as f:
        for stmt in f.read().split('--> statement-breakpoint'):
            s = stmt.strip()
            if s:
                conn.execute(s)

# Insert facility, camera, vehicle
conn.execute("INSERT INTO facilities (id, name, lat, lng, payload) VALUES ('palika', 'Palika', 28.63, 77.21, '{}')")
conn.execute("INSERT INTO parking_cameras (id, facility_id, name, feed_type, gate_type, status, created_at, updated_at) VALUES ('cam-1', 'palika', 'Entry Gate', 'USB', 'ENTRY', 'ONLINE', '2026-11-21T00:00:00Z', '2026-11-21T00:00:00Z')")
conn.execute("INSERT INTO vehicles (plate_number, state_code, vehicle_class, first_seen_at, last_seen_at, total_sessions, created_at) VALUES ('DL01AB1234', 'DL', 'CAR', '2026-11-21T00:00:00Z', '2026-11-21T00:00:00Z', 1, '2026-11-21T00:00:00Z')")

# Insert first active session
conn.execute("INSERT INTO vehicle_sessions (id, facility_id, plate_number, status, entry_camera_id, entry_time, created_at, updated_at) VALUES ('ses-1', 'palika', 'DL01AB1234', 'INSIDE', 'cam-1', '2026-11-21T00:00:00Z', '2026-11-21T00:00:00Z', '2026-11-21T00:00:00Z')")

# Attempt duplicate INSIDE session -> must raise IntegrityError
duplicate_rejected = False
try:
    conn.execute("INSERT INTO vehicle_sessions (id, facility_id, plate_number, status, entry_camera_id, entry_time, created_at, updated_at) VALUES ('ses-2', 'palika', 'DL01AB1234', 'INSIDE', 'cam-1', '2026-11-21T00:05:00Z', '2026-11-21T00:05:00Z', '2026-11-21T00:05:00Z')")
except sqlite3.IntegrityError:
    duplicate_rejected = True

assert duplicate_rejected, "SQLite partial unique index failed to reject duplicate INSIDE session"

# Exit first session
conn.execute("UPDATE vehicle_sessions SET status = 'EXITED', exit_time = '2026-11-21T01:00:00Z' WHERE id = 'ses-1'")

# Insert new INSIDE session after exit -> must succeed
conn.execute("INSERT INTO vehicle_sessions (id, facility_id, plate_number, status, entry_camera_id, entry_time, created_at, updated_at) VALUES ('ses-3', 'palika', 'DL01AB1234', 'INSIDE', 'cam-1', '2026-11-21T02:00:00Z', '2026-11-21T02:00:00Z', '2026-11-21T02:00:00Z')")

cur = conn.cursor()
cur.execute("SELECT COUNT(*) FROM vehicle_sessions WHERE facility_id = 'palika' AND status = 'INSIDE'")
count = cur.fetchone()[0]
assert count == 1, f"Expected 1 active session, got {count}"

# Test foreign key enforcement
fk_rejected = False
try:
    conn.execute("INSERT INTO vehicle_sessions (id, facility_id, plate_number, status, entry_camera_id, entry_time, created_at, updated_at) VALUES ('ses-invalid', 'non-existent-facility', 'DL01AB1234', 'INSIDE', 'cam-1', '2026-11-21T03:00:00Z', '2026-11-21T03:00:00Z', '2026-11-21T03:00:00Z')")
except sqlite3.IntegrityError:
    fk_rejected = True
assert fk_rejected, "SQLite FK enforcement failed on invalid facility"

# Test check constraint enforcement
check_rejected = False
try:
    conn.execute("INSERT INTO parking_cameras (id, facility_id, name, feed_type, gate_type, status, created_at, updated_at) VALUES ('cam-bad', 'palika', 'Bad Cam', 'INVALID_FEED', 'ENTRY', 'ONLINE', '2026-11-21T00:00:00Z', '2026-11-21T00:00:00Z')")
except sqlite3.IntegrityError:
    check_rejected = True
assert check_rejected, "SQLite CHECK constraint failed on invalid feed_type"

print("SQLITE_VERIFIED")
`;

  const b64 = Buffer.from(pyScript, 'utf8').toString('base64');
  const output = execSync(`python -c "import base64; exec(base64.b64decode('${b64}').decode('utf-8'))"`, {
    cwd: process.cwd(),
    encoding: 'utf8'
  });

  assert.ok(output.includes('SQLITE_VERIFIED'), 'SQLite DDL, foreign keys, check constraints, and partial unique index must verify cleanly');
});

test('M1: Multi-vehicle live occupancy aggregation and case-insensitive plate lookup', async () => {
  const db = new MemoryDatabase();
  const t0 = new Date().toISOString();

  // Insert 3 vehicles
  const plates = ['DL01AB1001', 'DL01AB1002', 'DL01AB1003'];
  for (let i = 0; i < plates.length; i++) {
    await db.prepare(
      'INSERT INTO vehicles (plate_number, state_code, vehicle_class, first_seen_at, last_seen_at, total_sessions, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)'
    ).bind(plates[i], 'DL', 'CAR', t0, t0, 1, t0).run();

    await db.prepare(
      'INSERT INTO vehicle_sessions (id, facility_id, plate_number, status, entry_camera_id, entry_time, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)'
    ).bind(`ses-${i + 1}`, 'palika', plates[i], 'INSIDE', 'palika-entry-1', t0, t0, t0).run();
  }

  // Occupancy should be 3
  const occ3 = await db.prepare("SELECT COUNT(*) as count FROM vehicle_sessions WHERE facility_id = ? AND status = 'INSIDE'")
    .bind('palika')
    .first<{ count: number }>();
  assert.equal(occ3?.count, 3);

  // Case-insensitive lookup (lowercase 'dl01ab1002')
  const found = await db.prepare("SELECT * FROM vehicle_sessions WHERE facility_id = ? AND plate_number = ? AND status = 'INSIDE'")
    .bind('palika', 'dl01ab1002')
    .first<VehicleSession>();
  assert.ok(found);
  assert.equal(found.id, 'ses-2');

  // Exit vehicle 2
  await db.prepare(
    "UPDATE vehicle_sessions SET status = 'EXITED', exit_time = ?, updated_at = ? WHERE id = ? AND status = 'INSIDE'"
  ).bind(t0, t0, 'ses-2').run();

  // Occupancy transitions to 2
  const occ2 = await db.prepare("SELECT COUNT(*) as count FROM vehicle_sessions WHERE facility_id = ? AND status = 'INSIDE'")
    .bind('palika')
    .first<{ count: number }>();
  assert.equal(occ2?.count, 2);
});
