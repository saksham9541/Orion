"""
RailOpt — FastAPI backend.

Provides REST endpoints for the React dashboard: task management,
plan generation (ML scoring → CP-SAT optimization → merge analysis),
NL briefings, what-if simulation, and a one-click demo setup.
"""

from __future__ import annotations

import logging
import os
from datetime import date, timedelta
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Depends, Request
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
    TaskRecord,
    BlockPlanRecord,
    CorridorRecord,
)
# Data
from railopt.synthetic_data import generate_full_dataset
from ml.feedback_logger import FeedbackLogger
from ml.defect_text_classifier import DefectTextClassifier
from railopt.data_integration import DataIntegrationService
from pydantic import BaseModel

from backend.auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    authenticate_user,
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
    User,
)
from railopt.models import (
    AssetType,
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

app = FastAPI(title="RailOpt API", version="1.0.0")

from fastapi import Request
import time

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = (time.time() - start_time) * 1000
    print(f"INFO:     {request.client.host} - \"{request.method} {request.url.path}\" {response.status_code} ({process_time:.1f}ms)", flush=True)
    return response

DEFAULT_CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

def get_cors_origins() -> list[str]:
    origins_env = os.environ.get("CORS_ORIGINS", "").strip()
    is_prod = os.environ.get("ENVIRONMENT", "").strip().lower() == "production"
    if origins_env:
        return [o.strip() for o in origins_env.split(",") if o.strip()]
    if is_prod:
        logger.warning("CORS_ORIGINS is not set in production. Falling back to localhost defaults.")
    return DEFAULT_CORS_ORIGINS

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = get_engine()


@app.on_event("startup")
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
    client_ip = http_req.client.host if http_req.client else None
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
    except Exception:
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
# Health
# ──────────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "models_loaded": bool(getattr(app.state, "models_loaded", False)),
        "database_ok": bool(getattr(app.state, "database_ok", True)),
    }


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
    tasks = app.state.tasks
    
    # RBAC: DEPT_USER only gets tasks of their own department
    if current_user.role == UserRole.DEPT_USER and current_user.department:
        department = current_user.department.value

    if department:
        tasks = [t for t in tasks if t.department.value == department or t.department == department]
    if severity:
        tasks = [t for t in tasks if t.ml_predicted_severity and (t.ml_predicted_severity.value == severity or t.ml_predicted_severity == severity)]
    if status:
        tasks = [t for t in tasks if t.status.value == status or t.status == status]
    if corridor:
        tasks = [t for t in tasks if t.corridor_id == corridor]
    return tasks


@app.get("/api/tasks/{task_id}")
def get_task(task_id: str, current_user: User = Depends(require_viewer_or_above)):
    for t in app.state.tasks:
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
    raise HTTPException(status_code=404, detail="Task not found")


class TaskStatusUpdate(BaseModel):
    status: str


@app.put("/api/tasks/{task_id}/status")
def update_task_status(
    task_id: str,
    request: TaskStatusUpdate,
    current_user: User = Depends(require_dept_or_above),
):
    for t in app.state.tasks:
        if t.task_id == task_id:
            if not can_access_task(current_user, t):
                raise HTTPException(status_code=403, detail="Cannot update task for different department")
            
            try:
                t.status = TaskStatus(request.status)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid status")
                
            session = get_session(engine)
            save_tasks(session, [t]) # Upsert
            session.close()
            return {"status": "ok", "new_status": t.status.value}
    raise HTTPException(status_code=404, detail="Task not found")


class ComplaintRequest(BaseModel):
    description: str
    corridor_id: str
    section_id: str
    km_location: float


