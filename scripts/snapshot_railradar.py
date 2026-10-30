"""
scripts/snapshot_railradar.py

RailRadar snapshot utility for Orion pilot sections.
Fetches:
1. Trains between stations per pilot section (1 call per section)
2. Timetable per train for up to N trains per section (1 call per train, default N=16)
   - Selects dynamically from trains-between API feed, balancing EMU/MEMU/passenger, express, and goods.
   - Falls back to seed list only if trains-between call fails or is empty.
3. Route geometry for ONE train per pilot corridor only (1 call per corridor)

Supports --dry-run to display projected calls vs key budget without making requests.
Saves standard JSON files into data/railradar_snapshots/ for offline operation.
Guarantees:
- Never overwrites a file marked provenance="live" with hand_written/non-live data.
- A failed or non-live call writes nothing to disk.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

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

# High-priority default fallback seed trains per pilot section (including 1 all-stops EMU/passenger train)
DEFAULT_PILOT_TRAINS: Dict[str, List[str]] = {
    "SEC-93135bb9": [  # NDLS - GZB
        "64424",  # All-stops EMU (NDLS-CSB-TKJ-ANVR-SBB-GZB)
        "12302", "12301", "12313", "12004", "12003",
        "12424", "12423", "12560", "12559", "14037",
        "12274", "12444", "12878", "12368", "15484"
    ],
    "SEC-d4d8b85c": [  # NDLS - MTJ
        "64904",  # All-stops Mathura-New Delhi EMU
        "12952", "12951", "12954", "12953", "12002",
        "12001", "22692", "22691", "12432", "12431",
        "12926", "12925", "12618", "12617", "12448"
    ],
}


def select_balanced_train_sample(
    train_items: List[dict],
    max_trains: int = 16,
    preferred_all_stops: Optional[str] = None,
    fallback_trains: Optional[List[str]] = None,
) -> Tuple[List[str], Dict[str, int]]:
    """
    Selects trains directly from the trains-between API response (trains running
    through both terminal stations), trying to include a balanced mix of:
    - Commuter / suburban / EMU / MEMU / Passenger
    - Goods / Freight (if present in feed)
    - Premium & Mail/Express (Rajdhani, Shatabdi, Superfast)
    Falls back to fallback_trains ONLY if train_items is empty.
    Returns (selected_train_numbers, category_counts).
    """
    if not train_items:
        fallback = (fallback_trains or [])[:max_trains]
        return fallback, {"fallback_used": len(fallback)}

    commuter_trains: List[str] = []
    goods_trains: List[str] = []
    express_trains: List[str] = []

    for item in train_items:
        t_num = str(item.get("train_number") or item.get("number") or "").strip()
        if not t_num:
            continue
        t_name = str(item.get("train_name") or item.get("name") or "").upper()
        t_type = str(item.get("train_type") or item.get("type") or "").upper()

        is_commuter = (
            "EMU" in t_type or "MEMU" in t_type or "DEMU" in t_type or
            "PASSENGER" in t_type or "SUBURBAN" in t_type or "LOCAL" in t_type or
            "EMU" in t_name or "MEMU" in t_name or "PASS" in t_name or "LOCAL" in t_name or
            t_num.startswith("64") or t_num.startswith("04")
        )
        is_goods = (
            "GOODS" in t_type or "FREIGHT" in t_type or "PARCEL" in t_type or "CONTAINER" in t_type or
            "GOODS" in t_name or "FREIGHT" in t_name
        )

        if is_commuter:
            commuter_trains.append(t_num)
        elif is_goods:
            goods_trains.append(t_num)
        else:
            express_trains.append(t_num)

    selected: List[str] = []

    # 1. Prioritize preferred all-stops train if given (e.g. 64424)
    if preferred_all_stops and preferred_all_stops not in selected:
        selected.append(str(preferred_all_stops))

    # 2. Add commuter / passenger trains (up to 3)
    for t in commuter_trains:
        if t not in selected and len(selected) < min(3, max_trains):
            selected.append(t)

    # 3. Add goods trains if any exist in the feed
    for t in goods_trains:
        if t not in selected and len(selected) < max_trains:
            selected.append(t)

    # 4. Fill remaining capacity with express / premium trains
    for t in express_trains:
        if t not in selected and len(selected) < max_trains:
            selected.append(t)

    # If still not full, add from any remaining
    for item in train_items:
        t = str(item.get("train_number") or item.get("number") or "").strip()
        if t and t not in selected and len(selected) < max_trains:
            selected.append(t)

    # If still below max_trains, complement from fallback list
    if fallback_trains:
        for t in fallback_trains:
            if t not in selected and len(selected) < max_trains:
                selected.append(t)

    counts = {
        "commuter": sum(1 for t in selected if t in commuter_trains or t == preferred_all_stops),
        "goods": sum(1 for t in selected if t in goods_trains),
        "express": sum(1 for t in selected if t in express_trains),
    }
    return selected, counts


def compute_call_plan(
    pilot_sections: Dict[str, PilotSectionConfig],
    max_trains_per_section: int = 16,
    all_stops_train: Optional[str] = None,
) -> dict:
    """Computes the expected API call plan for pilot sections."""
    sections_plan = []
    total_between_calls = len(pilot_sections)
    
    # Corridor geometry trains matching active pilot sections
    active_corridors = {sec.corridor_name for sec in pilot_sections.values()}
    unique_geometry_trains = [
        train_no for corr_name, train_no in PILOT_CORRIDOR_GEOMETRY_TRAINS.items()
        if corr_name in active_corridors
    ]
    total_geometry_calls = len(unique_geometry_trains)

    unique_trains_to_fetch: Set[str] = set()

    for sec_id, sec_cfg in pilot_sections.items():
        seed_trains = list(DEFAULT_PILOT_TRAINS.get(sec_id, []))
        if all_stops_train and all_stops_train not in seed_trains:
            seed_trains.insert(0, all_stops_train)
        seed_trains = seed_trains[:max_trains_per_section]
        unique_trains_to_fetch.update(seed_trains)
        sections_plan.append({
            "section_id": sec_id,
            "name": sec_cfg.name,
            "from_code": sec_cfg.from_code,
            "to_code": sec_cfg.to_code,
            "corridor": sec_cfg.corridor_name,
            "target_trains_count": len(seed_trains),
            "sample_trains": seed_trains[:5],
            "all_trains": seed_trains,
        })

    # Total timetable calls is bounded by unique trains across active pilot sections
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


def _verify_can_safely_write(out_file: Path, incoming_is_live: bool) -> bool:
    """Checks that we never overwrite an existing live file with non-live data."""
    if not out_file.exists():
        return True
    try:
        with open(out_file, "r", encoding="utf-8") as f:
            existing = json.load(f)
        existing_prov = existing.get("provenance") or (existing.get("meta") or {}).get("provenance")
        if existing_prov == "live" and not incoming_is_live:
            logger.warning("Safety check: refusing to overwrite live snapshot %s with non-live data", out_file.name)
            return False
    except Exception:
        pass
    return True


def snapshot_pilot_railradar(
    output_dir: Path,
    max_trains_per_section: int = 16,
    dry_run: bool = False,
    section_filter: Optional[str] = None,
    all_stops_train: Optional[str] = None,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    engine = get_engine()
    init_db(engine)
    session = get_session(engine)
    before_counts = get_all_key_usages(session)
    session.close()

    pilot_sections = get_pilot_sections()
    if section_filter:
        norm_filter = section_filter.strip().upper()
        matched = {}
        for k, v in pilot_sections.items():
            if norm_filter in (k.upper(), v.name.upper(), f"{v.from_code}-{v.to_code}".upper()):
                matched[k] = v
        if matched:
            pilot_sections = matched
        else:
            logger.warning("Section filter '%s' did not match; using all pilot sections", section_filter)

    plan = compute_call_plan(pilot_sections, max_trains_per_section=max_trains_per_section, all_stops_train=all_stops_train)

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
    print(f"  3. Timetable Schedule:     {plan['timetable_calls']} calls")
    print(f"  TOTAL PROJECTED CALLS:     {plan['total_calls']}")
    print("-" * 65)

    client = RailRadarClient(snapshots_dir=output_dir)
    total_budget_remaining = 0

    print("KEY BUDGET STATUS:")
    if not client.keys:
        print("  [WARN] No RAILRADAR_API_KEYS found in environment or .env")
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
            all_tr = sec.get("all_trains", [])
            print(f"  - Section {sec['name']} ({sec['from_code']}->{sec['to_code']}):")
            print(f"      1 x get_trains_between({sec['from_code']}, {sec['to_code']})")
            print(f"      {len(all_tr)} x get_train_timetable (selected dynamically from trains-between response):")
            print(f"        Fallback seeds: {', '.join(all_tr)}")
        for tr in plan["geometry_trains"]:
            print(f"  - Corridor Route Geometry: get_train_route({tr})")
        
        status_str = "PASS (sufficient budget)" if total_budget_remaining >= plan['total_calls'] else "WARN (budget constrained / no keys configured)"
        print(f"\nBudget feasibility: {status_str}")
        print("=" * 65)
        return

    successful = 0
    failed = 0
    total_between_trains_count = 0

    # 1. Fetch trains between stations for each pilot section
    trains_per_section: Dict[str, List[str]] = {}
    for sec_id, sec_cfg in pilot_sections.items():
        print(f"\n[1/3] Fetching trains between {sec_cfg.from_code} and {sec_cfg.to_code}...")
        fallback_list = list(DEFAULT_PILOT_TRAINS.get(sec_id, []))
        if all_stops_train and all_stops_train not in fallback_list:
            fallback_list = [all_stops_train] + fallback_list

        try:
            between_data = client.get_trains_between(sec_cfg.from_code, sec_cfg.to_code)
            # Verify response is truly from live network, not an offline snapshot fallback
            if between_data.get("source") != "live":
                raise RailRadarError(f"Response was served from fallback snapshot, not live network")

            ts = datetime.now(timezone.utc).isoformat()
            between_data["provenance"] = "live"
            between_data["snapshot_timestamp"] = ts
            between_data["illustrative"] = False
            if "meta" not in between_data or not isinstance(between_data["meta"], dict):
                between_data["meta"] = {}
            between_data["meta"]["provenance"] = "live"
            between_data["meta"]["snapshot_timestamp"] = ts
            between_data["meta"]["illustrative"] = False

            out_file = output_dir / f"train_between_{sec_cfg.from_code}_{sec_cfg.to_code}.json"
            if _verify_can_safely_write(out_file, incoming_is_live=True):
                with open(out_file, "w", encoding="utf-8") as f:
                    json.dump(between_data, f, indent=2)
                successful += 1

            # Extract raw train items
            data_field = between_data.get("data", [])
            train_items = data_field if isinstance(data_field, list) else data_field.get("trains", [])
            total_between_trains_count = len(train_items)

            # Balanced selection from real trains-between response
            selected_trains, mix_counts = select_balanced_train_sample(
                train_items=train_items,
                max_trains=max_trains_per_section,
                preferred_all_stops=all_stops_train or ("64424" if sec_cfg.from_code == "NDLS" and sec_cfg.to_code == "GZB" else None),
                fallback_trains=fallback_list,
            )
            trains_per_section[sec_id] = selected_trains
            print(f"  ✓ Saved trains-between ({total_between_trains_count} trains found on corridor)")
            print(f"  ✓ Dynamic sample selected: {len(selected_trains)} trains (EMU/commuter: {mix_counts.get('commuter', 0)}, express: {mix_counts.get('express', 0)}, goods: {mix_counts.get('goods', 0)})")
        except Exception as e:
            logger.warning("Trains-between failed for %s-%s: %s (no file written). Falling back to seed list.", sec_cfg.from_code, sec_cfg.to_code, e)
            trains_per_section[sec_id] = fallback_list[:max_trains_per_section]
            failed += 1

    # 2. Fetch route geometry for ONE train per pilot corridor
    print("\n[2/3] Fetching corridor route geometries (1 train per pilot corridor)...")
    for corridor_name, geo_train in PILOT_CORRIDOR_GEOMETRY_TRAINS.items():
        if corridor_name not in {sec.corridor_name for sec in pilot_sections.values()}:
            continue
        print(f"  Fetching geometry for {corridor_name} (Train {geo_train})...")
        try:
            route_data = client.get_train_route(geo_train)
            if route_data.get("source") != "live":
                raise RailRadarError(f"Route for train {geo_train} was served from fallback snapshot, not live network")

            ts = datetime.now(timezone.utc).isoformat()
            route_data["provenance"] = "live"
            route_data["snapshot_timestamp"] = ts
            route_data["illustrative"] = False
            if "meta" not in route_data or not isinstance(route_data["meta"], dict):
                route_data["meta"] = {}
            route_data["meta"]["provenance"] = "live"
            route_data["meta"]["snapshot_timestamp"] = ts
            route_data["meta"]["illustrative"] = False

            out_file = output_dir / f"train_{geo_train}_route.json"
            if _verify_can_safely_write(out_file, incoming_is_live=True):
                with open(out_file, "w", encoding="utf-8") as f:
                    json.dump(route_data, f, indent=2)
                successful += 1
                print(f"  ✓ Saved geometry snapshot: {out_file.name}")
        except Exception as e:
            logger.warning("Geometry fetch failed for train %s: %s (no file written)", geo_train, e)
            failed += 1

    # 3. Fetch timetables for selected unique trains
    all_unique_trains = list(dict.fromkeys([t for t_list in trains_per_section.values() for t in t_list]))
    print(f"\n[3/3] Fetching timetables for {len(all_unique_trains)} unique trains...")

    fetched_train_numbers: List[str] = []
    for idx, t_num in enumerate(all_unique_trains, 1):
        print(f"  [{idx}/{len(all_unique_trains)}] Fetching timetable for train {t_num}...")
        try:
            timetable_data = client.get_train_timetable(t_num)
            if timetable_data.get("source") != "live":
                raise RailRadarError(f"Timetable for train {t_num} was served from fallback snapshot, not live network")

            ts = datetime.now(timezone.utc).isoformat()
            timetable_data["provenance"] = "live"
            timetable_data["snapshot_timestamp"] = ts
            timetable_data["illustrative"] = False
            if "meta" not in timetable_data or not isinstance(timetable_data["meta"], dict):
                timetable_data["meta"] = {}
            timetable_data["meta"]["provenance"] = "live"
            timetable_data["meta"]["snapshot_timestamp"] = ts
            timetable_data["meta"]["illustrative"] = False

            out_file = output_dir / f"train_{t_num}_timetable.json"
            if _verify_can_safely_write(out_file, incoming_is_live=True):
                with open(out_file, "w", encoding="utf-8") as f:
                    json.dump(timetable_data, f, indent=2)
                successful += 1
                fetched_train_numbers.append(t_num)
                print(f"  ✓ Saved live timetable: {out_file.name}")
        except Exception as e:
            logger.warning("Timetable fetch failed for train %s: %s (no file written)", t_num, e)
            failed += 1

    # Final summary & usage reporting
    session = get_session(engine)
    after_counts = get_all_key_usages(session)
    session.close()

    print("\n" + "=" * 65)
    print("FETCH SUMMARY REPORT")
    print("=" * 65)
    print(f"Trains-between total count: {total_between_trains_count} trains running between pilot stations")
    print(f"Trains fetched live:        {len(fetched_train_numbers)} ({', '.join(fetched_train_numbers)})")
    print(f"Failed calls:               {failed}")
    print("-" * 65)

    # Known vs total trains per block section & date
    print("KNOWN VS TOTAL TRAINS PER BLOCK SECTION & DATE (TODAY):")
    try:
        from traffic.passages import load_pilot_block_passages
        from traffic.block_sections import get_all_pilot_block_sections
        for p_id, p_sec in pilot_sections.items():
            b_secs = get_all_pilot_block_sections(pilot_section_id=p_id)
            passages = load_pilot_block_passages(pilot_section_id=p_id, target_date=date.today())
            trains_per_bs: Dict[str, Set[str]] = {}
            for p in passages:
                trains_per_bs.setdefault(p.block_section_id, set()).add(p.train_no)

            print(f"Section {p_sec.name} ({date.today().isoformat()}):")
            for bs in b_secs:
                known_count = len(trains_per_bs.get(bs.id, set()))
                print(f"  - {bs.id} ({bs.name} {bs.line}): {known_count} known timetable train(s) (corridor total: {len(fetched_train_numbers)})")
    except Exception as e:
        logger.debug("Passage breakdown calculation skipped: %s", e)

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
    parser.add_argument("--section", type=str, default=None, help="Filter to specific section (e.g. SEC-93135bb9 or NDLS-GZB)")
    parser.add_argument("--all-stops", type=str, default=None, help="Specific all-stops passenger/MEMU train number (e.g. 64424)")
    parser.add_argument("--max-trains", type=int, default=16, help="Max trains per pilot section (default: 16)")
    parser.add_argument("--dry-run", action="store_true", help="Print call plan and budget projection without network calls")
    parser.add_argument("--dir", type=str, default=str(PROJECT_ROOT / "data" / "railradar_snapshots"), help="Output directory")

    args = parser.parse_args()
    snapshot_pilot_railradar(
        Path(args.dir),
        max_trains_per_section=args.max_trains,
        dry_run=args.dry_run,
        section_filter=args.section,
        all_stops_train=args.all_stops,
    )
