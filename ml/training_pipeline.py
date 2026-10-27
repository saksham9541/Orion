"""
RailOpt — End-to-end ML training pipeline.

Generates synthetic labelled data, trains all three ML models
(criticality scorer, impact predictor, duration estimator),
evaluates them, and saves artifacts.

Usage:
    pipeline = TrainingPipeline(data_dir="data", model_dir="ml/models")
    pipeline.generate_training_data(num_tasks=1000)
    metrics = pipeline.train_all()
    print(metrics)
"""

from __future__ import annotations

import logging
import os

import numpy as np
import pandas as pd

from railopt.models import (
    ALWAYS_EMERGENCY,
    SAFETY_CRITICAL_DEFECTS,
    DefectSeverity,
    MaintenanceTask,
    Section,
    TrafficDensityClass,
)
from railopt.synthetic_data import generate_full_dataset

from .criticality_scorer import CriticalityScorer
from .duration_estimator import DurationEstimator
from .feature_engineering import BlockWindowFeatureExtractor, TaskFeatureExtractor
from .impact_predictor import TrafficImpactPredictor

# logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _generate_criticality_labels(
    tasks: list[MaintenanceTask],
) -> tuple[pd.Series, pd.Series]:
    """
    Generate synthetic severity class labels and 0-100 criticality scores
    using Indian Railways safety rules as heuristics.

    ⚠ TODO(real-data): This entire function is a TEMPORARY SUBSTITUTE for
    real labelled data.  When actual IR maintenance records arrive, DELETE
    this function and train directly on expert-annotated severity/criticality
    labels.  The formulas below are domain-informed guesses, NOT ground truth.

    The labelling rules encode domain knowledge:
    - ALWAYS_EMERGENCY defects → score ≥ 95, class EMERGENCY
    - SAFETY_CRITICAL_DEFECTS → score 70-90, class HIGH
    - High days_overdue + high failure count → elevated score
    - Asset age contributes moderately
    - Low-risk items → score 10-40, class LOW
    """
    y_class: list[str] = []
    y_score: list[float] = []

    for task in tasks:
        # Base score from measurable factors
        score = 15.0
        score += min(task.days_overdue * 1.5, 30)          # Cap overdue contribution
        score += min(task.asset_age_years * 0.8, 20)       # Cap age contribution
        score += min(task.historical_failure_count * 6, 25) # Recurrence is a big signal
        score += task.deferred_count * 4                    # Repeated deferrals escalate

        # Noise for realism
        score += np.random.normal(0, 3)

        # Hard rules (domain knowledge)
        if task.defect_category in ALWAYS_EMERGENCY:
            score = max(95.0, score)
            severity = DefectSeverity.EMERGENCY.value
        elif task.defect_category in SAFETY_CRITICAL_DEFECTS:
            score = max(70.0, min(95.0, score + 25))
            severity = DefectSeverity.HIGH.value
        elif score >= 65:
            severity = DefectSeverity.HIGH.value
        elif score >= 35:
            severity = DefectSeverity.MEDIUM.value
        else:
            severity = DefectSeverity.LOW.value

        y_class.append(severity)
        y_score.append(float(np.clip(score, 0, 100)))

    return pd.Series(y_class), pd.Series(y_score)


def _generate_impact_labels(
    windows_df: pd.DataFrame,
    sections: dict[str, Section],
) -> pd.DataFrame:
    """
    Generate synthetic traffic impact labels based on section density,
    block duration, and time of day.
    """
    records = []
    for _, row in windows_df.iterrows():
        duration = row.get("block_duration_hours", 3.0)
        start_hour = row.get("block_start_hour", 2)

        # Peak hours have higher impact
        time_factor = 1.0
        if 7 <= start_hour <= 10 or 17 <= start_hour <= 20:
            time_factor = 2.5  # Peak
        elif 22 <= start_hour or start_hour <= 5:
            time_factor = 0.4  # Night (low impact)

        density_factor = row.get("section_traffic_density", 30)
        if isinstance(density_factor, str):
            density_factor = {
                "A_SPECIAL": 70, "A": 50, "B": 30, "C": 15, "D": 5
            }.get(density_factor, 30)

        trains = int(duration * (density_factor / 24) * time_factor * np.random.uniform(0.8, 1.2))
        delay = trains * np.random.uniform(5, 20)
        impact_score = float(np.clip(trains * 2 + duration * 5 + time_factor * 10, 0, 100))

        records.append({
            "traffic_impact_score": impact_score,
            "trains_affected": trains,
            "cumulative_delay_minutes": delay,
        })

    return pd.DataFrame(records, index=windows_df.index)


