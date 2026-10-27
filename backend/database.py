from sqlalchemy import create_engine, Column, String, Float, Integer, Boolean, Date, DateTime, Text, JSON
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from railopt.models import MaintenanceTask, BlockPlan, Corridor, EarlyWarning, TaskStatus, DefectSeverity, LiveTrainStatus
import datetime
import logging
from typing import Optional

logger = logging.getLogger(__name__)

Base = declarative_base()

class TaskRecord(Base):
    __tablename__ = 'tasks'
    task_id = Column(String, primary_key=True)
    source_system = Column(String)
    source_record_id = Column(String)
    department = Column(String)
    asset_type = Column(String)
    asset_id = Column(String)
    defect_category = Column(String)
    raw_severity = Column(String)
    corridor_id = Column(String)
    section_id = Column(String)
    km_location = Column(Float)
    km_start = Column(Float)
    km_end = Column(Float)
    reported_date = Column(Date)
    due_date = Column(Date, nullable=True)
    days_overdue = Column(Integer)
    inspector_remarks = Column(Text)
    is_safety_critical = Column(Boolean)
    requires_power_block = Column(Boolean)
    requires_traffic_block = Column(Boolean)
    crew_size_required = Column(Integer)
    tools_special = Column(JSON)
    asset_age_years = Column(Float)
    historical_failure_count = Column(Integer)
    last_maintenance_date = Column(Date, nullable=True)
    ml_criticality_score = Column(Float)
    ml_predicted_severity = Column(String, nullable=True)
    ml_predicted_duration_hours = Column(Float)
    ml_duration_confidence_lower = Column(Float)
    ml_duration_confidence_upper = Column(Float)
    ml_shap_values = Column(JSON)
    estimated_duration_hours = Column(Float)
    status = Column(String)
    assigned_block_id = Column(String, nullable=True)
    deferred_count = Column(Integer)

class BlockPlanRecord(Base):
    __tablename__ = 'plans'
    plan_id = Column(String, primary_key=True)
    horizon = Column(String)
    start_date = Column(Date)
    end_date = Column(Date)
    created_at = Column(DateTime)
    scheduled_blocks = Column(JSON)
    total_tasks_scheduled = Column(Integer)
    total_tasks_deferred = Column(Integer)
    total_block_hours = Column(Float)
    total_merge_savings_hours = Column(Float)
    total_trains_affected = Column(Integer)
    sla_compliance_pct = Column(Float)
    departments_summary = Column(JSON)
    deferred_task_ids = Column(JSON)
    escalated_task_ids = Column(JSON)
    solver_status = Column(String)
    solve_time_ms = Column(Float)
    status = Column(String)
    approved_by = Column(String)
    override_log = Column(JSON)

class CorridorRecord(Base):
    __tablename__ = 'corridors'
    corridor_id = Column(String, primary_key=True)
    name = Column(String)
    division = Column(String)
    zone = Column(String)
    sections = Column(JSON)
    total_length_km = Column(Float)
    is_rajdhani_route = Column(Boolean)

class AlertRecord(Base):
    __tablename__ = 'alerts'
    warning_id = Column(String, primary_key=True)
    corridor_id = Column(String)
    section_id = Column(String)
    asset_type = Column(String)
    risk_level = Column(String)
    message = Column(Text)
    trend_data = Column(JSON)
    recommended_action = Column(Text)
    estimated_failure_window_days = Column(Integer)
    created_at = Column(DateTime)


class LiveTrainStatusRecord(Base):
    __tablename__ = 'live_train_status'
    train_number = Column(String, primary_key=True)
    train_name = Column(String)
    corridor_id = Column(String)
    section_id = Column(String)
    delay_minutes = Column(Float)
    status = Column(String)
    last_updated = Column(DateTime)
    source = Column(String)


def get_engine(db_path='railopt.db'):
    return create_engine(f"sqlite:///{db_path}")

def init_db(engine):
    Base.metadata.create_all(engine)

def get_session(engine):
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()

