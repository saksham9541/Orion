"""
Tests for Multi-Agent Maintenance Block Optimization System (agents/ package).
Verifies:
1. DepartmentAgent: domain profiles, task filtering, urgency scoring, proposal formulation
2. ArbitratorAgent: conflict arbitration, block merging, duration consolidation, savings calculation, priority award
3. EarlyWarningAgent: defect recurrence hotspots, seasonal weather vulnerability, aging assets
4. ReplanningAgent: mid-schedule emergency repair, capacity-based displacement, minimal perturbation
5. AgentOrchestrator: end-to-end consensus planning cycle and summary generation
6. Multi-agent FastAPI endpoints: /api/agents/status, /api/agents/negotiate, /api/agents/early-warning/scan
"""
from datetime import date, datetime, time, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from agents.department_agent import DepartmentAgent, DepartmentProposal
from agents.arbitrator_agent import ArbitratorAgent, NegotiationAgreement, ConflictResolution
from agents.early_warning_agent import EarlyWarningAgent
from agents.replanning_agent import ReplanningAgent, ReplanResult
from agents.agent_orchestrator import AgentOrchestrator, AgentConsensusPlan

from railopt.models import (
    AssetType,
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
)
from backend.main import app
from backend.database import Base, UserRecord
from backend.auth import hash_password, create_access_token


# ──────────────────────────────────────────────────────────────────────
# Test Fixtures & Factories
# ──────────────────────────────────────────────────────────────────────

def create_sample_task(
    task_id: str,
    department: Department,
    section_id: str = "SEC-01",
    corridor_id: str = "COR-01",
    duration: float = 2.0,
    criticality: float = 50.0,
    is_safety_critical: bool = False,
    severity: DefectSeverity = DefectSeverity.HIGH,
    requires_power: bool = False,
    requires_traffic: bool = True,
    status: TaskStatus = TaskStatus.PENDING,
    days_overdue: int = 0,
    historical_failures: int = 0,
    asset_age: float = 5.0,
) -> MaintenanceTask:
    category = DefectCategory.RAIL_FRACTURE if is_safety_critical else DefectCategory.BALLAST_DEFICIENCY
    asset = AssetType.RAIL if (department == Department.ENGINEERING and is_safety_critical) else (
        AssetType.BALLAST if department == Department.ENGINEERING else (
            AssetType.POINT_MACHINE if department == Department.SNT else AssetType.OHE_WIRE
        )
    )
    return MaintenanceTask(
        task_id=task_id,
        corridor_id=corridor_id,
        section_id=section_id,
        km_location=12.5,
        km_start=10.0,
        km_end=15.0,
        department=department,
        asset_type=asset,
        defect_category=category,
        raw_severity=severity.value,
        status=status,
        reported_date=date(2026, 10, 20),
        due_date=date(2026, 11, 5),
        estimated_duration_hours=duration,
        crew_size_required=4,
        requires_power_block=requires_power,
        requires_traffic_block=requires_traffic,
        is_safety_critical=is_safety_critical,
        days_overdue=days_overdue,
        historical_failure_count=historical_failures,
        asset_age_years=asset_age,
        ml_predicted_severity=severity,
        ml_criticality_score=criticality,
    )


def create_sample_section(
    section_id: str = "SEC-01",
    corridor_id: str = "COR-01",
    name: str = "Alpha",
) -> Section:
    return Section(
        section_id=section_id,
        corridor_id=corridor_id,
        name=name,
        start_station="STN-A",
        end_station="STN-B",
        start_km=0.0,
        end_km=50.0,
    )


def create_sample_corridor(
    corridor_id: str = "COR-01",
    name: str = "Main Line",
    code: str = "ML",
) -> Corridor:
    return Corridor(
        corridor_id=corridor_id,
        name=name,
        code=code,
        division="DIV-1",
        zone="NR",
        total_length_km=100.0,
        sections=[],
    )


def create_sample_window(
    window_id: str = "WIN-01",
    section_id: str = "SEC-01",
    corridor_id: str = "COR-01",
    window_date: date = date(2026, 11, 2),
    start: time = time(1, 0),
    end: time = time(5, 0),
    duration: float = 4.0,
) -> BlockWindow:
    return BlockWindow(
        window_id=window_id,
        corridor_id=corridor_id,
        section_id=section_id,
        track_number=1,
        date=window_date,
        start_time=start,
        end_time=end,
        duration_hours=duration,
        day_of_week=0,
        is_night_window=True,
        shadow_corridor_available=False,
    )


