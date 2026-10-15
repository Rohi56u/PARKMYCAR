CREATE TABLE `audit_events` (
	`id` text PRIMARY KEY NOT NULL,
	`actor_id` text NOT NULL,
	`action` text NOT NULL,
	`entity_id` text NOT NULL,
	`fields` text NOT NULL,
	`created_at` text NOT NULL
);
--> statement-breakpoint
CREATE INDEX `audit_time_idx` ON `audit_events` (`created_at`);--> statement-breakpoint
CREATE TABLE `listing_changes` (
	`id` text PRIMARY KEY NOT NULL,
	`facility_id` text NOT NULL,
	`actor_id` text NOT NULL,
	`payload` text NOT NULL,
	`status` text DEFAULT 'PENDING' NOT NULL,
	`created_at` text NOT NULL,
	FOREIGN KEY (`facility_id`) REFERENCES `facilities`(`id`) ON UPDATE no action ON DELETE no action,
	CONSTRAINT "change_payload" CHECK(json_valid("listing_changes"."payload"))
);
--> statement-breakpoint
CREATE TABLE `facilities` (
	`id` text PRIMARY KEY NOT NULL,
	`name` text NOT NULL,
	`lat` real NOT NULL,
	`lng` real NOT NULL,
	`active` integer DEFAULT 1 NOT NULL,
	`version` integer DEFAULT 1 NOT NULL,
	`payload` text NOT NULL,
	CONSTRAINT "facility_lat" CHECK("facilities"."lat" BETWEEN 6 AND 38),
	CONSTRAINT "facility_lng" CHECK("facilities"."lng" BETWEEN 68 AND 98),
	CONSTRAINT "facility_payload" CHECK(json_valid("facilities"."payload"))
);
--> statement-breakpoint
CREATE INDEX `facility_geo_idx` ON `facilities` (`active`,`lat`,`lng`);--> statement-breakpoint
CREATE TABLE `request_limits` (
	`key` text PRIMARY KEY NOT NULL,
	`count` integer NOT NULL,
	`expires_at` integer NOT NULL
);
--> statement-breakpoint
CREATE TABLE `members` (
	`user_id` text PRIMARY KEY NOT NULL,
	`role` text NOT NULL,
	`display_name` text NOT NULL,
	`facility_ids` text DEFAULT '[]' NOT NULL,
	CONSTRAINT "member_role" CHECK("members"."role" IN ('ADMIN','OPERATOR','REVIEWER')),
	CONSTRAINT "member_facilities" CHECK(json_valid("members"."facility_ids"))
);
--> statement-breakpoint
CREATE TABLE `observations` (
	`id` text PRIMARY KEY NOT NULL,
	`facility_id` text NOT NULL,
	`state` text NOT NULL,
	`evidence_class` text NOT NULL,
	`source` text NOT NULL,
	`observed_at` text NOT NULL,
	`expires_at` text NOT NULL,
	FOREIGN KEY (`facility_id`) REFERENCES `facilities`(`id`) ON UPDATE no action ON DELETE no action,
	CONSTRAINT "observation_time" CHECK("observations"."expires_at" > "observations"."observed_at"),
	CONSTRAINT "observation_state" CHECK("observations"."state" IN ('AVAILABLE','LIMITED','FULL','UNKNOWN')),
	CONSTRAINT "observation_class" CHECK("observations"."evidence_class" IN ('OPERATOR_REPORTED','COMMUNITY_REPORTED'))
);
--> statement-breakpoint
CREATE INDEX `observation_lookup_idx` ON `observations` (`facility_id`,`expires_at`);--> statement-breakpoint
CREATE TABLE `reports` (
	`id` text PRIMARY KEY NOT NULL,
	`facility_id` text NOT NULL,
	`category` text NOT NULL,
	`observed_at` text NOT NULL,
	`created_at` text NOT NULL,
	`status` text DEFAULT 'PENDING' NOT NULL,
	`dedup_key` text NOT NULL,
	FOREIGN KEY (`facility_id`) REFERENCES `facilities`(`id`) ON UPDATE no action ON DELETE no action,
	CONSTRAINT "report_category" CHECK("reports"."category" IN ('FOUND_SPACE','FULL','CLOSED','DETAILS_WRONG')),
	CONSTRAINT "report_status" CHECK("reports"."status" IN ('PENDING','APPROVED','REJECTED','RESOLVED'))
);
--> statement-breakpoint
CREATE UNIQUE INDEX `reports_dedup_key_unique` ON `reports` (`dedup_key`);--> statement-breakpoint
CREATE INDEX `report_status_idx` ON `reports` (`status`,`created_at`);--> statement-breakpoint
CREATE TABLE `settings` (
	`key` text PRIMARY KEY NOT NULL,
	`value` text NOT NULL
);
