# HTTP API

Base: `/api/v1`. JSON requests, JSON responses, `Cache-Control: no-store`. Invalid JSON/content type/schema/size produces a structured error. Body cap: 8 KiB. Mutation requests require a same-origin `Origin` header; identity comes from the trusted gateway, never a caller-provided role.

| Method/path | Access | Purpose |
|---|---|---|
| GET `/health` | Site access | Database/seed reachability and catalogue version |
| GET `/bootstrap` | Site access | Public catalogue, destinations, coverage and server time |
| POST `/places/search` | Site access, same origin | India place lookup; JSON `{ "query": "Nawada Fatehpur Haryana" }` |
| POST `/search` | Site access | Filter/rank parking, at most 30 results |
| GET `/facilities/:id` | Site access | Public facility details and current evidence |
| POST `/reports` | Site access | Queue a recent driver report |
| GET `/workspace` | Optional identity | Identity/member/owner-setup state; scoped records if authorized |
| POST `/workspace/claim` | Signed in, private bootstrap | One-time owner creation |
| POST `/workspace/import` | Admin | Add a source-backed facility inside the pilot |
| POST `/workspace/members` | Admin | Assign operator/reviewer and facilities |
| DELETE `/workspace/members/:id` | Admin | Revoke non-owner role |
| PATCH `/workspace/facilities/:id` | Admin/assigned operator | Publish or propose sourced edits with base version |
| POST `/workspace/facilities/:id/status` | Assigned operator | Timestamped expiring observation |
| POST `/workspace/reports/:id/moderate` | Admin/reviewer | Approve/reject/resolve report |
| POST `/workspace/changes/:id/moderate` | Admin | Approve/reject proposed listing edit |

“Site access” is the private hosting access boundary in this delivery. The discovery service itself requires no driver account and can run anonymously if the owner later changes Site sharing. That does not remove workspace authorization.

## Search example

```json
{
  "destination": {"lat":28.6328,"lng":77.2183},
  "radius":1000,
  "arrivalAt":"2026-10-18T17:00:00+05:30",
  "durationMinutes":120,
  "vehicle":"CAR",
  "requirements":[],
  "type":"all",
  "sort":"distance",
  "includeUnknown":true,
  "includeCustomer":false
}
```

Example arrival is illustrative; submit the user's actual requested time. Responses contain `results`, `coverage`, `serverTime`, `distanceBasis: "straight_line"` and `catalogueVersion`. Each result includes a facility, distance, nullable total cost, reasons, hours state and a separate evidence object. `null` cost is not zero.

Canonical request types and constraints are in `lib/contracts.ts`; response/domain types are in `lib/domain.ts`. Unknown request keys are rejected. India coordinate bounds validate plausibility, not coverage. Out-of-coverage search returns a useful empty result rather than fictional records.

## Error contract

```json
{"error":{"code":"STALE_VERSION","message":"This listing changed. Refresh before saving.","requestId":"request-specific-id"}}
```

Typical codes: `INVALID_INPUT`, `CONTENT_TYPE`, `TOO_LARGE`, `SIGN_IN`, `FORBIDDEN`, `NOT_FOUND`, `DUPLICATE`, `RATE_LIMIT`, `STALE_VERSION`, `EXPIRED`, `ALREADY_REVIEWED`. Internal errors expose no SQL, secret or precise trip coordinate.

Limits: search 90/minute per daily caller hash; reports 3/10 minutes and one per facility/caller/15-minute bucket; protected workspace writes 30/minute/member. Driver reports accept observations from the last 30 minutes; approving status requires it to remain within the configured observation lifetime.

## Place lookup response

`places` contains at most eight contextual matches: stable OSM-derived ID, name, subtitle, latitude/longitude, kind and source URL. Also returns `provider`, `cached` and `retrievedAt`. Select a match before using it in parking search or directions. A geocoding response is not a parking/entrance/vacancy claim.

Input: 2–160 characters; Unicode accepted, control characters rejected. Caller cap: 20 requests/minute, including cache hits. Uncached provider requests have a shared minimum 1.2-second spacing and 1,000/day application ceiling. These are conservative application limits, not Photon service guarantees. No automatic retry flood or provider rotation. Upstream timeout: 8 seconds, bounded response: 512 KiB. Empty results cached five minutes; successful public results seven days. Provider failures are not cached as successful empty results.
