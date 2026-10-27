# RailOpt — AI-Powered Automatic Block Planning for Indian Railways

**Transforming decentralized, manual maintenance block planning into a data-driven, coordinated process that maximizes asset availability, improves safety, and supports reliable train operations.**

## Problem

Indian Railways maintenance across Engineering (track), S&T (signals), and TRD (traction/OHE) is planned independently. Each department requests blocks via BDMS without cross-department coordination. This leads to:
- **Inefficient block utilization** — departments take separate closures on the same corridor
- **No comparable urgency scale** — a "P1" track defect and a "P1" signal defect are scored differently
- **Block overruns** — unreliable duration estimates cause cascading delays
- **Suboptimal scheduling** — blocks during peak traffic when off-peak windows exist

## Solution

RailOpt integrates maintenance data from TMS, SMMS, and TDMS with corridor availability from COA to generate optimized, merged, multi-department block schedules.

### Core ML Engine
- **Criticality Scorer** (XGBoost) — produces cross-department comparable urgency scores (0-100)
- **Traffic Impact Predictor** (LightGBM) — predicts how disruptive each block window is
- **Duration Estimator** (Random Forest) — predicts realistic task duration with confidence intervals
- **Defect Text Classifier** (Gemini/NLP) — extracts structured severity from inspector free-text notes

### CP-SAT Block Scheduler
- Google OR-Tools constraint optimization assigns tasks to windows
- **Block merging** — combines multi-department work into shared blocks, saving hours of track closure
- **SLA enforcement** — emergency tasks force-scheduled, overdue tasks auto-escalated

### Multi-Agent Negotiation
- Engineering, S&T, and TRD department agents propose and negotiate block requests
- Arbitrator agent resolves conflicts via merge, priority override, or rescheduling
- Emergency re-planning agent handles mid-week urgent defects
- Early warning agent detects trending failure risks

### GenAI Layer
- Natural-language plan briefings for control rooms
- Query interface: "Why was defect #4521 pushed to next month?"
- SHAP-based explainability for every ML decision

## Architecture

```
Data Integration → ML Scoring/Prediction → CP-SAT Optimizer (+ Multi-Agent Negotiation)
                                                    ↓
                              GenAI Briefing / NL Query / Explainability
                                                    ↓
                                    FastAPI Backend → React Dashboard
```

## Quick Start

### Backend
```bash
# Install dependencies
pip install -r requirements.txt

# Start the server
uvicorn backend.main:app --reload --port 8000

# Setup demo data (in another terminal or via API)
curl -X POST http://localhost:8000/api/demo/setup
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Run Tests
```bash
pytest tests/ -v
```

## Project Structure

```
RailOpt/
├── railopt/                    # Core domain
│   ├── models.py               # Pydantic domain models
│   ├── synthetic_data.py       # Synthetic data generator
│   ├── data_integration.py     # TMS/SMMS/TDMS adapters
│   ├── sim_entities.py         # Train simulation entities
│   └── sim_state_machine.py    # Train state transitions
├── ml/                         # ML Engine
│   ├── criticality_scorer.py   # XGBoost risk scorer
│   ├── impact_predictor.py     # LightGBM impact model
│   ├── duration_estimator.py   # Random Forest duration
│   ├── defect_text_classifier.py # NLP severity extractor
│   ├── feature_engineering.py  # Feature pipeline
│   └── training_pipeline.py    # Training orchestration
├── optimizer/                  # Block Scheduling
│   ├── cpsat_solver.py         # CP-SAT optimizer
│   ├── block_merger.py         # Multi-dept merging
│   └── sla_engine.py           # SLA enforcement
├── agents/                     # Multi-Agent System
│   ├── department_agent.py     # Dept agents (Eng/S&T/TRD)
│   ├── arbitrator_agent.py     # Conflict resolver
│   ├── replanning_agent.py     # Emergency re-planner
│   ├── early_warning_agent.py  # Risk monitor
│   └── agent_orchestrator.py   # Workflow orchestrator
├── genai/                      # GenAI Layer
│   ├── briefing_generator.py   # NL plan briefings
│   ├── nl_query_engine.py      # NL query interface
│   └── explainability.py       # SHAP explanations
├── simulator/                  # What-If Engine
│   └── block_impact_simulator.py
├── backend/                    # FastAPI Backend
│   ├── main.py                 # API endpoints
│   ├── database.py             # SQLite persistence
│   └── schemas.py              # Request/response schemas
├── frontend/                   # React Dashboard
│   └── src/
├── tests/                      # Test suite
└── requirements.txt
```

## Key Differentiators

1. **Cross-department comparable urgency scoring** — ML produces one number that ranks track defects against signal faults against OHE damage
2. **Block merging** — the single biggest efficiency gain: when 3 departments need the same corridor, one shared block instead of 3 separate closures
3. **Multi-agent negotiation** — models the real-world coordination problem between departments as explicit agent interaction
4. **Explainability** — every score and every scheduling decision can be explained to the engineer who needs to trust it
5. **Proactive risk management** — early warning agent shifts from reactive to predictive maintenance scheduling

## Tech Stack

| Component | Technology |
|---|---|
| ML Models | XGBoost, LightGBM, scikit-learn, SHAP |
| Optimizer | Google OR-Tools CP-SAT |
| GenAI | Google Gemini API |
| Backend | FastAPI, SQLAlchemy, SQLite |
| Frontend | React, Vite, Tailwind CSS, Recharts |
| NLP | google-genai, regex fallback |

## License

Built for Smart India Hackathon 2026 — Ministry of Railways.
