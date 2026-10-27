"""
RailOpt — Shared Risk Component helpers.

Provides:
  1. RiskAccumulator — generic accumulator for the repeated pattern of
     "add to a running score, collect human-readable reason strings,
     then cap the total at a configurable maximum".
  2. Config dataclasses for each engine's magic numbers:
     - ContextEngineConfig
     - ComplianceEngineConfig
     - BehavioralConfig
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ── Generic Risk Accumulator ────────────────────────────────────────────────

class RiskAccumulator:
    """Accumulates a numeric risk/score value up to a configurable cap.

    Usage::

        acc = RiskAccumulator(cap=0.35)
        acc.add(0.15, "Recurring defect pattern")
        acc.add(0.10, "Accelerating trend")
        print(acc.score)    # 0.25  (would be capped at 0.35)
        print(acc.reasons)  # ["Recurring defect pattern", "Accelerating trend"]

    The *reason* argument is optional — when ``None`` or omitted, the score
    is bumped but no reason string is recorded.
    """

    __slots__ = ("_score", "_cap", "_reasons")

    def __init__(self, cap: float) -> None:
        self._score: float = 0.0
        self._cap: float = cap
        self._reasons: list[str] = []

    # -- mutators ----------------------------------------------------------

    def add(self, value: float, reason: Optional[str] = None) -> None:
        """Add *value* to the running score and optionally record a reason."""
        self._score += value
        if reason is not None:
            self._reasons.append(reason)

    def add_capped(self, value: float, item_cap: float,
                   reason: Optional[str] = None) -> None:
        """Like :meth:`add`, but clamp the individual *value* first."""
        self._score += min(value, item_cap)
        if reason is not None:
            self._reasons.append(reason)

    # -- accessors ---------------------------------------------------------

    @property
    def score(self) -> float:
        """Capped score."""
        return min(self._score, self._cap)

    @property
    def raw_score(self) -> float:
        """Un-capped score (useful for diagnostics)."""
        return self._score

    @property
    def reasons(self) -> list[str]:
        return list(self._reasons)

    def rounded_score(self, ndigits: int = 3) -> float:
        """Return the capped score rounded to *ndigits* decimals."""
        return round(self.score, ndigits)


# ── Context Engine Config ───────────────────────────────────────────────────

@dataclass(frozen=True)
class ContextEngineConfig:
    """Thresholds and weights for :class:`~railopt.context_engine.ContextEngine`.

    All ``risk_*`` fields are additive contributions to the component's
    risk_contribution value (0.0–1.0 range).
    """

    # Section failure history
    recurring_failure_threshold: int = 3
    risk_recurring_defect: float = 0.15
    risk_accelerating_trend: float = 0.10
    risk_per_section_failure: float = 0.02
    risk_per_section_failure_cap: float = 0.10
    history_cap: float = 0.35
    base_no_history_risk: float = 0.05

    # Asset lifecycle
    risk_beyond_design_life: float = 0.25
    risk_approaching_eol: float = 0.15
    risk_mid_life: float = 0.05
    risk_early_life: float = 0.0
    risk_high_failure_count: float = 0.10   # >= 5 failures
    risk_med_failure_count: float = 0.05    # >= 3 failures
    lifecycle_cap: float = 0.35

    # Corridor risk profile
    risk_single_line: float = 0.12
    risk_a_special_density: float = 0.10
    risk_a_density: float = 0.06
    risk_no_alternate_route: float = 0.05
    risk_rajdhani_route: float = 0.08
    corridor_cap: float = 0.35

    # Seasonal context
    risk_monsoon: float = 0.10
    risk_monsoon_amplified: float = 0.08
    risk_extreme_heat: float = 0.05
    risk_heat_sensitive: float = 0.05
    risk_fog: float = 0.05
    risk_fog_snt: float = 0.05
    seasonal_cap: float = 0.25


# ── Compliance Engine Config ────────────────────────────────────────────────

@dataclass(frozen=True)
class ComplianceEngineConfig:
    """Thresholds and weights for :class:`~railopt.compliance_engine.ComplianceEngine`.

    Score values are on a 0–100 scale.
    """

    # RDSO
    rdso_always_emergency: int = 30
    rdso_safety_critical: int = 15
    rdso_repeated_failures: int = 10
    rdso_repeated_failures_threshold: int = 3
    rdso_old_asset: int = 8
    rdso_old_asset_age_threshold: int = 20
    rdso_cap: int = 40

    # CRS
    crs_speed_restriction: int = 25
    crs_overdue_safety: int = 20
    crs_single_line_safety: int = 15
    crs_cap: int = 40

    # IRSGE / IRPWM
    irsge_track_geometry: int = 10
    irsge_monsoon_engineering: int = 12
    irsge_power_block: int = 8
    irsge_cap: int = 30

    # Railway Board
    rb_long_block: int = 5
    rb_long_block_hours: int = 4
    rb_high_failure_section: int = 8
    rb_high_failure_threshold: int = 5
    rb_deferred_task: int = 15
    rb_deferred_threshold: int = 2
    rb_cap: int = 25

    # Overall
    overall_cap: int = 100


# ── Behavioral Analyzer Config ──────────────────────────────────────────────

@dataclass(frozen=True)
class BehavioralConfig:
    """Thresholds and weights for :class:`~railopt.behavioral_analyzer.BehavioralAnalyzer`.

    Score values are on a 0–100 scale.
    """

    # Section failure anomaly
    section_ratio_severe: float = 3.0
    section_score_severe: int = 25
    section_ratio_high: float = 2.0
    section_score_high: int = 15
    section_ratio_moderate: float = 1.5
    section_score_moderate: int = 8

    # Department workload anomaly
    dept_overload_factor: float = 1.5
    dept_overload_score: int = 15
    dept_underload_factor: float = 0.5
    dept_underload_score: int = 5

    # Defect clustering
    cluster_severe_threshold: int = 3
    cluster_severe_score: int = 20
    cluster_moderate_threshold: int = 2
    cluster_moderate_score: int = 10
    cluster_section_threshold: int = 3
    cluster_section_score: int = 10
    clustering_cap: int = 30

    # Deferral pattern
    deferral_chronic_threshold: int = 3
    deferral_chronic_score: int = 20
    deferral_moderate_threshold: int = 2
    deferral_moderate_score: int = 10
    deferral_section_threshold: int = 3
    deferral_section_score: int = 10
    deferral_safety_score: int = 15
    deferral_cap: int = 35

    # Overall
    overall_cap: int = 100
