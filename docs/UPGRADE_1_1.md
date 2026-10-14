# ParkMyCar 1.1 — India place search and directions

## Use the upgrade

1. Type a destination: a city, village, locality, street, landmark or address. For small places, include a district/state, for example **Nawada Fatehpur Haryana**.
2. Press Enter or Search India. Choose the intended result using its area/state context. Search is submitted explicitly; typing does not send a request for each character.
3. The selected place appears on the street map. The globe control shows the India overview; zoom or choose a point manually when useful.
4. Optionally search a start point or use the one-time location button. Confirm typed fields before navigating.
5. **Directions in Google Maps** opens driving directions to that exact selected point. **Walk** uses walking mode. If no start point is set, Google Maps determines an available start or asks for one.

The same screen continues to show nearby parking where the curated catalogue contains records. A valid destination remains usable for directions even when the local parking result list is empty. General place-search results are not inserted into the parking catalogue.

## Coverage and data

Photon searches OSM-derived records with `countrycode=IN`; the server also rejects returned records with another/missing country code. The broad coordinate sanity bounds include India's island groups. Results retain names, contextual address parts, coordinates, feature kind and original OSM record links. Province/city/village points may represent a locality centre rather than an entrance. Results require user selection when ambiguous.

This enables nationwide mapped-place search, not exhaustive knowledge of every Indian village, house, nickname or spelling. Missing matches have a refinement/map-pin path and an explicitly labelled external Google Maps search. Unicode query input is supported; returned name language is `en` because the public server rejected `lang=hi` in a live check. Hindi relevance is data-dependent, not a translation guarantee.

## Provider decision and operating limits

Primary references: [Photon project policy](https://github.com/komoot/photon), [Photon API](https://github.com/komoot/photon/blob/master/docs/api-v1.md), [public service](https://photon.komoot.io/), [OSM tile policy](https://operations.osmfoundation.org/policies/tiles/), [Google Maps URLs](https://developers.google.com/maps/documentation/urls/get-started).

Photon permits reasonable project use without a numerical quota or availability guarantee. This owner-private version uses explicit lookups, an 8-second timeout, bounded results, a shared SQL spacing gate, per-caller/day limits and a shared expiring cache. These are our conservative controls, not an approved service allocation. Do not advertise unlimited service or an SLA. Before a large public rollout, configure a contracted or private Photon-compatible HTTPS provider using `PARKMYCAR_PHOTON_BASE_URL` and review its operating limits.

OpenStreetMap standard tiles load for the current interactive view. There is no tile scraping, regional prefetch or offline tile bundle. Google Maps URL hand-offs require no API key, but do not return route geometry or ETA to this app. OSRM is a routing engine, not a substitute for place-name geocoding, and is not needed for this navigation hand-off.

## Engineering changes

- `components/PlaceSearch.tsx`: destination/origin reuse, keyboard selection, cancellation/stale-response protection, contextual errors and explicit fallback.
- `lib/geocoding.ts`: country/coordinate/source validation, duplicate rejection, bounded provider response, cache and concurrency-safe provider spacing.
- `lib/places.ts`: shared place contract, Unicode normalization, explicit coordinates and map zoom/navigation helpers.
- `POST /api/v1/places/search`: validated same-origin service with no driver-account requirement inside the Site access boundary.
- `geocode_cache`: additive migration `0001_panoramic_edwin_jarvis.sql`; previous migration/history unchanged. Public cached results are not associated with a caller.
- India map zoom/pan, actual selected destination label and always-visible navigation actions. Edited unconfirmed input cannot silently send the user to the earlier selected destination.

## Verification

The upgrade's unit/SQL/API suite totals 82 tests. Existing operator/admin/report/search tests remain in place. Live provider checks during research returned Manesar (municipality OSM relation 3631133) and Nawada Fatehpur (relation 3738360). A Hindi Mumbai query returned real Mumbai-area places but not necessarily the city first, reinforcing the contextual-selection requirement. No fabricated record is used as a live result. Final deployment HTTP checks are reported with the delivered app; browser visual QA remains a separate outstanding check.
