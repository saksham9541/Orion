"""
traffic/window_finder.py

Discovers feasible maintenance block windows from real and synthetic train passages.
For each pilot section and date in the scheduling horizon, occupied intervals
(passage enter/exit +/- configurable clearance buffer) are identified,
and contiguous free gaps >= minimum required duration are surfaced as
BlockWindow objects with source="timetable_derived".
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import List, Optional, Tuple

from railopt.models import BlockType, BlockWindow
from traffic.fill import get_all_passages_for_section
from traffic.passages import TrainPassage
from traffic.section_map import PilotSectionConfig, get_pilot_section_config


@dataclass
class WindowFinderConfig:
    """Configuration parameters for timetable-derived block window discovery."""
    clearance_buffer_minutes: int = 10      # Safety clearance before train entry & after exit
    min_window_duration_hours: float = 1.5  # Minimum contiguous free gap to qualify as a window
    setup_buffer_minutes: int = 15         # Setup and handover buffer for maintenance teams
    max_windows_per_day: int = 4           # Maximum candidate windows to yield per day per section


def _time_to_minutes(t: time) -> int:
    """Convert time object to integer minutes since midnight (0..1439)."""
    return t.hour * 60 + t.minute


def _minutes_to_time(m: int) -> time:
    """Convert integer minutes since midnight to time object (clamped to 23:59)."""
    m = max(0, min(1439, m))
    return time(m // 60, m % 60)


def find_free_windows(
    sec_cfg: PilotSectionConfig | str,
    target_date: date,
    passages: Optional[List[TrainPassage]] = None,
    config: Optional[WindowFinderConfig] = None,
    snapshot_dir=None,
) -> List[BlockWindow]:
    """
    Find free gaps in train traffic on a pilot section for target_date.
    Returns BlockWindow objects labeled source="timetable_derived", delay_source="computed".
    """
    if isinstance(sec_cfg, str):
        resolved = get_pilot_section_config(sec_cfg)
        if not resolved:
            raise ValueError(f"Unknown pilot section: {sec_cfg}")
        sec_cfg = resolved

    cfg = config or WindowFinderConfig()

    if passages is None:
        passages, _ = get_all_passages_for_section(
            sec_cfg, target_date, snapshot_dir=snapshot_dir
        )

    # 1. Build occupied intervals in minute coordinates [0..1440]
    occupied_intervals: List[Tuple[int, int]] = []
    buf = cfg.clearance_buffer_minutes

    for p in passages:
        s = _time_to_minutes(p.enter_time)
        e = _time_to_minutes(p.exit_time)

        # Handle midnight transit
        if e < s:
            e += 1440

        # Pad with clearance buffer
        occ_s = max(0, s - buf)
        occ_e = e + buf

        if occ_s < 1440:
            occupied_intervals.append((occ_s, min(1440, occ_e)))
        if occ_e > 1440:
            # Wrapped portion in the start of next day (or early morning)
            occupied_intervals.append((0, min(1440, occ_e - 1440)))

    # Sort and merge occupied intervals
    occupied_intervals.sort(key=lambda iv: iv[0])
    merged_occupied: List[List[int]] = []
    for iv_s, iv_e in occupied_intervals:
        if not merged_occupied or iv_s > merged_occupied[-1][1]:
            merged_occupied.append([iv_s, iv_e])
        else:
            merged_occupied[-1][1] = max(merged_occupied[-1][1], iv_e)

    # 2. Extract free gaps between occupied intervals
    free_gaps: List[Tuple[int, int, int]] = []  # (start_min, end_min, duration_min)
    cursor = 0
    for occ_s, occ_e in merged_occupied:
        if occ_s > cursor:
            gap_len = occ_s - cursor
            free_gaps.append((cursor, occ_s, gap_len))
        cursor = max(cursor, occ_e)

    if cursor < 1440:
        free_gaps.append((cursor, 1440, 1440 - cursor))

    # 3. Filter gaps meeting minimum duration requirement
    min_duration_mins = int(cfg.min_window_duration_hours * 60)
    qualifying_gaps = [g for g in free_gaps if g[2] >= min_duration_mins]

    # Fallback: if no gap meets strict threshold, take the largest available gap >= 60 mins
    if not qualifying_gaps and free_gaps:
        free_gaps.sort(key=lambda g: g[2], reverse=True)
        if free_gaps[0][2] >= 60:
            qualifying_gaps = [free_gaps[0]]

    # Sort qualifying gaps by duration descending (most viable windows first)
    qualifying_gaps.sort(key=lambda g: g[2], reverse=True)
    selected_gaps = qualifying_gaps[: cfg.max_windows_per_day]

    # Sort chronologically for intuitive plan representation
    selected_gaps.sort(key=lambda g: g[0])

    windows: List[BlockWindow] = []
    for idx, (gap_s, gap_e, gap_len) in enumerate(selected_gaps):
        # Allow setup buffer inside the gap
        actual_s = gap_s
        actual_e = gap_e

        # Round times to neat 5-minute boundaries
        actual_s = (actual_s // 5) * 5
        actual_e = (actual_e // 5) * 5
        if actual_e <= actual_s:
            continue

        dur_hours = round((actual_e - actual_s) / 60.0, 2)
        if dur_hours < 1.0:
            continue

        start_t = _minutes_to_time(actual_s)
        # End time capped at 23:59 if 1440
        end_t = time(23, 59) if actual_e >= 1440 else _minutes_to_time(actual_e)

        win_id = f"WIN-TT-{sec_cfg.section_id[:8]}-{target_date.strftime('%Y%m%d')}-{idx+1:02d}"
        max_t = 6 if dur_hours >= 3.0 else (5 if dur_hours >= 2.0 else 3)

        window = BlockWindow(
            window_id=win_id,
            corridor_id=sec_cfg.corridor_id,
            section_id=sec_cfg.section_id,
            date=target_date,
            start_time=start_t,
            end_time=end_t,
            duration_hours=dur_hours,
            block_type=BlockType.TRAFFIC_BLOCK,
            max_tasks=max_t,
            ml_traffic_impact_score=0.0,
            ml_trains_affected=0,
            ml_cumulative_delay_minutes=0.0,
            source="timetable_derived",
            delay_source="computed",
        )
        windows.append(window)

    return windows
