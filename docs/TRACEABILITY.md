# Requirements traceability

Inputs reviewed: the supplied PRD, technical design, database schema, AI context/engineering guardrails and coding-agent skills catalogue. The public brand is **ParkMyCar**. Internal PRD identifiers below are for engineering traceability only and are not displayed as driver-facing copy.

| PRD requirement | Shipped behavior | Boundary or remaining work |
|---|---|---|
| FR-01 Origin/destination | India-filtered Photon place/address search for both fields, contextual selection, manual coordinates, map pin and one-time GPS | Depends on indexed OSM records; incomplete/misspelled addresses may need a map pin |
| FR-02 Filters | Arrival/duration, car/two-wheeler, radius, type, known EV/accessibility, incomplete/customer controls | Radius is straight-line, not maximum walk route; initial vehicle/features remain unknown |
| FR-03 Discovery | SQL bbox + exact distance, access/vehicle/hours/feature checks, empty/coverage state | Five initial records, 200-record guard |
| FR-04 Route-aware result | Correct driving and walking navigation hand-offs | In-app route distance, detour, ETA and route-aware ranking are **not implemented**; requires licensed provider and entrances |
| FR-05 Evidence | Static/operator/community separation, timestamp/source/expiry, conflict handling | No sensor, model or booking evidence; UI uses “Mapped parking” per requested wording |
| FR-06 Details | Sources/dates, access, type, sourced hours/rate/vehicle/features, entry note and report action | Initial centroids, not verified entrances; initial unknown fields clearly retained |
| FR-07 Operator | Authenticated facility-scoped edits/status, review queue, audit, configurable expiry | Requires actual operator onboarding; no partners are invented |
| FR-08 Community | Persistent reports, validation, dedup/rate controls, moderator review | No reputation engine or assumption that a report is fact |
| FR-09 Admin | Add/edit/deactivate, assign roles, review reports/edits, inspect audit | Coverage is reviewed source configuration, not an unrestricted UI polygon editor |
| FR-10 Navigation | Google Maps drive to parking / walk to destination | No reservation or held bay |
| FR-11 Localization | Domain/API independent of UI language | Initial UI is English; Hindi translation/catalogue not delivered |
| FR-12 Booking/payment | Deliberately absent per PRD non-goals | Contracted inventory/fulfilment/payment work required first |

Other delivered work: India/competitor research, three-choice comparison, map/list mobile layouts, loading and failure states, versioned database migration, automated authorization/integrity tests, private deployment workflow, GitHub CI configuration, local setup instructions and source ZIP.

Technical deviations: D1 replaces proposed PostgreSQL/PostGIS for this deployable cluster. Exact road routing is handed off to Google Maps. National geocoding uses live Photon results; no invented place or route estimates are used. No numerical confidence, search-time saving, user study, ML accuracy, parking safety or all-India inventory claim is made. Read `ARCHITECTURE.md` for the decisions.

This is a functioning bounded implementation, not evidence that every PRD feature or field-validation gate has been completed. Field/operator verification, real browser QA, Hindi UI, route provider integration and scale tests remain before a broad public launch.
