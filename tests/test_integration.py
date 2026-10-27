"""
RailOpt — End-to-end integration tests.

Tests the full pipeline: synthetic data → ML scoring → optimization →
block merging → SLA → briefing generation.
"""

import pytest
from datetime import date, time, timedelta

from railopt.models import (
    BlockPlan,
    BlockType,
    BlockWindow,
    Corridor,
    DefectCategory,
    DefectSeverity,
    Department,
    MaintenanceTask,
    PlanHorizon,
    ScheduledBlock,
    Section,
    TaskStatus,
    TrafficDensityClass,
    ALWAYS_EMERGENCY,
    SAFETY_CRITICAL_DEFECTS,
    MAX_DEFERRAL_HOURS,
)


# ──────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────

def _make_section(
    section_id: str = "SEC-001",
    corridor_id: str = "COR-001",
    start_km: float = 0.0,
    end_km: float = 10.0,
) -> Section:
    return Section(
        section_id=section_id,
        corridor_id=corridor_id,
        name="Test Section",
        start_station="Station A",
        end_station="Station B",
        start_km=start_km,
        end_km=end_km,
        traffic_density_class=TrafficDensityClass.B,
        daily_train_count=30,
    )


def _make_task(
    task_id: str = "MT-test001",
    department: Department = Department.ENGINEERING,
    defect_category: DefectCategory = DefectCategory.RAIL_CRACK,
    section_id: str = "SEC-001",
    corridor_id: str = "COR-001",
    days_overdue: int = 10,
    criticality: float = 60.0,
    duration: float = 2.0,
    severity: DefectSeverity = DefectSeverity.MEDIUM,
) -> MaintenanceTask:
    from railopt.models import AssetType
    return MaintenanceTask(
        task_id=task_id,
        department=department,
        asset_type=AssetType.RAIL,
        defect_category=defect_category,
        corridor_id=corridor_id,
        section_id=section_id,
        km_location=5.0,
        reported_date=date.today() - timedelta(days=days_overdue),
        days_overdue=days_overdue,
        ml_criticality_score=criticality,
        ml_predicted_severity=severity,
        ml_predicted_duration_hours=duration,
        estimated_duration_hours=duration,
    )


def _make_window(
    window_id: str = "BW-001",
    section_id: str = "SEC-001",
    corridor_id: str = "COR-001",
    date_val: date = None,
    duration: float = 4.0,
    impact: float = 20.0,
) -> BlockWindow:
    d = date_val or date.today()
    return BlockWindow(
        window_id=window_id,
        corridor_id=corridor_id,
        section_id=section_id,
        date=d,
        start_time=time(1, 0),
        end_time=time(5, 0),
        duration_hours=duration,
        ml_traffic_impact_score=impact,
        ml_trains_affected=3,
    )


# ──────────────────────────────────────────────────────────────────────
# Model Tests
# ──────────────────────────────────────────────────────────────────────

class TestModels:
    """Validate domain model behavior."""

    def test_section_length_auto(self):
        s = _make_section(start_km=100.0, end_km=115.0)
        assert s.length_km == 15.0

    def test_task_safety_critical_auto(self):
        t = _make_task(defect_category=DefectCategory.RAIL_FRACTURE)
        assert t.is_safety_critical is True

    def test_task_trd_power_block(self):
        from railopt.models import AssetType
        t = MaintenanceTask(
            department=Department.TRD,
            asset_type=AssetType.OHE_WIRE,
            defect_category=DefectCategory.OHE_BREAK,
            corridor_id="COR-001",
            section_id="SEC-001",
            km_location=5.0,
            reported_date=date.today(),
        )
        assert t.requires_power_block is True

    def test_window_duration_auto(self):
        w = BlockWindow(
            corridor_id="COR-001",
            section_id="SEC-001",
            date=date.today(),
            start_time=time(1, 0),
            end_time=time(5, 0),
        )
        assert w.duration_hours == 4.0

    def test_window_midnight_crossing(self):
        w = BlockWindow(
            corridor_id="COR-001",
            section_id="SEC-001",
            date=date.today(),
            start_time=time(23, 0),
            end_time=time(3, 0),
        )
        assert w.duration_hours == 4.0

    def test_block_plan_metrics(self):
        plan = BlockPlan(
            horizon=PlanHorizon.WEEKLY,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=7),
            scheduled_blocks=[
                ScheduledBlock(
                    window_id="BW-001",
                    corridor_id="COR-001",
                    section_id="SEC-001",
                    date=date.today(),
                    start_time=time(1, 0),
                    end_time=time(5, 0),
                    duration_hours=4.0,
                    task_ids=["MT-001", "MT-002"],
                    departments=[Department.ENGINEERING],
                    merge_savings_hours=2.0,
                    trains_affected=5,
                ),
            ],
        )
        tasks = [
            _make_task("MT-001", criticality=80, severity=DefectSeverity.HIGH),
            _make_task("MT-002", criticality=40),
        ]
        tasks[0].status = TaskStatus.SCHEDULED
        tasks[1].status = TaskStatus.SCHEDULED
        plan.compute_metrics(tasks)
        assert plan.total_tasks_scheduled == 2
        assert plan.total_block_hours == 4.0
        assert plan.total_merge_savings_hours == 2.0
        assert plan.total_trains_affected == 5


