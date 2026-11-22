# hackFront India Grand Finale: Persona Use Case Matrix

**Challenge 05 Deliverable: Expand Your Impact**  
**Project**: ParkMyCar | **Submission**: hackFront India (IIIT Delhi, 21–22 Nov 2026)

---

### Persona Use Case Matrix

| User Segment | Their Version of the Problem | Use Cases | Feature That Serves Them | Status in Live Build |
| :--- | :--- | :--- | :--- | :--- |
| **Primary Segment**:<br>**Urban Four-Wheeler Commuter / Shopper** | Circles Connaught Place roundabouts for 30 minutes; gets parked 1.2 km away or towed by traffic police. | 1. Find nearest verified parking to a specific pedestrian destination gate (e.g., Palika Bazaar Gate 1).<br>2. Evaluate walking distance vs driving detour trade-offs before arrival.<br>3. Search hands-free using natural Hindi voice while navigating traffic. | • Photon Nationwide Geocoding Engine<br>• Gate-Level Haversine Distance Polyline<br>• Sarvam AI Indic Speech-to-Text<br>• Turn-by-Turn Navigation Handoff | **Working (Live Build)** |
| **Segment 2**:<br>**Municipal / Private Parking Lot Operator** | Multi-level and basement lots sit at 25% occupancy; revenue leaks through cash pilferage; no way to announce open bays. | 1. Broadcast real-time slot occupancy (Available vs Full) with strict 15-min TTL.<br>2. Update dynamic tariff (e.g. ₹20/hr to ₹30/hr during peak shopping hours).<br>3. Manage lot attendants and review community dispute reports. | • Operator Workspace Dashboard (`/workspace`)<br>• One-Tap Slot Occupancy Toggle<br>• Evidence-Class Tagging (`OPERATOR_REPORTED`)<br>• Real-time Driver Sync | **Working (Live Build)** |
| **Segment 3**:<br>**Quick-Commerce & Delivery Fleet Riders** | 10-minute grocery and parcel delivery agents get ticketed for parking on footpaths and busy service roads. | 1. Locate designated 15-minute express loading/drop-off bays near commercial complexes.<br>2. Check overhead barrier height clearance for delivery vans and pickup trucks. | • Express Loading Bay Category Filter<br>• Height & Vehicle Clearance Badges<br>• Short-Stay Rapid Dispatch Routing | **Planned / In-Progress (Sprint Phase 2)** |

---

### Architectural Support for Remaining Use Cases

The ParkMyCar architecture is specifically designed to accommodate Segment 3 without schema rewrites:
1. **Facility Schema Extensibility**: The `parking_facilities` table in `lib/domain.ts` and `db/schema.ts` already includes `access` types (`PUBLIC`, `CUSTOMERS_ONLY`, `PERMIT`, `COMMERCIAL_LOADING`) and vehicle suitability flags.
2. **Dynamic Category Filtering**: The API route `/v1/facilities` accepts query filters for `maxWalkMeters`, `vehicleType`, and `stayDurationMinutes`.
3. **Synergy with NETC FASTag**: When automated FASTag boom barriers are deployed, webhook events directly update the occupancy table without requiring manual attendant intervention.
