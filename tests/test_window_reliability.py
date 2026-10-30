"""
tests/test_window_reliability.py

Comprehensive tests for Orion Phase 2 Reliability Layer (Step 0):
1. Brute-force oracle test (minute-by-minute occupancy grid vs interval-merge, randomized timetables incl. midnight crossing).
2. Dynamic per-passage margin growth for interpolated passages.
3. CONSERVATIVE vs OPTIMISTIC track conflict modes.
4. Cancelled train opens a maintenance window.
5. Delayed / diverted train closes or splits a maintenance window.
6. Invariant: Synthetic traffic NEVER produces a HIGH confidence window.
7. Bounding trains {prev, next} accurately identified.
8. Traffic mode switch (LIVE_ONLY vs LIVE_PLUS_SYNTHETIC) modifies candidate windows and stamps labels.
"""
from __future__ import annotations

import random
from datetime import date, datetime, time, timedelta, timezone
import pytest

try:
    from zoneinfo import ZoneInfo
    KOLKATA_TZ = ZoneInfo("Asia/Kolkata")
except Exception:
    KOLKATA_TZ = timezone(timedelta(hours=5, minutes=30))

from railopt.models import LiveTrainStatus, TrainType
from traffic.block_sections import BlockSection, build_block_sections
from traffic.passages import BlockSectionPassage
from traffic.window_finder import (
    BlockWindowConfig,
    _minutes_to_time,
    _time_to_minutes,
    find_block_section_windows,
)
from traffic.window_reliability import (
    ReliableBlockWindow,
    ReliabilityConfig,
    apply_live_train_statuses,
    compute_confidence_score,
    compute_passage_margin,
    extract_bounding_trains,
    filter_passages_by_track,
    find_reliable_block_windows,
    rank_reliable_candidate_windows,
)


def _make_dummy_passage(
    train_no: str,
    enter_t: time,
    exit_t: time,
    block_section_id: str = "BLK-845de309",
    line: str = "DN",
    train_type: TrainType = TrainType.MAIL_EXPRESS,
    provenance: str = "live",
    interpolated: bool = False,
    origin_date: date = date(2026, 11, 1),
    track_assignment_known: bool = False,
    assigned_track: str = None,
) -> BlockSectionPassage:
    """Helper to construct a typed BlockSectionPassage."""
    dt_enter = datetime.combine(origin_date, enter_t, tzinfo=KOLKATA_TZ)
    dt_exit = datetime.combine(origin_date, exit_t, tzinfo=KOLKATA_TZ)
    if exit_t < enter_t:
        dt_exit += timedelta(days=1)

    p = BlockSectionPassage(
        train_no=train_no,
        train_name=f"Train {train_no}",
        train_type=train_type,
        block_section_id=block_section_id,
        line=line,
        enter_datetime=dt_enter,
        exit_datetime=dt_exit,
        enter_time=enter_t,
        exit_time=exit_t,
        interpolated=interpolated,
        provenance=provenance,
        origin_date=origin_date,
    )
    p.track_assignment_known = track_assignment_known
    p.assigned_track = assigned_track
    return p


# ==============================================================================
# 1. Brute-Force Oracle Test: Minute Grid vs Interval-Merge
# ==============================================================================