# ──────────────────────────────────────────────────────────────────────
# SLA Engine Tests
# ──────────────────────────────────────────────────────────────────────

class TestSLAEngine:
    """Validate SLA enforcement."""

    def test_escalate_overdue(self):
        from optimizer.sla_engine import SLAEngine

        engine = SLAEngine()
        task = _make_task(
            days_overdue=8,
            severity=DefectSeverity.HIGH,
        )
        # HIGH max deferral is 168h (7 days), 8 days = 192h > 168h
        escalated = engine.escalate_overdue([task])
        assert len(escalated) == 1
        assert task.status == TaskStatus.ESCALATED

    def test_no_escalation_within_sla(self):
        from optimizer.sla_engine import SLAEngine

        engine = SLAEngine()
        task = _make_task(
            days_overdue=5,
            severity=DefectSeverity.HIGH,
        )
        escalated = engine.escalate_overdue([task])
        assert len(escalated) == 0

    def test_emergency_force_schedule(self):
        from optimizer.sla_engine import SLAEngine

        engine = SLAEngine()
        task = _make_task(
            defect_category=DefectCategory.RAIL_FRACTURE,
            severity=DefectSeverity.EMERGENCY,
            duration=2.0,
        )
        task.raw_severity = DefectSeverity.EMERGENCY.value
        window = _make_window(duration=4.0)
        forced = engine.force_schedule_emergency([task], [window])
        assert len(forced) >= 1


# ──────────────────────────────────────────────────────────────────────
# Optimizer Tests
# ──────────────────────────────────────────────────────────────────────

class TestOptimizer:
    """Validate CP-SAT scheduler."""

    def test_basic_scheduling(self):
        from optimizer.cpsat_solver import BlockScheduler, SchedulerConfig

        tasks = [
            _make_task("MT-001", criticality=80, duration=1.5),
            _make_task("MT-002", criticality=60, duration=2.0),
        ]
        windows = [
            _make_window("BW-001", duration=4.0),
        ]
        sections = {"SEC-001": _make_section()}

        scheduler = BlockScheduler(config=SchedulerConfig(time_limit_seconds=10))
        plan = scheduler.solve(tasks, windows, sections, time_limit_seconds=10)

        assert len(plan.scheduled_blocks) > 0
        assert plan.total_tasks_scheduled > 0

    def test_emergency_must_schedule(self):
        from optimizer.cpsat_solver import BlockScheduler, SchedulerConfig

        emergency_task = _make_task(
            "MT-EMG",
            defect_category=DefectCategory.RAIL_FRACTURE,
            criticality=98,
            severity=DefectSeverity.EMERGENCY,
            duration=2.0,
        )
        emergency_task.raw_severity = DefectSeverity.EMERGENCY.value
        low_task = _make_task("MT-LOW", criticality=10, duration=1.0)

        windows = [_make_window("BW-001", duration=3.0)]
        sections = {"SEC-001": _make_section()}

        config = SchedulerConfig(
            emergency_must_schedule=True,
            time_limit_seconds=10,
        )
        scheduler = BlockScheduler(config=config)
        plan = scheduler.solve(
            [emergency_task, low_task], windows, sections, time_limit_seconds=10,
        )

        # Emergency MUST be scheduled
        all_scheduled_ids = set()
        for b in plan.scheduled_blocks:
            all_scheduled_ids.update(b.task_ids)
        assert "MT-EMG" in all_scheduled_ids

    def test_section_compatibility(self):
        from optimizer.cpsat_solver import BlockScheduler, SchedulerConfig

        task = _make_task("MT-001", section_id="SEC-999")
        window = _make_window("BW-001", section_id="SEC-001")
        sections = {"SEC-001": _make_section()}

        scheduler = BlockScheduler(config=SchedulerConfig(time_limit_seconds=10))
        plan = scheduler.solve([task], [window], sections, time_limit_seconds=10)

        # Task should NOT be scheduled — wrong section
        all_scheduled_ids = set()
        for b in plan.scheduled_blocks:
            all_scheduled_ids.update(b.task_ids)
        assert "MT-001" not in all_scheduled_ids

    def test_duration_constraint(self):
        from optimizer.cpsat_solver import BlockScheduler, SchedulerConfig

        task = _make_task("MT-LONG", duration=10.0)  # 10h task
        window = _make_window("BW-001", duration=4.0)  # 4h window
        sections = {"SEC-001": _make_section()}

        scheduler = BlockScheduler(config=SchedulerConfig(time_limit_seconds=10))
        plan = scheduler.solve([task], [window], sections, time_limit_seconds=10)

        # Task should NOT fit
        all_scheduled_ids = set()
        for b in plan.scheduled_blocks:
            all_scheduled_ids.update(b.task_ids)
        assert "MT-LONG" not in all_scheduled_ids