# ──────────────────────────────────────────────────────────────────────
# 1. DepartmentAgent Tests
# ──────────────────────────────────────────────────────────────────────

def test_department_agent_domain_profiles():
    eng_agent = DepartmentAgent(Department.ENGINEERING)
    assert eng_agent.department == Department.ENGINEERING
    assert eng_agent.primary_block_type == BlockType.TRAFFIC_BLOCK
    assert eng_agent.standard_crew_size == 8

    snt_agent = DepartmentAgent(Department.SNT)
    assert snt_agent.department == Department.SNT
    assert snt_agent.primary_block_type == BlockType.NON_TRAFFIC
    assert snt_agent.default_flexibility > eng_agent.default_flexibility

    trd_agent = DepartmentAgent(Department.TRD)
    assert trd_agent.department == Department.TRD
    assert trd_agent.primary_block_type == BlockType.POWER_BLOCK
    assert trd_agent.default_flexibility == 0.4


def test_department_agent_filter_tasks():
    agent = DepartmentAgent(Department.ENGINEERING)
    tasks = [
        create_sample_task("T1", Department.ENGINEERING, status=TaskStatus.PENDING),
        create_sample_task("T2", Department.ENGINEERING, status=TaskStatus.COMPLETED),
        create_sample_task("T3", Department.SNT, status=TaskStatus.PENDING),
        create_sample_task("T4", Department.ENGINEERING, status=TaskStatus.ESCALATED),
    ]
    filtered = agent.filter_department_tasks(tasks)
    filtered_ids = {t.task_id for t in filtered}
    assert filtered_ids == {"T1", "T4"}


def test_department_agent_urgency_scoring():
    agent = DepartmentAgent(Department.ENGINEERING)

    # Standard task
    t_normal = create_sample_task("T1", Department.ENGINEERING, criticality=40.0)
    score_normal = agent.score_task_urgency(t_normal)
    assert score_normal == 40.0

    # Emergency task
    t_emergency = create_sample_task("T2", Department.ENGINEERING, severity=DefectSeverity.EMERGENCY)
    score_emergency = agent.score_task_urgency(t_emergency)
    assert score_emergency >= 98.0

    # Overdue task with historical failures
    t_overdue = create_sample_task(
        "T3", Department.ENGINEERING, criticality=50.0, days_overdue=5, historical_failures=2
    )
    score_overdue = agent.score_task_urgency(t_overdue)
    # 50 + min(5*2, 20) + min(2*3, 15) = 50 + 10 + 6 = 66
    assert score_overdue == 66.0


def test_department_agent_formulate_proposals():
    agent = DepartmentAgent(Department.ENGINEERING)
    tasks = [
        create_sample_task("T1", Department.ENGINEERING, section_id="SEC-01", duration=2.5),
        create_sample_task("T2", Department.ENGINEERING, section_id="SEC-01", duration=1.5),
    ]
    windows = [create_sample_window("W1", section_id="SEC-01", duration=4.0)]
    sections = {"SEC-01": create_sample_section(section_id="SEC-01", corridor_id="COR-01", name="Track Alpha")}

    proposals = agent.formulate_proposals(tasks, windows, sections)
    assert len(proposals) == 1
    prop = proposals[0]
    assert prop.department == Department.ENGINEERING
    assert prop.section_id == "SEC-01"
    assert "T1" in prop.task_ids and "T2" in prop.task_ids
    assert prop.requested_duration_hours == 2.5
    assert prop.preferred_window_id == "W1"


# ──────────────────────────────────────────────────────────────────────
# 2. ArbitratorAgent Tests (Block Merging & Conflict Resolution)
# ──────────────────────────────────────────────────────────────────────

def test_arbitrator_uncontested_proposal():
    arbitrator = ArbitratorAgent()
    target_d = date(2026, 11, 2)
    p = DepartmentProposal(
        proposal_id="PROP-ENG-1",
        department=Department.ENGINEERING,
        section_id="SEC-01",
        corridor_id="COR-01",
        target_date=target_d,
        preferred_window_id="W1",
        start_time=time(1, 0),
        end_time=time(4, 0),
        requested_duration_hours=3.0,
        task_ids=["T1"],
        total_urgency_score=70.0,
        has_emergency=False,
        requires_power_block=False,
        requires_traffic_block=True,
        crew_size_needed=6,
    )

    agreements, conflicts = arbitrator.arbitrate([p])
    assert len(agreements) == 1
    assert len(conflicts) == 0
    ag = agreements[0]
    assert ag.is_merged is False
    assert ag.merge_savings_hours == 0.0
    assert ag.duration_hours == 3.0
    assert ag.participating_departments == [Department.ENGINEERING]