class TrainingPipeline:
    """End-to-end training orchestration for all RailOpt ML models."""

    def __init__(self, data_dir: str = "data", model_dir: str = "ml/models"):
        self.data_dir = data_dir
        self.model_dir = model_dir
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.model_dir, exist_ok=True)

        self.tasks: list[MaintenanceTask] = []
        self.windows = []
        self.sections: dict[str, Section] = {}
        self.corridors = []

    def generate_training_data(self, num_tasks: int = 1000, seed: int = 42):
        """Generate synthetic dataset using the synthetic data generator."""
        logger.info(f"Generating synthetic data: {num_tasks} tasks, seed={seed}")
        dataset = generate_full_dataset(seed=seed, num_tasks=num_tasks)

        self.corridors = dataset["corridors"]
        self.tasks = dataset["tasks"]
        self.windows = dataset["block_windows"]
        self.sections = {s.section_id: s for s in dataset["sections"]}

        logger.info(
            f"Generated: {len(self.tasks)} tasks, "
            f"{len(self.windows)} windows, "
            f"{len(self.sections)} sections, "
            f"{len(self.corridors)} corridors"
        )

    def train_criticality_scorer(self) -> dict:
        """Train the XGBoost criticality/risk scoring model."""
        if not self.tasks:
            logger.warning("No tasks available. Call generate_training_data() first.")
            return {}

        logger.info("Training criticality scorer...")

        # Extract features
        extractor = TaskFeatureExtractor()
        X = extractor.transform(self.tasks, self.sections)

        # Generate labels
        y_class, y_score = _generate_criticality_labels(self.tasks)

        # Train
        scorer = CriticalityScorer()
        scorer.fit(X, y_class, y_score)

        # Save
        path = os.path.join(self.model_dir, "criticality_scorer.pkl")
        scorer.save(path)
        logger.info(f"Saved criticality scorer to {path}")

        # Evaluate on training set
        preds_class, preds_score = scorer.predict(X, self.tasks)
        accuracy = float((preds_class == y_class.values).mean())
        mae = float(np.abs(preds_score - y_score.values).mean())

        metrics = {"accuracy": round(accuracy, 4), "score_mae": round(mae, 2)}
        logger.info(f"Criticality Scorer — accuracy: {accuracy:.3f}, MAE: {mae:.1f}")
        return metrics

    def train_impact_predictor(self) -> dict:
        """Train the LightGBM traffic impact prediction model."""
        if not self.windows:
            logger.warning("No windows available. Call generate_training_data() first.")
            return {}

        logger.info("Training traffic impact predictor...")

        extractor = BlockWindowFeatureExtractor()
        X = extractor.transform(self.windows, self.sections)

        # Generate labels
        y = _generate_impact_labels(X, self.sections)

        # Train
        predictor = TrafficImpactPredictor()
        predictor.fit(X, y)

        # Save
        path = os.path.join(self.model_dir, "impact_predictor.pkl")
        predictor.save(path)
        logger.info(f"Saved impact predictor to {path}")

        # Evaluate
        preds = predictor.predict(X)
        mae = float(np.abs(preds.values - y.values).mean())

        metrics = {"mae": round(mae, 2)}
        logger.info(f"Impact Predictor — MAE: {mae:.1f}")
        return metrics

    def train_duration_estimator(self) -> dict:
        """Train the Random Forest duration estimator."""
        if not self.tasks:
            logger.warning("No tasks available. Call generate_training_data() first.")
            return {}

        logger.info("Training duration estimator...")

        extractor = TaskFeatureExtractor()
        X = extractor.transform(self.tasks, self.sections)

        # Synthetic "actual" durations = estimated + noise
        y = pd.Series([
            max(0.5, t.estimated_duration_hours * (1 + np.random.normal(0, 0.25)))
            for t in self.tasks
        ])

        # Train
        estimator = DurationEstimator()
        estimator.fit(X, y)

        # Save
        path = os.path.join(self.model_dir, "duration_estimator.pkl")
        estimator.save(path)
        logger.info(f"Saved duration estimator to {path}")

        # Evaluate
        preds = estimator.predict(X)
        pred_hours = preds["duration_hours"] if isinstance(preds, pd.DataFrame) else preds
        mae = float(np.abs(pred_hours.values - y.values).mean())
        within_30pct = float(
            (np.abs(pred_hours.values - y.values) / y.values < 0.3).mean()
        )

        metrics = {"mae": round(mae, 2), "within_30pct": round(within_30pct, 4)}
        logger.info(f"Duration Estimator — MAE: {mae:.2f}h, within 30%: {within_30pct:.1%}")
        return metrics

    def train_all(self) -> dict:
        """Train all models and return combined metrics."""
        logger.warning(
            "Training against domain-heuristic labels (synthetic). "
            "Metrics reflect fit to heuristics, NOT real-world performance. "
            "Do NOT present these as validated accuracy in presentations."
        )
        logger.info("=" * 60)
        logger.info("TRAINING ALL MODELS")
        logger.info("=" * 60)

        m1 = self.train_criticality_scorer()
        m2 = self.train_impact_predictor()
        m3 = self.train_duration_estimator()

        all_metrics = {"criticality": m1, "impact": m2, "duration": m3}
        logger.info(f"\nAll metrics: {all_metrics}")
        return all_metrics

    def score_tasks(self) -> list[MaintenanceTask]:
        """
        Load trained models and score all tasks.
        Returns tasks with ml_criticality_score, ml_predicted_severity,
        ml_predicted_duration_hours, and ml_shap_values populated.
        """
        scorer_path = os.path.join(self.model_dir, "criticality_scorer.pkl")
        duration_path = os.path.join(self.model_dir, "duration_estimator.pkl")

        if not os.path.exists(scorer_path):
            logger.warning("No trained criticality scorer found. Train first.")
            return self.tasks

        # Load models
        scorer = CriticalityScorer()
        scorer.load(scorer_path)

        extractor = TaskFeatureExtractor()
        X = extractor.transform(self.tasks, self.sections)

        # Score criticality
        classes, scores = scorer.predict(X, self.tasks)
        shap_values = scorer.explain(X)

        for i, task in enumerate(self.tasks):
            task.ml_criticality_score = float(scores[i])
            task.ml_predicted_severity = DefectSeverity(classes[i])
            task.ml_shap_values = shap_values[i]

        # Score duration if model exists
        if os.path.exists(duration_path):
            estimator = DurationEstimator()
            estimator.load(duration_path)
            preds = estimator.predict(X)
            if isinstance(preds, pd.DataFrame):
                for i, task in enumerate(self.tasks):
                    task.ml_predicted_duration_hours = float(preds.iloc[i]["duration_hours"])
                    if "p25" in preds.columns:
                        task.ml_duration_confidence_lower = float(preds.iloc[i]["p25"])
                    if "p75" in preds.columns:
                        task.ml_duration_confidence_upper = float(preds.iloc[i]["p75"])

        logger.info(f"Scored {len(self.tasks)} tasks")
        return self.tasks


# ──────────────────────────────────────────────────────────────────────
# CLI entry point
# ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    pipeline = TrainingPipeline(data_dir="data", model_dir="ml/models")
    pipeline.generate_training_data(num_tasks=1000, seed=42)
    metrics = pipeline.train_all()

    print("\n" + "=" * 60)
    print("TRAINING COMPLETE")
    print("=" * 60)
    for model_name, model_metrics in metrics.items():
        print(f"\n{model_name}:")
        for k, v in model_metrics.items():
            print(f"  {k}: {v}")

    # Score all tasks
    scored_tasks = pipeline.score_tasks()
    print(f"\nScored {len(scored_tasks)} tasks")

    # Show a sample
    for t in scored_tasks[:5]:
        print(
            f"  {t.task_id}: {t.defect_category.value} → "
            f"score={t.ml_criticality_score:.0f}, "
            f"severity={t.ml_predicted_severity.value if t.ml_predicted_severity else '?'}, "
            f"duration={t.ml_predicted_duration_hours:.1f}h"
        )
