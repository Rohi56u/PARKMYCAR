# hackFront India Grand Finale: 1-Page Market Fit Canvas

**Project**: ParkMyCar (Destination Parking Decision Intelligence Engine)  
**Lead**: Rohit Choudhary | **Target**: hackFront India Grand Finale (IIIT Delhi)

---

### Market Fit Canvas Matrix

| Parameter | What Must Be Shown (hackFront Finale Criteria) | ParkMyCar Evidence & Strategy |
| :--- | :--- | :--- |
| **Target Customer** | The one primary user you serve first, named specifically. | **Anil Sharma (32)**, IT consultant driving daily from Noida to Connaught Place / Cyber City for meetings, losing 25–35 minutes searching for parking and risking municipal towing. |
| **Problem Validation** | Evidence that this problem exists for them. | • CSE India & IBM Commuter Studies: **30%–40%** of CBD traffic in Delhi/Mumbai is "dead cruising" for parking.<br>• Commuters waste **~₹4,200/month** in idling fuel and risk ₹2,000 towing challans.<br>• Municipal Multi-Level Parkings (e.g. Palika Underground: 1,050 slots) operate at <30% capacity because entry barriers and walk distance are unmapped. |
| **Current Alternative** | What they do today instead, and why they would switch. | 1. **Google Maps**: Drops drivers at complex center centroids (pedestrian gardens/one-way lanes) with no vehicular barrier awareness.<br>2. **On-Street Touts (Parking Mafia)**: Extort ₹100–₹300 flat cash with counterfeit slips.<br>• *Why Switch*: ParkMyCar routes to the **exact vehicle barrier gate** with verified walking distance and transparent pricing. |
| **Value Proposition** | Why they would choose your product. | **Zero False Guarantees + Destination Gate Intelligence**: We don't promise phantom spaces; we show evidentiary freshness (TTL decay), conflict warnings ("Updates differ"), and direct turn-by-turn to the barrier gate with minimal walking time. |
| **Business Model** | Who pays, and a pricing hypothesis with a number. | • **B2C Drivers**: **₹15** micro-convenience fee per guaranteed destination routing / spot hold.<br>• **B2B Parking Operators / Valets**: **₹1,999 / month** SaaS subscription for live digital occupancy dispatch and dynamic tariff management via `/workspace`. |
| **Market Opportunity** | How large or relevant the market is, with a source. | **$1.8 Billion** Indian Smart Urban Parking Market by 2030 (CAGR 14.2%, Mordor Intelligence & NITI Aayog Urban Mobility). Driven by **38 Million+ registered private cars** in Top 8 Indian metros and 130M+ NETC FASTag users. |
| **Competitive Landscape** | Who else solves this, and where you differ. | • **Park+**: Cluttered super-app focused on FASTag recharge & car loans; lacks gate-level walk vs detour optimization.<br>• **Google Maps**: General navigation with static "P" pins; no live gate telemetry or conflict alerts.<br>• **ParkMyCar**: Ultra-fast PWA (<2s load), DPDP-compliant (no login/tracking), and Indic voice search via Sarvam AI. |
| **First 100 Users** | How you will acquire your first users. | 1. Partnership with New Delhi Traders Association (NDTA) for Connaught Place merchant parking.<br>2. QR code standees at Palika Bazaar underground entry and Cyber Hub parking entrances.<br>3. Community launch in Delhi-NCR Car Commuter WhatsApp & Telegram groups. |

---

### The 3 Customer Test (Venue Evidence Log)

Conducted at IIIT Delhi / Okhla commercial cluster:

1. **Customer 1: Delhi-NCR Car Commuter (Visitor at IIIT Delhi)**
   * *What we assumed*: Drivers strictly search for the lowest-priced parking spot.
   * *What we found out*: They prioritize **walking distance to their meeting gate** over saving ₹20. Walking 800m in Delhi summer heat is a dealbreaker.
   * *What we changed*: Prominently added the **"Walking Distance vs. Vehicle Detour"** comparison badge on every facility card.

2. **Customer 2: Commercial Cab Driver (Ola/Uber Driver at Govindpuri)**
   * *What we assumed*: Drivers will type destination addresses into a mobile search input.
   * *What we found out*: Drivers find it dangerous and difficult to type English landmark names while driving in traffic.
   * *What we changed*: Integrated **Sarvam AI Indic Speech-to-Text** for one-tap Hindi/Hinglish voice search.

3. **Customer 3: Local Surface Parking Attendant (Okhla Industrial Area)**
   * *What we assumed*: Parking contractors require automated IoT sensors and camera hardware.
   * *What we found out*: Small contractors cannot afford ₹50,000 sensor rigs; they need a dead-simple 2-button mobile dashboard (Full / Available).
   * *What we changed*: Streamlined the **Operator Workspace (`/workspace`)** into a lightweight mobile-first interface.
