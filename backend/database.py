import datetime
import logging
import os
import time
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    create_engine,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from railopt.models import (
    BlockPlan,
    BlockResponse,
    Corridor,
    DefectSeverity,
    EarlyWarning,
    LiveTrainStatus,
    MaintenanceTask,
    TaskStatus,
)

logger = logging.getLogger(__name__)

Base = declarative_base()

def utc_now() -> datetime.datetime:
    """Returns timezone-aware current UTC datetime."""
    return datetime.datetime.now(datetime.timezone.utc)

# Uses JSONB on PostgreSQL for indexing and speed, falls back to JSON on SQLite
JSON_TYPE = JSON().with_variant(JSONB, "postgresql")


class TaskRecord(Base):
    __tablename__ = 'tasks'
    task_id = Column(String, primary_key=True)
    source_system = Column(String)
    source_record_id = Column(String)
    source = Column(String(20), default="synthetic", nullable=False, index=True)  # "synthetic" | "user"
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
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    chainage_km = Column(Float, nullable=True)
    reported_date = Column(Date)
    due_date = Column(Date, nullable=True)
    days_overdue = Column(Integer)
    inspector_remarks = Column(Text)
    is_safety_critical = Column(Boolean)
    requires_power_block = Column(Boolean)
    requires_traffic_block = Column(Boolean)
    crew_size_required = Column(Integer)
    tools_special = Column(JSON_TYPE)
    asset_age_years = Column(Float)
    historical_failure_count = Column(Integer)
    last_maintenance_date = Column(Date, nullable=True)
    ml_criticality_score = Column(Float)
    ml_predicted_severity = Column(String, nullable=True)
    ml_predicted_duration_hours = Column(Float)
    ml_duration_confidence_lower = Column(Float)
    ml_duration_confidence_upper = Column(Float)
    ml_shap_values = Column(JSON_TYPE)
    estimated_duration_hours = Column(Float)
    status = Column(String)
    assigned_block_id = Column(String, nullable=True)
    deferred_count = Column(Integer)
    department_designated = Column(String(50), nullable=True)
    created_by = Column(String(100), nullable=True)
    created_by_department = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=True)


class BlockPlanRecord(Base):
    __tablename__ = 'plans'
    plan_id = Column(String, primary_key=True)
    source = Column(String(20), default="synthetic", nullable=False, index=True)  # "synthetic" | "user"
    horizon = Column(String)
    start_date = Column(Date)
    end_date = Column(Date)
    created_at = Column(DateTime)
    scheduled_blocks = Column(JSON_TYPE)
    total_tasks_scheduled = Column(Integer)
    total_tasks_deferred = Column(Integer)
    total_block_hours = Column(Float)
    total_merge_savings_hours = Column(Float)
    total_trains_affected = Column(Integer)
    sla_compliance_pct = Column(Float)
    departments_summary = Column(JSON_TYPE)
    deferred_task_ids = Column(JSON_TYPE)
    escalated_task_ids = Column(JSON_TYPE)
    solver_status = Column(String)
    solve_time_ms = Column(Float)
    status = Column(String)
    approved_by = Column(String)
    override_log = Column(JSON_TYPE)


class BlockResponseRecord(Base):
    __tablename__ = 'block_responses'
    id = Column(String(36), primary_key=True)
    plan_id = Column(String(64), index=True, nullable=False)
    block_id = Column(String(64), index=True, nullable=False)
    department = Column(String(32), nullable=False)
    decision = Column(String(16), nullable=False)  # "ACCEPT" | "REJECT" | "COUNTER"
    counter_window_id = Column(String(64), nullable=True)
    reason = Column(Text, nullable=True)
    reason_code = Column(String(64), nullable=True)
    decided_by_user_id = Column(String(36), nullable=False)
    decided_by_name = Column(String(128), nullable=True)
    decided_at = Column(DateTime, default=utc_now, nullable=False)


