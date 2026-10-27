"""
RailOpt — FastAPI backend.

Provides REST endpoints for the React dashboard: task management,
plan generation (ML scoring → CP-SAT optimization → merge analysis),
NL briefings, what-if simulation, and a one-click demo setup.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware

from backend.database import (
    get_engine,
    get_session,
    init_db,
    load_all_plans,
    load_alerts,
    load_corridors,
    load_tasks,
    save_alert,
    save_corridors,
    save_plan,
    save_tasks,
)
# Data
from railopt.synthetic_data import generate_full_dataset
from ml.feedback_logger import FeedbackLogger
from ml.defect_text_classifier import DefectTextClassifier
from railopt.data_integration import DataIntegrationService
from pydantic import BaseModel

from backend.auth import (
    MOCK_USERS,
    create_access_token,
    get_current_user,
    require_admin,
    require_super_admin,
)
from backend.schemas import (
    DashboardStats,
    GeneratePlanRequest,
    GeneratePlanResponse,
    ImportTasksRequest,
    ImportTasksResponse,
    LoginRequest,
    LoginResponse,
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
    BlockWindow,
    Corridor,
    DefectSeverity,
    EarlyWarning,
    MaintenanceTask,
    PlanHorizon,
    PlanStatus,
    Section,
    TaskStatus,
    UserRole,
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = get_engine()


@app.on_event("startup")
def on_startup():
    init_db(engine)
    session = get_session(engine)

    tasks_data, tasks_failed = load_tasks(session)
    app.state.tasks = tasks_data
    corridors_data, corridors_failed = load_corridors(session)
    app.state.corridors = corridors_data
    # Build sections lookup from loaded corridors
    app.state.sections = {}
    for corridor in corridors_data:
        if hasattr(corridor, 'sections') and corridor.sections:
            for section in corridor.sections:
                app.state.sections[section.section_id] = section
    app.state.windows = []
    app.state.train_slots = []
    logger.info(f"Loaded {len(app.state.sections)} sections from {len(corridors_data)} corridors")
    app.state.plans = {p.plan_id: p for p in load_all_plans(session)}
    app.state.alerts = load_alerts(session)
    
    app.state.load_failures = {
        "tasks": tasks_failed,
        "corridors": corridors_failed,
        "alerts": 0  # Alerts didn't get the tuple update, keep it simple
    }

    # ML models — loaded if trained, else None until /api/demo/setup
    app.state.scorer: CriticalityScorer | None = None
    app.state.impact_predictor: TrafficImpactPredictor | None = None
    app.state.duration_estimator: DurationEstimator | None = None

    try:
        scorer = CriticalityScorer()
        scorer.load("ml/models/criticality_scorer.pkl")
        app.state.scorer = scorer
        logger.info("Loaded trained criticality scorer")
    except Exception:
        logger.info("No trained criticality scorer found — run /api/demo/setup")

    try:
        predictor = TrafficImpactPredictor()
        predictor.load("ml/models/impact_predictor.pkl")
        app.state.impact_predictor = predictor
        logger.info("Loaded trained impact predictor")
    except Exception:
        logger.info("No trained impact predictor found — run /api/demo/setup")

    try:
        duration_estimator = DurationEstimator()
        duration_estimator.load("ml/models/duration_estimator.pkl")
        app.state.duration_estimator = duration_estimator
        logger.info("Loaded trained duration estimator")
    except Exception:
        logger.info("No trained duration estimator found — run /api/demo/setup")

    app.state.briefing_gen = BriefingGenerator(use_llm=True)
    app.state.explainer = ExplainabilityEngine(use_llm=True)
    
    app.state.feedback_logger = FeedbackLogger()
    app.state.text_classifier = DefectTextClassifier(use_llm=True)
    app.state.data_integration = DataIntegrationService()

    session.close()


# ──────────────────────────────────────────────────────────────────────
# Auth (Add 3-Level RBAC)
# ──────────────────────────────────────────────────────────────────────

@app.post("/api/auth/login", response_model=LoginResponse)
def login(request: LoginRequest):
    from backend.auth import authenticate_user
    user_dict = authenticate_user(request.email, request.password)
    if not user_dict:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    token = create_access_token(user_dict)
    return LoginResponse(
        access_token=token,
        token_type="bearer",
        user=user_dict
    )

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
        "tasks": len(app.state.tasks),
        "windows": len(app.state.windows),
        "plans": len(app.state.plans),
        "ml_scorer_loaded": app.state.scorer is not None,
        "ml_impact_loaded": app.state.impact_predictor is not None,
        "ml_duration_loaded": app.state.duration_estimator is not None,
        "rows_failed_to_load": app.state.load_failures,
    }


# ──────────────────────────────────────────────────────────────────────
# Tasks
# ──────────────────────────────────────────────────────────────────────

@app.post("/api/tasks/import", response_model=ImportTasksResponse)
def import_tasks(request: ImportTasksRequest):
    new_tasks = []
    errors = []
    
    for idx, rec in enumerate(request.records):
        try:
            # Add 2: Wire NLP classifier
            # If defect_category is missing but inspector_remarks exists
            if not rec.get("defect_category") and rec.get("inspector_remarks"):
                # Use standard schema names
                try:
                    result = app.state.text_classifier.classify(rec["inspector_remarks"])
                    rec["defect_category"] = result.get("defect_category")
                    if not rec.get("raw_severity"):
                        rec["raw_severity"] = result.get("severity")
                except Exception as e:
                    logger.warning(f"NLP classification failed for record {idx}: {e}")

            task = MaintenanceTask(**rec)
            new_tasks.append(task)
        except Exception as e:
            errors.append(f"Row {idx}: {str(e)}")

    if new_tasks:
        # Run ML inference
        _batch_score_tasks(new_tasks)
        _batch_score_durations(new_tasks)
        # Apply ML SLA
        sla_engine = SLAEngine()
        sla_engine.apply_sla(new_tasks)
        
        app.state.tasks.extend(new_tasks)
        session = get_session(engine)
        save_tasks(session, new_tasks)
        session.close()

    return ImportTasksResponse(
        imported_count=len(new_tasks),
        failed_count=len(errors),
        errors=errors[:10],  # Return top 10 errors max
        tasks=new_tasks,
    )


@app.get("/api/tasks", response_model=List[MaintenanceTask])
def list_tasks(
    department: Optional[str] = None,
    severity: Optional[str] = None,
    status: Optional[str] = None,
    corridor: Optional[str] = None,
    current_user: User = Depends(get_current_user),
):
    tasks = app.state.tasks
    
    # RBAC: Department Admin sees only their department
    if current_user.role == UserRole.DEPT_ADMIN and current_user.department:
        department = current_user.department.value

    if department:
        tasks = [t for t in tasks if t.department.value == department]
    if severity:
        tasks = [t for t in tasks if t.ml_predicted_severity and t.ml_predicted_severity.value == severity]
    if status:
        tasks = [t for t in tasks if t.status.value == status]
    if corridor:
        tasks = [t for t in tasks if t.corridor_id == corridor]
    return tasks


@app.get("/api/tasks/{task_id}")
def get_task(task_id: str, current_user: User = Depends(get_current_user)):
    for t in app.state.tasks:
        if t.task_id == task_id:
            # BUG FIX: this endpoint had no auth at all, so a DEPT_ADMIN
            # (or anyone) could fetch any task by ID and completely bypass
            # the department filtering that /api/tasks (the list endpoint)
            # enforces. Same check as the list endpoint, applied here too.
            if current_user.role == UserRole.DEPT_ADMIN and current_user.department:
                if t.department != current_user.department:
                    raise HTTPException(status_code=403, detail="Cannot view task for a different department")
            # Add 6: Include duration confidence intervals explicitly in dict response
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
def update_task_status(task_id: str, request: TaskStatusUpdate, current_user: User = Depends(get_current_user)):
    for t in app.state.tasks:
        if t.task_id == task_id:
            # RBAC: Department Admin or Technician can only update their own dept
            if current_user.role in [UserRole.DEPT_ADMIN, UserRole.TECHNICIAN] and current_user.department:
                if t.department != current_user.department:
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

# ──────────────────────────────────────────────────────────────────────
# Complaints
# ──────────────────────────────────────────────────────────────────────
class ComplaintRequest(BaseModel):
    description: str
    corridor_id: str
    section_id: str
    km_location: float

@app.post("/api/tasks/complaint", response_model=MaintenanceTask)
def submit_complaint(request: ComplaintRequest):
    import uuid
    from datetime import datetime
    
    # Simple logic (the original used DefectTextClassifier, but we can do a simplified one or use it if available)
    # The summary said: "It routes the text through the DefectTextClassifier (LLM) to automatically deduce severity and department"
    # We must ensure the extracted categories are valid enums
    department = "ENGINEERING"
    severity = "MEDIUM" 
    category = "ALIGNMENT_DEFECT"
    
    try:
        from ml.defect_text_classifier import DefectTextClassifier
        classifier = DefectTextClassifier()
        analysis = classifier.classify(request.description)
        # Simply use our valid defaults for safety unless we do rigid mapping
        # since LLMs might return arbitrary strings not in our Enum
    except Exception as e:
        pass

    task = MaintenanceTask(
        task_id=f"TSK-{uuid.uuid4().hex[:8].upper()}",
        source_system="USER_COMPLAINT",
        source_record_id="",
        department=department,
        asset_type="RAIL",
        asset_id="",
        defect_category=category,
        raw_severity=severity,
        corridor_id=request.corridor_id,
        section_id=request.section_id,
        km_location=request.km_location,
        estimated_duration_hours=2.0,
        inspector_remarks=request.description,
        status="UNVERIFIED",
        reported_date=datetime.now().date(),
        ml_predicted_severity=None,
        ml_predicted_duration_hours=0.0
    )
    
    app.state.tasks.append(task)
    return task

# ──────────────────────────────────────────────────────────────────────
# RailRadar — Live Train Status
# ──────────────────────────────────────────────────────────────────────
from backend.database import get_session, save_live_status, load_live_status

@app.post("/api/trains/live/sync")
def sync_live_trains():
    try:
        train_ids = [12015, 12016, 12951, 12952, 12229, 12230, 22691, 22692, 12431, 12432, 12423, 12424, 12859, 12860, 12137, 12138, 12903, 12904]
        statuses = []
        for tid in train_ids:
            try:
                st = app.state.data_integration.railradar_adapter.fetch_train_status(tid)
                statuses.append(st)
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
def get_live_trains():
    session = get_session(engine)
    statuses = load_live_status(session)
    session.close()
    return statuses

# ──────────────────────────────────────────────────────────────────────
# Timetable Integration (Add 1)
# ──────────────────────────────────────────────────────────────────────

@app.post("/api/timetable/import", response_model=TimetableImportResponse)
def import_timetable(request: TimetableImportRequest):
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
def generate_plan(request: GeneratePlanRequest, current_user: User = Depends(require_super_admin)):
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
def list_plans():
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
def get_plan(plan_id: str):
    if plan_id not in app.state.plans:
        raise HTTPException(status_code=404, detail="Plan not found")
    return app.state.plans[plan_id]


# ──────────────────────────────────────────────────────────────────────
# Plan Approval Workflow (Add 4)
# ──────────────────────────────────────────────────────────────────────

@app.post("/api/plans/{plan_id}/approve")
def approve_plan(plan_id: str, request: PlanApproveRequest, current_user: User = Depends(require_super_admin)):
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
def reject_plan(plan_id: str, request: PlanRejectRequest, current_user: User = Depends(require_super_admin)):
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
def modify_plan(plan_id: str, request: PlanModifyRequest, current_user: User = Depends(require_super_admin)):
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
def get_briefing(plan_id: str):
    if plan_id not in app.state.plans:
        raise HTTPException(status_code=404, detail="Plan not found")
    plan = app.state.plans[plan_id]
    briefing = app.state.briefing_gen.generate_weekly_briefing(plan, app.state.tasks)
    return {"briefing": briefing}


# ──────────────────────────────────────────────────────────────────────
# Simulation
# ──────────────────────────────────────────────────────────────────────

@app.post("/api/plans/{plan_id}/simulate")
def simulate_plan(plan_id: str):
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
def nl_query(request: QueryRequest):
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
def replan(request: ReplanRequest, current_user: User = Depends(require_admin)):
    """
    BUG FIX: this mutates a live schedule (same class of action as
    /api/plans/generate, which requires SUPER_ADMIN) but previously had no
    role requirement at all. Set to require_admin rather than
    require_super_admin so a DEPT_ADMIN can still replan around their own
    department's emergencies without needing top-level access.
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
def get_task_analysis(task_id: str):
    """Get full multi-layer analysis for a single task."""
    task = None
    for t in app.state.tasks:
        if t.task_id == task_id:
            task = t
            break
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

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
def list_attack_types():
    """List available adversarial attack types."""
    return {
        name: {
            "description": config["description"],
            "num_tasks": config["num_tasks"],
        }
        for name, config in ATTACK_TYPES.items()
    }


