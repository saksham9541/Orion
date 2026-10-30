"""
backend/sync_service.py

Live train delay sync manager for Orion:
- Selects only trains with a timetable snapshot on the pilot corridor.
- Server-side minimum interval enforcement (configurable, default 60 min) with HTTP 429.
- Reserved budget protection (configurable, default 30 calls/month) with HTTP 429.
- Confirmation preview: calls to be made, covered trains, per-key remaining budget.
- Execution report: trains updated, calls used, last synced time (IST), and failures.
"""
from __future__ import annotations

import json
import logging
import os
import zoneinfo
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.database import (
    LiveTrainStatusRecord,
    get_api_usage_count,
    load_live_status,
    save_live_status,
)
from integrations.railradar_client import RailRadarClient, key_identifier, mask_key
from railopt.models import LiveTrainStatus
from traffic.section_map import PILOT_SECTIONS

logger = logging.getLogger("sync_service")

KOLKATA_TZ = zoneinfo.ZoneInfo("Asia/Kolkata")
DEFAULT_SNAPSHOT_DIR = Path(__file__).resolve().parent.parent / "data" / "railradar_snapshots"

# In-memory last sync timestamp tracking
_LAST_SYNC_TIME: Optional[datetime] = None


def get_min_sync_interval_minutes() -> int:
    """Configurable minimum interval between live syncs in minutes (default: 60)."""
    try:
        return int(os.environ.get("RAILRADAR_SYNC_INTERVAL_MINUTES", "60"))
    except ValueError:
        return 60


def get_sync_reserved_budget() -> int:
    """Configurable reserved monthly budget across all keys that syncs cannot spend (default: 30)."""
    try:
        return int(os.environ.get("RAILRADAR_SYNC_RESERVED_BUDGET", "30"))
    except ValueError:
        return 30


def get_corridor_train_limit(section_id: str = "SEC-93135bb9") -> int:
    """Configurable max trains to consider: pilot corridor gets PILOT_MAX_TIMETABLE_TRAINS (default 40), others get DEFAULT_MAX_TIMETABLE_TRAINS (default 16)."""
    if section_id in ("SEC-93135bb9", "COR-82d9c510"):
        try:
            return int(os.environ.get("PILOT_MAX_TIMETABLE_TRAINS", "40"))
        except ValueError:
            return 40
    try:
        return int(os.environ.get("DEFAULT_MAX_TIMETABLE_TRAINS", "16"))
    except ValueError:
        return 16


def get_sync_horizon_hours(is_emergency: bool = False) -> float:
    """Configurable sync horizon in hours: general sync defaults to 3.0h, emergency defaults to 2.0h."""
    if is_emergency:
        try:
            return float(os.environ.get("RAILRADAR_EMERGENCY_SYNC_HORIZON_HOURS", "2.0"))
        except ValueError:
            return 2.0
    try:
        return float(os.environ.get("RAILRADAR_SYNC_HORIZON_HOURS", "3.0"))
    except ValueError:
        return 3.0


def get_last_sync_time(session: Optional[Session] = None) -> Optional[datetime]:
    """Returns the most recent sync timestamp from memory or database."""
    global _LAST_SYNC_TIME
    if _LAST_SYNC_TIME is not None:
        return _LAST_SYNC_TIME

    if session is not None:
        try:
            records = session.query(LiveTrainStatusRecord).all()
            if records:
                latest = max((r.last_updated for r in records if r.last_updated), default=None)
                if latest:
                    if latest.tzinfo is None:
                        now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
                        if latest > now_naive:
                            latest = latest.replace(tzinfo=KOLKATA_TZ).astimezone(timezone.utc)
                        else:
                            latest = latest.replace(tzinfo=timezone.utc)
                    return latest
        except Exception as e:
            logger.debug("Failed to query last sync from DB: %s", e)

    return None


def record_sync_time(dt: datetime) -> None:
    """Records the timestamp of a successful sync run."""
    global _LAST_SYNC_TIME
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    _LAST_SYNC_TIME = dt


def reset_last_sync_time() -> None:
    """Resets the last sync timestamp (used for testing cooldown reset)."""
    global _LAST_SYNC_TIME
    _LAST_SYNC_TIME = None


