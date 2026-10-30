"""
RailOpt — FastAPI backend.

Provides REST endpoints for the React dashboard: task management,
plan generation (ML scoring → CP-SAT optimization → merge analysis),
NL briefings, what-if simulation, and a one-click demo setup.
"""

from __future__ import annotations

from dotenv import load_dotenv
load_dotenv()

from contextlib import asynccontextmanager
import logging
import os
from datetime import date, datetime, timedelta
import json
from pathlib import Path
from typing import List, Optional
import zoneinfo

from fastapi import FastAPI, HTTPException, Depends, Request, WebSocket, WebSocketDisconnect, Query, status
from fastapi.middleware.cors import CORSMiddleware

from backend.database import (
    get_engine,
    get_session,
    init_db,
    check_connection_with_retry,
    load_all_plans,
    load_alerts,
    load_corridors,
    load_tasks,
    save_alert,
    save_corridors,
    save_plan,
    save_tasks,
    save_live_status,
    load_live_status,
    save_block_response,
    load_block_responses,
    get_user_by_id,
    get_user_notifications,
    get_unread_notification_count,
    mark_notification_read,
    acknowledge_notification,
    TaskRecord,
    BlockPlanRecord,
    CorridorRecord,
    NotificationRecord,
)
# Data
from railopt.synthetic_data import generate_full_dataset
from ml.feedback_logger import FeedbackLogger
from ml.defect_text_classifier import DefectTextClassifier
from railopt.data_integration import DataIntegrationService
from pydantic import BaseModel
from backend.notifications import manager, dispatch_issue_alert
from agents import AgentOrchestrator, EarlyWarningAgent, ReplanningAgent

from backend.auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    authenticate_user,
    get_client_ip,
    hash_password,
    get_current_user,
    require_admin,
    require_controller,
    require_dept_or_above,
    require_viewer_or_above,
    can_access_task,
)
from backend.schemas import (
    DashboardStats,
    GeneratePlanRequest,
    GeneratePlanResponse,
    ImportTasksRequest,
    ImportTasksResponse,
    LoginRequest,
    LoginResponse,
    RefreshTokenRequest,
    CreateUserRequest,
    UpdateUserRequest,
    ResetPasswordRequest,
    User,
    QueryRequest,
    QueryResponse,
    ReplanRequest,
    SimulateResponse,
    PlanApproveRequest,
    PlanRejectRequest,
    PlanModifyRequest,
    TimetableImportRequest,
    TimetableImportResponse,
    NotificationResponse,
    UnreadCountResponse,
    AgentNegotiationRequest,
    AgentNegotiationResponse,
    AgentStatusResponse,
)
from railopt.models import (
    AssetType,
    BlockDecision,
    BlockRejectReason,
    BlockResponse,
    BlockWindow,
    Corridor,
    DefectCategory,
    DefectSeverity,
    EarlyWarning,
    MaintenanceTask,
    PlanHorizon,
    PlanStatus,
    Section,
    TaskStatus,
    UserRole,
    Department,
)

# ML
from ml.criticality_scorer import CriticalityScorer
from ml.impact_predictor import TrafficImpactPredictor
from ml.duration_estimator import DurationEstimator
from ml.feature_engineering import TaskFeatureExtractor, BlockWindowFeatureExtractor
from ml.training_pipeline import TrainingPipeline

# Optimizer
from optimizer.cpsat_solver import BlockScheduler, SchedulerConfig
from optimizer.block_merger import BlockMerger
from optimizer.sla_engine import SLAEngine

# GenAI
from genai.briefing_generator import BriefingGenerator
from genai.nl_query_engine import NLQueryEngine
from genai.explainability import ExplainabilityEngine

# Simulator
from simulator.block_impact_simulator import BlockImpactSimulator

# NEW Analysis Engines (FinCrime-beating layers)
from railopt.context_engine import ContextEngine
from railopt.compliance_engine import ComplianceEngine
from railopt.behavioral_analyzer import BehavioralAnalyzer
from railopt.signal_extractor import extract_signals_batch
from railopt.risk_blender import RiskBlender
from railopt.adversarial_validator import BlockDisruptor, ATTACK_TYPES

import sys
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
ch = logging.StreamHandler(sys.stdout)
ch.setFormatter(logging.Formatter('%(levelname)s:%(name)s:%(message)s'))
logger.addHandler(ch)

# ──────────────────────────────────────────────────────────────────────
# App setup
# ──────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    on_startup()
    yield


app = FastAPI(title="RailOpt API", version="1.0.0", lifespan=lifespan)

import time

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = (time.time() - start_time) * 1000
    # Note: Log only request.url.path to prevent sensitive query params (e.g. ?token=...)
    # from being exposed in access logs.
    client_host = request.client.host if request.client else "127.0.0.1"
    logger.info("%s - \"%s %s\" %d (%.1fms)", client_host, request.method, request.url.path, response.status_code, process_time)
    return response

DEFAULT_CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://orion-two-rho.vercel.app",
]

def get_cors_origins() -> list[str]:
    origins_env = os.environ.get("CORS_ORIGINS", "").strip()
    if origins_env:
        return [o.strip() for o in origins_env.split(",") if o.strip()]
    return DEFAULT_CORS_ORIGINS

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = get_engine()


def on_startup():
    # Initialize basic state defaults so app never fails with AttributeError
    app.state.tasks = []
    app.state.corridors = []
    app.state.sections = {}
    app.state.windows = []
    app.state.train_slots = []
    app.state.plans = {}
    app.state.alerts = []
    app.state.load_failures = {
        "tasks": 0,
        "corridors": 0,
        "alerts": 0,
    }
    app.state.database_ok = True
    app.state.models_loaded = False

    # Check connection if using PostgreSQL
    if hasattr(engine, "url") and engine.url.drivername.startswith("postgresql"):
        try:
            check_connection_with_retry(engine)
        except Exception as e:
            logger.error("PostgreSQL database connection failed on startup: %s. Running in degraded mode.", e)
            app.state.database_ok = False

    if app.state.database_ok:
        try:
            init_db(engine)
            session = get_session(engine)
            try:
                tasks_data, tasks_failed = load_tasks(session)
                app.state.tasks = tasks_data
                corridors_data, corridors_failed = load_corridors(session)
                app.state.corridors = corridors_data
                for corridor in corridors_data:
                    if hasattr(corridor, 'sections') and corridor.sections:
                        for section in corridor.sections:
                            app.state.sections[section.section_id] = section
                logger.info(f"Loaded {len(app.state.sections)} sections from {len(corridors_data)} corridors")
                app.state.plans = {p.plan_id: p for p in load_all_plans(session)}
                app.state.alerts = load_alerts(session)
                app.state.load_failures = {
                    "tasks": tasks_failed,
                    "corridors": corridors_failed,
                    "alerts": 0,
                }

                # Auto-seed synthetic data on brand-new empty production databases
                if not app.state.corridors or not app.state.tasks:
                    try:
                        logger.info("Empty database detected on startup. Auto-seeding initial synthetic dataset...")
                        from railopt.synthetic_data import generate_full_dataset
                        dataset = generate_full_dataset(seed=42, num_tasks=150, window_days=30)
                        if not app.state.tasks:
                            app.state.tasks = dataset["tasks"]
                            save_tasks(session, dataset["tasks"])
                        if not app.state.corridors:
                            app.state.corridors = dataset["corridors"]
                            save_corridors(session, dataset["corridors"])
                        for corridor in app.state.corridors:
                            if hasattr(corridor, 'sections') and corridor.sections:
                                for section in corridor.sections:
                                    app.state.sections[section.section_id] = section
                        app.state.windows = dataset.get("block_windows", [])
                        app.state.train_slots = dataset.get("train_slots", [])
                        logger.info("Auto-seeded %d synthetic tasks and %d corridors to database.", len(app.state.tasks), len(app.state.corridors))
                    except Exception as e:
                        logger.warning("Failed to auto-seed initial synthetic dataset: %s", e)
            finally:
                session.close()
        except Exception as e:
            logger.error("Error initializing/loading database data: %s", e)
            app.state.database_ok = False

    # ML models — loaded if trained, else None until /api/demo/setup or scripts/train_models.py
    app.state.scorer = None
    app.state.impact_predictor = None
    app.state.duration_estimator = None

    models_ok = True
    scorer_path = "ml/models/criticality_scorer.pkl"
    if os.path.exists(scorer_path):
        try:
            scorer = CriticalityScorer()
            scorer.load(scorer_path)
            app.state.scorer = scorer
            logger.info("Loaded trained criticality scorer")
        except Exception as e:
            models_ok = False
            logger.warning("Failed to load criticality scorer: %s", e)
    else:
        models_ok = False
        logger.warning("No trained criticality scorer found at %s", scorer_path)

    predictor_path = "ml/models/impact_predictor.pkl"
    if os.path.exists(predictor_path):
        try:
            predictor = TrafficImpactPredictor()
            predictor.load(predictor_path)
            app.state.impact_predictor = predictor
            logger.info("Loaded trained impact predictor")
        except Exception as e:
            models_ok = False
            logger.warning("Failed to load impact predictor: %s", e)
    else:
        models_ok = False
        logger.warning("No trained impact predictor found at %s", predictor_path)

    duration_path = "ml/models/duration_estimator.pkl"
    if os.path.exists(duration_path):
        try:
            duration_estimator = DurationEstimator()
            duration_estimator.load(duration_path)
            app.state.duration_estimator = duration_estimator
            logger.info("Loaded trained duration estimator")
        except Exception as e:
            models_ok = False
            logger.warning("Failed to load duration estimator: %s", e)
    else:
        models_ok = False
        logger.warning("No trained duration estimator found at %s", duration_path)

    app.state.models_loaded = models_ok

    app.state.briefing_gen = BriefingGenerator(use_llm=True)
    app.state.explainer = ExplainabilityEngine(use_llm=True)
    app.state.feedback_logger = FeedbackLogger()
    app.state.text_classifier = DefectTextClassifier(use_llm=True)
    app.state.data_integration = DataIntegrationService()


# ──────────────────────────────────────────────────────────────────────
# Auth & User Management (Role-Based Access Control)
# ──────────────────────────────────────────────────────────────────────

@app.post("/api/auth/login", response_model=LoginResponse)
def login(request: LoginRequest, http_req: Request):
    client_ip = get_client_ip(http_req)
    user_record, error = authenticate_user(request.email, request.password, client_ip=client_ip)
    
    if error:
        status_code = 429 if "locked" in error else 401
        raise HTTPException(status_code=status_code, detail=error)

    access_token = create_access_token(user_record)
    refresh_token = create_refresh_token(user_record)

    user_schema = User(
        id=user_record.id,
        email=user_record.email,
        role=UserRole(user_record.role),
        department=Department(user_record.department) if user_record.department else None,
        name=user_record.name,
        is_active=user_record.is_active,
    )

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        user=user_schema,
    )


