# Release verification

Release: ParkMyCar 1.1.0, India search upgrade, October 2026. This file records checks actually performed, not a promise of zero bugs.

| Check | Result |
|---|---|
| TypeScript | `pnpm typecheck` passed |
| Application ESLint | `pnpm lint` passed |
| Automated suite | 82 tests passed; Node test runner with real SQLite migrations |
| Production compilation | Vinext/Worker/client build passed |
| Local D1 migration | Versioned migration applied successfully with Wrangler |
| Real parking source review | All five OSM way type/access records retrieved and reviewed on 17 Oct 2026 |
| Browser/mobile visual and interaction QA | Not run: required browser-control capability unavailable |
| Field visit / live operator feed | Not performed / not supplied |
| GitHub Actions | Workflow included; no external Actions run claimed |
| 1.1 deployment | Pending runs-on.dev account/domain configuration; the upgrade has not been published |

The automated suite covers Haversine invariants, source/expiry/conflict semantics, configurable TTL, India-time hours/overnight intervals, tariff units, unknown attributes, access/vehicle/features, deterministic ranking, navigation links, strict input/body limits, source seed/migrations, public API, operator isolation, escalation rejection, role revocation, owner claim, origin checks, report rate/dedup/moderation, stale edit conflicts, source-backed onboarding, public detail visibility, retention and sanitized failures. Provider failure is simulated to establish that first-party search still works.

Database integration tests execute the shipped migration in SQLite with foreign keys enabled. They do not emulate every Cloudflare network/runtime behavior. A local D1 migration adds a separate schema-compatibility check. No synthetic fixture is published as a real parking record.

The upgrade adds 24 geocoding/directions tests covering Indian country filtering, coordinate order, malformed/foreign records, OSM identity validation, deduplication, Unicode, source URLs, configurable HTTPS provider, coordinate input, navigation parameters, escaped external fallback, shared cache/throttle, expiry, upstream failures/429/timeout/size, API validation and cache pruning. Browser interaction checks remain unperformed; these tests do not replace them.

## Reproduce

```sh
pnpm install --frozen-lockfile
pnpm typecheck
pnpm lint
pnpm test
pnpm build
```

## Manual release checks still needed

Use a real mobile/desktop browser to check keyboard focus, map/list selection, map pin placement, dialog close/escape, optional geolocation denial, street-map network failure, shortlist persistence, Google Maps hand-off and signed-in owner/operator workflows. Verify the layout at narrow/mobile widths and with large text. Run an accessibility audit and fix observed issues. Conduct a field review of parking entrances/access before advertising verified entrance directions.

Before expanding coverage: collect operator permission and current source facts, configure licensed routing/geocoding if needed, baseline real latency and search outcomes, review data retention/backups, and calibrate observation TTL against arrival outcomes. No p95, load capacity, conversion rate, parking success rate or time-saving percentage has been measured here.
