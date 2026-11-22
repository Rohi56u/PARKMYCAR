CREATE TABLE `parking_cameras` (
	`id` text PRIMARY KEY NOT NULL,
	`facility_id` text NOT NULL,
	`name` text NOT NULL,
	`feed_type` text NOT NULL,
	`stream_url` text,
	`gate_type` text NOT NULL,
	`status` text DEFAULT 'OFFLINE' NOT NULL,
	`last_heartbeat_at` text,
	`fps` real,
	`config` text,
	`created_at` text NOT NULL,
	`updated_at` text NOT NULL,
	FOREIGN KEY (`facility_id`) REFERENCES `facilities`(`id`) ON UPDATE no action ON DELETE no action,
	CONSTRAINT "camera_feed_type" CHECK("parking_cameras"."feed_type" IN ('USB','IP_RTSP','VIDEO_FILE','SIMULATION')),
	CONSTRAINT "camera_gate_type" CHECK("parking_cameras"."gate_type" IN ('ENTRY','EXIT','BIDIRECTIONAL')),
	CONSTRAINT "camera_status" CHECK("parking_cameras"."status" IN ('ONLINE','DEGRADED','OFFLINE','SIMULATING')),
	CONSTRAINT "camera_config_json" CHECK("parking_cameras"."config" IS NULL OR json_valid("parking_cameras"."config"))
);
--> statement-breakpoint
CREATE INDEX `camera_facility_idx` ON `parking_cameras` (`facility_id`,`status`);
--> statement-breakpoint
CREATE TABLE `vehicles` (
	`plate_number` text PRIMARY KEY NOT NULL,
	`state_code` text,
	`vehicle_class` text DEFAULT 'CAR' NOT NULL,
	`first_seen_at` text NOT NULL,
	`last_seen_at` text NOT NULL,
	`total_sessions` integer DEFAULT 0 NOT NULL,
	`created_at` text NOT NULL,
	CONSTRAINT "vehicle_class_check" CHECK("vehicles"."vehicle_class" IN ('CAR','TWO_WHEELER','COMMERCIAL','UNKNOWN'))
);
--> statement-breakpoint
CREATE INDEX `vehicle_class_idx` ON `vehicles` (`vehicle_class`);
--> statement-breakpoint
CREATE TABLE `vehicle_sessions` (
	`id` text PRIMARY KEY NOT NULL,
	`facility_id` text NOT NULL,
	`plate_number` text NOT NULL,
	`status` text NOT NULL,
	`entry_event_id` text,
	`entry_camera_id` text,
	`entry_time` text NOT NULL,
	`exit_event_id` text,
	`exit_camera_id` text,
	`exit_time` text,
	`duration_seconds` integer,
	`calculated_tariff` real,
	`review_status` text,
	`operator_notes` text,
	`created_at` text NOT NULL,
	`updated_at` text NOT NULL,
	FOREIGN KEY (`facility_id`) REFERENCES `facilities`(`id`) ON UPDATE no action ON DELETE no action,
	FOREIGN KEY (`plate_number`) REFERENCES `vehicles`(`plate_number`) ON UPDATE no action ON DELETE no action,
	FOREIGN KEY (`entry_camera_id`) REFERENCES `parking_cameras`(`id`) ON UPDATE no action ON DELETE no action,
	FOREIGN KEY (`exit_camera_id`) REFERENCES `parking_cameras`(`id`) ON UPDATE no action ON DELETE no action,
	CONSTRAINT "session_status_check" CHECK("vehicle_sessions"."status" IN ('INSIDE','EXITED','OVERSTAY','NEEDS_REVIEW','CANCELLED')),
	CONSTRAINT "session_review_status" CHECK("vehicle_sessions"."review_status" IS NULL OR "vehicle_sessions"."review_status" IN ('VERIFIED','NEEDS_REVIEW','MANUALLY_CORRECTED','REJECTED'))
);
--> statement-breakpoint
CREATE UNIQUE INDEX `unique_active_vehicle_session` ON `vehicle_sessions` (`facility_id`, `plate_number`) WHERE `status` = 'INSIDE';
--> statement-breakpoint
CREATE INDEX `session_lookup_idx` ON `vehicle_sessions` (`facility_id`,`status`,`entry_time`);
--> statement-breakpoint
CREATE INDEX `session_plate_idx` ON `vehicle_sessions` (`plate_number`,`created_at`);
--> statement-breakpoint
CREATE TABLE `anpr_events` (
	`id` text PRIMARY KEY NOT NULL,
	`facility_id` text NOT NULL,
	`camera_id` text NOT NULL,
	`gate_type` text NOT NULL,
	`plate_number` text NOT NULL,
	`confidence` real NOT NULL,
	`plate_crop_url` text,
	`full_frame_url` text,
	`processing_time_ms` integer,
	`status` text NOT NULL,
	`review_reason` text,
	`session_id` text,
	`detected_at` text NOT NULL,
	`created_at` text NOT NULL,
	FOREIGN KEY (`facility_id`) REFERENCES `facilities`(`id`) ON UPDATE no action ON DELETE no action,
	FOREIGN KEY (`camera_id`) REFERENCES `parking_cameras`(`id`) ON UPDATE no action ON DELETE no action,
	FOREIGN KEY (`session_id`) REFERENCES `vehicle_sessions`(`id`) ON UPDATE no action ON DELETE no action,
	CONSTRAINT "anpr_gate_type" CHECK("anpr_events"."gate_type" IN ('ENTRY','EXIT')),
	CONSTRAINT "anpr_status" CHECK("anpr_events"."status" IN ('ACCEPTED','COOLDOWN_IGNORED','NEEDS_REVIEW','MANUALLY_RESOLVED','UNMATCHED_EXIT','REJECTED'))
);
--> statement-breakpoint
CREATE INDEX `anpr_events_review_idx` ON `anpr_events` (`facility_id`,`status`,`detected_at`);
--> statement-breakpoint
CREATE INDEX `anpr_events_cooldown_idx` ON `anpr_events` (`camera_id`,`plate_number`,`detected_at`);
