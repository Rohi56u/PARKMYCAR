import { sql, relations } from 'drizzle-orm';
import { sqliteTable, text, integer, real, index, uniqueIndex, check } from 'drizzle-orm/sqlite-core';

export const facilities = sqliteTable('facilities', { id:text('id').primaryKey(), name:text('name').notNull(), lat:real('lat').notNull(), lng:real('lng').notNull(), active:integer('active').notNull().default(1), version:integer('version').notNull().default(1), payload:text('payload').notNull() },t=>[index('facility_geo_idx').on(t.active,t.lat,t.lng),check('facility_lat',sql`${t.lat} BETWEEN 6 AND 38`),check('facility_lng',sql`${t.lng} BETWEEN 68 AND 98`),check('facility_payload',sql`json_valid(${t.payload})`)]);
export const observations = sqliteTable('observations',{id:text('id').primaryKey(),facilityId:text('facility_id').notNull().references(()=>facilities.id),state:text('state').notNull(),evidenceClass:text('evidence_class').notNull(),source:text('source').notNull(),observedAt:text('observed_at').notNull(),expiresAt:text('expires_at').notNull()},t=>[index('observation_lookup_idx').on(t.facilityId,t.expiresAt),check('observation_time',sql`${t.expiresAt} > ${t.observedAt}`),check('observation_state',sql`${t.state} IN ('AVAILABLE','LIMITED','FULL','UNKNOWN')`),check('observation_class',sql`${t.evidenceClass} IN ('OPERATOR_REPORTED','COMMUNITY_REPORTED')`)]);
export const members = sqliteTable('members',{userId:text('user_id').primaryKey(),role:text('role').notNull(),displayName:text('display_name').notNull(),facilityIds:text('facility_ids').notNull().default('[]')},t=>[check('member_role',sql`${t.role} IN ('ADMIN','OPERATOR','REVIEWER')`),check('member_facilities',sql`json_valid(${t.facilityIds})`)]);
export const settings = sqliteTable('settings',{key:text('key').primaryKey(),value:text('value').notNull()});
export const reports = sqliteTable('reports',{id:text('id').primaryKey(),facilityId:text('facility_id').notNull().references(()=>facilities.id),category:text('category').notNull(),observedAt:text('observed_at').notNull(),createdAt:text('created_at').notNull(),status:text('status').notNull().default('PENDING'),dedupKey:text('dedup_key').notNull().unique()},t=>[index('report_status_idx').on(t.status,t.createdAt),check('report_category',sql`${t.category} IN ('FOUND_SPACE','FULL','CLOSED','DETAILS_WRONG')`),check('report_status',sql`${t.status} IN ('PENDING','APPROVED','REJECTED','RESOLVED')`)]);
export const changes = sqliteTable('listing_changes',{id:text('id').primaryKey(),facilityId:text('facility_id').notNull().references(()=>facilities.id),actorId:text('actor_id').notNull(),payload:text('payload').notNull(),status:text('status').notNull().default('PENDING'),createdAt:text('created_at').notNull()},t=>[check('change_payload',sql`json_valid(${t.payload})`)]);
export const audit = sqliteTable('audit_events',{id:text('id').primaryKey(),actorId:text('actor_id').notNull(),action:text('action').notNull(),entityId:text('entity_id').notNull(),fields:text('fields').notNull(),createdAt:text('created_at').notNull()},t=>[index('audit_time_idx').on(t.createdAt)]);
export const limits = sqliteTable('request_limits',{key:text('key').primaryKey(),count:integer('count').notNull(),expiresAt:integer('expires_at').notNull()});
export const geocodeCache = sqliteTable('geocode_cache',{key:text('key').primaryKey(),payload:text('payload').notNull(),retrievedAt:text('retrieved_at').notNull(),expiresAt:integer('expires_at').notNull()},t=>[index('geocode_expiry_idx').on(t.expiresAt),check('geocode_payload',sql`json_valid(${t.payload})`)]);

// ==========================================
// ANPR & PARKING OCCUPANCY TABLES (MILESTONE 1)
// ==========================================

export const parkingCameras = sqliteTable('parking_cameras', {
  id: text('id').primaryKey(),
  facilityId: text('facility_id').notNull().references(() => facilities.id),
  name: text('name').notNull(),
  feedType: text('feed_type').notNull(),
  streamUrl: text('stream_url'),
  gateType: text('gate_type').notNull(),
  status: text('status').notNull().default('OFFLINE'),
  lastHeartbeatAt: text('last_heartbeat_at'),
  fps: real('fps'),
  config: text('config'),
  createdAt: text('created_at').notNull(),
  updatedAt: text('updated_at').notNull()
}, t => [
  index('camera_facility_idx').on(t.facilityId, t.status),
  check('camera_feed_type', sql`${t.feedType} IN ('USB','IP_RTSP','VIDEO_FILE','SIMULATION')`),
  check('camera_gate_type', sql`${t.gateType} IN ('ENTRY','EXIT','BIDIRECTIONAL')`),
  check('camera_status', sql`${t.status} IN ('ONLINE','DEGRADED','OFFLINE','SIMULATING')`),
  check('camera_config_json', sql`${t.config} IS NULL OR json_valid(${t.config})`)
]);

export const vehicles = sqliteTable('vehicles', {
  plateNumber: text('plate_number').primaryKey(),
  stateCode: text('state_code'),
  vehicleClass: text('vehicle_class').notNull().default('CAR'),
  firstSeenAt: text('first_seen_at').notNull(),
  lastSeenAt: text('last_seen_at').notNull(),
  totalSessions: integer('total_sessions').notNull().default(0),
  createdAt: text('created_at').notNull()
}, t => [
  index('vehicle_class_idx').on(t.vehicleClass),
  check('vehicle_class_check', sql`${t.vehicleClass} IN ('CAR','TWO_WHEELER','COMMERCIAL','UNKNOWN')`)
]);

