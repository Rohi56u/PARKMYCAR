# Data provenance and operating policy

## Shipped catalogue

The initial five parking polygons are OSM ways: Palika `1393736859`, west `1234918799`, north `1533055892`, east `1306321428`, southwest `1316315034`. IDs, URLs, geometry/coordinate snapshot dates and supported fields are preserved in `data/source-catalog.json`. `data/source-review.json` records the 17 October 2026 recheck of current type/access tags, OSM version and source update timestamp. No OSM contributor identity is included.

`public/data/connaught-place.geojson` is an OSM-derived vector snapshot from 10 October 2026, not a tile archive. The four destination coordinates have that earlier snapshot date. A later tag review does not imply every coordinate, entrance or street was re-surveyed.

Palika is additionally corroborated by [NDMC's directory](https://www.ndmc.gov.in/departments/pms_sites.aspx), row 74. The other four names are descriptive area labels. All current parking coordinates are area centroids. No field inspection of vehicular entrances occurred.

| Attribute | Initial treatment |
|---|---|
| OSM `amenity=parking`, parking type and access tags | Sourced map facts, subject to mapping error and later change |
| Rates, hours, vehicle restrictions, accessibility, EV | Unknown until evidence is entered; never inferred from an empty tag |
| Vacancy | Unknown until a current operator or approved community observation exists |
| Walk/drive route | External Google Maps hand-off; no in-app route calculation |
| Coverage | Connaught Place bounding area only; five initial facilities |

## New records and corrections

The owner can add sourced locations within the configured area. The import contract requires source name, HTTPS URL and declared ODbL or first-party permission. It rejects duplicates within 15 metres and records the addition in the audit table. This declaration is an operational review, not an automatic legal licence verification. Current centroid-based imports do not assert a surveyed entrance. Additional tariffs/hours require a sourced edit.

Operators are assigned by the owner after real association is checked outside the application. They can propose listing changes; the owner publishes them. Reviewers/admins can review driver reports. `CLOSED` and `DETAILS_WRONG` reports remain workflow items for correction and do not silently mutate published hours/access. Approved `FULL` or `FOUND_SPACE` can become short-lived, explicitly community-labelled observations.

Source records are references to factual support. Avoid attaching a source to fields it does not establish. Update only fields actually checked; retain older relevant sources, and deactivate incorrect locations. A date means a reference was checked, not that the facility was physically inspected.

## Licensing and provider boundaries

- OSM-derived catalogue and map: [Open Database Licence 1.0](https://opendatacommons.org/licenses/odbl/1-0/) and [OSM attribution](https://www.openstreetmap.org/copyright). The app credits OpenStreetMap contributors and provides the source catalogue download. Preserve attribution and applicable share-alike requirements when redistributing.
- OSM standard tiles: normal interactive viewing only under the [tile usage policy](https://operations.osmfoundation.org/policies/tiles/). No offline download/prefetch/tile redistribution is shipped. There is no service SLA.
- NDMC: an official factual corroboration link. No unrestricted municipal bulk-data licence was established; the application does not redistribute the municipal directory wholesale.
- No public Nominatim autocomplete, Google Maps scraping, public routing-demo dependency, or hidden paid API is used.

## Retention

Trip origins/destinations are not stored as user-linked history. Explicit place-search text is sent to Photon. Public returned place records are cached for up to seven days under hashed query/provider keys, without caller association; raw query text is not persisted. Saved choices contain at most three facility IDs in browser storage. Clear them using **Clear shortlist**. Reports contain the facility/category/time and a daily salted caller hash for deduplication; raw IP is not stored. Operator identity and changed field names are retained for operational audit.

On the first request of a new day, maintenance removes expired geocoding cache entries and rate buckets, reports older than 30 days, observations expired over 30 days ago, audit events older than 180 days and resolved listing changes older than 90 days. Pending listing changes remain for review. This is request-driven maintenance, not a separate scheduled job. Hosting/provider logs are governed separately by their platforms.