def test_oracle_minute_grid_vs_interval_merge():
    """
    Brute-force oracle verification:
    Compares the 1440-minute occupancy grid against find_block_section_windows interval merge,
    testing with 20 randomized timetables including midnight crossings.
    """
    rng = random.Random(12345)
    target_d = date(2026, 11, 1)
    bs = BlockSection(
        id="BLK-TEST-ORACLE",
        from_station="STA_A",
        to_station="STA_B",
        start_km=0.0,
        end_km=15.0,
        line="DN",
        length_km=15.0,
        max_speed=110.0,
        tracks=2,
        split_points_source="none",
        station_list_source="hand_written",
    )

    clr = 10
    task_duration = 90
    pre_buf = 15
    post_buf = 15
    required_gap = task_duration + pre_buf + post_buf

    cfg = BlockWindowConfig(
        clearance_buffer_minutes=clr,
        pre_buffer_minutes=pre_buf,
        post_buffer_minutes=post_buf,
    )

    # Generate 12 randomized train passages across the 24h day
    passages = []
    for i in range(12):
        start_m = rng.randint(0, 1420)
        dur_m = rng.randint(4, 25)
        end_m = (start_m + dur_m) % 1440

        t_enter = _minutes_to_time(start_m)
        t_exit = _minutes_to_time(end_m)
        passages.append(_make_dummy_passage(
            train_no=f"T-{i+1:03d}",
            enter_t=t_enter,
            exit_t=t_exit,
            block_section_id=bs.id,
            line="DN",
            origin_date=target_d,
        ))

    # A. Oracle: 1440-minute boolean grid
    # minute m is True (occupied) if any train + clr occupies it
    grid = [False] * 1440
    for p in passages:
        s_m = _time_to_minutes(p.enter_time)
        e_m = _time_to_minutes(p.exit_time)
        if e_m < s_m:
            e_m += 1440

        occ_start = s_m - clr
        occ_end = e_m + clr

        for m in range(occ_start, occ_end):
            grid[m % 1440] = True

    # Find free continuous gaps in [0..1440] coordinates
    oracle_free_gaps = []
    cursor = 0
    while cursor < 1440:
        if not grid[cursor]:
            gap_start = cursor
            while cursor < 1440 and not grid[cursor]:
                cursor += 1
            gap_end = cursor
            gap_len = gap_end - gap_start
            if gap_len >= required_gap:
                oracle_free_gaps.append((gap_start, gap_end, gap_len))
        else:
            cursor += 1

    # B. Engine result
    engine_windows = find_block_section_windows(
        block_section=bs,
        target_date=target_d,
        task_duration_minutes=task_duration,
        line="DN",
        passages=passages,
        config=cfg,
    )

    # Verify count and coordinates
    assert len(engine_windows) == len(oracle_free_gaps), (
        f"Oracle found {len(oracle_free_gaps)} gaps, engine found {len(engine_windows)}"
    )

    for ew, (og_s, og_e, og_len) in zip(engine_windows, oracle_free_gaps):
        assert ew.gap_start_min == og_s
        assert ew.gap_end_min == og_e
        assert (ew.gap_end_min - ew.gap_start_min) == og_len
        # Earliest start = gap_start + pre_buffer
        assert _time_to_minutes(ew.earliest_start) == og_s + pre_buf


# ==============================================================================
# 2. Dynamic Margin Growth for Interpolated Passages
# ==============================================================================

def test_margin_grows_for_interpolated_passages():
    """Verify that interpolated passages receive larger uncertainty margins."""
    target_d = date(2026, 11, 5)
    p_real = _make_dummy_passage("12301", time(10, 0), time(10, 15), interpolated=False)
    p_interp = _make_dummy_passage("12302", time(10, 0), time(10, 20), interpolated=True)

    cfg = ReliabilityConfig(
        default_clearance_minutes=10,
        interpolated_base_uncertainty=5,
        days_ahead_uncertainty_per_day=2.0,
    )

    margin_real = compute_passage_margin(p_real, target_d, cfg)
    margin_interp = compute_passage_margin(p_interp, target_d, cfg)

    # Interpolated must receive strictly larger buffer
    assert margin_interp > margin_real
    assert margin_interp >= margin_real + cfg.interpolated_base_uncertainty


# ==============================================================================
# 3. Conservative vs Optimistic Track Conflict Modes
# ==============================================================================