# ──────────────────────────────────────────────────────────────────────
# Block Merger Tests
# ──────────────────────────────────────────────────────────────────────

class TestBlockMerger:
    """Validate merge detection and savings calculation."""

    def test_detect_merge(self):
        from optimizer.block_merger import BlockMerger

        plan = BlockPlan(
            horizon=PlanHorizon.WEEKLY,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=7),
            scheduled_blocks=[
                ScheduledBlock(
                    window_id="BW-001",
                    corridor_id="COR-001",
                    section_id="SEC-001",
                    date=date.today(),
                    start_time=time(1, 0),
                    end_time=time(5, 0),
                    duration_hours=4.0,
                    task_ids=["MT-ENG", "MT-SNT"],
                    departments=[Department.ENGINEERING, Department.SNT],
                ),
            ],
        )
        tasks = [
            _make_task("MT-ENG", department=Department.ENGINEERING),
            _make_task("MT-SNT", department=Department.SNT),
        ]

        merger = BlockMerger()
        report = merger.analyze_merge_opportunities(plan, tasks)

        assert report.total_merged_blocks == 1
        assert report.total_hours_saved > 0


# ──────────────────────────────────────────────────────────────────────
# GenAI Layer Tests
# ──────────────────────────────────────────────────────────────────────

class TestBriefingGenerator:
    """Validate briefing generation (template mode)."""

    def test_weekly_briefing(self):
        from genai.briefing_generator import BriefingGenerator

        plan = BlockPlan(
            horizon=PlanHorizon.WEEKLY,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=7),
            total_tasks_scheduled=10,
            total_block_hours=20.0,
            total_merge_savings_hours=4.0,
            sla_compliance_pct=95.0,
            departments_summary={"ENGINEERING": 5, "SNT": 3, "TRD": 2},
        )

        gen = BriefingGenerator(use_llm=False)
        briefing = gen.generate_weekly_briefing(plan, [])

        assert "Weekly" in briefing
        assert "ENGINEERING" in briefing
        assert "95.0%" in briefing


class TestNLQueryEngine:
    """Validate NL query engine (keyword mode)."""

    def test_sla_query(self):
        from genai.nl_query_engine import NLQueryEngine

        plan = BlockPlan(
            horizon=PlanHorizon.WEEKLY,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=7),
            sla_compliance_pct=92.5,
            total_tasks_scheduled=20,
            total_tasks_deferred=3,
        )

        engine = NLQueryEngine(plan, [], [], use_llm=False)
        answer = engine.query("What is the SLA compliance?")

        assert "92.5" in answer

    def test_merged_query(self):
        from genai.nl_query_engine import NLQueryEngine

        plan = BlockPlan(
            horizon=PlanHorizon.WEEKLY,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=7),
            total_merge_savings_hours=6.0,
        )

        engine = NLQueryEngine(plan, [], [], use_llm=False)
        answer = engine.query("Show me merged blocks")

        assert "merged" in answer.lower() or "No merged" in answer

    def test_task_lookup(self):
        from genai.nl_query_engine import NLQueryEngine

        task = _make_task("MT-abc12345", criticality=75, severity=DefectSeverity.HIGH)
        task.status = TaskStatus.SCHEDULED

        plan = BlockPlan(
            horizon=PlanHorizon.WEEKLY,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=7),
            scheduled_blocks=[
                ScheduledBlock(
                    window_id="BW-001",
                    corridor_id="COR-001",
                    section_id="SEC-001",
                    date=date.today(),
                    start_time=time(1, 0),
                    end_time=time(5, 0),
                    duration_hours=4.0,
                    task_ids=["MT-abc12345"],
                    departments=[Department.ENGINEERING],
                ),
            ],
        )

        engine = NLQueryEngine(plan, [task], [], use_llm=False)
        answer = engine.query("Tell me about task MT-abc12345")

        assert "MT-abc12345" in answer
        assert "SCHEDULED" in answer