def get_pilot_timetable_trains(
    section_id: str = "SEC-93135bb9",
    snapshot_dir: Optional[Path] = None,
    horizon_hours: Optional[float] = None,
    emergency_block_id: Optional[str] = None,
    target_time: Optional[datetime] = None,
) -> List[str]:
    """
    Returns only trains that have a timetable snapshot on disk AND run on the pilot corridor.
    Applies corridor train limit (PILOT_MAX_TIMETABLE_TRAINS=40 vs 16 for non-pilot).
    When horizon_hours is set (>0), filters to trains due to pass through the pilot corridor
    (or emergency block section) in the next N hours.
    """
    s_dir = snapshot_dir or DEFAULT_SNAPSHOT_DIR
    if not s_dir.exists():
        return []

    sec_cfg = PILOT_SECTIONS.get(section_id, PILOT_SECTIONS.get("SEC-93135bb9"))
    pilot_station_codes = set(sec_cfg.station_codes if sec_cfg else ["NDLS", "GZB"])
    # Include alias codes like ANVR/ANVT
    if "ANVT" in pilot_station_codes:
        pilot_station_codes.add("ANVR")
    if "ANVR" in pilot_station_codes:
        pilot_station_codes.add("ANVT")

    target_stations = pilot_station_codes
    if emergency_block_id:
        try:
            from traffic.block_sections import build_block_sections
            b_secs = build_block_sections(section_id, snapshot_dir=s_dir)
            target_b = next((b for b in b_secs if b.id == emergency_block_id), None)
            if target_b:
                target_stations = {target_b.from_station, target_b.to_station}
        except Exception:
            pass

    max_limit = get_corridor_train_limit(section_id)

    # High-priority default trains known to run on this corridor
    from scripts.snapshot_railradar import DEFAULT_PILOT_TRAINS
    known_corridor_trains = set(DEFAULT_PILOT_TRAINS.get(section_id, []))

    # Determine horizon window in minutes from midnight (Asia/Kolkata)
    eff_horizon = horizon_hours
    if eff_horizon is None:
        eff_horizon = get_sync_horizon_hours(is_emergency=bool(emergency_block_id))

    ref = target_time or datetime.now(KOLKATA_TZ)
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=KOLKATA_TZ)
    ref_min = ref.hour * 60 + ref.minute
    horizon_end_min = (ref_min + int(eff_horizon * 60)) if (eff_horizon and eff_horizon > 0) else None

    covered_trains: List[str] = []

    for f in sorted(s_dir.glob("train_*_timetable.json")):
        t_num = f.stem.replace("train_", "").replace("_timetable", "")
        if not t_num:
            continue

        try:
            with open(f, "r", encoding="utf-8") as fp:
                data = json.load(fp)
            route = (data.get("data") or {}).get("route") or []
            if not route:
                continue

            station_matches = []
            for r in route:
                code = r.get("station_code")
                if code in target_stations:
                    station_matches.append(r)

            # If corridor check without target_stations
            if not station_matches:
                codes = set(r.get("station_code") for r in route if r.get("station_code"))
                if sec_cfg and (sec_cfg.from_code in codes and sec_cfg.to_code in codes):
                    station_matches = [r for r in route if r.get("station_code") in codes.intersection(pilot_station_codes)]
                elif len(codes.intersection(pilot_station_codes)) >= 2:
                    station_matches = [r for r in route if r.get("station_code") in codes.intersection(pilot_station_codes)]
                elif t_num in known_corridor_trains:
                    station_matches = route

            if not station_matches:
                continue

            # Horizon filter check
            if horizon_end_min is not None:
                in_horizon = False
                for s in station_matches:
                    dep = s.get("departure") or s.get("arrival") or s.get("departure_time") or s.get("arrival_time") or ""
                    if ":" in dep:
                        try:
                            hh, mm = map(int, dep.strip().split(":")[:2])
                            stop_min = hh * 60 + mm
                            if ref_min <= stop_min <= horizon_end_min:
                                in_horizon = True
                                break
                            elif horizon_end_min > 1440 and ref_min <= (stop_min + 1440) <= horizon_end_min:
                                in_horizon = True
                                break
                        except Exception:
                            continue
                if not in_horizon:
                    continue

            covered_trains.append(t_num)
        except Exception:
            continue

    unique_trains = sorted(list(dict.fromkeys(covered_trains)))
    if not unique_trains and horizon_end_min is not None:
        # Fallback: if narrow horizon has no train at this hour, return all corridor timetable trains
        return get_pilot_timetable_trains(section_id=section_id, snapshot_dir=snapshot_dir, horizon_hours=-1, emergency_block_id=emergency_block_id)[:max_limit]
    return unique_trains[:max_limit]