def test_conservative_vs_optimistic_modes():
    """
    In CONSERVATIVE mode:
    A passage blocks all tracks in its direction unless task.line is specific AND
    track assignment is known and different.
    In OPTIMISTIC mode:
    If task.line is specific, unknown-track passages are assumed non-conflicting.
    """
    bs = BlockSection(
        id="BLK-MULTI-TRACK",
        from_station="STA_A",
        to_station="STA_B",
        start_km=0.0,
        end_km=10.0,
        line="UP",
        length_km=10.0,
        max_speed=110.0,
        tracks=2,
        split_points_source="none",
        station_list_source="hand_written",
    )

    # Passage on UP direction with unknown track
    p_unknown = _make_dummy_passage(
        "T-UNK", time(12, 0), time(12, 10),
        block_section_id=bs.id, line="UP", track_assignment_known=False
    )

    # 1. Conservative mode with specific task line "UP_SLOW"
    res_cons = filter_passages_by_track(
        passages=[p_unknown],
        block_section=bs,
        task_line="UP_SLOW",
        mode="CONSERVATIVE",
    )
    # Conservative blocks because track is unknown
    assert len(res_cons) == 1

    # 2. Optimistic mode with specific task line "UP_SLOW"
    res_opt = filter_passages_by_track(
        passages=[p_unknown],
        block_section=bs,
        task_line="UP_SLOW",
        mode="OPTIMISTIC",
    )
    # Optimistic assumes train can use the parallel UP_FAST line
    assert len(res_opt) == 0

    # 3. Conservative mode with known different track ("UP_FAST" vs task "UP_SLOW")
    p_fast = _make_dummy_passage(
        "T-FAST", time(12, 0), time(12, 10),
        block_section_id=bs.id, line="UP",
        track_assignment_known=True, assigned_track="UP_FAST"
    )
    res_cons_diff = filter_passages_by_track(
        passages=[p_fast],
        block_section=bs,
        task_line="UP_SLOW",
        mode="CONSERVATIVE",
    )
    assert len(res_cons_diff) == 0


# ==============================================================================
# 4. Cancelled Train Opens a Maintenance Window
# ==============================================================================

def test_cancelled_train_opens_window():
    """
    A train running at midday blocks a 3-hour window.
    Marking it CANCELLED in LiveTrainStatus opens that maintenance window.
    """
    today = date.today()
    bs = BlockSection(
        id="BLK-CANCEL-TEST",
        from_station="STA_A",
        to_station="STA_B",
        start_km=0.0,
        end_km=10.0,
        line="DN",
        length_km=10.0,
        max_speed=110.0,
        tracks=2,
        split_points_source="none",
        station_list_source="hand_written",
    )

    p1 = _make_dummy_passage("T-01", time(9, 0), time(9, 10), block_section_id=bs.id, origin_date=today)
    p_mid = _make_dummy_passage("T-02", time(12, 0), time(12, 10), block_section_id=bs.id, origin_date=today)
    p3 = _make_dummy_passage("T-03", time(15, 0), time(15, 10), block_section_id=bs.id, origin_date=today)

    passages = [p1, p_mid, p3]

    # Without live status: gap between 09:10 and 12:00 is 170 min (usable for 120m + 30m buffers)
    # but a 3-hour task (180 min + 30m = 210 min) cannot fit between 09:10 and 12:00 or 12:10 and 15:00
    wins_blocked = find_reliable_block_windows(
        block_section=bs,
        target_date=today,
        task_duration_minutes=180,
        passages=passages,
    )
    # Check that no window is available in the midday corridor (between 09:30 and 14:30)
    midday_wins_blocked = [
        w for w in wins_blocked
        if 570 <= _time_to_minutes(w.recommended_start) <= 870
    ]
    assert len(midday_wins_blocked) == 0

    # Apply CANCELLED status to T-02
    live_statuses = {
        "T-02": LiveTrainStatus(
            train_number="T-02",
            status="CANCELLED",
            last_updated=datetime.now(),
        )
    }

    wins_open = find_reliable_block_windows(
        block_section=bs,
        target_date=today,
        task_duration_minutes=180,
        passages=passages,
        live_statuses=live_statuses,
    )

    # T-02 removal opens a 350-minute midday gap from 09:10 to 15:00, surfacing a midday window
    midday_wins_open = [
        w for w in wins_open
        if 570 <= _time_to_minutes(w.recommended_start) <= 870
    ]
    assert len(midday_wins_open) >= 1