def test_arbitrator_block_merging():
    arbitrator = ArbitratorAgent()
    target_d = date(2026, 11, 2)

    # Engineering proposal: 3.0 hours on SEC-01
    p_eng = DepartmentProposal(
        proposal_id="PROP-ENG-1",
        department=Department.ENGINEERING,
        section_id="SEC-01",
        corridor_id="COR-01",
        target_date=target_d,
        preferred_window_id="W1",
        start_time=time(1, 0),
        end_time=time(5, 0),
        requested_duration_hours=3.0,
        task_ids=["ENG-T1"],
        total_urgency_score=75.0,
        has_emergency=False,
        requires_power_block=False,
        requires_traffic_block=True,
        crew_size_needed=8,
    )

    # S&T proposal: 2.0 hours on SEC-01
    p_snt = DepartmentProposal(
        proposal_id="PROP-SNT-1",
        department=Department.SNT,
        section_id="SEC-01",
        corridor_id="COR-01",
        target_date=target_d,
        preferred_window_id="W1",
        start_time=time(1, 0),
        end_time=time(5, 0),
        requested_duration_hours=2.0,
        task_ids=["SNT-T1"],
        total_urgency_score=60.0,
        has_emergency=False,
        requires_power_block=False,
        requires_traffic_block=False,
        crew_size_needed=4,
    )

    # TRD proposal: 2.5 hours on SEC-01 requiring power block
    p_trd = DepartmentProposal(
        proposal_id="PROP-TRD-1",
        department=Department.TRD,
        section_id="SEC-01",
        corridor_id="COR-01",
        target_date=target_d,
        preferred_window_id="W1",
        start_time=time(1, 0),
        end_time=time(5, 0),
        requested_duration_hours=2.5,
        task_ids=["TRD-T1"],
        total_urgency_score=65.0,
        has_emergency=False,
        requires_power_block=True,
        requires_traffic_block=False,
        crew_size_needed=6,
    )

    agreements, conflicts = arbitrator.arbitrate([p_eng, p_snt, p_trd])

    assert len(agreements) == 1
    assert len(conflicts) == 1

    ag = agreements[0]
    cr = conflicts[0]

    assert cr.resolution_type == "MERGED"
    assert ag.is_merged is True
    # Merged duration = max(3.0, 2.0, 2.5) = 3.0 hours
    assert ag.duration_hours == 3.0
    # Merge savings = (3.0 + 2.0 + 2.5) - 3.0 = 4.5 hours saved!
    assert ag.merge_savings_hours == 4.5
    # Has both traffic block and power block -> COMBINED
    assert ag.block_type == BlockType.COMBINED
    assert set(ag.participating_departments) == {Department.ENGINEERING, Department.SNT, Department.TRD}
    assert set(ag.task_ids) == {"ENG-T1", "SNT-T1", "TRD-T1"}


def test_arbitrator_priority_award_when_incompatible():
    arbitrator = ArbitratorAgent()
    target_d = date(2026, 11, 2)

    # Two proposals on same section and date where one refuses merge (flexibility = 0.0)
    p1 = DepartmentProposal(
        proposal_id="PROP-1",
        department=Department.ENGINEERING,
        section_id="SEC-01",
        corridor_id="COR-01",
        target_date=target_d,
        preferred_window_id="W1",
        start_time=time(1, 0),
        end_time=time(4, 0),
        requested_duration_hours=3.0,
        task_ids=["T1"],
        total_urgency_score=90.0,
        has_emergency=True,
        requires_power_block=False,
        requires_traffic_block=True,
        crew_size_needed=8,
        flexibility=0.0,  # Refuses merge due to physical rail crane operation
    )

    p2 = DepartmentProposal(
        proposal_id="PROP-2",
        department=Department.TRD,
        section_id="SEC-01",
        corridor_id="COR-01",
        target_date=target_d,
        preferred_window_id="W1",
        start_time=time(1, 0),
        end_time=time(4, 0),
        requested_duration_hours=2.0,
        task_ids=["T2"],
        total_urgency_score=60.0,
        has_emergency=False,
        requires_power_block=True,
        requires_traffic_block=False,
        crew_size_needed=4,
        flexibility=0.4,
    )

    agreements, conflicts = arbitrator.arbitrate([p1, p2])
    assert len(agreements) == 1
    assert len(conflicts) == 1

    cr = conflicts[0]
    assert cr.resolution_type == "PRIORITY_AWARD"
    assert agreements[0].participating_departments == [Department.ENGINEERING]
    assert agreements[0].is_merged is False


