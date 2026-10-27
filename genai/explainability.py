"""
RailOpt — Explainability engine for ML decisions and scheduling decisions.

Provides human-readable explanations of why a task received a particular
criticality score, why it was scheduled/deferred, and why blocks were merged.
Supports both Gemini LLM-powered and template-based explanations.
"""

from __future__ import annotations

from typing import List, Optional

from railopt.models import (
    BlockPlan,
    DefectSeverity,
    MaintenanceTask,
    ScheduledBlock,
    TaskStatus,
    ALWAYS_EMERGENCY,
    SAFETY_CRITICAL_DEFECTS,
)


# Human-readable names for SHAP feature keys
FEATURE_NAMES = {
    "department": "Department",
    "asset_type": "Asset type",
    "defect_category": "Defect category",
    "days_overdue": "Days overdue",
    "asset_age_years": "Asset age",
    "historical_failure_count": "Historical failures at location",
    "traffic_density_class": "Traffic density class",
    "is_safety_critical": "Safety-critical classification",
    "is_single_line": "Single-line section",
    "requires_power_block": "Requires power block",
    "crew_size_required": "Crew size",
    "season": "Season",
    "deferred_count": "Times previously deferred",
    "nlp_extracted_severity": "NLP-extracted severity",
}

from genai.llm_mixin import GeminiMixin


