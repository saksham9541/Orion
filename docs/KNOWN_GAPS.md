# Orion — Known Gaps, Operational Boundaries & Technical Debt

This document records architectural boundaries, data provenance (real vs. approximate vs. synthetic), operational assumptions, and known technical debt in Orion for operators and maintainers.

---

## 1. Data Provenance Hierarchy: Real, Approximate & Synthetic

Orion operates on a tiered data hierarchy that bridges real Indian Railways operational data with robust mathematical simulations.

| Data Domain | Classification | Source & Implementation | Operational Notes & Guarantees |
|---|---|---|---|
| **Passenger Train Timetables** | **REAL** | Seeded from RailRadar API snapshots (`data/railradar_snapshots/`) for pilot sections (`New Delhi–Ghaziabad` & `New Delhi–Mathura Jn`). | Timetables respect real running days (MON–SUN), train types (Rajdhani, Shatabdi, Mail/Exp, Local/EMU), and halt schedules. |
| **Station Coordinates & Geometry** | **REAL** | High-precision WGS-84 coordinates for pilot stations (NDLS, GZB, SDB, NZM, FDB, BVH, PWL, KSV, CHJ, MTJ) extracted from route geometry snapshots. | Station coordinates are anchor points for section polylines and interactive map views. |
| **Live Delay Snapshots** | **REAL** | Captured via `/api/trains/live/sync` and stored in `live_delay_snapshots` table. | Zero live network calls on user request paths; queries consume local database records. |
| **Track Chainage** | **APPROXIMATE** | Section track distance (`chainage_km`) calculated along segmented station coordinates via `traffic.geo.locate` and `nearest_chainage`. | Labeled as approximate; actual track chainage includes curvature, track doubling, and civil engineering curves. |
| **Pass-Through Station Interpolation** | **APPROXIMATE** | Indian Railways timetables only record scheduled passenger halts. Non-stopping pass-through times are interpolated from distance and maximum sectional speed (130 km/h). | All interpolated entries are explicitly flagged `interpolated=True` on `TrainPassage`. |
| **Live Delay Forecast Decay** | **APPROXIMATE** | For trains expected within a 6-hour horizon, live delay is decayed linearly: $\text{delay}_{\text{eff}} = \max(0, \text{delay} \times (1 - \frac{\Delta t}{6\text{h}}))$. | Models recovery margin and driver regulation over distance. |
| **Track Maintenance Tasks** | **SYNTHETIC** | Procedurally generated with realistic Indian Railways defect types (rail fractures, signal relay failures, catenary breaks). | Located on real track polylines (`latitude`, `longitude`, `chainage_km`) on pilot sections; tagged `source: "synthetic"`. |
| **Passenger Filler Trains** | **SYNTHETIC** | Daytime paths (05:00–23:59) added to match Indian Railways sectional density classes. | Marked with `source: "synthetic_fill"`. Enables coverage metric: $\text{coverage} = \frac{\text{real}}{\text{total}}$. |
| **Freight / Goods Trains** | **SYNTHETIC** | Simulated freight paths added to fill density targets without public timetables. | Tagged `source: "synthetic_goods"`. In production, this requires FOIS (Freight Operations Information System) feed integration. |
| **Non-Pilot Corridor Windows** | **SYNTHETIC** | Corridors outside pilot sections maintain density-class heuristic windows. | Explicitly labeled `source: "synthetic"`. Pilot sections use `source: "timetable_derived"`. |

---

## 2. Window Sensitivity & Filler Rule Analysis

To evaluate how synthetic filler and goods trains affect block window availability, we ran an empirical sensitivity analysis across both pilot sections comparing 4 operational variants:
1. **Variant (a) Real Trains Only**: Timetable-derived passenger trains from RailRadar snapshots ($100\%$ real coverage).
2. **Variant (b) Real + Passenger Filler**: Real trains + synthetic passenger filler (`synthetic_fill`) scheduled during operational daytime hours ($05:00\text{--}23:59$).
3. **Variant (c) Real + Fill + Goods (Default Rule)**: Full target density ($70\text{ trains/day}$ for Class A Special), with passenger filler restricted to daytime operational hours and goods traffic operating across $24\text{ hours}$.
4. **Variant (d) Real + Fill + Goods (Unrestricted 24h Uniform)**: Full target density ($70\text{ trains/day}$), but passenger fillers are distributed uniformly across all $24\text{ hours}$ without respecting the corridor block shadow.

