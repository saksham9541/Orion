"""
CP-SAT based optimizer for maintenance block scheduling.

Model size note: a decision variable x[i, j] is only created when task i can
actually use window j (same section AND the task fits inside the window).
The old version created a variable for every task x window pair (500 x 260 =
130,000) and then forced ~97% of them to 0, which slowed the solver a lot.
With only the valid pairs the model is roughly 30x smaller, so the solver can
finish and prove the answer is optimal instead of stopping at "FEASIBLE".
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
import logging
from typing import Any, Dict, List, Optional, Set, Tuple

from ortools.sat.python import cp_model

logger = logging.getLogger(__name__)

from optimizer.block_merger import BlockMerger
from railopt.models import (
    BlockPlan,
    BlockWindow,
    DefectSeverity,
    Department,
    MaintenanceTask,
    PlanHorizon,
    ScheduledBlock,
    Section,
    TaskStatus,
)


def _dur(t: MaintenanceTask) -> float:
    """Planned duration: the ML estimate if there is one (> 0), else the manual estimate."""
    return t.ml_predicted_duration_hours if t.ml_predicted_duration_hours else t.estimated_duration_hours


def _window_interval(w: BlockWindow) -> tuple[datetime, datetime]:
    """Return start and end datetimes for a window, accounting for midnight crossovers."""
    s = datetime.combine(w.date, w.start_time)
    e = datetime.combine(w.date, w.end_time)
    if e < s:
        e += timedelta(days=1)
    return s, e


def _windows_conflict(w1: BlockWindow, w2: BlockWindow) -> bool:
    """
    Check if two windows conflict on track resources.
    Windows conflict only if they share the same section AND:
    - If block_section_ids are defined on both:
      they conflict only if block_section_id is the same AND lines overlap (l1 == l2 or 'BOTH' in (l1, l2)).
    - If either has no block_section_id:
      they conflict if sections match (legacy full-section block).
    """
    if w1.section_id != w2.section_id:
        return False

    b1 = getattr(w1, "block_section_id", None)
    b2 = getattr(w2, "block_section_id", None)
    if b1 and b2:
        if b1 != b2:
            return False
        l1 = (getattr(w1, "line", None) or "BOTH").upper()
        l2 = (getattr(w2, "line", None) or "BOTH").upper()
        return l1 == "BOTH" or l2 == "BOTH" or l1 == l2

    return True


def _is_task_compat(t: MaintenanceTask, w: BlockWindow) -> bool:
    """Check if task t can physically be scheduled in window w."""
    if t.section_id != w.section_id:
        return False
    if _dur(t) > w.duration_hours:
        return False
    # If window has a block_section_id and task has a block_section_id, they must match
    b_task = getattr(t, "block_section_id", None)
    b_win = getattr(w, "block_section_id", None)
    if b_win and b_task:
        if b_win != b_task:
            return False

    # Line compatibility
    w_line = (getattr(w, "line", None) or "BOTH").upper()
    t_line = (getattr(t, "line", None) or "DN").upper()
    req_both = getattr(t, "requires_both_lines", False) or t_line == "BOTH"
    if req_both:
        if w_line != "BOTH":
            return False
    elif w_line != "BOTH":
        if t_line != w_line:
            return False
    return True


@dataclass
class SchedulerConfig:
    """Weights and constraints configuration for the optimizer.

    Scoring weights note:
        The solver maximizes criticality reward using `-(beta + delta) * crit` in the
        minimization objective. `delta` is kept for backward compatibility; effective
        criticality reward weight is `beta + delta`. Default scoring results are unchanged.

    Unenforced constraints note:
        `max_block_hours_per_corridor_per_week` is currently not enforced to prevent
        infeasibility across multi-section corridors.
    """
    alpha: int = 10  # minimize traffic disruption
    beta: int = 100  # reward scheduling critical tasks
    gamma: int = 50  # reward multi-dept merging
    delta: int = 200  # extra reward for scheduling critical tasks (effective criticality weight = beta + delta; kept for backward compatibility)
    emergency_penalty: int = 1000  # heavy penalty for unscheduled emergencies (soft constraint)
    max_tasks_per_dept_per_day: int = 10
    max_block_hours_per_corridor_per_week: float = 40.0  # NOTE: not enforced (see docstring and README)
    emergency_must_schedule: bool = True
    time_limit_seconds: int = 60


class BlockScheduler:
    """Core optimizer using Google OR-Tools CP-SAT solver."""

    def __init__(self, config: SchedulerConfig = None):
        self.config = config or SchedulerConfig()

    def solve(
        self,
        tasks: list[MaintenanceTask],
        windows: list[BlockWindow],
        sections: dict[str, Section],
        time_limit_seconds: int | None = None,
        horizon: PlanHorizon = PlanHorizon.WEEKLY,
        forbidden_assignments: Optional[set[tuple[str, str]]] = None,
    ) -> BlockPlan:
        """
        Assigns tasks to block windows maximizing scheduling of critical tasks
        and inter-department merging, while minimizing disruption.
        Supports forbidden_assignments: set of (task_id, window_id) to exclude.
        """
        cfg = self.config
        time_limit = time_limit_seconds if time_limit_seconds is not None else cfg.time_limit_seconds

        SCALE = 10  # CP-SAT needs integers: keep 1 decimal
        num_tasks, num_windows = len(tasks), len(windows)

        # ---- which (task, window) pairs are possible at all -----------------
        windows_by_section = defaultdict(list)
        for j, w in enumerate(windows):
            windows_by_section[w.section_id].append(j)

        compat: Dict[int, list[int]] = {}
        for i, t in enumerate(tasks):
            compat[i] = [j for j in windows_by_section.get(t.section_id, []) if _is_task_compat(t, windows[j])]

        no_compat_emergencies = []
        emerg_with_compat = []
        for i, t in enumerate(tasks):
            is_emergency = (
                getattr(t, "raw_severity", None) in (DefectSeverity.EMERGENCY, DefectSeverity.EMERGENCY.value, "EMERGENCY")
                or getattr(t, "ml_predicted_severity", None) in (DefectSeverity.EMERGENCY, DefectSeverity.EMERGENCY.value, "EMERGENCY")
            )
            if is_emergency:
                if not compat[i]:
                    logger.warning(
                        "Emergency task %s on section %s has no compatible block window",
                        t.task_id,
                        t.section_id,
                    )
                    no_compat_emergencies.append(t)
                else:
                    emerg_with_compat.append(i)

        def _build_model(hard_emergency: bool):
            model = cp_model.CpModel()
            x = {}
            tasks_in_window = defaultdict(list)
            for i, js in compat.items():
                for j in js:
                    x[i, j] = model.NewBoolVar(f"x_t{i}_w{j}")
                    tasks_in_window[j].append(i)

            # ---- merge tracking --------------------------------------------------
            dept_present = {}
            is_merged = {}
            for j in range(num_windows):
                for d in Department:
                    v = model.NewBoolVar(f"dept_{d.value}_w{j}")
                    dept_present[j, d] = v
                    in_j = [x[i, j] for i in tasks_in_window[j] if tasks[i].department == d]
                    if in_j:
                        model.AddMaxEquality(v, in_j)
                    else:
                        model.Add(v == 0)
                is_merged[j] = model.NewBoolVar(f"merged_w{j}")
                # merged only if at least 2 departments are present
                model.Add(2 * is_merged[j] <= sum(dept_present[j, d] for d in Department))

            # ---- constraints -----------------------------------------------------
            # 1. each task in at most one window
            for i in range(num_tasks):
                if compat[i]:
                    model.Add(sum(x[i, j] for j in compat[i]) <= 1)

            # 4 + 5. window capacity (number of tasks and total duration)
            for j, w in enumerate(windows):
                ids = tasks_in_window[j]
                if not ids:
                    continue
                model.Add(sum(x[i, j] for i in ids) <= w.max_tasks)
                model.Add(
                    sum(x[i, j] * int(_dur(tasks[i]) * SCALE) for i in ids)
                    <= int(w.duration_hours * SCALE)
                )

            # 6. emergency tasks
            emergency_not_scheduled = {}
            if cfg.emergency_must_schedule:
                if hard_emergency:
                    for i in emerg_with_compat:
                        model.Add(sum(x[i, j] for j in compat[i]) >= 1)
                else:
                    for i in emerg_with_compat:
                        not_sched = model.NewBoolVar(f"emerg_not_sched_{i}")
                        scheduled_sum = sum(x[i, j] for j in compat[i])
                        model.Add(scheduled_sum >= 1).OnlyEnforceIf(not_sched.Not())
                        model.Add(scheduled_sum == 0).OnlyEnforceIf(not_sched)
                        emergency_not_scheduled[i] = not_sched

            # 7. crew limit: max tasks per department per day
            windows_by_date = defaultdict(list)
            for j, w in enumerate(windows):
                windows_by_date[w.date].append(j)
            for js in windows_by_date.values():
                for d in Department:
                    terms = [x[i, j] for j in js for i in tasks_in_window[j] if tasks[i].department == d]
                    if terms:
                        model.Add(sum(terms) <= cfg.max_tasks_per_dept_per_day)

            # 8. section conflict: overlapping windows on the same section cannot both be scheduled
            window_used = {}
            for j in range(num_windows):
                ids = tasks_in_window[j]
                if ids:
                    v = model.NewBoolVar(f"window_used_{j}")
                    model.AddMaxEquality(v, [x[i, j] for i in ids])
                    window_used[j] = v

            for sec_id, sec_windows in windows_by_section.items():
                for idx_a, j1 in enumerate(sec_windows):
                    if j1 not in window_used:
                        continue
                    s1, e1 = _window_interval(windows[j1])
                    for j2 in sec_windows[idx_a + 1:]:
                        if j2 not in window_used:
                            continue
                        if not _windows_conflict(windows[j1], windows[j2]):
                            continue
                        s2, e2 = _window_interval(windows[j2])
                        if max(s1, s2) < min(e1, e2):  # overlapping intervals
                            model.Add(window_used[j1] + window_used[j2] <= 1)

            # 9. Forbidden assignments (e.g. from department rejections)
            if forbidden_assignments:
                for (i, j), var in x.items():
                    if (tasks[i].task_id, windows[j].window_id) in forbidden_assignments:
                        model.Add(var == 0)

            # 10. Locked tasks: tasks with approved or in-progress status/assigned window are fixed constraints
            for i, t in enumerate(tasks):
                is_locked = (
                    t.status in (TaskStatus.APPROVED, TaskStatus.IN_PROGRESS)
                    or getattr(t, "status", None) in ("APPROVED", "IN_PROGRESS")
                )
                if is_locked and compat[i]:
                    if t.assigned_block_id:
                        matching_j = [j for j in compat[i] if windows[j].window_id == t.assigned_block_id]
                        if matching_j:
                            model.Add(x[i, matching_j[0]] == 1)
                        else:
                            model.Add(sum(x[i, j] for j in compat[i]) == 1)
                    else:
                        model.Add(sum(x[i, j] for j in compat[i]) == 1)

            # ---- objective (minimize) -------------------------------------------
            obj = []
            for (i, j), var in x.items():
                impact = int(windows[j].ml_traffic_impact_score * SCALE)
                crit = int(tasks[i].ml_criticality_score * SCALE)
                # + traffic disruption, - reward for scheduling a critical task
                obj.append(var * (cfg.alpha * impact - (cfg.beta + cfg.delta) * crit))

            avg_crit = sum(int(t.ml_criticality_score * SCALE) for t in tasks) // max(num_tasks, 1)
            for j in range(num_windows):
                obj.append(is_merged[j] * (-cfg.gamma * avg_crit))  # merge incentive

            if emergency_not_scheduled:
                total_max_reward = sum(
                    max(0, (cfg.beta + cfg.delta) * int(getattr(t, "ml_criticality_score", 1.0) * SCALE))
                    for t in tasks
                ) + cfg.gamma * SCALE * max(num_windows, 1)
                penalty = max(cfg.emergency_penalty * SCALE, total_max_reward + 10000)
                for i, not_sched in emergency_not_scheduled.items():
                    obj.append(not_sched * penalty)

            model.Minimize(sum(obj))
            return model, x, tasks_in_window

        # ---- solve -----------------------------------------------------------
        fell_back_to_soft = False
        if cfg.emergency_must_schedule and emerg_with_compat:
            model, x, tasks_in_window = _build_model(hard_emergency=True)
            solver = cp_model.CpSolver()
            solver.parameters.max_time_in_seconds = float(time_limit)
            status = solver.Solve(model)
            if status == cp_model.INFEASIBLE:
                fell_back_to_soft = True
                logger.warning(
                    "Emergency task hard constraints resulted in INFEASIBLE model; falling back to soft penalty."
                )
                model, x, tasks_in_window = _build_model(hard_emergency=False)
                solver = cp_model.CpSolver()
                solver.parameters.max_time_in_seconds = float(time_limit)
                status = solver.Solve(model)
        else:
            model, x, tasks_in_window = _build_model(hard_emergency=False)
            solver = cp_model.CpSolver()
            solver.parameters.max_time_in_seconds = float(time_limit)
            status = solver.Solve(model)

        solver_status_name = solver.StatusName(status)
        solve_time_ms = round(solver.WallTime() * 1000, 1)

        # ---- build output ----------------------------------------------------
        plan = BlockPlan(
            horizon=horizon,
            start_date=min(w.date for w in windows) if windows else date.today(),
            end_date=max(w.date for w in windows) if windows else date.today(),
        )
        plan.solver_status = solver_status_name
        plan.solve_time_ms = solve_time_ms

        if fell_back_to_soft:
            plan.warnings.append(
                "Emergency tasks could not all be scheduled as hard constraints (model infeasible); fell back to soft penalty."
            )

        for t in no_compat_emergencies:
            plan.warnings.append(
                f"Emergency task {t.task_id} on section {t.section_id} has no compatible window and was deferred."
            )
            if t.task_id not in plan.escalated_task_ids:
                plan.escalated_task_ids.append(t.task_id)

        scheduled_blocks = {}
        scheduled_task_ids = set()

        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            for j, w in enumerate(windows):
                assigned = [tasks[i] for i in tasks_in_window[j] if solver.Value(x[i, j]) == 1]
                if not assigned:
                    continue
                section = sections.get(w.section_id)
                block = ScheduledBlock(
                    window_id=w.window_id,
                    corridor_id=w.corridor_id,
                    section_id=w.section_id,
                    section_name=section.name if section else "",
                    block_section_id=getattr(w, "block_section_id", None),
                    line=getattr(w, "line", None),
                    date=w.date,
                    start_time=w.start_time,
                    end_time=w.end_time,
                    duration_hours=w.duration_hours,
                    block_type=w.block_type,
                    task_ids=[t.task_id for t in assigned],
                    departments=list({t.department for t in assigned}),
                    is_merged=False,
                    merge_savings_hours=0.0,
                    trains_affected=w.ml_trains_affected,
                    cumulative_delay_minutes=w.ml_cumulative_delay_minutes,
                    total_criticality_score=sum(t.ml_criticality_score for t in assigned),
                )
                for t in assigned:
                    t.status = TaskStatus.SCHEDULED
                    t.assigned_block_id = block.block_id
                    scheduled_task_ids.add(t.task_id)
                scheduled_blocks[block.block_id] = block
            plan.scheduled_blocks = list(scheduled_blocks.values())

        plan.deferred_task_ids = [t.task_id for t in tasks if t.task_id not in scheduled_task_ids]
        for t in tasks:
            if t.task_id not in scheduled_task_ids:
                t.status = TaskStatus.DEFERRED
                t.deferred_count += 1

        plan.compute_metrics(tasks)

        for block in plan.scheduled_blocks:
            depts = [d.value for d in block.departments]
            block.justification = (
                f"Assigned {len(block.task_ids)} tasks across {len(depts)} departments "
                f"({', '.join(depts)}) to optimize utilization of {block.duration_hours}h block."
            )

        BlockMerger().analyze_merge_opportunities(plan, tasks)
        return plan