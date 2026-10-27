"""
RailOpt — Indian Railways Compliance Engine.

Assesses maintenance tasks against 4 regulatory frameworks:
  1. RDSO — Research Designs & Standards Organisation guidelines
  2. CRS  — Commissioner of Railway Safety notifications
  3. IRSGE — Indian Railway Standard General Engineering
  4. Railway Board Circulars — operational directives

Produces compliance flags, risk score, regulatory citations,
and a structured report — analogous to FinCrime's ComplianceEngine
(which checks RBI, FATF, PMLA) but for railway safety regulations.
"""

from __future__ import annotations

from railopt.models import (
    DefectCategory,
    DefectSeverity,
    Department,
    MaintenanceTask,
    SAFETY_CRITICAL_DEFECTS,
    ALWAYS_EMERGENCY,
    MAX_DEFERRAL_HOURS,
)


# ── Regulatory framework definitions ─────────────────────────────────────────
FRAMEWORKS = {
    "RDSO": {
        "name": "Research Designs & Standards Organisation",
        "full_name": "RDSO Guidelines for Track Maintenance (2020)",
        "url": "https://rdso.indianrailways.gov.in/",
        "scope": "Track, structures, and material standards",
    },
    "CRS": {
        "name": "Commissioner of Railway Safety",
        "full_name": "CRS Safety Directives & Notifications",
        "url": "https://crs.gov.in/",
        "scope": "Safety compliance, accident investigation, speed restrictions",
    },
    "IRSGE": {
        "name": "Indian Railway Standard — General Engineering",
        "full_name": "IRSGE/IRPWM — Indian Railway Permanent Way Manual",
        "url": "https://indianrailways.gov.in/",
        "scope": "Track geometry, gauge, alignment, curve standards",
    },
    "RB": {
        "name": "Railway Board",
        "full_name": "Railway Board Circulars & Operating Directives",
        "url": "https://indianrailways.gov.in/railwayboard/",
        "scope": "Block planning policy, asset utilization norms, maintenance windows",
    },
}

# ── RDSO tolerance limits ─────────────────────────────────────────────────────
# Based on RDSO Track Maintenance manual Table 3.1
RDSO_GAUGE_TOLERANCE_MM = {
    "A_SPECIAL": {"min": -3, "max": 6},
    "A": {"min": -3, "max": 6},
    "B": {"min": -5, "max": 10},
    "C": {"min": -5, "max": 15},
    "D": {"min": -5, "max": 15},
    "E": {"min": -5, "max": 20},
}

# ── CRS speed restriction triggers ───────────────────────────────────────────
CRS_IMMEDIATE_SPEED_RESTRICTION = {
    DefectCategory.RAIL_FRACTURE,
    DefectCategory.WELD_DEFECT,
    DefectCategory.GAUGE_IRREGULARITY,
    DefectCategory.EMBANKMENT_SLIP,
}

# ── IRPWM deferral limits (stricter than SLA engine) ─────────────────────────
IRPWM_MAX_RESPONSE_HOURS = {
    DefectSeverity.EMERGENCY: 2,    # IRPWM Ch. 3: Immediate attention
    DefectSeverity.HIGH: 24,        # Within 24 hours
    DefectSeverity.MEDIUM: 168,     # Within 1 week
    DefectSeverity.LOW: 720,        # Within 1 month
}


from railopt.risk_component import ComplianceEngineConfig, RiskAccumulator