### Sensitivity Comparison Table (Target Date: 2026-11-01)

| Pilot Section | Variant | Total Daily Trains | Real Trains | Coverage Ratio | Available Windows ($\ge 0.5\text{h}$) | Key Discovered Windows (Time & Duration) |
|---|---|---|---|---|---|---|
| **New Delhi–Ghaziabad** (`SEC-93135bb9`, 19 km, $130\text{ km/h}$) | (a) Real Only | 15 | 15 | $100.0\%$ | **5 windows** | 00:00–05:35 ($5.58\text{h}$), 08:40–16:10 ($7.50\text{h}$), 17:35–19:55 ($2.33\text{h}$) |
| | (b) Real + Fill | 55 | 15 | $27.3\%$ | **2 windows** | 00:00–05:35 ($5.58\text{h}$), 08:40–10:10 ($1.50\text{h}$) |
| | (c) Real + Fill + Goods (Default) | 70 | 15 | $21.4\%$ | **2 windows** | **01:00–04:45 ($3.75\text{h}$)**, 09:00–10:10 ($1.17\text{h}$) |
| | (d) Unrestricted 24h | 70 | 15 | $21.4\%$ | **4 windows** | 01:35–02:15 ($0.67\text{h}$), 04:10–04:45 ($0.58\text{h}$), 06:35–07:45 ($1.17\text{h}$) |
| **New Delhi–Mathura Jn** (`SEC-d4d8b85c`, 141 km, $130\text{ km/h}$) | (a) Real Only | 15 | 15 | $100.0\%$ | **3 windows** | 00:00–04:35 ($4.58\text{h}$), 08:40–16:10 ($7.50\text{h}$), 19:15–19:55 ($0.67\text{h}$) |
| | (b) Real + Fill | 55 | 15 | $27.3\%$ | **1 window** | **02:20–04:35 ($2.25\text{h}$)** |
| | (c) Real + Fill + Goods (Default) | 70 | 15 | $21.4\%$ | **0 windows** (shared line) | Gaps fragmented by continuous $80\text{m}$ transit times without directional track splitting |
| | (d) Unrestricted 24h | 70 | 15 | $21.4\%$ | **0 windows** | Completely saturated when modeled as single track capacity |

### Impact of the Operational Hours Filler Rule
- **Why Night Gaps Depend on the Rule**: In Variant (d), uniformly scattering filler trains across 24 hours fragments the night window into micro-gaps ($35\text{--}50\text{ min}$) insufficient for heavy track maintenance. Restricting passenger filler traffic to $05:00\text{--}23:59$ preserves the realistic $3.75\text{h}$ night window on NDLS–GZB and $2.25\text{h}$ on NDLS–MTJ.
- **Indian Railways Operational Justification**: This matches physical Indian Railways operations where long-distance passenger services through Delhi division are scheduled away from $01:00\text{--}04:30\text{ AM}$ precisely to create the divisional maintenance window.
- **Configurability**: In `traffic/fill.py`, `FillerConfig` provides `restrict_passenger_to_operational_hours` (default `True`), `passenger_operational_hours` (default `[0, 5..23]`), and `goods_operational_hours` (default `0..23`), allowing operators to test unconstrained scenarios.

---

## 3. Mathematical Modeling & Simulation Assumptions

### Clearance Buffers & Headway
- **Clearance Buffer**: A configurable safety buffer of **10 minutes** is enforced before and after every train passage. A candidate block window must provide at least $\text{task\_duration} + \text{setup\_time} + \text{clearance\_buffer}$ of continuous unoccupied track.
- **Minimum Headway**: A spacing of **5 minutes** is enforced between consecutive trains running on the same track section.

