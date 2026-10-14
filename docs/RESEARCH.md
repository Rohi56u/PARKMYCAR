# ParkMyCar: India problem, competitors and data evidence

Research checked: 17 October 2026. This is desk research, not a field survey or a measurement of present-day parking occupancy. Source publication dates are kept separate from the retrieval date.

## Decision

Parking discovery and management are documented problems in multiple Indian urban regions. The evidence below supports an India-focused product, beginning with a bounded, sourced catalogue. It does **not** justify “the same problem everywhere in India”, a ranking of the worst cities, an all-India parking-shortage percentage, or a claim that this app has reduced congestion. No comparable nationwide parking-search-time dataset was verified in this review.

Product positioning hypothesis: **Help a driver choose parking near their destination, understand the evidence behind the choice, and keep a practical alternative before leaving.** Source visibility, evidence age, honest unknowns, explicit access constraints and explainable comparison form a coherent product approach. They are not proof of a new invention or a moat.

## City evidence

| Region | Primary evidence and date | What it supports | Limit |
|---|---|---|---|
| Delhi / NDMC area | [NDMC parking facilities](https://ndmc.gov.in/departments/enforcement_parking_facilities.aspx), undated municipal page | NDMC explicitly acknowledges serious local parking problems and mentions better use of underground Palika parking. | Undated statement, NDMC jurisdiction only. Do not generalize the statement to all NCR or call it a 2026 survey. |
| Mumbai | [BMC parking-system tender](https://www.mcgm.gov.in/irj/go/km/docs/documents/Tenders/ETH/ETH_8000041178_050523.pdf), May 2023, PDF pp.18–19 and 67 | Municipal procurement for parking guidance, availability systems, entry-point guidance and digital payment; the background discusses scarce parking in Maharashtra business districts and street congestion. | A tender demonstrates a recognized need and intended system, not completed deployment, measured benefit or a public API. The scarcity passage is a quoted older legal-policy background. |
| Bengaluru | [BMRCL Metro Parking Policy](https://www.bmrc.co.in/pd/FinalMetroParkingPolicy02-04-2026.pdf), April 2026 file, PDF p.6 | Growing parking demand, particularly near transit stations; disorganized on-street parking reduces arterial-road capacity. The policy records parking at 69 Metro stations, across 80 locations. | Counts are the policy's snapshot, not live inventory. Metro parking is for transit use with applicable access conditions; do not recommend restricted park-and-ride lots as unrestricted visitor parking. |
| Chennai / T. Nagar | [GCC Council Resolution](https://chennaicorporation.gov.in/council/resolution/Council%20Resolution%2028.06.2022.pdf), 28 June 2022, PDF p.280 | The council documented excessive on-street demand on Theyagaraya Road while the nearby multilevel facility was underused. It recorded 222 equivalent-car-space capacity and 513 two-wheelers at the MLP. | This is a historical location-specific case, not Chennai-wide shortage or current tariff evidence. Do not put its 2022 prices in current facility cards. |
| Hyderabad | [Telangana state press release](https://www.telangana.gov.in/news/press-releases/2024/01/government-pays-special-focus-on-hyderabads-traffic/), 31 January 2024 | State traffic review explicitly addressed parking and requested a special parking policy and multilevel centres. | A policy instruction, not proof that facilities were built or a live feed became available. |
| Pune | [Pune International Centre working paper page](https://puneinternationalcentre.org/publications/towards-a-new-parking-policy-for-pune/), December 2025 | The original authors identify pricing, enforcement and outdated zoning problems in Pune's parking management. | Primary research publication, **not** a municipal/government finding or a quantified citywide vacancy survey. |

Short verified excerpts, kept under 25 quoted words per source:

- NDMC: “parking problems in its area which have taken serious shape and require urgent attention.”
- BMRCL: “A growing trend in parking demand is seen in the entire city, especially near the transit stations.”
- GCC: “there is traffic congestion and excessive demand for parking on-street, while the MLP facility remains under-utilized.”
- Telangana: “The CM ordered the officials to prepare a special parking policy with all modalities.”

### National context, without inflated statistics

The [Ministry of Urban Development's parking-policy advisory](https://www.mohua.gov.in/upload/uploadfiles/files/ut_parking.pdf) is dated **28 March 2007**. It addresses all States/UTs, observes that arterial-road parking occupies mobility space, and calls for city/town parking policies. This provides longstanding national policy context, **not current numerical proof** of the number of affected cities or drivers.

Useful website copy: “Parking decisions matter across India's cities. ParkMyCar brings nearby options and their source details into one clear comparison.” Coverage must separately state which cities and records the actual catalogue contains.

## Competitors: verified official product descriptions

| Product | What its own website advertises | Product implication |
|---|---|---|
| [Park+](https://parkplus.io/parking) | Destination/location search, map view, advance reservations, daily/monthly booking and cashless payment. Its parking page explicitly mentions Delhi NCR, Bengaluru and Mumbai, and links additional city pages. | Finding and booking parking is already established. Do not claim competitors only support “near me”, or that destination-first search alone is unique. A city landing page is not a verified count of operational lots. |
| [Get My Parking](https://www.getmyparking.com/product.php) | White-labelled mobile/web parking apps, reservation/payment, operator portals, hardware retrofit, real-time occupancy tracking, permit management and integrations. | IoT, operator dashboards, APIs and occupancy are not novel features by themselves. Treat this as a major operations-platform competitor; do not assert it lacks consumer capability. |
| [ParkQwik](https://parkqwik.com/) | Official-site search result describes finding, reserving and paying for parking and advance booking. The page is client-rendered and yielded no text on direct retrieval. | Core booking/discovery overlap is supported. Detailed feature absence, current operational coverage and current inventory were not established. |

These are vendor statements, checked 17 October 2026, not independently completed bookings or performance benchmarks. No competitor price/coverage numbers are used.

### Defensible differentiator to build and test

1. **Evidence attached to the decision:** every listing exposes provenance and a checked/snapshot date. Static catalogue facts remain distinct from timestamped operator, community or sensor observations.
2. **Explainable trade-offs:** compare destination proximity, known price/access/features, with missing prices excluded from “cheapest” calculations. Show the reason each option is ranked.
3. **A primary and backup choice:** save two options and retain navigation hand-offs; do not imply a hold or reservation exists without contracted inventory.
4. **A correction loop:** a driver can flag wrong access/location information into a moderation queue; unreviewed reports cannot silently become verified facts.
5. **Privacy-light search:** no account for discovery; optional location only on deliberate user request; avoid logging precise travel coordinates.

All are product hypotheses. The advantage must be evaluated through real task completion, decision time, wrong-entrance rate and successful arrival reports. Do not invent interview findings, percentage time saved, carbon reduction, calibrated confidence scores or PMF evidence.

## Real public data options

| Source | Useful information | Integration boundary |
|---|---|---|
| [OpenStreetMap](https://www.openstreetmap.org/copyright), [parking tagging documentation](https://wiki.openstreetmap.org/wiki/Tag:amenity%3Dparking) | Real mapped parking points/polygons, IDs and available tags; coordinates can support spatial search. | ODbL with attribution and share-alike conditions for derived data. Preserve OSM IDs/version/snapshot provenance. Incomplete tags are unknowns. `amenity=parking` can include private/customer-only facilities; enforce access filtering. An area centroid is not a surveyed vehicle entrance. |
| [NDMC parking-sites directory](https://ndmc.gov.in/departments/pms_sites.aspx) | Official name/location and parking type for 141 numbered rows. Palika is row 74. | No coordinates, vacancy API or current prices on this page. Verify individual matching carefully. No explicit open-data reuse licence was identified; link and corroborate selected factual listings rather than assume unrestricted database redistribution. |
| [Hyderabad Traffic Police parking zones](https://echallan.tspolice.gov.in/htp/parking.html) | Named parking areas grouped by traffic police zone, maps links and some vehicle-type restrictions. | Includes explicit no-parking areas and lorry/bus-only areas; not every row is car parking. Links are not live occupancy. Do not bulk scrape Google Maps content to populate an OSM-derived database. No open reuse licence confirmed. |
| [BMC parking map](https://portal.mcgm.gov.in/irj/portal/anonymous/BMC-on-Map-Facilities-ParkingLots?guest_user=english), [GIS layers metadata](https://prsrvgisapp.mcgm.gov.in/server/rest/services/mcgm/MCGMGIS_Departments_Master_All_Layers/MapServer/layers) | Official discovery UI; indexed GIS metadata names Public Parking Lots layer 329 and Parking Spot. | Direct GIS layer could not be retrieved in this research, so neither response schema, coordinates, completeness nor licence is verified. Keep as a future source, not a working shipped API claim. |
| [PCMC general information](https://www.pcmcindia.gov.in/general-info.php) | Directory links include on-/off-street parking and no-parking lists. | Pune metropolitan area, not identical to Pune Municipal Corporation. Individual linked files/coordinates/reuse terms were not verified. |

No unrestricted public India-wide **live occupancy** feed was verified. An integration interface and authenticated ingest can be built, but real sensor status requires an actual connected source with known count semantics, source identity and freshness.

## Provider policies checked for implementation

- [OSM copyright/licence](https://www.openstreetmap.org/copyright): credit OpenStreetMap contributors and link the ODbL. Data and server-service permissions are different. Do not copy Google Maps data into OSM-derived data without permission.
- [OSM standard tile policy](https://operations.osmfoundation.org/policies/tiles/): ordinary browser viewing is permitted under attribution, Referer and caching requirements. No bulk download, offline tile bundles, prefetch scans or claims of service SLA. Make provider configurable. The shipped ZIP may include permitted OSM **data**, not a scraped standard-tile archive.
- [Public Nominatim policy](https://operations.osmfoundation.org/policies/nominatim/): at most one request/second for the whole application, identifiable traffic, cache, no client autocomplete or systematic POI enumeration. Current policy explicitly restricts generic inclusion by no-code/low-code/vibe-coding platforms and requires an informed, responsible developer decision. Do not automatically wire public Nominatim into a generic live-search box. Prefer a local curated destination index plus a configurable licensed/self-hosted geocoder adapter.

## Research caveats worth preserving

- PCMC's indexed 2026 Climate Action Plan contains an internal inconsistency: prose says 8 on-street locations, table says 7; four-wheeler subtotals sum to 845 while total says 846. Do **not** use those counts in marketing. Source: https://www.pcmcindia.gov.in/pdf/Climate%20Action%20Plan%202026.pdf (direct fetch timed out; indexed passage only).
- Transport congestion rankings are not parking-shortage rankings. Do not substitute one for the other.
- Historical tariff tables can explain a study; they should not become current user prices without fresh operator evidence.
- A government directory establishes listing provenance, not a vacancy guarantee, safety certification or legal permission for every user at every time.