# ──────────────────────────────────────────────────────────────────────
# 3. EarlyWarningAgent Tests
# ──────────────────────────────────────────────────────────────────────

def test_early_warning_hotspot_detection():
    agent = EarlyWarningAgent()
    # 6 tasks on SEC-01
    tasks = [
        create_sample_task(f"T{i}", Department.ENGINEERING, section_id="SEC-HOT", historical_failures=2)
        for i in range(6)
    ]
    corridors = [create_sample_corridor(corridor_id="COR-01", name="Main Line", code="ML")]
    sections = {"SEC-HOT": create_sample_section(section_id="SEC-HOT", corridor_id="COR-01", name="Hotspot Section")}

    warnings = agent.scan_corridor_risks(tasks, corridors, sections, current_date=date(2026, 7, 15))
    hotspot_warnings = [w for w in warnings if "HOTSPOT" in w.warning_id]

    assert len(hotspot_warnings) >= 1
    hw = hotspot_warnings[0]
    assert hw.section_id == "SEC-HOT"
    assert hw.risk_level == "HIGH"
    assert hw.trend_data["active_defects"] == 6


# ──────────────────────────────────────────────────────────────────────
# 4. ReplanningAgent Tests
# ──────────────────────────────────────────────────────────────────────

def test_replanning_agent_emergency_absorption():
    agent = ReplanningAgent()
    target_d = date(2026, 11, 2)

    existing_block = ScheduledBlock(
        block_id="BLK-01",
        window_id="WIN-01",
        corridor_id="COR-01",
        section_id="SEC-01",
        section_name="Alpha",
        date=target_d,
        start_time=time(1, 0),
        end_time=time(4, 0),
        duration_hours=3.0,
        task_ids=["T1", "T2"],
        departments=[Department.ENGINEERING],
        block_type=BlockType.TRAFFIC_BLOCK,
    )

    current_plan = BlockPlan(
        plan_id="PLN-01",
        horizon=PlanHorizon.WEEKLY,
        start_date=target_d,
        end_date=target_d + timedelta(days=7),
        created_at=datetime.now(timezone.utc),
        scheduled_blocks=[existing_block],
        total_tasks_scheduled=2,
        total_tasks_deferred=0,
        total_block_hours=3.0,
        total_merge_savings_hours=0.0,
        total_trains_affected=2,
        sla_compliance_pct=100.0,
        departments_summary={"ENGINEERING": 2},
        deferred_task_ids=[],
    )

    emergency_task = create_sample_task(
        "EMG-99", Department.TRD, section_id="SEC-01", severity=DefectSeverity.EMERGENCY, requires_power=True
    )

    t1 = create_sample_task("T1", Department.ENGINEERING, section_id="SEC-01")
    t2 = create_sample_task("T2", Department.ENGINEERING, section_id="SEC-01")

    res = agent.handle_emergency(current_plan, emergency_task, [t1, t2])

    assert isinstance(res, ReplanResult)
    assert res.emergency_task_id == "EMG-99"
    assert res.assigned_block_id == "BLK-01"
    assert "EMG-99" in res.updated_plan.scheduled_blocks[0].task_ids
    # Block type upgraded to COMBINED since TRD emergency requires power block
    assert res.updated_plan.scheduled_blocks[0].block_type == BlockType.COMBINED


# ──────────────────────────────────────────────────────────────────────
# 5. AgentOrchestrator End-to-End Consensus Cycle
# ──────────────────────────────────────────────────────────────────────

