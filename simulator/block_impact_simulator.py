"""
RailOpt — Block Impact Simulator.

Evaluates how proposed maintenance blocks affect train operations.
Uses real/derived train passages, hold/reroute rules, and headway cascade propagation
for pilot sections with calendar dates.
Falls back to train slot time-of-day lookup table for non-pilot sections (clearly flagged).
"""
from __future__ import annotations

from datetime import date as date_cls, datetime, time, timedelta
from typing import Any, Dict, List, Optional

from railopt.models import (
    BlockPlan,
    Corridor,
    ScheduledBlock,
    SimulationReport,
    TrainSlot,
    TrainType,
)
from railopt.sim_entities import Resource, ResourceType
from traffic.cascade import propagate_cascade
from traffic.delay_model import calculate_block_delays
from traffic.fill import get_all_passages_for_section
from traffic.section_map import get_pilot_section_config, is_pilot_section


# Delay lookup by train type (minutes) — base fallback delay for a 3h block
_DELAY_BY_TRAIN_TYPE: dict[TrainType, float] = {
    TrainType.RAJDHANI: 25.0,
    TrainType.SHATABDI: 20.0,
    TrainType.DURONTO: 22.0,
    TrainType.VANDE_BHARAT: 18.0,
    TrainType.GARIB_RATH: 20.0,
    TrainType.SUPERFAST: 15.0,
    TrainType.MAIL_EXPRESS: 12.0,
    TrainType.PASSENGER: 8.0,
    TrainType.SUBURBAN: 5.0,
    TrainType.FREIGHT: 10.0,
    TrainType.MILITARY: 15.0,
}


def _times_overlap(
    a_start: time, a_end: time, b_start: time, b_end: time
) -> bool:
    """Check if two time ranges overlap, handling midnight crossing."""
    ref = date_cls(2000, 1, 1)

    def _to_range(s: time, e: time):
        s_dt = datetime.combine(ref, s)
        e_dt = datetime.combine(ref, e)
        if e_dt <= s_dt:
            e_dt = e_dt.replace(day=2)  # crosses midnight
        return s_dt, e_dt

    a_s, a_e = _to_range(a_start, a_end)
    b_s, b_e = _to_range(b_start, b_end)
    return a_s < b_e and b_s < a_e


