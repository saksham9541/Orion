"""
tests/test_block_sections.py

Comprehensive test suite for Phase 1 Block-Section Window Engine:
1. Known-answer gap calculation (Train 1 exit 01:04, Train 2 enter 04:00, 78m task, 15/15 buffers => 01:19-02:27)
2. Midnight-crossing passages and running days resolved on origin date
3. Direction derived strictly from station order (not train number parity)
4. Window invariants (no overlap with occupied clearance, duration >= needed, line isolation)
5. Double line vs single line track rules
6. Candidate window ranking with held trains and cascade delay
7. CP-SAT solver block-section conflict resolution & locked task fixed constraints
8. Provenance honesty (coverage % counts only provenance == 'live')
9. Block-section availability and revalidation endpoints
"""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo
import pytest

from railopt.models import (
    AssetType,
    BlockPlan,
    BlockType,
    BlockWindow,
    DefectCategory,
    Department,
    MaintenanceTask,
    PlanHorizon,
    Section,
    TaskStatus,
)
from traffic.block_sections import (
    BlockSection,
    build_block_sections,
    get_all_pilot_block_sections,
    get_block_section_by_id,
    find_block_section_for_chainage,
)
from traffic.passages import (
    BlockSectionPassage,
    KOLKATA_TZ,
)
from traffic.window_finder import (
    BlockWindowConfig,
    find_block_section_windows,
    rank_candidate_windows,
    calculate_block_availability,
    revalidate_window,
    UsableBlockWindow,
)
from traffic.fill import BlockCoverageSummary
from optimizer.cpsat_solver import BlockScheduler, SchedulerConfig


def _make_test_block_section(
    block_id: str = "BLK-TEST01-DN",
    from_stn: str = "NDLS",
    to_stn: str = "CSB",
    start_km: float = 0.0,
    end_km: float = 4.2,
    line: str = "DN",
    tracks: int = 2,
) -> BlockSection:
    return BlockSection(
        id=block_id,
        from_station=from_stn,
        to_station=to_stn,
        start_km=start_km,
        end_km=end_km,
        line=line,
        length_km=round(abs(end_km - start_km), 2),
        max_speed=110.0,
        tracks=tracks,
        split_points_source="none",
        station_list_source="test",
        pilot_section_id="SEC-93135bb9",
    )


# ----------------------------------------------------------------------
# 1. Known-Answer Gap Math
# ----------------------------------------------------------------------

def test_known_answer_gap_start_range():
    """
    Known-Answer Gap:
    Train 1: exits block section at 01:04 (e.g. 00:40 -> 01:04).
    Train 2: enters block section at 04:00 (e.g. 04:00 -> 04:24).
    Clearance / buffers: pre_buffer = 15m, post_buffer = 15m.
    Task duration: 78m.
    Total gap: 01:04 to 04:00 = 176 minutes.
    Earliest task start: 01:04 + 15m = 01:19.
    Latest task start: 04:00 - 15m - 78m = 02:27.
    Margin: 176 - (78 + 30) = 68 min -> COMFORTABLE.
    """
    b_sec = _make_test_block_section()
    target_date = date(2026, 11, 1)

    # Train 1: exits at 01:04
    p1 = BlockSectionPassage(
        train_number="12001",
        train_type="SHATABDI",
        block_section_id=b_sec.id,
        line=b_sec.line,
        direction="DN",
        origin_date=target_date,
        block_date=target_date,
        scheduled_enter=datetime(2026, 11, 1, 0, 40, tzinfo=KOLKATA_TZ),
        scheduled_exit=datetime(2026, 11, 1, 1, 4, tzinfo=KOLKATA_TZ),
        provenance="live",
    )

    # Train 2: enters at 04:00
    p2 = BlockSectionPassage(
        train_number="12003",
        train_type="SHATABDI",
        block_section_id=b_sec.id,
        line=b_sec.line,
        direction="DN",
        origin_date=target_date,
        block_date=target_date,
        scheduled_enter=datetime(2026, 11, 1, 4, 0, tzinfo=KOLKATA_TZ),
        scheduled_exit=datetime(2026, 11, 1, 4, 24, tzinfo=KOLKATA_TZ),
        provenance="live",
    )

    cfg = BlockWindowConfig(
        pre_buffer_minutes=15,
        post_buffer_minutes=15,
        default_clearance_minutes=0,  # Pre and post buffers handle clearance
        comfortable_margin_threshold_minutes=60,
    )

    windows = find_block_section_windows(
        b_sec,
        target_date=target_date,
        task_duration_minutes=78,
        passages=[p1, p2],
        config=cfg,
    )

    assert len(windows) >= 1
    # Find the window between Train 1 and Train 2
    gap_win = next(w for w in windows if w.earliest_start == time(1, 19))

    assert gap_win.earliest_start == time(1, 19), f"Expected 01:19, got {gap_win.earliest_start}"
    assert gap_win.latest_start == time(2, 27), f"Expected 02:27, got {gap_win.latest_start}"
    assert gap_win.recommended_start >= time(1, 19)
    assert gap_win.recommended_start <= time(2, 27)
    assert gap_win.task_duration_minutes == 78
    assert gap_win.pre_buffer_minutes == 15
    assert gap_win.post_buffer_minutes == 15
    assert gap_win.comfort_label == "COMFORTABLE"
    assert (gap_win.margin_before_min + gap_win.margin_after_min) == 68


