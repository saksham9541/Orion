"""
RailOpt — Risk Blender.

Fuses scores from all analysis layers into a single blended
criticality score — analogous to FinCrime's weighted blending:
    blended = ML(40%) + Context(20%) + Compliance(20%) + Behavior(20%)

RailOpt's formula:
    blended = ML(30%) + Context(20%) + Compliance(15%) + Behavior(20%) + Signals(15%)

The blended score replaces ml_criticality_score for downstream use
by the CP-SAT optimizer, giving it a richer, multi-perspective input.

SAFETY FLOOR (fix): a pure weighted average can dilute an EMERGENCY task
down to HIGH or lower if its other four layers score low — e.g. a rail
fracture with no history, no compliance flags, and no behavioral anomalies
blends to ~55-65 even though the ML layer alone said EMERGENCY/95. That
silently erases the solver's emergency-must-schedule constraint and the
24h SLA deferral limit for that task. apply_to_tasks() re-applies the same
ALWAYS_EMERGENCY / SAFETY_CRITICAL_DEFECTS floor used by
CriticalityScorer.predict() and BlockDisruptor._apply_safety_overrides()
after blending, so these categories can never end up under-classified
regardless of what the other layers say.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from railopt.models import (
    DefectSeverity,
    MaintenanceTask,
    ALWAYS_EMERGENCY,
    SAFETY_CRITICAL_DEFECTS,
)


@dataclass
class BlendWeights:
    """Configurable weights for score fusion."""
    ml_score: float = 0.30
    context: float = 0.20
    compliance: float = 0.15
    behavior: float = 0.20
    signals: float = 0.15

    def __post_init__(self):
        total = self.ml_score + self.context + self.compliance + self.behavior + self.signals
        assert abs(total - 1.0) < 0.01, f"Weights must sum to 1.0, got {total}"


@dataclass
class BlendedResult:
    """Result of multi-layer score blending for a single task."""
    task_id: str
    ml_score: float
    context_score: float
    compliance_score: float
    behavior_score: float
    signal_score: float
    blended_score: float
    risk_level: str
    action: str
    layer_contributions: dict[str, float]
    evidence_summary: list[str]


class RiskBlender:
    """
    Fuses multi-layer analysis results into a single blended score.

    Usage:
        blender = RiskBlender()
        results = blender.blend_batch(tasks, contexts, compliances, behaviors, signals)
        for r in results:
            task.ml_criticality_score = r.blended_score  # Override with richer score
    """

    def __init__(self, weights: Optional[BlendWeights] = None):
        self.weights = weights or BlendWeights()

    def blend(
        self,
        task: MaintenanceTask,
        context: dict,
        compliance: dict,
        behavior: dict,
        signals: dict,
    ) -> BlendedResult:
        """Blend all layer scores for a single task."""

        # Normalize all scores to 0-100 range
        ml = task.ml_criticality_score  # Already 0-100
        ctx = context.get("context_risk_score", 0) * 100       # 0-1 → 0-100
        comp = compliance.get("compliance_score", 0)            # Already 0-100
        beh = behavior.get("behavior_score", 0)                 # Already 0-100
        sig = signals.get("signal_score", 0)                    # Already 0-100

        # Weighted blend
        blended = (
            ml * self.weights.ml_score
            + ctx * self.weights.context
            + comp * self.weights.compliance
            + beh * self.weights.behavior
            + sig * self.weights.signals
        )
        blended = round(min(blended, 100.0), 2)

        # Risk level and action
        risk_level = self._risk_level(blended)
        action = self._action(blended)

        # Layer contributions (for explainability)
        contributions = {
            "ml_model": round(ml * self.weights.ml_score, 1),
            "context_engine": round(ctx * self.weights.context, 1),
            "compliance_engine": round(comp * self.weights.compliance, 1),
            "behavioral_analyzer": round(beh * self.weights.behavior, 1),
            "signal_extractor": round(sig * self.weights.signals, 1),
        }

        # Aggregate evidence
        evidence = []
        evidence.extend(context.get("evidence_summary", []))
        evidence.extend(behavior.get("reasons", []))
        evidence.extend(signals.get("triggered_descriptions", []))
        # Add top compliance flags
        for flag_list_key in ["rdso_assessment", "crs_assessment", "irsge_assessment", "rb_assessment"]:
            assessment = compliance.get(flag_list_key, {})
            for flag in assessment.get("flags", [])[:2]:  # Top 2 per framework
                evidence.append(f"[{flag['rule']}] {flag['description']}")

        return BlendedResult(
            task_id=task.task_id,
            ml_score=round(ml, 1),
            context_score=round(ctx, 1),
            compliance_score=round(comp, 1),
            behavior_score=round(beh, 1),
            signal_score=round(sig, 1),
            blended_score=blended,
            risk_level=risk_level,
            action=action,
            layer_contributions=contributions,
            evidence_summary=evidence,
        )

    def blend_batch(
        self,
        tasks: list[MaintenanceTask],
        contexts: list[dict],
        compliances: list[dict],
        behaviors: list[dict],
        signals_list: list[dict],
    ) -> list[BlendedResult]:
        """Blend all tasks in batch."""
        results = []
        for i, task in enumerate(tasks):
            result = self.blend(
                task,
                contexts[i] if i < len(contexts) else {},
                compliances[i] if i < len(compliances) else {},
                behaviors[i] if i < len(behaviors) else {},
                signals_list[i] if i < len(signals_list) else {},
            )
            results.append(result)
        return results

    def apply_to_tasks(
        self, tasks: list[MaintenanceTask], results: list[BlendedResult]
    ) -> None:
        """Apply blended scores back to task objects for optimizer consumption."""
        severity_map = {
            "CRITICAL": DefectSeverity.EMERGENCY,
            "HIGH": DefectSeverity.HIGH,
            "MEDIUM": DefectSeverity.MEDIUM,
            "LOW": DefectSeverity.LOW,
        }
        for task, result in zip(tasks, results):
            # Override ML score with richer blended score
            task.ml_criticality_score = result.blended_score
            # Update severity based on blended risk level
            task.ml_predicted_severity = severity_map.get(
                result.risk_level, task.ml_predicted_severity
            )

            # --- SAFETY FLOOR (fix) ---------------------------------------
            # The weighted average above can drag an ALWAYS_EMERGENCY or
            # SAFETY_CRITICAL defect down to MEDIUM/HIGH if its other layers
            # (context, compliance, behavior, signals) score low. That would
            # silently disable the solver's emergency-must-schedule
            # constraint and the 24h SLA deferral limit for that task. Never
            # let blending lower these categories below their safety floor —
            # it may only ever raise a score/severity, never suppress one.
            if task.defect_category in ALWAYS_EMERGENCY:
                task.ml_predicted_severity = DefectSeverity.EMERGENCY
                task.ml_criticality_score = max(task.ml_criticality_score, 95.0)
            elif task.defect_category in SAFETY_CRITICAL_DEFECTS:
                task.ml_criticality_score = max(task.ml_criticality_score, 70.0)
                if task.ml_predicted_severity in (DefectSeverity.MEDIUM, DefectSeverity.LOW):
                    task.ml_predicted_severity = DefectSeverity.HIGH

    @staticmethod
    def _risk_level(score: float) -> str:
        if score >= 75:
            return "CRITICAL"
        elif score >= 50:
            return "HIGH"
        elif score >= 30:
            return "MEDIUM"
        return "LOW"

    @staticmethod
    def _action(score: float) -> str:
        if score >= 80:
            return "SCHEDULE_IMMEDIATELY"
        elif score >= 60:
            return "SCHEDULE_THIS_WEEK"
        elif score >= 40:
            return "SCHEDULE_THIS_FORTNIGHT"
        return "CAN_DEFER"