@app.post("/api/tasks/complaint", response_model=MaintenanceTask)
def submit_complaint(
    request: ComplaintRequest,
    current_user: User = Depends(require_dept_or_above),
):
    import uuid
    from datetime import datetime
    
    classifier = DefectTextClassifier()
    classification = classifier.classify(request.description)

    # Validate category against DefectCategory enum
    raw_cat = classification.get("defect_category", "")
    try:
        category = DefectCategory(raw_cat)
    except ValueError:
        category = DefectCategory.GAUGE_IRREGULARITY

    # Validate severity against DefectSeverity enum
    raw_sev = classification.get("severity", "")
    try:
        severity = DefectSeverity(raw_sev)
    except ValueError:
        severity = DefectSeverity.MEDIUM

    department, asset_type = CATEGORY_DEPARTMENT_ASSET_MAP.get(
        category, (Department.ENGINEERING, AssetType.RAIL)
    )

    # DEPT_USER can only submit for their own department
    if current_user.role == UserRole.DEPT_USER and current_user.department:
        if department != current_user.department:
            raise HTTPException(
                status_code=403,
                detail=f"Cannot submit complaint for department {department.value} as user belongs to {current_user.department.value}",
            )

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
    )
    
    app.state.tasks.append(task)
    session = get_session(engine)
    save_tasks(session, [task])
    session.close()
    return task

# ──────────────────────────────────────────────────────────────────────
# RailRadar — Live Train Status
# ──────────────────────────────────────────────────────────────────────
from backend.database import get_session, save_live_status, load_live_status

@app.post("/api/trains/live/sync")
def sync_live_trains(current_user: User = Depends(require_controller)):
    adapter = app.state.data_integration.railradar_adapter
    if adapter is None:
        raise HTTPException(status_code=503, detail="RailRadar not configured — set RAILRADAR_API_KEYS in .env")

    try:
        from railopt.real_train_registry import resolve_train_corridor_map
        train_corridor_map = resolve_train_corridor_map(app.state.corridors)

        # Use trains from the registry (real train numbers mapped to corridors)
        train_ids = list(train_corridor_map.keys())
        if not train_ids:
            # Fallback to hardcoded list if registry is empty
            train_ids = ["12015", "12016", "12951", "12952", "12229", "12230",
                         "22691", "22692", "12431", "12432", "12423", "12424",
                         "12859", "12860", "12137", "12138", "12903", "12904"]

        statuses = []
        import time
        for tid in train_ids:
            try:
                raw = adapter.get_train_status(str(tid))
                corridor_id = train_corridor_map.get(str(tid), "")
                status = adapter.parse_live_status(raw, corridor_id=corridor_id)
                statuses.append(status)
                time.sleep(0.5)  # Throttle to avoid connection resets
            except Exception as e:
                logger.warning(f"RailRadar sync failed for {tid}: {e}")
        
        session = get_session(engine)
        save_live_status(session, statuses)
        session.close()
        return {"status": "ok", "synced": len(statuses)}
    except Exception as e:
        logger.error(f"Sync failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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
    range_start = request.start_date or date.today()
    range_end = request.end_date or (range_start + timedelta(days=horizon_days))

    tasks = [t for t in app.state.tasks if t.status in (TaskStatus.PENDING, TaskStatus.ESCALATED)]
    windows = [
        w for w in app.state.windows
        if w.window_id not in locked_windows and range_start <= w.date <= range_end
    ]

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
    return app.state.corridors


@app.get("/api/alerts", response_model=List[EarlyWarning])
def list_alerts(current_user: User = Depends(require_viewer_or_above)):
    return app.state.alerts


# ──────────────────────────────────────────────────────────────────────
# Dashboard stats
# ──────────────────────────────────────────────────────────────────────

@app.get("/api/dashboard/stats", response_model=DashboardStats)
def dashboard_stats(current_user: User = Depends(require_viewer_or_above)):
    tasks = app.state.tasks

    # RBAC filtering: if DEPT_USER, calculate stats only on own department tasks
    if current_user.role == UserRole.DEPT_USER and current_user.department:
        tasks = [t for t in tasks if (t.department == current_user.department or t.department.value == current_user.department.value)]

    plans = list(app.state.plans.values())
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
    analysis = _run_multi_layer_analysis(app.state.tasks)
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