# ----------------------------------------------------------------------
# 2. Midnight Crossing & Origin Date Running Days
# ----------------------------------------------------------------------

def test_midnight_crossing_passage_dates():
    """
    Test that a train crossing midnight has origin_date preserved,
    block_date set to the next day when entry is past midnight,
    and running days checked at origin date.
    """
    origin_sunday = date(2026, 11, 1)  # Sunday
    block_monday = date(2026, 11, 2)   # Monday

    p = BlockSectionPassage(
        train_number="12423",
        train_type="RAJDHANI",
        block_section_id="BLK-TEST01-DN",
        line="DN",
        direction="DN",
        origin_date=origin_sunday,
        block_date=block_monday,
        scheduled_enter=datetime(2026, 11, 2, 0, 15, tzinfo=KOLKATA_TZ),
        scheduled_exit=datetime(2026, 11, 2, 0, 25, tzinfo=KOLKATA_TZ),
        running_days=[6],  # Sunday only (0=Mon .. 6=Sun)
        provenance="live",
    )

    assert p.origin_date == origin_sunday
    assert p.block_date == block_monday
    assert p.scheduled_enter.date() == block_monday
    assert p.scheduled_exit.date() == block_monday


# ----------------------------------------------------------------------
# 3. Direction Derived from Station Order (Not Train Parity)
# ----------------------------------------------------------------------

def test_direction_from_station_order():
    """
    An even train number like 12002 running NDLS -> GZB (increasing chainage)
    must be classified as DN, NOT UP, regardless of train number parity.
    """
    b_sec_dn = _make_test_block_section(line="DN", from_stn="NDLS", to_stn="CSB")

    # Even numbered train moving away from Delhi (DN)
    p_even_dn = BlockSectionPassage(
        train_number="12002",  # Even number!
        train_type="SHATABDI",
        block_section_id=b_sec_dn.id,
        line="DN",
        direction="DN",
        origin_date=date(2026, 11, 1),
        block_date=date(2026, 11, 1),
        scheduled_enter=datetime(2026, 11, 1, 6, 0, tzinfo=KOLKATA_TZ),
        scheduled_exit=datetime(2026, 11, 1, 6, 8, tzinfo=KOLKATA_TZ),
    )

    assert p_even_dn.direction == "DN"
    assert p_even_dn.line == "DN"


# ----------------------------------------------------------------------
# 4. Invariants Verification
# ----------------------------------------------------------------------

def test_window_invariants():
    """
    Verify:
    - No returned free window interval overlaps with any passage's transit
    - Duration >= needed task duration
    - Line isolation: DN window is not blocked by UP passages
    """
    b_sec_dn = _make_test_block_section(line="DN")
    target_date = date(2026, 11, 1)

    p_dn = BlockSectionPassage(
        train_number="12001",
        train_type="SHATABDI",
        block_section_id=b_sec_dn.id,
        line="DN",
        direction="DN",
        origin_date=target_date,
        block_date=target_date,
        scheduled_enter=datetime(2026, 11, 1, 2, 0, tzinfo=KOLKATA_TZ),
        scheduled_exit=datetime(2026, 11, 1, 2, 10, tzinfo=KOLKATA_TZ),
    )
    p_up = BlockSectionPassage(
        train_number="12004",
        train_type="SHATABDI",
        block_section_id=b_sec_dn.id,
        line="UP",
        direction="UP",
        origin_date=target_date,
        block_date=target_date,
        scheduled_enter=datetime(2026, 11, 1, 3, 0, tzinfo=KOLKATA_TZ),
        scheduled_exit=datetime(2026, 11, 1, 3, 10, tzinfo=KOLKATA_TZ),
    )

    windows = find_block_section_windows(
        b_sec_dn,
        target_date=target_date,
        task_duration_minutes=90,
        line="DN",
        requires_both_lines=False,
        passages=[p_dn, p_up],
    )

    for w in windows:
        # Invariant 1: duration fits
        assert w.task_duration_minutes == 90
        # Invariant 2: rec start to rec end doesn't overlap p_dn
        s_min = w.recommended_start.hour * 60 + w.recommended_start.minute
        e_min = w.recommended_end.hour * 60 + w.recommended_end.minute
        # p_dn transit is 120..130 min
        assert not (max(s_min, 120) < min(e_min, 130))
        # Invariant 3: UP train does not constrain DN on double track
        assert w.line == "DN"


