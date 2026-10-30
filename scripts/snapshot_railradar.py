"""
scripts/snapshot_railradar.py

RailRadar snapshot utility for Orion pilot sections.
Fetches:
1. Trains between stations per pilot section (1 call per section)
2. Timetable per train for up to N trains per section (1 call per train, default N=15)
3. Route geometry for ONE train per pilot corridor only (1 call per corridor)

Supports --dry-run to display projected calls vs key budget without making requests.
Saves standard JSON files into data/railradar_snapshots/ for offline operation.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Set

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from integrations.railradar_client import RailRadarClient, RailRadarError, mask_key
from backend.database import get_all_key_usages, get_engine, get_session, init_db
from traffic.section_map import get_pilot_sections, PilotSectionConfig

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("snapshot_railradar")

# One anchor train with real track geometry per pilot corridor
PILOT_CORRIDOR_GEOMETRY_TRAINS = {
    "Delhi–Howrah Main": "12302",          # Howrah Rajdhani
    "Delhi–Mumbai Rajdhani Route": "12952", # Mumbai Rajdhani
}

# High-priority default trains per pilot section for offline seed fallback
DEFAULT_PILOT_TRAINS: Dict[str, List[str]] = {
    "SEC-93135bb9": [  # NDLS - GZB
        "12302", "12301", "12313", "12004", "12003",
        "12424", "12423", "12560", "12559", "14037",
        "12274", "12444", "12878", "12368", "15484"
    ],
    "SEC-d4d8b85c": [  # NDLS - MTJ
        "12952", "12951", "12954", "12953", "12002",
        "12001", "22692", "22691", "12432", "12431",
        "12926", "12925", "12618", "12617", "12448"
    ],
}


def compute_call_plan(
    pilot_sections: Dict[str, PilotSectionConfig],
    max_trains_per_section: int = 15,
) -> dict:
    """Computes the expected API call plan for pilot sections."""
    sections_plan = []
    total_between_calls = len(pilot_sections)
    unique_geometry_trains = list(PILOT_CORRIDOR_GEOMETRY_TRAINS.values())
    total_geometry_calls = len(unique_geometry_trains)

    unique_trains_to_fetch: Set[str] = set()

    for sec_id, sec_cfg in pilot_sections.items():
        seed_trains = DEFAULT_PILOT_TRAINS.get(sec_id, [])[:max_trains_per_section]
        unique_trains_to_fetch.update(seed_trains)
        sections_plan.append({
            "section_id": sec_id,
            "name": sec_cfg.name,
            "from_code": sec_cfg.from_code,
            "to_code": sec_cfg.to_code,
            "corridor": sec_cfg.corridor_name,
            "target_trains_count": min(len(seed_trains), max_trains_per_section),
            "sample_trains": seed_trains[:5],
        })

    # Total timetable calls is bounded by unique trains across all pilot sections
    total_timetable_calls = len(unique_trains_to_fetch)
    total_projected_calls = total_between_calls + total_geometry_calls + total_timetable_calls

    return {
        "sections": sections_plan,
        "between_calls": total_between_calls,
        "geometry_calls": total_geometry_calls,
        "geometry_trains": unique_geometry_trains,
        "timetable_calls": total_timetable_calls,
        "unique_trains": sorted(list(unique_trains_to_fetch)),
        "total_calls": total_projected_calls,
    }


def snapshot_pilot_railradar(
    output_dir: Path,
    max_trains_per_section: int = 15,
    dry_run: bool = False,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    engine = get_engine()
    init_db(engine)
    session = get_session(engine)
    before_counts = get_all_key_usages(session)
    session.close()

    pilot_sections = get_pilot_sections()
    plan = compute_call_plan(pilot_sections, max_trains_per_section=max_trains_per_section)

    print("=" * 65)
    print("ORION RAILRADAR SNAPSHOT RUNNER (PILOT TIMETABLE & TRACK GEOMETRY)")
    print("=" * 65)
    print(f"Output Directory:      {output_dir}")
    print(f"Max trains / section:  {max_trains_per_section}")
    print(f"Execution Mode:        {'DRY RUN (no network calls)' if dry_run else 'LIVE RUN'}")
    print("-" * 65)
    print("CALL PLAN BREAKDOWN:")
    print(f"  1. Trains-Between calls:   {plan['between_calls']} (1 per pilot section)")
    print(f"  2. Corridor Geometry:      {plan['geometry_calls']} (1 per pilot corridor: {', '.join(plan['geometry_trains'])})")
    print(f"  3. Timetable Schedule:     {plan['timetable_calls']} calls (up to {max_trains_per_section} trains/section)")
    print(f"  TOTAL PROJECTED CALLS:     {plan['total_calls']}")
    print("-" * 65)

    client = RailRadarClient(snapshots_dir=output_dir)
    total_budget_remaining = 0

    print("KEY BUDGET STATUS:")
    for key in client.keys:
        suffix = key[-4:]
        used = before_counts.get(suffix, 0)
        rem = max(0, client.key_limit - used)
        total_budget_remaining += rem
        print(f"  Key ...{suffix} : {used}/{client.key_limit} used ({rem} remaining)")

    print(f"Total available budget across keys: {total_budget_remaining} calls")
    print("=" * 65)

    if dry_run:
        print("\n[DRY RUN] Call plan evaluated. Projected requests:")
        for sec in plan["sections"]:
            print(f"  - Section {sec['name']} ({sec['from_code']}->{sec['to_code']}): get_trains_between + {sec['target_trains_count']} timetables")
        for tr in plan["geometry_trains"]:
            print(f"  - Geometry route for corridor train: {tr}")
        print(f"\nBudget feasibility: {'PASS (sufficient budget)' if total_budget_remaining >= plan['total_calls'] else 'WARN (budget constrained)'}")
        return

    successful = 0
    failed = 0

    # 1. Fetch trains between stations for each pilot section
    trains_per_section: Dict[str, List[str]] = {}
    for sec_id, sec_cfg in pilot_sections.items():
        print(f"\n[1/3] Fetching trains between {sec_cfg.from_code} and {sec_cfg.to_code}...")
        try:
            between_data = client.get_trains_between(sec_cfg.from_code, sec_cfg.to_code)
            out_file = output_dir / f"train_between_{sec_cfg.from_code}_{sec_cfg.to_code}.json"
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(between_data, f, indent=2)
            successful += 1

            # Extract train numbers from between response if available
            extracted: List[str] = []
            data_field = between_data.get("data", [])
            train_items = data_field if isinstance(data_field, list) else data_field.get("trains", [])
            for item in train_items:
                t_num = item.get("train_number") or item.get("number")
                if t_num:
                    extracted.append(str(t_num))

            # Merge with default fallback seeds if API returned empty
            merged_trains = list(dict.fromkeys(extracted + DEFAULT_PILOT_TRAINS.get(sec_id, [])))
            trains_per_section[sec_id] = merged_trains[:max_trains_per_section]
            print(f"  ✓ Saved trains-between ({len(trains_per_section[sec_id])} trains selected for timetables)")
        except Exception as e:
            logger.warning("Trains-between failed for %s-%s: %s. Using default pilot seed list.", sec_cfg.from_code, sec_cfg.to_code, e)
            trains_per_section[sec_id] = DEFAULT_PILOT_TRAINS.get(sec_id, [])[:max_trains_per_section]
            failed += 1

    # 2. Fetch route geometry for ONE train per pilot corridor
    print("\n[2/3] Fetching corridor route geometries (1 train per pilot corridor)...")
    for corridor_name, geo_train in PILOT_CORRIDOR_GEOMETRY_TRAINS.items():
        print(f"  Fetching geometry for {corridor_name} (Train {geo_train})...")
        try:
            route_data = client.get_train_route(geo_train)
            out_file = output_dir / f"train_{geo_train}_route.json"
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(route_data, f, indent=2)
            successful += 1
            print(f"  ✓ Saved geometry snapshot: {out_file.name}")
        except Exception as e:
            logger.warning("Geometry fetch failed for train %s: %s", geo_train, e)
            failed += 1

    # 3. Fetch timetables for selected unique trains
    all_unique_trains = list(dict.fromkeys([t for t_list in trains_per_section.values() for t in t_list]))
    print(f"\n[3/3] Fetching timetables for {len(all_unique_trains)} unique trains...")

    for idx, t_num in enumerate(all_unique_trains, 1):
        print(f"  [{idx}/{len(all_unique_trains)}] Fetching timetable for train {t_num}...")
        try:
            timetable_data = client.get_train_timetable(t_num)
            out_file = output_dir / f"train_{t_num}_timetable.json"
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(timetable_data, f, indent=2)
            successful += 1
        except Exception as e:
            logger.warning("Timetable fetch failed for train %s: %s", t_num, e)
            failed += 1

    # Final summary & usage reporting
    session = get_session(engine)
    after_counts = get_all_key_usages(session)
    session.close()

    print("\n" + "=" * 65)
    print("SNAPSHOT COMPLETE")
    print(f"Successful calls: {successful}")
    print(f"Failed calls:     {failed}")
    print("-" * 65)
    print("REQUESTS USED PER KEY THIS MONTH:")
    for key in client.keys:
        suffix = key[-4:]
        total_used = after_counts.get(suffix, 0)
        run_used = max(0, total_used - before_counts.get(suffix, 0))
        rem = max(0, client.key_limit - total_used)
        print(f"  Key ...{suffix} : {run_used} calls in this run (month total: {total_used}/{client.key_limit}, remaining: {rem})")
    print("=" * 65)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Snapshot RailRadar pilot timetable and track data.")
    parser.add_argument("--max-trains", type=int, default=15, help="Max trains per pilot section (default: 15)")
    parser.add_argument("--dry-run", action="store_true", help="Print call plan and budget projection without network calls")
    parser.add_argument("--dir", type=str, default=str(PROJECT_ROOT / "data" / "railradar_snapshots"), help="Output directory")

    args = parser.parse_args()
    snapshot_pilot_railradar(Path(args.dir), max_trains_per_section=args.max_trains, dry_run=args.dry_run)
