"""
SLA and escalation enforcement module.
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Dict
from datetime import datetime

from railopt.models import (
    MaintenanceTask,
    BlockPlan,
    TaskStatus,
    MAX_DEFERRAL_HOURS,
    SAFETY_CRITICAL_DEFECTS,
    DefectSeverity,
    BlockWindow
)

@dataclass
class SLAReport:
    """Report on SLA compliance and escalations."""
    compliance_percentage: float = 100.0
    total_critical_tasks: int = 0
    scheduled_critical_tasks: int = 0
    breaching_tasks: List[str] = field(default_factory=list)
    escalation_alerts: List[str] = field(default_factory=list)


class SLAEngine:
    """Enforces safety SLAs and escalates overdue maintenance tasks."""

    def apply_sla(self, tasks: List[MaintenanceTask]) -> List[MaintenanceTask]:
        """
        Convenience entry point used at task-ingestion time (see main.py
        /api/tasks/import): runs overdue-escalation on freshly imported/scored
        tasks so newly ingested records immediately reflect SLA status
        rather than waiting for the next scheduled escalation pass.

        Returns the list of tasks that were escalated (subset of `tasks`).
        """
        return self.escalate_overdue(tasks)

    def check_compliance(
        self, tasks: List[MaintenanceTask], plan: BlockPlan
    ) -> SLAReport:
        """
        Evaluate a plan against safety compliance targets.
        """
        report = SLAReport()
        
        # All tasks that are safety critical
        critical_tasks = [t for t in tasks if t.is_safety_critical]
        report.total_critical_tasks = len(critical_tasks)
        
        scheduled_critical = [t for t in critical_tasks if t.status == TaskStatus.SCHEDULED]
        report.scheduled_critical_tasks = len(scheduled_critical)
        
        if report.total_critical_tasks > 0:
            report.compliance_percentage = round(
                (report.scheduled_critical_tasks / report.total_critical_tasks) * 100, 1
            )
            
        # Check for deferral breaches
        for t in tasks:
            if t.status in (TaskStatus.PENDING, TaskStatus.DEFERRED):
                severity = t.ml_predicted_severity or DefectSeverity.MEDIUM
                # Fallback to a default if severity not recognized
                max_hours = MAX_DEFERRAL_HOURS.get(severity, MAX_DEFERRAL_HOURS[DefectSeverity.LOW])
                
                # Check if days_overdue translated to hours exceeds limit
                overdue_hours = t.days_overdue * 24
                
                if overdue_hours > max_hours:
                    report.breaching_tasks.append(t.task_id)
                    report.escalation_alerts.append(
                        f"ALERT: Task {t.task_id} ({t.defect_category.value}) breached SLA limit "
                        f"of {max_hours}h (Current: {overdue_hours}h). Severity: {severity.value}."
                    )
                    
        return report

    def escalate_overdue(self, tasks: List[MaintenanceTask]) -> List[MaintenanceTask]:
        """
        Marks tasks that breach MAX_DEFERRAL_HOURS as ESCALATED.
        Returns the list of modified tasks.
        """
        escalated_tasks = []
        for t in tasks:
            if t.status in (TaskStatus.PENDING, TaskStatus.DEFERRED):
                severity = t.ml_predicted_severity or DefectSeverity.MEDIUM
                    
                max_hours = MAX_DEFERRAL_HOURS.get(severity, MAX_DEFERRAL_HOURS[DefectSeverity.LOW])
                overdue_hours = t.days_overdue * 24
                
                if overdue_hours > max_hours:
                    t.status = TaskStatus.ESCALATED
                    escalated_tasks.append(t)
                    
        return escalated_tasks

    def force_schedule_emergency(
        self, tasks: List[MaintenanceTask], windows: List[BlockWindow]
    ) -> List[Tuple[str, str]]:
        """
        Identify emergency tasks that must be forced into windows.
        Returns a list of (task_id, window_id) tuples.
        """
        forced_assignments = []
        
        emergency_tasks = [
            t for t in tasks 
            if t.raw_severity == DefectSeverity.EMERGENCY.value 
            or t.ml_predicted_severity == DefectSeverity.EMERGENCY
            or t.defect_category in SAFETY_CRITICAL_DEFECTS
        ]
        
        # Very simplistic greedy fallback for emergencies
        for t in emergency_tasks:
            for w in windows:
                duration = t.ml_predicted_duration_hours if t.ml_predicted_duration_hours is not None else t.estimated_duration_hours
                if duration <= w.duration_hours and t.section_id == w.section_id:
                    forced_assignments.append((t.task_id, w.window_id))
                    break  # Assign to first matching window
                    
        return forced_assignments