"""
scripts/train_models.py

Train all Orion ML models on demand and save to ml/models/.
Usage:
    python scripts/train_models.py [--tasks NUM_TASKS] [--seed SEED]
"""
import argparse
import logging
import os
import sys

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ml.training_pipeline import TrainingPipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("train_models")


def main():
    parser = argparse.ArgumentParser(description="Train Orion ML models on demand.")
    parser.add_argument("--tasks", type=int, default=1000, help="Number of synthetic tasks for training (default: 1000)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for data generation (default: 42)")
    parser.add_argument("--data-dir", type=str, default="data", help="Directory for training data")
    parser.add_argument("--model-dir", type=str, default="ml/models", help="Directory to save trained models")
    args = parser.parse_args()

    logger.info("Initializing TrainingPipeline(data_dir=%s, model_dir=%s)...", args.data_dir, args.model_dir)
    pipeline = TrainingPipeline(data_dir=args.data_dir, model_dir=args.model_dir)

    logger.info("Generating training data (%d tasks, seed=%d)...", args.tasks, args.seed)
    pipeline.generate_training_data(num_tasks=args.tasks, seed=args.seed)

    logger.info("Starting training...")
    metrics = pipeline.train_all()

    print("\n" + "=" * 60)
    print("MODEL TRAINING COMPLETE")
    print("=" * 60)
    for model_name, model_metrics in metrics.items():
        print(f"\n{model_name}:")
        for k, v in model_metrics.items():
            print(f"  {k}: {v}")

    scored = pipeline.score_tasks()
    print(f"\nScored {len(scored)} tasks successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
