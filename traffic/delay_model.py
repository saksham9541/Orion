"""
traffic/delay_model.py

Transparent delay calculation model for maintenance blocks on railway sections.
For each train passage overlapping a proposed block window:
1. Computes expected passage time = scheduled + current live delay (from stored LiveTrainStatus, decaying with horizon).
2. Applies the hold rule: delayed until the block clears plus dispatch headway.
3. Applies the alternate route rule: if an alternate corridor is configured and hold delay exceeds the detour penalty,
   the train is rerouted with that penalty.
4. Returns per-train delays, trains affected, and total primary delay.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, Optional, Tuple

from railopt.models import LiveTrainStatus, TrainType
from traffic.passages import TrainPassage
from traffic.section_map import PilotSectionConfig, get_pilot_section_config


@dataclass
class DelayModelConfig:
    """Configuration for transparent block delay calculation."""
    headway_buffer_minutes: float = 5.0            # Min headway spacing between dispatched held trains
    live_delay_decay_horizon_hours: float = 6.0    # Horizon after which live delay decays to zero
    default_reroute_penalty_minutes: float = 30.0  # Fallback detour penalty if not specified on section


@dataclass
class AffectedTrainDetail:
    """Detailed delay calculation for a single affected train."""
    train_no: str
    train_name: str
    train_type: TrainType
    scheduled_enter: str
    scheduled_exit: str
    effective_enter: str
    actual_enter: str
    actual_exit: str
    delay_minutes: float
    status: str  # "HELD" | "REROUTED" | "CLEAR"
    reason: str


@dataclass
class DelayCalculationResult:
    """Summary of primary traffic delays incurred by a maintenance block."""
    block_id: str
    section_id: str
    target_date: str
    trains_affected: int
    total_delay_minutes: float
    per_train_delays: Dict[str, float]
    rerouted_trains: List[str]
    held_trains: List[str]
    train_details: List[AffectedTrainDetail] = field(default_factory=list)


def _time_to_minutes(t: time) -> int:
    return t.hour * 60 + t.minute


def _minutes_to_time(m: int) -> time:
    m = int(m) % 1440
    return time(m // 60, m % 60)


def compute_live_decay(
    target_date: date,
    enter_t: time,
    now: Optional[datetime] = None,
    horizon_hours: float = 6.0,
) -> float:
    """
    Compute delay decay factor [0.0, 1.0] based on temporal distance from now.
    If target passage is > horizon_hours in future, or in the past, decays toward 0.
    """
    now_dt = now or datetime.now()
    passage_dt = datetime.combine(target_date, enter_t)

    # If passage date crosses midnight
    delta_hours = (passage_dt - now_dt).total_seconds() / 3600.0

    if delta_hours < 0:
        return 0.0  # Train already passed
    if delta_hours > horizon_hours:
        return 0.0  # Too far in the future for current live snapshot to remain valid

    return max(0.0, 1.0 - (delta_hours / horizon_hours))


def calculate_block_delays(
    sec_cfg: PilotSectionConfig | str,
    target_date: date,
    block_start: time,
    block_end: time,
    passages: List[TrainPassage],
    live_statuses: Optional[Dict[str, LiveTrainStatus]] = None,
    config: Optional[DelayModelConfig] = None,
    block_id: str = "",
    now: Optional[datetime] = None,
) -> DelayCalculationResult:
    """
    Calculate transparent primary train delays caused by a block on sec_cfg.
    Never calls external APIs; consumes stored live_statuses if provided.
    """
    if isinstance(sec_cfg, str):
        resolved = get_pilot_section_config(sec_cfg)
        if not resolved:
            raise ValueError(f"Unknown pilot section: {sec_cfg}")
        sec_cfg = resolved

    cfg = config or DelayModelConfig()
    live_map = live_statuses or {}

    b_start_min = _time_to_minutes(block_start)
    b_end_min = _time_to_minutes(block_end)
    if b_end_min <= b_start_min:
        b_end_min += 1440  # Block crosses midnight

    # 1. Evaluate effective passage times (scheduled + decayed live delay)
    evaluated_passages: List[Tuple[TrainPassage, int, int, float]] = []
    for p in passages:
        s_min = _time_to_minutes(p.enter_time)
        e_min = _time_to_minutes(p.exit_time)
        if e_min < s_min:
            e_min += 1440

        live_delay = 0.0
        if p.train_no in live_map:
            raw_delay = live_map[p.train_no].delay_minutes
            decay = compute_live_decay(target_date, p.enter_time, now=now, horizon_hours=cfg.live_delay_decay_horizon_hours)
            live_delay = max(0.0, raw_delay * decay)

        eff_s = s_min + int(live_delay)
        eff_e = e_min + int(live_delay)
        evaluated_passages.append((p, eff_s, eff_e, live_delay))

    # 2. Identify overlapping passages that conflict with the block
    conflicting: List[Tuple[TrainPassage, int, int, float]] = []
    for item in evaluated_passages:
        p, eff_s, eff_e, live_delay = item
        # Overlap condition: train interval intersects block interval
        if max(eff_s, b_start_min) < min(eff_e, b_end_min):
            conflicting.append(item)

    # Sort conflicting trains by scheduled effective arrival time to determine dispatch queue order
    conflicting.sort(key=lambda x: x[1])

    rerouted_trains: List[str] = []
    held_trains: List[str] = []
    per_train_delays: Dict[str, float] = {}
    details: List[AffectedTrainDetail] = []
    total_delay = 0.0

    # Reroute penalty from section config
    reroute_penalty = (
        sec_cfg.alternate_route_penalty_minutes
        if sec_cfg.has_alternate_route
        else float("inf")
    )

    current_dispatch_min = b_end_min
    for idx, (p, eff_s, eff_e, live_delay) in enumerate(conflicting):
        transit_duration = eff_e - eff_s
        # Hold rule: Train waits until the block ends, plus headway spacing for queued trains
        hold_entry_min = current_dispatch_min + (idx * cfg.headway_buffer_minutes)
        hold_delay = max(0.0, hold_entry_min - eff_s)

        # Check if alternate route is available and more optimal than holding
        if sec_cfg.has_alternate_route and hold_delay > reroute_penalty:
            # Train is rerouted
            chosen_delay = reroute_penalty
            status = "REROUTED"
            reason = (
                f"Rerouted via alternate route (penalty {reroute_penalty:.1f}m < hold delay {hold_delay:.1f}m)"
            )
            rerouted_trains.append(p.train_no)
            act_enter = _minutes_to_time(eff_s)
            act_exit = _minutes_to_time(eff_e + int(reroute_penalty))
        else:
            # Train is held
            chosen_delay = hold_delay
            status = "HELD"
            reason = f"Held at section boundary until block clearance at {block_end.strftime('%H:%M')} + {idx * cfg.headway_buffer_minutes:.0f}m headway"
            held_trains.append(p.train_no)
            act_enter = _minutes_to_time(hold_entry_min)
            act_exit = _minutes_to_time(hold_entry_min + transit_duration)

        per_train_delays[p.train_no] = round(chosen_delay, 1)
        total_delay += chosen_delay

        details.append(
            AffectedTrainDetail(
                train_no=p.train_no,
                train_name=p.train_name,
                train_type=p.train_type,
                scheduled_enter=p.enter_time.strftime("%H:%M"),
                scheduled_exit=p.exit_time.strftime("%H:%M"),
                effective_enter=_minutes_to_time(eff_s).strftime("%H:%M"),
                actual_enter=act_enter.strftime("%H:%M"),
                actual_exit=act_exit.strftime("%H:%M"),
                delay_minutes=round(chosen_delay, 1),
                status=status,
                reason=reason,
            )
        )

    return DelayCalculationResult(
        block_id=block_id,
        section_id=sec_cfg.section_id,
        target_date=str(target_date),
        trains_affected=len(conflicting),
        total_delay_minutes=round(total_delay, 1),
        per_train_delays=per_train_delays,
        rerouted_trains=rerouted_trains,
        held_trains=held_trains,
        train_details=details,
    )
