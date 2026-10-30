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

## 2. Mathematical Modeling & Simulation Assumptions

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