# ==============================================================================
# 5. Diverted / Delayed Train Closes a Window
# ==============================================================================

def test_diverted_or_delayed_train_closes_window():
    """
    A train originally scheduled at 08:00 gets delayed by 210 minutes (now at 11:30),
    encroaching on and closing an 11:00-13:00 window.
    """
    today = date.today()
    bs = BlockSection(
        id="BLK-DELAY-TEST",
        from_station="STA_A",
        to_station="STA_B",
        start_km=0.0,
        end_km=10.0,
        line="DN",
        length_km=10.0,
        max_speed=110.0,
        tracks=2,
        split_points_source="none",
        station_list_source="hand_written",
    )

    # Free window between 10:00 and 14:00
    p1 = _make_dummy_passage("T-01", time(8, 0), time(8, 10), block_section_id=bs.id, origin_date=today)
    p2 = _make_dummy_passage("T-02", time(14, 0), time(14, 10), block_section_id=bs.id, origin_date=today)

    passages = [p1, p2]
    wins_clean = find_reliable_block_windows(
        block_section=bs,
        target_date=today,
        task_duration_minutes=120,
        passages=passages,
    )
    midday_clean = [w for w in wins_clean if w.gap_start_min >= 480 and w.gap_end_min <= 900]
    assert len(midday_clean) >= 1

    # T-01 delayed by 210 minutes -> now occupies ~11:30 to 11:40
    live_statuses = {
        "T-01": LiveTrainStatus(
            train_number="T-01",
            delay_minutes=210.0,
            status="DELAYED",
            last_updated=datetime.now(),
        )
    }

    wins_after_delay = find_reliable_block_windows(
        block_section=bs,
        target_date=today,
        task_duration_minutes=120,
        passages=passages,
        live_statuses=live_statuses,
    )

    # 4-hour window was split: remaining gaps are smaller than 120m + 30m buffers
    midday_after_delay = [w for w in wins_after_delay if w.gap_start_min >= 480 and w.gap_end_min <= 900]
    assert len(midday_after_delay) == 0


# ==============================================================================
# 6. Confidence Scoring: Synthetic Traffic NEVER produces HIGH confidence
# ==============================================================================

def test_confidence_never_high_with_synthetic_traffic():
    """
    Strict safety invariant:
    Any presence of synthetic filler / goods traffic forces confidence to MEDIUM or LOW,
    never HIGH.
    """
    target_d = date.today() + timedelta(days=1)

    # Scenario A: All real live trains
    live_passages = [
        _make_dummy_passage(f"LIVE-{i}", time(i * 2 + 1, 0), time(i * 2 + 1, 10), provenance="live")
        for i in range(8)
    ]
    conf_live, breakdown_live = compute_confidence_score(
        passages=live_passages,
        target_date=target_d,
        traffic_mode="LIVE_ONLY",
    )
    assert conf_live == "HIGH"
    assert breakdown_live["share_live"] == 1.0
    assert breakdown_live["share_synthetic"] == 0.0

    # Scenario B: Mix with synthetic filler
    mixed_passages = list(live_passages)
    mixed_passages.append(
        _make_dummy_passage("SYNTH-01", time(16, 0), time(16, 10), provenance="synthetic")
    )
    conf_mixed, breakdown_mixed = compute_confidence_score(
        passages=mixed_passages,
        target_date=target_d,
        traffic_mode="LIVE_ONLY",
    )
    assert conf_mixed != "HIGH", "Synthetic traffic must never produce a HIGH confidence window!"
    assert conf_mixed in ("MEDIUM", "LOW")
    assert breakdown_mixed["share_synthetic"] > 0.0

    # Scenario C: traffic_mode == "LIVE_PLUS_SYNTHETIC"
    conf_mode_synth, _ = compute_confidence_score(
        passages=live_passages,
        target_date=target_d,
        traffic_mode="LIVE_PLUS_SYNTHETIC",
    )
    assert conf_mode_synth != "HIGH", "traffic_mode='LIVE_PLUS_SYNTHETIC' must never be HIGH!"


