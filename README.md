# ParkMyCar

India-wide place search and directions, with a sourced parking directory beginning in Connaught Place, New Delhi. A working React/TypeScript application with a SQL-backed API, source-aware facility details, a three-place shortlist, reporting, operator permissions and an administrative review workflow.

## India search upgrade · 1.1.0

Type a city, village, locality, road, landmark or address into **Where are you headed?**, then press **Enter / Search India**. Choose the correct match using its district/state context. The map moves to that place. Use **Directions in Google Maps** or **Walk**, with an optional searched start point or one-time device location.

Search uses real OpenStreetMap records through Photon with `countrycode=IN`. It is not limited to the four original destination suggestions. A matching record can be selected anywhere in India's mapped coverage, including island locations. No provider guarantees every small village, house or spelling; add district/state context, choose a map pin, or use the explicit Google Maps fallback when a record is missing. **Place-search coverage is separate from parking-catalogue coverage.** The existing five parking areas remain sourced pilot records; no nationwide parking inventory or live vacancy has been invented.

See [upgrade details and provider policy](docs/UPGRADE_1_1.md).

### Requested deployment domain

This release is prepared for a user-owned `*.runs-on.dev` hostname. Domain claim, DNS validation and publication are pending authenticated domain-account access. The 1.1 upgrade has not been published to the previous default hostname. `runs-on.dev` supplies the domain; ParkMyCar also needs its Worker backend, D1 database and verified authentication gateway. See [domain setup and release status](docs/RUNS_ON_DEV.md).

## Start here

1. Install **Node.js 24 LTS** and **pnpm 11.25.0**.
2. Extract this folder and open a terminal inside it.
3. Run:

```sh
pnpm install --frozen-lockfile
pnpm local:setup
pnpm dev
```

Open **http://localhost:5173**. The setup command creates local development configuration and applies the versioned database migrations. No paid API key is required for the included directory, low-volume Photon place search, normal OSM street-map viewing or Google Maps directions links. Internet access is required for those external services.

Local sign-in: open **Operator workspace → Sign in with ChatGPT**. The starter simulates a local identity on loopback development requests. Choose **Set up my workspace** once. This local identity is not a production authentication service. Never expose the development server publicly.

The hosted version uses real, gateway-managed ChatGPT sign-in. Open its operator workspace and choose **Set up my workspace** while the Site is owner-private. You then become its administrator. Additional users receive access through both the Site sharing controls and the application's Team permissions. **The shared Site is currently private to its owner.**

## What works

- India-filtered place/address search for destination and origin, contextual match selection, four local quick picks, manual coordinates and map-pin input.
- Optional one-time location or manual origin for a navigation hand-off.
- Destination-radius search, car/two-wheeler eligibility, parking-type/feature filters, planned arrival and duration.
- Deterministic distance ranking; price comparison only where a sourced compatible tariff exists.
- India street map, place-aware zoom, all-India overview, selectable markers, local CP vector fallback, accessible list, mobile map/list views and loading/error/empty states.
- Facility details with sources, dates, access, recorded hours/rates, vehicle fit, and navigation links.
- Save up to three parking IDs on this device and compare alternatives.
- Driver reports persisted to a moderation queue, with deduplication and rate limits.
- Operator updates scoped to assigned facilities; listing edits require admin review.
- Administrator listing edits, source-backed onboarding within the pilot area, team access, moderation and audit history.
- Expiring, source-labelled observations; conflicting current sources produce an unknown state.
- Nine relational database tables, foreign keys/checks/indexes, versioned migrations and optimistic concurrency checks.

## What the data actually establishes

The parking seed contains **five OSM parking areas and four OSM quick-pick destinations**. Other searched places are retrieved from Photon; they are not automatically parking facilities. All five parking access/type records were rechecked on 17 October 2026. Map geometry and destination coordinates are the earlier 10 October 2026 snapshot. Palika Parking is also corroborated by NDMC's municipal directory.

The data is real, but it is **not an on-site inspection**. Four names are descriptive area labels. Parking coordinates are area centroids, not surveyed entrance coordinates. No current tariffs, opening hours, vehicle restrictions or occupancy feed were supplied, so those fields start unknown. Empty values are never rendered as free, open or vacant.

Distances in the app are **straight-line proximity**. Driving and walking directions open Google Maps for the actual selected coordinates. The app does not calculate in-app road-route times, detours or guaranteed walking distance. A licensed routing-provider integration remains a separate step; the implementation does not silently call a public routing demo endpoint.

