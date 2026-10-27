# Orion — AI-Powered Maintenance Block Optimization for Indian Railways

**Transforming decentralized, manual maintenance block planning into a data-driven, coordinated process that maximizes asset availability, improves safety, and supports reliable train operations.**

---

## 1. Problem

Indian Railways maintenance across Engineering (track), S&T (signals), and TRD (traction/OHE) is planned independently. Each department requests blocks via BDMS without cross-department coordination. This leads to:
- **Inefficient block utilization** — departments take separate closures on the same corridor
- **No comparable urgency scale** — a "P1" track defect and a "P1" signal defect are scored differently
- **Block overruns** — unreliable duration estimates cause cascading delays
- **Suboptimal scheduling** — blocks during peak traffic when off-peak windows exist

---

## 2. Solution & Core Engines

Orion integrates maintenance data with corridor availability and real passenger train schedules to generate optimized, merged, multi-department block schedules.

### Core ML Engine
- **Criticality Scorer** (XGBoost) — produces cross-department comparable urgency scores (0-100)
- **Traffic Impact Predictor** (LightGBM) — predicts how disruptive each block window is
- **Duration Estimator** (Random Forest) — predicts realistic task duration with confidence intervals
- **Defect Text Classifier** (NLP/LLM) — extracts structured severity from inspector free-text notes

### CP-SAT Block Scheduler
- Google OR-Tools constraint optimization assigns tasks to windows
- **Block merging** — combines multi-department work into shared blocks, saving hours of track closure
- **SLA enforcement** — emergency tasks force-scheduled, overdue tasks auto-escalated
- **Optimization Constraints & Weights** —
  - Criticality reward weight is effective `beta + delta` (`delta` maintained for backward compatibility).
  - Overlapping windows on the same track section cannot be simultaneously scheduled.
  - `max_block_hours_per_corridor_per_week` config parameter is currently not enforced.

### Real Passenger Train Integration
- Real-time live train running status, delays, and GeoJSON route geometry via RailRadar API (`https://api.railradar.in/v1`)
- Multi-key rotation and caching with monthly quota protections (default 90 req/month/key)
- Heatmap visualizer displaying defect hotspots correlated with real train delays

### GenAI & Explainability Layer
- Natural-language plan briefings for control rooms
- Query interface for controllers: "Why was defect #4521 pushed to next month?"
- SHAP-based explainability for every ML prioritization decision

---

## 3. Data Rule: Real vs. Simulated

Every API response and UI view carries an unambiguous `source` label ("live", "cache", "snapshot", "synthetic", or "user"):

| Domain Element | Data Nature | Source & Handling | Source Label |
|---|---|---|---|
| **Passenger Train Timetables & Delays** | **REAL** | Fetched live via RailRadar API; local cache and fallback snapshots | `"live"`, `"cache"`, `"snapshot"` |
| **Train Route Geometries (GeoJSON)** | **REAL** | Real track alignments fetched from RailRadar | `"live"`, `"cache"` |
| **Maintenance Defect Tasks** | **SIMULATED** | Generated synthetically or input by operators | `"synthetic"`, `"user"` |
| **Corridors & Sections** | **CALIBRATED** | Delhi-Howrah and Delhi-Mumbai geographically calibrated; others approximated | `"synthetic"` |
| **Block Windows & Goods Trains** | **SIMULATED** | Synthetically generated to match density patterns | `"synthetic"` |

---

## 4. Architecture

```
Real Train Feeds (RailRadar) ──┐
                               ├──► ML Scoring & Traffic Impact ──► CP-SAT Optimizer (Block Merging)
Maintenance Systems (TMS/SMMS) ─┘                                            │
                                                                             ▼
                                 React Dashboard ◄── FastAPI Backend ◄── GenAI Explainability
```

---

## 5. Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+ (for frontend)
- PostgreSQL (e.g., Neon serverless) or SQLite for local development

### Backend Setup
```bash
# 1. Install production dependencies
pip install -r requirements.txt

# (Optional) Install development & test dependencies
pip install -r requirements-dev.txt

# 2. Configure environment
cp .env.example .env
# Edit .env with your JWT_SECRET, DATABASE_URL, and RAILRADAR_API_KEYS

# 3. Apply database migrations
alembic upgrade head

# 4. Create initial administrator account
python scripts/create_admin.py --email admin@railways.gov.in --name "Chief Controller" --password "<secure-password>"

# 5. (Optional) Pre-train ML models
python scripts/train_models.py --tasks 1000

# 6. Start backend server
uvicorn backend.main:app --reload --port 8000
```

### Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

### Running Tests
```bash
pytest tests/ -v
```

---

## 6. Project Structure