export const vehicleSessions = sqliteTable('vehicle_sessions', {
  id: text('id').primaryKey(),
  facilityId: text('facility_id').notNull().references(() => facilities.id),
  plateNumber: text('plate_number').notNull().references(() => vehicles.plateNumber),
  status: text('status').notNull(),
  entryEventId: text('entry_event_id'),
  entryCameraId: text('entry_camera_id').references(() => parkingCameras.id),
  entryTime: text('entry_time').notNull(),
  exitEventId: text('exit_event_id'),
  exitCameraId: text('exit_camera_id').references(() => parkingCameras.id),
  exitTime: text('exit_time'),
  durationSeconds: integer('duration_seconds'),
  calculatedTariff: real('calculated_tariff'),
  reviewStatus: text('review_status'),
  operatorNotes: text('operator_notes'),
  createdAt: text('created_at').notNull(),
  updatedAt: text('updated_at').notNull()
}, t => [
  uniqueIndex('unique_active_vehicle_session').on(t.facilityId, t.plateNumber).where(sql`${t.status} = 'INSIDE'`),
  index('session_lookup_idx').on(t.facilityId, t.status, t.entryTime),
  index('session_plate_idx').on(t.plateNumber, t.createdAt),
  check('session_status_check', sql`${t.status} IN ('INSIDE','EXITED','OVERSTAY','NEEDS_REVIEW','CANCELLED')`),
  check('session_review_status', sql`${t.reviewStatus} IS NULL OR ${t.reviewStatus} IN ('VERIFIED','NEEDS_REVIEW','MANUALLY_CORRECTED','REJECTED')`)
]);

export const anprEvents = sqliteTable('anpr_events', {
  id: text('id').primaryKey(),
  facilityId: text('facility_id').notNull().references(() => facilities.id),
  cameraId: text('camera_id').notNull().references(() => parkingCameras.id),
  gateType: text('gate_type').notNull(),
  plateNumber: text('plate_number').notNull(),
  confidence: real('confidence').notNull(),
  plateCropUrl: text('plate_crop_url'),
  fullFrameUrl: text('full_frame_url'),
  processingTimeMs: integer('processing_time_ms'),
  status: text('status').notNull(),
  reviewReason: text('review_reason'),
  sessionId: text('session_id').references(() => vehicleSessions.id),
  detectedAt: text('detected_at').notNull(),
  createdAt: text('created_at').notNull()
}, t => [
  index('anpr_events_review_idx').on(t.facilityId, t.status, t.detectedAt),
  index('anpr_events_cooldown_idx').on(t.cameraId, t.plateNumber, t.detectedAt),
  check('anpr_gate_type', sql`${t.gateType} IN ('ENTRY','EXIT')`),
  check('anpr_status', sql`${t.status} IN ('ACCEPTED','COOLDOWN_IGNORED','NEEDS_REVIEW','MANUALLY_RESOLVED','UNMATCHED_EXIT','REJECTED')`)
]);

// Inferred Types
export type ParkingCamera = typeof parkingCameras.$inferSelect;
export type NewParkingCamera = typeof parkingCameras.$inferInsert;
export type Vehicle = typeof vehicles.$inferSelect;
export type NewVehicle = typeof vehicles.$inferInsert;
export type VehicleSession = typeof vehicleSessions.$inferSelect;
export type NewVehicleSession = typeof vehicleSessions.$inferInsert;
export type AnprEvent = typeof anprEvents.$inferSelect;
export type NewAnprEvent = typeof anprEvents.$inferInsert;

// Entity Relations
export const facilitiesRelations = relations(facilities, ({ many }) => ({
  cameras: many(parkingCameras),
  sessions: many(vehicleSessions),
  anprEvents: many(anprEvents),
}));

export const parkingCamerasRelations = relations(parkingCameras, ({ one, many }) => ({
  facility: one(facilities, { fields: [parkingCameras.facilityId], references: [facilities.id] }),
  entrySessions: many(vehicleSessions, { relationName: 'entryCamera' }),
  exitSessions: many(vehicleSessions, { relationName: 'exitCamera' }),
  events: many(anprEvents),
}));

export const vehiclesRelations = relations(vehicles, ({ many }) => ({
  sessions: many(vehicleSessions),
}));

export const vehicleSessionsRelations = relations(vehicleSessions, ({ one, many }) => ({
  facility: one(facilities, { fields: [vehicleSessions.facilityId], references: [facilities.id] }),
  vehicle: one(vehicles, { fields: [vehicleSessions.plateNumber], references: [vehicles.plateNumber] }),
  entryCamera: one(parkingCameras, { fields: [vehicleSessions.entryCameraId], references: [parkingCameras.id], relationName: 'entryCamera' }),
  exitCamera: one(parkingCameras, { fields: [vehicleSessions.exitCameraId], references: [parkingCameras.id], relationName: 'exitCamera' }),
  events: many(anprEvents),
}));

export const anprEventsRelations = relations(anprEvents, ({ one }) => ({
  facility: one(facilities, { fields: [anprEvents.facilityId], references: [facilities.id] }),
  camera: one(parkingCameras, { fields: [anprEvents.cameraId], references: [parkingCameras.id] }),
  session: one(vehicleSessions, { fields: [anprEvents.sessionId], references: [vehicleSessions.id] }),
}));