class TestExplainability:
    """Validate explainability engine (template mode)."""

    def test_criticality_explanation(self):
        from genai.explainability import ExplainabilityEngine

        task = _make_task(criticality=87)
        task.ml_shap_values = {
            "defect_category": 35.2,
            "days_overdue": 25.1,
            "traffic_density_class": 20.3,
            "asset_age_years": 8.7,
        }

        engine = ExplainabilityEngine(use_llm=False)
        explanation = engine.explain_criticality_score(task)

        assert "87" in explanation
        assert "defect_category" in explanation.lower() or "Defect" in explanation

    def test_deferral_explanation(self):
        from genai.explainability import ExplainabilityEngine

        task = _make_task(criticality=15)
        task.status = TaskStatus.DEFERRED
        task.deferred_count = 2

        plan = BlockPlan(
            horizon=PlanHorizon.WEEKLY,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=7),
        )

        engine = ExplainabilityEngine(use_llm=False)
        explanation = engine.explain_deferral(task, plan)

        assert "DEFERRED" in explanation
        assert "2" in explanation


# ──────────────────────────────────────────────────────────────────────
# Synthetic Data Tests
# ──────────────────────────────────────────────────────────────────────

class TestSyntheticData:
    """Validate synthetic data generation."""

    def test_generate_dataset(self):
        from railopt.synthetic_data import generate_full_dataset

        dataset = generate_full_dataset(seed=42, num_tasks=50)

        assert "corridors" in dataset
        assert "sections" in dataset
        assert "tasks" in dataset
        assert "train_slots" in dataset
        assert "block_windows" in dataset

        assert len(dataset["corridors"]) > 0
        assert len(dataset["tasks"]) >= 50
        assert len(dataset["sections"]) > 0

    def test_department_distribution(self):
        from railopt.synthetic_data import generate_full_dataset

        dataset = generate_full_dataset(seed=42, num_tasks=200)
        tasks = dataset["tasks"]

        dept_counts = {}
        for t in tasks:
            d = t.department.value if hasattr(t.department, "value") else t.department
            dept_counts[d] = dept_counts.get(d, 0) + 1

        # Engineering should be most common
        assert dept_counts.get("ENGINEERING", 0) > 0
        assert dept_counts.get("SNT", 0) > 0
        assert dept_counts.get("TRD", 0) > 0


# ──────────────────────────────────────────────────────────────────────
# Integration Pipeline Test
# ──────────────────────────────────────────────────────────────────────

class TestFullPipeline:
    """End-to-end pipeline: data → ML → optimizer → briefing."""

    def test_pipeline(self):
        """Run the complete pipeline on a small dataset."""
        from railopt.synthetic_data import generate_full_dataset
        from optimizer.cpsat_solver import BlockScheduler, SchedulerConfig
        from optimizer.block_merger import BlockMerger
        from optimizer.sla_engine import SLAEngine
        from genai.briefing_generator import BriefingGenerator

        # 1. Generate data
        dataset = generate_full_dataset(seed=42, num_tasks=30)
        tasks = dataset["tasks"]
        windows = dataset["block_windows"]
        sections_list = dataset["sections"]
        sections = {s.section_id: s for s in sections_list}

        # 2. Assign mock ML scores (skip actual ML training for speed)
        for t in tasks:
            if t.defect_category in ALWAYS_EMERGENCY:
                t.ml_criticality_score = 97.0
                t.ml_predicted_severity = DefectSeverity.EMERGENCY
            elif t.is_safety_critical:
                t.ml_criticality_score = 75.0
                t.ml_predicted_severity = DefectSeverity.HIGH
            elif t.days_overdue > 30:
                t.ml_criticality_score = 55.0
                t.ml_predicted_severity = DefectSeverity.MEDIUM
            else:
                t.ml_criticality_score = 25.0
                t.ml_predicted_severity = DefectSeverity.LOW
            t.ml_predicted_duration_hours = t.estimated_duration_hours

        # 3. Run SLA escalation
        sla = SLAEngine()
        escalated = sla.escalate_overdue(tasks)

        # 4. Run optimizer
        config = SchedulerConfig(time_limit_seconds=15)
        scheduler = BlockScheduler(config=config)
        plan = scheduler.solve(tasks, windows, sections, time_limit_seconds=15)

        # 5. Analyze merges
        merger = BlockMerger()
        merge_report = merger.analyze_merge_opportunities(plan, tasks)

        # 6. Generate briefing
        gen = BriefingGenerator(use_llm=False)
        briefing = gen.generate_weekly_briefing(plan, tasks)

        # Assertions
        assert plan is not None
        assert plan.total_tasks_scheduled >= 0
        assert isinstance(briefing, str)
        assert len(briefing) > 50
        assert merge_report is not None

        # Check SLA compliance
        sla_report = sla.check_compliance(tasks, plan)
        assert sla_report.compliance_percentage >= 0
