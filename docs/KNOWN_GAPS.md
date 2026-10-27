# Orion — Known Gaps, Operational Boundaries & Technical Debt

This document records architectural boundaries, external dependencies, and known production gaps in Orion for operators and maintainers.

---

## 1. Real vs. Simulated Data Boundary

| Component | Status | Source & Handling | Production Requirement |
|---|---|---|---|
| **Passenger Train Timetables & Live Status** | **REAL** | Polled live or read from cached snapshots via the RailRadar API (`https://api.railradar.in/v1`). | Requires active RailRadar enterprise API subscription with sufficient request quotas. |
| **Track Maintenance Tasks** | **SIMULATED** | Generated synthetically or imported manually by operators. Marked with `source: "synthetic"` or `source: "user"`. | In production, ingested directly from Indian Railways TMS, SMMS, and TDMS databases. |
| **Block Windows & Corridors** | **SIMULATED / CALIBRATED** | Delhi-Howrah and Delhi-Mumbai corridors are geographically and distance calibrated; other corridors use domain approximations. Windows are synthetic. | Integration with Indian Railways Control Office Application (COA) for real-time section block availability. |
| **Goods / Freight Trains** | **SIMULATED** | Simulated timetable paths to capture traffic density. | Real FOIS (Freight Operations Information System) feed integration. |

---

## 2. Machine Learning Models & Training

- **Synthetic Label Ground Truth**: ML models (`CriticalityScorer`, `TrafficImpactPredictor`, `DurationEstimator`) are trained on synthetic data generated via domain heuristics.
- **On-Demand Training**: Models are not automatically retrained upon server boot. Use `python scripts/train_models.py` or trigger `/api/demo/setup` to retrain and persist models to `ml/models/*.pkl`.
- **Missing Models Fallback**: If models are missing on boot, the app starts in degraded mode with `app.state.models_loaded = False`, logging a warning and falling back to heuristic scoring.

---

## 3. Database & Cloud Architecture

- **PostgreSQL Neon Serverless Sleeping**: When deployed to Neon serverless PostgreSQL, inactive databases enter sleep mode. Orion uses SQLAlchemy pre-ping pooling (`pool_pre_ping=True`) and retries the first connection once upon boot.
- **SQLite Fallback**: Local development and standalone tests fall back to SQLite if `DATABASE_URL` is omitted. SQLite does not support native `JSONB` indexes or PostgreSQL full-text search.
- **Alembic Migrations**: All database schema changes must be applied via `alembic upgrade head`. Manual `create_all` is restricted to local SQLite test runs.

---

## 4. API Rate Limiting & Cooldowns

- **RailRadar API Quotas**: Multi-key rotation operates across `RAILRADAR_API_KEYS`. Each key enforces a safe ceiling of `RAILRADAR_KEY_LIMIT` (default 90 calls/month).
- **Failure Cooldowns**:
  - `401`, `403`, `429`: 1-hour cooldown per failing key.
  - `5xx` Server Errors: 5-minute cooldown per key.
  - `400`, `404`, `422`: Records API usage but does **not** fail over or burn subsequent keys.
- **Login Rate Limiting**: 5 failed login attempts per `(email, ip)` pair locks out for 15 minutes. A secondary ceiling of 20 failed attempts per IP prevents distributed brute-force attacks across accounts.

---

## 5. Security & Deployment

- **Secret Safety**: In production (`ENVIRONMENT=production`), the application refuses to start if `JWT_SECRET` is missing or shorter than 32 characters.
- **CORS Configuration**: In production, `CORS_ORIGINS` must be explicitly defined. A warning is logged if default localhost origins are active in production.