class ExplainabilityEngine(GeminiMixin):
    """Explains ML predictions and scheduling decisions to build trust."""

    def __init__(self, use_llm: bool = True):
        self._init_llm(use_llm, model="gemini-2.0-flash")

    # ------------------------------------------------------------------ #
    # Criticality Score Explanation
    # ------------------------------------------------------------------ #

    def explain_criticality_score(self, task: MaintenanceTask) -> str:
        """Explain why a task received its criticality score."""
        if self.use_llm and self._client:
            return self._llm_criticality(task)
        return self._template_criticality(task)

    def _template_criticality(self, task: MaintenanceTask) -> str:
        """Template-based explanation using SHAP values."""
        lines = [
            f"Task {task.task_id} scored {task.ml_criticality_score:.0f}/100 criticality.",
        ]

        severity = task.ml_predicted_severity
        if severity:
            lines.append(f"Predicted severity: {severity.value}")

        # Safety overrides
        if task.defect_category in ALWAYS_EMERGENCY:
            lines.append(
                f"\n⚠ Safety override: {task.defect_category.value} is classified "
                f"as ALWAYS EMERGENCY — score floor set to 95."
            )
        elif task.defect_category in SAFETY_CRITICAL_DEFECTS:
            lines.append(
                f"\n⚠ Safety flag: {task.defect_category.value} is a "
                f"safety-critical defect category."
            )

        # SHAP-based factors
        if task.ml_shap_values:
            sorted_shap = sorted(
                task.ml_shap_values.items(),
                key=lambda x: abs(x[1]),
                reverse=True,
            )
            lines.append("\nTop contributing factors:")
            for rank, (feature, value) in enumerate(sorted_shap[:7], 1):
                name = FEATURE_NAMES.get(feature, feature)
                direction = "↑" if value > 0 else "↓"
                sign = "+" if value > 0 else ""
                # Add contextual detail
                detail = self._get_feature_context(task, feature)
                lines.append(
                    f"  {rank}. {name} ({sign}{value:.1f}) {direction} — {detail}"
                )
        else:
            lines.append("\nFactor breakdown: (SHAP values not available)")
            lines.append(f"  • Department: {task.department.value}")
            lines.append(f"  • Defect: {task.defect_category.value}")
            lines.append(f"  • Days overdue: {task.days_overdue}")
            lines.append(f"  • Asset age: {task.asset_age_years:.1f} years")
            lines.append(
                f"  • Historical failures: {task.historical_failure_count}"
            )
            lines.append(
                f"  • Safety critical: {'Yes' if task.is_safety_critical else 'No'}"
            )

        return "\n".join(lines)

    def _get_feature_context(self, task: MaintenanceTask, feature: str) -> str:
        """Get contextual detail for a feature in plain English."""
        ctx = {
            "department": f"{task.department.value} department",
            "asset_type": f"{task.asset_type.value}",
            "defect_category": f"{task.defect_category.value}",
            "days_overdue": (
                f"{task.days_overdue} days past recommended window"
                if task.days_overdue > 0
                else "Within maintenance window"
            ),
            "asset_age_years": f"Asset is {task.asset_age_years:.1f} years old",
            "historical_failure_count": (
                f"{task.historical_failure_count} previous failures at this location"
            ),
            "is_safety_critical": (
                "Classified as safety-critical" if task.is_safety_critical
                else "Not safety-critical"
            ),
            "deferred_count": f"Deferred {task.deferred_count} times previously",
        }
        return ctx.get(feature, "")

    def _llm_criticality(self, task: MaintenanceTask) -> str:
      """LLM-powered explanation of criticality score."""
      template = self._template_criticality(task)
      prompt = (
          "You are explaining a maintenance task criticality score to an "
          "Indian Railways engineer. Rewrite this technical explanation "
          "in clear, professional language. Keep the SHAP factor rankings "
          "but make them easier to understand. Add a one-sentence summary "
          "of what action is recommended.\n"
          "Use ONLY the facts below. Do not add numbers, causes, or "
          "regulations that are not in the text.\n\n"
          f"{template}"
      )
      return self._llm_generate(prompt) or template

    # ------------------------------------------------------------------ #
    # Scheduling Decision Explanation
    # ------------------------------------------------------------------ #

    def explain_scheduling_decision(
        self, task: MaintenanceTask, plan: BlockPlan
    ) -> str:
        """Explain why a task was placed in a specific block."""
        if task.status != TaskStatus.SCHEDULED:
            return self.explain_deferral(task, plan)

        block = next(
            (b for b in plan.scheduled_blocks if task.task_id in b.task_ids),
            None,
        )
        if not block:
            return f"Task {task.task_id} is marked SCHEDULED but no block found."

        lines = [
            f"Task {task.task_id} was scheduled in block {block.block_id}.",
            "",
            f"Assigned window: {block.date} {block.start_time}–{block.end_time} "
            f"({block.duration_hours:.1f}h) on {block.section_name or block.section_id}.",
            "",
            "Reasons for this assignment:",
        ]

        reasons = []

        # Criticality-driven
        if task.ml_criticality_score >= 80:
            reasons.append(
                f"High criticality score ({task.ml_criticality_score:.0f}/100) "
                f"— prioritized for earliest available window"
            )
        elif task.ml_criticality_score >= 50:
            reasons.append(
                f"Moderate criticality ({task.ml_criticality_score:.0f}/100) "
                f"— scheduled within standard maintenance cycle"
            )

        # SLA-driven
        if task.is_safety_critical:
            reasons.append("Safety-critical task — SLA requires mandatory scheduling")

        if task.ml_predicted_severity == DefectSeverity.EMERGENCY:
            reasons.append("EMERGENCY severity — force-scheduled by SLA engine")

        # Impact optimization
        if block.trains_affected == 0:
            reasons.append(
                "Selected window has zero train impact (ideal off-peak slot)"
            )
        elif block.trains_affected <= 5:
            reasons.append(
                f"Low-impact window ({block.trains_affected} trains affected)"
            )

        # Merge benefit
        if block.is_merged:
            reasons.append(
                f"Merged with {', '.join(d.value for d in block.departments)} "
                f"— saved {block.merge_savings_hours:.1f}h vs separate blocks"
            )

        if not reasons:
            reasons.append(
                "Best available window matching section and duration requirements"
            )

        for i, reason in enumerate(reasons, 1):
            lines.append(f"  {i}. {reason}")

        return "\n".join(lines)

    # ------------------------------------------------------------------ #
    # Deferral Explanation
    # ------------------------------------------------------------------ #

    def explain_deferral(self, task: MaintenanceTask, plan: BlockPlan) -> str:
        """Explain why a task was deferred."""
        lines = [
            f"Task {task.task_id} ({task.defect_category.value}) was DEFERRED.",
            "",
        ]

        reasons = []

        if task.ml_criticality_score < 30:
            reasons.append(
                f"Low criticality score ({task.ml_criticality_score:.0f}/100) "
                f"— lower priority than scheduled tasks"
            )

        if task.deferred_count > 1:
            reasons.append(
                f"This task has been deferred {task.deferred_count} times previously"
            )
            if task.deferred_count >= 3:
                reasons.append(
                    "⚠ Repeated deferral — consider manual escalation review"
                )

        # Check if it was crowded out by higher-priority tasks
        same_section_blocks = [
            b for b in plan.scheduled_blocks if b.section_id == task.section_id
        ]
        if same_section_blocks:
            avg_crit = sum(
                b.total_criticality_score / max(len(b.task_ids), 1)
                for b in same_section_blocks
            ) / len(same_section_blocks)
            if task.ml_criticality_score < avg_crit:
                reasons.append(
                    f"Higher-priority tasks (avg criticality {avg_crit:.0f}) "
                    f"occupied available windows on this section"
                )
        else:
            reasons.append(
                "No compatible block windows available on this section "
                "within the planning horizon"
            )

        if not reasons:
            reasons.append(
                "Insufficient block window capacity to accommodate all tasks"
            )

        lines.append("Reasons:")
        for i, reason in enumerate(reasons, 1):
            lines.append(f"  {i}. {reason}")

        # Risk assessment
        if task.is_safety_critical:
            lines.append(
                "\n⚠ WARNING: This is a safety-critical task. "
                "Deferral should be reviewed by the section engineer."
            )

        return "\n".join(lines)

    # ------------------------------------------------------------------ #
    # Merge Explanation
    # ------------------------------------------------------------------ #

    def explain_merge(
        self, block: ScheduledBlock, tasks: list[MaintenanceTask]
    ) -> str:
        """Explain the benefits of a merged multi-department block."""
        task_map = {t.task_id: t for t in tasks}
        block_tasks = [task_map[tid] for tid in block.task_ids if tid in task_map]

        dept_tasks: dict[str, list[MaintenanceTask]] = {}
        for t in block_tasks:
            dept_tasks.setdefault(t.department.value, []).append(t)

        lines = [
            f"Block {block.block_id} is a MERGED multi-department block.",
            f"Section: {block.section_name or block.section_id}",
            f"Date: {block.date} {block.start_time}–{block.end_time} "
            f"({block.duration_hours:.1f}h)",
            "",
            f"Departments coordinated: {', '.join(d.value for d in block.departments)}",
            "",
            "Why merging was beneficial:",
            f"  • Without merging: {len(block.departments)} separate blocks "
            f"× {block.duration_hours:.1f}h = "
            f"{len(block.departments) * block.duration_hours:.1f}h total downtime",
            f"  • With merging: {block.duration_hours:.1f}h shared block",
            f"  • Savings: {block.merge_savings_hours:.1f} hours of "
            f"avoided track closure",
            "",
            "Tasks by department:",
        ]
        for dept_name, dept_task_list in sorted(dept_tasks.items()):
            lines.append(f"  {dept_name} ({len(dept_task_list)} tasks):")
            for t in dept_task_list:
                lines.append(
                    f"    • {t.task_id}: {t.defect_category.value} "
                    f"(criticality {t.ml_criticality_score:.0f})"
                )

        return "\n".join(lines)
