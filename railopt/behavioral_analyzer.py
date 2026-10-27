"""
RailOpt — Behavioral Analyzer.

Detects anomalous patterns in maintenance tasks by comparing against
historical baselines — analogous to FinCrime's behavioral scoring
(deviation from user spending patterns).

Analyzes:
  1. Section Failure Rate Anomaly — is this section failing more than peers?
  2. Department Workload Anomaly — is one department overloaded?
  3. Defect Clustering — are defects clustering in time/space?
  4. Deferral Pattern — are tasks being repeatedly deferred?
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, timedelta
from typing import Optional

from railopt.models import (
    DefectCategory,
    Department,
    MaintenanceTask,
    Section,
    SAFETY_CRITICAL_DEFECTS,
)
from railopt.risk_component import BehavioralConfig, RiskAccumulator


class BehavioralAnalyzer:
    """
    Detects anomalous maintenance patterns by comparing each task's
    context against fleet-wide baselines. Produces a behavior_score
    (0–100) and a list of behavioral_reasons.
    """

    def __init__(self, config: BehavioralConfig | None = None) -> None:
        self._cfg = config or BehavioralConfig()

    def analyze_task(
        self,
        task: MaintenanceTask,
        all_tasks: list[MaintenanceTask],
        sections: dict[str, Section],
    ) -> dict:
        """Full behavioral analysis for a single task."""
        section_anomaly = self._section_failure_anomaly(task, all_tasks)
        dept_anomaly = self._department_workload_anomaly(task, all_tasks)
        clustering = self._defect_clustering(task, all_tasks)
        deferral = self._deferral_pattern(task, all_tasks)

        behavior_score = min(
            section_anomaly["score"]
            + dept_anomaly["score"]
            + clustering["score"]
            + deferral["score"],
            self._cfg.overall_cap,
        )

        reasons = (
            section_anomaly["reasons"]
            + dept_anomaly["reasons"]
            + clustering["reasons"]
            + deferral["reasons"]
        )

        return {
            "behavior_score": round(behavior_score, 1),
            "reasons": reasons,
            "section_anomaly": section_anomaly,
            "department_anomaly": dept_anomaly,
            "defect_clustering": clustering,
            "deferral_pattern": deferral,
            "risk_contribution": round(min(behavior_score / 100, 1.0), 3),
        }

    def analyze_batch(
        self,
        tasks: list[MaintenanceTask],
        sections: dict[str, Section],
    ) -> list[dict]:
        """Batch analysis — one result per task."""
        return [self.analyze_task(t, tasks, sections) for t in tasks]

    # ── 1. SECTION FAILURE RATE ANOMALY ─────────────────────────────────────

    def _section_failure_anomaly(
        self, task: MaintenanceTask, all_tasks: list[MaintenanceTask]
    ) -> dict:
        """Is this section failing more than the fleet average?"""
        section_counts: dict[str, int] = Counter(t.section_id for t in all_tasks)
        total_sections = len(section_counts)
        if total_sections == 0:
            return {"score": 0, "reasons": [], "ratio": 1.0}

        avg_failures = len(all_tasks) / total_sections
        this_section = section_counts.get(task.section_id, 0)
        ratio = this_section / avg_failures if avg_failures > 0 else 1.0

        score = 0
        reasons = []

        if ratio >= self._cfg.section_ratio_severe:
            score = self._cfg.section_score_severe
            reasons.append(
                f"Section {task.section_id} has {ratio:.1f}x the average failure rate "
                f"({this_section} vs avg {avg_failures:.0f})"
            )
        elif ratio >= self._cfg.section_ratio_high:
            score = self._cfg.section_score_high
            reasons.append(
                f"Section has {ratio:.1f}x the average failure rate"
            )
        elif ratio >= self._cfg.section_ratio_moderate:
            score = self._cfg.section_score_moderate
            reasons.append(f"Section failure rate {ratio:.1f}x above average")

        return {"score": score, "reasons": reasons, "ratio": round(ratio, 2)}

    # ── 2. DEPARTMENT WORKLOAD ANOMALY ──────────────────────────────────────

    def _department_workload_anomaly(
        self, task: MaintenanceTask, all_tasks: list[MaintenanceTask]
    ) -> dict:
        """Is one department disproportionately overloaded?"""
        dept_counts = Counter(t.department for t in all_tasks)
        total = len(all_tasks)
        if total == 0:
            return {"score": 0, "reasons": [], "dept_share": 0}

        dept_share = dept_counts.get(task.department, 0) / total
        expected_shares = {
            Department.ENGINEERING: 0.55,
            Department.SNT: 0.25,
            Department.TRD: 0.20,
        }
        expected = expected_shares.get(task.department, 0.33)

        score = 0
        reasons = []

        if dept_share > expected * self._cfg.dept_overload_factor:
            score = self._cfg.dept_overload_score
            reasons.append(
                f"{task.department.value} has {dept_share:.0%} of all tasks "
                f"(expected ~{expected:.0%}) — workload concentration risk"
            )
        elif dept_share < expected * self._cfg.dept_underload_factor:
            score = self._cfg.dept_underload_score
            reasons.append(
                f"{task.department.value} has unusually low task count — "
                f"possible under-reporting"
            )

        return {"score": score, "reasons": reasons, "dept_share": round(dept_share, 3)}

    # ── 3. DEFECT CLUSTERING ────────────────────────────────────────────────

    def _defect_clustering(
        self, task: MaintenanceTask, all_tasks: list[MaintenanceTask]
    ) -> dict:
        """Are similar defects clustering in time within this corridor?"""
        corridor_tasks = [
            t for t in all_tasks
            if t.corridor_id == task.corridor_id
            and t.defect_category == task.defect_category
            and t.task_id != task.task_id
        ]

        recent = [
            t for t in corridor_tasks
            if abs((t.reported_date - task.reported_date).days) <= 7
        ]

        same_section = [
            t for t in corridor_tasks if t.section_id == task.section_id
        ]

        acc = RiskAccumulator(cap=self._cfg.clustering_cap)

        if len(recent) >= self._cfg.cluster_severe_threshold:
            acc.add(
                self._cfg.cluster_severe_score,
                f"CLUSTER: {len(recent)} {task.defect_category.value} defects "
                f"reported within 7 days in corridor {task.corridor_id}",
            )
        elif len(recent) >= self._cfg.cluster_moderate_threshold:
            acc.add(
                self._cfg.cluster_moderate_score,
                f"{len(recent)} similar defects within 7 days in same corridor",
            )

        if len(same_section) >= self._cfg.cluster_section_threshold:
            acc.add(
                self._cfg.cluster_section_score,
                f"{len(same_section)} {task.defect_category.value} defects in "
                f"same section — systematic issue likely",
            )

        return {
            "score": acc.score,
            "reasons": acc.reasons,
            "recent_cluster_size": len(recent),
            "section_cluster_size": len(same_section),
        }

    # ── 4. DEFERRAL PATTERN ─────────────────────────────────────────────────

    def _deferral_pattern(
        self, task: MaintenanceTask, all_tasks: list[MaintenanceTask]
    ) -> dict:
        """Are tasks in this section being repeatedly deferred?"""
        section_tasks = [
            t for t in all_tasks if t.section_id == task.section_id
        ]
        deferred_tasks = [t for t in section_tasks if t.deferred_count >= self._cfg.deferral_moderate_threshold]

        acc = RiskAccumulator(cap=self._cfg.deferral_cap)

        if task.deferred_count >= self._cfg.deferral_chronic_threshold:
            acc.add(
                self._cfg.deferral_chronic_score,
                f"Task deferred {task.deferred_count} times — chronic neglect pattern",
            )
        elif task.deferred_count >= self._cfg.deferral_moderate_threshold:
            acc.add(
                self._cfg.deferral_moderate_score,
                f"Task deferred {task.deferred_count} times",
            )

        if len(deferred_tasks) >= self._cfg.deferral_section_threshold:
            acc.add(
                self._cfg.deferral_section_score,
                f"{len(deferred_tasks)} tasks in this section have been deferred 2+ times",
            )

        if task.deferred_count >= 1 and task.defect_category in SAFETY_CRITICAL_DEFECTS:
            acc.add(
                self._cfg.deferral_safety_score,
                f"ALERT: Safety-critical defect ({task.defect_category.value}) "
                f"was deferred — violates safety protocol",
            )

        return {"score": acc.score, "reasons": acc.reasons}