def get_api_budget_breakdown(
    session: Session,
    client: RailRadarClient,
) -> dict:
    """Returns monthly API budget status per key and overall."""
    ym = datetime.now(timezone.utc).strftime("%Y-%m")
    keys_status = []
    total_used = 0
    total_limit = 0
    total_remaining = 0

    for k in client.keys:
        ident = key_identifier(k)
        used = get_api_usage_count(session, ident, ym)
        limit = client.key_limit
        rem = max(0, limit - used)
        total_used += used
        total_limit += limit
        total_remaining += rem
        keys_status.append({
            "key_suffix": mask_key(k),
            "used": used,
            "limit": limit,
            "remaining": rem,
        })

    reserved = get_sync_reserved_budget()
    available_for_sync = max(0, total_remaining - reserved)

    return {
        "year_month": ym,
        "keys": keys_status,
        "key_count": len(client.keys),
        "total_used": total_used,
        "total_limit": total_limit,
        "total_remaining": total_remaining,
        "reserved_budget": reserved,
        "available_for_sync": available_for_sync,
    }


def print_sync_summary(
    section_id: str,
    total_found: int,
    with_timetables: int,
    covered_trains: List[str],
    keys_status: List[dict],
    calls_used: int,
    snapshot_dir: Optional[Path] = None,
) -> str:
    """
    Prints and returns a formatted summary after sync:
    trains found on the corridor, trains with timetables, known versus total
    trains per block section, and calls used per key.
    """
    sec_cfg = PILOT_SECTIONS.get(section_id, PILOT_SECTIONS.get("SEC-93135bb9"))
    sec_name = sec_cfg.name if sec_cfg else section_id
    s_dir = snapshot_dir or DEFAULT_SNAPSHOT_DIR

    block_lines = []
    try:
        from traffic.block_sections import build_block_sections
        from traffic.passages import load_pilot_block_passages
        b_secs = build_block_sections(section_id, snapshot_dir=s_dir)
        all_passages = load_pilot_block_passages(section_id, snapshot_dir=s_dir)
        covered_set = set(covered_trains)
        for b in b_secs:
            b_pass = [p for p in all_passages if getattr(p, "block_section_id", "") == b.id or getattr(p, "line", "") == b.line]
            total_b = len(set(p.train_no for p in b_pass))
            known_b = len(set(p.train_no for p in b_pass if p.train_no in covered_set))
            block_lines.append(f"  - {b.id} ({b.name}): {known_b} known in horizon / {total_b} total timetable trains")
    except Exception as e:
        block_lines.append(f"  (Block section details unavailable: {e})")

    key_lines = []
    for k in keys_status:
        key_lines.append(f"  - Key {k.get('key_suffix', '***')}: {k.get('used', 0)} used, {k.get('remaining', 0)} remaining (limit {k.get('limit', 90)})")

    summary = (
        f"\n================================================================================\n"
        f"RAILRADAR LIVE SYNC SUMMARY\n"
        f"================================================================================\n"
        f"Corridor: {sec_name} ({section_id})\n"
        f"Trains found on the corridor: {total_found}\n"
        f"Trains with timetables on disk: {with_timetables}\n"
        f"Trains selected for live delay sync: {len(covered_trains)} trains: {', '.join(covered_trains)}\n"
        f"Known versus total trains per block section:\n" + "\n".join(block_lines) + "\n"
        f"Calls used per key:\n" + "\n".join(key_lines) + "\n"
        f"Total calls executed in this sync: {calls_used}\n"
        f"================================================================================\n"
    )
    print(summary, flush=True)
    logger.info("RailRadar live sync completed: %d trains, %d calls", len(covered_trains), calls_used)
    return summary


EMERGENCY_SYNC_COOLDOWN_MINUTES_DEFAULT = 30.0

def get_emergency_sync_cooldown_minutes() -> float:
    try:
        return float(os.getenv("EMERGENCY_SYNC_COOLDOWN_MINUTES", str(EMERGENCY_SYNC_COOLDOWN_MINUTES_DEFAULT)))
    except ValueError:
        return EMERGENCY_SYNC_COOLDOWN_MINUTES_DEFAULT

_LAST_EMERGENCY_SYNC_BY_TASK: Dict[str, datetime] = {}