def test_agent_orchestrator_consensus_cycle():
    orchestrator = AgentOrchestrator()
    target_d = date(2026, 11, 2)

    # 3 departments have tasks on SEC-01
    tasks = [
        create_sample_task("T-ENG", Department.ENGINEERING, section_id="SEC-01", duration=3.0),
        create_sample_task("T-SNT", Department.SNT, section_id="SEC-01", duration=2.0),
        create_sample_task("T-TRD", Department.TRD, section_id="SEC-01", duration=2.5, requires_power=True),
        # Another task on SEC-02 for Engineering
        create_sample_task("T-ENG2", Department.ENGINEERING, section_id="SEC-02", duration=2.0),
    ]

    windows = [
        create_sample_window("W1", section_id="SEC-01", window_date=target_d, duration=4.0),
        create_sample_window("W2", section_id="SEC-02", window_date=target_d, duration=3.0),
    ]

    sections = {
        "SEC-01": create_sample_section(section_id="SEC-01", corridor_id="COR-01", name="Alpha"),
        "SEC-02": create_sample_section(section_id="SEC-02", corridor_id="COR-01", name="Beta"),
    }
    corridors = [create_sample_corridor(corridor_id="COR-01", name="Main", code="ML")]

    consensus = orchestrator.run_planning_cycle(
        tasks=tasks,
        available_windows=windows,
        sections=sections,
        corridors=corridors,
        horizon=PlanHorizon.WEEKLY,
        start_date=target_d,
    )

    assert isinstance(consensus, AgentConsensusPlan)
    assert consensus.plan.total_tasks_scheduled == 4
    # Block merging on SEC-01 saved hours
    assert consensus.plan.total_merge_savings_hours > 0.0
    assert consensus.orchestration_summary["merged_blocks_count"] >= 1
    assert len(consensus.agreements) == 2  # SEC-01 (merged) and SEC-02 (uncontested)
    assert len(consensus.conflict_resolutions) == 1  # SEC-01 resolved by merging


# ──────────────────────────────────────────────────────────────────────
# 6. Multi-Agent API Endpoints Tests
# ──────────────────────────────────────────────────────────────────────

@pytest.fixture
def agent_api_client(tmp_path, monkeypatch):
    """Sets up an isolated SQLite database and seeded user for agent endpoint tests."""
    db_file = tmp_path / "agent_test.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    monkeypatch.setattr("backend.database.get_engine", lambda: engine)
    monkeypatch.setattr("backend.auth.get_session", lambda: Session())
    monkeypatch.setattr("backend.main.engine", engine)

    session = Session()
    user = UserRecord(
        id="usr_ctrl",
        name="Section Controller",
        email="controller@test.gov.in",
        password_hash=hash_password("controller123"),
        role="CONTROLLER",
        department=None,
        is_active=True,
    )
    session.add(user)
    session.commit()
    token = create_access_token(user)
    session.close()

    # Seed app.state
    app.state.tasks = [
        create_sample_task("T-E", Department.ENGINEERING, section_id="SEC-01", duration=3.0),
        create_sample_task("T-S", Department.SNT, section_id="SEC-01", duration=2.0),
    ]
    app.state.windows = [
        create_sample_window("W-1", section_id="SEC-01", duration=4.0),
    ]
    app.state.sections = {
        "SEC-01": create_sample_section(section_id="SEC-01", corridor_id="COR-01", name="Mainline Alpha")
    }
    app.state.corridors = [
        create_sample_corridor(corridor_id="COR-01", name="Mainline", code="ML")
    ]
    app.state.plans = {}

    client = TestClient(app)
    return client, token


def test_api_agents_status(agent_api_client):
    client, token = agent_api_client
    resp = client.get("/api/agents/status", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert "agents" in data
    assert len(data["agents"]) >= 5
    agent_names = [a["name"] for a in data["agents"]]
    assert any("Engineering" in n for n in agent_names)
    assert any("Arbitrator" in n for n in agent_names)
    assert any("Early Warning" in n for n in agent_names)


def test_api_agents_early_warning_scan(agent_api_client):
    client, token = agent_api_client
    resp = client.post("/api/agents/early-warning/scan", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert "early_warnings" in data
    assert isinstance(data["early_warnings"], list)


def test_api_agents_negotiate(agent_api_client):
    client, token = agent_api_client
    resp = client.post(
        "/api/agents/negotiate",
        headers={"Authorization": f"Bearer {token}"},
        json={"horizon": "WEEKLY"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "plan_id" in data
    assert data["total_tasks_scheduled"] == 2
    assert data["merged_blocks_count"] >= 1
    assert data["total_merge_savings_hours"] > 0
    assert "conflict_resolutions" in data
    assert len(data["conflict_resolutions"]) >= 1
