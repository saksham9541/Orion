"""
RailOpt — Natural language briefing generator for block plans.

Produces readable summaries of block plans for control room use.
Supports both LLM-powered (Gemini) and template-based generation.
"""

from __future__ import annotations

from collections import Counter
from typing import List, Optional

from railopt.models import (
    BlockPlan,
    DefectSeverity,
    Department,
    MaintenanceTask,
    ScheduledBlock,
    TaskStatus,
)

from genai.llm_mixin import GeminiMixin


class BriefingGenerator(GeminiMixin):
    """Generates natural-language summaries of block plans."""

    def __init__(self, use_llm: bool = True):
        self._init_llm(use_llm, model="gemini-2.0-flash")

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def generate_weekly_briefing(
        self, plan: BlockPlan, tasks: list[MaintenanceTask]
    ) -> str:
        """Generate a human-readable weekly briefing."""
        context = self._build_plan_context(plan, tasks, "Weekly")
        if self.use_llm and self._client:
            return self._llm_briefing(context)
        return self._template_briefing(plan, tasks, "Weekly")

    def generate_monthly_briefing(
        self, plan: BlockPlan, tasks: list[MaintenanceTask]
    ) -> str:
        """Generate a human-readable monthly briefing."""
        context = self._build_plan_context(plan, tasks, "Monthly")
        if self.use_llm and self._client:
            return self._llm_briefing(context)
        return self._template_briefing(plan, tasks, "Monthly")

    def generate_block_summary(
        self, block: ScheduledBlock, tasks: list[MaintenanceTask]
    ) -> str:
        """Generate a summary for a single scheduled block."""
        task_map = {t.task_id: t for t in tasks}
        block_tasks = [task_map[tid] for tid in block.task_ids if tid in task_map]

        lines = [
            f"Block {block.block_id} on {block.section_name or block.section_id}",
            f"Date: {block.date}  Time: {block.start_time}–{block.end_time} "
            f"({block.duration_hours:.1f}h)",
            f"Type: {block.block_type.value}",
            f"Departments: {', '.join(d.value for d in block.departments)}",
        ]

        if block.is_merged:
            lines.append(
                f"✓ Multi-department merged block — "
                f"saved ~{block.merge_savings_hours:.1f}h vs separate blocks"
            )

        lines.append(f"\nTasks ({len(block_tasks)}):")
        for t in block_tasks:
            sev = t.ml_predicted_severity or t.raw_severity or "—"
            if hasattr(sev, "value"):
                sev = sev.value
            lines.append(
                f"  • {t.task_id}: {t.defect_category.value} on {t.asset_type.value} "
                f"(criticality {t.ml_criticality_score:.0f}/100, severity {sev})"
            )

        if block.trains_affected:
            lines.append(
                f"\nTraffic impact: {block.trains_affected} trains affected, "
                f"~{block.cumulative_delay_minutes:.0f} min cumulative delay"
            )

        if block.justification:
            lines.append(f"\nJustification: {block.justification}")

        return "\n".join(lines)

    # ------------------------------------------------------------------ #
    # LLM-powered generation
    # ------------------------------------------------------------------ #

    def _build_plan_context(
        self, plan: BlockPlan, tasks: list[MaintenanceTask], horizon: str
    ) -> str:
        """Serialize plan data into structured context for the LLM."""
        task_map = {t.task_id: t for t in tasks}

        corridors = set(b.corridor_id for b in plan.scheduled_blocks)
        merged_blocks = [b for b in plan.scheduled_blocks if b.is_merged]
        emergency_tasks = [
            t for t in tasks
            if t.ml_predicted_severity == DefectSeverity.EMERGENCY
            and t.status == TaskStatus.SCHEDULED
        ]
        escalated = [t for t in tasks if t.status == TaskStatus.ESCALATED]
        deferred = [t for t in tasks if t.status == TaskStatus.DEFERRED]

        # Department breakdown
        dept_counts: dict[str, int] = Counter()
        for b in plan.scheduled_blocks:
            for tid in b.task_ids:
                if tid in task_map:
                    dept_counts[task_map[tid].department.value] += 1

        ctx_lines = [
            f"PLAN TYPE: {horizon} Block Plan",
            f"PERIOD: {plan.start_date} to {plan.end_date}",
            f"TOTAL BLOCKS: {len(plan.scheduled_blocks)}",
            f"CORRIDORS COVERED: {len(corridors)}",
            f"TASKS SCHEDULED: {plan.total_tasks_scheduled}",
            f"TASKS DEFERRED: {plan.total_tasks_deferred}",
            f"TOTAL BLOCK HOURS: {plan.total_block_hours:.1f}",
            f"MERGE SAVINGS: {plan.total_merge_savings_hours:.1f} hours",
            f"TRAINS AFFECTED: {plan.total_trains_affected}",
            f"SLA COMPLIANCE: {plan.sla_compliance_pct:.1f}%",
            "",
            "DEPARTMENT BREAKDOWN:",
        ]
        for dept, count in sorted(dept_counts.items()):
            ctx_lines.append(f"  {dept}: {count} tasks")

        if merged_blocks:
            ctx_lines.append(f"\nMERGED BLOCKS ({len(merged_blocks)}):")
            for b in merged_blocks[:5]:
                depts = ", ".join(d.value for d in b.departments)
                ctx_lines.append(
                    f"  {b.section_name or b.section_id} on {b.date}: "
                    f"{depts} — saved {b.merge_savings_hours:.1f}h"
                )

        if emergency_tasks:
            ctx_lines.append(f"\nEMERGENCY TASKS SCHEDULED ({len(emergency_tasks)}):")
            for t in emergency_tasks[:5]:
                ctx_lines.append(
                    f"  {t.task_id}: {t.defect_category.value} — "
                    f"criticality {t.ml_criticality_score:.0f}"
                )

        if escalated:
            ctx_lines.append(f"\nESCALATED TASKS ({len(escalated)}):")
            for t in escalated[:5]:
                ctx_lines.append(
                    f"  {t.task_id}: {t.defect_category.value} — "
                    f"{t.days_overdue} days overdue"
                )

        if deferred:
            ctx_lines.append(f"\nDEFERRED TASKS ({len(deferred)}):")
            for t in deferred[:5]:
                sev = t.ml_predicted_severity.value if t.ml_predicted_severity else "—"
                ctx_lines.append(
                    f"  {t.task_id}: {t.defect_category.value} — "
                    f"severity {sev}, deferred {t.deferred_count} times"
                )

        return "\n".join(ctx_lines)

    def _llm_briefing(self, context: str) -> str:
        """Generate a briefing using Gemini."""
        prompt = (
            "You are a railway maintenance planning assistant for Indian Railways. "
            "Generate a clear, professional control-room briefing from this block plan data.\n\n"
            "Requirements:\n"
            "- Start with a one-line executive summary\n"
            "- Include Key Highlights (3-5 bullets with the most important items)\n"
            "- Include Department Breakdown\n"
            "- Include SLA Compliance status\n"
            "- Mention merge savings prominently\n"
            "- Flag any emergency or escalated items\n"
            "- Note deferred tasks and whether they pose risk\n"
            "- Use concise, factual language suitable for railway controllers\n\n"
            f"PLAN DATA:\n{context}"
        )
        result = self._llm_generate(prompt)
        if result:
            return result
        return self._template_briefing_from_context(context)

    # ------------------------------------------------------------------ #
    # Template-based fallback
    # ------------------------------------------------------------------ #

    def _template_briefing(
        self, plan: BlockPlan, tasks: list[MaintenanceTask], horizon: str
    ) -> str:
        """Generate a structured briefing using Python templates."""
        corridors = set(b.corridor_id for b in plan.scheduled_blocks)
        merged = [b for b in plan.scheduled_blocks if b.is_merged]
        emergency_scheduled = [
            t for t in tasks
            if t.ml_predicted_severity == DefectSeverity.EMERGENCY
            and t.status == TaskStatus.SCHEDULED
        ]

        lines = [
            f"{horizon} Block Plan Summary ({plan.start_date} to {plan.end_date})",
            "=" * 60,
            "",
            f"Overview: {len(plan.scheduled_blocks)} maintenance blocks scheduled "
            f"across {len(corridors)} corridors, covering "
            f"{plan.total_tasks_scheduled} tasks.",
            "",
            "Key Highlights:",
        ]

        if emergency_scheduled:
            lines.append(
                f"  • {len(emergency_scheduled)} emergency defect(s) "
                f"force-scheduled for immediate attention"
            )

        if merged:
            total_saved = sum(b.merge_savings_hours for b in merged)
            lines.append(
                f"  • {len(merged)} multi-department merged block(s) — "
                f"saved ~{total_saved:.1f} hours vs separate closures"
            )

        if plan.total_tasks_deferred:
            lines.append(
                f"  • {plan.total_tasks_deferred} task(s) deferred to next cycle"
            )

        lines.append(
            f"  • Total block hours: {plan.total_block_hours:.1f}h"
        )
        lines.append(
            f"  • Total trains affected: {plan.total_trains_affected}"
        )

        # Department breakdown
        lines.append("")
        lines.append("Department Breakdown:")
        for dept, count in sorted(plan.departments_summary.items()):
            lines.append(f"  • {dept}: {count} tasks")

        # SLA
        lines.append("")
        if plan.sla_compliance_pct >= 95:
            lines.append(f"SLA Compliance: {plan.sla_compliance_pct:.1f}% ✓")
        elif plan.sla_compliance_pct >= 80:
            lines.append(
                f"SLA Compliance: {plan.sla_compliance_pct:.1f}% ⚠ "
                f"(some critical tasks may need attention)"
            )
        else:
            lines.append(
                f"SLA Compliance: {plan.sla_compliance_pct:.1f}% ✗ "
                f"(CRITICAL — multiple safety tasks unscheduled)"
            )

        if plan.escalated_task_ids:
            lines.append(
                f"\n⚠ {len(plan.escalated_task_ids)} task(s) auto-escalated "
                f"due to SLA breach"
            )

        return "\n".join(lines)

    def _template_briefing_from_context(self, context: str) -> str:
        """Minimal fallback: just return the context as-is with a header."""
        return f"Block Plan Briefing\n{'=' * 40}\n\n{context}"