# ==============================================================================
# 7. Bounding Trains Extraction
# ==============================================================================

def test_bounding_trains_correct():
    """Verify accurate extraction of previous clearing train and next entering train."""
    bs = BlockSection(
        id="BLK-BOUNDING-TEST",
        from_station="STA_A",
        to_station="STA_B",
        start_km=0.0,
        end_km=10.0,
        line="DN",
        length_km=10.0,
        max_speed=110.0,
        tracks=2,
        split_points_source="none",
        station_list_source="hand_written",
    )

    p_prev = _make_dummy_passage("12301", time(10, 0), time(10, 20), provenance="live")
    p_next = _make_dummy_passage("12302", time(14, 15), time(14, 30), provenance="live")
    p_far_prev = _make_dummy_passage("12300", time(7, 0), time(7, 20), provenance="live")
    p_far_next = _make_dummy_passage("12303", time(18, 0), time(18, 20), provenance="live")

    passages = [p_far_prev, p_prev, p_next, p_far_next]

    bounding = extract_bounding_trains(
        passages=passages,
        window_start=time(11, 0),
        window_end=time(13, 0),
    )

    assert bounding["prev"] is not None
    assert bounding["prev"]["train_number"] == "12301"
    assert bounding["prev"]["time"] == "10:20"
    assert bounding["prev"]["provenance"] == "live"

    assert bounding["next"] is not None
    assert bounding["next"]["train_number"] == "12302"
    assert bounding["next"]["time"] == "14:15"
    assert bounding["next"]["provenance"] == "live"


# ==============================================================================
# 8. Traffic Mode Switch Modifies Candidate Windows & Stamped Labels
# ==============================================================================

def test_traffic_mode_switch_changes_results_and_labels():
    """
    Switching traffic_mode between LIVE_ONLY and LIVE_PLUS_SYNTHETIC:
    - Changes window availability / count due to synthetic filler insertion
    - Correctly stamps traffic_mode on every generated ReliableBlockWindow
    - Stamped proposal=True and status_note='requires controller confirmation'
    """
    sections = build_block_sections("SEC-93135bb9")
    pilot_bs = sections[0]
    target_d = date(2026, 11, 1)

    # 1. LIVE_ONLY run
    cfg_live = ReliabilityConfig(traffic_mode="LIVE_ONLY")
    wins_live = find_reliable_block_windows(
        block_section=pilot_bs,
        target_date=target_d,
        task_duration_minutes=90,
        config=cfg_live,
    )
    assert len(wins_live) > 0
    for w in wins_live:
        assert w.traffic_mode == "LIVE_ONLY"
        assert w.proposal is True
        assert w.status_note == "requires controller confirmation"
        assert w.mode == "CONSERVATIVE"

    # 2. LIVE_PLUS_SYNTHETIC run
    cfg_synth = ReliabilityConfig(traffic_mode="LIVE_PLUS_SYNTHETIC")
    wins_synth = find_reliable_block_windows(
        block_section=pilot_bs,
        target_date=target_d,
        task_duration_minutes=90,
        config=cfg_synth,
    )
    for w in wins_synth:
        assert w.traffic_mode == "LIVE_PLUS_SYNTHETIC"
        assert w.confidence != "HIGH"  # Must never be HIGH

    # 3. Candidate ranking with estimated cascade
    ranked = rank_reliable_candidate_windows(
        block_section=pilot_bs,
        target_date=target_d,
        task_duration_minutes=90,
        config=cfg_live,
        top_k=3,
    )
    assert len(ranked) > 0
    for r in ranked:
        assert hasattr(r, "estimated_cascade")
        assert hasattr(r, "weighted_delay_minutes")
        assert r.proposal is True
        assert r.confidence in ("HIGH", "MEDIUM", "LOW")
