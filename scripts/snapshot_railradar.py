"""
Orion — RailRadar Snapshot Utility.
Fetches timetable, route, and delay data for a selected list of trains,
saving raw JSON files to data/railradar_snapshots/ for offline operation.
Counts all requests against the monthly database budget and outputs safe key masks.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from integrations.railradar_client import RailRadarClient, RailRadarError, mask_key
from backend.database import get_all_key_usages, get_engine, get_session, init_db

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Default chosen train list (25 important trains across all 10 corridors)
DEFAULT_SNAPSHOT_TRAINS = [
    # Delhi–Mumbai Rajdhani Route
    "12952",  # Mumbai Rajdhani (NDLS -> MMCT)
    "12951",  # Mumbai Rajdhani (MMCT -> NDLS)
    "12953",  # August Kranti Tejas Rajdhani
    # Delhi–Howrah Main
    "12302",  # Howrah Rajdhani (NDLS -> HWH)
    "12301",  # Howrah Rajdhani (HWH -> NDLS)
    "12313",  # Sealdah Rajdhani
    # Delhi–Amritsar Main
    "12013",  # Amritsar Shatabdi (NDLS -> ASR)
    "12014",  # Amritsar Shatabdi (ASR -> NDLS)
    # Delhi–Kalka Suburban
    "12005",  # Kalka Shatabdi (NDLS -> KLK)
    "12011",  # Kalka Shatabdi
    # Delhi–Rewari
    "14323",  # Intercity Express
    "14731",  # Kisan Express
    # Delhi–Rohtak
    "14035",  # Dhauladhar Express
    "12481",  # Intercity Express
    # Delhi–Saharanpur
    "14545",  # Express
    "14732",  # Kisan Express
    # Delhi–Chennai Rajdhani
    "12434",  # Chennai Rajdhani (NZM -> MAS)
    "12433",  # Chennai Rajdhani (MAS -> NZM)
    # Delhi–Jaipur
    "12986",  # Double Decker Express
    "12015",  # Ajmer Shatabdi (NDLS -> DOZ)
    "12016",  # Ajmer Shatabdi (DOZ -> NDLS)
    # Additional high-density freight/passenger corridor anchors
    "22691",  # Bengaluru Rajdhani
    "12424",  # Dibrugarh Rajdhani
    "12859",  # Gitanjali Express
    "12137",  # Punjab Mail
]


def snapshot_trains(
    train_numbers: list[str],
    output_dir: Path,
    dry_run: bool = False,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    engine = get_engine()
    init_db(engine)
    session = get_session(engine)
    before_counts = get_all_key_usages(session)
    session.close()

    print("=" * 60)
    print("RAILRADAR SNAPSHOT RUNNER")
    print("=" * 60)
    print(f"Target trains ({len(train_numbers)}): {', '.join(train_numbers)}")
    print(f"Destination: {output_dir}")
    print(f"Mode: {'DRY RUN (no network calls)' if dry_run else 'LIVE'}")
    print("=" * 60)

    if dry_run:
        print(f"Dry run complete. Estimated requests: {len(train_numbers) * 3} calls (timetable, route, delay per train).")
        return

    client = RailRadarClient(snapshots_dir=output_dir)

    successful = 0
    failed = 0

    for idx, train_num in enumerate(train_numbers, 1):
        print(f"[{idx}/{len(train_numbers)}] Fetching train {train_num}...")
        
        # 1. Timetable / Schedule
        try:
            timetable = client.get_train_timetable(train_num)
            out_file = output_dir / f"train_{train_num}_timetable.json"
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(timetable, f, indent=2)
            successful += 1
        except Exception as e:
            print(f"  ✗ Timetable failed for {train_num}: {e}")
            failed += 1

        # 2. Route Geometry
        try:
            route = client.get_train_route(train_num)
            out_file = output_dir / f"train_{train_num}_route.json"
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(route, f, indent=2)
            successful += 1
        except Exception as e:
            print(f"  ✗ Route failed for {train_num}: {e}")
            failed += 1

        # 3. Delay & Punctuality
        try:
            delay = client.get_train_delay(train_num)
            out_file = output_dir / f"train_{train_num}_delay.json"
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(delay, f, indent=2)
            successful += 1
        except Exception as e:
            print(f"  ✗ Delay failed for {train_num}: {e}")
            failed += 1

    # Print final usage per key
    session = get_session(engine)
    after_counts = get_all_key_usages(session)
    session.close()

    print("\n" + "=" * 60)
    print("SNAPSHOT COMPLETE")
    print(f"Successful calls: {successful}")
    print(f"Failed calls:     {failed}")
    print("-" * 60)
    print("REQUESTS USED PER KEY THIS MONTH:")
    for key in client.keys:
        suffix = key[-4:]
        total_used = after_counts.get(suffix, 0)
        run_used = max(0, total_used - before_counts.get(suffix, 0))
        rem = max(0, client.key_limit - total_used)
        print(f"  Key ...{suffix} : {run_used} calls in this run (month total: {total_used}/{client.key_limit}, remaining: {rem})")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Snapshot RailRadar data for offline Orion use.")
    parser.add_argument("--trains", nargs="*", help="Specific train numbers to snapshot", default=None)
    parser.add_argument("--dry-run", action="store_true", help="Print plan without making network requests")
    parser.add_argument("--dir", type=str, default=str(PROJECT_ROOT / "data" / "railradar_snapshots"), help="Output directory")

    args = parser.parse_args()
    selected = args.trains or DEFAULT_SNAPSHOT_TRAINS
    snapshot_trains(selected, Path(args.dir), dry_run=args.dry_run)