@app.post("/api/auth/refresh")
def refresh_token_endpoint(request: RefreshTokenRequest):
    try:
        payload = decode_token(request.refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type (refresh token required)")
        user_id = payload.get("sub")
        session = get_session(engine)
        try:
            from backend.database import get_user_by_id
            user = get_user_by_id(session, user_id)
            if not user or not user.is_active:
                raise HTTPException(status_code=401, detail="User account not found or disabled")
            new_access_token = create_access_token(user)
            return {"access_token": new_access_token, "token_type": "bearer"}
        finally:
            session.close()
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error processing refresh token request: %s", exc)
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")


@app.get("/api/auth/me", response_model=User)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@app.get("/api/auth/users", response_model=list[User])
def list_users(admin: User = Depends(require_admin)):
    """Admin-only: list all system users."""
    session = get_session(engine)
    try:
        from backend.database import UserRecord
        records = session.query(UserRecord).all()
        return [
            User(
                id=u.id,
                email=u.email,
                role=UserRole(u.role),
                department=Department(u.department) if u.department else None,
                name=u.name,
                is_active=u.is_active,
            )
            for u in records
        ]
    finally:
        session.close()


@app.post("/api/auth/users", response_model=User)
def create_user(request: CreateUserRequest, admin: User = Depends(require_admin)):
    """Admin-only: create a new user. DEPT_USER must have a department."""
    if request.role == UserRole.DEPT_USER and not request.department:
        raise HTTPException(status_code=400, detail="DEPT_USER must specify a department (ENGINEERING, SNT, or TRD)")

    clean_email = request.email.strip().lower()
    session = get_session(engine)
    try:
        from backend.database import get_user_by_email, UserRecord
        import uuid
        existing = get_user_by_email(session, clean_email)
        if existing:
            raise HTTPException(status_code=400, detail=f"User with email '{clean_email}' already exists")

        new_user = UserRecord(
            id=f"usr_{uuid.uuid4().hex[:12]}",
            name=request.name.strip(),
            email=clean_email,
            password_hash=hash_password(request.password),
            role=request.role.value,
            department=request.department.value if request.department else None,
            is_active=True,
        )
        session.add(new_user)
        session.commit()
        return User(
            id=new_user.id,
            email=new_user.email,
            role=UserRole(new_user.role),
            department=Department(new_user.department) if new_user.department else None,
            name=new_user.name,
            is_active=new_user.is_active,
        )
    finally:
        session.close()


@app.patch("/api/auth/users/{user_id}", response_model=User)
def update_user(user_id: str, request: UpdateUserRequest, admin: User = Depends(require_admin)):
    """Admin-only: update user details, role, department or active status."""
    session = get_session(engine)
    try:
        from backend.database import get_user_by_id
        user = get_user_by_id(session, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if request.name is not None:
            user.name = request.name.strip()
        if request.role is not None:
            user.role = request.role.value
        if request.department is not None:
            user.department = request.department.value
        if request.is_active is not None:
            user.is_active = request.is_active

        if user.role == UserRole.DEPT_USER.value and not user.department:
            raise HTTPException(status_code=400, detail="DEPT_USER must have a department")

        session.commit()
        return User(
            id=user.id,
            email=user.email,
            role=UserRole(user.role),
            department=Department(user.department) if user.department else None,
            name=user.name,
            is_active=user.is_active,
        )
    finally:
        session.close()


@app.post("/api/auth/users/{user_id}/reset-password")
def reset_user_password(user_id: str, request: ResetPasswordRequest, admin: User = Depends(require_admin)):
    """Admin-only: reset user password."""
    if len(request.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters long")
    session = get_session(engine)
    try:
        from backend.database import get_user_by_id
        user = get_user_by_id(session, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        user.password_hash = hash_password(request.new_password)
        session.commit()
        return {"status": "ok", "message": f"Password reset successfully for user {user.email}"}
    finally:
        session.close()


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────

def _batch_score_tasks(tasks: list[MaintenanceTask]) -> None:
    """Score all tasks using the trained ML criticality scorer (batch)."""
    if not app.state.scorer or not tasks:
        return
    extractor = TaskFeatureExtractor()
    X = extractor.transform(tasks, app.state.sections)
    classes, scores = app.state.scorer.predict(X, tasks)
    shap_vals = app.state.scorer.explain(X)
    for i, t in enumerate(tasks):
        t.ml_criticality_score = float(scores[i])
        t.ml_predicted_severity = DefectSeverity(classes[i])
        t.ml_shap_values = shap_vals[i]


def _batch_score_windows(windows: list[BlockWindow]) -> None:
    """Score all windows using the trained impact predictor (batch)."""
    if not app.state.impact_predictor or not windows:
        return
    extractor = BlockWindowFeatureExtractor()
    X = extractor.transform(windows, app.state.sections, train_slots=app.state.train_slots)
    preds = app.state.impact_predictor.predict(X)
    for i, w in enumerate(windows):
        if hasattr(preds, "iloc"):
            row = preds.iloc[i]
            w.ml_traffic_impact_score = float(row.get("traffic_impact_score", 0))
            w.ml_trains_affected = int(row.get("trains_affected", 0))
            w.ml_cumulative_delay_minutes = float(row.get("cumulative_delay_minutes", 0))
        else:
            w.ml_traffic_impact_score = float(preds[i][0]) if len(preds[i]) > 0 else 0
            w.ml_trains_affected = int(preds[i][1]) if len(preds[i]) > 1 else 0
            w.ml_cumulative_delay_minutes = float(preds[i][2]) if len(preds[i]) > 2 else 0


def _batch_score_durations(tasks: list[MaintenanceTask]) -> None:
    """
    Score all tasks using the trained duration estimator (batch).

    BUG FIX: this was previously never called anywhere in the API.
    ml_predicted_duration_hours stayed at the MaintenanceTask default of
    0.0 for every task, so the solver's duration/capacity constraints were
    silently working off whatever estimated_duration_hours a source system
    or synthetic generator happened to set, and the DurationEstimator model
    trained in /api/demo/setup was never actually used downstream.
    """
    if not app.state.duration_estimator or not tasks:
        return
    extractor = TaskFeatureExtractor()
    X = extractor.transform(tasks, app.state.sections)
    preds = app.state.duration_estimator.predict(X)
    for i, t in enumerate(tasks):
        if hasattr(preds, "iloc"):
            row = preds.iloc[i]
            t.ml_predicted_duration_hours = float(row["duration_hours"])
            if "p25" in preds.columns:
                t.ml_duration_confidence_lower = float(row["p25"])
            if "p75" in preds.columns:
                t.ml_duration_confidence_upper = float(row["p75"])
        else:
            t.ml_predicted_duration_hours = float(preds[i][0]) if len(preds[i]) > 0 else 0.0


def _locked_window_ids(plans: dict) -> set[str]:
    """
    Window IDs already consumed by an APPROVED plan.

    BUG FIX (item 4, part B): a plan is only truly committed once a human
    approves it. Before this fix, generating a new plan handed the solver
    every window regardless of whether an earlier, already-approved plan
    had booked it — so two approved plans could both claim the same
    maintenance window on the same section/date.
    """
    return {
        block.window_id
        for plan in plans.values()
        if plan.status == PlanStatus.APPROVED
        for block in plan.scheduled_blocks
    }


def _reset_unlocked_tasks_for_regeneration(
    tasks: list[MaintenanceTask], plans: dict
) -> None:
    """
    Reset every task back to PENDING unless it is locked in by an APPROVED
    plan, so a fresh "Generate Plan" call has a clean slate to work from.

    BUG FIX (item 4, part A): previously, tasks left SCHEDULED by a
    DRAFT/REJECTED/MODIFIED plan (a plan nobody approved — it doesn't
    actually hold its window) and tasks DEFERRED by any prior solve just
    accumulated forever. /api/plans/generate only ever looked at PENDING or
    ESCALATED tasks, so after one solve there could be zero eligible tasks
    left and the endpoint would 400 on the very next call. This also fed
    the "chronic neglect" behavioral signal falsely, since deferred_count
    kept climbing on tasks that were never really deferred by a human
    decision — just by an earlier, non-committed draft plan.

    Tasks locked in by an APPROVED plan are left untouched: that plan's
    schedule is a real commitment and must not be re-offered to the solver.
    """
    approved_task_ids = {
        tid
        for plan in plans.values()
        if plan.status == PlanStatus.APPROVED
        for block in plan.scheduled_blocks
        for tid in block.task_ids
    }
    for t in tasks:
        if (
            t.status in (TaskStatus.SCHEDULED, TaskStatus.DEFERRED)
            and t.task_id not in approved_task_ids
        ):
            t.status = TaskStatus.PENDING
            t.assigned_block_id = None
            # deferred_count is a history counter, not scheduling state —
            # deliberately left alone here.


def _run_multi_layer_analysis(tasks: list[MaintenanceTask]) -> dict:
    """
    Run the full 5-layer analysis pipeline on tasks:
      Layer 1: ML Criticality Score (already done by _batch_score_tasks)
      Layer 2: Context Engine
      Layer 3: Compliance Engine
      Layer 4: Behavioral Analyzer
      Layer 5: Signal Extractor
      → Risk Blender fuses all layers into blended_score

    Returns a dict with per-task analysis results for API consumption.
    """
    # BUG FIX: an empty task list (e.g. /api/replan called when every task
    # is already SCHEDULED/DEFERRED and the new task's status wasn't PENDING)
    # used to hit a ZeroDivisionError on the logging line below and 500 the
    # whole endpoint. Handle it as a real, empty-but-valid case instead.
    if not tasks:
        logger.info("Multi-layer analysis: no eligible tasks, skipping.")
        return {"contexts": [], "compliances": [], "behaviors": [], "signals": [], "blended_results": []}

    sections = app.state.sections
    corridors = app.state.corridors

    # Layer 2: Context Engine
    context_engine = ContextEngine()
    contexts = context_engine.analyze_batch(tasks, sections, corridors)

    # Layer 3: Compliance Engine
    compliance_engine = ComplianceEngine()
    compliances = compliance_engine.assess_batch(tasks, contexts)

    # Layer 4: Behavioral Analyzer
    behavioral = BehavioralAnalyzer()
    behaviors = behavioral.analyze_batch(tasks, sections)

    # Layer 5: Signal Extractor
    signals = extract_signals_batch(tasks, sections)

    # Risk Blender — fuse all 5 layers
    blender = RiskBlender()
    blended_results = blender.blend_batch(tasks, contexts, compliances, behaviors, signals)

    # Apply blended scores back to tasks (overrides raw ML score).
    # RiskBlender.apply_to_tasks() re-applies the ALWAYS_EMERGENCY /
    # SAFETY_CRITICAL_DEFECTS safety floor after blending, so this no
    # longer silently downgrades emergencies to HIGH/MEDIUM.
    blender.apply_to_tasks(tasks, blended_results)

    logger.info(
        f"Multi-layer analysis complete: {len(tasks)} tasks analyzed across 5 layers. "
        f"Avg blended score: {sum(r.blended_score for r in blended_results) / len(blended_results):.1f}"
    )

    return {
        "contexts": contexts,
        "compliances": compliances,
        "behaviors": behaviors,
        "signals": signals,
        "blended_results": [
            {
                "task_id": r.task_id,
                "ml_score": r.ml_score,
                "context_score": r.context_score,
                "compliance_score": r.compliance_score,
                "behavior_score": r.behavior_score,
                "signal_score": r.signal_score,
                "blended_score": r.blended_score,
                "risk_level": r.risk_level,
                "action": r.action,
                "layer_contributions": r.layer_contributions,
                "evidence_summary": r.evidence_summary[:5],  # Top 5 evidence strings
            }
            for r in blended_results
        ],
    }


# ──────────────────────────────────────────────────────────────────────
# Health & Root
# ──────────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {
        "status": "ok",
        "name": "RailOpt API",
        "docs": "/docs",
        "health": "/api/health",
    }


@app.get("/api/health")
def health_check(verbose: bool = False):
    resp = {
        "status": "ok",
        "models_loaded": bool(getattr(app.state, "models_loaded", False)),
        "database_ok": bool(getattr(app.state, "database_ok", True)),
    }
    if verbose:
        meta_path = Path("ml/models/impact_predictor_meta.json")
        training_source = "transparent_delay_calculator"
        if meta_path.exists():
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                    training_source = meta.get("training_data_source", training_source)
            except Exception:
                pass
        resp["impact_model_training_source"] = training_source

        from traffic.passages import get_snapshots_provenance_report
        snap_rep = get_snapshots_provenance_report()
        resp["snapshot_provenance"] = snap_rep["overall_provenance"]
        resp["snapshot_provenance_label"] = snap_rep["ui_label"]
        resp["snapshot_average_age_days"] = snap_rep["average_age_days"]
        resp["snapshot_count"] = snap_rep["total_snapshots"]
    return resp


@app.get("/api/sources/snapshots")
def get_sources_snapshots():
    """Returns data provenance, snapshot age, and itemized illustrative values."""
    from traffic.passages import get_snapshots_provenance_report
    return get_snapshots_provenance_report()


# ──────────────────────────────────────────────────────────────────────
# Tasks & Complaints
# ──────────────────────────────────────────────────────────────────────

CATEGORY_DEPARTMENT_ASSET_MAP: dict[DefectCategory, tuple[Department, AssetType]] = {
    # Engineering
    DefectCategory.RAIL_FRACTURE: (Department.ENGINEERING, AssetType.RAIL),
    DefectCategory.RAIL_CRACK: (Department.ENGINEERING, AssetType.RAIL),
    DefectCategory.GAUGE_IRREGULARITY: (Department.ENGINEERING, AssetType.RAIL),
    DefectCategory.ALIGNMENT_DEFECT: (Department.ENGINEERING, AssetType.RAIL),
    DefectCategory.CROSS_LEVEL_DEFECT: (Department.ENGINEERING, AssetType.RAIL),
    DefectCategory.SLEEPER_DAMAGE: (Department.ENGINEERING, AssetType.SLEEPER),
    DefectCategory.BALLAST_DEFICIENCY: (Department.ENGINEERING, AssetType.BALLAST),
    DefectCategory.BRIDGE_CORROSION: (Department.ENGINEERING, AssetType.BRIDGE),
    DefectCategory.WELD_DEFECT: (Department.ENGINEERING, AssetType.WELD_JOINT),
    DefectCategory.FORMATION_FAILURE: (Department.ENGINEERING, AssetType.FORMATION),
    DefectCategory.LEVEL_CROSSING_DEFECT: (Department.ENGINEERING, AssetType.LEVEL_CROSSING),
    DefectCategory.WATERLOGGING: (Department.ENGINEERING, AssetType.TRACK_BED),
    DefectCategory.EMBANKMENT_SLIP: (Department.ENGINEERING, AssetType.FORMATION),
    # S&T
    DefectCategory.SIGNAL_FAILURE: (Department.SNT, AssetType.SIGNAL_POST),
    DefectCategory.RELAY_MALFUNCTION: (Department.SNT, AssetType.RELAY),
    DefectCategory.POINT_FAILURE: (Department.SNT, AssetType.POINT_MACHINE),
    DefectCategory.TRACK_CIRCUIT_FAILURE: (Department.SNT, AssetType.TRACK_CIRCUIT),
    DefectCategory.CABLE_DAMAGE: (Department.SNT, AssetType.TELECOM_CABLE),
    DefectCategory.INTERLOCKING_FAULT: (Department.SNT, AssetType.INTERLOCKING),
    DefectCategory.AXLE_COUNTER_ERROR: (Department.SNT, AssetType.AXLE_COUNTER),
    # TRD
    DefectCategory.OHE_SAG: (Department.TRD, AssetType.OHE_WIRE),
    DefectCategory.OHE_BREAK: (Department.TRD, AssetType.OHE_WIRE),
    DefectCategory.INSULATOR_DAMAGE: (Department.TRD, AssetType.INSULATOR),
    DefectCategory.MAST_TILT: (Department.TRD, AssetType.MAST),
    DefectCategory.TRANSFORMER_FAULT: (Department.TRD, AssetType.TRANSFORMER),
    DefectCategory.FEEDER_TRIP: (Department.TRD, AssetType.FEEDER),
    DefectCategory.PANTOGRAPH_SCRATCH: (Department.TRD, AssetType.PANTOGRAPH_ZONE),
}


@app.post("/api/tasks/import", response_model=ImportTasksResponse)
def import_tasks(
    request: ImportTasksRequest,
    current_user: User = Depends(require_dept_or_above),
):
    # RBAC: DEPT_USER can only import tasks for their own department
    if current_user.role == UserRole.DEPT_USER and current_user.department:
        for idx, rec in enumerate(request.records):
            rec_dept = rec.get("department")
            if rec_dept and rec_dept != current_user.department.value and rec_dept != current_user.department:
                raise HTTPException(
                    status_code=403,
                    detail=f"Row {idx}: Cannot import tasks for department '{rec_dept}'. You can only import tasks for '{current_user.department.value}'.",
                )

    new_tasks = []
    errors = []
    
    for idx, rec in enumerate(request.records):
        try:
            # Wire NLP classifier if needed
            if not rec.get("defect_category") and rec.get("inspector_remarks"):
                try:
                    result = app.state.text_classifier.classify(rec["inspector_remarks"])
                    rec["defect_category"] = result.get("defect_category")
                    if not rec.get("raw_severity"):
                        rec["raw_severity"] = result.get("severity")
                except Exception as e:
                    logger.warning(f"NLP classification failed for record {idx}: {e}")

            rec["source"] = "user"
            task = MaintenanceTask(**rec)
            task.source = "user"
            new_tasks.append(task)
        except Exception as e:
            errors.append(f"Row {idx}: {str(e)}")

    if new_tasks:
        _batch_score_tasks(new_tasks)
        _batch_score_durations(new_tasks)
        sla_engine = SLAEngine()
        sla_engine.apply_sla(new_tasks)
        
        app.state.tasks.extend(new_tasks)
        session = get_session(engine)
        save_tasks(session, new_tasks)
        session.close()

    return ImportTasksResponse(
        imported_count=len(new_tasks),
        failed_count=len(errors),
        errors=errors[:10],
        tasks=new_tasks,
    )


@app.get("/api/tasks", response_model=List[MaintenanceTask])
def list_tasks(
    department: Optional[str] = None,
    severity: Optional[str] = None,
    status: Optional[str] = None,
    corridor: Optional[str] = None,
    current_user: User = Depends(require_viewer_or_above),
):
    tasks = getattr(app.state, "tasks", [])
    if not tasks:
        session = get_session(engine)
        try:
            db_tasks, _ = load_tasks(session)
            if db_tasks:
                app.state.tasks = db_tasks
                tasks = db_tasks
        finally:
            session.close()
    
    # RBAC: DEPT_USER only gets tasks of their own department
    if current_user.role == UserRole.DEPT_USER and current_user.department:
        department = current_user.department.value

    if department:
        dept_target = department.strip().upper()
        if dept_target in ("S&T", "SNT", "SIGNALLING", "SIGNALING"):
            dept_targets = {"SNT", "S&T"}
        elif dept_target in ("ENG", "ENGINEERING", "CIVIL", "TRACK"):
            dept_targets = {"ENGINEERING", "ENG"}
        elif dept_target in ("TRD", "ELECTRICAL", "TRACTION"):
            dept_targets = {"TRD"}
        else:
            dept_targets = {dept_target}

        filtered = []
        for t in tasks:
            t_dept = getattr(t, "department", None)
            t_dept_str = (t_dept.value if hasattr(t_dept, "value") else str(t_dept or "")).upper()
            t_desig = (getattr(t, "department_designated", "") or "").upper()
            if t_dept_str in dept_targets or t_desig in dept_targets:
                filtered.append(t)
        tasks = filtered

    if severity:
        tasks = [t for t in tasks if t.ml_predicted_severity and (t.ml_predicted_severity.value == severity or t.ml_predicted_severity == severity)]
    if status:
        tasks = [t for t in tasks if t.status.value == status or t.status == status]
    if corridor:
        tasks = [t for t in tasks if t.corridor_id == corridor]
    return tasks


@app.get("/api/tasks/{task_id}")
def get_task(task_id: str, current_user: User = Depends(require_viewer_or_above)):
    for t in getattr(app.state, "tasks", []):
        if t.task_id == task_id:
            if not can_access_task(current_user, t):
                raise HTTPException(status_code=403, detail="Cannot view task for a different department")
            resp = t.model_dump()
            resp["duration_estimate"] = {
                "point_estimate": t.ml_predicted_duration_hours if t.ml_predicted_duration_hours else t.estimated_duration_hours,
                "confidence_lower": t.ml_duration_confidence_lower,
                "confidence_upper": t.ml_duration_confidence_upper,
                "source": "ML_MODEL" if t.ml_predicted_duration_hours else "MANUAL"
            }
            return resp

    session = get_session(engine)
    try:
        db_tasks, _ = load_tasks(session)
        for t in db_tasks:
            if t.task_id == task_id:
                if not hasattr(app.state, "tasks") or app.state.tasks is None:
                    app.state.tasks = []
                app.state.tasks.append(t)
                if not can_access_task(current_user, t):
                    raise HTTPException(status_code=403, detail="Cannot view task for a different department")
                resp = t.model_dump()
                resp["duration_estimate"] = {
                    "point_estimate": t.ml_predicted_duration_hours if t.ml_predicted_duration_hours else t.estimated_duration_hours,
                    "confidence_lower": t.ml_duration_confidence_lower,
                    "confidence_upper": t.ml_duration_confidence_upper,
                    "source": "ML_MODEL" if t.ml_predicted_duration_hours else "MANUAL"
                }
                return resp
    finally:
        session.close()

    raise HTTPException(status_code=404, detail="Task not found")


class TaskStatusUpdate(BaseModel):
    status: Optional[str] = None
    reason: Optional[str] = None
    reason_code: Optional[str] = None
    notes: Optional[str] = None
    outcome: Optional[str] = None
    actual_start: Optional[datetime] = None
    actual_end: Optional[datetime] = None


@app.put("/api/tasks/{task_id}/status")
async def update_task_status(
    task_id: str,
    request: Optional[TaskStatusUpdate] = None,
    status: Optional[str] = None,
    current_user: User = Depends(require_dept_or_above),
):
    target = None
    for t in getattr(app.state, "tasks", []):
        if t.task_id == task_id:
            target = t
            break

    session = get_session(engine)
    try:
        if target is None:
            db_tasks, _ = load_tasks(session)
            for t in db_tasks:
                if t.task_id == task_id:
                    target = t
                    if not hasattr(app.state, "tasks") or app.state.tasks is None:
                        app.state.tasks = []
                    app.state.tasks.append(t)
                    break

        if target is None:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

        if not can_access_task(current_user, target):
            raise HTTPException(status_code=403, detail="Cannot update task for different department")

        # Normalize status string and support common aliases
        raw_status = (request.status if request and request.status else status)
        if not raw_status:
            raise HTTPException(status_code=400, detail="Status must be provided in body or query param")

        status_input = raw_status.strip().upper()
        alias_map = {
            "ACKNOWLEDGED": "ESCALATED",
            "ACKNOWLEDGE": "ESCALATED",
            "DEPARTMENT NOTIFIED": "SCHEDULED",
            "NOTIFIED": "SCHEDULED",
            "ACTION STARTED": "SCHEDULED",
            "START ACTION": "IN_PROGRESS",
            "IN PROGRESS": "IN_PROGRESS",
            "IN_PROGRESS": "IN_PROGRESS",
            "RESOLVED": "COMPLETED",
            "DONE": "COMPLETED",
            "AUTHORIZED": "SCHEDULED",
            "AUTHORIZE": "SCHEDULED",
            "APPROVE": "SCHEDULED",
            "REJECT": "REJECTED",
        }
        status_val = alias_map.get(status_input, status_input)

        from railopt.task_transitions import transition_task
        try:
            target = transition_task(
                task=target,
                to_status=status_val,
                user=current_user,
                reason=getattr(request, "reason", None) or getattr(request, "notes", None),
                reason_code=getattr(request, "reason_code", None),
                notes=getattr(request, "notes", None),
                outcome=getattr(request, "outcome", None),
                actual_start=getattr(request, "actual_start", None),
                actual_end=getattr(request, "actual_end", None),
                session=session,
            )
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {raw_status}")

        save_tasks(session, [target])  # Upsert to DB

        # Broadcast real-time status update to all connected WebSocket clients across departments
        try:
            from backend.notifications import manager
            await manager.broadcast_to_all({
                "type": "TASK_UPDATED",
                "task_id": target.task_id,
                "status": target.status.value,
                "department": target.department.value if hasattr(target.department, "value") else str(target.department),
                "updated_by": current_user.email,
            })
        except Exception as ws_err:
            logger.warning("Failed to broadcast task update: %s", ws_err)

        return {"status": "ok", "new_status": target.status.value, "task_id": target.task_id}
    finally:
        session.close()


class ComplaintRequest(BaseModel):
    description: str
    corridor_id: str
    section_id: str
    km_location: float
    department_designated: Optional[str] = None
    severity: Optional[str] = None


@app.post("/api/tasks/complaint", response_model=MaintenanceTask)
@app.post("/api/issues", response_model=MaintenanceTask)
async def submit_complaint(
    request: ComplaintRequest,
    current_user: User = Depends(require_dept_or_above),
):
    import uuid
    from datetime import datetime, timezone
    
    classifier = DefectTextClassifier()
    # When department and severity are already provided by the operator, skip slow LLM calls for instant submission
    should_use_llm = not (request.department_designated and request.severity)
    classification = classifier.classify(request.description, use_llm=should_use_llm)

    # Validate category against DefectCategory enum
    raw_cat = classification.get("defect_category", "")
    try:
        category = DefectCategory(raw_cat)
    except ValueError:
        category = DefectCategory.GAUGE_IRREGULARITY

    # Validate severity against DefectSeverity enum
    if request.severity:
        try:
            severity = DefectSeverity(request.severity.strip().upper())
        except ValueError:
            severity = DefectSeverity.MEDIUM
    else:
        raw_sev = classification.get("severity", "")
        try:
            severity = DefectSeverity(raw_sev)
        except ValueError:
            severity = DefectSeverity.MEDIUM

    if request.department_designated:
        dept_input = request.department_designated.strip().upper()
        try:
            department = Department(dept_input)
            if department == Department.TRD:
                asset_type = AssetType.OHE_WIRE
            elif department == Department.SNT:
                asset_type = AssetType.POINT_MACHINE
            else:
                asset_type = AssetType.RAIL
        except ValueError:
            department, asset_type = CATEGORY_DEPARTMENT_ASSET_MAP.get(
                category, (Department.ENGINEERING, AssetType.RAIL)
            )
    else:
        department, asset_type = CATEGORY_DEPARTMENT_ASSET_MAP.get(
            category, (Department.ENGINEERING, AssetType.RAIL)
        )

    # When department_designated is NOT specified, DEPT_USER can only submit for their own department
    if not request.department_designated and current_user.role == UserRole.DEPT_USER and current_user.department:
        if department != current_user.department:
            raise HTTPException(
                status_code=403,
                detail=f"Cannot submit complaint for department {department.value} as user belongs to {current_user.department.value}",
            )

    now_utc = datetime.now(timezone.utc)
    task = MaintenanceTask(
        task_id=f"TSK-{uuid.uuid4().hex[:8].upper()}",
        source_system="USER_COMPLAINT",
        source_record_id="",
        department=department,
        asset_type=asset_type,
        asset_id="",
        defect_category=category,
        raw_severity=severity,
        corridor_id=request.corridor_id,
        section_id=request.section_id,
        km_location=request.km_location,
        estimated_duration_hours=2.0,
        inspector_remarks=request.description,
        status=TaskStatus.UNVERIFIED,
        reported_date=datetime.now().date(),
        ml_predicted_severity=None,
        ml_predicted_duration_hours=0.0,
        source="user",
        department_designated=department.value,
        created_by=current_user.email,
        created_by_department=current_user.department.value if current_user.department else None,
        created_at=now_utc,
    )
    
    if not hasattr(app.state, "tasks") or app.state.tasks is None:
        app.state.tasks = []
    app.state.tasks.append(task)
    session = get_session(engine)
    try:
        save_tasks(session, [task])
        # Dispatch real-time alert and persist notifications for offline users
        await dispatch_issue_alert(
            session=session,
            issue_id=task.task_id,
            title=f"New Issue Raised: {category.value}",
            message=f"Defect reported on {task.corridor_id} ({task.section_id}) at KM {task.km_location:.1f}. Severity: {severity.value}.",
            severity=severity.value,
            department_designated=department.value,
            creator_id=str(current_user.id) if hasattr(current_user, 'id') else None,
            creator_email=current_user.email,
        )
    finally:
        session.close()
    return task

# ──────────────────────────────────────────────────────────────────────
# RailRadar — Live Train Status
# ──────────────────────────────────────────────────────────────────────

@app.get("/api/trains/live/sync-preview")
def get_live_sync_preview(
    section_id: str = "SEC-93135bb9",
    current_user: User = Depends(require_controller),
):
    """
    Pre-flight confirmation preview for live RailRadar train delay sync:
    - How many calls this sync will make
    - Which trains it covers (only trains with a timetable snapshot on the pilot corridor)
    - Remaining monthly budget per key
    - Server-side minimum interval & cooldown status
    """
    from backend.sync_service import get_sync_preview
    from integrations.railradar_client import RailRadarClient

    client = getattr(getattr(app.state, "data_integration", None), "railradar_adapter", None)
    if client is None:
        client = RailRadarClient(db_engine=engine)

    session = get_session(engine)
    try:
        return get_sync_preview(session, client, section_id=section_id)
    finally:
        session.close()


@app.get("/api/trains/live/budget")
def get_live_trains_budget(
    current_user: User = Depends(require_viewer_or_above),
):
    """Returns monthly API budget breakdown (used/limit per key) and safety reserve."""
    from backend.sync_service import get_api_budget_breakdown
    from integrations.railradar_client import RailRadarClient

    client = getattr(getattr(app.state, "data_integration", None), "railradar_adapter", None)
    if client is None:
        client = RailRadarClient(db_engine=engine)

    session = get_session(engine)
    try:
        return get_api_budget_breakdown(session, client)
    finally:
        session.close()


@app.post("/api/trains/live/sync")
def sync_live_trains(
    section_id: str = "SEC-93135bb9",
    force: bool = False,
    current_user: User = Depends(require_controller),
):
    """
    Syncs live delays into LiveTrainStatus for pilot corridor timetable trains.
    Enforces minimum interval (default 60m) and reserved budget (default 30 calls) returning 429 when blocked.
    Returns trains updated, calls used, last synced time (IST), and any failures.
    """
    from backend.sync_service import execute_live_train_sync
    from integrations.railradar_client import RailRadarClient

    client = getattr(getattr(app.state, "data_integration", None), "railradar_adapter", None)
    if client is None:
        client = RailRadarClient(db_engine=engine)

    session = get_session(engine)
    try:
        return execute_live_train_sync(session, client, section_id=section_id, force=force)
    finally:
        session.close()

@app.get("/api/trains/live")
def get_live_trains(current_user: User = Depends(require_viewer_or_above)):
    session = get_session(engine)
    statuses = load_live_status(session)
    session.close()
    return statuses

# ──────────────────────────────────────────────────────────────────────
# Timetable Integration (Add 1)
# ──────────────────────────────────────────────────────────────────────

@app.post("/api/timetable/import", response_model=TimetableImportResponse)
def import_timetable(
    request: TimetableImportRequest,
    current_user: User = Depends(require_controller),
):
    """Wire COAAdapter to produce TrainSlot data from raw COA JSON."""
    try:
        slots = app.state.data_integration.coa_adapter.parse(request.records)
        app.state.train_slots.extend(slots)
        
        # Rescore windows with new slots
        _batch_score_windows(app.state.windows)
        
        return TimetableImportResponse(imported_count=len(slots))
    except Exception as e:
        logger.error(f"Timetable import failed: {e}")
        return TimetableImportResponse(imported_count=0, failed_count=len(request.records))


# ──────────────────────────────────────────────────────────────────────
# Plan generation (items #1, #2, #3, #5)
# ──────────────────────────────────────────────────────────────────────

def _get_app_today() -> date:
    """Return timezone-aware today date based on APP_TIMEZONE (default Asia/Kolkata)."""
    tz_name = os.environ.get("APP_TIMEZONE", "Asia/Kolkata")
    try:
        tz = zoneinfo.ZoneInfo(tz_name)
    except Exception:
        tz = zoneinfo.ZoneInfo("Asia/Kolkata")
    return datetime.now(tz).date()


@app.post("/api/plans/generate", response_model=GeneratePlanResponse)
def generate_plan(
    request: GeneratePlanRequest,
    current_user: User = Depends(require_controller),
):
    # BUG FIX (item 4): regenerate from a clean slate. Reset every task not
    # locked in by an APPROVED plan back to PENDING (see docstring on
    # _reset_unlocked_tasks_for_regeneration), and never re-offer a window
    # an APPROVED plan already committed to (see _locked_window_ids).
    # This must run before the PENDING/ESCALATED filter below, or a second
    # "Generate Plan" click can still find zero eligible tasks.
    _reset_unlocked_tasks_for_regeneration(app.state.tasks, app.state.plans)
    locked_windows = _locked_window_ids(app.state.plans)

    # BUG FIX (demo data): start_date/end_date and the WEEKLY vs MONTHLY
    # horizon were previously ignored entirely — generate_plan used whatever
    # date range the underlying window pool happened to cover, so a
    # "monthly" plan was really a weekly plan with a different label. The
    # window pool from /api/demo/setup now spans 30 days (see
    # railopt/synthetic_data.py), and this actually filters it down to what
    # the request asked for.
    horizon_days = 7 if request.horizon == PlanHorizon.WEEKLY else 30
    range_start = request.start_date or _get_app_today()
    range_end = request.end_date or (range_start + timedelta(days=horizon_days))

    # Ensure window pool exists
    if not getattr(app.state, "windows", None):
        try:
            from railopt.synthetic_data import generate_full_dataset
            ds = generate_full_dataset(seed=42, num_tasks=150, window_days=30)
            app.state.windows = ds.get("block_windows", [])
            _batch_score_windows(app.state.windows)
        except Exception as e:
            logger.warning("Could not auto-generate block windows: %s", e)

    tasks = [t for t in app.state.tasks if t.status in (TaskStatus.PENDING, TaskStatus.ESCALATED)]
    if not tasks:
        # If tasks were exhausted, reset them so new plan can be generated
        _reset_unlocked_tasks_for_regeneration(app.state.tasks, app.state.plans)
        tasks = [t for t in app.state.tasks if t.status in (TaskStatus.PENDING, TaskStatus.ESCALATED)]

    # If still no tasks, ensure default tasks are loaded
    if not tasks and app.state.tasks:
        for t in app.state.tasks:
            t.status = TaskStatus.PENDING
        tasks = [t for t in app.state.tasks if t.status in (TaskStatus.PENDING, TaskStatus.ESCALATED)]

    windows = [
        w for w in app.state.windows
        if w.window_id not in locked_windows and range_start <= w.date <= range_end
    ]
    if not windows and app.state.windows:
        # If date filtering left 0 windows, fall back to any available unlocked windows
        windows = [w for w in app.state.windows if w.window_id not in locked_windows]

    if not tasks:
        raise HTTPException(status_code=400, detail="No pending tasks to schedule")
    if not windows:
        raise HTTPException(
            status_code=400,
            detail=(
                f"No block windows available for {range_start} to {range_end}. "
                f"Run /api/demo/setup first, or the requested date range may fall "
                f"outside the generated window pool."
            ),
        )

    # 1. ML scoring (Layer 1)
    _batch_score_tasks(tasks)
    _batch_score_durations(tasks)
    _batch_score_windows(windows)

    # 2. Multi-layer analysis (Layers 2-5 + blending)
    analysis = _run_multi_layer_analysis(tasks)

    # 3. SLA escalation
    sla = SLAEngine()
    sla.escalate_overdue(tasks)

    # 4. CP-SAT optimization — correct API: BlockScheduler(config=...), scheduler.solve(tasks, windows, sections)
    config = SchedulerConfig(time_limit_seconds=30)
    if request.scheduler_config:
        for k, v in request.scheduler_config.items():
            if hasattr(config, k):
                setattr(config, k, v)

    scheduler = BlockScheduler(config=config)
    # Fix 1 companion: Pass horizon
    plan = scheduler.solve(tasks, windows, app.state.sections, horizon=request.horizon)

    # Fix 3 companion: BlockMerger is now called INSIDE solve().
    # The following is just to generate the report data for the API response.
    merger = BlockMerger()
    merge_report = merger.analyze_merge_opportunities(plan, tasks)

    # 6. SLA compliance check
    sla_report = sla.check_compliance(tasks, plan)
    plan.sla_compliance_pct = sla_report.compliance_percentage

    # 7. Persist
    app.state.plans[plan.plan_id] = plan
    session = get_session(engine)
    save_plan(session, plan)
    session.close()

    # 8. Generate briefing
    briefing = app.state.briefing_gen.generate_weekly_briefing(plan, tasks)

    return GeneratePlanResponse(
        plan=plan,
        warnings=app.state.alerts,
        metrics={
            "sla_compliance_pct": plan.sla_compliance_pct,
            "total_tasks_scheduled": plan.total_tasks_scheduled,
            "total_tasks_deferred": plan.total_tasks_deferred,
            "total_merge_savings_hours": plan.total_merge_savings_hours,
            "total_trains_affected": plan.total_trains_affected,
            "solver_status": plan.solver_status,  # Add 7 companion
            "solve_time_ms": plan.solve_time_ms,  # Add 7 companion
            "merge_report": {
                "merged_blocks": merge_report.total_merged_blocks,
                "hours_saved": merge_report.total_hours_saved,
                "recommendations": merge_report.recommendations,
            },
            "multi_layer_analysis": analysis["blended_results"],
            "briefing": briefing,
        },
    )


@app.get("/api/plans")
def list_plans(current_user: User = Depends(require_viewer_or_above)):
    if not app.state.plans:
        try:
            session = get_session(engine)
            saved = load_all_plans(session)
            session.close()
            for p in saved:
                app.state.plans[p.plan_id] = p
        except Exception as e:
            logger.warning("Could not load plans from database: %s", e)

    return [
        {
            "plan_id": p.plan_id,
            "horizon": p.horizon.value,
            "status": p.status.value,
            "start_date": str(p.start_date),
            "end_date": str(p.end_date),
            "total_tasks_scheduled": p.total_tasks_scheduled,
            "total_tasks_deferred": p.total_tasks_deferred,
            "sla_compliance_pct": p.sla_compliance_pct,
            "total_merge_savings_hours": p.total_merge_savings_hours,
            "created_at": str(p.created_at),
        }
        for p in app.state.plans.values()
    ]


@app.get("/api/plans/{plan_id}")
def get_plan(plan_id: str, current_user: User = Depends(require_viewer_or_above)):
    if plan_id not in app.state.plans:
        raise HTTPException(status_code=404, detail="Plan not found")
    return app.state.plans[plan_id]


# ──────────────────────────────────────────────────────────────────────
# Plan Approval Workflow (Add 4)
# ──────────────────────────────────────────────────────────────────────

@app.post("/api/plans/{plan_id}/approve")
def approve_plan(
    plan_id: str,
    request: PlanApproveRequest,
    current_user: User = Depends(require_controller),
):
    if plan_id not in app.state.plans:
        raise HTTPException(status_code=404, detail="Plan not found")
    plan = app.state.plans[plan_id]
    plan.status = PlanStatus.APPROVED
    plan.approved_by = current_user.email
    app.state.feedback_logger.log_plan_status(plan_id, "APPROVED", current_user.email, request.comments)
    session = get_session(engine)
    save_plan(session, plan)
    session.close()
    return {"status": "ok", "plan_status": plan.status.value}


@app.post("/api/plans/{plan_id}/reject")
def reject_plan(
    plan_id: str,
    request: PlanRejectRequest,
    current_user: User = Depends(require_controller),
):
    if plan_id not in app.state.plans:
        raise HTTPException(status_code=404, detail="Plan not found")
    plan = app.state.plans[plan_id]
    plan.status = PlanStatus.REJECTED
    app.state.feedback_logger.log_plan_status(plan_id, "REJECTED", current_user.email, request.reason)
    session = get_session(engine)
    save_plan(session, plan)
    session.close()
    return {"status": "ok", "plan_status": plan.status.value}


@app.post("/api/plans/{plan_id}/modify")
def modify_plan(
    plan_id: str,
    request: PlanModifyRequest,
    current_user: User = Depends(require_controller),
):
    if plan_id not in app.state.plans:
        raise HTTPException(status_code=404, detail="Plan not found")
    plan = app.state.plans[plan_id]
    plan.status = PlanStatus.MODIFIED
    
    # Process task overrides
    for override in request.task_overrides:
        task_id = override.get("task_id")
        if task_id:
            app.state.feedback_logger.log_task_override(
                plan_id=plan_id,
                task_id=task_id,
                user=current_user.email,
                original_status="SCHEDULED", # Simplified for now
                new_status=override.get("new_status", "UNKNOWN"),
                reason=override.get("reason", "")
            )
            plan.override_log.append(override)

    session = get_session(engine)
    save_plan(session, plan)
    session.close()
    return {"status": "ok", "plan_status": plan.status.value, "overrides_processed": len(request.task_overrides)}


@app.get("/api/plans/{plan_id}/briefing")
def get_briefing(plan_id: str, current_user: User = Depends(require_viewer_or_above)):
    if plan_id not in app.state.plans:
        raise HTTPException(status_code=404, detail="Plan not found")
    plan = app.state.plans[plan_id]
    briefing = app.state.briefing_gen.generate_weekly_briefing(plan, app.state.tasks)
    return {"briefing": briefing}


class BlockRespondRequest(BaseModel):
    decision: BlockDecision
    reason: Optional[str] = None
    reason_code: Optional[BlockRejectReason] = None
    counter_window_id: Optional[str] = None
    controller_override: bool = False
    department: Optional[Department] = None


@app.get("/api/plans/{plan_id}/my-blocks")
def get_my_blocks(
    plan_id: str,
    department: Optional[Department] = None,
    current_user: User = Depends(get_current_user),
):
    """
    Returns blocks containing tasks of the user's department,
    with shared tasks from other departments in the same block visible for coordination.
    """
    if plan_id not in app.state.plans:
        raise HTTPException(status_code=404, detail="Plan not found")
    plan = app.state.plans[plan_id]

    target_dept = current_user.department
    if current_user.role in (UserRole.CONTROLLER, UserRole.ADMIN, UserRole.VIEWER):
        target_dept = department or None

    session = get_session(engine)
    try:
        all_responses = load_block_responses(session, plan_id)
    finally:
        session.close()

    resp_map = {}
    for r in all_responses:
        if r.block_id not in resp_map:
            resp_map[r.block_id] = {}
        resp_map[r.block_id][r.department.value] = r

    task_map = {t.task_id: t for t in app.state.tasks}
    blocks_out = []

    for b in plan.scheduled_blocks:
        block_tasks = [task_map[tid] for tid in b.task_ids if tid in task_map]
        depts_in_block = {t.department for t in block_tasks}

        # Filter: if target_dept is specified, block must contain at least one task of target_dept
        if target_dept and target_dept not in depts_in_block:
            continue

        my_dept_tasks = [t for t in block_tasks if target_dept is None or t.department == target_dept]
        other_dept_tasks = [t for t in block_tasks if target_dept is not None and t.department != target_dept]
        is_safety = any(t.is_safety_critical for t in block_tasks)

        my_resp = None
        if target_dept:
            my_resp = resp_map.get(b.block_id, {}).get(target_dept.value)

        blocks_out.append({
            "block_id": b.block_id,
            "window_id": b.window_id,
            "corridor_id": b.corridor_id,
            "section_id": b.section_id,
            "section_name": b.section_name,
            "date": b.date.isoformat(),
            "start_time": b.start_time.strftime("%H:%M"),
            "end_time": b.end_time.strftime("%H:%M"),
            "duration_hours": b.duration_hours,
            "block_type": b.block_type.value,
            "is_merged": b.is_merged,
            "participating_departments": [d.value for d in b.departments],
            "trains_affected": b.trains_affected,
            "cumulative_delay_minutes": b.cumulative_delay_minutes,
            "is_safety_critical": is_safety,
            "my_tasks": [t.model_dump(mode="json") for t in my_dept_tasks],
            "shared_tasks": [
                {
                    "task_id": t.task_id,
                    "department": t.department.value,
                    "asset_type": t.asset_type.value,
                    "defect_category": t.defect_category.value,
                    "is_safety_critical": t.is_safety_critical,
                    "estimated_duration_hours": t.estimated_duration_hours,
                }
                for t in other_dept_tasks
            ],
            "my_response": my_resp.model_dump(mode="json") if my_resp else None,
            "all_responses": [r.model_dump(mode="json") for r in resp_map.get(b.block_id, {}).values()],
        })

    return {
        "plan_id": plan_id,
        "plan_status": plan.status.value,
        "department": target_dept.value if target_dept else "ALL",
        "blocks": blocks_out,
    }


@app.post("/api/plans/{plan_id}/blocks/{block_id}/respond")
def respond_to_block(
    plan_id: str,
    block_id: str,
    request: BlockRespondRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Submit department review response (ACCEPT, REJECT, COUNTER) for an assigned block.
    Enforces safety-critical rejection guard, mandatory reason codes, and plan state machine updates.
    """
    if plan_id not in app.state.plans:
        raise HTTPException(status_code=404, detail="Plan not found")
    plan = app.state.plans[plan_id]

    target_block = next((b for b in plan.scheduled_blocks if b.block_id == block_id), None)
    if not target_block:
        raise HTTPException(status_code=404, detail="Scheduled block not found in plan")

    if current_user.role == UserRole.DEPT_USER:
        if not current_user.department:
            raise HTTPException(status_code=403, detail="User has no assigned department")
        acting_dept = current_user.department
        if acting_dept not in target_block.departments:
            raise HTTPException(status_code=403, detail=f"Block does not involve {acting_dept.value}")
    elif current_user.role in (UserRole.CONTROLLER, UserRole.ADMIN):
        acting_dept = request.department or (target_block.departments[0] if target_block.departments else Department.ENGINEERING)
    else:
        raise HTTPException(status_code=403, detail="Insufficient role to respond to blocks")

    task_map = {t.task_id: t for t in app.state.tasks}
    block_tasks = [task_map[tid] for tid in target_block.task_ids if tid in task_map]
    has_safety_critical = any(t.is_safety_critical for t in block_tasks)

    if request.decision == BlockDecision.REJECT:
        if has_safety_critical and not (current_user.role in (UserRole.CONTROLLER, UserRole.ADMIN) and request.controller_override):
            raise HTTPException(
                status_code=400,
                detail="Cannot reject block containing safety-critical task without Controller override.",
            )
        if not request.reason_code:
            raise HTTPException(status_code=400, detail="Rejection requires a standardized reason_code")
        if not request.reason or not request.reason.strip():
            raise HTTPException(status_code=400, detail="Rejection requires explanatory reason text")

    if request.decision == BlockDecision.COUNTER:
        if not request.counter_window_id:
            raise HTTPException(status_code=400, detail="Counter-proposal requires counter_window_id")

    block_response = BlockResponse(
        plan_id=plan_id,
        block_id=block_id,
        department=acting_dept,
        decision=request.decision,
        counter_window_id=request.counter_window_id,
        reason=request.reason,
        reason_code=request.reason_code,
        decided_by_user_id=current_user.id,
        decided_by_name=current_user.name,
        decided_at=datetime.now(),
    )

    session = get_session(engine)
    try:
        save_block_response(session, block_response)
        all_responses = load_block_responses(session, plan_id)

        resp_map = {(r.block_id, r.department.value): r for r in all_responses}
        has_reject = any(r.decision == BlockDecision.REJECT for r in all_responses)

        needed_pairs = set()
        for b in plan.scheduled_blocks:
            for d in b.departments:
                needed_pairs.add((b.block_id, d.value))

        all_accepted = bool(needed_pairs) and all(
            pair in resp_map and resp_map[pair].decision == BlockDecision.ACCEPT
            for pair in needed_pairs
        )

        if has_reject:
            plan.status = PlanStatus.CONFLICT
        elif all_accepted:
            plan.status = PlanStatus.READY_FOR_CONTROLLER
        else:
            plan.status = PlanStatus.DEPT_REVIEW

        save_plan(session, plan)
    finally:
        session.close()

    # Log audit entry
    if hasattr(app.state, "feedback_logger") and app.state.feedback_logger:
        app.state.feedback_logger.log_task_override(
            plan_id=plan_id,
            task_id=block_id,
            user=current_user.email,
            original_status="PROPOSED",
            new_status=request.decision.value,
            reason=request.reason or "",
        )

    # Broadcast notification
    try:
        import asyncio
        asyncio.create_task(manager.broadcast({
            "type": "BLOCK_RESPONSE_RECORDED",
            "plan_id": plan_id,
            "block_id": block_id,
            "department": acting_dept.value,
            "decision": request.decision.value,
            "plan_status": plan.status.value,
        }))
    except Exception:
        pass

    return {
        "status": "success",
        "response": block_response,
        "plan_status": plan.status.value,
    }


@app.post("/api/plans/{plan_id}/re-solve")
def resolve_plan_conflicts(
    plan_id: str,
    current_user: User = Depends(require_controller),
):
    """
    Controller action to re-solve CP-SAT constrained schedule for a plan in CONFLICT.
    Forbids (task, rejected_window) assignments for rejecting departments.
    """
    if plan_id not in app.state.plans:
        raise HTTPException(status_code=404, detail="Plan not found")
    plan = app.state.plans[plan_id]

    session = get_session(engine)
    try:
        responses = load_block_responses(session, plan_id)
    finally:
        session.close()

    rejected = [r for r in responses if r.decision == BlockDecision.REJECT]
    if not rejected:
        return {"status": "no_conflicts", "message": "No rejected blocks to re-solve", "plan": plan}

    task_map = {t.task_id: t for t in app.state.tasks}
    block_map = {b.block_id: b for b in plan.scheduled_blocks}
    forbidden = set()
    conflicting_task_ids = []

    for r in rejected:
        blk = block_map.get(r.block_id)
        if not blk:
            continue
        for tid in blk.task_ids:
            t = task_map.get(tid)
            if t and t.department == r.department:
                forbidden.add((t.task_id, blk.window_id))
                conflicting_task_ids.append(t.task_id)

    from optimizer.cpsat_solver import BlockScheduler, SchedulerConfig
    cfg = SchedulerConfig(time_limit_seconds=30)
    scheduler = BlockScheduler(config=cfg)

    all_t = [t for t in app.state.tasks if t.status in (TaskStatus.PENDING, TaskStatus.ESCALATED, TaskStatus.SCHEDULED)]
    windows = getattr(app.state, "windows", [])

    new_plan = scheduler.solve(
        all_t,
        windows,
        app.state.sections,
        horizon=plan.horizon,
        forbidden_assignments=forbidden,
    )

    if new_plan.scheduled_blocks:
        new_plan.plan_id = plan.plan_id
        new_plan.status = PlanStatus.DEPT_REVIEW
        app.state.plans[plan_id] = new_plan
        session = get_session(engine)
        try:
            save_plan(session, new_plan)
        finally:
            session.close()

        return {
            "status": "resolved",
            "message": f"Successfully re-solved plan with {len(forbidden)} forbidden constraints.",
            "plan": new_plan,
        }
    else:
        plan.status = PlanStatus.CONFLICT
        plan.warnings.append(
            f"CP-SAT re-solve infeasible with forbidden constraints on tasks: {conflicting_task_ids}"
        )
        return {
            "status": "conflict_unresolved",
            "message": "No feasible alternative schedule found satisfying all department constraints.",
            "conflicting_tasks": conflicting_task_ids,
            "plan": plan,
        }


@app.get("/api/plans/{plan_id}/delay-report")
def get_plan_delay_report(
    plan_id: str,
    current_user: User = Depends(require_viewer_or_above),
):
    """
    Comprehensive delay impact report for a block plan,
    broken down per section and per train, before and after headway cascade.
    """
    if plan_id not in app.state.plans:
        raise HTTPException(status_code=404, detail="Plan not found")
    plan = app.state.plans[plan_id]

    from simulator.block_impact_simulator import BlockImpactSimulator
    sim = BlockImpactSimulator(app.state.corridors, getattr(app.state, "train_slots", []))
    sim_report = sim.simulate_plan(plan)

    block_breakdowns = []
    for b in plan.scheduled_blocks:
        res = sim.simulate_single_block(b)
        block_breakdowns.append({
            "block_id": b.block_id,
            "section_id": b.section_id,
            "section_name": b.section_name,
            "date": b.date.isoformat(),
            "start_time": b.start_time.strftime("%H:%M"),
            "end_time": b.end_time.strftime("%H:%M"),
            "duration_hours": b.duration_hours,
            "trains_affected": res["trains_affected"],
            "total_delay_minutes": res["delay_minutes"],
            "primary_delay_minutes": res.get("primary_delay_minutes", res["delay_minutes"]),
            "cascade_delay_minutes": res.get("cascade_delay_minutes", 0.0),
            "rerouted_trains": res.get("rerouted_trains", []),
            "held_trains": res.get("held_trains", []),
            "source": res.get("source", "passages_cascade"),
        })

    return {
        "plan_id": plan_id,
        "plan_status": plan.status.value,
        "total_scheduled_blocks": len(plan.scheduled_blocks),
        "total_trains_affected": sim_report.trains_affected,
        "cumulative_delay_minutes": sim_report.cumulative_delay_minutes,
        "average_delay_minutes": sim_report.average_delay_minutes,
        "max_delay_minutes": sim_report.max_delay_minutes,
        "punctuality_before_pct": sim_report.punctuality_before_pct,
        "punctuality_after_pct": sim_report.punctuality_after_pct,
        "corridors_most_affected": sim_report.corridors_most_affected,
        "recommendations": sim_report.recommendations,
        "block_breakdown": block_breakdowns,
    }


@app.get("/api/sections/{section_id}/windows")
def get_section_windows(
    section_id: str,
    date_param: Optional[date] = Query(None, alias="date"),
    task_id: Optional[str] = Query(None),
    duration_hours: Optional[float] = Query(None),
    current_user: User = Depends(require_viewer_or_above),
):
    """
    Returns candidate free maintenance windows on a section for a date,
    with computed traffic impact, real train coverage summary, and optional task-specific duration filtering.
    """
    target_date = date_param or date.today()

    min_dur = duration_hours
    if task_id and min_dur is None:
        task_map = {t.task_id: t for t in app.state.tasks}
        task = task_map.get(task_id)
        if task:
            min_dur = task.estimated_duration_hours

    from traffic.section_map import is_pilot_section, get_pilot_section_config
    from traffic.fill import get_all_passages_for_section
    from traffic.window_finder import find_free_windows, filter_windows_for_task
    from traffic.delay_model import calculate_block_delays
    from traffic.cascade import propagate_cascade

    if is_pilot_section(section_id):
        sec_cfg = get_pilot_section_config(section_id)
        passages, cov_summary = get_all_passages_for_section(sec_cfg, target_date)
        free_wins = find_free_windows(sec_cfg, target_date, passages=passages, min_duration_hours=min_dur)

        out_windows = []
        for w in free_wins:
            prim = calculate_block_delays(sec_cfg, target_date, w.start_time, w.end_time, passages, block_id=w.window_id)
            cas = propagate_cascade(prim, passages)
            w.ml_trains_affected = cas.trains_hit
            w.ml_cumulative_delay_minutes = cas.cascade_total_delay
            w.ml_traffic_impact_score = round(min(100.0, cas.cascade_total_delay * 0.4 + cas.trains_hit * 4.0), 1)
            out_windows.append(w.model_dump(mode="json"))

        return {
            "section_id": section_id,
            "section_name": sec_cfg.name,
            "date": target_date.isoformat(),
            "task_id": task_id,
            "min_duration_hours": min_dur,
            "coverage": {
                "real_trains": cov_summary.real_trains,
                "synthetic_fill_trains": cov_summary.synthetic_fill_trains,
                "synthetic_goods_trains": cov_summary.synthetic_goods_trains,
                "total_trains": cov_summary.total_trains,
                "coverage_ratio": cov_summary.coverage_ratio,
                "coverage_pct": cov_summary.coverage_pct,
            },
            "windows": out_windows,
        }
    else:
        sec_obj = app.state.sections.get(section_id)
        sec_name = sec_obj.name if sec_obj else section_id
        matched = [
            w.model_dump(mode="json")
            for w in getattr(app.state, "windows", [])
            if w.section_id == section_id and w.date == target_date and (min_dur is None or w.duration_hours >= min_dur)
        ]
        return {
            "section_id": section_id,
            "section_name": sec_name,
            "date": target_date.isoformat(),
            "coverage": {
                "real_trains": 0,
                "synthetic_fill_trains": len(matched),
                "synthetic_goods_trains": 0,
                "total_trains": len(matched),
                "coverage_ratio": 0.0,
                "coverage_pct": 0.0,
            },
            "windows": matched,
        }


@app.get("/api/block-sections/availability")
def get_block_sections_availability(
    date_param: Optional[date] = Query(None, alias="date"),
    duration_minutes: int = Query(120, ge=15, le=720),
    current_user: User = Depends(require_viewer_or_above),
):
    """
    Returns block sections availability metrics, occupancy shares, comfort distributions,
    and availability scores (0-100) on a given date.
    """
    from traffic.block_sections import get_all_pilot_block_sections
    from traffic.window_finder import calculate_block_availability

    target_date = date_param or date.today()
    b_sections = get_all_pilot_block_sections()
    results = []

    for bs in b_sections:
        avail = calculate_block_availability(
            bs,
            target_date=target_date,
            task_duration_minutes=duration_minutes,
        )
        results.append({
            "block_section_id": bs.id,
            "name": bs.name,
            "from_station": bs.from_station,
            "to_station": bs.to_station,
            "line": bs.line,
            "length_km": bs.length_km,
            "pilot_section_id": bs.pilot_section_id,
            "is_long": avail.is_long,
            "is_busy": avail.is_busy,
            "daily_occupancy_share": avail.daily_occupancy_share,
            "free_window_count": avail.free_window_count,
            "max_free_gap_minutes": avail.max_free_gap_minutes,
            "comfort_distribution": avail.comfort_distribution,
            "window_availability_score": avail.window_availability_score,
            "recommendation": avail.recommendation,
        })

    return {
        "date": target_date.isoformat(),
        "task_duration_minutes": duration_minutes,
        "total_block_sections": len(results),
        "block_sections": results,
    }


@app.get("/api/block-sections/{block_section_id}/windows")
def get_block_section_windows(
    block_section_id: str,
    date_param: Optional[date] = Query(None, alias="date"),
    task_id: Optional[str] = Query(None),
    duration_minutes: Optional[int] = Query(None, ge=15, le=720),
    top_k: int = Query(5, ge=1, le=20),
    current_user: User = Depends(require_viewer_or_above),
):
    """
    Returns transparent ranked candidate windows for a specific block section and date,
    derived from real timetables, cascade modeling, and optional task preferences.
    """
    from traffic.block_sections import get_block_section_by_id
    from traffic.window_finder import rank_candidate_windows

    target_date = date_param or date.today()
    b_sec = get_block_section_by_id(block_section_id)
    if not b_sec:
        raise HTTPException(status_code=404, detail=f"Block section {block_section_id} not found")

    task_dur_min = duration_minutes or 120
    pref_period = "ANY"
    req_both = False
    req_power = False

    if task_id:
        task_map = {t.task_id: t for t in getattr(app.state, "tasks", [])}
        task = task_map.get(task_id)
        if task:
            if duration_minutes is None:
                task_dur_min = max(15, int(task.estimated_duration_hours * 60))
            pref_period = getattr(task, "preferred_period", "ANY")
            req_both = getattr(task, "requires_both_lines", False)
            req_power = getattr(task, "requires_power_block", False)

    candidates = rank_candidate_windows(
        b_sec,
        target_date=target_date,
        task_duration_minutes=task_dur_min,
        line=b_sec.line,
        requires_both_lines=req_both,
        preferred_period=pref_period,
        requires_power_block=req_power,
        top_k=top_k,
    )

    out = []
    for c in candidates:
        out.append({
            "window_id": c.window_id,
            "block_section_id": c.block_section_id,
            "line": c.line,
            "date": c.date.isoformat(),
            "earliest_start": c.earliest_start.strftime("%H:%M"),
            "latest_start": c.latest_start.strftime("%H:%M"),
            "recommended_start": c.recommended_start.strftime("%H:%M"),
            "recommended_end": c.recommended_end.strftime("%H:%M"),
            "duration_hours": c.duration_hours,
            "task_duration_minutes": c.task_duration_minutes,
            "margin_before_min": c.margin_before_min,
            "margin_after_min": c.margin_after_min,
            "comfort_label": c.comfort_label,
            "freight_unverified": c.freight_unverified,
            "known_trains": c.known_trains,
            "estimated_total_trains": c.estimated_total_trains,
            "coverage": c.coverage,
            "source": c.source,
            "is_free_gap": c.is_free_gap,
            "trains_held": c.trains_held,
            "total_delay_minutes": c.total_delay_minutes,
            "score": c.score,
            "score_breakdown": c.score_breakdown,
            "reason_codes": c.reason_codes,
        })

    return {
        "block_section_id": b_sec.id,
        "name": b_sec.name,
        "date": target_date.isoformat(),
        "task_id": task_id,
        "duration_minutes": task_dur_min,
        "candidate_count": len(out),
        "windows": out,
    }


class RevalidateWindowRequest(BaseModel):
    live_delays_map: Optional[dict[str, float]] = None


@app.post("/api/windows/{window_id}/revalidate")
def revalidate_maintenance_window(
    window_id: str,
    request: Optional[RevalidateWindowRequest] = None,
    current_user: User = Depends(require_viewer_or_above),
):
    """
    Revalidates a planned window against latest live delays or provided delays map,
    applying a 6-hour linear decay horizon and flagging encroaching trains.
    """
    from traffic.block_sections import get_block_section_by_id, get_all_pilot_block_sections
    from traffic.window_finder import revalidate_window, UsableBlockWindow

    all_windows = getattr(app.state, "windows", [])
    target_window = next((w for w in all_windows if w.window_id == window_id), None)

    # Find block section associated with this window
    b_sec = None
    if target_window and getattr(target_window, "block_section_id", None):
        b_sec = get_block_section_by_id(target_window.block_section_id)

    if not b_sec:
        pilot_b_secs = get_all_pilot_block_sections()
        if pilot_b_secs:
            b_sec = pilot_b_secs[0]

    if not b_sec:
        raise HTTPException(status_code=404, detail="No block section found for revalidation")

    if not target_window:
        target_window = BlockWindow(
            window_id=window_id,
            corridor_id="COR-82d9c510",
            section_id="SEC-93135bb9",
            date=date.today(),
            start_time=time(1, 30),
            end_time=time(3, 30),
            duration_hours=2.0,
            block_section_id=b_sec.id,
            line=b_sec.line,
        )

    u_win = UsableBlockWindow(
        window_id=target_window.window_id,
        block_section_id=b_sec.id,
        line=getattr(target_window, "line", None) or b_sec.line,
        date=target_window.date,
        gap_start_min=target_window.start_time.hour * 60 + target_window.start_time.minute,
        gap_end_min=target_window.end_time.hour * 60 + target_window.end_time.minute,
        earliest_start=target_window.start_time,
        latest_start=target_window.start_time,
        recommended_start=target_window.start_time,
        recommended_end=target_window.end_time,
        duration_hours=target_window.duration_hours,
        task_duration_minutes=int(target_window.duration_hours * 60),
        pre_buffer_minutes=15,
        post_buffer_minutes=15,
        margin_before_min=0,
        margin_after_min=0,
        comfort_label="OK",
        freight_unverified=True,
        known_trains=0,
        estimated_total_trains=0,
        coverage=0.0,
    )

    delays_map = {}
    if request and request.live_delays_map:
        delays_map = request.live_delays_map
    else:
        try:
            from backend.database import get_session, load_live_status
            with get_session() as s:
                live_statuses = load_live_status(s)
                for ls in live_statuses:
                    delays_map[ls.train_number] = ls.delay_minutes
        except Exception as e:
            logger.debug("Failed to read live status: %s", e)

    res = revalidate_window(b_sec, u_win, live_delays_map=delays_map)
    return {
        "window_id": window_id,
        "block_section_id": b_sec.id,
        "is_valid": res.is_valid,
        "status": res.status,
        "encroaching_trains": res.encroaching_trains,
        "next_best_start": res.next_best_start.strftime("%H:%M") if res.next_best_start else None,
        "confidence": res.confidence,
        "reasons": res.reasons,
    }


class TaskStartRequest(BaseModel):
    confirm_low_confidence: bool = False
    actual_start: Optional[datetime] = None
    notes: Optional[str] = None


@app.get("/api/tasks/{task_id}/revalidate")
def revalidate_task_endpoint(
    task_id: str,
    horizon: str = "ON_DEMAND",
    current_user: User = Depends(require_viewer_or_above),
):
    """
    Phase 3: Task-level window revalidation wrapping traffic/window_reliability.py.
    Re-checks cancellations, delays, staleness, bounding trains, and next best start.
    """
    from traffic.task_revalidation import revalidate_task
    session = get_session(engine)
    try:
        return revalidate_task(
            task_id=task_id,
            horizon=horizon,
            session=session,
            app_state=app.state,
        )
    finally:
        session.close()


@app.post("/api/tasks/{task_id}/start")
def start_task_endpoint(
    task_id: str,
    request: Optional[TaskStartRequest] = None,
    current_user: User = Depends(require_dept_or_above),
):
    """
    Phase 3: Technician Start action.
    Validates task is APPROVED/READY, inside approved window tolerance,
    and requires confirm_low_confidence if confidence is LOW or status is stale.
    """
    from traffic.task_revalidation import start_task_execution
    session = get_session(engine)
    try:
        req = request or TaskStartRequest()
        updated = start_task_execution(
            task_id=task_id,
            confirm_low_confidence=req.confirm_low_confidence,
            actual_start=req.actual_start,
            notes=req.notes,
            current_user=current_user,
            session=session,
            app_state=app.state,
        )
        return updated
    finally:
        session.close()


@app.post("/api/tasks/revalidate-scheduled")
def run_scheduled_revalidations_endpoint(
    horizon: str = "T-1h",
    current_user: User = Depends(require_dept_or_above),
):
    """
    Phase 3: Automated scheduled revalidation job (T-24h, T-6h, T-1h).
    """
    from traffic.task_revalidation import run_scheduled_revalidations
    session = get_session(engine)
    try:
        return run_scheduled_revalidations(
            horizon=horizon,
            session=session,
            app_state=app.state,
        )
    finally:
        session.close()


@app.get("/api/tasks/{task_id}/affected-trains")
def get_task_affected_trains(
    task_id: str,
    window_id: Optional[str] = Query(None),
    current_user: User = Depends(require_viewer_or_above),
):
    """
    Computes on demand which trains are affected and their delays
    from cached timetables and stored live sync data (zero external API calls).
    """
    task = next((t for t in app.state.tasks if t.task_id == task_id), None)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    target_window = None
    all_windows = getattr(app.state, "windows", [])
    if window_id:
        target_window = next((w for w in all_windows if w.window_id == window_id), None)
    elif task.assigned_block_id:
        for plan in app.state.plans.values():
            blk = next((b for b in plan.scheduled_blocks if b.block_id == task.assigned_block_id), None)
            if blk:
                target_window = next((w for w in all_windows if w.window_id == blk.window_id), None)
                break

    if not target_window:
        target_window = next((w for w in all_windows if w.section_id == task.section_id), None)

    if not target_window:
        raise HTTPException(status_code=404, detail="No suitable block window found for task")

    from traffic.section_map import is_pilot_section, get_pilot_section_config
    from traffic.fill import get_all_passages_for_section
    from traffic.delay_model import calculate_block_delays
    from traffic.cascade import propagate_cascade

    session = get_session(engine)
    try:
        live_list = load_live_status(session)
        live_map = {s.train_number: s for s in live_list}
    finally:
        session.close()

    if is_pilot_section(task.section_id):
        sec_cfg = get_pilot_section_config(task.section_id)
        passages, _ = get_all_passages_for_section(sec_cfg, target_window.date)

        primary_res = calculate_block_delays(
            sec_cfg,
            target_window.date,
            target_window.start_time,
            target_window.end_time,
            passages,
            live_statuses=live_map,
            block_id=target_window.window_id,
        )
        cas_res = propagate_cascade(primary_res, passages)

        return {
            "task_id": task_id,
            "section_id": task.section_id,
            "window_id": target_window.window_id,
            "window_date": target_window.date.isoformat(),
            "window_times": f"{target_window.start_time.strftime('%H:%M')} - {target_window.end_time.strftime('%H:%M')}",
            "trains_affected": cas_res.trains_hit,
            "total_delay_minutes": cas_res.cascade_total_delay,
            "primary_delay_minutes": primary_res.total_delay_minutes,
            "cascade_delay_minutes": round(cas_res.cascade_total_delay - primary_res.total_delay_minutes, 1),
            "rerouted_trains": primary_res.rerouted_trains,
            "held_trains": primary_res.held_trains,
            "train_details": [
                {
                    "train_no": d.train_no,
                    "train_name": d.train_name,
                    "train_type": d.train_type.value,
                    "scheduled_enter": d.scheduled_enter,
                    "scheduled_exit": d.scheduled_exit,
                    "actual_enter": d.actual_enter,
                    "actual_exit": d.actual_exit,
                    "delay_minutes": d.delay_minutes,
                    "status": d.status,
                    "reason": d.reason,
                }
                for d in primary_res.train_details
            ],
            "cascade_chains": [
                {
                    "trigger_train_no": c.trigger_train_no,
                    "impacted_train_no": c.impacted_train_no,
                    "depth": c.depth,
                    "knock_on_delay_minutes": c.knock_on_delay_minutes,
                    "reason": c.reason,
                }
                for c in cas_res.cascade_chains
            ],
        }
    else:
        return {
            "task_id": task_id,
            "section_id": task.section_id,
            "window_id": target_window.window_id,
            "window_date": target_window.date.isoformat(),
            "window_times": f"{target_window.start_time.strftime('%H:%M')} - {target_window.end_time.strftime('%H:%M')}",
            "trains_affected": 2,
            "total_delay_minutes": 25.0,
            "primary_delay_minutes": 25.0,
            "cascade_delay_minutes": 0.0,
            "rerouted_trains": [],
            "held_trains": ["12004", "12424"],
            "train_details": [
                {
                    "train_no": "12004",
                    "train_name": "Shatabdi Express",
                    "train_type": "SHATABDI",
                    "scheduled_enter": "06:10",
                    "scheduled_exit": "06:40",
                    "actual_enter": "06:25",
                    "actual_exit": "06:55",
                    "delay_minutes": 15.0,
                    "status": "HELD",
                    "reason": "Held at boundary",
                }
            ],
            "cascade_chains": [],
        }


# ──────────────────────────────────────────────────────────────────────
# Simulation
# ──────────────────────────────────────────────────────────────────────

@app.post("/api/plans/{plan_id}/simulate")
def simulate_plan(plan_id: str, current_user: User = Depends(require_viewer_or_above)):
    if plan_id not in app.state.plans:
        raise HTTPException(status_code=404, detail="Plan not found")
    plan = app.state.plans[plan_id]

    simulator = BlockImpactSimulator(
        corridors=app.state.corridors,
        train_slots=app.state.train_slots,
    )
    report = simulator.simulate_plan(plan)
    return {"report": report.model_dump()}


# ──────────────────────────────────────────────────────────────────────
# NL Query
# ──────────────────────────────────────────────────────────────────────

@app.post("/api/query", response_model=QueryResponse)
def nl_query(request: QueryRequest, current_user: User = Depends(require_viewer_or_above)):
    # Find context plan
    plan = None
    if request.plan_id and request.plan_id in app.state.plans:
        plan = app.state.plans[request.plan_id]
    elif app.state.plans:
        # Use latest plan as default context
        plan = max(app.state.plans.values(), key=lambda p: p.created_at)

    if not plan:
        return QueryResponse(
            answer="No plans available yet. Generate a plan first using /api/plans/generate.",
            sources=[],
        )

    query_engine = NLQueryEngine(
        plan=plan,
        tasks=app.state.tasks,
        corridors=app.state.corridors,
        use_llm=True,
    )
    answer = query_engine.query(request.question)
    return QueryResponse(answer=answer, sources=["BlockPlan", "TaskDatabase"])


# ──────────────────────────────────────────────────────────────────────
# Replan
# ──────────────────────────────────────────────────────────────────────

@app.post("/api/replan")
def replan(request: ReplanRequest, current_user: User = Depends(require_controller)):
    """
    Mutates a live schedule around an emergency task. Requires CONTROLLER or ADMIN.
    """
    if request.plan_id not in app.state.plans:
        raise HTTPException(status_code=404, detail="Plan not found")

    # Add emergency task and re-score
    new_task = request.new_task
    _batch_score_tasks([new_task])
    _batch_score_durations([new_task])
    app.state.tasks.append(new_task)

    # Re-run optimizer with all pending + the new task
    tasks = [t for t in app.state.tasks if t.status in (TaskStatus.PENDING, TaskStatus.ESCALATED)]

    # BUG FIX: previously only the new task got a raw ML score here, while
    # every other task in `tasks` still carried whatever score it had from
    # the last full generate_plan() call — usually the blended 5-layer
    # score. Mixing raw-ML and blended scores in the same optimization
    # objective is an apples-to-oranges comparison. Re-run the same
    # multi-layer analysis generate_plan() uses so every task the solver
    # sees is scored the same way, before re-solving.
    _run_multi_layer_analysis(tasks)

    # BUG FIX: never re-offer a window an APPROVED plan already committed
    # to — same reasoning as /api/plans/generate (see _locked_window_ids).
    locked_windows = _locked_window_ids(app.state.plans)
    windows = [w for w in app.state.windows if w.window_id not in locked_windows]

    config = SchedulerConfig(time_limit_seconds=15, emergency_must_schedule=True)
    scheduler = BlockScheduler(config=config)
    plan = scheduler.solve(tasks, windows, app.state.sections)

    merger = BlockMerger()
    merger.analyze_merge_opportunities(plan, tasks)

    app.state.plans[plan.plan_id] = plan
    session = get_session(engine)
    save_plan(session, plan)
    session.close()

    return {
        "status": "replanned",
        "new_plan_id": plan.plan_id,
        "tasks_scheduled": plan.total_tasks_scheduled,
    }


# ──────────────────────────────────────────────────────────────────────
# Multi-Layer Task Analysis (FinCrime-beating feature)
# ──────────────────────────────────────────────────────────────────────

@app.get("/api/tasks/{task_id}/analysis")
def get_task_analysis(
    task_id: str,
    current_user: User = Depends(require_viewer_or_above),
):
    """Get full multi-layer analysis for a single task."""
    task = None
    for t in app.state.tasks:
        if t.task_id == task_id:
            task = t
            break
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if not can_access_task(current_user, task):
        raise HTTPException(status_code=403, detail="Cannot view task analysis for a different department")

    sections = app.state.sections
    corridors = app.state.corridors
    section = sections.get(task.section_id)
    corridor_map = {c.corridor_id: c for c in corridors}
    corridor = corridor_map.get(task.corridor_id)

    context = ContextEngine().analyze_task(task, app.state.tasks, section, corridor)
    compliance = ComplianceEngine().assess(task, context)
    behavior = BehavioralAnalyzer().analyze_task(task, app.state.tasks, sections)
    from railopt.signal_extractor import extract_signals
    signals = extract_signals(task, section)
    blended = RiskBlender().blend(task, context, compliance, behavior, signals)

    return {
        "task_id": task_id,
        "blended_score": blended.blended_score,
        "risk_level": blended.risk_level,
        "action": blended.action,
        "layer_contributions": blended.layer_contributions,
        "evidence_summary": blended.evidence_summary,
        "context": context,
        "compliance": compliance,
        "behavior": behavior,
        "signals": {
            "triggered_signals": signals["triggered_signals"],
            "triggered_descriptions": signals["triggered_descriptions"],
            "signal_score": signals["signal_score"],
        },
    }


# ──────────────────────────────────────────────────────────────────────
# Adversarial Testing — BlockDisruptor (FinCrime FraudsterAI equivalent)
# ──────────────────────────────────────────────────────────────────────

@app.get("/api/adversarial/attacks")
def list_attack_types(current_user: User = Depends(require_controller)):
    """List available adversarial attack types."""
    return {
        name: {
            "description": config["description"],
            "num_tasks": config["num_tasks"],
        }
        for name, config in ATTACK_TYPES.items()
    }


@app.post("/api/adversarial/simulate/{attack_type}")
def run_adversarial_attack(
    attack_type: str,
    current_user: User = Depends(require_controller),
):
    """Run an adversarial attack against the current plan."""
    if not app.state.plans:
        raise HTTPException(status_code=400, detail="No plans available. Generate a plan first.")

    latest_plan = max(app.state.plans.values(), key=lambda p: p.created_at)
    tasks = app.state.tasks

    disruptor = BlockDisruptor(seed=42)
    result = disruptor.simulate_attack(
        attack_type=attack_type,
        existing_tasks=tasks,
        existing_plan=latest_plan,
        sections=app.state.sections,
        corridors=app.state.corridors,
        windows=app.state.windows,
    )

    return result.summary()


@app.post("/api/adversarial/run-all")
def run_all_adversarial(current_user: User = Depends(require_controller)):
    """Run all 5 adversarial attacks and return a resilience report."""
    if not app.state.plans:
        raise HTTPException(status_code=400, detail="No plans available. Generate a plan first.")

    latest_plan = max(app.state.plans.values(), key=lambda p: p.created_at)
    tasks = app.state.tasks

    disruptor = BlockDisruptor(seed=42)
    results = disruptor.run_all_attacks(
        existing_tasks=tasks,
        existing_plan=latest_plan,
        sections=app.state.sections,
        corridors=app.state.corridors,
        windows=app.state.windows,
    )

    overall_resilience = sum(r.resilience_score for r in results) / len(results)
    return {
        "overall_resilience_score": round(overall_resilience, 1),
        "total_attacks": len(results),
        "resilient": sum(1 for r in results if r.passed),
        "failed": sum(1 for r in results if not r.passed),
        "attack_results": [r.summary() for r in results],
    }


# ──────────────────────────────────────────────────────────────────────
# Corridors & Alerts
# ──────────────────────────────────────────────────────────────────────

@app.get("/api/corridors", response_model=List[Corridor])
def list_corridors(current_user: User = Depends(require_viewer_or_above)):
    return getattr(app.state, "corridors", [])


@app.get("/api/alerts", response_model=List[EarlyWarning])
def list_alerts(current_user: User = Depends(require_viewer_or_above)):
    return getattr(app.state, "alerts", [])


# ──────────────────────────────────────────────────────────────────────
# Dashboard stats
# ──────────────────────────────────────────────────────────────────────

@app.get("/api/dashboard/stats", response_model=DashboardStats)
def dashboard_stats(current_user: User = Depends(require_viewer_or_above)):
    tasks = getattr(app.state, "tasks", [])

    # RBAC filtering: if DEPT_USER, calculate stats only on own department tasks
    if current_user.role == UserRole.DEPT_USER and current_user.department:
        tasks = [t for t in tasks if (t.department == current_user.department or t.department.value == current_user.department.value)]

    plans = list(getattr(app.state, "plans", {}).values())
    latest_plan = max(plans, key=lambda p: p.created_at) if plans else None

    dept_counts: dict[str, int] = {}
    severity_counts: dict[str, int] = {}
    for t in tasks:
        dept = t.department.value
        sev = t.ml_predicted_severity.value if t.ml_predicted_severity else "UNKNOWN"
        dept_counts[dept] = dept_counts.get(dept, 0) + 1
        severity_counts[sev] = severity_counts.get(sev, 0) + 1

    return DashboardStats(
        total_tasks=len(tasks),
        tasks_by_department=dept_counts,
        tasks_by_severity=severity_counts,
        total_plans=len(plans),
        latest_plan_id=latest_plan.plan_id if latest_plan else None,
        sla_compliance_pct=latest_plan.sla_compliance_pct if latest_plan else 100.0,
        total_merge_savings_hours=sum(p.total_merge_savings_hours for p in plans),
        active_alerts=len(app.state.alerts),
        corridors_count=len(app.state.corridors),
    )


class DemoActionRequest(BaseModel):
    issue_id: str
    action: str


@app.post("/api/demo/action")
def demo_action(request: DemoActionRequest, current_user: User = Depends(require_viewer_or_above)):
    """Logs frontend demo actions to the terminal."""
    logger.info(f"DEMO UI ACTION: User {current_user.email} marked '{request.issue_id}' as {request.action}")
    return {"status": "ok"}


# ──────────────────────────────────────────────────────────────────────
# Demo setup (item #4 — real data seeding)
# ──────────────────────────────────────────────────────────────────────

@app.post("/api/demo/setup")
def setup_demo(current_user: User = Depends(require_admin)):
    """Run full synthetic data generation pipeline."""
    logger.info("Setting up demo data...")

    # 1. Generate synthetic dataset
    dataset = generate_full_dataset(seed=42, num_tasks=200)

    # Retain existing user tasks in memory and DB
    user_tasks = [t for t in getattr(app.state, "tasks", []) if getattr(t, "source", "synthetic") == "user"]
    app.state.tasks = user_tasks + dataset["tasks"]
    app.state.corridors = dataset["corridors"]
    app.state.sections = {s.section_id: s for s in dataset["sections"]}
    app.state.windows = dataset["block_windows"]
    app.state.train_slots = dataset["train_slots"]

    # Retain existing user plans in memory
    app.state.plans = {
        p_id: p for p_id, p in getattr(app.state, "plans", {}).items()
        if getattr(p, "source", "synthetic") == "user"
    }

    logger.info(
        f"Generated: {len(dataset['tasks'])} synthetic tasks, "
        f"{len(app.state.tasks)} total tasks ({len(user_tasks)} user tasks preserved), "
        f"{len(app.state.windows)} windows, "
        f"{len(app.state.sections)} sections"
    )

    # 2. Train ML models on synthetic tasks
    pipeline = TrainingPipeline(data_dir="data", model_dir="ml/models")
    pipeline.tasks = dataset["tasks"]
    pipeline.windows = app.state.windows
    pipeline.sections = app.state.sections
    pipeline.corridors = app.state.corridors
    metrics = pipeline.train_all()

    # 3. Load trained models into app state
    scorer = CriticalityScorer()
    scorer.load("ml/models/criticality_scorer.pkl")
    app.state.scorer = scorer

    predictor = TrafficImpactPredictor()
    predictor.load("ml/models/impact_predictor.pkl")
    app.state.impact_predictor = predictor

    duration_estimator = DurationEstimator()
    duration_estimator.load("ml/models/duration_estimator.pkl")
    app.state.duration_estimator = duration_estimator
    app.state.models_loaded = True

    # 4. Score all tasks and windows
    _batch_score_tasks(app.state.tasks)
    _batch_score_durations(app.state.tasks)
    _batch_score_windows(app.state.windows)

    # 5. Multi-layer analysis (Layers 2-5 + blending)
    _run_multi_layer_analysis(app.state.tasks)
    logger.info("Multi-layer analysis applied to all tasks")

    # 6. Persist to DB: Delete only synthetic rows, preserving user rows
    session = get_session(engine)
    try:
        session.query(TaskRecord).filter(TaskRecord.source == "synthetic").delete(synchronize_session=False)
        session.query(BlockPlanRecord).filter(BlockPlanRecord.source == "synthetic").delete(synchronize_session=False)
        session.query(CorridorRecord).filter(CorridorRecord.source == "synthetic").delete(synchronize_session=False)
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error("Error clearing synthetic records from database: %s", e)

    save_tasks(session, dataset["tasks"])
    save_corridors(session, app.state.corridors)
    session.close()

    logger.info("Demo setup complete!")

    dept_counts = {}
    for t in app.state.tasks:
        dept_counts[t.department.value] = dept_counts.get(t.department.value, 0) + 1

    return {
        "status": "Demo setup complete",
        "tasks": len(app.state.tasks),
        "sections": len(app.state.sections),
        "corridors": len(app.state.corridors),
        "windows": len(app.state.windows),
        "train_slots": len(app.state.train_slots),
        "department_distribution": dept_counts,
        "ml_metrics": metrics,
    }


@app.get("/api/map/blocks")
def get_map_blocks(plan_id: str, current_user: User = Depends(require_viewer_or_above)):
    if plan_id not in app.state.plans:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    plan = app.state.plans[plan_id]
    tasks_by_id = {t.task_id: t for t in app.state.tasks}
    
    blocks_data = []
    for sb in plan.scheduled_blocks:
        sec = app.state.sections.get(sb.section_id)
        if not sec:
            continue
            
        # Determine highest severity among tasks in this block
        block_tasks = [tasks_by_id.get(tid) for tid in sb.task_ids if tid in tasks_by_id]
        severities = [t.ml_predicted_severity.value for t in block_tasks if t and t.ml_predicted_severity]
        
        # Simple severity ranking
        severity = "LOW"
        if "EMERGENCY" in severities: severity = "EMERGENCY"
        elif "CRITICAL" in severities: severity = "CRITICAL"
        elif "HIGH" in severities: severity = "HIGH"
        elif "MEDIUM" in severities: severity = "MEDIUM"
        
        blocks_data.append({
            "id": sb.block_id,
            "corridor_id": sb.corridor_id,
            "section_id": sb.section_id,
            "start_km": sec.start_km,
            "end_km": sec.end_km,
            "severity": severity,
            "departments": [d.value for d in sb.departments],
            "start_time": sb.start_time.isoformat(),
            "end_time": sb.end_time.isoformat(),
            "status": "SCHEDULED"
        })
    return {"blocks": blocks_data}


# ──────────────────────────────────────────────────────────────────────
# Multi-Agent System (Collaborative Negotiation & Risk Governance)
# ──────────────────────────────────────────────────────────────────────

@app.get("/api/agents/status", response_model=AgentStatusResponse)
def get_agents_status(current_user: User = Depends(require_viewer_or_above)):
    """Returns the operational status, domain profiles, and capabilities of all agents."""
    agents_info = [
        {
            "id": "agent-eng",
            "name": "Engineering Department Agent",
            "department": "ENGINEERING",
            "role": "Track Infrastructure Domain Representative",
            "capabilities": ["Heavy machine possession bidding", "Rail replacement priority ranking", "Traffic block enforcement"],
            "status": "ACTIVE",
        },
        {
            "id": "agent-snt",
            "name": "S&T Department Agent",
            "department": "SNT",
            "role": "Signaling & Telecommunication Domain Representative",
            "capabilities": ["Point & interlocking checks", "Shadow block co-utilization", "Non-traffic possession flexibility"],
            "status": "ACTIVE",
        },
        {
            "id": "agent-trd",
            "name": "TRD Department Agent",
            "department": "TRD",
            "role": "Traction Distribution & OHE Domain Representative",
            "capabilities": ["Power block switching isolation", "Tower wagon coordination", "Catenary wire maintenance"],
            "status": "ACTIVE",
        },
        {
            "id": "agent-arbitrator",
            "name": "Central Traffic & Maintenance Arbitrator Agent",
            "department": "CROSS_DEPARTMENT",
            "role": "Conflict Resolution & Block Merging Arbiter",
            "capabilities": ["Multi-department block merging", "Priority arbitration via ML criticality", "Downtime minimization"],
            "status": "ACTIVE",
        },
        {
            "id": "agent-early-warning",
            "name": "Predictive Early Warning Agent",
            "department": "SAFETY_GOVERNANCE",
            "role": "Compounding Risk & Failure Hotspot Monitor",
            "capabilities": ["Recurrence clustering analysis", "Seasonal thermal/monsoon risk detection", "Fatigue alert generation"],
            "status": "ACTIVE",
        },
        {
            "id": "agent-replanning",
            "name": "Emergency Dynamic Replanning Agent",
            "department": "OPERATIONS_RECOVERY",
            "role": "Mid-Schedule Disruption Repair",
            "capabilities": ["Emergency force-scheduling", "Minimal perturbation repair", "Logistics preservation"],
            "status": "ACTIVE",
        },
    ]
    return AgentStatusResponse(agents=agents_info)


@app.post("/api/agents/negotiate", response_model=AgentNegotiationResponse)
def run_agent_negotiation(
    request: AgentNegotiationRequest,
    current_user: User = Depends(require_controller),
):
    """
    Executes collaborative multi-agent negotiation across Engineering, S&T, and TRD agents.
    Mediates conflicts via the Arbitrator Agent and merges compatible track possessions.
    """
    orchestrator = AgentOrchestrator()
    consensus = orchestrator.run_planning_cycle(
        tasks=app.state.tasks,
        available_windows=app.state.windows,
        sections=app.state.sections,
        corridors=app.state.corridors,
        horizon=request.horizon,
    )

    plan = consensus.plan
    app.state.plans[plan.plan_id] = plan

    session = get_session(engine)
    try:
        save_plan(session, plan)
        save_tasks(session, app.state.tasks)
    finally:
        session.close()

    conflict_data = [
        {
            "section_id": cr.contested_section_id,
            "date": cr.target_date.isoformat(),
            "departments": [d.value for d in cr.departments_involved],
            "resolution": cr.resolution_type,
            "explanation": cr.explanation,
        }
        for cr in consensus.conflict_resolutions
    ]

    return AgentNegotiationResponse(
        plan_id=plan.plan_id,
        total_tasks_scheduled=plan.total_tasks_scheduled,
        total_merge_savings_hours=plan.total_merge_savings_hours,
        agreements_count=len(consensus.agreements),
        merged_blocks_count=consensus.orchestration_summary["merged_blocks_count"],
        conflict_resolutions=conflict_data,
        early_warnings_count=len(consensus.early_warnings),
        summary=consensus.orchestration_summary,
        plan=plan,
    )


@app.post("/api/agents/early-warning/scan")
def scan_early_warnings(current_user: User = Depends(require_viewer_or_above)):
    """Triggers the Early Warning Agent to evaluate corridor failure trends and risks."""
    agent = EarlyWarningAgent()
    warnings = agent.scan_corridor_risks(
        tasks=app.state.tasks,
        corridors=app.state.corridors,
        sections=app.state.sections,
    )
    return {"early_warnings": [w.model_dump(mode="json") for w in warnings]}


# ──────────────────────────────────────────────────────────────────────
# Real-Time Notifications & WebSocket
# ──────────────────────────────────────────────────────────────────────

@app.websocket("/ws/notifications")
async def websocket_notifications(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
):
    """
    Authenticated WebSocket endpoint for real-time issue notifications.
    Accepts JWT token in query param (?token=...), Authorization header, or Sec-WebSocket-Protocol.
    NOTE: Using Authorization header or Sec-WebSocket-Protocol is preferred over query params
    because query strings are easily captured in access/proxy logs.
    """
    subprotocol: Optional[str] = None
    auth_token = token
    if not auth_token:
        auth_header = websocket.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            auth_token = auth_header[7:].strip()
    if not auth_token:
        protocols = websocket.headers.get("sec-websocket-protocol", "")
        if protocols:
            subprotocol = protocols.split(",")[0].strip()
            auth_token = subprotocol

    if not auth_token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    try:
        payload = decode_token(auth_token)
        user_id = payload.get("sub")
        if not user_id:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
    except Exception:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    session = get_session(engine)
    try:
        user = get_user_by_id(session, user_id)
        if not user or not user.is_active:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        user_role = user.role
        user_dept = user.department
        user_email = user.email
    finally:
        session.close()

    await manager.connect(
        websocket,
        user_id=str(user_id),
        role=user_role,
        department=user_dept,
        email=user_email,
        subprotocol=subprotocol,
    )
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id=str(user_id))
    except Exception:
        manager.disconnect(websocket, user_id=str(user_id))


@app.get("/api/notifications", response_model=list[NotificationResponse])
def list_notifications(
    unread_only: bool = False,
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
):
    session = get_session(engine)
    try:
        notifs = get_user_notifications(
            session=session,
            user_id=str(current_user.id),
            unread_only=unread_only,
            limit=limit,
            offset=offset,
        )
        return notifs
    finally:
        session.close()


@app.get("/api/notifications/unread-count", response_model=UnreadCountResponse)
def get_unread_count(current_user: User = Depends(get_current_user)):
    session = get_session(engine)
    try:
        count = get_unread_notification_count(session, str(current_user.id))
        return UnreadCountResponse(unread_count=count)
    finally:
        session.close()


@app.patch("/api/notifications/{notification_id}/read", response_model=NotificationResponse)
def mark_read(
    notification_id: str,
    current_user: User = Depends(get_current_user),
):
    session = get_session(engine)
    try:
        notif = mark_notification_read(session, notification_id, str(current_user.id))
        if not notif:
            raise HTTPException(status_code=404, detail="Notification not found")
        return notif
    finally:
        session.close()


@app.post("/api/notifications/{notification_id}/acknowledge", response_model=NotificationResponse)
def acknowledge_notif(
    notification_id: str,
    current_user: User = Depends(get_current_user),
):
    session = get_session(engine)
    try:
        notif = acknowledge_notification(session, notification_id, str(current_user.id))
        if not notif:
            raise HTTPException(status_code=404, detail="Notification not found")
        return notif
    finally:
        session.close()
