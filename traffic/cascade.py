"""
traffic/cascade.py

Propagates primary train delays through downstream stops and following trains.
1. Propagates delay along later stops of the same train (primary delay persists downstream).
2. Propagates headway spacing delays to subsequent following trains on the section.
   If train A departs at T_A' and train B was scheduled to enter/exit at T_B < T_A' + min_headway,
   train B suffers knock-on delay = (T_A' + min_headway) - T_B.
   This cascades sequentially up to max_cascade_depth.

ASSUMPTIONS & ARCHITECTURAL LIMITATIONS:
- Rake Linkage: No physical rake turnaround/linkage data exists in Indian Railways open APIs.
  Therefore, rake-chain propagation (where delay to an incoming train delays its subsequent return
  service on a different train number) is deliberately omitted and documented here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import time
from typing import Dict, List, Optional, Tuple

from traffic.delay_model import DelayCalculationResult
from traffic.passages import TrainPassage


@dataclass
class CascadeConfig:
    """Configuration for delay cascade propagation."""
    min_headway_minutes: float = 5.0  # Minimum safety headway between successive train dispatches
    max_cascade_depth: int = 5        # Maximum sequential chain of following trains to propagate
    stop_propagation_factor: float = 0.85  # Fraction of delay carried downstream to later stops (cushion absorption)


@dataclass
class CascadeLink:
    """Record of a knock-on delay event between a leading train and a following train."""
    trigger_train_no: str
    impacted_train_no: str
    depth: int
    scheduled_time: str
    delayed_dispatch_time: str
    knock_on_delay_minutes: float
    reason: str


@dataclass
class CascadeResult:
    """Complete impact of a maintenance block including primary and secondary cascade delays."""
    primary_trains_affected: int
    primary_delay_minutes: float
    cascade_total_delay: float
    trains_hit: int
    max_depth: int
    train_delay_breakdown: Dict[str, float]
    cascade_chains: List[CascadeLink] = field(default_factory=list)


def _time_to_minutes(t: time) -> int:
    return t.hour * 60 + t.minute


def _minutes_to_time(m: int) -> time:
    m = int(m) % 1440
    return time(m // 60, m % 60)


def propagate_cascade(
    primary_result: DelayCalculationResult,
    all_passages: List[TrainPassage],
    config: Optional[CascadeConfig] = None,
) -> CascadeResult:
    """
    Propagate primary delays across following trains and downstream stops.
    """
    cfg = config or CascadeConfig()

    delays: Dict[str, float] = dict(primary_result.per_train_delays)
    chains: List[CascadeLink] = []
    max_depth_reached = 0

    if not delays:
        return CascadeResult(
            primary_trains_affected=0,
            primary_delay_minutes=0.0,
            cascade_total_delay=0.0,
            trains_hit=0,
            max_depth=0,
            train_delay_breakdown={},
            cascade_chains=[],
        )

    # Downstream stops cascade:
    # A delayed train carries its delay downstream.
    # In Indian Railways, timetable buffer can absorb ~15% of delay; the remainder persists downstream.
    downstream_stop_delay = sum(
        d * cfg.stop_propagation_factor for d in primary_result.per_train_delays.values()
    )

    # Sort all passages chronologically by entry time
    sorted_passages = sorted(all_passages, key=lambda p: _time_to_minutes(p.enter_time))
    passage_by_train = {p.train_no: p for p in sorted_passages}

    # Queue of currently delayed trains that could impact subsequent trains
    active_delayed = [
        (t_no, d, 0) for t_no, d in primary_result.per_train_delays.items()
    ]

    visited_cascade: set[str] = set(primary_result.per_train_delays.keys())

    while active_delayed:
        lead_tno, lead_delay, depth = active_delayed.pop(0)
        if depth >= cfg.max_cascade_depth:
            continue

        lead_p = passage_by_train.get(lead_tno)
        if not lead_p:
            continue

        lead_exit_min = _time_to_minutes(lead_p.exit_time) + int(lead_delay)
        min_cleared_entry = lead_exit_min + int(cfg.min_headway_minutes)

        # Look for subsequent trains on the same section whose entry is blocked
        for follow_p in sorted_passages:
            if follow_p.train_no in visited_cascade:
                continue
            # Directional constraint: headway contention occurs in the same direction or on single line
            if follow_p.direction != lead_p.direction:
                continue

            follow_enter_min = _time_to_minutes(follow_p.enter_time)
            # If follow train enters after lead train was scheduled, but before lead train cleared
            if _time_to_minutes(lead_p.enter_time) < follow_enter_min < min_cleared_entry:
                knock_on = round(min_cleared_entry - follow_enter_min, 1)
                if knock_on >= 1.0:
                    delays[follow_p.train_no] = knock_on
                    visited_cascade.add(follow_p.train_no)
                    current_depth = depth + 1
                    max_depth_reached = max(max_depth_reached, current_depth)

                    chains.append(
                        CascadeLink(
                            trigger_train_no=lead_tno,
                            impacted_train_no=follow_p.train_no,
                            depth=current_depth,
                            scheduled_time=follow_p.enter_time.strftime("%H:%M"),
                            delayed_dispatch_time=_minutes_to_time(min_cleared_entry).strftime("%H:%M"),
                            knock_on_delay_minutes=knock_on,
                            reason=f"Headway conflict with delayed train {lead_tno} (delayed by {lead_delay:.1f}m)",
                        )
                    )

                    active_delayed.append((follow_p.train_no, knock_on, current_depth))

    total_delay = sum(delays.values()) + downstream_stop_delay

    return CascadeResult(
        primary_trains_affected=primary_result.trains_affected,
        primary_delay_minutes=primary_result.total_delay_minutes,
        cascade_total_delay=round(total_delay, 1),
        trains_hit=len(delays),
        max_depth=max_depth_reached,
        train_delay_breakdown=delays,
        cascade_chains=chains,
    )
