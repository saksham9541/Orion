"""
RailOpt — Signal Extractor.

Extracts discrete risk signals from task attributes — analogous
to FinCrime's extract_signals(). Each signal is a boolean flag
with a description, used both for scoring and for LLM context.
"""

from __future__ import annotations

from datetime import time
from railopt.models import (
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


# ── Night-time maintenance window (higher risk, lower visibility) ────────────
NIGHT_START = time(22, 0)
NIGHT_END = time(5, 0)

# ── High crew-size threshold ─────────────────────────────────────────────────
HIGH_CREW_THRESHOLD = 15


def extract_signals(
    task: MaintenanceTask,
    section: Section | None = None,
) -> dict:
    """
    Extract discrete risk signals from a maintenance task.

    Returns:
        {
            "signals": [{"name": str, "triggered": bool, "description": str}, ...],
            "triggered_signals": [str, ...],   # names of triggered signals
            "signal_score": float,             # 0-100
            "risk_contribution": float,        # 0.0-1.0
        }
    """
    signals = []

    # ── 1. SAFETY-CRITICAL DEFECT ────────────────────────────────────────
    is_emergency = task.defect_category in ALWAYS_EMERGENCY
    signals.append({
        "name": "EMERGENCY_DEFECT",
        "triggered": is_emergency,
        "description": f"Defect ({task.defect_category.value}) requires immediate emergency action",
        "weight": 30,
    })

    is_safety = task.defect_category in SAFETY_CRITICAL_DEFECTS
    signals.append({
        "name": "SAFETY_CRITICAL",
        "triggered": is_safety and not is_emergency,
        "description": f"Safety-critical defect category: {task.defect_category.value}",
        "weight": 20,
    })

    # ── 2. HIGHLY OVERDUE ────────────────────────────────────────────────
    signals.append({
        "name": "SEVERELY_OVERDUE",
        "triggered": task.days_overdue > 30,
        "description": f"Task is {task.days_overdue} days overdue (>30 day threshold)",
        "weight": 15,
    })

    signals.append({
        "name": "OVERDUE",
        "triggered": 7 < task.days_overdue <= 30,
        "description": f"Task is {task.days_overdue} days overdue",
        "weight": 8,
    })

    # ── 3. AGED ASSET ────────────────────────────────────────────────────
    signals.append({
        "name": "AGED_ASSET",
        "triggered": task.asset_age_years > 20,
        "description": f"Asset is {task.asset_age_years} years old — beyond typical design life",
        "weight": 10,
    })

    # ── 4. REPEAT FAILURE ────────────────────────────────────────────────
    signals.append({
        "name": "REPEAT_FAILURE",
        "triggered": task.historical_failure_count >= 3,
        "description": f"Asset has failed {task.historical_failure_count} times previously",
        "weight": 12,
    })

    # ── 5. POWER BLOCK REQUIRED ──────────────────────────────────────────
    signals.append({
        "name": "POWER_BLOCK_REQUIRED",
        "triggered": task.requires_power_block,
        "description": "Requires OHE power block — coordination with TRD mandatory",
        "weight": 5,
    })

    # ── 6. LARGE CREW ────────────────────────────────────────────────────
    signals.append({
        "name": "LARGE_CREW",
        "triggered": task.crew_size_required >= HIGH_CREW_THRESHOLD,
        "description": f"Requires {task.crew_size_required} crew members — resource-intensive",
        "weight": 5,
    })

    # ── 7. DEFERRED MULTIPLE TIMES ───────────────────────────────────────
    signals.append({
        "name": "MULTI_DEFERRED",
        "triggered": task.deferred_count >= 2,
        "description": f"Deferred {task.deferred_count} times — neglect risk",
        "weight": 12,
    })

    # ── 8. MONSOON + ENGINEERING ─────────────────────────────────────────
    season = get_season(task.reported_date)
    signals.append({
        "name": "MONSOON_RISK",
        "triggered": season == Season.MONSOON and task.department == Department.ENGINEERING,
        "description": "Engineering defect during monsoon — water damage amplification",
        "weight": 8,
    })

    # ── 9. HIGH-TRAFFIC SECTION ──────────────────────────────────────────
    is_high_traffic = (
        section is not None
        and section.traffic_density_class in (
            TrafficDensityClass.A_SPECIAL, TrafficDensityClass.A
        )
    )
    signals.append({
        "name": "HIGH_TRAFFIC_SECTION",
        "triggered": is_high_traffic,
        "description": "Section carries >40 trains/day — high disruption potential",
        "weight": 8,
    })

    # ── 10. SINGLE LINE ──────────────────────────────────────────────────
    is_single = section is not None and section.is_single_line
    signals.append({
        "name": "SINGLE_LINE",
        "triggered": is_single,
        "description": "Single-line section — complete traffic halt during block",
        "weight": 10,
    })

    # ── SCORE COMPUTATION ────────────────────────────────────────────────
    triggered = [s for s in signals if s["triggered"]]
    signal_score = min(sum(s["weight"] for s in triggered), 100)

    return {
        "signals": signals,
        "triggered_signals": [s["name"] for s in triggered],
        "triggered_descriptions": [s["description"] for s in triggered],
        "signal_count": len(triggered),
        "signal_score": signal_score,
        "risk_contribution": round(min(signal_score / 100, 1.0), 3),
    }


def extract_signals_batch(
    tasks: list[MaintenanceTask],
    sections: dict[str, Section],
) -> list[dict]:
    """Batch signal extraction."""
    return [
        extract_signals(t, sections.get(t.section_id))
        for t in tasks
    ]
