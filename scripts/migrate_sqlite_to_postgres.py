"""
Orion — SQLite to PostgreSQL Migration Utility.
Copies existing database records from SQLite to PostgreSQL (Neon or local),
ensuring that all migrated tasks, plans, and blocks are explicitly tagged as 'synthetic'.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import (
    Base,
    TaskRecord,
    BlockPlanRecord,
    CorridorRecord,
    AlertRecord,
    LiveTrainStatusRecord,
    ApiUsageRecord,
    ApiCacheRecord,
    UserRecord,
    get_database_url,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def migrate_data(sqlite_path: str, pg_url: str) -> None:
    sqlite_file = Path(sqlite_path)
    if not sqlite_file.exists():
        logger.error("SQLite file not found at: %s", sqlite_file)
        sys.exit(1)

    logger.info("Connecting to source SQLite: %s", sqlite_path)
    src_engine = create_engine(f"sqlite:///{sqlite_path}", connect_args={"check_same_thread": False})
    SrcSession = sessionmaker(bind=src_engine)
    src_session = SrcSession()

    logger.info("Connecting to target PostgreSQL: %s", pg_url.split("@")[-1] if "@" in pg_url else pg_url)
    dst_engine = create_engine(pg_url, pool_pre_ping=True)
    # Ensure tables exist on target
    Base.metadata.create_all(dst_engine)
    DstSession = sessionmaker(bind=dst_engine)
    dst_session = DstSession()

    stats = {}

    try:
        # 1. Corridors
        corridors = src_session.query(CorridorRecord).all()
        for c in corridors:
            dst_session.merge(CorridorRecord(
                corridor_id=c.corridor_id,
                name=c.name,
                division=c.division,
                zone=c.zone,
                sections=c.sections,
                total_length_km=c.total_length_km,
                is_rajdhani_route=c.is_rajdhani_route,
            ))
        stats["corridors"] = len(corridors)
        dst_session.commit()

        # 2. Tasks (Tag as synthetic!)
        tasks = src_session.query(TaskRecord).all()
        for t in tasks:
            d = t.__dict__.copy()
            d.pop('_sa_instance_state', None)
            d["source"] = "synthetic"  # Enforce synthetic tag
            dst_session.merge(TaskRecord(**d))
        stats["tasks"] = len(tasks)
        dst_session.commit()

        # 3. Plans (Tag plan and contained scheduled_blocks as synthetic!)
        plans = src_session.query(BlockPlanRecord).all()
        for p in plans:
            d = p.__dict__.copy()
            d.pop('_sa_instance_state', None)
            d["source"] = "synthetic"  # Enforce synthetic tag
            blocks = d.get("scheduled_blocks") or []
            if isinstance(blocks, list):
                for b in blocks:
                    if isinstance(b, dict):
                        b["source"] = "synthetic"
                d["scheduled_blocks"] = blocks
            dst_session.merge(BlockPlanRecord(**d))
        stats["plans"] = len(plans)
        dst_session.commit()

        # 4. Alerts
        alerts = src_session.query(AlertRecord).all()
        for a in alerts:
            d = a.__dict__.copy()
            d.pop('_sa_instance_state', None)
            dst_session.merge(AlertRecord(**d))
        stats["alerts"] = len(alerts)
        dst_session.commit()

        # 5. Live train status
        statuses = src_session.query(LiveTrainStatusRecord).all()
        for s in statuses:
            d = s.__dict__.copy()
            d.pop('_sa_instance_state', None)
            dst_session.merge(LiveTrainStatusRecord(**d))
        stats["live_train_status"] = len(statuses)
        dst_session.commit()

        # 6. API usage
        usages = src_session.query(ApiUsageRecord).all()
        for u in usages:
            d = u.__dict__.copy()
            d.pop('_sa_instance_state', None)
            dst_session.merge(ApiUsageRecord(**d))
        stats["api_usage"] = len(usages)
        dst_session.commit()

        # 7. API cache
        caches = src_session.query(ApiCacheRecord).all()
        for c in caches:
            d = c.__dict__.copy()
            d.pop('_sa_instance_state', None)
            dst_session.merge(ApiCacheRecord(**d))
        stats["api_cache"] = len(caches)
        dst_session.commit()

        # 8. Users
        users = src_session.query(UserRecord).all()
        for u in users:
            d = u.__dict__.copy()
            d.pop('_sa_instance_state', None)
            dst_session.merge(UserRecord(**d))
        stats["users"] = len(users)
        dst_session.commit()

        logger.info("Migration successful!")
        for tbl, count in stats.items():
            logger.info("  %s: %d rows migrated", tbl, count)

    except Exception as e:
        dst_session.rollback()
        logger.error("Migration failed: %s", e)
        raise
    finally:
        src_session.close()
        dst_session.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate Orion SQLite database to PostgreSQL.")
    parser.add_argument("--sqlite-path", default="railopt.db", help="Path to source SQLite database")
    parser.add_argument("--postgres-url", default=None, help="Target PostgreSQL connection URL (or DATABASE_URL env)")

    args = parser.parse_args()
    target_url = args.postgres_url or os.environ.get("DATABASE_URL")
    if not target_url or target_url.startswith("sqlite"):
        logger.error("Please supply a valid PostgreSQL URL via --postgres-url or DATABASE_URL env var.")
        sys.exit(1)

    migrate_data(args.sqlite_path, target_url)
