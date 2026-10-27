"""
RailOpt — Context Engine.

Gathers contextual evidence for maintenance tasks by analyzing:
  1. Section Failure History — recurring failures, MTBF, trend direction
  2. Asset Lifecycle — age vs expected life, maintenance history
  3. Corridor Risk Profile — traffic density, strategic importance
  4. Seasonal/Environmental — monsoon, extreme heat, fog belt effects

Produces a context_risk_score (0-1) and evidence_summary list,
analogous to FinCrime's ContextEngine but for railway maintenance.
"""

from __future__ import annotations

import math
from collections import Counter
from datetime import date, timedelta
from typing import Optional

from railopt.models import (
    Corridor,
    DefectCategory,
    Department,
    MaintenanceTask,
    Section,
    Season,
    TrafficDensityClass,
    get_season,
    SAFETY_CRITICAL_DEFECTS,
    ALWAYS_EMERGENCY,
)
from railopt.risk_component import ContextEngineConfig, RiskAccumulator


# ── Asset expected lifespan (years) by asset type ──────────────────────────
ASSET_EXPECTED_LIFE = {
    "RAIL": 25, "SLEEPER": 30, "BALLAST": 15,
    "BRIDGE": 60, "LEVEL_CROSSING": 25, "TRACK_BED": 40,
    "FORMATION": 50, "TURNOUT": 15, "WELD_JOINT": 12,
    "SIGNAL_POST": 25, "RELAY": 20, "POINT_MACHINE": 15,
    "AXLE_COUNTER": 12, "TELECOM_CABLE": 15, "TRACK_CIRCUIT": 15,
    "INTERLOCKING": 20, "LED_SIGNAL": 10,
    "OHE_WIRE": 25, "INSULATOR": 20, "MAST": 40,
    "TRANSFORMER": 30, "CIRCUIT_BREAKER": 20,
    "PANTOGRAPH_ZONE": 15, "FEEDER": 25,
}

# ── Section with recurring failures threshold ──────────────────────────────
RECURRING_FAILURE_THRESHOLD = 3  # tasks in same section with same defect category


