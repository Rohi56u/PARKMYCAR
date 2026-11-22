# hackFront India Grand Finale — STEP ZERO: PRODUCT AUDIT & FINALE BUILD PLAN
**Team Name / Project**: ParkMyCar  
**Team Lead / Submitter**: Rohit Choudhary  
**Venue & Date**: IIIT Delhi · 21 November 2026, 4:00 PM IST  
**Live URL**: [https://parkmycarr.netlify.app](https://parkmycarr.netlify.app) | **GitHub**: [Rohi56u/PARKMYCAR](https://github.com/Rohi56u/PARKMYCAR)

---

### 1. Where You Are (Current Prototype Status: Audit)
* **What Works Today (Live Build)**:
  * **Nationwide Geocoding & Pan**: Resolves Indian locations (cities, landmarks, commercial hubs) via Komoot Photon with country-code biasing (`in`) and auto-pans the interactive Leaflet map.
  * **Gate-Level Destination Model**: Models specific pedestrian access gates (e.g., Palika Bazaar Gate 1, Connaught Place Blocks) with exact walking distance vs. vehicle detour trade-offs.
  * **Dynamic Facility Engine**: Automatically discovers and generates parking facilities around any searched Indian coordinate when out-of-catalogue.
  * **Zero False Guarantees Principle**: Clearly distinguishes between verified physical entry gates and estimated open parking records with transparent evidence attribution.
  * **Operator Workspace Preview**: Basic facility inspection and manual slot verification dashboard.
* **What is Mocked / Hardcoded**:
  * Connaught Place facility records are static seed data in `catalogue.ts`.
  * Dynamic facility generation simulates capacity, pricing, and operating hours based on spatial offsets rather than live sensor/municipal APIs.
  * Database operates via an in-memory D1 emulation wrapper (`lib/db.ts`) rather than a persistent distributed database.
* **What is Missing**:
  * Real-time user authentication and personalized parking shortlists.
  * Native Indian-language voice search for hands-free driver safety.
  * Real persistent data store for community slot feedback and operator updates.

---

### 2. Where You Will Be (By 12 PM on 22 November: 22-Hour Target)
By 12:00 PM tomorrow, ParkMyCar will reach **65–70% production maturity** with:
1. **Persistent Cloud Database**: Migration from in-memory D1 shim to persistent backend storage (Supabase / Turso / Cloudflare D1) for real operator capacity updates and verified driver reviews.
2. **Sarvam AI Indic Voice Search Integration**: Full hands-free voice interface in Hindi and English (`Sarvam Speech-to-Text + Indic NER`) allowing drivers to speak destinations while navigating (e.g., *"Bhai Palika Bazaar Gate 2 ke paas car parking dikhao"*).
3. **Multi-Segment Dual Workflow**:
   * *Driver Journey (End-to-End)*: Voice/text search → Gate-level facility cards → Detour vs. walking trade-off → One-tap navigation to exact vehicular entry barrier.
   * *Parking Operator / Valet Journey (Live)*: Operator login → Dynamic slot availability update → Rate adjustment → Immediate driver-side sync.
4. **ArgosX Security Remediation**: Zero critical/high vulnerabilities across API routes, CORS headers, and input sanitization, backed by two scan audit reports.

---

### 3. User Segments (Primary + 2 Additional)
* **Primary Segment (Urban Car Commuter / Shopper)**: Daily drivers visiting congested commercial hubs (CP, Cyber Hub, MG Road) who lose 25–40 minutes searching for parking and risk towing or predatory overcharging.
* **Segment 2 (Local Parking Operator / Attendant)**: Municipal lot contractors and private basement owners needing digital visibility, occupancy management, and fair price communication without expensive hardware.
* **Segment 3 (Commercial Fleet / Quick-Commerce Drivers)**: Cab and delivery drivers requiring rapid 15–30 minute short-stay drop-off bays and clear height/gate clearance info.

---

### 4. Partner Tech Choice: Sarvam AI (Indian Language Speech & Voice Discovery)
* **Partner Selected**: **Sarvam AI** (with optional Neo4j location graph).
* **Product Need It Solves**: In Indian traffic, drivers **cannot safely type** English street names on mobile screens while navigating chaotic roundabouts and congested intersections. Sarvam AI's Indic Speech-to-Text (`Saaras`) and vernacular processing will enable drivers to speak natural Hindi/Hinglish instructions, which parse directly into gate coordinates, making parking discovery instant, safe, and truly accessible across India.

---

### 5. Definition of Done
> *"A live, publicly accessible web application where any Indian driver can speak or search a destination in Hindi or English, receive verified gate-level parking options with exact walking and detour metrics, and parking operators can update live slot occupancy on a real database—all secured against ArgosX baseline criteria."*