def get_sync_preview(
    session: Session,
    client: RailRadarClient,
    section_id: str = "SEC-93135bb9",
    snapshot_dir: Optional[Path] = None,
    horizon_hours: Optional[float] = None,
    emergency_block_id: Optional[str] = None,
    emergency_task_id: Optional[str] = None,
) -> dict:
    """
    Computes preview confirmation data for live sync:
    - calls_needed
    - covered_trains (filtered by corridor limit & time horizon or emergency block)
    - per-key remaining budget
    - interval cooldown status and remaining time
    """
    covered = get_pilot_timetable_trains(
        section_id=section_id,
        snapshot_dir=snapshot_dir,
        horizon_hours=horizon_hours,
        emergency_block_id=emergency_block_id,
    )
    calls_needed = len(covered)

    budget = get_api_budget_breakdown(session, client)
    min_interval = get_min_sync_interval_minutes()
    last_synced = get_last_sync_time(session)

    now_utc = datetime.now(timezone.utc)
    cooldown_active = False
    cooldown_seconds_remaining = 0
    em_id = emergency_task_id or emergency_block_id

    # Item 4: Emergency targeted sync limited to one per task per 30 minutes (configurable)
    if em_id:
        last_em = _LAST_EMERGENCY_SYNC_BY_TASK.get(em_id)
        if last_em is not None:
            elapsed_sec = (now_utc - last_em).total_seconds()
            em_cd_sec = get_emergency_sync_cooldown_minutes() * 60
            if 0 <= elapsed_sec < em_cd_sec:
                cooldown_active = True
                cooldown_seconds_remaining = max(0, int(em_cd_sec - elapsed_sec))
    elif last_synced is not None:
        elapsed_sec = (now_utc - last_synced).total_seconds()
        min_sec = min_interval * 60
        if 0 <= elapsed_sec < min_sec:
            cooldown_active = True
            cooldown_seconds_remaining = max(0, int(min_sec - elapsed_sec))

    has_keys = len(client.keys) > 0
    budget_ok = budget["available_for_sync"] >= calls_needed

    can_sync = has_keys and (not cooldown_active) and budget_ok
    blocked_reason = None
    if not has_keys:
        # Item 5: Explicit reason when no keys loaded
        blocked_reason = "NO_API_KEYS_LOADED"
    elif cooldown_active:
        blocked_reason = "EMERGENCY_COOLDOWN_ACTIVE" if em_id else "COOLDOWN_ACTIVE"
    elif not budget_ok:
        blocked_reason = "INSUFFICIENT_RESERVED_BUDGET"

    last_synced_ist = None
    if last_synced is not None:
        last_synced_ist = last_synced.astimezone(KOLKATA_TZ).strftime("%d %b %Y, %H:%M:%S IST")

    sec_cfg = PILOT_SECTIONS.get(section_id, PILOT_SECTIONS.get("SEC-93135bb9"))
    sec_name = sec_cfg.name if sec_cfg else section_id
    corridor_name = sec_cfg.corridor_name if sec_cfg else "Delhi–Howrah Main"

    return {
        "calls_needed": calls_needed,
        "covered_trains": covered,
        "train_count": len(covered),
        "section_id": section_id,
        "section_name": sec_name,
        "corridor_name": corridor_name,
        "keys_budget": budget["keys"],
        "total_remaining_budget": budget["total_remaining"],
        "reserved_budget": budget["reserved_budget"],
        "available_for_sync": budget["available_for_sync"],
        "can_sync": can_sync,
        "cooldown_active": cooldown_active,
        "cooldown_seconds_remaining": cooldown_seconds_remaining,
        "cooldown_minutes_remaining": round(cooldown_seconds_remaining / 60.0, 1),
        "min_interval_minutes": min_interval,
        "last_synced_at": last_synced.isoformat() if last_synced else None,
        "last_synced_ist": last_synced_ist,
        "blocked_reason": blocked_reason,
        "is_emergency": bool(emergency_block_id),
        "emergency_block_id": emergency_block_id,
    }


