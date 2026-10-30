from datetime import date
from alembic.config import Config
from alembic import command
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from backend.database import (
    TaskRecord,
    BlockPlanRecord,
    CorridorRecord,
    AlertRecord,
    UserRecord,
    LoginAttemptRecord,
    ApiUsageRecord,
    ApiCacheRecord,
    LiveTrainStatusRecord,
    NotificationRecord,
    RevalidationResultRecord,
    TaskTransitionAuditRecord,
    utc_now,
)


def test_alembic_upgrade_head_on_fresh_sqlite_and_crud(tmp_path, monkeypatch):
    """
    Test alembic upgrade head against a fresh SQLite database,
    verify that all tables and columns are created properly,
    and save/load one row of each model.
    """
    db_file = tmp_path / "fresh_migrated.db"
    db_url = f"sqlite:///{db_file}"
    monkeypatch.setenv("DATABASE_URL", db_url)

    # 1. Run alembic upgrade head
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(alembic_cfg, "head")

    # 2. Inspect created tables and columns
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    expected_tables = {
        "tasks",
        "plans",
        "corridors",
        "alerts",
        "users",
        "login_attempts",
        "api_usage",
        "api_cache",
        "live_train_status",
        "notifications",
        "revalidation_results",
        "task_transition_audits",
    }
    for t in expected_tables:
        assert t in tables, f"Expected table '{t}' was not created by alembic migration"

    # Verify specific requested columns
    tasks_cols = {c["name"] for c in inspector.get_columns("tasks")}
    assert "source" in tasks_cols
    assert "acknowledged_by" in tasks_cols
    assert "declined_by" in tasks_cols
    assert "awaiting_acknowledgement" in tasks_cols

    notif_cols = {c["name"] for c in inspector.get_columns("notifications")}
    assert "resolved_at" in notif_cols
    assert "resolved_by" in notif_cols
    assert "action_taken" in notif_cols

    plans_cols = {c["name"] for c in inspector.get_columns("plans")}
    assert "source" in plans_cols

    api_usage_cols = {c["name"] for c in inspector.get_columns("api_usage")}
    assert "key_suffix" in api_usage_cols

    login_attempts_cols = {c["name"] for c in inspector.get_columns("login_attempts")}
    assert "ip_address" in login_attempts_cols

    corridors_cols = {c["name"] for c in inspector.get_columns("corridors")}
    assert "source" in corridors_cols

    # 3. Save and load one row of each model
    Session = sessionmaker(bind=engine)
    session = Session()

    now = utc_now()
    today = date.today()

    task = TaskRecord(
        task_id="TSK-ALEMBIC-1",
        source="synthetic",
        department="ENGINEERING",
        asset_type="RAIL",
        reported_date=today,
    )
    plan = BlockPlanRecord(
        plan_id="PLN-ALEMBIC-1",
        source="user",
        horizon="WEEKLY",
        start_date=today,
        end_date=today,
        created_at=now,
    )
    corridor = CorridorRecord(
        corridor_id="COR-ALEMBIC-1",
        source="synthetic",
        name="Delhi-Agra",
        division="Delhi",
        zone="Northern",
        sections=[],
        total_length_km=200.0,
        is_rajdhani_route=True,
    )
    alert = AlertRecord(
        warning_id="ALT-ALEMBIC-1",
        corridor_id="COR-ALEMBIC-1",
        section_id="SEC-1",
        asset_type="RAIL",
        risk_level="HIGH",
        message="Rail fatigue detected",
        trend_data={},
        recommended_action="Inspect joint",
        estimated_failure_window_days=7,
        created_at=now,
    )
    user = UserRecord(
        id="usr_alembic_1",
        name="Test User",
        email="test@alembic.gov.in",
        password_hash="fakehash",
        role="CONTROLLER",
        department=None,
        is_active=True,
        created_at=now,
    )
    login_attempt = LoginAttemptRecord(
        email="test@alembic.gov.in",
        ip_address="192.168.1.1",
        attempted_at=now,
        success=True,
    )
    usage = ApiUsageRecord(
        key_suffix="1234abcd",
        year_month="2026-10",
        endpoint="/trains/12301",
        timestamp=now,
        status_code=200,
        success=True,
    )
    cache = ApiCacheRecord(
        cache_key="test_cache_key",
        endpoint="/trains/12301",
        data={"route": "Delhi-Howrah"},
        meta={"source": "live"},
        created_at=now,
        expires_at=now,
    )
    train_status = LiveTrainStatusRecord(
        train_number="12301",
        train_name="Howrah Rajdhani",
        corridor_id="COR-ALEMBIC-1",
        section_id="SEC-1",
        delay_minutes=5.0,
        status="RUNNING",
        last_updated=now,
        source="live",
    )
    notification = NotificationRecord(
        id="notif_alembic_1",
        issue_id="TSK-ALEMBIC-1",
        recipient_user_id="usr_alembic_1",
        type="ISSUE_RAISED",
        title="Test Notification",
        message="A test issue has been raised",
        severity="HIGH",
        created_at=now,
    )

    reval = RevalidationResultRecord(
        id="rev-alembic-1",
        task_id="TSK-ALEMBIC-1",
        window_id="WIN-1",
        block_section_id="BLK-1",
        checked_at=now,
        horizon="T-1h",
        is_valid=True,
        status="CLEAN",
        confidence="HIGH",
        stale_status=False,
        status_age_hours=0.5,
        has_conflict=False,
    )
    audit = TaskTransitionAuditRecord(
        id="aud-alembic-1",
        task_id="TSK-ALEMBIC-1",
        from_status="APPROVED",
        to_status="READY",
        changed_by_user_id="usr_alembic_1",
        changed_by_role="TECHNICIAN",
        changed_by_department="ENGINEERING",
        timestamp=now,
    )

    records = [task, plan, corridor, alert, user, login_attempt, usage, cache, train_status, notification, reval, audit]
    for r in records:
        session.add(r)
    session.commit()

    # Verify query for each row
    assert session.query(TaskRecord).filter_by(task_id="TSK-ALEMBIC-1").first() is not None
    assert session.query(RevalidationResultRecord).filter_by(id="rev-alembic-1").first().confidence == "HIGH"
    assert session.query(TaskTransitionAuditRecord).filter_by(id="aud-alembic-1").first().to_status == "READY" 
    assert session.query(BlockPlanRecord).filter_by(plan_id="PLN-ALEMBIC-1").first().source == "user"
    assert session.query(CorridorRecord).filter_by(corridor_id="COR-ALEMBIC-1").first().source == "synthetic"
    assert session.query(AlertRecord).filter_by(warning_id="ALT-ALEMBIC-1").first() is not None
    assert session.query(UserRecord).filter_by(id="usr_alembic_1").first() is not None
    assert session.query(LoginAttemptRecord).filter_by(email="test@alembic.gov.in").first().ip_address == "192.168.1.1"
    assert session.query(ApiUsageRecord).filter_by(key_suffix="1234abcd").first() is not None
    assert session.query(ApiCacheRecord).filter_by(cache_key="test_cache_key").first() is not None
    assert session.query(LiveTrainStatusRecord).filter_by(train_number="12301").first() is not None
    assert session.query(NotificationRecord).filter_by(id="notif_alembic_1").first().severity == "HIGH"


    session.close()
