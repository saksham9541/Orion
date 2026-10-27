"""
CP-SAT based optimizer for maintenance block scheduling.

Model size note: a decision variable x[i, j] is only created when task i can
actually use window j (same section AND the task fits inside the window).
The old version created a variable for every task x window pair (500 x 260 =
130,000) and then forced ~97% of them to 0, which slowed the solver a lot.
With only the valid pairs the model is roughly 30x smaller, so the solver can
finish and prove the answer is optimal instead of stopping at "FEASIBLE".
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Dict

from ortools.sat.python import cp_model

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


@dataclass
class SchedulerConfig:
    """Weights and constraints configuration for the optimizer."""
    alpha: int = 10  # minimize traffic disruption
    beta: int = 100  # reward scheduling critical tasks
    gamma: int = 50  # reward multi-dept merging
    delta: int = 200  # extra reward for scheduling critical tasks (same effect as beta)
    emergency_penalty: int = 1000  # heavy penalty for unscheduled emergencies (soft constraint)
    max_tasks_per_dept_per_day: int = 10
    max_block_hours_per_corridor_per_week: float = 40.0  # NOTE: not enforced yet
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
    ) -> BlockPlan:
        """
        Assigns tasks to block windows maximizing scheduling of critical tasks
        and inter-department merging, while minimizing disruption.
        """
        cfg = self.config
        if time_limit_seconds is not None:  # only override the config if the caller asks
            cfg.time_limit_seconds = time_limit_seconds

        model = cp_model.CpModel()
        SCALE = 10  # CP-SAT needs integers: keep 1 decimal
        num_tasks, num_windows = len(tasks), len(windows)

        # ---- which (task, window) pairs are possible at all -----------------
        windows_by_section = defaultdict(list)
        for j, w in enumerate(windows):
            windows_by_section[w.section_id].append(j)

        compat: Dict[int, list[int]] = {}
        for i, t in enumerate(tasks):
            d = _dur(t)
            compat[i] = [j for j in windows_by_section.get(t.section_id, []) if d <= windows[j].duration_hours]

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

        # 6. emergency tasks: soft constraint with a heavy penalty
        emergency_not_scheduled = {}
        if cfg.emergency_must_schedule:
            for i, t in enumerate(tasks):
                is_emergency = (
                    t.raw_severity == DefectSeverity.EMERGENCY.value
                    or t.ml_predicted_severity == DefectSeverity.EMERGENCY
                )
                if is_emergency and compat[i]:
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

        for i, not_sched in emergency_not_scheduled.items():
            obj.append(not_sched * (cfg.emergency_penalty * SCALE))

        model.Minimize(sum(obj))

        # ---- solve -----------------------------------------------------------
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = float(cfg.time_limit_seconds)
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