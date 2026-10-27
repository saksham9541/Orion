"""
RailOpt — Block Impact Simulator.

Evaluates how proposed maintenance blocks affect train operations
by checking time-overlap between blocks and train slots, with
delay estimates scaled by train type and block duration.
"""

from __future__ import annotations

from datetime import datetime, time, date as date_cls
from typing import Any, Dict, List

from railopt.models import (
    BlockPlan,
    Corridor,
    ScheduledBlock,
    SimulationReport,
    TrainSlot,
    TrainType,
)
from railopt.sim_entities import Resource, ResourceType


# Delay lookup by train type (minutes) — base delay for a 3h block
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

        for block in plan.scheduled_blocks:
            res = self.simulate_single_block(block)
            affected += res["trains_affected"]
            total_delay += res["delay_minutes"]

        report.total_trains_simulated = len(self.train_slots)
        report.trains_affected = affected
        report.cumulative_delay_minutes = total_delay
        report.average_delay_minutes = total_delay / affected if affected > 0 else 0.0
        return report

    def simulate_single_block(self, block: ScheduledBlock) -> dict[str, Any]:
        """Simulate a single block's impact on train slots.

        Only counts trains whose time range actually overlaps the block's
        time range on the same section. Delay is scaled by train type
        and block duration.
        """
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


if __name__ == "__main__":
    print("BlockImpactSimulator loaded.")