```
ORION/
├── railopt/                    # Core Domain Models & Adapters
│   ├── models.py               # Pydantic domain models
│   ├── synthetic_data.py       # Deterministic synthetic data generator
│   ├── data_integration.py     # TMS/SMMS/TDMS ingestion adapters
│   ├── sim_entities.py         # Train simulation entities
│   └── sim_state_machine.py    # Train state transitions
├── ml/                         # Machine Learning Pipeline
│   ├── criticality_scorer.py   # XGBoost risk scorer
│   ├── impact_predictor.py     # LightGBM impact model
│   ├── duration_estimator.py   # Random Forest duration estimator
│   ├── defect_text_classifier.py # NLP severity extractor
│   ├── feature_engineering.py  # Tabular feature extractors
│   └── training_pipeline.py    # Training orchestration
├── optimizer/                  # Mathematical Optimization
│   ├── cpsat_solver.py         # Google OR-Tools CP-SAT scheduler
│   ├── block_merger.py         # Multi-department block merger
│   └── sla_engine.py           # SLA enforcement & escalation
├── integrations/               # External APIs
│   └── railradar_client.py     # Multi-key rotating RailRadar client
├── genai/                      # GenAI & Explainability
│   ├── briefing_generator.py   # Control room briefings
│   ├── nl_query_engine.py      # Natural language query engine
│   └── explainability.py       # SHAP explanation provider
├── simulator/                  # What-If Impact Simulator
│   └── block_impact_simulator.py
├── backend/                    # FastAPI Application
│   ├── main.py                 # REST API endpoints & lifecycle
│   ├── database.py             # PostgreSQL (Neon) & SQLite persistence
│   ├── auth.py                 # RBAC, JWT tokens, login rate limiting
│   └── schemas.py              # Pydantic API schemas
├── scripts/                    # CLI Utilities
│   ├── create_admin.py         # Admin user creation
│   ├── train_models.py         # On-demand ML model training
│   ├── migrate_sqlite_to_postgres.py # SQLite to PostgreSQL data migration
│   └── snapshot_railradar.py   # Snapshot generator for offline use
├── alembic/                    # Database Migrations
│   └── versions/               # Schema version history
├── docs/                       # Project Documentation
│   ├── PERMISSIONS.md          # Role-Based Access Control matrix
│   ├── KNOWN_GAPS.md           # Operational boundaries & technical gaps
│   ├── implementation_plan.md
│   ├── map_instructions.md
│   ├── walkthrough.md
│   └── pitch_deck_content.md
├── frontend/                   # React + Vite Dashboard
└── tests/                      # Automated Test Suite
```

---

## 7. Environment Variables & Configuration

Configure via `.env` (refer to `.env.example`):

| Variable | Description | Default / Example |
|---|---|---|
| `ENVIRONMENT` | Environment mode (`development` or `production`) | `development` |
| `JWT_SECRET` | Secret key for JWT tokens (min 32 characters in production) | Auto-generated in dev |
| `RAILOPT_SECRET` | Backward-compatible alias for `JWT_SECRET` | — |
| `DATABASE_URL` | PostgreSQL connection string with SSL required | Falls back to SQLite |
| `CORS_ORIGINS` | Comma-separated allowed origins | `http://localhost:5173,http://localhost:3000` |
| `RAILRADAR_API_KEYS` | Comma-separated list of RailRadar API keys | `""` |
| `RAILRADAR_BASE_URL` | RailRadar base endpoint | `https://api.railradar.in/v1` |
| `RAILRADAR_OFFLINE` | `1` to disable network calls and use snapshots | `0` |
| `RAILRADAR_KEY_LIMIT` | Safe monthly request cap per key | `90` |
| `NVIDIA_API_KEY` | NVIDIA NIM / OpenAI-compatible API key for LLM | — |
| `GEMINI_API_KEY` | Optional fallback key for Gemini | — |
| `TRUST_PROXY` | Set to `1` behind reverse proxies (Render, Nginx) to extract client IP from `X-Forwarded-For` for rate limiting | `0` |

### Deployment on Render

1. Create a **Web Service** connected to this repository.
2. In the **Environment** tab, set:
   - `ENVIRONMENT`: `production` (required)
   - `JWT_SECRET`: A secure 32+ character random string (required in production)
   - `TRUST_PROXY`: `1` (ensures accurate client IP rate limiting behind Render's reverse proxy)
   - `DATABASE_URL`: Your Neon PostgreSQL connection string (`postgresql+psycopg://...sslmode=require`)
   - `CORS_ORIGINS`: Your frontend URL
   - `RAILRADAR_API_KEYS`: Comma-separated API keys
   - `RAILRADAR_OFFLINE`: `0`
   - `RAILRADAR_KEY_LIMIT`: `90`
   - `NVIDIA_API_KEY`: Your LLM API key
3. Build Command: `pip install -r requirements.txt && alembic upgrade head`
4. Start Command: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`

---

## 8. Role-Based Access Control

Orion enforces strict authorization across 4 roles:
- **`ADMIN`**: User management, demo dataset generation, system config.
- **`CONTROLLER`**: Block plan generation, approval, rejection, and simulation across all departments.
- **`DEPT_USER`**: Maintenance task creation and updates restricted exclusively to their assigned department (`ENGINEERING`, `SNT`, `TRD`).
- **`VIEWER`**: Read-only dashboard access.

Full details are documented in [docs/PERMISSIONS.md](docs/PERMISSIONS.md).

---

## 9. License

Built for Smart India Hackathon 2026 — Ministry of Railways.
