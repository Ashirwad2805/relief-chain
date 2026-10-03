# AUDIT RESPONSE — ReliefChain v3
*Updated automatically as fixes are applied. Phase order: 1→7.*

> **Machine:** Windows 11 (user's laptop) — document spec when stress tests run.

---

## Defect Register Status

| ID | Priority | Title | Status | Fix Summary | Test Evidence |
|---|---|---|---|---|---|
| **A1** | P0 | Frontend never talks to backend | 🔄 Phase 1 | Typed API client + WS live store | TODO |
| **A2** | P0 | Two divergent worlds | 🔄 Phase 1 | One scenario, backend-only | TODO |
| **A3** | P1 | Dead dependency, stub packages | 🔄 Phase 1 | Remove @supabase, implement stubs | TODO |
| **A4** | P1 | Role is client-chosen, open tamper/reset | 🔄 Phase 4 | JWT + RBAC | TODO |
| **A5** | P1 | persist_to_db swallows errors, no event store | 🔄 Phase 4 | Append-only events table | TODO |
| **B1** | P0 | Hard-coded comparison metrics | 🔄 Phase 3 | Compute from per-patient timelines | TODO |
| **B2** | P0 | Hard-coded baseline survivors | 🔄 Phase 3 | Same survival function both worlds | TODO |
| **B3** | P0 | Forecast fabricated, equity random | 🔄 Phase 3 | Real forecast from backend | TODO |
| **B4** | P1 | Canned decision explanations | 🔄 Phase 3 | Top-K real candidates + zero-slack constraints | TODO |
| **B5** | P1 | Static anomalies | 🔄 Phase 3 | Anomaly detector over ledger/delivery events | TODO |
| **C1** | P0 | Math.random()/Date.now()/uuid4 in sim state | 🔄 Phase 1 | Seeded RNG streams, deterministic IDs | TODO |
| **C2** | P0 | RESTART re-uses consumed RNG | 🔄 Phase 1 | Create RNG inside reset(seed) | TODO |
| **C3** | P0 | Reducer mutates state, SEEK is fake | 🔄 Phase 1 | Server owns state; client replaces immutably | TODO |
| **C4** | P1 | Module-level ledgerVerificationResult | 🔄 Phase 4 | Verification from API | TODO |
| **C5** | P0 | Time-unit bug: 15 real seconds = 15 sim min | 🔄 Phase 1 | 1 sim-min = 6 real sec at 1x, 90 min scenario | TODO |
| **D1** | P0 | One ambulance per incident regardless of count | 🔄 Phase 3 | Patient-count variables with capacity | TODO |
| **D2** | P0 | Ambulances skip pickup, go straight to hospital | 🔄 Phase 3 | Full state machine | TODO |
| **D3** | P0 | ICU double-booking | 🔄 Phase 3 | Exact projected-capacity per resource | TODO |
| **D4** | P0 | Road blockage does not re-route | 🔄 Phase 2/3 | All ETAs from shortest path on live graph | TODO |
| **D5** | P0 | Stale decisions never replaced, duplicates accumulate | 🔄 Phase 3 | Stale detection by dependency, supersede | TODO |
| **D6** | P1 | Anti-thrashing is additive bonus, not en-route lock | 🔄 Phase 3 | En-route lock + reroute threshold | TODO |
| **D7** | P1 | Baseline differs only in hospital choice | 🔄 Phase 3 | True parallel world server-side | TODO |
| **D8** | P1 | Black triage ignored; chaos targets hard-coded | 🔄 Phase 3 | Model black triage, seeded random target | TODO |
| **E1** | P0 | MUMBAI_AREAS coordinates wrong | 🔄 Phase 2 | Verified coords vs OpenStreetMap | TODO |
| **E2** | P0 | Hospitals in wrong areas | 🔄 Phase 2 | Re-place at verified real coordinates | TODO |
| **E3** | P0 | Road network is 10-19 straight lines | 🔄 Phase 2 | Real OSM-derived road graph | TODO |
| **E4** | P1 | SIMULATED DATA labelling | DONE | Labels present in UI | N/A |
| **F1** | P0 | MapView is hand-drawn SVG | 🔄 Phase 2 | Leaflet canvas map with free tiles | TODO |
| **F2** | P1 | No code-splitting, fonts not loaded | 🔄 Phase 6 | Lazy routes, self-hosted fonts | TODO |
| **G1** | - | Flat dark UI, no glass, minimal motion | 🔄 Phase 6 | Liquid Glass redesign per section 4 | TODO |
| **G2** | - | Autopilot fires fixed event IDs | 🔄 Phase 1 | Autopilot via API with captions | TODO |
| **H1** | P1 | Shallow tests | 🔄 Phase 1-5 | Tests listed in section 7 | TODO |
| **H2** | P1 | No Docker, compose, Makefile | 🔄 Phase 7 | docker-compose, Makefile | TODO |

---

## Security Notice (Immediate — DONE)

> **CRITICAL — FIXED:** The `.env` file at repo root contained real API keys for MapTiler,
> Mapbox, and OpenAI. These have been **removed** and replaced with safe placeholder comments.
> A `.env.example` template has been created. `.gitignore` updated to exclude parent `.env` files.
> **Action required by operator:** Rotate/revoke the leaked keys immediately from their dashboards.

---

## Phase Progress

| Phase | Description | Status |
|---|---|---|
| **1** | Wire + delete duplicate engine (A1-A3, C1-C5) | 🔄 In Progress |
| **2** | Geography and map (E1-E3, F1, section 3) | Pending |
| **3** | Allocation repairs (D1-D8, B1-B5) | Pending |
| **4** | Security and ledger (A4, A5, C4, 5.6, 5.7) | Pending |
| **5** | Crisis Stress Lab + perf engineering | Pending |
| **6** | Liquid glass redesign | Pending |
| **7** | Docker, compose, Makefile, docs | Pending |