class BlockImpactSimulator:
    """Evaluates how proposed maintenance blocks affect train operations."""

    def __init__(
        self, corridors: list[Corridor], train_slots: list[TrainSlot]
    ):
        self.corridors = corridors
        self.train_slots = train_slots
        self.resources: dict[str, Resource] = {}
        self._init_resources()

    def _init_resources(self):
        """Initialize simulation resources based on corridor sections."""
        for corridor in self.corridors:
            for section in corridor.sections:
                res = Resource(
                    resource_id=section.section_id,
                    resource_type=ResourceType.BLOCK,
                    length_m=section.length_km * 1000,
                    max_speed_kmh=section.max_speed_kmh,
                )
                self.resources[section.section_id] = res

    def simulate_plan(self, plan: BlockPlan) -> SimulationReport:
        """Simulate the entire block plan and generate a report."""
        report = SimulationReport(plan_id=plan.plan_id)
        total_delay = 0.0
        affected = 0
        max_delay = 0.0
        corridor_delay_map: dict[str, float] = {}

        for block in plan.scheduled_blocks:
            res = self.simulate_single_block(block)
            block_affected = res["trains_affected"]
            block_delay = res["delay_minutes"]

            affected += block_affected
            total_delay += block_delay
            max_delay = max(max_delay, block_delay)

            c_id = block.corridor_id or "UNKNOWN"
            corridor_delay_map[c_id] = corridor_delay_map.get(c_id, 0.0) + block_delay

        simulated_train_count = max(len(self.train_slots), affected)
        report.total_trains_simulated = simulated_train_count
        report.trains_affected = affected
        report.trains_delayed = affected
        report.cumulative_delay_minutes = round(total_delay, 1)
        report.average_delay_minutes = (
            round(total_delay / affected, 1) if affected > 0 else 0.0
        )
        report.max_delay_minutes = round(max_delay, 1)

        # Estimate punctuality impact (trains delayed >= 15 min are considered unpunctual)
        if simulated_train_count > 0:
            unpunctual_pct = min(100.0, (affected / simulated_train_count) * 100.0 * 0.7)
            report.punctuality_after_pct = round(max(0.0, 100.0 - unpunctual_pct), 1)

        # Most affected corridors
        sorted_corridors = sorted(
            corridor_delay_map.items(), key=lambda kv: kv[1], reverse=True
        )
        report.corridors_most_affected = [c[0] for c in sorted_corridors[:3] if c[1] > 0]

        if total_delay > 120.0:
            report.recommendations.append(
                "High cumulative delay detected. Consider shifting peak day blocks into night maintenance windows."
            )
        if any(b.trains_affected > 5 for b in plan.scheduled_blocks):
            report.recommendations.append(
                "Several blocks conflict with high-density train clusters. Utilize alternate detour routes where available."
            )

        return report

    def simulate_single_block(self, block: ScheduledBlock) -> dict[str, Any]:
        """
        Simulate a single block's impact on train operations.
        Uses real timetable passages, hold & reroute rules, and cascade propagation for pilot sections.
        Falls back to fixed delay table when no passages exist.
        """
        # 1. Pilot section evaluation with date-aware passages and cascade
        if is_pilot_section(block.section_id):
            sec_cfg = get_pilot_section_config(block.section_id)
            if sec_cfg:
                target_d = block.date or date_cls.today()
                passages, _ = get_all_passages_for_section(sec_cfg, target_d)

                primary_res = calculate_block_delays(
                    sec_cfg,
                    target_d,
                    block.start_time,
                    block.end_time,
                    passages,
                    block_id=block.block_id,
                )
                cas_res = propagate_cascade(primary_res, passages)

                return {
                    "block_id": block.block_id,
                    "trains_affected": cas_res.trains_hit,
                    "delay_minutes": round(cas_res.cascade_total_delay, 1),
                    "primary_delay_minutes": primary_res.total_delay_minutes,
                    "cascade_delay_minutes": round(
                        cas_res.cascade_total_delay - primary_res.total_delay_minutes, 1
                    ),
                    "rerouted_trains": primary_res.rerouted_trains,
                    "held_trains": primary_res.held_trains,
                    "max_cascade_depth": cas_res.max_depth,
                    "source": "passages_cascade",
                }

        # 2. Flagged fallback for non-pilot or unconfigured sections
        affected = 0
        delay = 0.0

        for slot in self.train_slots:
            if slot.section_id != block.section_id:
                continue

            # Check actual time overlap
            if _times_overlap(
                slot.arrival_time, slot.departure_time,
                block.start_time, block.end_time,
            ):
                affected += 1
                base_delay = _DELAY_BY_TRAIN_TYPE.get(slot.train_type, 15.0)
                # Scale delay by block duration (base is calibrated for 3h)
                delay += base_delay * (block.duration_hours / 3.0)

        return {
            "block_id": block.block_id,
            "trains_affected": affected,
            "delay_minutes": round(delay, 1),
            "source": "fallback_lookup",
        }

    def compare_plans(
        self, plan_a: BlockPlan, plan_b: BlockPlan
    ) -> dict[str, Any]:
        """Compare two plans by running simulations on both."""
        sim_a = self.simulate_plan(plan_a)
        sim_b = self.simulate_plan(plan_b)
        return {
            "plan_a_metrics": sim_a.model_dump(),
            "plan_b_metrics": sim_b.model_dump(),
            "delta_delay": sim_b.cumulative_delay_minutes - sim_a.cumulative_delay_minutes,
            "recommendation": (
                "Plan A is better"
                if sim_a.cumulative_delay_minutes < sim_b.cumulative_delay_minutes
                else "Plan B is better"
            ),
        }
