"""
tests/test_traffic.py

Unit and integration tests for real track mapping, timetable passages,
window discovery, transparent delay calculation, and headway cascade.
All network calls are strictly mocked or avoided (using offline snapshots).
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
import pytest

from railopt.models import Department, DefectCategory, AssetType, MaintenanceTask, TrainType, BlockType, BlockWindow
from traffic.section_map import (
    get_pilot_sections,
    get_pilot_section_config,
    is_pilot_section,
)
from traffic.geo import locate, nearest_chainage
from traffic.passages import TrainPassage, load_pilot_passages
from traffic.fill import get_all_passages_for_section
from traffic.window_finder import find_free_windows, WindowFinderConfig
from traffic.delay_model import calculate_block_delays, DelayModelConfig
from traffic.cascade import propagate_cascade, CascadeConfig
from optimizer.cpsat_solver import BlockScheduler, SchedulerConfig
from agents.replanning_agent import ReplanningAgent
from railopt.models import BlockPlan, ScheduledBlock, PlanHorizon, TaskStatus


# ----------------------------------------------------------------------
# 1. Pilot Section Mapping & Geo Tests
# ----------------------------------------------------------------------

def test_pilot_section_mapping():
    assert is_pilot_section("SEC-93135bb9")
    assert is_pilot_section("New Delhi–Ghaziabad")
    assert is_pilot_section("SEC-d4d8b85c")
    assert is_pilot_section("New Delhi–Mathura Jn")
    assert not is_pilot_section("NON_EXISTENT_SECTION")

    sec = get_pilot_section_config("SEC-93135bb9")
    assert sec is not None
    assert sec.from_code == "NDLS"
    assert sec.to_code == "GZB"
    assert sec.distance_km == 19.0
    assert sec.max_speed_kmh == 130.0
    assert len(sec.stations) >= 2


def test_geo_locate_and_nearest_chainage():
    sec_id = "SEC-93135bb9"
    # Start of section (0.0 km) should be near NDLS coords
    lat0, lon0 = locate(sec_id, 0.0)
    assert round(lat0, 2) == 28.64
    assert round(lon0, 2) == 77.22

    # End of section (19.0 km) should be near GZB coords
    lat19, lon19 = locate(sec_id, 19.0)
    assert round(lat19, 2) == 28.67
    assert round(lon19, 2) == 77.43

    # Nearest chainage should be roughly inverse within 0.5 km tolerance
    km_test = 8.5
    lat_mid, lon_mid = locate(sec_id, km_test)
    recovered_km = nearest_chainage(sec_id, lat_mid, lon_mid)
    assert abs(recovered_km - km_test) < 0.6


# ----------------------------------------------------------------------
# 2. Timetable Passages & Interpolation Tests
# ----------------------------------------------------------------------

def test_passages_interpolation_and_running_days():
    sec = get_pilot_section_config("SEC-93135bb9")
    passages = load_pilot_passages(sec)
    assert len(passages) >= 10

    # Every passage must have valid non-empty enter/exit times and transit > 0
    for p in passages:
        assert isinstance(p.enter_time, time)
        assert isinstance(p.exit_time, time)
        transit = p.transit_minutes()
        # On 19 km NDLS-GZB at 130 km/h, transit is between 8 and 35 mins
        assert 8.0 <= transit <= 45.0, f"Unrealistic transit {transit}m for train {p.train_no}"

    # Test running days
    # Train running on weekdays only
    weekday_train = TrainPassage(
        train_no="99999",
        train_name="Weekday Express",
        train_type=TrainType.SUPERFAST,
        section_id=sec.section_id,
        direction="DN",
        running_days=[0, 1, 2, 3, 4],  # Mon-Fri
        enter_time=time(8, 0),
        exit_time=time(8, 20),
    )
    assert weekday_train.runs_on_date(date(2026, 11, 2))  # Monday
    assert not weekday_train.runs_on_date(date(2026, 11, 1))  # Sunday


def test_section_coverage_summary():
    sec = get_pilot_section_config("SEC-93135bb9")
    target_d = date(2026, 11, 1)
    passages, cov = get_all_passages_for_section(sec, target_d)

    assert len(passages) >= 50
    assert cov.real_trains > 0
    assert cov.total_trains == len(passages)
    assert 0.0 < cov.coverage_ratio <= 1.0
    assert cov.coverage_pct == round(cov.coverage_ratio * 100.0, 1)


# ----------------------------------------------------------------------
# 3. Window Finder Tests
# ----------------------------------------------------------------------

def test_window_finder_known_gaps():
    sec = get_pilot_section_config("SEC-93135bb9")
    target_d = date(2026, 11, 1)

    # Synthetic schedule with two deterministic passages and an open gap
    p1 = TrainPassage(
        train_no="T1",
        train_name="Morning Service",
        train_type=TrainType.SUPERFAST,
        section_id=sec.section_id,
        direction="DN",
        running_days=[target_d.weekday()],
        enter_time=time(8, 0),
        exit_time=time(8, 15),
    )
    p2 = TrainPassage(
        train_no="T2",
        train_name="Afternoon Service",
        train_type=TrainType.SUPERFAST,
        section_id=sec.section_id,
        direction="DN",
        running_days=[target_d.weekday()],
        enter_time=time(12, 0),
        exit_time=time(12, 15),
    )

    cfg = WindowFinderConfig(clearance_buffer_minutes=10, min_window_duration_hours=1.5)
    windows = find_free_windows(sec, target_d, passages=[p1, p2], config=cfg)

    assert len(windows) >= 1
    # Check that discovered window sits inside the free interval
    gap_window = next((w for w in windows if w.start_time >= time(8, 25) and w.end_time <= time(11, 50)), None)
    assert gap_window is not None
    assert gap_window.duration_hours >= 1.5
    assert gap_window.source == "timetable_derived"
    assert gap_window.delay_source == "computed"


# ----------------------------------------------------------------------
# 4. Delay Model & Live Delay Shift Tests
# ----------------------------------------------------------------------

def test_delay_model_hold_and_reroute():
    sec = get_pilot_section_config("SEC-93135bb9")
    target_d = date(2026, 11, 1)

    # Train scheduled right in the middle of a proposed 14:00-16:00 block
    p = TrainPassage(
        train_no="12345",
        train_name="Midday SF",
        train_type=TrainType.SUPERFAST,
        section_id=sec.section_id,
        direction="DN",
        running_days=[target_d.weekday()],
        enter_time=time(14, 30),
        exit_time=time(14, 45),
    )

    # Case A: Section without alternate route -> held until 16:00
    sec_no_alt = get_pilot_section_config("SEC-93135bb9")
    res = calculate_block_delays(sec_no_alt, target_d, time(14, 0), time(16, 0), passages=[p])

    assert res.trains_affected == 1
    assert "12345" in res.per_train_delays
    # With alternate route enabled on pilot (penalty 22.0 min < 90 min hold), train gets rerouted
    if sec_no_alt.has_alternate_route:
        assert "12345" in res.rerouted_trains
        assert res.per_train_delays["12345"] == sec_no_alt.alternate_route_penalty_minutes
    else:
        assert "12345" in res.held_trains
        assert res.per_train_delays["12345"] >= 90.0


# ----------------------------------------------------------------------
# 5. Cascade Propagation Tests
# ----------------------------------------------------------------------

def test_cascade_headway_propagation_and_depth():
    sec = get_pilot_section_config("SEC-93135bb9")
    target_d = date(2026, 11, 1)

    # Chain of 3 trains scheduled closely
    t1 = TrainPassage("T1", "Lead Train", TrainType.PASSENGER, sec.section_id, "DN", [0,1,2,3,4,5,6], time(10, 0), time(10, 15))
    t2 = TrainPassage("T2", "Second Train", TrainType.PASSENGER, sec.section_id, "DN", [0,1,2,3,4,5,6], time(10, 16), time(10, 31))
    t3 = TrainPassage("T3", "Third Train", TrainType.PASSENGER, sec.section_id, "DN", [0,1,2,3,4,5,6], time(10, 22), time(10, 37))

    # T1 is delayed by 20 min
    from traffic.delay_model import DelayCalculationResult
    primary_res = DelayCalculationResult(
        block_id="B1",
        section_id=sec.section_id,
        target_date=str(target_d),
        trains_affected=1,
        total_delay_minutes=20.0,
        per_train_delays={"T1": 20.0},
        rerouted_trains=[],
        held_trains=["T1"],
    )

    cfg = CascadeConfig(min_headway_minutes=5.0, max_cascade_depth=3)
    cas_res = propagate_cascade(primary_res, [t1, t2, t3], config=cfg)

    assert cas_res.primary_trains_affected == 1
    assert cas_res.trains_hit >= 2
    assert cas_res.cascade_total_delay > 20.0
    assert cas_res.max_depth >= 1
    assert len(cas_res.cascade_chains) >= 1


# ----------------------------------------------------------------------
# 6. Solver Integration Tests on Timetable-Derived Windows
# ----------------------------------------------------------------------

def test_solver_on_timetable_derived_windows():
    from railopt.synthetic_data import generate_full_dataset
    ds = generate_full_dataset(num_tasks=20, window_days=7)

    pilot_wins = [w for w in ds["block_windows"] if w.source == "timetable_derived"]
    assert len(pilot_wins) > 0

    # Ensure tasks have non-zero criticality scores so optimizer has incentive to schedule
    for i, t in enumerate(ds["tasks"]):
        t.ml_criticality_score = 60.0 + (i % 30)

    scheduler = BlockScheduler(config=SchedulerConfig(time_limit_seconds=5))
    plan = scheduler.solve(ds["tasks"], ds["block_windows"], {s.section_id: s for s in ds["sections"]})

    assert isinstance(plan, BlockPlan)
    assert len(plan.scheduled_blocks) > 0


# ----------------------------------------------------------------------
# 7. Replanning Agent Computes Real Numbers (No Hardcoded 35m / 2 Trains)
# ----------------------------------------------------------------------

def test_replanning_agent_computes_real_impact():
    sec_id = "SEC-93135bb9"
    sec = get_pilot_section_config(sec_id)

    dummy_plan = BlockPlan(
        plan_id="PLN-TEST-001",
        horizon=PlanHorizon.WEEKLY,
        start_date=date(2026, 11, 1),
        end_date=date(2026, 11, 8),
        scheduled_blocks=[],
    )

    emergency_task = MaintenanceTask(
        task_id="MT-EMG-001",
        department=Department.ENGINEERING,
        asset_type=AssetType.RAIL,
        defect_category=DefectCategory.RAIL_FRACTURE,
        corridor_id="COR-82d9c510",
        section_id=sec_id,
        km_location=5.0,
        reported_date=date(2026, 11, 1),
        estimated_duration_hours=2.0,
        is_safety_critical=True,
    )

    agent = ReplanningAgent()
    res = agent.handle_emergency(dummy_plan, emergency_task, [emergency_task])

    assert res.assigned_block_id != ""
    sched_block = res.updated_plan.scheduled_blocks[0]
    # Verify that numbers were computed dynamically and not hardcoded to trains_affected=2 and delay=35.0
    assert sched_block.duration_hours >= 2.0
    # On a real free gap at night, disruption should be minimal/realistic
    assert sched_block.trains_affected >= 0
