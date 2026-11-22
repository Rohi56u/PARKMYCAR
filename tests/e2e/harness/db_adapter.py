"""Standalone SQLite Database Adapter for E2E Testing.

Executes Cloudflare D1 / SQLite schemas, enforces foreign key constraints,
creates partial unique indexes, and seeds default test facilities & cameras.
Authoritative occupancy is strictly derived from active vehicle sessions.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Optional


class DatabaseAdapter:
    """SQLite database manager for ParkMyCar ANPR E2E test harness."""

    DEFAULT_FACILITIES = [
        {
            "id": "palika",
            "name": "Palika Parking",
            "lat": 28.6313821,
            "lng": 77.2179101,
            "active": 1,
            "version": 1,
            "payload": {
                "totalCapacity": 900,
                "capacity": 900,
                "type": "underground",
                "coverage": "Connaught Place, New Delhi",
            },
        },
        {
            "id": "cp-west",
            "name": "CP West parking",
            "lat": 28.6323662,
            "lng": 77.2163371,
            "active": 1,
            "version": 1,
            "payload": {
                "totalCapacity": 150,
                "capacity": 150,
                "type": "street_side",
                "coverage": "Connaught Place, New Delhi",
            },
        },
        {
            "id": "cp-east",
            "name": "CP East parking",
            "lat": 28.6333333,
            "lng": 77.2210363,
            "active": 1,
            "version": 1,
            "payload": {
                "totalCapacity": 200,
                "capacity": 200,
                "type": "surface",
                "coverage": "Connaught Place, New Delhi",
            },
        },
        {
            "id": "cp-north",
            "name": "CP North parking",
            "lat": 28.6340348,
            "lng": 77.2192007,
            "active": 1,
            "version": 1,
            "payload": {
                "totalCapacity": 100,
                "capacity": 100,
                "type": "surface",
                "coverage": "Connaught Place, New Delhi",
            },
        },
        {
            "id": "cp-south",
            "name": "CP South parking",
            "lat": 28.6284451,
            "lng": 77.2167505,
            "active": 1,
            "version": 1,
            "payload": {
                "totalCapacity": 120,
                "capacity": 120,
                "type": "surface",
                "coverage": "Connaught Place, New Delhi",
            },
        },
    ]

    DEFAULT_CAMERAS = [
        {
            "id": "palika-entry-1",
            "facility_id": "palika",
            "name": "Palika Entry Gate 1",
            "feed_type": "SIMULATION",
            "stream_url": "simulation://palika/entry/1",
            "gate_type": "ENTRY",
            "status": "ONLINE",
            "fps": 25.0,
            "config": json.dumps({"resolution": "1920x1080", "sensitivity": "HIGH"}),
        },
        {
            "id": "palika-exit-1",
            "facility_id": "palika",
            "name": "Palika Exit Gate 1",
            "feed_type": "SIMULATION",
            "stream_url": "simulation://palika/exit/1",
            "gate_type": "EXIT",
            "status": "ONLINE",
            "fps": 25.0,
            "config": json.dumps({"resolution": "1920x1080", "sensitivity": "HIGH"}),
        },
        {
            "id": "palika-sim-entry",
            "facility_id": "palika",
            "name": "Palika Simulation Gate",
            "feed_type": "SIMULATION",
            "stream_url": "simulation://palika/sim-entry",
            "gate_type": "ENTRY",
            "status": "ONLINE",
            "fps": 30.0,
            "config": json.dumps({"mode": "synthetic", "batch_size": 10}),
        },
    ]

    def __init__(self, db_path: str = ":memory:"):
        """Initialize SQLite database connection with foreign key enforcement."""
        self.db_path = db_path
        self._conn = sqlite3.connect(
            self.db_path,
            check_same_thread=False,
            isolation_level=None,  # Autocommit mode by default
        )
        self._conn.row_factory = sqlite3.Row
        # Strictly enforce foreign key constraints
        self._conn.execute("PRAGMA foreign_keys = ON;")
        self.init_schema()
        self.seed_defaults()

    def get_connection(self) -> sqlite3.Connection:
        """Return the raw sqlite3 connection."""
        return self._conn

    def init_schema(self) -> None:
        """Execute D1 DDL statements creating core ParkMyCar & ANPR tables."""
        cursor = self._conn.cursor()

        # 1. Facilities
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS facilities (
                id text PRIMARY KEY NOT NULL,
                name text NOT NULL,
                lat real NOT NULL,
                lng real NOT NULL,
                active integer DEFAULT 1 NOT NULL,
                version integer DEFAULT 1 NOT NULL,
                payload text NOT NULL
            );
            """
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS facility_geo_idx ON facilities (active, lat, lng);"
        )

        # 2. Observations
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS observations (
                id text PRIMARY KEY NOT NULL,
                facility_id text NOT NULL,
                state text NOT NULL,
                evidence_class text NOT NULL,
                source text NOT NULL,
                observed_at text NOT NULL,
                expires_at text NOT NULL,
                FOREIGN KEY (facility_id) REFERENCES facilities(id) ON UPDATE NO ACTION ON DELETE NO ACTION
            );
            """
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS observation_lookup_idx ON observations (facility_id, expires_at);"
        )

        # 3. Members
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS members (
                user_id text PRIMARY KEY NOT NULL,
                role text NOT NULL,
                display_name text NOT NULL,
                facility_ids text DEFAULT '[]' NOT NULL
            );
            """
        )

        # 4. Reports
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS reports (
                id text PRIMARY KEY NOT NULL,
                facility_id text NOT NULL,
                category text NOT NULL,
                observed_at text NOT NULL,
                created_at text NOT NULL,
                status text DEFAULT 'PENDING' NOT NULL,
                dedup_key text NOT NULL UNIQUE,
                FOREIGN KEY (facility_id) REFERENCES facilities(id) ON UPDATE NO ACTION ON DELETE NO ACTION
            );
            """
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS report_status_idx ON reports (status, created_at);"
        )

        # 5. Audit Events
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_events (
                id text PRIMARY KEY NOT NULL,
                actor_id text NOT NULL,
                action text NOT NULL,
                entity_id text NOT NULL,
                fields text NOT NULL,
                created_at text NOT NULL
            );
            """
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS audit_time_idx ON audit_events (created_at);"
        )

        # 6. Parking Cameras
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS parking_cameras (
                id text PRIMARY KEY NOT NULL,
                facility_id text NOT NULL,
                name text NOT NULL,
                feed_type text NOT NULL,
                stream_url text,
                gate_type text NOT NULL,
                status text NOT NULL,
                last_heartbeat_at text,
                fps real,
                config text,
                created_at text NOT NULL,
                updated_at text NOT NULL,
                FOREIGN KEY (facility_id) REFERENCES facilities(id) ON UPDATE NO ACTION ON DELETE NO ACTION
            );
            """
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS camera_facility_idx ON parking_cameras (facility_id, status);"
        )

        # 7. Vehicles
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS vehicles (
                plate_number text PRIMARY KEY NOT NULL,
                state_code text,
                vehicle_class text DEFAULT 'CAR',
                first_seen_at text NOT NULL,
                last_seen_at text NOT NULL,
                total_sessions integer DEFAULT 0,
                created_at text NOT NULL
            );
            """
        )

        # 8. Vehicle Sessions
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS vehicle_sessions (
                id text PRIMARY KEY NOT NULL,
                facility_id text NOT NULL,
                plate_number text NOT NULL,
                status text NOT NULL,
                entry_event_id text,
                entry_camera_id text,
                entry_time text NOT NULL,
                exit_event_id text,
                exit_camera_id text,
                exit_time text,
                duration_seconds integer,
                calculated_tariff real,
                review_status text DEFAULT 'VERIFIED',
                operator_notes text,
                created_at text NOT NULL,
                updated_at text NOT NULL,
                FOREIGN KEY (facility_id) REFERENCES facilities(id) ON UPDATE NO ACTION ON DELETE NO ACTION,
                FOREIGN KEY (plate_number) REFERENCES vehicles(plate_number) ON UPDATE NO ACTION ON DELETE NO ACTION,
                FOREIGN KEY (entry_camera_id) REFERENCES parking_cameras(id) ON UPDATE NO ACTION ON DELETE NO ACTION,
                FOREIGN KEY (exit_camera_id) REFERENCES parking_cameras(id) ON UPDATE NO ACTION ON DELETE NO ACTION
            );
            """
        )
        # Partial unique index: strictly prevent concurrent duplicate active sessions
        cursor.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS unique_active_vehicle_session
            ON vehicle_sessions(facility_id, plate_number)
            WHERE status = 'INSIDE';
            """
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS session_facility_status_idx ON vehicle_sessions (facility_id, status);"
        )

        # 9. ANPR Events
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS anpr_events (
                id text PRIMARY KEY NOT NULL,
                facility_id text NOT NULL,
                camera_id text NOT NULL,
                gate_type text NOT NULL,
                plate_number text,
                confidence real,
                plate_crop_url text,
                full_frame_url text,
                processing_time_ms integer,
                status text NOT NULL,
                review_reason text,
                session_id text,
                detected_at text NOT NULL,
                created_at text NOT NULL,
                FOREIGN KEY (facility_id) REFERENCES facilities(id) ON UPDATE NO ACTION ON DELETE NO ACTION,
                FOREIGN KEY (camera_id) REFERENCES parking_cameras(id) ON UPDATE NO ACTION ON DELETE NO ACTION,
                FOREIGN KEY (session_id) REFERENCES vehicle_sessions(id) ON UPDATE NO ACTION ON DELETE SET NULL
            );
            """
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS anpr_event_lookup_idx ON anpr_events (facility_id, status, detected_at);"
        )

    def seed_defaults(self) -> None:
        """Seed default facilities and camera fixtures."""
        iso_now = datetime.now(timezone.utc).isoformat()
        cursor = self._conn.cursor()

        # Seed facilities
        for f in self.DEFAULT_FACILITIES:
            cursor.execute(
                """
                INSERT OR IGNORE INTO facilities (id, name, lat, lng, active, version, payload)
                VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    f["id"],
                    f["name"],
                    f["lat"],
                    f["lng"],
                    f["active"],
                    f["version"],
                    json.dumps(f["payload"]),
                ),
            )

        # Seed cameras
        for c in self.DEFAULT_CAMERAS:
            cursor.execute(
                """
                INSERT OR IGNORE INTO parking_cameras
                (id, facility_id, name, feed_type, stream_url, gate_type, status, last_heartbeat_at, fps, config, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    c["id"],
                    c["facility_id"],
                    c["name"],
                    c["feed_type"],
                    c["stream_url"],
                    c["gate_type"],
                    c["status"],
                    iso_now,
                    c["fps"],
                    c["config"],
                    iso_now,
                    iso_now,
                ),
            )

    def query(self, sql: str, params: tuple | list = ()) -> list[dict[str, Any]]:
        """Execute a SELECT query and return rows as dictionaries."""
        cursor = self._conn.cursor()
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def query_one(self, sql: str, params: tuple | list = ()) -> Optional[dict[str, Any]]:
        """Execute a SELECT query and return single row as dict, or None."""
        cursor = self._conn.cursor()
        cursor.execute(sql, params)
        row = cursor.fetchone()
        return dict(row) if row else None

    def execute(self, sql: str, params: tuple | list = ()) -> int:
        """Execute a DML statement and return affected row count or lastrowid."""
        cursor = self._conn.cursor()
        cursor.execute(sql, params)
        return cursor.rowcount

    def executemany(self, sql: str, seq_of_params: list[tuple | list]) -> int:
        """Execute batch DML statements and return affected count."""
        cursor = self._conn.cursor()
        cursor.executemany(sql, seq_of_params)
        return cursor.rowcount

    def get_facility(self, facility_id: str) -> Optional[dict[str, Any]]:
        """Retrieve facility record and parse payload."""
        rec = self.query_one("SELECT * FROM facilities WHERE id = ?", (facility_id,))
        if rec and "payload" in rec and isinstance(rec["payload"], str):
            try:
                rec["parsed_payload"] = json.loads(rec["payload"])
            except json.JSONDecodeError:
                rec["parsed_payload"] = {}
        return rec

    def get_facility_total_capacity(self, facility_id: str) -> int:
        """Extract total capacity for facility, defaulting to 900 for palika."""
        rec = self.get_facility(facility_id)
        if not rec:
            return 900 if facility_id == "palika" else 100
        payload = rec.get("parsed_payload", {})
        capacity = payload.get("totalCapacity") or payload.get("capacity")
        if capacity is not None:
            return int(capacity)
        return 900 if facility_id == "palika" else 100

    def get_active_session(
        self, facility_id: str, plate_number: str
    ) -> Optional[dict[str, Any]]:
        """Retrieve active INSIDE session for a vehicle at a facility."""
        return self.query_one(
            """
            SELECT * FROM vehicle_sessions
            WHERE facility_id = ? AND plate_number = ? AND status = 'INSIDE'
            LIMIT 1;
            """,
            (facility_id, plate_number),
        )

    def get_live_occupancy(self, facility_id: str) -> int:
        """Authoritatively calculate live occupancy strictly from database records.
        
        Live Occupancy = SELECT COUNT(*) FROM vehicle_sessions WHERE facility_id=? AND status='INSIDE'
        """
        row = self.query_one(
            """
            SELECT COUNT(*) AS active_count
            FROM vehicle_sessions
            WHERE facility_id = ? AND status = 'INSIDE';
            """,
            (facility_id,),
        )
        return int(row["active_count"]) if row else 0

    def get_available_capacity(self, facility_id: str) -> int:
        """Calculate available parking spaces from authoritative records."""
        total = self.get_facility_total_capacity(facility_id)
        live = self.get_live_occupancy(facility_id)
        return max(0, total - live)

    def reset_db(self) -> None:
        """Drop all tables and recreate clean schema with seed data."""
        cursor = self._conn.cursor()
        cursor.execute("PRAGMA foreign_keys = OFF;")
        tables = [
            "anpr_events",
            "vehicle_sessions",
            "vehicles",
            "parking_cameras",
            "observations",
            "reports",
            "audit_events",
            "members",
            "facilities",
        ]
        for tbl in tables:
            cursor.execute(f"DROP TABLE IF EXISTS {tbl};")
        cursor.execute("PRAGMA foreign_keys = ON;")
        self.init_schema()
        self.seed_defaults()

    def close(self) -> None:
        """Close SQLite database connection."""
        try:
            self._conn.close()
        except Exception:
            pass

    def __enter__(self) -> DatabaseAdapter:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