class ComplianceEngine:
    """
    Runs a maintenance task through RDSO, CRS, IRSGE, and Railway Board
    rule sets. Returns compliance flags, risk level, and regulatory citations.
    References are representative placeholders modeled on Indian Railways regulatory structure. Pending mapping to specific RDSO/CRS/IRPWM chapter and paragraph numbers from official manuals.
    """

    def __init__(self, config: ComplianceEngineConfig | None = None) -> None:
        self._cfg = config or ComplianceEngineConfig()

    def assess(self, task: MaintenanceTask, context: dict = None) -> dict:
        """
        Full compliance assessment for a maintenance task.

        Returns:
            {
                rdso_assessment:    {...},
                crs_assessment:     {...},
                irsge_assessment:   {...},
                rb_assessment:      {...},
                overall_compliance_risk: LOW/MEDIUM/HIGH/CRITICAL,
                total_flags:        int,
                regulatory_report:  [list of strings],
                compliance_score:   0-100 (higher = more regulatory concern)
            }
        """
        rdso = self._assess_rdso(task, context)
        crs = self._assess_crs(task, context)
        irsge = self._assess_irsge(task, context)
        rb = self._assess_railway_board(task, context)

        total_flags = (
            len(rdso["flags"]) + len(crs["flags"])
            + len(irsge["flags"]) + len(rb["flags"])
        )
        compliance_score = min(
            rdso["risk_score"] + crs["risk_score"]
            + irsge["risk_score"] + rb["risk_score"],
            self._cfg.overall_cap,
        )

        overall = self._overall_risk(compliance_score)
        report = self._build_report(rdso, crs, irsge, rb, overall)

        return {
            "rdso_assessment": rdso,
            "crs_assessment": crs,
            "irsge_assessment": irsge,
            "rb_assessment": rb,
            "overall_compliance_risk": overall,
            "total_flags": total_flags,
            "compliance_score": round(compliance_score, 1),
            "regulatory_report": report,
            "frameworks_checked": list(FRAMEWORKS.keys()),
        }

    def assess_batch(self, tasks: list[MaintenanceTask], contexts: list[dict] = None) -> list[dict]:
        """Batch assessment — one compliance result per task."""
        if contexts is None:
            contexts = [None] * len(tasks)
        return [self.assess(t, c) for t, c in zip(tasks, contexts)]

    # ── RDSO ASSESSMENT ──────────────────────────────────────────────────────

    def _assess_rdso(self, task: MaintenanceTask, context: dict = None) -> dict:
        flags = []
        acc = RiskAccumulator(cap=self._cfg.rdso_cap)

        if task.defect_category in ALWAYS_EMERGENCY:
            flags.append({
                "rule": "RDSO-TRACK-3.1",
                "description": f"{task.defect_category.value} classified as immediate action defect",
                "illustrative_reference": "RDSO Track Maintenance Manual, Chapter 3, Table 3.1",
                "severity": "CRITICAL",
            })
            acc.add(self._cfg.rdso_always_emergency)

        if task.defect_category in SAFETY_CRITICAL_DEFECTS:
            flags.append({
                "rule": "RDSO-SAFETY-4.2",
                "description": f"Safety-critical defect: {task.defect_category.value}",
                "illustrative_reference": "RDSO Safety Circular No. 48/2019",
                "severity": "HIGH",
            })
            acc.add(self._cfg.rdso_safety_critical)

        if task.historical_failure_count >= self._cfg.rdso_repeated_failures_threshold:
            flags.append({
                "rule": "RDSO-RELIABILITY-5.1",
                "description": f"Asset has {task.historical_failure_count} prior failures — replacement review required",
                "illustrative_reference": "RDSO Guidelines on Asset Renewal Planning, Section 5",
                "severity": "MEDIUM",
            })
            acc.add(self._cfg.rdso_repeated_failures)

        if task.asset_age_years > self._cfg.rdso_old_asset_age_threshold and task.department == Department.ENGINEERING:
            flags.append({
                "rule": "RDSO-LIFECYCLE-6.3",
                "description": f"Engineering asset is {task.asset_age_years}y old — exceeds RDSO recommended assessment interval",
                "illustrative_reference": "RDSO Circular on Condition-Based Maintenance (2021)",
                "severity": "MEDIUM",
            })
            acc.add(self._cfg.rdso_old_asset)

        return {"flags": flags, "risk_score": acc.score, "framework": "RDSO"}

    # ── CRS ASSESSMENT ───────────────────────────────────────────────────────

    def _assess_crs(self, task: MaintenanceTask, context: dict = None) -> dict:
        flags = []
        acc = RiskAccumulator(cap=self._cfg.crs_cap)

        if task.defect_category in CRS_IMMEDIATE_SPEED_RESTRICTION:
            flags.append({
                "rule": "CRS-SR-2024-01",
                "description": f"{task.defect_category.value} mandates immediate speed restriction per CRS notification",
                "illustrative_reference": "CRS Notification on Speed Restrictions for Track Defects (2024)",
                "severity": "CRITICAL",
            })
            acc.add(self._cfg.crs_speed_restriction)

        severity = task.ml_predicted_severity or DefectSeverity.MEDIUM
        max_hours = IRPWM_MAX_RESPONSE_HOURS.get(severity, 720)
        overdue_hours = task.days_overdue * 24
        if overdue_hours > max_hours and task.defect_category in SAFETY_CRITICAL_DEFECTS:
            flags.append({
                "rule": "CRS-OVERDUE-3.4",
                "description": (
                    f"Safety-critical task overdue by {task.days_overdue} days "
                    f"(limit: {max_hours}h) — CRS reportable incident"
                ),
                "illustrative_reference": "CRS Standing Order: Delayed Maintenance Reporting",
                "severity": "HIGH",
            })
            acc.add(self._cfg.crs_overdue_safety)

        if context and context.get("corridor_risk_profile", {}).get("is_single_line"):
            if task.defect_category in SAFETY_CRITICAL_DEFECTS:
                flags.append({
                    "rule": "CRS-SL-5.1",
                    "description": "Safety defect on single-line section — no alternate route",
                    "illustrative_reference": "CRS Advisory on Single-Line Section Maintenance Priority",
                    "severity": "HIGH",
                })
                acc.add(self._cfg.crs_single_line_safety)

        return {"flags": flags, "risk_score": acc.score, "framework": "CRS"}

    # ── IRSGE / IRPWM ASSESSMENT ─────────────────────────────────────────────

    def _assess_irsge(self, task: MaintenanceTask, context: dict = None) -> dict:
        flags = []
        acc = RiskAccumulator(cap=self._cfg.irsge_cap)

        if task.defect_category in (
            DefectCategory.GAUGE_IRREGULARITY,
            DefectCategory.ALIGNMENT_DEFECT,
        ):
            flags.append({
                "rule": "IRPWM-CH3-301",
                "description": f"Track geometry defect ({task.defect_category.value}) — IRPWM Chapter 3 tolerances apply",
                "illustrative_reference": "Indian Railway Permanent Way Manual, Chapter 3, Para 301-305",
                "severity": "MEDIUM",
            })
            acc.add(self._cfg.irsge_track_geometry)

        if context:
            season = context.get("seasonal_context", {}).get("season", "")
            if season == "MONSOON" and task.department == Department.ENGINEERING:
                flags.append({
                    "rule": "IRPWM-CH8-801",
                    "description": "Monsoon season — enhanced patrolling and maintenance required per IRPWM",
                    "illustrative_reference": "IRPWM Chapter 8: Monsoon Precautions, Para 801-815",
                    "severity": "HIGH",
                })
                acc.add(self._cfg.irsge_monsoon_engineering)

        if task.requires_power_block and task.department == Department.TRD:
            flags.append({
                "rule": "IRSGE-TRD-7.2",
                "description": "Power block mandatory — OHE work requires scheduled power block as per IRSGE-TRD",
                "illustrative_reference": "IRSGE (TRD) Manual: Power Block Procedure, Section 7",
                "severity": "MEDIUM",
            })
            acc.add(self._cfg.irsge_power_block)

        return {"flags": flags, "risk_score": acc.score, "framework": "IRSGE"}

    # ── RAILWAY BOARD ASSESSMENT ─────────────────────────────────────────────

    def _assess_railway_board(self, task: MaintenanceTask, context: dict = None) -> dict:
        flags = []
        acc = RiskAccumulator(cap=self._cfg.rb_cap)

        if task.estimated_duration_hours and task.estimated_duration_hours > self._cfg.rb_long_block_hours:
            flags.append({
                "rule": "RB-BLOCK-2023-14",
                "description": f"Task duration ({task.estimated_duration_hours}h) exceeds standard {self._cfg.rb_long_block_hours}h block — split recommended",
                "illustrative_reference": "Railway Board Circular 2023/Safety/Block/14: Block Duration Policy",
                "severity": "LOW",
            })
            acc.add(self._cfg.rb_long_block)

        if context:
            section_history = context.get("section_failure_history", {})
            if section_history.get("total_failures", 0) >= self._cfg.rb_high_failure_threshold:
                flags.append({
                    "rule": "RB-COORD-2024-08",
                    "description": "High-failure section — mandatory coordination meeting per Railway Board directive",
                    "illustrative_reference": "Railway Board Letter 2024/Safety/Coord/08: Inter-departmental Coordination",
                    "severity": "MEDIUM",
                })
                acc.add(self._cfg.rb_high_failure_section)

        if task.deferred_count >= self._cfg.rb_deferred_threshold:
            flags.append({
                "rule": "RB-DEFER-2022-03",
                "description": f"Task deferred {task.deferred_count} times — mandatory DRM review per Railway Board policy",
                "illustrative_reference": "Railway Board Policy on Maintenance Deferral Limits (2022)",
                "severity": "HIGH",
            })
            acc.add(self._cfg.rb_deferred_task)

        return {"flags": flags, "risk_score": acc.score, "framework": "RB"}

    # ── HELPERS ──────────────────────────────────────────────────────────────

    @staticmethod
    def _overall_risk(score: float) -> str:
        if score >= 60:
            return "CRITICAL"
        elif score >= 40:
            return "HIGH"
        elif score >= 20:
            return "MEDIUM"
        return "LOW"

    @staticmethod
    def _build_report(
        rdso: dict, crs: dict, irsge: dict, rb: dict, overall: str
    ) -> list[str]:
        report = [f"Overall Compliance Risk: {overall}"]
        for name, assessment in [
            ("RDSO", rdso), ("CRS", crs), ("IRSGE/IRPWM", irsge), ("Railway Board", rb)
        ]:
            if assessment["flags"]:
                report.append(f"\n--- {name} ({assessment['risk_score']} pts) ---")
                for flag in assessment["flags"]:
                    report.append(
                        f"  [{flag['severity']}] {flag['rule']}: {flag['description']}"
                    )
                    report.append(f"    Illustrative Reference: {flag['illustrative_reference']}")
        return report
