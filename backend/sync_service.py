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
) -> List[str]:
    """
    Returns only trains that have a timetable snapshot on disk AND run on the pilot corridor.
    Inspects data/railradar_snapshots/train_*_timetable.json.
    """
    s_dir = snapshot_dir or DEFAULT_SNAPSHOT_DIR
    if not s_dir.exists():
        return []

    sec_cfg = PILOT_SECTIONS.get(section_id, PILOT_SECTIONS["SEC-93135bb9"])
    pilot_station_codes = set(sec_cfg.station_codes)
    # Include alias codes like ANVR/ANVT
    if "ANVT" in pilot_station_codes:
        pilot_station_codes.add("ANVR")
    if "ANVR" in pilot_station_codes:
        pilot_station_codes.add("ANVT")

    # High-priority default trains known to run on this corridor
    from scripts.snapshot_railradar import DEFAULT_PILOT_TRAINS
    known_corridor_trains = set(DEFAULT_PILOT_TRAINS.get(section_id, []))

    covered_trains: List[str] = []

    for f in sorted(s_dir.glob("train_*_timetable.json")):
        t_num = f.stem.replace("train_", "").replace("_timetable", "")
        if not t_num:
            continue

        # Check if train belongs to pilot corridor
        if t_num in known_corridor_trains:
            covered_trains.append(t_num)
            continue

        try:
            with open(f, "r", encoding="utf-8") as fp:
                data = json.load(fp)
            route = (data.get("data") or {}).get("route") or []
            codes = set(r.get("station_code") for r in route if r.get("station_code"))
            # If route contains from_code and to_code or overlaps corridor stops
            if sec_cfg.from_code in codes and sec_cfg.to_code in codes:
                covered_trains.append(t_num)
            elif len(codes.intersection(pilot_station_codes)) >= 2:
                covered_trains.append(t_num)
        except Exception:
            continue

    return sorted(list(dict.fromkeys(covered_trains)))


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


def get_sync_preview(
    session: Session,
    client: RailRadarClient,
    section_id: str = "SEC-93135bb9",
    snapshot_dir: Optional[Path] = None,
) -> dict:
    """
    Computes preview confirmation data for live sync:
    - calls_needed
    - covered_trains (only trains with timetable snapshots on the pilot corridor)
    - per-key remaining budget
    - interval cooldown status and remaining time
    """
    covered = get_pilot_timetable_trains(section_id=section_id, snapshot_dir=snapshot_dir)
    calls_needed = len(covered)

    budget = get_api_budget_breakdown(session, client)
    min_interval = get_min_sync_interval_minutes()
    last_synced = get_last_sync_time(session)

    now_utc = datetime.now(timezone.utc)
    cooldown_active = False
    cooldown_seconds_remaining = 0

    if last_synced is not None:
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
        blocked_reason = "NO_API_KEYS_CONFIGURED"
    elif cooldown_active:
        blocked_reason = "COOLDOWN_ACTIVE"
    elif not budget_ok:
        blocked_reason = "INSUFFICIENT_RESERVED_BUDGET"

    last_synced_ist = None
    if last_synced is not None:
        last_synced_ist = last_synced.astimezone(KOLKATA_TZ).strftime("%d %b %Y, %H:%M:%S IST")

    sec_cfg = PILOT_SECTIONS.get(section_id, PILOT_SECTIONS["SEC-93135bb9"])

    return {
        "calls_needed": calls_needed,
        "covered_trains": covered,
        "train_count": len(covered),
        "section_id": section_id,
        "section_name": sec_cfg.name,
        "corridor_name": sec_cfg.corridor_name,
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
    }


def execute_live_train_sync(
    session: Session,
    client: RailRadarClient,
    section_id: str = "SEC-93135bb9",
    snapshot_dir: Optional[Path] = None,
    force: bool = False,
) -> dict:
    """
    Executes live delay sync for pilot corridor timetable trains.
    Enforces minimum interval (default 60m) and reserved budget (default 30 calls).
    Returns trains updated, calls used, last synced time (IST), and any failures.
    """
    if not client.keys and not client.offline:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RailRadar not configured — set RAILRADAR_API_KEYS in .env",
        )

    preview = get_sync_preview(session, client, section_id=section_id, snapshot_dir=snapshot_dir)
    calls_needed = preview["calls_needed"]
    covered_trains = preview["covered_trains"]

    if not force:
        # 1. Minimum interval check (429)
        if preview["cooldown_active"]:
            mins_left = preview["cooldown_minutes_remaining"]
            min_interval = preview["min_interval_minutes"]
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Sync cooldown active. Minimum interval between live syncs is {min_interval} minutes. "
                    f"Please wait {mins_left} more minute(s) before syncing again."
                ),
            )

        # 2. Reserved budget check (429)
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

    sec_cfg = PILOT_SECTIONS.get(section_id, PILOT_SECTIONS["SEC-93135bb9"])
    corridor_id = sec_cfg.corridor_id or "COR-82d9c510"

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
    }