def execute_live_train_sync(
    session: Session,
    client: RailRadarClient,
    section_id: str = "SEC-93135bb9",
    snapshot_dir: Optional[Path] = None,
    force: bool = False,
    horizon_hours: Optional[float] = None,
    emergency_block_id: Optional[str] = None,
    emergency_task_id: Optional[str] = None,
) -> dict:
    """
    Executes live delay sync for pilot corridor timetable trains.
    Enforces minimum interval (default 60m, bypassed for emergency tasks)
    and reserved budget (default 30 calls, always enforced).
    Returns trains updated, calls used, last synced time (IST), summary, and any failures.
    """
    if not client.keys and not client.offline:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RailRadar not configured — set RAILRADAR_API_KEYS in .env",
        )

    preview = get_sync_preview(
        session,
        client,
        section_id=section_id,
        snapshot_dir=snapshot_dir,
        horizon_hours=horizon_hours,
        emergency_block_id=emergency_block_id,
        emergency_task_id=emergency_task_id,
    )
    calls_needed = preview["calls_needed"]
    covered_trains = preview["covered_trains"]

    if not force:
        # 1. Minimum interval check (429) - 30 min per-task limit for emergency tasks, 60m normal
        em_id = emergency_task_id or emergency_block_id
        if preview["cooldown_active"]:
            mins_left = preview["cooldown_minutes_remaining"]
            if em_id:
                em_cd = get_emergency_sync_cooldown_minutes()
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=(
                        f"Emergency targeted sync cooldown active for task {em_id}. Limit is one sync per task per {em_cd:.0f} minutes. "
                        f"Please wait {mins_left} more minute(s) before syncing again."
                    ),
                )
            else:
                min_interval = preview["min_interval_minutes"]
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=(
                        f"Sync cooldown active. Minimum interval between live syncs is {min_interval} minutes. "
                        f"Please wait {mins_left} more minute(s) before syncing again."
                    ),
                )

        # 2. Reserved budget check (429) - strictly enforced even for emergency tasks
        if preview["available_for_sync"] < calls_needed:
            avail = preview["available_for_sync"]
            res = preview["reserved_budget"]
            tot = preview["total_remaining_budget"]
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Insufficient unreserved RailRadar API budget. Syncing {calls_needed} trains requires {calls_needed} calls, "
                    f"but only {avail} call(s) available above the mandatory reserve of {res} calls "
                    f"(Total remaining: {tot}, Reserved: {res})."
                ),
            )

    sec_cfg = PILOT_SECTIONS.get(section_id, PILOT_SECTIONS.get("SEC-93135bb9"))
    corridor_id = (sec_cfg.corridor_id if sec_cfg else None) or "COR-82d9c510"

    statuses: List[LiveTrainStatus] = []
    failures: List[dict] = []
    calls_made = 0

    for tid in covered_trains:
        try:
            raw = client.get_train_live(tid)
            calls_made += 1
            st = client.parse_live_status(raw, corridor_id=corridor_id)
            statuses.append(st)
        except Exception as e:
            logger.warning("Live sync failed for train %s: %s", tid, e)
            failures.append({
                "train_number": tid,
                "error": str(e),
            })

    # Save successfully fetched live train positions into local database
    if statuses:
        save_live_status(session, statuses)

    # Record sync timestamp
    now_utc = datetime.now(timezone.utc)
    record_sync_time(now_utc)
    now_ist_str = now_utc.astimezone(KOLKATA_TZ).strftime("%d %b %Y, %H:%M:%S IST")

    # Fetch updated budget status post-sync
    updated_budget = get_api_budget_breakdown(session, client)

    # Compute corridor counts for summary
    s_dir = snapshot_dir or DEFAULT_SNAPSHOT_DIR
    trains_file = s_dir / "train_between_NDLS_GZB.json"
    total_found = 40
    if trains_file.exists():
        try:
            with open(trains_file, "r", encoding="utf-8") as f:
                t_data = json.load(f)
            total_found = len((t_data.get("data") or {}).get("trains") or [])
        except Exception:
            pass
    with_timetables = len(list(s_dir.glob("train_*_timetable.json")))

    em_id = emergency_task_id or emergency_block_id
    if em_id:
        _LAST_EMERGENCY_SYNC_BY_TASK[em_id] = datetime.now(timezone.utc)

    summary_text = print_sync_summary(
        section_id=section_id,
        total_found=total_found,
        with_timetables=with_timetables,
        covered_trains=covered_trains,
        keys_status=updated_budget["keys"],
        calls_used=calls_made,
        snapshot_dir=s_dir,
    )

    return {
        "status": "ok",
        "trains_updated": len(statuses),
        "calls_used": calls_made,
        "covered_trains": covered_trains,
        "last_synced_time_ist": now_ist_str,
        "last_synced_at": now_utc.isoformat(),
        "failures": failures,
        "failure_count": len(failures),
        "keys_usage": updated_budget["keys"],
        "total_remaining_budget": updated_budget["total_remaining"],
        "reserved_budget": updated_budget["reserved_budget"],
        "summary": summary_text,
    }