def save_tasks(session: Session, tasks: list[MaintenanceTask]):
    mappings = []
    for t in tasks:
        task_data = t.model_dump(mode='json')
        # Ensure date fields are proper date objects for SQLAlchemy
        if hasattr(t, "reported_date") and t.reported_date:
            task_data["reported_date"] = t.reported_date
        if hasattr(t, "due_date") and t.due_date:
            task_data["due_date"] = t.due_date
        if hasattr(t, "last_maintenance_date") and t.last_maintenance_date:
            task_data["last_maintenance_date"] = t.last_maintenance_date
        mappings.append(task_data)
    if mappings:
        # Use merge for upsert semantics (bulk_insert would fail on duplicates)
        for m in mappings:
            session.merge(TaskRecord(**m))
        session.commit()
        logger.info("Saved %d tasks to database", len(mappings))

def load_tasks(session: Session) -> tuple[list[MaintenanceTask], int]:
    """Returns (tasks, failed_count)."""
    records = session.query(TaskRecord).all()
    tasks = []
    skipped = 0
    for r in records:
        d = r.__dict__.copy()
        d.pop('_sa_instance_state', None)
        try:
            tasks.append(MaintenanceTask(**d))
        except Exception as e:
            skipped += 1
            logger.warning("Failed to reconstruct task %s: %s", d.get("task_id", "?"), e)
    if skipped:
        logger.warning("load_tasks: %d/%d rows failed Pydantic validation", skipped, len(records))
    return tasks, skipped

def save_plan(session: Session, plan: BlockPlan):
    plan_data = plan.model_dump(mode='json')
    record = BlockPlanRecord(**plan_data)
    if hasattr(plan, "start_date") and plan.start_date:
        record.start_date = plan.start_date
    if hasattr(plan, "end_date") and plan.end_date:
        record.end_date = plan.end_date
    if hasattr(plan, "created_at") and plan.created_at:
        record.created_at = plan.created_at
    session.merge(record)
    session.commit()

def load_plan(session: Session, plan_id: str) -> Optional[BlockPlan]:
    r = session.query(BlockPlanRecord).filter(BlockPlanRecord.plan_id == plan_id).first()
    if r:
        d = r.__dict__.copy()
        d.pop('_sa_instance_state', None)
        return BlockPlan(**d)
    return None

def load_all_plans(session: Session) -> list[BlockPlan]:
    records = session.query(BlockPlanRecord).all()
    plans = []
    for r in records:
        d = r.__dict__.copy()
        d.pop('_sa_instance_state', None)
        plans.append(BlockPlan(**d))
    return plans

def save_corridors(session: Session, corridors: list[Corridor]):
    for c in corridors:
        record = CorridorRecord(**c.model_dump(mode='json'))
        session.merge(record)
    session.commit()

def load_corridors(session: Session) -> tuple[list[Corridor], int]:
    """Returns (corridors, failed_count)."""
    records = session.query(CorridorRecord).all()
    corridors = []
    skipped = 0
    for r in records:
        d = r.__dict__.copy()
        d.pop('_sa_instance_state', None)
        try:
            corridors.append(Corridor(**d))
        except Exception as e:
            skipped += 1
            logger.warning("Failed to reconstruct corridor %s: %s", d.get("corridor_id", "?"), e)
    return corridors, skipped

def save_alert(session: Session, alert: EarlyWarning):
    alert_data = alert.model_dump(mode='json')
    record = AlertRecord(**alert_data)
    if hasattr(alert, "created_at") and alert.created_at:
        record.created_at = alert.created_at
    session.merge(record)
    session.commit()

def load_alerts(session: Session) -> list[EarlyWarning]:
    records = session.query(AlertRecord).all()
    alerts = []
    for r in records:
        d = r.__dict__.copy()
        d.pop('_sa_instance_state', None)
        try:
            alerts.append(EarlyWarning(**d))
        except Exception as e:
            logger.warning("Failed to reconstruct alert %s: %s", d.get("warning_id", "?"), e)
    return alerts


def save_live_status(session: Session, statuses: list[LiveTrainStatus]):
    """Upsert live RailRadar train status rows."""
    for s in statuses:
        session.merge(LiveTrainStatusRecord(**s.model_dump()))
    session.commit()


def load_live_status(session: Session) -> list[LiveTrainStatus]:
    records = session.query(LiveTrainStatusRecord).all()
    result = []
    for r in records:
        d = r.__dict__.copy()
        d.pop('_sa_instance_state', None)
        try:
            result.append(LiveTrainStatus(**d))
        except Exception as e:
            logger.warning("Failed to reconstruct live status %s: %s", d.get("train_number", "?"), e)
    return result