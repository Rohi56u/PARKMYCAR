CREATE TABLE `geocode_cache` (
	`key` text PRIMARY KEY NOT NULL,
	`payload` text NOT NULL,
	`retrieved_at` text NOT NULL,
	`expires_at` integer NOT NULL,
	CONSTRAINT "geocode_payload" CHECK(json_valid("geocode_cache"."payload"))
);
--> statement-breakpoint
CREATE INDEX `geocode_expiry_idx` ON `geocode_cache` (`expires_at`);