class CorridorRecord(Base):
    __tablename__ = 'corridors'
    corridor_id = Column(String, primary_key=True)
    source = Column(String(20), default="synthetic", nullable=False, index=True)  # "synthetic" | "user"
    name = Column(String)
    division = Column(String)
    zone = Column(String)
    sections = Column(JSON_TYPE)
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
    trend_data = Column(JSON_TYPE)
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


class LiveDelaySnapshotRecord(Base):
    __tablename__ = 'live_delay_snapshots'
    id = Column(Integer, primary_key=True, autoincrement=True)
    train_number = Column(String, index=True, nullable=False)
    train_name = Column(String, nullable=True)
    corridor_id = Column(String, nullable=True)
    section_id = Column(String, nullable=True)
    delay_minutes = Column(Float, default=0.0)
    status = Column(String, default="RUNNING")
    snapshot_timestamp = Column(DateTime, default=utc_now, nullable=False, index=True)
    source = Column(String, default="LIVE_SYNC")


class ApiUsageRecord(Base):
    __tablename__ = 'api_usage'
    id = Column(Integer, primary_key=True, autoincrement=True)
    key_suffix = Column(String(10), index=True)
    year_month = Column(String(7), index=True)  # YYYY-MM
    endpoint = Column(String)
    timestamp = Column(DateTime, default=utc_now)
    status_code = Column(Integer)
    success = Column(Boolean)


class ApiCacheRecord(Base):
    __tablename__ = 'api_cache'
    cache_key = Column(String, primary_key=True)
    endpoint = Column(String)
    data = Column(JSON_TYPE)
    meta = Column(JSON_TYPE, nullable=True)
    created_at = Column(DateTime, default=utc_now)
    expires_at = Column(DateTime, index=True)


class UserRecord(Base):
    __tablename__ = 'users'
    id = Column(String(36), primary_key=True)
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False)  # ADMIN, CONTROLLER, DEPT_USER, VIEWER
    department = Column(String(20), nullable=True)  # ENGINEERING, SNT, TRD
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    last_login_at = Column(DateTime, nullable=True)


class NotificationRecord(Base):
    __tablename__ = 'notifications'
    id = Column(String(36), primary_key=True)
    issue_id = Column(String, nullable=True, index=True)
    recipient_user_id = Column(String(36), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    type = Column(String(50), default="ISSUE_RAISED", nullable=False)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    severity = Column(String(20), nullable=False)  # EMERGENCY, HIGH, MEDIUM, LOW
    created_at = Column(DateTime, default=utc_now, nullable=False)
    read_at = Column(DateTime, nullable=True)
    acknowledged_at = Column(DateTime, nullable=True)



class LoginAttemptRecord(Base):
    __tablename__ = 'login_attempts'
    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), index=True, nullable=False)
    ip_address = Column(String(45), nullable=True)
    attempted_at = Column(DateTime, default=utc_now, nullable=False)
    success = Column(Boolean, default=False, nullable=False)


def get_database_url() -> str:
    """Retrieve normalized database URL, defaulting to local SQLite for tests."""
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        return "sqlite:///railopt.db"

    # Normalize postgres:// to postgresql://
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]

    # Specify psycopg3 driver if unspecified generic postgresql
    if url.startswith("postgresql://") and not url.startswith("postgresql+"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]

    # Neon requirement: sslmode=require for non-local connections
    if "sslmode=" not in url and "localhost" not in url and "127.0.0.1" not in url and not url.startswith("sqlite"):
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}sslmode=require"

    return url


def get_engine(db_url: Optional[str] = None):
    """
    Create SQLAlchemy engine.
    For PostgreSQL/Neon: handles connection pre-pinging and connection pool recycling.
    For SQLite: configures single-file/thread args for tests.
    """
    url = db_url or get_database_url()
    if url.startswith("sqlite"):
        return create_engine(
            url,
            connect_args={"check_same_thread": False},
            pool_pre_ping=True,
        )
    return create_engine(
        url,
        pool_pre_ping=True,   # Pings connection before checkout; revives sleeping Neon instances
        pool_recycle=300,     # Recycles connection after 5 minutes
        pool_timeout=30,
        max_overflow=10,
    )


