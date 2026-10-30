"""
traffic/window_reliability.py

Reliability layer wrapping the Phase 1 Block-Section Window Engine.
Provides:
1. Dynamic per-passage margins (clearance + uncertainty based on interpolation, days ahead, delay spread).
2. Multi-track modeling with CONSERVATIVE (default) and OPTIMISTIC conflict evaluation.
3. Multi-factor confidence scoring (HIGH/MEDIUM/LOW) with full audit breakdown;
   strictly enforces that synthetic traffic can NEVER produce a HIGH confidence window.
4. Bounding trains extraction (prev train clearing block, next train entering block).
5. Live status adjustments within 24h (cancelled trains opening gaps, diverted/rescheduled closing gaps, stale flagging).
6. Estimated cascade delay weighted by train type priority weights shared with CP-SAT solver.
7. Mandatory proposal designation: every window carries proposal=True and 'requires controller confirmation'.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    from zoneinfo import ZoneInfo
    KOLKATA_TZ = ZoneInfo("Asia/Kolkata")
except Exception:
    KOLKATA_TZ = timezone(timedelta(hours=5, minutes=30))

from railopt.models import BlockWindow, LiveTrainStatus, TrainType
from traffic.block_sections import BlockSection, get_block_section_by_id
from traffic.passages import (
    BlockSectionPassage,
    load_pilot_block_passages,
)
from traffic.train_weights import TRAIN_TYPE_PRIORITY_WEIGHTS, get_train_type_weight
from traffic.window_finder import (
    BlockWindowConfig,
    UsableBlockWindow,
    _minutes_to_time,
    _time_to_minutes,
    find_block_section_windows,
    rank_candidate_windows,
)


@dataclass
class ReliabilityConfig:
    """Configuration for dynamic window reliability and buffer calculations."""
    default_clearance_minutes: int = 10
    interpolated_base_uncertainty: int = 5
    interpolated_time_span_penalty: float = 0.05
    days_ahead_uncertainty_per_day: float = 2.0
    max_uncertainty_minutes: int = 45
    mode: str = "CONSERVATIVE"               # "CONSERVATIVE" | "OPTIMISTIC"
    traffic_mode: str = "LIVE_ONLY"          # "LIVE_ONLY" | "LIVE_PLUS_SYNTHETIC"
    stale_status_threshold_hours: float = 2.0
    pre_buffer_minutes: int = 15
    post_buffer_minutes: int = 15
    step_minutes: int = 5
    min_headway_minutes: int = 5
    has_alternate_route: bool = True
    alternate_route_penalty_minutes: float = 22.0


@dataclass
class ReliableBlockWindow(UsableBlockWindow):
    """
    Enriched block window with explicit confidence breakdown, bounding trains,
    and decision-support confirmation semantics.
    """
    confidence: str = "MEDIUM"                # "HIGH" | "MEDIUM" | "LOW"
    confidence_breakdown: Dict[str, Any] = field(default_factory=dict)
    bounding_trains: Dict[str, Optional[Dict[str, str]]] = field(default_factory=dict)
    proposal: bool = True
    status_note: str = "requires controller confirmation"
    estimated_cascade: float = 0.0
    weighted_delay_minutes: float = 0.0
    mode: str = "CONSERVATIVE"
    stale_status: bool = False
    status_age_hours: float = 0.0

    def to_block_window(self, corridor_id: str = "", section_id: str = "") -> BlockWindow:
        """Convert to standard BlockWindow, preserving ML and solver properties."""
        bw = super().to_block_window(corridor_id=corridor_id, section_id=section_id)
        bw.ml_cumulative_delay_minutes = self.weighted_delay_minutes
        return bw


def compute_passage_margin(
    p: BlockSectionPassage,
    target_date: date,
    config: Optional[ReliabilityConfig] = None,
) -> int:
    """
    Calculate dynamic per-passage margin: clearance + uncertainty.
    Uncertainty grows with:
    - Interpolated status (+5 base + transit span)
    - Days ahead (+2 min per day)
    - Historical delay spread / live uncertainty
    """
    cfg = config or ReliabilityConfig()
    clearance = cfg.default_clearance_minutes
    uncertainty = 0

    # 1. Interpolated passages get more margin
    if getattr(p, "interpolated", False):
        uncertainty += cfg.interpolated_base_uncertainty
        transit_m = (p.exit_datetime - p.enter_datetime).total_seconds() / 60.0
        if transit_m > 5.0:
            uncertainty += int((transit_m - 5.0) * cfg.interpolated_time_span_penalty)

    # 2. Distance in time to execution date
    try:
        today = date.today()
        days_ahead = max(0, (target_date - today).days)
    except Exception:
        days_ahead = 0
    uncertainty += int(days_ahead * cfg.days_ahead_uncertainty_per_day)

    # 3. Delay spread if available on passage
    delay_spread = getattr(p, "delay_spread_minutes", 0.0) or getattr(p, "historical_delay_spread_min", 0.0)
    if delay_spread > 0:
        uncertainty += int(delay_spread * 0.5)

    total_uncertainty = min(cfg.max_uncertainty_minutes, uncertainty)
    return clearance + total_uncertainty


def apply_live_train_statuses(
    passages: List[BlockSectionPassage],
    target_date: date,
    live_statuses: Optional[Dict[str, LiveTrainStatus]] = None,
    config: Optional[ReliabilityConfig] = None,
) -> Tuple[List[BlockSectionPassage], bool, float]:
    """
    Applies real-time live train statuses for dates within 24h:
    - Cancelled trains are removed (opens free windows).
    - Diverted / Rescheduled trains update occupancy.
    - Flags stale status if older than threshold.
    Returns (adjusted_passages, is_stale, status_age_hours).
    """
    cfg = config or ReliabilityConfig()
    if not live_statuses:
        return list(passages), False, 0.0

    today = date.today()
    if abs((target_date - today).days) > 1:
        # Not within 24h horizon; live status is not applicable
        return list(passages), False, 0.0

    # Check staleness
    now = datetime.now()
    oldest_updated = None
    for st in live_statuses.values():
        lu = getattr(st, "last_updated", None)
        if lu is not None:
            if oldest_updated is None or lu < oldest_updated:
                oldest_updated = lu

    status_age_hours = 0.0
    is_stale = False
    if oldest_updated:
        if oldest_updated.tzinfo:
            now_aware = datetime.now(oldest_updated.tzinfo)
            status_age_hours = max(0.0, (now_aware - oldest_updated).total_seconds() / 3600.0)
        else:
            status_age_hours = max(0.0, (now - oldest_updated).total_seconds() / 3600.0)
        is_stale = status_age_hours > cfg.stale_status_threshold_hours

    adjusted: List[BlockSectionPassage] = []
    for p in passages:
        st = live_statuses.get(p.train_no) or live_statuses.get(p.train_number)
        if not st:
            adjusted.append(p)
            continue

        raw_status = (getattr(st, "status", "") or "").upper()

        # 1. Cancelled train -> does not run, omit passage
        if "CANCEL" in raw_status:
            continue

        # 2. Diverted train -> if diverted away from this section, omit
        if "DIVERT" in raw_status:
            if "AWAY" in raw_status or "ALT" in raw_status or "OFF_ROUTE" in raw_status:
                continue

        # 3. Rescheduled or delayed train -> shift passage occupancy
        delay_min = float(getattr(st, "delay_minutes", 0.0) or 0.0)
        if delay_min != 0.0 or "RESCHEDULE" in raw_status:
            # Shift by delay_min
            new_enter_dt = p.enter_datetime + timedelta(minutes=delay_min)
            new_exit_dt = p.exit_datetime + timedelta(minutes=delay_min)

            # Re-clone passage with updated times
            p_copy = copy.copy(p)
            p_copy.enter_datetime = new_enter_dt
            p_copy.exit_datetime = new_exit_dt
            p_copy.enter_time = new_enter_dt.time()
            p_copy.exit_time = new_exit_dt.time()
            adjusted.append(p_copy)
        else:
            adjusted.append(p)

    return adjusted, is_stale, round(status_age_hours, 1)


def filter_passages_by_track(
    passages: List[BlockSectionPassage],
    block_section: BlockSection,
    task_line: str = "DN",
    mode: str = "CONSERVATIVE",
) -> List[BlockSectionPassage]:
    """
    Filters passages based on line and track configuration:
    - CONSERVATIVE mode: a passage blocks all tracks in its direction unless task_line is
      specific (e.g. UP_SLOW vs UP_FAST) and the passage's track assignment is known and distinct.
    - OPTIMISTIC mode: if task_line is specific and the passage is on another track (or unknown),
      it does not block.
    """
    req_line = task_line.upper()
    req_dir = "UP" if "UP" in req_line else ("DN" if "DN" in req_line else "BOTH")

    relevant: List[BlockSectionPassage] = []
    for p in passages:
        if p.block_section_id != block_section.id:
            continue

        # Direction match
        p_dir = getattr(p, "direction", p.line).upper()
        if req_dir != "BOTH" and p_dir != req_dir and block_section.tracks > 1:
            continue

        # Sub-track match in multi-track territory
        p_track = getattr(p, "assigned_track", None)
        p_track_known = getattr(p, "track_assignment_known", False)

        if mode == "CONSERVATIVE":
            if req_line in ("UP", "DN", "BOTH"):
                relevant.append(p)
            elif p_track_known and p_track and p_track != req_line:
                # Track is known and different: does not block
                continue
            else:
                relevant.append(p)
        else:  # OPTIMISTIC
            if req_line in ("UP", "DN", "BOTH"):
                relevant.append(p)
            elif p_track and p_track != req_line:
                continue
            elif not p_track_known and block_section.tracks >= 2:
                # Assume train can be held or routed on the parallel line
                continue
            else:
                relevant.append(p)

    return relevant


def extract_bounding_trains(
    passages: List[BlockSectionPassage],
    window_start: time,
    window_end: time,
) -> Dict[str, Optional[Dict[str, str]]]:
    """
    Finds the last train clearing the block before window_start and
    the first train entering the block after window_end.
    """
    win_start_m = _time_to_minutes(window_start)
    win_end_m = _time_to_minutes(window_end)
    if win_end_m < win_start_m:
        win_end_m += 1440

    prev_train: Optional[BlockSectionPassage] = None
    prev_exit_m = -1

    next_train: Optional[BlockSectionPassage] = None
    next_enter_m = 999999

    for p in passages:
        s_m = _time_to_minutes(p.enter_time)
        e_m = _time_to_minutes(p.exit_time)
        if e_m < s_m:
            e_m += 1440

        # Preceding train: exit before window start
        if e_m <= win_start_m:
            if e_m > prev_exit_m:
                prev_exit_m = e_m
                prev_train = p

        # Following train: enter after window end
        if s_m >= win_end_m:
            if s_m < next_enter_m:
                next_enter_m = s_m
                next_train = p

    res: Dict[str, Optional[Dict[str, str]]] = {"prev": None, "next": None}
    if prev_train:
        res["prev"] = {
            "train_number": prev_train.train_no,
            "train_name": prev_train.train_name,
            "time": prev_train.exit_time.strftime("%H:%M"),
            "provenance": getattr(prev_train, "provenance", "hand_written"),
        }
    if next_train:
        res["next"] = {
            "train_number": next_train.train_no,
            "train_name": next_train.train_name,
            "time": next_train.enter_time.strftime("%H:%M"),
            "provenance": getattr(next_train, "provenance", "hand_written"),
        }
    return res


def compute_confidence_score(
    passages: List[BlockSectionPassage],
    target_date: date,
    traffic_mode: str = "LIVE_ONLY",
    snapshot_age_days: int = 0,
) -> Tuple[str, Dict[str, Any]]:
    """
    Computes HIGH / MEDIUM / LOW confidence and returns full audit breakdown.
    Strict Invariant:
    Synthetic traffic in the calculation means confidence can NEVER be HIGH.
    """
    total = len(passages)
    if total == 0:
        days_ahead = max(0, (target_date - date.today()).days)
        breakdown = {
            "share_live": 0.0,
            "share_interpolated": 0.0,
            "share_synthetic": 0.0,
            "snapshot_age_days": snapshot_age_days,
            "goods_unverified": False,
            "days_ahead": days_ahead,
        }
        return "LOW", breakdown

    live_count = sum(1 for p in passages if getattr(p, "provenance", "") == "live")
    interp_count = sum(1 for p in passages if getattr(p, "interpolated", False))
    synth_count = sum(
        1 for p in passages
        if getattr(p, "provenance", "") == "synthetic"
        or getattr(p, "source", "") in ("synthetic_fill", "synthetic_goods")
    )
    goods_unverified = any(
        getattr(p, "train_type", TrainType.MAIL_EXPRESS).value == "FREIGHT"
        or getattr(p, "provenance", "") == "synthetic"
        for p in passages
    )

    days_ahead = max(0, (target_date - date.today()).days)
    share_live = round(live_count / total, 3)
    share_interp = round(interp_count / total, 3)
    share_synth = round(synth_count / total, 3)

    breakdown = {
        "share_live": share_live,
        "share_interpolated": share_interp,
        "share_synthetic": share_synth,
        "snapshot_age_days": snapshot_age_days,
        "goods_unverified": goods_unverified,
        "days_ahead": days_ahead,
    }

    # RULE: Synthetic traffic in the calculation means NEVER HIGH
    has_synthetic = (share_synth > 0.0) or (traffic_mode == "LIVE_PLUS_SYNTHETIC")
    if has_synthetic:
        if share_live >= 0.4 and days_ahead <= 5:
            return "MEDIUM", breakdown
        return "LOW", breakdown

    # Without synthetic traffic:
    if share_live >= 0.7 and share_interp <= 0.3 and days_ahead <= 2 and not goods_unverified:
        return "HIGH", breakdown
    elif share_live >= 0.3 or days_ahead <= 7:
        return "MEDIUM", breakdown
    else:
        return "LOW", breakdown


def find_reliable_block_windows(
    block_section: BlockSection,
    target_date: date,
    task_duration_minutes: int = 120,
    line: Optional[str] = None,
    requires_both_lines: bool = False,
    passages: Optional[List[BlockSectionPassage]] = None,
    live_statuses: Optional[Dict[str, LiveTrainStatus]] = None,
    config: Optional[ReliabilityConfig] = None,
    snapshot_dir=None,
) -> List[ReliableBlockWindow]:
    """
    Discovers free maintenance windows using the reliability layer.
    Wraps Phase 1 find_block_section_windows with dynamic margins, track modeling,
    live status adjustment, confidence scoring, and bounding trains.
    """
    cfg = config or ReliabilityConfig()
    req_line = line or block_section.line

    # 1. Base passage loading
    if passages is None:
        passages = load_pilot_block_passages(
            pilot_section_id=block_section.pilot_section_id,
            target_date=target_date,
            snapshot_dir=snapshot_dir,
        )

    # 2. Live status adjustment (cancelled, diverted, delayed)
    active_passages, is_stale, status_age = apply_live_train_statuses(
        passages=passages,
        target_date=target_date,
        live_statuses=live_statuses,
        config=cfg,
    )

    # 3. Track filtering
    active_passages = filter_passages_by_track(
        passages=active_passages,
        block_section=block_section,
        task_line=req_line,
        mode=cfg.mode,
    )

    # 4. Passage margin function seam
    margin_fn = lambda p: compute_passage_margin(p, target_date, cfg)

    # 5. Core finder call
    finder_cfg = BlockWindowConfig(
        clearance_buffer_minutes=cfg.default_clearance_minutes,
        pre_buffer_minutes=cfg.pre_buffer_minutes,
        post_buffer_minutes=cfg.post_buffer_minutes,
        step_minutes=cfg.step_minutes,
        traffic_mode=cfg.traffic_mode,
    )

    raw_windows = find_block_section_windows(
        block_section=block_section,
        target_date=target_date,
        task_duration_minutes=task_duration_minutes,
        line=req_line,
        requires_both_lines=requires_both_lines,
        passages=active_passages,
        config=finder_cfg,
        snapshot_dir=snapshot_dir,
        passage_margin_fn=margin_fn,
    )

    # 6. Confidence & Bounding train enrichment
    confidence, conf_breakdown = compute_confidence_score(
        passages=active_passages,
        target_date=target_date,
        traffic_mode=cfg.traffic_mode,
    )

    reliable_windows: List[ReliableBlockWindow] = []
    for w in raw_windows:
        bounding = extract_bounding_trains(
            passages=active_passages,
            window_start=w.recommended_start,
            window_end=w.recommended_end,
        )

        rw = ReliableBlockWindow(
            window_id=w.window_id,
            block_section_id=w.block_section_id,
            line=w.line,
            date=w.date,
            gap_start_min=w.gap_start_min,
            gap_end_min=w.gap_end_min,
            earliest_start=w.earliest_start,
            latest_start=w.latest_start,
            recommended_start=w.recommended_start,
            recommended_end=w.recommended_end,
            duration_hours=w.duration_hours,
            task_duration_minutes=w.task_duration_minutes,
            pre_buffer_minutes=w.pre_buffer_minutes,
            post_buffer_minutes=w.post_buffer_minutes,
            margin_before_min=w.margin_before_min,
            margin_after_min=w.margin_after_min,
            comfort_label=w.comfort_label,
            freight_unverified=w.freight_unverified,
            known_trains=w.known_trains,
            estimated_total_trains=w.estimated_total_trains,
            coverage=w.coverage,
            traffic_mode=cfg.traffic_mode,
            source=w.source,
            is_free_gap=w.is_free_gap,
            trains_held=w.trains_held,
            total_delay_minutes=w.total_delay_minutes,
            score=w.score,
            score_breakdown=w.score_breakdown,
            reason_codes=w.reason_codes,
            confidence=confidence,
            confidence_breakdown=conf_breakdown,
            bounding_trains=bounding,
            proposal=True,
            status_note="requires controller confirmation",
            estimated_cascade=0.0,
            weighted_delay_minutes=0.0,
            mode=cfg.mode,
            stale_status=is_stale,
            status_age_hours=status_age,
        )
        reliable_windows.append(rw)

    return reliable_windows


def rank_reliable_candidate_windows(
    block_section: BlockSection,
    target_date: date,
    task_duration_minutes: int = 120,
    line: Optional[str] = None,
    requires_both_lines: bool = False,
    preferred_period: str = "ANY",
    requires_power_block: bool = False,
    passages: Optional[List[BlockSectionPassage]] = None,
    live_statuses: Optional[Dict[str, LiveTrainStatus]] = None,
    config: Optional[ReliabilityConfig] = None,
    top_k: int = 5,
    snapshot_dir=None,
) -> List[ReliableBlockWindow]:
    """
    Ranks top maintenance window candidates using the reliability wrapper.
    Computes train-type weighted delays and exposes estimated_cascade.
    """
    cfg = config or ReliabilityConfig()
    req_line = line or block_section.line

    # 1. Base passage loading
    if passages is None:
        passages = load_pilot_block_passages(
            pilot_section_id=block_section.pilot_section_id,
            target_date=target_date,
            snapshot_dir=snapshot_dir,
        )

    # 2. Live status adjustment
    active_passages, is_stale, status_age = apply_live_train_statuses(
        passages=passages,
        target_date=target_date,
        live_statuses=live_statuses,
        config=cfg,
    )

    # 3. Track filtering
    active_passages = filter_passages_by_track(
        passages=active_passages,
        block_section=block_section,
        task_line=req_line,
        mode=cfg.mode,
    )

    # 4. Passage margin function
    margin_fn = lambda p: compute_passage_margin(p, target_date, cfg)

    # 5. Finder configuration
    finder_cfg = BlockWindowConfig(
        clearance_buffer_minutes=cfg.default_clearance_minutes,
        pre_buffer_minutes=cfg.pre_buffer_minutes,
        post_buffer_minutes=cfg.post_buffer_minutes,
        step_minutes=cfg.step_minutes,
        min_headway_minutes=cfg.min_headway_minutes,
        traffic_mode=cfg.traffic_mode,
    )

    raw_candidates = rank_candidate_windows(
        block_section=block_section,
        target_date=target_date,
        task_duration_minutes=task_duration_minutes,
        line=req_line,
        requires_both_lines=requires_both_lines,
        preferred_period=preferred_period,
        requires_power_block=requires_power_block,
        has_alternate_route=cfg.has_alternate_route,
        alternate_route_penalty_minutes=cfg.alternate_route_penalty_minutes,
        passages=active_passages,
        config=finder_cfg,
        top_k=top_k * 2,
        snapshot_dir=snapshot_dir,
        passage_margin_fn=margin_fn,
    )

    # 6. Confidence & Bounding train enrichment
    confidence, conf_breakdown = compute_confidence_score(
        passages=active_passages,
        target_date=target_date,
        traffic_mode=cfg.traffic_mode,
    )

    reliable_candidates: List[ReliableBlockWindow] = []
    active_sorted = sorted(active_passages, key=lambda p: _time_to_minutes(p.enter_time))

    for w in raw_candidates:
        bounding = extract_bounding_trains(
            passages=active_passages,
            window_start=w.recommended_start,
            window_end=w.recommended_end,
        )

        # Compute weighted delay and estimated cascade
        primary_weighted = 0.0
        cascade_weighted = 0.0

        if not w.is_free_gap:
            win_start_m = _time_to_minutes(w.recommended_start) - cfg.pre_buffer_minutes
            win_end_m = _time_to_minutes(w.recommended_end) + cfg.post_buffer_minutes

            held_with_delay = []
            for p in active_passages:
                s_m = _time_to_minutes(p.enter_time)
                e_m = _time_to_minutes(p.exit_time)
                if e_m < s_m:
                    e_m += 1440
                p_clr = margin_fn(p)

                if (s_m - p_clr) < win_end_m and win_start_m < (e_m + p_clr):
                    hold = max(0.0, (win_end_m + p_clr) - s_m)
                    if cfg.has_alternate_route:
                        hold = min(hold, cfg.alternate_route_penalty_minutes)
                    w_train = get_train_type_weight(p.train_type)
                    primary_weighted += hold * w_train
                    held_with_delay.append((p, hold))

            for ht, ht_delay in held_with_delay:
                ht_new_enter = _time_to_minutes(ht.enter_time) + ht_delay
                for other in active_sorted:
                    if other.train_no == ht.train_no:
                        continue
                    o_enter = _time_to_minutes(other.enter_time)
                    if o_enter > _time_to_minutes(ht.enter_time) and o_enter < ht_new_enter + cfg.min_headway_minutes:
                        push = max(0.0, (ht_new_enter + cfg.min_headway_minutes) - o_enter)
                        w_other = get_train_type_weight(other.train_type)
                        cascade_weighted += push * w_other

        total_weighted = round(primary_weighted + cascade_weighted, 1)

        rw = ReliableBlockWindow(
            window_id=w.window_id,
            block_section_id=w.block_section_id,
            line=w.line,
            date=w.date,
            gap_start_min=w.gap_start_min,
            gap_end_min=w.gap_end_min,
            earliest_start=w.earliest_start,
            latest_start=w.latest_start,
            recommended_start=w.recommended_start,
            recommended_end=w.recommended_end,
            duration_hours=w.duration_hours,
            task_duration_minutes=w.task_duration_minutes,
            pre_buffer_minutes=w.pre_buffer_minutes,
            post_buffer_minutes=w.post_buffer_minutes,
            margin_before_min=w.margin_before_min,
            margin_after_min=w.margin_after_min,
            comfort_label=w.comfort_label,
            freight_unverified=w.freight_unverified,
            known_trains=w.known_trains,
            estimated_total_trains=w.estimated_total_trains,
            coverage=w.coverage,
            traffic_mode=cfg.traffic_mode,
            source=w.source,
            is_free_gap=w.is_free_gap,
            trains_held=w.trains_held,
            total_delay_minutes=w.total_delay_minutes,
            score=w.score,
            score_breakdown=w.score_breakdown,
            reason_codes=w.reason_codes,
            confidence=confidence,
            confidence_breakdown=conf_breakdown,
            bounding_trains=bounding,
            proposal=True,
            status_note="requires controller confirmation",
            estimated_cascade=round(cascade_weighted, 1),
            weighted_delay_minutes=total_weighted,
            mode=cfg.mode,
            stale_status=is_stale,
            status_age_hours=status_age,
        )
        reliable_candidates.append(rw)

    # Rank and trim to top_k
    reliable_candidates.sort(
        key=lambda w: (
            0 if w.is_free_gap else 1,
            w.trains_held,
            w.weighted_delay_minutes,
            -w.score,
        )
    )
    return reliable_candidates[:top_k]
