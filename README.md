<div align="center">

<img src="https://img.shields.io/badge/🚗_ParkMyCar-Find_parking._Finish_the_journey.-1a1a2e?style=for-the-badge&labelColor=1a1a2e&color=7c3aed" alt="ParkMyCar"/>

# ParkMyCar

**The parking decision tool built for Indian drivers.**  
Search any destination in India. Compare real nearby parking. Get directions.

[![Live App](https://img.shields.io/badge/🌐_Live_App-parkmycarr.netlify.app-7c3aed?style=flat-square)](https://parkmycarr.netlify.app)
[![Deploy Status](https://img.shields.io/badge/Netlify-Deployed-00C7B7?style=flat-square&logo=netlify)](https://parkmycarr.netlify.app)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](LICENSE)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg?style=flat-square)](LICENSE)
[![Next.js 16](https://img.shields.io/badge/Next.js-16.3-black?style=flat-square&logo=next.js)](https://nextjs.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.9-3178c6?style=flat-square&logo=typescript)](https://www.typescriptlang.org/)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind-4.2-06b6d4?style=flat-square&logo=tailwindcss)](https://tailwindcss.com/)
[![Leaflet Maps](https://img.shields.io/badge/Leaflet-1.9-199900?style=flat-square&logo=leaflet)](https://leafletjs.com/)
[![AI Powered](https://img.shields.io/badge/AI-Decision_Engine-7c3aed?style=flat-square)](#)

**[Try it live →](https://parkmycarr.netlify.app)**  |  [How it works](#how-it-works)  |  [What's different](#what-makes-this-different)  |  [Deploy your own](#deploy-your-own)  |  [API Docs](#api-reference)

</div>

---

## 🎬 90-Second Product Video Walkthrough

> Watch the full voiceover walkthrough demonstrating destination parking discovery, gate verification, and evidence transparency in Indian urban environments.

[![ParkMyCar Live Web Application](docs/screenshots/app-preview.png)](https://parkmycarr.netlify.app)

* **Direct video asset:** [`public/video/demo.mp4`](public/video/demo.mp4) *(7.15 MB, MP4 with voiceover)*
* **Interactive playback in live web app:** Click the **`90s Demo`** button in the top navigation bar at **[parkmycarr.netlify.app](https://parkmycarr.netlify.app)** to open the full-screen modal player.

---

## 📊 Official Product Presentation & Architectural Roadmap (14 Slides)

> The strategic and technical pitch deck presented for Indian smart city mobility, featuring municipal data context (NDMC & BMRCL 2026), 4-step decision flow, and IoT sensor integration.

**📄 [Download Complete Pitch Deck PDF (14 Slides, 17.8 MB)](docs/ParkMyCar_Product_Presentation.pdf)**

<div align="center">

| Slide 02 — The Parking Decision | Slide 03 — 4-Step Decision Flow |
|:---:|:---:|
| [![Slide 2](docs/slides/slide_02.png)](docs/ParkMyCar_Product_Presentation.pdf) | [![Slide 3](docs/slides/slide_03.png)](docs/ParkMyCar_Product_Presentation.pdf) |
| *Municipal problem context (NDMC & BMRCL 2026)* | *Destination to parking in 4 steps* |

| Slide 04 — Usable Shortlist UI | Slide 07 — Report Review Lifecycle |
|:---:|:---:|
| [![Slide 4](docs/slides/slide_04.png)](docs/ParkMyCar_Product_Presentation.pdf) | [![Slide 7](docs/slides/slide_07.png)](docs/ParkMyCar_Product_Presentation.pdf) |
| *Compare up to 3 options side-by-side* | *Time-sensitive review queue with TTL expiry* |

| Slide 08 — Platform Architecture | Slide 11 — Positioning vs. Google Maps |
|:---:|:---:|
| [![Slide 8](docs/slides/slide_08.png)](docs/ParkMyCar_Product_Presentation.pdf) | [![Slide 11](docs/slides/slide_11.png)](docs/ParkMyCar_Product_Presentation.pdf) |
| *Next.js + Worker API + D1/Memory SQLite* | *Why ParkMyCar if Google Maps already exists* |

| Slide 12 — Phased Implementation Roadmap | Slide 13 — Planned Live Sensors Flow |
|:---:|:---:|
| [![Slide 12](docs/slides/slide_12.png)](docs/ParkMyCar_Product_Presentation.pdf) | [![Slide 13](docs/slides/slide_13.png)](docs/ParkMyCar_Product_Presentation.pdf) |
| *Four strict release gates (01 Current → 04 City Scale)* | *Area, capacity, unlisted lots & bay counts* |

</div>

---

## The problem this solves

Most drivers in India find parking by guessing. Google Maps shows parking dots — no access rules, no vehicle fit check, no honest signal of whether the place is actually open or full. Navigation apps are built for *getting there*, not for *choosing where to park once you arrive*.

**ParkMyCar is built around the single moment that matters: arriving at a destination and needing to make a real parking decision.**

Before you arrive, you need answers to three specific questions:

| Question | What apps show today | What ParkMyCar shows |
|---|---|---|
| **Can I use this parking?** | A pin. Maybe a label. | Access type (Public / Customers only / Permit / Unknown), vehicle compatibility, entry notes |
| **Which option fits my trip?** | One suggestion, if any | Up to 30 ranked options — by distance or price — with a save shortlist for alternatives |
| **How current is this?** | No indication | Evidence source, timestamp, TTL expiry. If data is stale: **"Availability not confirmed"** |

---

## What makes this different

### 1. Evidence-First Architecture — No Fake Availability

Every parking status shown has a **traceable source, a reporter, and an expiry time**. When a report expires, the state resets to `UNKNOWN` — it does not roll over as "still available."

```
STATIC_LISTING      → Mapped from OSM/NDMC. No live status.
OPERATOR_REPORTED   → Posted by a verified operator for this facility.
COMMUNITY_REPORTED  → Submitted by a driver, reviewed before publishing.
```

There is no interpolation, no guessing, no stale data dressed as fresh data. This is the core design principle.

### 2. Access Gate Differentiation — Not Just "Parking"

The app distinguishes between five access states that matter to different drivers:

```
PUBLIC           → Anyone can park
CUSTOMERS_ONLY   → Restricted to customers of the venue
PRIVATE          → Not shown in public results
PERMIT           → Not shown in public results  
UNKNOWN          → Shown with "Check access before arrival" warning
```

This is not a cosmetic filter. Private and permit-only facilities are excluded from search results. You won't navigate to a parking area that won't let you in.

### 3. Four-Step Decision Flow

```
Search destination → Filter by vehicle/type/features → Compare up to 3 → Open directions
```

The flow ends with **two sets of directions**: drive to parking, then walk to your destination. The walking leg is shown separately because it is the leg most apps ignore.

### 4. Reviewed Report Pipeline

Driver reports don't publish instantly. They enter a review queue:

```
Driver submits → Review queue → Reviewer decides → Published (or rejected)
```

Reports carry: who submitted it, when, and when it expires. The expiry is strict — a 15-minute observation cannot survive as "current" for an hour.

### 5. Arrival-First AI Decision Intelligence

After each search, the app optionally surfaces an AI-powered natural language recommendation — a single sentence that weighs distance, availability state, hours, and price. It degrades gracefully: if no API key is configured, it simply doesn't appear.

---

## How it works

```mermaid
sequenceDiagram
    participant Driver
    participant WebApp as Next.js App
    participant API as Worker API
    participant Photon as Photon (Place Search)
    participant DB as In-Memory / D1 DB
    participant AI as Decision AI Engine

    Driver->>WebApp: Enter destination (e.g. "Palika Bazaar")
    WebApp->>API: POST /api/v1/places/search
    API->>Photon: Query India place data
    Photon-->>API: GeoJSON features
    API-->>WebApp: Normalised place list

    Driver->>WebApp: Select place + set arrival time, vehicle
    WebApp->>API: POST /api/v1/search
    API->>DB: Query facilities within radius
    API->>DB: Query non-expired observations
    API-->>WebApp: Ranked results with evidence

    WebApp->>API: POST /api/v1/ai-suggest
    API->>AI: Top 3 results + context
    AI-->>API: Natural language recommendation
    API-->>WebApp: AI suggestion

    Driver->>WebApp: Open directions
    WebApp-->>Driver: Google Maps (drive to parking → walk to destination)
```

---

## Live demo

**→ [https://parkmycarr.netlify.app](https://parkmycarr.netlify.app)**

**What you can do right now:**
- Search any destination in India by name, landmark, neighbourhood, or city
- View 5 sourced parking facilities in Connaught Place, New Delhi
- Filter by vehicle type, parking type, radius, and features
- Save up to 3 options to a shortlist and compare them side by side
- Open driving directions to any parking facility
- Report an issue with a listing (enters the moderated review queue)
- View evidence source and timestamp for every status shown

**Current pilot area:** Connaught Place, New Delhi (5 verified facilities from OSM + NDMC)  
**Place search:** All of India (cities, towns, villages, landmarks via Photon + OSM)

---

## Deploy your own

### One-click deploy

[![Deploy to Netlify](https://www.netlify.com/img/deploy/button.svg)](https://app.netlify.com/start/deploy?repository=https://github.com/Rohi56u/PARKMYCAR)
[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https://github.com/Rohi56u/PARKMYCAR)

### Manual deploy

```bash
git clone https://github.com/Rohi56u/PARKMYCAR.git
cd PARKMYCAR
pnpm install
pnpm dev
```

Requirements: **Node.js ≥ 22.13**, **pnpm 11**

### Enable AI suggestions (optional)

Provide an AI API key as an environment variable in .env.local or on your deployment host:

```
AI_API_KEY=your_key_here
```

On Netlify: Site settings → Environment variables → Add `AI_API_KEY`.  
The app works fully without this key — AI suggestions simply won't appear.

### Netlify config (already included)

```toml
# netlify.toml
[build]
  command = "pnpm run build"
  publish = ".next"

[build.environment]
  NODE_VERSION = "22"
```

---

## Project structure

```
parkmycar/
├── app/                    # Next.js App Router pages & API routes
│   ├── api/v1/             # REST API: parking search, AI suggest
│   ├── research/           # Research explorer page
│   ├── workspace/          # Operator workspace dashboard
│   ├── globals.css         # Design-system tokens & component styles
│   └── layout.tsx          # Root layout with PWA manifest
├── components/             # UI components
│   ├── ParkApp.tsx         # Main search & results interface
│   ├── ParkingMap.tsx      # Leaflet map with parking overlays
│   ├── PlaceSearch.tsx     # Geocoding-powered place search
│   ├── AiSuggest.tsx       # AI parking suggestion bar
│   ├── Dialog.tsx          # Confirmation & detail dialogs
│   ├── Workspace.tsx       # Operator dashboard
│   └── ui/                 # shadcn/ui component library (50+ components)
├── data/                   # Static data sources
│   ├── source-catalog.json # Parking facility catalogue
│   ├── source-destinations.json
│   └── source-review.json
├── db/                     # Database layer
│   ├── schema.ts           # Drizzle ORM schema
│   └── index.ts            # DB connection helper
├── docs/                   # Documentation & assets
│   ├── API.md              # API reference
│   ├── ARCHITECTURE.md     # System architecture
│   ├── SECURITY.md         # Security model
│   ├── RESEARCH.md         # Research notes
│   ├── TRACEABILITY.md     # Decision traceability
│   └── slides/             # Product presentation slides
├── drizzle/                # Database migrations (SQLite/D1)
├── hooks/                  # React hooks
├── lib/                    # Core business logic
│   ├── catalogue.ts        # Parking catalogue loader
│   ├── geocoding.ts        # Geocoding utilities
│   ├── places.ts           # Places API integration
│   ├── service.ts          # Parking search service
│   ├── domain.ts           # Domain types
│   ├── contracts.ts        # API contracts
│   ├── store.ts            # Client state store
│   ├── db.ts               # Database utilities
│   ├── client.ts           # API client
│   └── utils.ts            # Shared utilities
├── public/                 # Static assets (fonts, icons, PWA manifest)
├── scripts/                # Developer utilities
│   └── setup-local.mjs     # Local dev environment setup
├── tests/                  # Test suite
│   ├── api.test.ts         # API route tests
│   ├── domain.test.ts      # Domain logic tests
│   └── geocoding.test.ts   # Geocoding tests
├── .github/workflows/      # CI/CD (GitHub Actions)
├── .env.example            # Environment variable template
├── netlify.toml            # Netlify deployment config
├── next.config.ts          # Next.js configuration
├── drizzle.config.ts       # Drizzle ORM configuration
└── package.json            # Dependencies & scripts
```
## API reference

Base URL: `https://parkmycarr.netlify.app/api/v1`

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check — returns `{status:"ok", catalogueVersion}` |
| `GET` | `/bootstrap` | Fetch all destinations, facilities and coverage metadata |
| `POST` | `/places/search` | Search places across India (requires `Same-Origin`) |
| `POST` | `/search` | Find and rank parking near a destination |
| `GET` | `/facilities/:id` | Get a single facility with current evidence |
| `POST` | `/reports` | Submit a driver report (requires `Same-Origin`) |
| `POST` | `/ai-suggest` | Get AI parking recommendation |
| `GET` | `/workspace` | Operator/admin dashboard data (requires auth) |

### POST /search — request body

```json
{
  "destination": { "lat": 28.6313, "lng": 77.2179 },
  "origin": { "lat": 28.6100, "lng": 77.2090 },
  "radius": 1000,
  "arrivalAt": "2026-10-31T14:00:00+05:30",
  "durationMinutes": 120,
  "vehicle": "CAR",
  "requirements": [],
  "type": "all",
  "sort": "distance",
  "includeUnknown": true,
  "includeCustomer": false
}
```

### POST /search — response

```json
{
  "results": [
    {
      "id": "palika",
      "name": "Palika Parking",
      "type": "underground",
      "access": "PUBLIC",
      "distanceMeters": 142,
      "evidence": {
        "state": "UNKNOWN",
        "evidenceClass": "STATIC_LISTING",
        "label": "Mapped parking",
        "source": null,
        "observedAt": null,
        "expiresAt": null,
        "conflict": false
      },
      "hoursState": "unknown",
      "totalCost": null,
      "reasons": ["140 m from your destination", "Underground parking", "Listed by NDMC"]
    }
  ],
  "coverage": { "name": "Connaught Place, New Delhi", ... },
  "serverTime": "2026-10-31T08:30:00.000Z",
  "catalogueVersion": "cp-2026-10-17-v1"
}
```

---

## Data sources

All data is sourced, dated, and attributed. No data is invented.

| Source | What it contributes | License |
|--------|---------------------|---------|
| OpenStreetMap | Facility locations, type, mapped access | ODbL 1.0 |
| NDMC (ndmc.gov.in) | Municipal facility confirmation for Connaught Place | Public record |
| BMRCL (2026 Metro Parking Policy) | Policy evidence for urban parking demand | Public record |
| MoHUA Lok Sabha Q292 (Mar 2026) | Infrastructure context | Public record |
| Photon (komoot.io) | Place search geocoding across India | ODbL 1.0 |

Data currency and source links are visible within the app on every facility listing.

---

## Roadmap

The expansion plan follows a phased release gate model — each stage requires meeting reliability criteria before proceeding:

```
01  CURRENT    Working app · India place search · 5 sourced CP facilities · AI suggestions
02  NEXT       Field pilot · Survey entrances · Confirm rules · Onboard operators
03  THEN       Live operations · Operator APIs · Gate counts · Bay sensors
04  THEN       City expansion · PostGIS spatial search · Multi-language · New areas
```

No city is added without a surveyed facility with a named source and accountable owner. This is the release gate.

---

## Roles

The app has three distinct user roles with strictly enforced permissions:

| Role | Can do |
|------|--------|
| **Driver** | Search, compare, save shortlist, report issues |
| **Operator** | Update assigned parking listings, post status observations |
| **Admin** | Review reports, moderate changes, manage team, view audit log |

Operators work only on locations assigned to them. Admins review all changes. Every write action creates an audit event.

---

## License

This project is dual-licensed:

**[MIT License](LICENSE)** — permissive use, modification, and distribution with attribution.  
**[Apache License 2.0](LICENSE)** — same permissive terms, with explicit patent grant.

You may use this project under either license.

Copyright © 2026 [Rohit Choudhary (Rohi56u)](https://github.com/Rohi56u)

---

## Acknowledgements

- [OpenStreetMap contributors](https://openstreetmap.org/copyright) — map data and facility locations
- [Photon by Komoot](https://photon.komoot.io) — geocoding API
- [Leaflet](https://leafletjs.com) — interactive maps
- [Next.js](https://nextjs.org), [Tailwind CSS](https://tailwindcss.com), [Lucide](https://lucide.dev) — UI stack
- [Decision Intelligence AI Engine] — contextual parking guidance
- NDMC, BMRCL, MoHUA — public data sources

---

<div align="center">

**[parkmycarr.netlify.app](https://parkmycarr.netlify.app)** · **[GitHub](https://github.com/Rohi56u/PARKMYCAR)**

*A place for your car. A plan for your journey.*

</div>
