"""
Orion — Early Warning Agent for Predictive Maintenance Risk Detection.
Monitors track sections, defect recurrence, asset aging, and seasonal weather
to detect compounding failure risks before they escalate into emergencies.
"""
from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional

from railopt.models import (
    Corridor,
    DefectCategory,
    DefectSeverity,
    EarlyWarning,
    MaintenanceTask,
    Season,
    Section,
    get_season,
)

logger = logging.getLogger(__name__)


class EarlyWarningAgent:
    """
    Proactive monitoring agent. Identifies trending failure hotspots,
    defect clusters, and environmental vulnerabilities.
    """

    def __init__(self):
        self.name = "Predictive Early Warning Agent"

    def scan_corridor_risks(
        self,
        tasks: List[MaintenanceTask],
        corridors: List[Corridor],
        sections: Dict[str, Section],
        current_date: Optional[date] = None,
    ) -> List[EarlyWarning]:
        """
        Scans all tasks and infrastructure topology to generate proactive alerts.
        """
        eval_date = current_date or date.today()
        season = get_season(eval_date)
        warnings: List[EarlyWarning] = []

        # 1. Cluster analysis: group tasks by section
        section_tasks: Dict[str, List[MaintenanceTask]] = {}
        for t in tasks:
            section_tasks.setdefault(t.section_id, []).append(t)

        for section_id, t_list in section_tasks.items():
            sec = sections.get(section_id)
            corridor_id = t_list[0].corridor_id if t_list else ""

            # Check 1: Recurrence hotspot (>= 3 historic failures or >= 4 active defects)
            total_historical = sum(t.historical_failure_count for t in t_list)
            active_count = len(t_list)

            if total_historical >= 6 or active_count >= 5:
                w = EarlyWarning(
                    warning_id=f"EW-HOTSPOT-{uuid.uuid4().hex[:6].upper()}",
                    corridor_id=corridor_id,
                    section_id=section_id,
                    asset_type=t_list[0].asset_type.value,
                    risk_level="HIGH" if active_count >= 6 else "MEDIUM",
                    message=(
                        f"Defect Hotspot Alert on {sec.name if sec else section_id}: "
                        f"{active_count} active defects with {total_historical} cumulative historical failures. "
                        f"Risk of compounding signal or track breakdown."
                    ),
                    trend_data={
                        "active_defects": float(active_count),
                        "historical_failures": float(total_historical),
                    },
                    recommended_action="Schedule comprehensive integrated corridor inspection during next available block.",
                    estimated_failure_window_days=7 if active_count >= 6 else 14,
                    created_at=datetime.now(timezone.utc),
                )
                warnings.append(w)

            # Check 2: Seasonal weather risk
            seasonal_alert = self._evaluate_seasonal_vulnerability(
                t_list, sec, season, corridor_id, section_id
            )
            if seasonal_alert:
                warnings.append(seasonal_alert)

            # Check 3: Safety-critical aging infrastructure
            aging_tasks = [t for t in t_list if t.asset_age_years >= 15.0 and t.is_safety_critical]
            if len(aging_tasks) >= 2:
                w = EarlyWarning(
                    warning_id=f"EW-AGING-{uuid.uuid4().hex[:6].upper()}",
                    corridor_id=corridor_id,
                    section_id=section_id,
                    asset_type=aging_tasks[0].asset_type.value,
                    risk_level="HIGH",
                    message=(
                        f"Asset Fatigue on {sec.name if sec else section_id}: "
                        f"{len(aging_tasks)} safety-critical defects on assets exceeding 15 years in service."
                    ),
                    trend_data={"aging_assets_count": len(aging_tasks)},
                    recommended_action="Execute ultrasonic rail flaw detection (USFD) or insulator replacement.",
                    estimated_failure_window_days=5,
                    created_at=datetime.now(timezone.utc),
                )
                warnings.append(w)

        return warnings

    def _evaluate_seasonal_vulnerability(
        self,
        t_list: List[MaintenanceTask],
        sec: Optional[Section],
        season: Season,
        corridor_id: str,
        section_id: str,
    ) -> Optional[EarlyWarning]:
        """Evaluates seasonal vulnerabilities specific to Indian Railways conditions."""
        sec_name = sec.name if sec else section_id

        if season in (Season.EXTREME_HEAT, Season.SUMMER):
            # Track buckling risk in high heat
            weld_defects = [
                t for t in t_list
                if t.defect_category in (DefectCategory.WELD_FAILURE, DefectCategory.GAUGE_IRREGULARITY)
            ]
            if weld_defects:
                return EarlyWarning(
                    warning_id=f"EW-SEASON-{uuid.uuid4().hex[:6].upper()}",
                    corridor_id=corridor_id,
                    section_id=section_id,
                    asset_type="TRACK",
                    risk_level="HIGH",
                    message=f"Thermal Track Buckling Risk ({season.value}) on {sec_name}. High ambient rail temperatures exacerbate existing weld irregularities.",
                    trend_data={"weld_issues": float(len(weld_defects)), "thermal_stress_factor": 1.4},
                    recommended_action="Deploy mobile track destressing patrol and implement temporary caution order.",
                    estimated_failure_window_days=3,
                    created_at=datetime.now(timezone.utc),
                )

        elif season == Season.MONSOON:
            # Drainage and signaling track circuit failures during monsoon
            water_defects = [
                t for t in t_list
                if t.defect_category in (DefectCategory.WATERLOGGING, DefectCategory.TRACK_CIRCUIT_FAILURE)
            ]
            if water_defects:
                return EarlyWarning(
                    warning_id=f"EW-MONSOON-{uuid.uuid4().hex[:6].upper()}",
                    corridor_id=corridor_id,
                    section_id=section_id,
                    asset_type="SIGNAL",
                    risk_level="HIGH",
                    message=f"Monsoon Waterlogging & Track Circuit Failure Alert on {sec_name}.",
                    trend_data={"monsoon_issues": len(water_defects)},
                    recommended_action="Clear catchwater drains and inspect bootleg track circuit junctions.",
                    estimated_failure_window_days=4,
                    created_at=datetime.now(timezone.utc),
                )

        elif season in (Season.WINTER, Season.FOG):
            # Cold weather rail fractures
            fracture_risks = [
                t for t in t_list
                if t.defect_category in (DefectCategory.RAIL_FRACTURE, DefectCategory.ULTRASONIC_FLAW)
            ]
            if fracture_risks:
                return EarlyWarning(
                    warning_id=f"EW-WINTER-{uuid.uuid4().hex[:6].upper()}",
                    corridor_id=corridor_id,
                    section_id=section_id,
                    asset_type="RAIL",
                    risk_level="EMERGENCY" if any(t.defect_category == DefectCategory.RAIL_FRACTURE for t in fracture_risks) else "HIGH",
                    message=f"Cold Weather Rail Tensile Fracture Hazard on {sec_name}.",
                    trend_data={"fracture_risks": len(fracture_risks)},
                    recommended_action="Execute immediate fishplate clamping and joggled fishplate reinforcement.",
                    estimated_failure_window_days=2,
                    created_at=datetime.now(timezone.utc),
                )

        return None