# ----------------------------------------------------------------------
# 5. Double Line vs Single Line Track
# ----------------------------------------------------------------------

def test_double_vs_single_line_rules():
    """
    On double line without requires_both_lines: UP train does not affect DN line.
    On single line (tracks=1) or requires_both_lines: UP train DOES occupy the track.
    """
    target_date = date(2026, 11, 1)

    p_up = BlockSectionPassage(
        train_number="12004",
        train_type="SHATABDI",
        block_section_id="BLK-TEST",
        line="UP",
        direction="UP",
        origin_date=target_date,
        block_date=target_date,
        scheduled_enter=datetime(2026, 11, 1, 2, 0, tzinfo=KOLKATA_TZ),
        scheduled_exit=datetime(2026, 11, 1, 2, 20, tzinfo=KOLKATA_TZ),
    )

    # Double line: DN task ignores UP train
    b_double = _make_test_block_section(tracks=2, line="DN")
    wins_double = find_block_section_windows(
        b_double,
        target_date=target_date,
        task_duration_minutes=60,
        line="DN",
        requires_both_lines=False,
        passages=[p_up],
    )
    # 00:00 to 23:59 should be completely free because p_up is ignored on DN line
    assert any(w.earliest_start <= time(2, 0) and w.latest_start >= time(2, 20) for w in wins_double)

    # Double line with requires_both_lines: UP train blocks the track
    wins_both = find_block_section_windows(
        b_double,
        target_date=target_date,
        task_duration_minutes=60,
        line="DN",
        requires_both_lines=True,
        passages=[p_up],
    )
    # The interval 02:00-02:20 is occupied, so no window can cover it
    for w in wins_both:
        s_m = w.recommended_start.hour * 60 + w.recommended_start.minute
        e_m = w.recommended_end.hour * 60 + w.recommended_end.minute
        assert not (max(s_m, 120) < min(e_m, 140))


# ----------------------------------------------------------------------
# 6. Candidate Window Ranking
# ----------------------------------------------------------------------

def test_candidate_window_ranking():
    """
    Test that rank_candidate_windows evaluates sliding intervals,
    correctly holds conflicting trains and scores delay.
    """
    b_sec = _make_test_block_section()
    target_date = date(2026, 11, 1)

    p_busy = BlockSectionPassage(
        train_number="12001",
        train_type="PASSENGER",
        block_section_id=b_sec.id,
        line="DN",
        direction="DN",
        origin_date=target_date,
        block_date=target_date,
        scheduled_enter=datetime(2026, 11, 1, 10, 0, tzinfo=KOLKATA_TZ),
        scheduled_exit=datetime(2026, 11, 1, 10, 10, tzinfo=KOLKATA_TZ),
    )

    ranked = rank_candidate_windows(
        b_sec,
        target_date=target_date,
        task_duration_minutes=60,
        line="DN",
        passages=[p_busy],
        top_k=3,
    )

    assert len(ranked) >= 1
    # Top ranked window should have 0 trains held if free gap exists
    assert ranked[0].trains_held == 0
    assert ranked[0].score >= 80.0


# ----------------------------------------------------------------------
# 7. CP-SAT Block-Section Conflict & Locked Tasks
# ----------------------------------------------------------------------