### Delay Calculation & Hold Rule
- **Hold Rule**: Any train scheduled to traverse a section during an active maintenance block is held at the section entry station until the block concludes, incurring delay:
  $$\text{Delay} = \text{Overlap Duration} + \text{Minimum Headway}$$
- **Reroute Penalty**: If the section configuration specifies a viable alternate bypass route, trains are marked rerouted with a penalty of **25 minutes** rather than being held indefinitely.

### Cascade Propagation
- Delay propagates sequentially:
  1. **Subsequent Stops**: To all downstream stations for the delayed train.
  2. **Following Trains**: To subsequent trains on the same section whose arrival violates the minimum 5-minute headway.
- **Rake Linkage Limitation**: Indian Railways open APIs do not provide physical rake turnaround rosters (e.g., train 12004 turnaround becoming train 12003). Therefore, cross-journey rake-chain turnaround delay propagation is omitted.

---

## 3. Department Governance & State Machine Guarantees

Orion implements a five-stage Plan State Machine:
$$\text{PROPOSED} \longrightarrow \text{DEPT_REVIEW} \longrightarrow \begin{cases} \text{READY\_FOR\_CONTROLLER} & \text{(all depts accept)} \\ \text{CONFLICT} & \text{(any dept rejects)} \end{cases} \longrightarrow \text{APPROVED / REJECTED}$$

### Safety-Critical Defect Guard
- **Derailment Risk Prevention**: Rejection of maintenance blocks containing safety-critical defects (e.g., severe rail fractures, broken OHE wires) cannot be performed unilaterally by a department user (`DEPT_USER`).
- **Controller Override Requirement**: Rejecting a safety-critical block requires explicit Controller authorization (`controller_override: True`) with a logged operational justification.
- **Re-solving with Forbidden Constraints**: Re-running CP-SAT via `POST /api/plans/{id}/re-solve` adds hard constraints forbidding rejected `(task_id, window_id)` assignments while preserving existing approved blocks.

---

## 4. Machine Learning Models & Training Honesty

- **Training Provenance Metadata**: Model training records data provenance (`transparent_delay_calculator` vs `real_delay_snapshots`). Training on live delay snapshots requires at least $N \ge 50$ logged snapshots.
- **Health Exposure**: The active training provenance is inspectable via `GET /api/health?verbose=true`.
- **Missing Models Fallback**: If models are missing on boot, the application starts in degraded mode (`models_loaded = False`) with deterministic heuristic fallbacks.

---

## 5. API Rate Limiting & Cooldowns

- **RailRadar API Quotas**: Multi-key rotation operates across `RAILRADAR_API_KEYS`. Each key enforces a safe ceiling of `RAILRADAR_KEY_LIMIT` (default 90 calls/month).
- **Zero Live Calls on Request Paths**: All frontend requests consume cached timetable passages, geometry, and local delay snapshots. RailRadar calls occur only via explicit snapshot/sync scripts (`scripts/snapshot_railradar.py`, `scripts/log_live_delays.py`).
- **Failure Cooldowns**:
  - `401`, `403`, `429`: 1-hour cooldown per failing key.
  - `5xx` Server Errors: 5-minute cooldown per key.
  - `400`, `404`, `422`: Records API usage without burning subsequent keys.
- **Login Rate Limiting**: 5 failed login attempts per `(email, ip)` pair locks out for 15 minutes. A secondary ceiling of 20 failed attempts per IP prevents distributed brute-force attacks across accounts.

---

## 6. Security & Deployment

- **Secret Safety**: In production (`ENVIRONMENT=production`), the application refuses to start if `JWT_SECRET` is missing or shorter than 32 characters.
- **CORS Configuration**: In production, `CORS_ORIGINS` must be explicitly defined. A warning is logged if default localhost origins are active in production.
- **PostgreSQL Pre-Ping**: Database connection pools employ `pool_pre_ping=True` and connection retries to absorb serverless cold starts.
