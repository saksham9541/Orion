import logging
from datetime import date, time, timedelta
import pytest

from optimizer.cpsat_solver import BlockScheduler, SchedulerConfig
from railopt.models import (
    AssetType,
    BlockType,
    BlockWindow,
    DefectCategory,
    DefectSeverity,
    Department,
    MaintenanceTask,
    Section,
    TrafficDensityClass,
)


def _make_section(section_id="SEC-TEST-1"):
    return Section(
        section_id=section_id,
        corridor_id="COR-TEST-1",
        name="Test Section",
        start_station="STN-A",
        end_station="STN-B",
        start_km=0.0,
        end_km=10.0,
        length_km=10.0,
        max_speed_kmh=110.0,
        is_single_line=False,
        electrified=True,
        traffic_density_class=TrafficDensityClass.B,
        daily_train_count=20,
    )


def _make_window(window_id="BW-TEST-1", section_id="SEC-TEST-1", duration=4.0, max_tasks=1):
    return BlockWindow(
        window_id=window_id,
        corridor_id="COR-TEST-1",
        section_id=section_id,
        date=date.today(),
        start_time=time(1, 0),
        end_time=time(5, 0),
        duration_hours=duration,
        block_type=BlockType.TRAFFIC_BLOCK,
        max_tasks=max_tasks,
        ml_traffic_impact_score=10.0,
    )


def _make_task(
    task_id="TASK-1",
    section_id="SEC-TEST-1",
    duration=2.0,
    criticality=50.0,
    severity=DefectSeverity.MEDIUM,
    is_emergency=False,
):
    sev = DefectSeverity.EMERGENCY if is_emergency else severity
    return MaintenanceTask(
        task_id=task_id,
        department=Department.ENGINEERING,
        asset_type=AssetType.RAIL,
        defect_category=DefectCategory.RAIL_FRACTURE if is_emergency else DefectCategory.RAIL_CRACK,
        corridor_id="COR-TEST-1",
        section_id=section_id,
        km_location=2.0,
        reported_date=date.today() - timedelta(days=2),
        days_overdue=2,
        ml_criticality_score=criticality,
        raw_severity=sev.value,
        ml_predicted_severity=sev,
        ml_predicted_duration_hours=duration,
        estimated_duration_hours=duration,
    )


def test_emergency_beats_higher_criticality_normal_task():
    """An emergency task with lower criticality beats a higher-criticality normal task for a single-slot window."""
    section = _make_section("SEC-TEST-1")
    # Single-slot window (max_tasks=1)
    window = _make_window("BW-1", section_id="SEC-TEST-1", duration=4.0, max_tasks=1)

    # Normal task with very high criticality score
    normal_task = _make_task(
        task_id="TASK-NORMAL-HIGH-CRIT",
        section_id="SEC-TEST-1",
        duration=2.0,
        criticality=100.0,
        severity=DefectSeverity.HIGH,
        is_emergency=False,
    )

    # Emergency task with very low criticality score
    emergency_task = _make_task(
        task_id="TASK-EMERGENCY-LOW-CRIT",
        section_id="SEC-TEST-1",
        duration=2.0,
        criticality=1.0,
        is_emergency=True,
    )

    scheduler = BlockScheduler(config=SchedulerConfig(time_limit_seconds=10, emergency_must_schedule=True))
    plan = scheduler.solve(
        tasks=[normal_task, emergency_task],
        windows=[window],
        sections={"SEC-TEST-1": section},
    )

    scheduled_ids = [tid for b in plan.scheduled_blocks for tid in b.task_ids]
    assert "TASK-EMERGENCY-LOW-CRIT" in scheduled_ids, "Emergency task must be scheduled even with low criticality"
    assert "TASK-NORMAL-HIGH-CRIT" not in scheduled_ids, "Normal task must be displaced in a single-slot window"
    assert "TASK-NORMAL-HIGH-CRIT" in plan.deferred_task_ids


def test_emergency_task_with_no_compatible_window(caplog):
    """An emergency task with no compatible window must be logged with logger.warning and exposed in plan output."""
    section = _make_section("SEC-TEST-1")
    # Window is on a different section, so emergency task on SEC-TEST-1 has no compatible window
    window = _make_window("BW-OTHER", section_id="SEC-OTHER", duration=4.0, max_tasks=5)

    emergency_task = _make_task(
        task_id="TASK-EMERG-NO-WINDOW",
        section_id="SEC-TEST-1",
        duration=2.0,
        criticality=80.0,
        is_emergency=True,
    )

    scheduler = BlockScheduler(config=SchedulerConfig(time_limit_seconds=5, emergency_must_schedule=True))
    with caplog.at_level(logging.WARNING):
        plan = scheduler.solve(
            tasks=[emergency_task],
            windows=[window],
            sections={"SEC-TEST-1": section, "SEC-OTHER": _make_section("SEC-OTHER")},
        )

    # Check warning was logged
    assert any("TASK-EMERG-NO-WINDOW" in rec.message and "no compatible" in rec.message for rec in caplog.records)
    # Check exposed in plan output
    assert "TASK-EMERG-NO-WINDOW" in plan.deferred_task_ids
    assert any("TASK-EMERG-NO-WINDOW" in w for w in plan.warnings)


def test_emergency_fallback_when_hard_infeasible():
    """If hard constraint makes model infeasible, falls back to soft version with a warning."""
    section = _make_section("SEC-TEST-1")
    # Only 1 task can fit
    window = _make_window("BW-1", section_id="SEC-TEST-1", duration=4.0, max_tasks=1)

    # 2 emergency tasks competing for the same single slot
    emerg1 = _make_task("EMERG-1", section_id="SEC-TEST-1", duration=2.0, criticality=50.0, is_emergency=True)
    emerg2 = _make_task("EMERG-2", section_id="SEC-TEST-1", duration=2.0, criticality=40.0, is_emergency=True)

    scheduler = BlockScheduler(config=SchedulerConfig(time_limit_seconds=10, emergency_must_schedule=True))
    plan = scheduler.solve(
        tasks=[emerg1, emerg2],
        windows=[window],
        sections={"SEC-TEST-1": section},
    )

    # Infeasible as hard constraint, so it falls back to soft penalty
    scheduled_ids = [tid for b in plan.scheduled_blocks for tid in b.task_ids]
    assert len(scheduled_ids) == 1
    assert any("infeasible" in w.lower() for w in plan.warnings)


def test_solve_does_not_mutate_config_time_limit():
    """Consecutive solve() calls must not leak the time_limit_seconds override to self.config."""
    config = SchedulerConfig(time_limit_seconds=60)
    scheduler = BlockScheduler(config=config)
    assert scheduler.config.time_limit_seconds == 60

    section = _make_section("SEC-TEST-1")
    window = _make_window("BW-1", section_id="SEC-TEST-1")
    task = _make_task("TASK-1", section_id="SEC-TEST-1")

    # Call 1 with override
    scheduler.solve(tasks=[task], windows=[window], sections={"SEC-TEST-1": section}, time_limit_seconds=5)
    assert scheduler.config.time_limit_seconds == 60, "First solve() mutated self.config.time_limit_seconds"

    # Call 2 without override
    scheduler.solve(tasks=[task], windows=[window], sections={"SEC-TEST-1": section})
    assert scheduler.config.time_limit_seconds == 60, "Second solve() saw mutated time_limit_seconds"