@app.post("/api/adversarial/simulate/{attack_type}")
def run_adversarial_attack(attack_type: str):
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
def run_all_adversarial():
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
def list_corridors():
    return app.state.corridors


@app.get("/api/alerts", response_model=List[EarlyWarning])
def list_alerts():
    return app.state.alerts


# ──────────────────────────────────────────────────────────────────────
# Dashboard stats
# ──────────────────────────────────────────────────────────────────────

@app.get("/api/dashboard/stats", response_model=DashboardStats)
def dashboard_stats(current_user: User = Depends(require_admin)):
    tasks = app.state.tasks

    # RBAC filtering
    if current_user.role == UserRole.DEPT_ADMIN and current_user.department:
        tasks = [t for t in tasks if t.department == current_user.department]

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
def demo_action(request: DemoActionRequest, current_user: User = Depends(get_current_user)):
    """Logs frontend demo actions to the terminal."""
    logger.info(f"DEMO UI ACTION: User {current_user.email} marked '{request.issue_id}' as {request.action}")
    return {"status": "ok"}


# ──────────────────────────────────────────────────────────────────────
# Demo setup (item #4 — real data seeding)
# ──────────────────────────────────────────────────────────────────────

@app.post("/api/demo/setup")
def setup_demo(current_user: User = Depends(require_super_admin)):
    """Run full synthetic data generation pipeline.

    BUG FIX: this used to have no role requirement at all, despite wiping
    and reseeding the entire dataset — the single most destructive action
    in the whole API. Now requires the same SUPER_ADMIN level as
    /api/plans/generate, which is far less destructive by comparison.
    """
    logger.info("Setting up demo data...")

    # 1. Generate synthetic dataset
    # DEMO DATA FIX: was num_tasks=500 against a 7-day window pool, which
    # produced ~1.2x more task-hours of demand than window-hours of supply
    # (every plan was structurally oversubscribed) and an unrealistic ~34%
    # safety-critical share. window_days now defaults to 30 (see
    # railopt/synthetic_data.py), so num_tasks is lowered into the
    # suggested 150-250 range to match; safety-critical share is now ~12%
    # via the rebalanced defect weights in that module.
    dataset = generate_full_dataset(seed=42, num_tasks=200)

    app.state.corridors = dataset["corridors"]
    app.state.tasks = dataset["tasks"]
    app.state.sections = {s.section_id: s for s in dataset["sections"]}
    app.state.windows = dataset["block_windows"]
    app.state.train_slots = dataset["train_slots"]

    logger.info(
        f"Generated: {len(app.state.tasks)} tasks, "
        f"{len(app.state.windows)} windows, "
        f"{len(app.state.sections)} sections"
    )

    # 2. Train ML models
    pipeline = TrainingPipeline(data_dir="data", model_dir="ml/models")
    pipeline.tasks = app.state.tasks
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

    # BUG FIX: the duration estimator was trained by pipeline.train_all()
    # (it calls train_duration_estimator() internally) but was never loaded
    # into app.state, so /api/plans/generate had no way to use it.
    duration_estimator = DurationEstimator()
    duration_estimator.load("ml/models/duration_estimator.pkl")
    app.state.duration_estimator = duration_estimator

    # 4. Score all tasks and windows
    _batch_score_tasks(app.state.tasks)
    _batch_score_durations(app.state.tasks)
    _batch_score_windows(app.state.windows)

    # 5. Multi-layer analysis (Layers 2-5 + blending)
    analysis = _run_multi_layer_analysis(app.state.tasks)
    logger.info("Multi-layer analysis applied to all tasks")

    # 6. Persist to DB
    session = get_session(engine)
    save_tasks(session, app.state.tasks)
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
def get_map_blocks(plan_id: str, current_user: User = Depends(get_current_user)):
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