The India research covers evidence from Delhi, Bengaluru, Mumbai, Chennai, Hyderabad and Pune. It does not turn the five-location pilot into nationwide coverage. Read [research](docs/RESEARCH.md), [source policy](docs/DATA.md) and [requirements traceability](docs/TRACEABILITY.md).

## Stack and architecture

- React 19 + TypeScript, Vinext server routes, Leaflet, Lucide icons.
- Cloudflare Worker runtime and D1 SQL database, with Drizzle schema/migration generation.
- A TypeScript modular service with validated contracts, a repository boundary and pure domain functions.
- Node built-in test runner and real SQLite migration/API integration tests.
- pnpm lockfile; GitHub Actions CI; a versioned private Sites deployment.

The input documents propose PostgreSQL/PostGIS. This deployment deliberately uses D1 for the bounded pilot because Sites provisions it directly. Spatial prefiltering uses indexed latitude/longitude bounds followed by Haversine distance. This is **not a PostGIS implementation**. The catalogue is capped at 200 records. See [ADR and migration strategy](docs/ARCHITECTURE.md).

## Commands

```sh
pnpm typecheck       # TypeScript checks
pnpm lint            # Application lint checks
pnpm test            # Domain, migration, API and authorization checks
pnpm build           # Production Worker and client bundle
pnpm local:setup     # Local configuration and idempotent migration application
pnpm db:generate     # Generate a new reviewed SQL migration after schema changes
```

The CI workflow runs the same checks and build. It is included for a future GitHub repository; no GitHub workflow run is claimed. Hosted publication is handled through the Sites source/version/deployment workflow, not an invented GitHub deployment credential.

## Source map

| Location | Responsibility |
|---|---|
| `components/ParkApp.tsx`, `ParkingMap.tsx` | Driver flow, accessible dialogs, map/list interaction |
| `components/Workspace.tsx` | Owner/operator/reviewer tools |
| `lib/domain.ts` | Geography, eligibility, hours, tariffs, evidence and ranking |
| `components/PlaceSearch.tsx`, `lib/geocoding.ts`, `lib/places.ts` | India place lookup, request cancellation, normalized provider data, cache and directions helpers |
| `lib/contracts.ts` | Strict runtime request validation and request bounds |
| `lib/store.ts` | SQL repository, seed, atomic limits and retention |
| `lib/service.ts` | HTTP use cases, authorization, review and auditing |
| `app/api/v1/[...path]/route.ts` | Worker/D1/auth integration |
| `db/schema.ts`, `drizzle/` | Schema and migration history |
| `data/`, `public/data/` | Versioned source records and OSM-derived map data |
| `tests/` | Synthetic test fixtures, never published as real parking records |
| `docs/` | Architecture, API, data, security, release checks and research |

## Runtime configuration

See `.env.example`. The hosted application expects D1 binding `DB`. `PARKMYCAR_PHOTON_BASE_URL` may select an operator-managed HTTPS Photon-compatible service; the low-volume default is `https://photon.komoot.io`. On Sites, set `PARKMYCAR_TRUSTED_SITES_GATEWAY=1`, a secret random `RATE_LIMIT_SALT`, and initially `PARKMYCAR_ALLOW_BOOTSTRAP=1`. The one-time owner claim is protected by private Site access and the unique owner record; turn the bootstrap flag off after setup and before broad sharing. The owner role cannot be reassigned through Team UI.

`PARKMYCAR_TRUSTED_SITES_GATEWAY` must stay disabled behind an untrusted or absent gateway. The app must not trust internet-supplied identity headers on an unrelated host. For a different hosting provider, implement and test its verified identity adapter before enabling operator/admin access.

## Validation and limits

See [VERIFICATION.md](docs/VERIFICATION.md) for the actual release checks. Browser visual and interaction QA could not be run in this environment because the required browser-control capability was unavailable. No field audit, operator partnership, user study, paid-provider account, live occupancy, booking, payment or prediction is claimed.

The source includes a web manifest but does not promise offline dynamic data or cache third-party tiles. The bundled local CP map is OSM vector data. Street-map tiles are requested for normal interactive viewing. Public geocoding results are cached for up to seven days using hashed keys, without caller association. Raw place query text is not stored in the application database.

## Licensing

Application code: MIT (see `LICENSE`). OSM-derived datasets/map geometry: ODbL 1.0 with required attribution and share-alike terms. Rubik fonts: SIL Open Font License. Do not treat a municipal reference link as an unrestricted bulk-data licence. See `THIRD_PARTY_NOTICES.md` and `docs/DATA.md`.
