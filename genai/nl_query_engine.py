"""
RailOpt — Natural language query interface over block plans.

Supports LLM-powered grounded answers (NVIDIA-hosted model via LLMMixin) and a
keyword/regex fallback for offline use. Controllers can ask questions like:
  "What's blocked on the Delhi-Ghaziabad corridor next week?"
  "Why was defect #MT-a1b2c3d4 deferred?"

How the LLM path stays honest:
  Before asking the LLM, we pick the records that match the question
  (corridor, section, task ID, department, emergencies). The LLM only sees
  those records plus plan-wide totals, and every list says how many records
  exist in total and whether it is partial.
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import date

from railopt.models import (
    BlockPlan,
    Corridor,
    DefectSeverity,
    MaintenanceTask,
    ScheduledBlock,
    TaskStatus,
)

from genai.llm_mixin import GeminiMixin

# Caps keep the prompt small and fast. Every capped list says so in the context.
MAX_BLOCKS_UNFILTERED = 40
MAX_BLOCKS_FILTERED = 60
MAX_TASK_LINES = 30

_TASK_ID_RE = re.compile(r"MT-[a-z0-9]+", re.IGNORECASE)

# Words ignored when matching corridor / section names against the question.
_STOP_WORDS = {
    "the", "and", "corridor", "line", "main", "route", "section", "sec",
    "via", "junction", "division",
}

# Department words a controller might type -> normalized department key.
_DEPT_ALIASES = {
    "engineering": {"engineering", "eng"},
    "snt": {"snt", "signal", "signalling", "telecom"},
    "trd": {"trd", "traction", "ohe"},
}


def _tokens(text: str) -> set[str]:
    """Lowercase alphabetic words (3+ letters) without filler words."""
    return {
        w for w in re.findall(r"[a-z]+", text.lower())
        if len(w) > 2 and w not in _STOP_WORDS
    }


def _name_hit(name: str | None, question_tokens: set[str]) -> bool:
    """True if every meaningful word of `name` appears in the question."""
    if not name:
        return False
    name_tokens = _tokens(name)
    return bool(name_tokens) and name_tokens <= question_tokens


def _dept_key(value: str) -> str:
    """'S&T' / 'SNT' -> 'snt', 'Engineering' -> 'engineering'."""
    return re.sub(r"[^a-z]", "", value.lower().replace("&", "n"))


class NLQueryEngine(GeminiMixin):
    """Natural language query interface over plans."""

    def __init__(
        self,
        plan: BlockPlan,
        tasks: list[MaintenanceTask],
        corridors: list[Corridor],
        use_llm: bool = True,
    ):
        self.plan = plan
        self.tasks = tasks
        self.corridors = corridors
        self._task_map = {t.task_id: t for t in tasks}
        # Case-insensitive lookup so "mt-abc123" finds "MT-abc123".
        self._task_map_ci = {t.task_id.lower(): t for t in tasks}
        self._corridor_map = {c.corridor_id: c for c in corridors}
        self._init_llm(use_llm)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def query(self, question: str) -> str:
        """Answer a question about the plan."""
        if self.use_llm and self._client:
            return self._llm_query(question)
        return self._keyword_fallback(question)

    # ------------------------------------------------------------------ #
    # Question matching (which records does this question talk about?)
    # ------------------------------------------------------------------ #

    def _match_corridor_ids(self, question: str) -> set[str]:
        q = question.lower()
        q_tokens = _tokens(q)
        hits: set[str] = set()
        for c in self.corridors:
            cid = (c.corridor_id or "").lower()
            id_hit = bool(cid) and re.search(rf"\b{re.escape(cid)}\b", q)
            if id_hit or _name_hit(c.name, q_tokens):
                hits.add(c.corridor_id)
        return hits

    def _match_section_ids(self, question: str) -> set[str]:
        q = question.lower()
        q_tokens = _tokens(q)
        hits: set[str] = set()
        seen: set[str] = set()
        for b in self.plan.scheduled_blocks:
            if b.section_id in seen:
                continue
            seen.add(b.section_id)
            sid = (b.section_id or "").lower()
            id_hit = bool(sid) and re.search(rf"\b{re.escape(sid)}\b", q)
            if id_hit or _name_hit(b.section_name, q_tokens):
                hits.add(b.section_id)
        return hits

    def _mentioned_tasks(
        self, question: str
    ) -> tuple[list[MaintenanceTask], list[str]]:
        """Task IDs typed in the question -> (found tasks, IDs not in dataset)."""
        found: list[MaintenanceTask] = []
        missing: list[str] = []
        for raw in dict.fromkeys(m.lower() for m in _TASK_ID_RE.findall(question)):
            task = self._task_map_ci.get(raw)
            if task:
                found.append(task)
            else:
                missing.append(raw)
        return found, missing

    def _mentioned_dept_keys(self, question: str) -> set[str]:
        words = set(re.findall(r"[a-z]+", question.lower().replace("s&t", "snt")))
        return {key for key, aliases in _DEPT_ALIASES.items() if words & aliases}

    def _select_blocks(
        self, question: str
    ) -> tuple[list[ScheduledBlock], list[str]]:
        """
        Blocks that match everything the question names.
        Returns (blocks, filter descriptions). No descriptions = no filter hit.
        """
        blocks = list(self.plan.scheduled_blocks)
        described: list[str] = []

        corridor_ids = self._match_corridor_ids(question)
        if corridor_ids:
            blocks = [b for b in blocks if b.corridor_id in corridor_ids]
            names = [
                (self._corridor_map[cid].name if cid in self._corridor_map else cid)
                for cid in sorted(corridor_ids)
            ]
            described.append("corridor " + ", ".join(names))

        section_ids = self._match_section_ids(question)
        if section_ids:
            blocks = [b for b in blocks if b.section_id in section_ids]
            described.append("section " + ", ".join(sorted(section_ids)))

        found_tasks, _ = self._mentioned_tasks(question)
        if found_tasks:
            ids = {t.task_id for t in found_tasks}
            blocks = [b for b in blocks if ids & set(b.task_ids)]
            described.append("task " + ", ".join(sorted(ids)))

        dept_keys = self._mentioned_dept_keys(question)
        if dept_keys:
            def has_dept(b: ScheduledBlock) -> bool:
                return any(_dept_key(d.value) in dept_keys for d in b.departments)

            # Only filter if department names really match this plan's data;
            # otherwise a spelling mismatch would wrongly empty the list.
            if any(has_dept(b) for b in self.plan.scheduled_blocks):
                blocks = [b for b in blocks if has_dept(b)]
                described.append("department " + ", ".join(sorted(dept_keys)))

        return blocks, described

    # ------------------------------------------------------------------ #
    # Small formatting helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _severity(task: MaintenanceTask) -> str:
        sev = task.ml_predicted_severity or task.raw_severity or "—"
        return sev.value if hasattr(sev, "value") else str(sev)

    def _block_lines(self, b: ScheduledBlock) -> list[str]:
        section_name = b.section_name or b.section_id
        corridor = self._corridor_map.get(b.corridor_id)
        corridor_name = corridor.name if corridor else b.corridor_id
        depts = ", ".join(d.value for d in b.departments)
        merged_tag = " [MERGED]" if b.is_merged else ""
        lines = [
            f"  {b.block_id}: {corridor_name} / {section_name} on {b.date} "
            f"{b.start_time}-{b.end_time} | {depts}{merged_tag} | "
            f"{len(b.task_ids)} tasks | impact: {b.trains_affected} trains"
        ]
        if b.justification:
            lines.append(f"    Reason: {b.justification}")
        return lines

    def _task_detail_lines(self, task: MaintenanceTask) -> list[str]:
        lines = [
            f"  {task.task_id}: {task.defect_category.value} on "
            f"{task.asset_type.value} | {task.department.value} | "
            f"section {task.section_id}",
            f"    status {task.status.value} | severity {self._severity(task)} | "
            f"criticality {task.ml_criticality_score:.0f}/100 | "
            f"deferred {task.deferred_count}x | {task.days_overdue} days overdue",
        ]
        block = next(
            (b for b in self.plan.scheduled_blocks if task.task_id in b.task_ids),
            None,
        )
        if block:
            lines.append(
                f"    scheduled in {block.block_id} on {block.date} "
                f"{block.start_time}-{block.end_time} at "
                f"{block.section_name or block.section_id}"
            )
            if block.justification:
                lines.append(f"    block reason: {block.justification}")
        return lines

    # ------------------------------------------------------------------ #
    # LLM-powered query
    # ------------------------------------------------------------------ #

    def _build_context(self, question: str = "") -> str:
        """Serialize the plan data that matters for this question."""
        plan = self.plan
        total_blocks = len(plan.scheduled_blocks)

        lines = [
            f"TODAY: {date.today().isoformat()}",
            f"PLAN ID: {plan.plan_id}",
            f"PERIOD: {plan.start_date} to {plan.end_date}",
            f"HORIZON: {plan.horizon.value}",
            f"TOTAL BLOCKS: {total_blocks}",
            f"TASKS SCHEDULED: {plan.total_tasks_scheduled}",
            f"TASKS DEFERRED: {plan.total_tasks_deferred}",
            f"BLOCK HOURS: {plan.total_block_hours:.1f}",
            f"MERGE SAVINGS: {plan.total_merge_savings_hours:.1f}h",
            f"TRAINS AFFECTED: {plan.total_trains_affected}",
            f"SLA COMPLIANCE: {plan.sla_compliance_pct:.1f}%",
            "",
            "DEPARTMENT SUMMARY:",
        ]
        for dept, cnt in sorted(plan.departments_summary.items()):
            lines.append(f"  {dept}: {cnt} tasks")

        # Counts for ALL blocks, so "which corridor has the most blocks" works.
        counts = Counter(b.corridor_id for b in plan.scheduled_blocks)
        lines.append("\nBLOCKS PER CORRIDOR (all blocks in the plan):")
        for cid, n in counts.most_common():
            corridor = self._corridor_map.get(cid)
            lines.append(f"  {corridor.name if corridor else cid} ({cid}): {n} blocks")

        # Blocks that match the question
        blocks, described = self._select_blocks(question)
        limit = MAX_BLOCKS_FILTERED if described else MAX_BLOCKS_UNFILTERED
        shown = blocks[:limit]
        if described:
            header = (
                f"SCHEDULED BLOCKS matching {' + '.join(described)}: "
                f"{len(blocks)} of {total_blocks} total"
            )
        else:
            header = f"SCHEDULED BLOCKS: showing {len(shown)} of {total_blocks} total"
        if len(blocks) > len(shown):
            header += f" (showing first {len(shown)}, LIST IS PARTIAL)"
        lines.append(f"\n{header}:")
        if not blocks:
            lines.append("  NONE — no scheduled block matches this filter.")
        for b in shown:
            lines.extend(self._block_lines(b))

        # Specific tasks named in the question
        found_tasks, missing_ids = self._mentioned_tasks(question)
        if found_tasks or missing_ids:
            lines.append("\nTASKS NAMED IN THE QUESTION:")
            for task in found_tasks:
                lines.extend(self._task_detail_lines(task))
            for tid in missing_ids:
                lines.append(f"  {tid}: NOT FOUND in the dataset.")

        # Emergency tasks (only when asked)
        q = question.lower()
        if "emergenc" in q:
            emergencies = [
                t for t in self.tasks
                if t.ml_predicted_severity == DefectSeverity.EMERGENCY
                or t.raw_severity == DefectSeverity.EMERGENCY.value
            ]
            lines.append(f"\nEMERGENCY TASKS ({len(emergencies)} total):")
            for t in emergencies[:MAX_TASK_LINES]:
                lines.append(
                    f"  {t.task_id}: {t.defect_category.value} on {t.asset_type.value} "
                    f"| {t.department.value} | section {t.section_id} | "
                    f"status {t.status.value}"
                )
            if len(emergencies) > MAX_TASK_LINES:
                lines.append(f"  ... LIST IS PARTIAL (showing {MAX_TASK_LINES})")

        # Deferred tasks
        deferred_ids = plan.deferred_task_ids or []
        if deferred_ids:
            lines.append(f"\nDEFERRED TASKS ({len(deferred_ids)} total):")
            for tid in deferred_ids[:MAX_TASK_LINES]:
                task = self._task_map.get(tid)
                if task:
                    lines.append(
                        f"  {tid}: {task.defect_category.value} | "
                        f"{task.department.value} | severity {self._severity(task)} | "
                        f"criticality {task.ml_criticality_score:.0f} | "
                        f"deferred {task.deferred_count}x"
                    )
            if len(deferred_ids) > MAX_TASK_LINES:
                lines.append(f"  ... LIST IS PARTIAL (showing {MAX_TASK_LINES})")

        # Escalated tasks
        escalated_ids = plan.escalated_task_ids or []
        if escalated_ids:
            lines.append(f"\nESCALATED TASKS ({len(escalated_ids)} total):")
            for tid in escalated_ids[:MAX_TASK_LINES]:
                task = self._task_map.get(tid)
                if task:
                    lines.append(
                        f"  {tid}: {task.defect_category.value} | "
                        f"{task.days_overdue} days overdue"
                    )
            if len(escalated_ids) > MAX_TASK_LINES:
                lines.append(f"  ... LIST IS PARTIAL (showing {MAX_TASK_LINES})")

        # Corridors
        lines.append("\nCORRIDORS:")
        for c in self.corridors[:30]:
            lines.append(f"  {c.corridor_id}: {c.name} ({c.division})")

        return "\n".join(lines)

    def _llm_query(self, question: str) -> str:
        """Answer with the LLM, using only the records picked for this question."""
        context = self._build_context(question)
        prompt = (
            "You are a railway maintenance planning assistant for Indian Railways. "
            "Answer the user's question based ONLY on the plan data provided below. "
            "If the answer is not in the data, say so. "
            "Be concise and factual. Reference specific task IDs, corridor names, "
            "and dates from the data.\n"
            "Rules:\n"
            "- Do not invent task IDs, dates, or numbers.\n"
            "- If a list says 'NONE', tell the user nothing matches.\n"
            "- If a list says 'LIST IS PARTIAL', say the answer covers only part "
            "of the records and give the total count.\n"
            "- If the data does not state the reason for a decision, do not make "
            "one up. Say the reason is not recorded.\n\n"
            f"PLAN DATA:\n{context}\n\n"
            f"USER QUESTION: {question}"
        )
        result = self._llm_generate(prompt)
        if result:
            return result
        return (
            "[AI answer unavailable, showing basic lookup]\n\n"
            f"{self._keyword_fallback(question)}"
        )

    # ------------------------------------------------------------------ #
    # Keyword/regex fallback
    # ------------------------------------------------------------------ #

    def _fallback_task_answer(self, task: MaintenanceTask) -> str:
        status_info = f"Status: {task.status.value}"
        if task.status == TaskStatus.DEFERRED:
            status_info += (
                f" (deferred {task.deferred_count} times). "
                f"Likely reason: lower criticality score "
                f"({task.ml_criticality_score:.0f}/100) relative to "
                f"available block windows."
            )
        elif task.status == TaskStatus.SCHEDULED:
            block = next(
                (b for b in self.plan.scheduled_blocks if task.task_id in b.task_ids),
                None,
            )
            if block:
                status_info += (
                    f". Scheduled in block {block.block_id} on {block.date} "
                    f"{block.start_time}-{block.end_time} "
                    f"at {block.section_name or block.section_id}."
                )
        return (
            f"Task {task.task_id}: {task.defect_category.value} on "
            f"{task.asset_type.value}\n"
            f"Department: {task.department.value}\n"
            f"Criticality: {task.ml_criticality_score:.0f}/100\n"
            f"{status_info}"
        )

    def _keyword_fallback(self, question: str) -> str:
        """Parse question for keywords and look up answers from plan data."""
        q = question.lower().strip()

        # Specific task query. Checked FIRST: a question like
        # "why was MT-xxxx deferred?" also contains "defer" and used to be
        # swallowed by the generic deferred-list branch below.
        found_tasks, missing_ids = self._mentioned_tasks(question)
        if found_tasks or missing_ids:
            parts = [self._fallback_task_answer(t) for t in found_tasks]
            parts += [f"Task {tid} not found in the current dataset." for tid in missing_ids]
            return "\n\n".join(parts)

        # SLA compliance
        if "sla" in q or "compliance" in q:
            return (
                f"SLA Compliance: {self.plan.sla_compliance_pct:.1f}%. "
                f"{self.plan.total_tasks_scheduled} tasks scheduled, "
                f"{self.plan.total_tasks_deferred} deferred."
            )

        # Emergency tasks
        if "emergency" in q or "emergencies" in q:
            emergencies = [
                t for t in self.tasks
                if t.ml_predicted_severity == DefectSeverity.EMERGENCY
                or t.raw_severity == DefectSeverity.EMERGENCY.value
            ]
            if emergencies:
                details = "\n".join(
                    f"  • {t.task_id}: {t.defect_category.value} on "
                    f"{t.asset_type.value} — status {t.status.value}"
                    for t in emergencies[:10]
                )
                return f"Found {len(emergencies)} emergency task(s):\n{details}"
            return "No emergency tasks found."

        # Merged blocks
        if "merge" in q or "merged" in q:
            merged = [b for b in self.plan.scheduled_blocks if b.is_merged]
            if merged:
                details = "\n".join(
                    f"  • {b.block_id}: {b.section_name or b.section_id} on {b.date} "
                    f"— {', '.join(d.value for d in b.departments)} "
                    f"(saved {b.merge_savings_hours:.1f}h)"
                    for b in merged[:10]
                )
                return (
                    f"{len(merged)} merged block(s), saving "
                    f"{self.plan.total_merge_savings_hours:.1f} hours total:\n{details}"
                )
            return "No merged blocks in this plan."

        # Deferred tasks
        if "defer" in q:
            if self.plan.deferred_task_ids:
                details = []
                for tid in self.plan.deferred_task_ids[:10]:
                    task = self._task_map.get(tid)
                    if task:
                        details.append(
                            f"  • {tid}: {task.defect_category.value} "
                            f"(severity {self._severity(task)}, "
                            f"criticality {task.ml_criticality_score:.0f})"
                        )
                return (
                    f"{len(self.plan.deferred_task_ids)} deferred task(s):\n"
                    + "\n".join(details)
                )
            return "No tasks were deferred in this plan."

        # Department queries
        dept_match = re.search(
            r"(engineering|snt|s&t|signal|trd|traction)", q
        )
        if dept_match or "department" in q:
            if self.plan.departments_summary:
                breakdown = ", ".join(
                    f"{d}: {c} tasks" for d, c in sorted(self.plan.departments_summary.items())
                )
                return f"Department breakdown: {breakdown}"
            return "No department data available."

        # Corridor/section queries
        if "corridor" in q or "section" in q or "block" in q:
            if self._match_corridor_ids(question) or self._match_section_ids(question):
                blocks_on, described = self._select_blocks(question)
                label = " + ".join(described)
                if blocks_on:
                    details = "\n".join(
                        f"  • {b.date} {b.start_time}-{b.end_time}: "
                        f"{b.section_name or b.section_id} "
                        f"({len(b.task_ids)} tasks, "
                        f"{', '.join(d.value for d in b.departments)})"
                        for b in blocks_on
                    )
                    return f"Blocks matching {label}:\n{details}"
                return f"No blocks scheduled matching {label}."

            # Most-blocked corridor
            if "most" in q:
                corridor_counts = Counter(
                    b.corridor_id for b in self.plan.scheduled_blocks
                )
                if corridor_counts:
                    top_id, top_count = corridor_counts.most_common(1)[0]
                    c = self._corridor_map.get(top_id)
                    name = c.name if c else top_id
                    return f"Most-blocked corridor: {name} with {top_count} blocks."

            return (
                f"This plan covers {len(set(b.corridor_id for b in self.plan.scheduled_blocks))} "
                f"corridors with {len(self.plan.scheduled_blocks)} total blocks."
            )

        # Fallback
        return (
            f"I can answer questions about this plan. Try asking about:\n"
            f"• SLA compliance\n"
            f"• Emergency tasks\n"
            f"• Merged blocks and savings\n"
            f"• Deferred tasks\n"
            f"• Department breakdown\n"
            f"• Specific corridors (by name)\n"
            f"• Specific tasks (by ID, e.g. MT-xxxxxxxx)"
        )