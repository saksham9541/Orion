"""
traffic/window_finder.py

Discovers feasible maintenance block windows from real and synthetic train passages.
Supports both:
1. Block-Section Level Window Engine (modern, directional UP/DN, buffer/margin aware)
2. Section Level Window Finder (legacy compatibility with existing endpoints and tests)

Provides:
- Earliest and latest start times with pre- and post-buffers
- Margin before and after with comfort labels (TIGHT / OK / COMFORTABLE)
- Candidate ranking via 5-minute sliding window with train holding and delay cascade
- Single-line vs double-line directional filtering
- Long and busy block section identification
- Window availability scoring (0-100)
- Live delay decay and revalidation
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from typing import Callable, Dict, List, Optional, Tuple

try:
    from zoneinfo import ZoneInfo
    KOLKATA_TZ = ZoneInfo("Asia/Kolkata")
except Exception:
    KOLKATA_TZ = timezone(timedelta(hours=5, minutes=30))

from railopt.models import BlockType, BlockWindow
from traffic.block_sections import (
    BlockSection,
    LONG_BLOCK_THRESHOLD_KM,
    BUSY_OCCUPANCY_SHARE_THRESHOLD,
    build_block_sections,
    get_block_section_by_id,
)
from traffic.fill import get_all_passages_for_section
from traffic.passages import (
    BlockSectionPassage,
    TrainPassage,
    load_pilot_block_passages,
    load_pilot_passages,
)
from traffic.section_map import PilotSectionConfig, get_pilot_section_config


@dataclass
class WindowFinderConfig:
    """Configuration parameters for section-level block window discovery (legacy)."""
    clearance_buffer_minutes: int = 10
    min_window_duration_hours: float = 0.5
    setup_buffer_minutes: int = 15
    max_windows_per_day: int = 6


@dataclass
class BlockWindowConfig:
    """Configuration parameters for Block-Section level window discovery & ranking."""
    clearance_buffer_minutes: int = 10      # Clearance before train enters and after train exits
    default_clearance_minutes: int = 10
    pre_buffer_minutes: int = 15           # Setup buffer before task work starts
    post_buffer_minutes: int = 15          # Handover buffer after task work ends
    tight_margin_threshold_minutes: int = 15        # Margin < 15m -> TIGHT
    comfortable_margin_threshold_minutes: int = 30  # Margin >= 30m -> COMFORTABLE
    step_minutes: int = 5                  # Sliding window resolution
    min_headway_minutes: int = 5           # Minimum headway between trains for delay cascade
    decay_horizon_hours: float = 6.0       # Live delay decay horizon (delay decays to 0 over 6h)
    long_block_km: float = LONG_BLOCK_THRESHOLD_KM
    busy_occupancy_share: float = BUSY_OCCUPANCY_SHARE_THRESHOLD
    traffic_mode: str = "LIVE_ONLY"        # "LIVE_ONLY" | "LIVE_PLUS_SYNTHETIC"

    def __post_init__(self):
        if self.default_clearance_minutes != 10 and self.clearance_buffer_minutes == 10:
            self.clearance_buffer_minutes = self.default_clearance_minutes


@dataclass
class UsableBlockWindow:
    """A feasible maintenance window on a specific block section and line."""
    window_id: str
    block_section_id: str
    line: str  # "UP" | "DN" | "BOTH"
    date: date
    gap_start_min: int
    gap_end_min: int
    earliest_start: time
    latest_start: time
    recommended_start: time
    recommended_end: time
    duration_hours: float
    task_duration_minutes: int
    pre_buffer_minutes: int
    post_buffer_minutes: int
    margin_before_min: int
    margin_after_min: int
    comfort_label: str  # "TIGHT" | "OK" | "COMFORTABLE"
    freight_unverified: bool
    known_trains: int
    estimated_total_trains: int
    coverage: float  # known_trains / estimated_total_trains (only provenance='live' counts as real)
    traffic_mode: str = "LIVE_ONLY"  # "LIVE_ONLY" | "LIVE_PLUS_SYNTHETIC"
    source: str = "timetable_derived"
    is_free_gap: bool = True
    trains_held: int = 0
    total_delay_minutes: float = 0.0
    score: float = 100.0
    score_breakdown: dict = field(default_factory=dict)
    reason_codes: List[str] = field(default_factory=list)

    def to_block_window(self, corridor_id: str = "", section_id: str = "") -> BlockWindow:
        """Convert UsableBlockWindow to standard BlockWindow for CP-SAT solver and legacy APIs."""
        return BlockWindow(
            window_id=self.window_id,
            corridor_id=corridor_id,
            section_id=section_id,
            block_section_id=self.block_section_id,
            line=self.line,
            date=self.date,
            start_time=self.recommended_start,
            end_time=self.recommended_end,
            duration_hours=self.duration_hours,
            source=self.source,
            delay_source="computed",
            ml_trains_affected=self.trains_held,
            ml_cumulative_delay_minutes=self.total_delay_minutes,
            ml_traffic_impact_score=round(max(0.0, 100.0 - self.score), 1),
        )


def _time_to_minutes(t: time) -> int:
    """Convert time object to integer minutes since midnight (0..1439)."""
    return t.hour * 60 + t.minute


def _minutes_to_time(m: int) -> time:
    """Convert integer minutes since midnight to time object (clamped to 23:59)."""
    m = max(0, min(1439, m))
    return time(m // 60, m % 60)


def filter_windows_for_task(
    windows: List[BlockWindow],
    task_duration_hours: float,
    setup_buffer_hours: float = 0.25,
) -> List[BlockWindow]:
    """Task-specific window filter for section-level BlockWindow objects."""
    needed = task_duration_hours + setup_buffer_hours
    return [w for w in windows if w.duration_hours >= needed]


# ----------------------------------------------------------------------
# Block-Section Window Engine (Phase 1 core)
# ----------------------------------------------------------------------

def find_block_section_windows(
    block_section: BlockSection,
    target_date: date,
    task_duration_minutes: int = 120,
    line: Optional[str] = None,
    line_filter: Optional[str] = None,
    requires_both_lines: bool = False,
    passages: Optional[List[BlockSectionPassage]] = None,
    config: Optional[BlockWindowConfig] = None,
    snapshot_dir=None,
    passage_margin_fn: Optional[Callable[[BlockSectionPassage], int]] = None,
) -> List[UsableBlockWindow]:
    """
    Finds clean free gaps on block_section for target_date.
    
    Occupied = passage enter/exit +/- clearance (default 10 min); merged.
    Required gap = task_duration + pre_buffer + post_buffer (defaults 15/15).
    For each usable gap returns:
    - earliest_start = gap_start + pre_buffer
    - latest_start = gap_end - post_buffer - task_duration
    - margin_before_min, margin_after_min
    - comfort label (TIGHT / OK / COMFORTABLE)
    - freight_unverified flag
    - known_trains / estimated_total_trains (coverage counts only live provenance)
    """
    cfg = config or BlockWindowConfig()
    req_line = line or line_filter or block_section.line

    # Load passages if not supplied
    if passages is None:
        if cfg.traffic_mode == "LIVE_PLUS_SYNTHETIC":
            from traffic.fill import get_all_block_section_passages
            passages, _ = get_all_block_section_passages(
                block_section=block_section,
                target_date=target_date,
                snapshot_dir=snapshot_dir,
            )
        else:
            passages = load_pilot_block_passages(
                pilot_section_id=block_section.pilot_section_id,
                target_date=target_date,
                snapshot_dir=snapshot_dir,
            )

    # Line filtering rule (Double line vs Single line)
    # Double line counts only relevant line unless requires_both_lines
    # Single line counts both directions
    relevant_passages: List[BlockSectionPassage] = []
    for p in passages:
        if p.block_section_id != block_section.id:
            continue
        if cfg.traffic_mode == "LIVE_ONLY" and getattr(p, "provenance", "") == "synthetic":
            continue
        if block_section.tracks == 1 or requires_both_lines or req_line == "BOTH":
            relevant_passages.append(p)
        elif p.line == req_line or p.line == block_section.line:
            relevant_passages.append(p)

    # Coverage metrics: only provenance="live" counts as real
    live_trains = sum(1 for p in relevant_passages if p.provenance == "live")
    total_trains = len(relevant_passages)
    coverage = round(live_trains / max(total_trains, 1), 3)
    freight_unverified = any(p.train_type.value == "FREIGHT" or p.provenance == "synthetic" for p in relevant_passages)

    # 1. Build occupied intervals in minute coordinates [0..1440]
    occupied: List[Tuple[int, int]] = []

    for p in relevant_passages:
        # Time within target date in minutes
        s_min = _time_to_minutes(p.enter_time)
        e_min = _time_to_minutes(p.exit_time)
        if e_min < s_min:
            e_min += 1440

        # Padded with clearance buffer or per-passage margin
        buf = passage_margin_fn(p) if passage_margin_fn is not None else cfg.clearance_buffer_minutes
        occ_s = max(0, s_min - buf)
        occ_e = e_min + buf

        if occ_s < 1440:
            occupied.append((occ_s, min(1440, occ_e)))
        if occ_e > 1440:
            occupied.append((0, min(1440, occ_e - 1440)))

    # Sort and merge occupied intervals
    occupied.sort(key=lambda x: x[0])
    merged_occupied: List[List[int]] = []
    for s, e in occupied:
        if not merged_occupied or s > merged_occupied[-1][1]:
            merged_occupied.append([s, e])
        else:
            merged_occupied[-1][1] = max(merged_occupied[-1][1], e)

    # 2. Extract free gaps between occupied intervals
    free_gaps: List[Tuple[int, int, int]] = []  # (gap_start, gap_end, gap_length)
    cursor = 0
    for s, e in merged_occupied:
        if s > cursor:
            free_gaps.append((cursor, s, s - cursor))
        cursor = max(cursor, e)
    if cursor < 1440:
        free_gaps.append((cursor, 1440, 1440 - cursor))

    # 3. Required total gap duration = task duration + pre_buffer + post_buffer
    required_min = task_duration_minutes + cfg.pre_buffer_minutes + cfg.post_buffer_minutes

    usable_windows: List[UsableBlockWindow] = []
    for idx, (gap_s, gap_e, gap_len) in enumerate(free_gaps):
        if gap_len < required_min:
            continue

        earliest_start_min = gap_s + cfg.pre_buffer_minutes
        latest_start_min = gap_e - cfg.post_buffer_minutes - task_duration_minutes

        total_margin = gap_len - required_min
        # Center recommended start within the gap
        recommended_start_min = earliest_start_min + (total_margin // 2)
        recommended_end_min = recommended_start_min + task_duration_minutes

        margin_before = recommended_start_min - cfg.pre_buffer_minutes - gap_s
        margin_after = gap_e - (recommended_end_min + cfg.post_buffer_minutes)

        # Comfort label based on total available margin
        if total_margin < cfg.tight_margin_threshold_minutes:
            comfort = "TIGHT"
        elif total_margin >= cfg.comfortable_margin_threshold_minutes:
            comfort = "COMFORTABLE"
        else:
            comfort = "OK"

        win_id = f"BW-{block_section.id[:8]}-{target_date.strftime('%Y%m%d')}-{idx+1:02d}"

        usable_windows.append(
            UsableBlockWindow(
                window_id=win_id,
                block_section_id=block_section.id,
                line=req_line,
                date=target_date,
                gap_start_min=gap_s,
                gap_end_min=gap_e,
                earliest_start=_minutes_to_time(earliest_start_min),
                latest_start=_minutes_to_time(latest_start_min),
                recommended_start=_minutes_to_time(recommended_start_min),
                recommended_end=_minutes_to_time(recommended_end_min),
                duration_hours=round(task_duration_minutes / 60.0, 2),
                task_duration_minutes=task_duration_minutes,
                pre_buffer_minutes=cfg.pre_buffer_minutes,
                post_buffer_minutes=cfg.post_buffer_minutes,
                margin_before_min=margin_before,
                margin_after_min=margin_after,
                comfort_label=comfort,
                freight_unverified=freight_unverified,
                known_trains=live_trains,
                estimated_total_trains=total_trains,
                coverage=coverage,
                traffic_mode=cfg.traffic_mode,
                source="timetable_derived",
                is_free_gap=True,
                trains_held=0,
                total_delay_minutes=0.0,
                score=100.0,
                score_breakdown={"base": 100.0, "clean_gap_bonus": 15.0, "margin_bonus": min(15.0, total_margin / 2.0)},
                reason_codes=["FREE_GAP", f"MARGIN_{comfort}"] + (["FREIGHT_UNVERIFIED"] if freight_unverified else []),
            )
        )

    return usable_windows


def rank_candidate_windows(
    block_section: BlockSection,
    target_date: date,
    task_duration_minutes: int = 120,
    line: str = "DN",
    requires_both_lines: bool = False,
    preferred_period: str = "ANY",  # "NIGHT" | "DAY" | "ANY"
    requires_power_block: bool = False,
    has_alternate_route: bool = True,
    alternate_route_penalty_minutes: float = 22.0,
    passages: Optional[List[BlockSectionPassage]] = None,
    config: Optional[BlockWindowConfig] = None,
    top_k: int = 5,
    snapshot_dir=None,
    passage_margin_fn: Optional[Callable[[BlockSectionPassage], int]] = None,
) -> List[UsableBlockWindow]:
    """
    Sliding window candidate evaluation (every 5 min over the 24h day).
    Computes overlapping trains, hold delay (block_end + clearance - scheduled_enter),
    and cascade to downstream stops and following trains by min headway.
    
    Ranks by:
    1. Trains held (ascending)
    2. Total delay incl. cascade (ascending)
    3. Time-of-day alignment
    4. Margin & comfort
    5. Alternate route availability
    """
    cfg = config or BlockWindowConfig()
    req_line = line or block_section.line

    if passages is None:
        if cfg.traffic_mode == "LIVE_PLUS_SYNTHETIC":
            from traffic.fill import get_all_block_section_passages
            passages, _ = get_all_block_section_passages(
                block_section=block_section,
                target_date=target_date,
                snapshot_dir=snapshot_dir,
            )
        else:
            passages = load_pilot_block_passages(
                pilot_section_id=block_section.pilot_section_id,
                target_date=target_date,
                snapshot_dir=snapshot_dir,
            )

    # Filter passages by line
    active_passages: List[BlockSectionPassage] = []
    for p in passages:
        if p.block_section_id != block_section.id:
            continue
        if cfg.traffic_mode == "LIVE_ONLY" and getattr(p, "provenance", "") == "synthetic":
            continue
        if block_section.tracks == 1 or requires_both_lines or req_line == "BOTH":
            active_passages.append(p)
        elif p.line == req_line or p.line == block_section.line:
            active_passages.append(p)

    live_trains = sum(1 for p in active_passages if p.provenance == "live")
    total_trains = len(active_passages)
    coverage = round(live_trains / max(total_trains, 1), 3)
    freight_unverified = any(p.train_type.value == "FREIGHT" or p.provenance == "synthetic" for p in active_passages)

    # First check clean free gaps
    free_windows = find_block_section_windows(
        block_section=block_section,
        target_date=target_date,
        task_duration_minutes=task_duration_minutes,
        line_filter=req_line,
        requires_both_lines=requires_both_lines,
        passages=passages,
        config=cfg,
        snapshot_dir=snapshot_dir,
        passage_margin_fn=passage_margin_fn,
    )

    candidates: List[UsableBlockWindow] = list(free_windows)

    # Slide start time every step_minutes across the day (0..1440)
    step = cfg.step_minutes
    pre = cfg.pre_buffer_minutes
    post = cfg.post_buffer_minutes
    clr = cfg.clearance_buffer_minutes
    headway = cfg.min_headway_minutes

    for start_m in range(0, 1440 - task_duration_minutes - post, step):
        win_start_m = start_m - pre
        win_end_m = start_m + task_duration_minutes + post

        # Check overlapping passages
        held_trains: List[BlockSectionPassage] = []
        for p in active_passages:
            p_enter = _time_to_minutes(p.enter_time)
            p_exit = _time_to_minutes(p.exit_time)
            if p_exit < p_enter:
                p_exit += 1440

            p_clr = passage_margin_fn(p) if passage_margin_fn is not None else clr
            # Overlap test with clearance buffer
            if (p_enter - p_clr) < win_end_m and win_start_m < (p_exit + p_clr):
                held_trains.append(p)

        if not held_trains:
            # Already surfaced via clean free gaps finder
            continue

        # Compute hold delay for each held train using canonical shared delay function
        from traffic.delay_model import compute_train_hold_delay
        total_delay = 0.0
        train_delays: List[float] = []
        for p in held_trains:
            p_enter = _time_to_minutes(p.enter_time)
            p_clr = passage_margin_fn(p) if passage_margin_fn is not None else clr
            hold = compute_train_hold_delay(
                block_end_minutes=win_end_m,
                enter_minutes=p_enter,
                clearance_margin_minutes=p_clr,
                has_alternate_route=has_alternate_route,
                alternate_route_penalty_minutes=alternate_route_penalty_minutes,
            )
            train_delays.append(hold)
            total_delay += hold

        # Headway cascade to following trains
        cascade_delay = 0.0
        active_sorted = sorted(active_passages, key=lambda p: _time_to_minutes(p.enter_time))
        for ht, ht_delay in zip(held_trains, train_delays):
            ht_new_enter = _time_to_minutes(ht.enter_time) + ht_delay
            for other in active_sorted:
                if other.train_no == ht.train_no:
                    continue
                other_enter = _time_to_minutes(other.enter_time)
                if other_enter > _time_to_minutes(ht.enter_time) and other_enter < ht_new_enter + headway:
                    push = max(0.0, (ht_new_enter + headway) - other_enter)
                    cascade_delay += push

        cumulative_delay = round(total_delay + cascade_delay, 1)

        # Time of day alignment score
        tod_score = 0.0
        is_night = (60 <= start_m <= 300)  # 01:00 to 05:00
        is_day = (540 <= start_m <= 1020)  # 09:00 to 17:00
        if preferred_period == "NIGHT" and is_night:
            tod_score = 25.0
        elif preferred_period == "DAY" and is_day:
            tod_score = 25.0
        elif preferred_period == "ANY":
            tod_score = 10.0 if is_night else 5.0

        # Score calculation (higher is better)
        score = 80.0 - (len(held_trains) * 20.0) - (cumulative_delay * 0.3) + tod_score
        score = max(5.0, round(score, 1))

        reason_codes = ["TRAINS_HELD"]
        if freight_unverified:
            reason_codes.append("FREIGHT_UNVERIFIED")
        if requires_power_block:
            reason_codes.append("POWER_BLOCK_ISOLATION")

        win_id = f"BW-SLIDE-{block_section.id[:8]}-{target_date.strftime('%Y%m%d')}-{start_m:04d}"

        candidates.append(
            UsableBlockWindow(
                window_id=win_id,
                block_section_id=block_section.id,
                line=req_line,
                date=target_date,
                gap_start_min=win_start_m,
                gap_end_min=win_end_m,
                earliest_start=_minutes_to_time(start_m),
                latest_start=_minutes_to_time(start_m),
                recommended_start=_minutes_to_time(start_m),
                recommended_end=_minutes_to_time(start_m + task_duration_minutes),
                duration_hours=round(task_duration_minutes / 60.0, 2),
                task_duration_minutes=task_duration_minutes,
                pre_buffer_minutes=pre,
                post_buffer_minutes=post,
                margin_before_min=0,
                margin_after_min=0,
                comfort_label="TIGHT",
                freight_unverified=freight_unverified,
                known_trains=live_trains,
                estimated_total_trains=total_trains,
                coverage=coverage,
                traffic_mode=cfg.traffic_mode,
                source="sliding_candidate",
                is_free_gap=False,
                trains_held=len(held_trains),
                total_delay_minutes=cumulative_delay,
                score=score,
                score_breakdown={
                    "base": 80.0,
                    "trains_held_penalty": -(len(held_trains) * 20.0),
                    "delay_penalty": -(cumulative_delay * 0.3),
                    "time_of_day_score": tod_score,
                },
                reason_codes=reason_codes,
            )
        )

    # Rank: free gaps first, then lowest trains held, lowest delay, highest score
    candidates.sort(
        key=lambda w: (
            0 if w.is_free_gap else 1,
            w.trains_held,
            w.total_delay_minutes,
            -w.score,
        )
    )

    return candidates[:top_k]


class BlockAvailabilityResult(dict):
    """Dictionary subclass supporting dot-attribute access."""
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)

    def __setattr__(self, name, value):
        self[name] = value


class RevalidationResult(dict):
    """Dictionary subclass supporting dot-attribute access."""
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)

    def __setattr__(self, name, value):
        self[name] = value


def calculate_block_availability(
    block_section: BlockSection,
    target_date: date,
    passages: Optional[List[BlockSectionPassage]] = None,
    config: Optional[BlockWindowConfig] = None,
    task_duration_minutes: int = 120,
    snapshot_dir=None,
) -> BlockAvailabilityResult:
    """
    Computes window_availability_score (0-100), long and busy block flags,
    longest contiguous free gap, comfort distribution, and total free contiguous minutes.
    """
    cfg = config or BlockWindowConfig()

    if passages is None:
        passages = load_pilot_block_passages(
            pilot_section_id=block_section.pilot_section_id,
            target_date=target_date,
            snapshot_dir=snapshot_dir,
        )

    # Filter to this block section
    bs_passages = [p for p in passages if p.block_section_id == block_section.id]
    total_occupancy_mins = sum(p.transit_minutes() for p in bs_passages)

    # Busy flag: > 60% of 1440 min
    occupancy_share = min(1.0, total_occupancy_mins / 1440.0)
    is_busy = occupancy_share >= cfg.busy_occupancy_share

    # Free windows for requested duration
    usable = find_block_section_windows(
        block_section=block_section,
        target_date=target_date,
        task_duration_minutes=task_duration_minutes,
        passages=bs_passages,
        config=cfg,
    )

    comfort_dist = {
        "COMFORTABLE": sum(1 for w in usable if w.comfort_label == "COMFORTABLE"),
        "OK": sum(1 for w in usable if w.comfort_label == "OK"),
        "TIGHT": sum(1 for w in usable if w.comfort_label == "TIGHT"),
    }

    # Free contiguous minutes and longest gap
    buf = cfg.clearance_buffer_minutes
    occ_intervals: List[Tuple[int, int]] = []
    for p in bs_passages:
        s = _time_to_minutes(p.enter_time)
        e = _time_to_minutes(p.exit_time)
        if e < s:
            e += 1440
        occ_intervals.append((max(0, s - buf), min(1440, e + buf)))

    occ_intervals.sort(key=lambda x: x[0])
    merged: List[List[int]] = []
    for s, e in occ_intervals:
        if not merged or s > merged[-1][1]:
            merged.append([s, e])
        else:
            merged[-1][1] = max(merged[-1][1], e)

    free_gaps: List[int] = []
    cursor = 0
    for s, e in merged:
        if s > cursor:
            free_gaps.append(s - cursor)
        cursor = max(cursor, e)
    if cursor < 1440:
        free_gaps.append(1440 - cursor)

    longest_gap_mins = max(free_gaps) if free_gaps else 0
    total_free_mins = sum(free_gaps)

    # Availability score composite:
    # 40% usable windows count (>=3 windows = full 40 pts)
    # 30% longest gap (>=240 min = full 30 pts)
    # 30% total free time (>=720 min = full 30 pts)
    score_windows = min(40.0, len(usable) * 13.3)
    score_longest = min(30.0, (longest_gap_mins / 240.0) * 30.0)
    score_total = min(30.0, (total_free_mins / 720.0) * 30.0)
    availability_score = round(score_windows + score_longest + score_total, 1)

    return BlockAvailabilityResult({
        "block_section_id": block_section.id,
        "name": block_section.name,
        "line": block_section.line,
        "length_km": block_section.length_km,
        "is_long": block_section.length_km > cfg.long_block_km,
        "is_busy": is_busy,
        "daily_occupancy_share": round(occupancy_share, 4),
        "occupancy_share_pct": round(occupancy_share * 100.0, 1),
        "total_trains": len(bs_passages),
        "free_window_count": len(usable),
        "usable_2h_windows_count": len(usable),
        "max_free_gap_minutes": longest_gap_mins,
        "longest_free_gap_minutes": longest_gap_mins,
        "total_free_minutes": total_free_mins,
        "comfort_distribution": comfort_dist,
        "window_availability_score": availability_score,
        "recommendation": "SUITABLE_FOR_MAINTENANCE" if availability_score >= 50.0 else "CONSTRAINED_TRAFFIC",
    })


def revalidate_window(
    arg1: Any,
    arg2: Any,
    passages: Optional[List[BlockSectionPassage]] = None,
    live_delays: Optional[Dict[str, float]] = None,
    live_delays_map: Optional[Dict[str, float]] = None,
    config: Optional[BlockWindowConfig] = None,
) -> RevalidationResult:
    """
    Revalidates approaching trains against the window interval,
    applying live delays with a 6-hour linear decay horizon.
    Returns whether the window is still conflict-free and the next best start time.
    """
    if isinstance(arg1, BlockSection):
        block_section = arg1
        window = arg2
    else:
        window = arg1
        block_section = arg2

    delays = live_delays or live_delays_map or {}
    cfg = config or BlockWindowConfig()
    now_dt = datetime.now(KOLKATA_TZ)

    if passages is None:
        passages = load_pilot_block_passages(
            pilot_section_id=block_section.pilot_section_id,
            target_date=window.date,
        )

    # Apply live delay decay over 6 hours
    shifted_passages: List[BlockSectionPassage] = []

    for p in passages:
        if p.block_section_id != block_section.id:
            continue
        delay_min = delays.get(p.train_no, 0.0)
        if delay_min > 0.0:
            # Hours ahead of passage entry
            hours_ahead = max(0.0, (p.enter_datetime - now_dt).total_seconds() / 3600.0)
            decay_factor = max(0.0, 1.0 - (hours_ahead / cfg.decay_horizon_hours))
            effective_delay = delay_min * decay_factor
            shifted_passages.append(
                BlockSectionPassage(
                    train_no=p.train_no,
                    train_name=p.train_name,
                    train_type=p.train_type,
                    block_section_id=p.block_section_id,
                    line=p.line,
                    enter_datetime=p.enter_datetime + timedelta(minutes=effective_delay),
                    exit_datetime=p.exit_datetime + timedelta(minutes=effective_delay),
                    enter_time=(p.enter_datetime + timedelta(minutes=effective_delay)).time(),
                    exit_time=(p.exit_datetime + timedelta(minutes=effective_delay)).time(),
                    interpolated=p.interpolated,
                    provenance=p.provenance,
                    origin_date=p.origin_date,
                    block_date=p.block_date,
                    source=p.source,
                )
            )
        else:
            shifted_passages.append(p)

    # Check conflict with window interval
    w_start_m = _time_to_minutes(window.recommended_start) - window.pre_buffer_minutes
    w_end_m = _time_to_minutes(window.recommended_end) + window.post_buffer_minutes
    clr = cfg.clearance_buffer_minutes

    conflicts: List[dict] = []
    for p in shifted_passages:
        if p.line != window.line and window.line != "BOTH":
            continue
        p_enter = _time_to_minutes(p.enter_time)
        p_exit = _time_to_minutes(p.exit_time)
        if p_exit < p_enter:
            p_exit += 1440

        if (p_enter - clr) < w_end_m and w_start_m < (p_exit + clr):
            conflicts.append({
                "train_no": p.train_no,
                "train_name": p.train_name,
                "enter_time": p.enter_time.strftime("%H:%M"),
                "exit_time": p.exit_time.strftime("%H:%M"),
                "encroachment_minutes": min(w_end_m, p_exit + clr) - max(w_start_m, p_enter - clr),
            })

    if not conflicts:
        return RevalidationResult({
            "is_valid": True,
            "conflicts": [],
            "encroaching_trains": [],
            "next_best_start": window.recommended_start,
            "confidence": 0.95,
            "reasons": ["NO_CONFLICT_DETECTED"],
            "status": "VALID",
        })

    # If encroached, find next best start time via candidate ranking
    ranked = rank_candidate_windows(
        block_section=block_section,
        target_date=window.date,
        task_duration_minutes=window.task_duration_minutes,
        line=window.line,
        passages=shifted_passages,
        config=cfg,
        top_k=1,
    )
    next_start = ranked[0].recommended_start if ranked else window.recommended_start

    return RevalidationResult({
        "is_valid": False,
        "conflicts": conflicts,
        "encroaching_trains": conflicts,
        "next_best_start": next_start,
        "confidence": 0.45,
        "reasons": ["APPROACHING_TRAIN_ENCROACHMENT"],
        "status": "ENCROACHED",
    })


# ----------------------------------------------------------------------
# Legacy Section-level Window Finder (Maintained for existing API/tests)
# ----------------------------------------------------------------------

def find_free_windows(
    sec_cfg: PilotSectionConfig | str,
    target_date: date,
    passages: Optional[List[TrainPassage]] = None,
    config: Optional[WindowFinderConfig] = None,
    min_duration_hours: Optional[float] = None,
    snapshot_dir=None,
) -> List[BlockWindow]:
    """
    Legacy Section-level window finder for pilot sections.
    Yields BlockWindow objects compatible with BlockScheduler.
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

    occupied_intervals: List[Tuple[int, int]] = []
    buf = cfg.clearance_buffer_minutes

    for p in passages:
        s = _time_to_minutes(p.enter_time)
        e = _time_to_minutes(p.exit_time)
        if e < s:
            e += 1440
        occ_s = max(0, s - buf)
        occ_e = e + buf
        if occ_s < 1440:
            occupied_intervals.append((occ_s, min(1440, occ_e)))
        if occ_e > 1440:
            occupied_intervals.append((0, min(1440, occ_e - 1440)))

    occupied_intervals.sort(key=lambda iv: iv[0])
    merged_occupied: List[List[int]] = []
    for iv_s, iv_e in occupied_intervals:
        if not merged_occupied or iv_s > merged_occupied[-1][1]:
            merged_occupied.append([iv_s, iv_e])
        else:
            merged_occupied[-1][1] = max(merged_occupied[-1][1], iv_e)

    free_gaps: List[Tuple[int, int, int]] = []
    cursor = 0
    for occ_s, occ_e in merged_occupied:
        if occ_s > cursor:
            free_gaps.append((cursor, occ_s, occ_s - cursor))
        cursor = max(cursor, occ_e)
    if cursor < 1440:
        free_gaps.append((cursor, 1440, 1440 - cursor))

    effective_min_hours = min_duration_hours if min_duration_hours is not None else cfg.min_window_duration_hours
    min_duration_mins = int(effective_min_hours * 60)
    qualifying_gaps = [g for g in free_gaps if g[2] >= min_duration_mins]

    if not qualifying_gaps and free_gaps:
        free_gaps.sort(key=lambda g: g[2], reverse=True)
        if free_gaps[0][2] >= 30:
            qualifying_gaps = [free_gaps[0]]

    qualifying_gaps.sort(key=lambda g: g[2], reverse=True)
    selected_gaps = qualifying_gaps[: cfg.max_windows_per_day]
    selected_gaps.sort(key=lambda g: g[0])

    windows: List[BlockWindow] = []
    for idx, (gap_s, gap_e, gap_len) in enumerate(selected_gaps):
        actual_s = (gap_s // 5) * 5
        actual_e = (gap_e // 5) * 5
        if actual_e <= actual_s:
            continue

        dur_hours = round((actual_e - actual_s) / 60.0, 2)
        if dur_hours < effective_min_hours:
            continue

        start_t = _minutes_to_time(actual_s)
        end_t = time(23, 59) if actual_e >= 1440 else _minutes_to_time(actual_e)
        win_id = f"WIN-TT-{sec_cfg.section_id[:8]}-{target_date.strftime('%Y%m%d')}-{idx+1:02d}"
        max_t = 6 if dur_hours >= 3.0 else (5 if dur_hours >= 2.0 else 3)

        windows.append(
            BlockWindow(
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
        )

    return windows