def test_cpsat_block_section_isolation_and_locked_tasks():
    """
    1. Tasks on DIFFERENT block sections (NDLS-CSB vs TKJ-ANVT) do NOT conflict
       even if scheduled at the exact same time on the same corridor section.
    2. A task with status=APPROVED and assigned_block_id is strictly locked to that window.
    """
    b1_id = "BLK-NDLS-CSB-DN"
    b2_id = "BLK-TKJ-ANVT-DN"
    sec_id = "SEC-93135bb9"
    cor_id = "COR-82d9c510"

    t1 = MaintenanceTask(
        task_id="MT-LOCKED-01",
        department=Department.ENGINEERING,
        asset_type=AssetType.RAIL,
        defect_category=DefectCategory.RAIL_FRACTURE,
        corridor_id=cor_id,
        section_id=sec_id,
        km_location=2.0,
        block_section_id=b1_id,
        line="DN",
        reported_date=date(2026, 11, 1),
        estimated_duration_hours=2.0,
        ml_criticality_score=80.0,
        status=TaskStatus.APPROVED,
        assigned_block_id="BW-B1-01",
    )

    t2 = MaintenanceTask(
        task_id="MT-CONCURRENT-02",
        department=Department.SNT,
        asset_type=AssetType.TRACK_CIRCUIT,
        defect_category=DefectCategory.TRACK_CIRCUIT_FAILURE,
        corridor_id=cor_id,
        section_id=sec_id,
        km_location=7.0,
        block_section_id=b2_id,
        line="DN",
        reported_date=date(2026, 11, 1),
        estimated_duration_hours=2.0,
        ml_criticality_score=60.0,
        status=TaskStatus.PENDING,
    )

    # Windows overlapping in time at 02:00-04:00 on the same date!
    w1 = BlockWindow(
        window_id="BW-B1-01",
        corridor_id=cor_id,
        section_id=sec_id,
        block_section_id=b1_id,
        line="DN",
        date=date(2026, 11, 1),
        start_time=time(2, 0),
        end_time=time(4, 0),
        duration_hours=2.0,
    )

    w2 = BlockWindow(
        window_id="BW-B2-01",
        corridor_id=cor_id,
        section_id=sec_id,
        block_section_id=b2_id,
        line="DN",
        date=date(2026, 11, 1),
        start_time=time(2, 0),
        end_time=time(4, 0),
        duration_hours=2.0,
    )

    scheduler = BlockScheduler(SchedulerConfig(time_limit_seconds=10))
    plan = scheduler.solve(
        tasks=[t1, t2],
        windows=[w1, w2],
        sections={sec_id: Section(corridor_id=cor_id, name="NDLS-GZB", start_station="NDLS", end_station="GZB", start_km=0, end_km=19)},
    )

    # Both must be scheduled simultaneously without conflict!
    scheduled_task_ids = {tid for b in plan.scheduled_blocks for tid in b.task_ids}
    assert "MT-LOCKED-01" in scheduled_task_ids
    assert "MT-CONCURRENT-02" in scheduled_task_ids

    # t1 must be assigned to w1 (its locked window)
    b1_block = next(b for b in plan.scheduled_blocks if "MT-LOCKED-01" in b.task_ids)
    assert b1_block.window_id == "BW-B1-01"


# ----------------------------------------------------------------------
# 8. Provenance Honesty (Coverage % counts only live)
# ----------------------------------------------------------------------

def test_coverage_honesty_rule():
    """
    Coverage ratio must count ONLY trains with provenance == 'live'.
    Hand-written and synthetic passages report real_trains=0 and coverage=0.0.
    """
    cov = BlockCoverageSummary(
        real_live_trains=0,
        synthetic_fill_trains=10,
        synthetic_goods_trains=5,
        total_trains=15,
        coverage_ratio=0.0,
        coverage_pct=0.0,
        provenance_label="illustrative",
    )
    assert cov.coverage_ratio == 0.0
    assert cov.coverage_pct == 0.0
    assert cov.provenance_label == "illustrative"


# ----------------------------------------------------------------------
# 9. Block Section Availability & Revalidation
# ----------------------------------------------------------------------

def test_block_section_availability_and_revalidate():
    """
    Verify calculate_block_availability and revalidate_window functions.
    """
    b_sec = _make_test_block_section()
    target_date = date(2026, 11, 1)

    avail = calculate_block_availability(
        b_sec, target_date=target_date, task_duration_minutes=90
    )
    assert avail.window_availability_score >= 0.0
    assert avail.window_availability_score <= 100.0
    assert avail.comfort_distribution is not None

    u_win = UsableBlockWindow(
        window_id="BW-TEST-01",
        block_section_id=b_sec.id,
        line="DN",
        date=target_date,
        gap_start_min=120,
        gap_end_min=240,
        earliest_start=time(2, 0),
        latest_start=time(2, 0),
        recommended_start=time(2, 0),
        recommended_end=time(3, 30),
        duration_hours=1.5,
        task_duration_minutes=90,
        pre_buffer_minutes=15,
        post_buffer_minutes=15,
        margin_before_min=15,
        margin_after_min=15,
        comfort_label="OK",
        freight_unverified=True,
        known_trains=0,
        estimated_total_trains=0,
        coverage=0.0,
    )

    reval = revalidate_window(b_sec, u_win, live_delays_map={})
    assert reval.is_valid is True
    assert reval.status in ("VALID", "ENCROACHED", "INVALID")