def check_connection_with_retry(engine, max_retries: int = 1, delay_s: float = 2.0) -> bool:
    """Check database connection, retrying once if Neon was asleep/cold."""
    for attempt in range(max_retries + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception as e:
            if attempt < max_retries:
                logger.warning("Database connection failed (Neon waking up?). Retrying in %.1fs: %s", delay_s, e)
                time.sleep(delay_s)
            else:
                logger.error("Database connection failed after retry: %s", e)
                raise


def seed_default_users(session: Session):
    """Ensures standard department and admin users exist for login and alert routing."""
    from backend.auth import hash_password
    default_users = [
        ("usr_admin_1", "admin@railopt.gov.in", "Super Admin", "ADMIN", None),
        ("usr_eng_1", "eng@railopt.gov.in", "Engineering Officer", "DEPT_USER", "ENGINEERING"),
        ("usr_snt_1", "snt@railopt.gov.in", "S&T Officer", "DEPT_USER", "SNT"),
        ("usr_trd_1", "trd@railopt.gov.in", "TRD Officer", "DEPT_USER", "TRD"),
        ("usr_tech_1", "tech@railopt.gov.in", "Track Technician", "DEPT_USER", "ENGINEERING"),
    ]
    for uid, email, name, role, dept in default_users:
        existing = session.query(UserRecord).filter(UserRecord.email == email).first()
        if not existing:
            session.add(
                UserRecord(
                    id=uid,
                    name=name,
                    email=email,
                    password_hash=hash_password("password123"),
                    role=role,
                    department=dept,
                    is_active=True,
                )
            )
    session.commit()


def init_db(engine):
    """Initializes tables and seeds default users; safe for both SQLite and PostgreSQL."""
    Base.metadata.create_all(engine)
    url = str(engine.url)
    if url.startswith("sqlite"):
        # Ensure newer columns exist on existing local SQLite databases
        with engine.connect() as conn:
            for table, col, col_type in [
                ("corridors", "source", "VARCHAR(20) DEFAULT 'synthetic'"),
                ("tasks", "source", "VARCHAR(20) DEFAULT 'synthetic'"),
                ("tasks", "latitude", "FLOAT"),
                ("tasks", "longitude", "FLOAT"),
                ("tasks", "chainage_km", "FLOAT"),
                ("plans", "source", "VARCHAR(20) DEFAULT 'synthetic'"),
                ("login_attempts", "ip_address", "VARCHAR(64)"),
                ("api_usage", "key_suffix", "VARCHAR(16)"),
            ]:
                try:
                    res = conn.execute(text(f"PRAGMA table_info({table})"))
                    cols = [r[1] for r in res.fetchall()]
                    if cols and col not in cols:
                        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"))
                        conn.commit()
                except Exception as e:
                    logger.debug("Column migration skipped for %s.%s: %s", table, col, e)
        # Ensure default department users are seeded
        try:
            SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
            with SessionLocal() as s:
                seed_default_users(s)
        except Exception as e:
            logger.debug("Default user seeding skipped: %s", e)


def get_session(engine=None):
    if engine is None:
        engine = get_engine()
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
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
        if hasattr(t, "created_at") and t.created_at:
            task_data["created_at"] = t.created_at
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
    valid_cols = {c.name for c in BlockPlanRecord.__table__.columns}
    record = BlockPlanRecord(**{k: v for k, v in plan_data.items() if k in valid_cols})
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


def save_block_response(session: Session, response: BlockResponse):
    """Save or update department response to a scheduled block."""
    d = response.model_dump(mode='json')
    if hasattr(response, "decided_at") and response.decided_at:
        d["decided_at"] = response.decided_at
    session.merge(BlockResponseRecord(**d))
    session.commit()


def load_block_responses(session: Session, plan_id: str) -> list[BlockResponse]:
    """Load all department block responses for a plan."""
    records = session.query(BlockResponseRecord).filter(BlockResponseRecord.plan_id == plan_id).all()
    responses = []
    for r in records:
        d = r.__dict__.copy()
        d.pop('_sa_instance_state', None)
        try:
            responses.append(BlockResponse(**d))
        except Exception as e:
            logger.warning("Failed to parse BlockResponse %s: %s", d.get("id"), e)
    return responses

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


def save_delay_snapshots(session: Session, snapshots: list[dict]):
    """Persist historical live delay snapshots for honest ML training."""
    for s in snapshots:
        record = LiveDelaySnapshotRecord(**s)
        session.add(record)
    session.commit()


def load_delay_snapshots(session: Session, min_records: int = 100) -> list[LiveDelaySnapshotRecord]:
    """Retrieve historical delay snapshots from database."""
    return session.query(LiveDelaySnapshotRecord).all()


def record_api_usage(
    session: Session,
    key_suffix: str,
    endpoint: str,
    status_code: int,
    success: bool,
    year_month: Optional[str] = None,
) -> None:
    """Record an API request in api_usage table for monthly budget tracking."""
    if not year_month:
        year_month = utc_now().strftime("%Y-%m")
    record = ApiUsageRecord(
        key_suffix=key_suffix,
        year_month=year_month,
        endpoint=endpoint,
        status_code=status_code,
        success=success,
        timestamp=utc_now(),
    )
    session.add(record)
    session.commit()


def get_api_usage_count(
    session: Session,
    key_suffix: str,
    year_month: Optional[str] = None,
) -> int:
    """Get the request count for a given key_suffix in a calendar month."""
    if not year_month:
        year_month = utc_now().strftime("%Y-%m")
    count = (
        session.query(func.count(ApiUsageRecord.id))
        .filter(
            ApiUsageRecord.key_suffix == key_suffix,
            ApiUsageRecord.year_month == year_month,
        )
        .scalar()
    )
    return count or 0


def get_all_key_usages(
    session: Session,
    year_month: Optional[str] = None,
) -> dict[str, int]:
    """Get request counts grouped by key_suffix for a calendar month."""
    if not year_month:
        year_month = utc_now().strftime("%Y-%m")
    rows = (
        session.query(ApiUsageRecord.key_suffix, func.count(ApiUsageRecord.id))
        .filter(ApiUsageRecord.year_month == year_month)
        .group_by(ApiUsageRecord.key_suffix)
        .all()
    )
    return {row[0]: row[1] for row in rows}


def get_api_cache(session: Session, cache_key: str) -> Optional[dict]:
    """Retrieve an unexpired cached API response."""
    now = utc_now()
    record = (
        session.query(ApiCacheRecord)
        .filter(
            ApiCacheRecord.cache_key == cache_key,
            ApiCacheRecord.expires_at > now,
        )
        .first()
    )
    if record:
        return {
            "data": record.data,
            "meta": record.meta,
            "cached_at": record.created_at.isoformat() if record.created_at else None,
            "expires_at": record.expires_at.isoformat() if record.expires_at else None,
        }
    return None


def set_api_cache(
    session: Session,
    cache_key: str,
    endpoint: str,
    data: dict | list,
    meta: Optional[dict] = None,
    ttl_seconds: int = 600,
) -> None:
    """Upsert a cached API response with TTL in seconds."""
    now = utc_now()
    expires_at = now + datetime.timedelta(seconds=ttl_seconds)
    record = ApiCacheRecord(
        cache_key=cache_key,
        endpoint=endpoint,
        data=data,
        meta=meta,
        created_at=now,
        expires_at=expires_at,
    )
    session.merge(record)
    session.commit()


# ──────────────────────────────────────────────────────────────────────
# User & Authentication Queries
# ──────────────────────────────────────────────────────────────────────

def get_user_by_email(session: Session, email: str) -> Optional[UserRecord]:
    return session.query(UserRecord).filter(func.lower(UserRecord.email) == email.strip().lower()).first()


def get_user_by_id(session: Session, user_id: str) -> Optional[UserRecord]:
    return session.query(UserRecord).filter(UserRecord.id == user_id).first()


def save_user(session: Session, user: UserRecord) -> UserRecord:
    session.merge(user)
    session.commit()
    return user


def update_last_login(session: Session, user_id: str) -> None:
    user = session.query(UserRecord).filter(UserRecord.id == user_id).first()
    if user:
        user.last_login_at = utc_now()
        session.commit()


def record_login_attempt(session: Session, email: str, ip_address: Optional[str], success: bool) -> None:
    attempt = LoginAttemptRecord(
        email=email.strip().lower(),
        ip_address=ip_address.strip() if ip_address else None,
        attempted_at=utc_now(),
        success=success,
    )
    session.add(attempt)
    session.commit()


def get_failed_login_count(
    session: Session,
    email: Optional[str] = None,
    ip_address: Optional[str] = None,
    window_minutes: int = 15,
) -> int:
    cutoff = utc_now() - datetime.timedelta(minutes=window_minutes)
    query = session.query(func.count(LoginAttemptRecord.id)).filter(
        LoginAttemptRecord.success == False,
        LoginAttemptRecord.attempted_at >= cutoff,
    )
    if email:
        query = query.filter(func.lower(LoginAttemptRecord.email) == email.strip().lower())
    if ip_address:
        query = query.filter(LoginAttemptRecord.ip_address == ip_address.strip())
    count = query.scalar()
    return count or 0


def clear_failed_login_attempts(
    session: Session,
    email: str,
    ip_address: Optional[str] = None,
) -> None:
    query = session.query(LoginAttemptRecord).filter(
        func.lower(LoginAttemptRecord.email) == email.strip().lower(),
        LoginAttemptRecord.success == False,
    )
    if ip_address:
        query = query.filter(LoginAttemptRecord.ip_address == ip_address.strip())
    query.delete(synchronize_session=False)
    session.commit()


# ──────────────────────────────────────────────────────────────────────
# Notifications
# ──────────────────────────────────────────────────────────────────────

def save_notification(session: Session, notification: NotificationRecord) -> NotificationRecord:
    session.add(notification)
    session.commit()
    session.refresh(notification)
    return notification


def get_user_notifications(
    session: Session,
    user_id: str,
    unread_only: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> list[NotificationRecord]:
    query = session.query(NotificationRecord).filter(
        NotificationRecord.recipient_user_id == user_id
    )
    if unread_only:
        query = query.filter(NotificationRecord.read_at.is_(None))
    
    query = query.order_by(
        NotificationRecord.read_at.is_(None).desc(),
        NotificationRecord.created_at.desc(),
    )
    return query.offset(offset).limit(limit).all()


def get_unread_notification_count(session: Session, user_id: str) -> int:
    count = session.query(func.count(NotificationRecord.id)).filter(
        NotificationRecord.recipient_user_id == user_id,
        NotificationRecord.read_at.is_(None),
    ).scalar()
    return count or 0


def mark_notification_read(session: Session, notification_id: str, user_id: str) -> Optional[NotificationRecord]:
    notif = session.query(NotificationRecord).filter(
        NotificationRecord.id == notification_id,
        NotificationRecord.recipient_user_id == user_id,
    ).first()
    if notif:
        if notif.read_at is None:
            notif.read_at = utc_now()
            session.commit()
            session.refresh(notif)
    return notif


def acknowledge_notification(session: Session, notification_id: str, user_id: str) -> Optional[NotificationRecord]:
    notif = session.query(NotificationRecord).filter(
        NotificationRecord.id == notification_id,
        NotificationRecord.recipient_user_id == user_id,
    ).first()
    if notif:
        now = utc_now()
        notif.acknowledged_at = now
        if notif.read_at is None:
            notif.read_at = now
        session.commit()
        session.refresh(notif)
    return notif