class ContextEngine:
    """
    Autonomously gathers contextual evidence for maintenance tasks.

    Returns a structured dict with risk contributions from 4 perspectives,
    a blended context_risk_score (0.0 – 1.0), and evidence_summary strings
    for LLM/report consumption.
    """

    def __init__(self, config: ContextEngineConfig | None = None) -> None:
        self._cfg = config or ContextEngineConfig()

    def analyze_task(
        self,
        task: MaintenanceTask,
        all_tasks: list[MaintenanceTask],
        section: Optional[Section],
        corridor: Optional[Corridor],
    ) -> dict:
        """Full contextual analysis for a single task."""
        history = self._section_failure_history(task, all_tasks)
        lifecycle = self._asset_lifecycle(task)
        corridor_risk = self._corridor_risk_profile(section, corridor)
        seasonal = self._seasonal_context(task)

        # Aggregate context risk score (capped at 1.0)
        context_risk = min(
            history["risk_contribution"]
            + lifecycle["risk_contribution"]
            + corridor_risk["risk_contribution"]
            + seasonal["risk_contribution"],
            1.0,
        )

        evidence = self._build_evidence_summary(
            history, lifecycle, corridor_risk, seasonal
        )

        return {
            "section_failure_history": history,
            "asset_lifecycle": lifecycle,
            "corridor_risk_profile": corridor_risk,
            "seasonal_context": seasonal,
            "evidence_summary": evidence,
            "context_risk_score": round(context_risk, 3),
        }

    def analyze_batch(
        self,
        tasks: list[MaintenanceTask],
        sections: dict[str, Section],
        corridors: list[Corridor],
    ) -> list[dict]:
        """Batch analysis — one context dict per task."""
        corridor_map = {c.corridor_id: c for c in corridors}
        results = []
        for task in tasks:
            section = sections.get(task.section_id)
            corridor = corridor_map.get(task.corridor_id)
            results.append(self.analyze_task(task, tasks, section, corridor))
        return results

    # ── 1. SECTION FAILURE HISTORY ──────────────────────────────────────────

    def _section_failure_history(
        self, task: MaintenanceTask, all_tasks: list[MaintenanceTask]
    ) -> dict:
        """Analyze failure patterns in the task's section."""
        cfg = self._cfg
        section_tasks = [
            t for t in all_tasks
            if t.section_id == task.section_id and t.task_id != task.task_id
        ]

        if not section_tasks:
            return {
                "total_failures": 0,
                "recurring_defect": False,
                "same_category_count": 0,
                "mean_days_between_failures": None,
                "trend": "INSUFFICIENT_DATA",
                "risk_contribution": cfg.base_no_history_risk,
            }

        # Count same-category failures
        same_cat = [t for t in section_tasks if t.defect_category == task.defect_category]
        recurring = len(same_cat) >= cfg.recurring_failure_threshold

        # Compute MTBF (mean time between failures) from reported dates
        dates = sorted([t.reported_date for t in section_tasks])
        if len(dates) >= 2:
            gaps = [(dates[i + 1] - dates[i]).days for i in range(len(dates) - 1)]
            mtbf = sum(gaps) / len(gaps)
        else:
            mtbf = None

        # Trend: are failures accelerating?
        trend = "STABLE"
        if mtbf is not None:
            recent_dates = [d for d in dates if d >= date.today() - timedelta(days=90)]
            if len(recent_dates) >= 3:
                trend = "ACCELERATING"
            elif len(recent_dates) == 0:
                trend = "IMPROVING"

        # Risk contribution
        acc = RiskAccumulator(cap=cfg.history_cap)
        if recurring:
            acc.add(cfg.risk_recurring_defect)
        if trend == "ACCELERATING":
            acc.add(cfg.risk_accelerating_trend)
        acc.add(min(len(section_tasks) * cfg.risk_per_section_failure,
                     cfg.risk_per_section_failure_cap))

        return {
            "total_failures": len(section_tasks),
            "recurring_defect": recurring,
            "same_category_count": len(same_cat),
            "mean_days_between_failures": round(mtbf, 1) if mtbf else None,
            "trend": trend,
            "risk_contribution": acc.rounded_score(3),
        }

    # ── 2. ASSET LIFECYCLE ──────────────────────────────────────────────────

    def _asset_lifecycle(self, task: MaintenanceTask) -> dict:
        """Assess asset health based on age, expected life, failure history."""
        cfg = self._cfg
        expected_life = ASSET_EXPECTED_LIFE.get(task.asset_type.value, 20)
        age_ratio = task.asset_age_years / expected_life if expected_life > 0 else 1.0

        # Risk tiers
        acc = RiskAccumulator(cap=cfg.lifecycle_cap)
        if age_ratio >= 1.0:
            lifecycle_status = "BEYOND_DESIGN_LIFE"
            acc.add(cfg.risk_beyond_design_life)
        elif age_ratio >= 0.8:
            lifecycle_status = "APPROACHING_END_OF_LIFE"
            acc.add(cfg.risk_approaching_eol)
        elif age_ratio >= 0.5:
            lifecycle_status = "MID_LIFE"
            acc.add(cfg.risk_mid_life)
        else:
            lifecycle_status = "EARLY_LIFE"
            acc.add(cfg.risk_early_life)

        # Failure frequency amplifier
        if task.historical_failure_count >= 5:
            acc.add(cfg.risk_high_failure_count)
        elif task.historical_failure_count >= 3:
            acc.add(cfg.risk_med_failure_count)

        return {
            "asset_age_years": task.asset_age_years,
            "expected_life_years": expected_life,
            "age_ratio": round(age_ratio, 2),
            "lifecycle_status": lifecycle_status,
            "historical_failures": task.historical_failure_count,
            "risk_contribution": acc.rounded_score(3),
        }

    # ── 3. CORRIDOR RISK PROFILE ────────────────────────────────────────────

    def _corridor_risk_profile(
        self, section: Optional[Section], corridor: Optional[Corridor]
    ) -> dict:
        """Evaluate risk from the corridor/section characteristics."""
        cfg = self._cfg
        acc = RiskAccumulator(cap=cfg.corridor_cap)

        if section:
            # Single-line sections: any block completely disrupts traffic
            if section.is_single_line:
                acc.add(cfg.risk_single_line, "Single-line section — no bypass available")

            # High-traffic sections
            density = section.traffic_density_class
            if density in (TrafficDensityClass.A_SPECIAL,):
                acc.add(cfg.risk_a_special_density, f"A-Special traffic density (>60 trains/day)")
            elif density in (TrafficDensityClass.A,):
                acc.add(cfg.risk_a_density, f"A-class traffic density (40-60 trains/day)")

            # No alternate routes
            if not section.alternate_routes:
                acc.add(cfg.risk_no_alternate_route, "No alternate route available")

        if corridor:
            # Rajdhani/Shatabdi corridor = strategic importance
            if corridor.is_rajdhani_route:
                acc.add(cfg.risk_rajdhani_route, "Rajdhani/Shatabdi corridor — strategic route")

        return {
            "factors": acc.reasons,
            "is_single_line": section.is_single_line if section else False,
            "traffic_density": section.traffic_density_class.value if section else "UNKNOWN",
            "risk_contribution": acc.rounded_score(3),
        }

    # ── 4. SEASONAL / ENVIRONMENTAL CONTEXT ─────────────────────────────────

    def _seasonal_context(self, task: MaintenanceTask) -> dict:
        """Season-aware risk assessment."""
        season = get_season(task.reported_date)
        risk = 0.0
        factors = []

        if season == Season.MONSOON:
            risk += 0.10
            factors.append("Monsoon season — waterlogging, embankment risk, OHE flash-over")
            # Rail fractures are especially dangerous in monsoon
            if task.defect_category in (
                DefectCategory.RAIL_FRACTURE,
                DefectCategory.WATERLOGGING,
                DefectCategory.EMBANKMENT_SLIP,
            ):
                risk += 0.08
                factors.append(f"{task.defect_category.value} during monsoon — amplified risk")

        elif season == Season.EXTREME_HEAT:
            risk += 0.05
            factors.append("Extreme heat — rail buckling risk, OHE sag")
            if task.defect_category in (
                DefectCategory.RAIL_FRACTURE,
                DefectCategory.GAUGE_IRREGULARITY,
            ):
                risk += 0.05
                factors.append("Heat-sensitive defect category")

        elif season == Season.FOG:
            risk += 0.05
            factors.append("Fog season — signal visibility degraded")
            if task.department == Department.SNT:
                risk += 0.05
                factors.append("S&T defect during fog season — visibility-critical")

        return {
            "season": season.value,
            "factors": factors,
            "risk_contribution": round(min(risk, 0.25), 3),
        }

    # ── EVIDENCE SUMMARY ────────────────────────────────────────────────────

    def _build_evidence_summary(
        self, history: dict, lifecycle: dict, corridor: dict, seasonal: dict
    ) -> list[str]:
        """Build human-readable evidence strings for LLM/report."""
        evidence = []

        # History evidence
        if history["recurring_defect"]:
            evidence.append(
                f"RECURRING: {history['same_category_count']} similar failures "
                f"in this section (MTBF: {history['mean_days_between_failures']} days)"
            )
        if history["trend"] == "ACCELERATING":
            evidence.append("TREND: Failure rate is ACCELERATING in this section")

        # Lifecycle evidence
        if lifecycle["lifecycle_status"] == "BEYOND_DESIGN_LIFE":
            evidence.append(
                f"ASSET: {lifecycle['asset_age_years']}y old — BEYOND design life "
                f"of {lifecycle['expected_life_years']}y "
                f"({lifecycle['historical_failures']} prior failures)"
            )
        elif lifecycle["lifecycle_status"] == "APPROACHING_END_OF_LIFE":
            evidence.append(
                f"ASSET: {lifecycle['age_ratio']:.0%} through expected life "
                f"({lifecycle['historical_failures']} prior failures)"
            )

        # Corridor evidence
        for f in corridor["factors"]:
            evidence.append(f"CORRIDOR: {f}")

        # Seasonal evidence
        for f in seasonal["factors"]:
            evidence.append(f"SEASON: {f}")

        return evidence
