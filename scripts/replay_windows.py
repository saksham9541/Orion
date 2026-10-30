"""
scripts/replay_windows.py

Replay engine that evaluates predicted-free block windows against real logged/live delays.
Calculates window hit rate, tracks train encroachments, and measures margin erosion under live operating conditions.

Usage:
    python scripts/replay_windows.py --date 2026-11-01
    python scripts/replay_windows.py --section SEC-93135bb9 --format json
    python scripts/replay_windows.py --window-id BW-e3a1f94b-20261101-01
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Dict, List, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from traffic.block_sections import (
    BlockSection,
    get_all_pilot_block_sections,
    get_block_section_by_id,
)
from traffic.passages import (
    BlockSectionPassage,
    load_pilot_block_passages,
    KOLKATA_TZ,
)
from traffic.window_finder import (
    BlockWindowConfig,
    find_block_section_windows,
    revalidate_window,
    UsableBlockWindow,
)
from backend.database import get_session, load_live_status


def load_synced_live_delays() -> Dict[str, float]:
    """Load latest synced live delay dictionary (train_no -> delay_minutes) from database."""
    delays: Dict[str, float] = {}
    try:
        with get_session() as s:
            records = load_live_status(s)
            for r in records:
                delays[r.train_number] = float(r.delay_minutes)
    except Exception as e:
        print(f"[WARN] Could not load live delays from database: {e}", file=sys.stderr)
    return delays


def run_replay(
    target_date: date,
    section_id: Optional[str] = None,
    specific_window_id: Optional[str] = None,
    task_duration_minutes: int = 90,
    delays_override: Optional[Dict[str, float]] = None,
) -> dict:
    """
    Replay live delays against predicted-free block windows.
    Returns structured metrics including window hit rate and encroachments.
    """
    live_delays = delays_override if delays_override is not None else load_synced_live_delays()
    block_sections = get_all_pilot_block_sections(section_id or "SEC-93135bb9")

    results = []
    total_windows = 0
    clean_windows = 0
    encroached_windows = 0
    total_margin_erosion = 0.0

    for b_sec in block_sections:
        free_windows = find_block_section_windows(
            b_sec,
            target_date=target_date,
            task_duration_minutes=task_duration_minutes,
        )

        for w in free_windows:
            if specific_window_id and w.window_id != specific_window_id:
                continue

            total_windows += 1
            reval = revalidate_window(
                b_sec,
                w,
                live_delays=live_delays,
            )

            is_clean = reval.is_valid
            encroachments = reval.conflicts
            erosion = sum(e.get("encroachment_minutes", 0.0) for e in encroachments)
            total_margin_erosion += erosion

            if is_clean:
                clean_windows += 1
            else:
                encroached_windows += 1

            results.append({
                "window_id": w.window_id,
                "block_section_id": b_sec.id,
                "block_section_name": b_sec.name,
                "line": w.line,
                "date": w.date.isoformat(),
                "predicted_start": w.recommended_start.strftime("%H:%M"),
                "predicted_end": w.recommended_end.strftime("%H:%M"),
                "comfort_label": w.comfort_label,
                "is_clean": is_clean,
                "status": reval.status,
                "encroaching_trains_count": len(encroachments),
                "margin_erosion_minutes": round(erosion, 1),
                "next_best_start": reval.next_best_start.strftime("%H:%M") if hasattr(reval.next_best_start, "strftime") else str(reval.next_best_start),
                "encroachments": encroachments,
            })

    hit_rate_pct = round((clean_windows / max(total_windows, 1)) * 100.0, 1)
    avg_erosion = round(total_margin_erosion / max(total_windows, 1), 1)

    return {
        "date": target_date.isoformat(),
        "task_duration_minutes": task_duration_minutes,
        "total_windows_evaluated": total_windows,
        "clean_windows_count": clean_windows,
        "encroached_windows_count": encroached_windows,
        "window_hit_rate_pct": hit_rate_pct,
        "average_margin_erosion_minutes": avg_erosion,
        "live_delays_tracked": len(live_delays),
        "windows": results,
    }


def main():
    parser = argparse.ArgumentParser(description="Replay live delays against predicted-free block windows.")
    parser.add_argument("--date", default=date.today().isoformat(), help="Target date YYYY-MM-DD (default: today)")
    parser.add_argument("--section", default="SEC-93135bb9", help="Pilot section ID (default: SEC-93135bb9)")
    parser.add_argument("--window-id", default=None, help="Filter to specific window ID")
    parser.add_argument("--duration", type=int, default=90, help="Task duration in minutes (default: 90)")
    parser.add_argument("--format", choices=["table", "json"], default="table", help="Output format (default: table)")
    args = parser.parse_args()

    target_d = date.fromisoformat(args.date)
    metrics = run_replay(
        target_date=target_d,
        section_id=args.section,
        specific_window_id=args.window_id,
        task_duration_minutes=args.duration,
    )

    if args.format == "json":
        print(json.dumps(metrics, indent=2))
        return

    # Table format
    print("\n" + "=" * 80)
    print(f" ORION MAINTENANCE WINDOW REPLAY ENGINE - {metrics['date']}")
    print("=" * 80)
    print(f"Total Windows Evaluated : {metrics['total_windows_evaluated']}")
    print(f"Clean Windows           : {metrics['clean_windows_count']}")
    print(f"Encroached Windows      : {metrics['encroached_windows_count']}")
    print(f"Window Hit Rate         : {metrics['window_hit_rate_pct']}%")
    print(f"Avg Margin Erosion      : {metrics['average_margin_erosion_minutes']} min")
    print(f"Live Delays Tracked     : {metrics['live_delays_tracked']} trains")
    print("-" * 80)
    print(f"{'WINDOW ID':<26} {'BLOCK SECTION':<18} {'TIME':<12} {'COMFORT':<12} {'STATUS':<10} {'EROSION'}")
    print("-" * 80)

    for w in metrics["windows"]:
        time_span = f"{w['predicted_start']}-{w['predicted_end']}"
        status_disp = "[PASS]" if w['is_clean'] else "[ENCROACHED]"
        print(f"{w['window_id']:<26} {w['block_section_name']:<18} {time_span:<12} {w['comfort_label']:<12} {status_disp:<10} {w['margin_erosion_minutes']}m")
        if not w['is_clean']:
            for enc in w["encroachments"]:
                print(f"  --> Encroaching Train {enc['train_no']} ({enc['train_name']}) entered at {enc['enter_time']}")

    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
