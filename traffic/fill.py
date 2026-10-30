"""
traffic/fill.py

Generates labeled synthetic filler passages (source="synthetic_fill" and source="synthetic_goods")
so total daily trains match the track section's density class.
Operates at both:
1. Block-Section Level (directional UP/DN, realistic hourly profiles)
2. Section Level (legacy compatibility)

Exposes coverage metric: real_live_trains / total_trains (strictly provenance='live').
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    from zoneinfo import ZoneInfo
    KOLKATA_TZ = ZoneInfo("Asia/Kolkata")
except Exception:
    KOLKATA_TZ = timezone(timedelta(hours=5, minutes=30))

from railopt.models import TrafficDensityClass, TrainType
from traffic.block_sections import BlockSection, build_block_sections
from traffic.passages import (
    BlockSectionPassage,
    TrainPassage,
    load_pilot_block_passages,
    load_pilot_passages,
)
from traffic.section_map import get_pilot_section_config, PilotSectionConfig

TARGET_DAILY_TRAINS_BY_DENSITY: Dict[str, int] = {
    "A_SPECIAL": 70,
    "A": 50,
    "B": 30,
    "C": 15,
    "D": 6,
}

# Realistic 24-hour traffic density profiles (hourly weights 0..23 summing to ~1.0)
# Passenger traffic: lower at night (01:00-05:00), peaks at morning/evening rush hours
DEFAULT_PASSENGER_HOURLY_WEIGHTS: List[float] = [
    0.02, 0.01, 0.01, 0.01, 0.02, 0.05, 0.07, 0.08, 0.07, 0.06,
    0.05, 0.05, 0.05, 0.05, 0.06, 0.07, 0.08, 0.07, 0.05, 0.04,
    0.03, 0.03, 0.02, 0.02
]

# Goods traffic: runs around the clock, with higher density at night (22:00-06:00) when passenger slots open
DEFAULT_GOODS_HOURLY_WEIGHTS: List[float] = [
    0.06, 0.06, 0.06, 0.06, 0.05, 0.04, 0.03, 0.03, 0.03, 0.03,
    0.03, 0.03, 0.03, 0.03, 0.04, 0.04, 0.04, 0.04, 0.04, 0.05,
    0.05, 0.06, 0.06, 0.06
]


@dataclass
class FillerConfig:
    """
    Configuration for synthetic filler train generation.
    
    Night-protection hack is disabled by default:
    - night_maintenance_corridor: bool = False
      When False, realistic 24h hourly profiles are used including night traffic.
      When True (explicit scenario switch), passenger slots between 01:00 and 04:59
      are cleared to simulate Indian Railways nocturnal engineering block windows.
    """
    night_maintenance_corridor: bool = False
    passenger_operational_hours: Optional[List[int]] = None
    goods_operational_hours: Optional[List[int]] = None
    goods_ratio: float = 0.28
    restrict_passenger_to_operational_hours: bool = False
    restrict_goods_to_operational_hours: bool = False
    passenger_hourly_weights: Optional[List[float]] = None
    goods_hourly_weights: Optional[List[float]] = None


@dataclass
class SectionCoverageSummary:
    """Summary of real vs synthetic train distribution on a section."""
    section_id: str
    date: str
    real_trains: int
    synthetic_fill_trains: int
    synthetic_goods_trains: int
    total_trains: int
    coverage_ratio: float
    coverage_pct: float


@dataclass
class BlockCoverageSummary:
    """Detailed provenance & coverage breakdown for a specific BlockSection."""
    block_section_id: str = ""
    line: str = "DN"
    date: str = ""
    real_live_trains: int = 0         # Only provenance='live' counts as real
    hand_written_trains: int = 0      # Provenance='hand_written' (illustrative)
    synthetic_fill_trains: int = 0    # Synthetic passenger filler
    synthetic_goods_trains: int = 0   # Synthetic goods filler
    total_trains: int = 0
    coverage_ratio: float = 0.0       # real_live_trains / total_trains
    coverage_pct: float = 0.0
    is_live_data: bool = False
    provenance_label: str = "illustrative"


def _sample_hour_from_weights(rng: random.Random, weights: List[float]) -> int:
    """Samples an hour (0..23) weighted by the hourly profile."""
    cum_weights = []
    total = 0.0
    for w in weights:
        total += max(0.001, w)
        cum_weights.append(total)
    r = rng.uniform(0.0, total)
    for h, cw in enumerate(cum_weights):
        if r <= cw:
            return h
    return 12


# ----------------------------------------------------------------------
# Block-Section Level Filler Generation
# ----------------------------------------------------------------------

def generate_block_section_filler(
    block_section: BlockSection,
    target_date: date,
    needed_count: int,
    seed: int = 42,
    config: Optional[FillerConfig] = None,
) -> List[BlockSectionPassage]:
    """
    Generates synthetic filler and goods passages for a specific BlockSection.
    Passages are strictly directional (matching block_section.line),
    tagged with provenance="synthetic", and use realistic 24-hour hourly profiles.
    """
    if needed_count <= 0:
        return []

    cfg = config or FillerConfig()

    # Deterministic date seed
    date_seed = seed + int(target_date.strftime("%Y%m%d")) + hash(block_section.id) % 10000
    rng = random.Random(date_seed)

    fillers: List[BlockSectionPassage] = []

    # Transit time through block section (at least 2 minutes)
    speed_kmh = max(50.0, block_section.max_speed * 0.75)
    transit_mins = max(2.0, (block_section.length_km / speed_kmh) * 60.0)

    goods_count = max(1, int(needed_count * cfg.goods_ratio))

    # Determine hourly weights
    p_weights = list(cfg.passenger_hourly_weights or DEFAULT_PASSENGER_HOURLY_WEIGHTS)
    g_weights = list(cfg.goods_hourly_weights or DEFAULT_GOODS_HOURLY_WEIGHTS)

    # If night maintenance corridor scenario switch is enabled, suppress passenger night hours 01..04
    if cfg.night_maintenance_corridor or cfg.restrict_passenger_to_operational_hours:
        for h in range(1, 5):
            p_weights[h] = 0.0

    for i in range(needed_count):
        is_goods = i < goods_count
        source = "synthetic_goods" if is_goods else "synthetic_fill"
        t_type = TrainType.FREIGHT if is_goods else rng.choice([
            TrainType.PASSENGER, TrainType.SUBURBAN, TrainType.MAIL_EXPRESS, TrainType.SUPERFAST
        ])

        hour = _sample_hour_from_weights(rng, g_weights if is_goods else p_weights)
        minute = rng.randint(0, 59)
        second = rng.randint(0, 59)

        enter_dt = datetime.combine(target_date, time(hour, minute, second), tzinfo=KOLKATA_TZ)
        dur_mins = max(2.0, transit_mins * rng.uniform(0.9, 1.3))
        exit_dt = enter_dt + timedelta(minutes=dur_mins)

        prefix = "GDS" if is_goods else "FLR"
        t_num = f"{prefix}-{rng.randint(1000, 9999)}"
        t_name = f"Synthetic Freight {t_num}" if is_goods else f"Synthetic Passenger {t_num}"

        p = BlockSectionPassage(
            train_no=t_num,
            train_name=t_name,
            train_type=t_type,
            block_section_id=block_section.id,
            line=block_section.line,
            enter_datetime=enter_dt,
            exit_datetime=exit_dt,
            enter_time=enter_dt.time(),
            exit_time=exit_dt.time(),
            interpolated=True,
            provenance="synthetic",
            origin_date=target_date,
            block_date=target_date,
            source=source,
        )
        fillers.append(p)

    fillers.sort(key=lambda p: p.enter_datetime)
    return fillers


def get_all_block_section_passages(
    block_section: BlockSection,
    target_date: date,
    snapshot_dir=None,
    seed: int = 42,
    include_fill: bool = True,
    include_goods: bool = True,
    filler_config: Optional[FillerConfig] = None,
) -> Tuple[List[BlockSectionPassage], BlockCoverageSummary]:
    """
    Returns all train passages for a BlockSection on target_date, with configurable
    filler and goods.
    Strictly enforces: only provenance='live' trains count towards real coverage ratio.
    """
    # 1. Load real / snapshot passages for this block section
    raw_passages = load_pilot_block_passages(
        pilot_section_id=block_section.pilot_section_id,
        target_date=target_date,
        snapshot_dir=snapshot_dir,
    )
    existing_on_block = [p for p in raw_passages if p.block_section_id == block_section.id]

    # Target daily train quota for one line in A_SPECIAL corridor ~35 trains per line
    target_total = 35
    needed = max(0, target_total - len(existing_on_block))

    cfg = filler_config or FillerConfig()
    raw_fillers = generate_block_section_filler(
        block_section=block_section,
        target_date=target_date,
        needed_count=needed,
        seed=seed,
        config=cfg,
    )

    fillers: List[BlockSectionPassage] = []
    for f in raw_fillers:
        if f.source == "synthetic_goods" and include_goods:
            fillers.append(f)
        elif f.source == "synthetic_fill" and include_fill:
            fillers.append(f)

    all_passages = existing_on_block + fillers
    all_passages.sort(key=lambda p: p.enter_datetime)

    live_count = sum(1 for p in all_passages if p.provenance == "live")
    hand_written_count = sum(1 for p in all_passages if p.provenance == "hand_written")
    fill_count = sum(1 for p in all_passages if p.source == "synthetic_fill")
    goods_count = sum(1 for p in all_passages if p.source == "synthetic_goods")
    total_count = len(all_passages)

    cov_ratio = round(live_count / max(total_count, 1), 4)

    summary = BlockCoverageSummary(
        block_section_id=block_section.id,
        line=block_section.line,
        date=str(target_date),
        real_live_trains=live_count,
        hand_written_trains=hand_written_count,
        synthetic_fill_trains=fill_count,
        synthetic_goods_trains=goods_count,
        total_trains=total_count,
        coverage_ratio=cov_ratio,
        coverage_pct=round(cov_ratio * 100.0, 1),
        is_live_data=(live_count > 0),
    )

    return all_passages, summary


# ----------------------------------------------------------------------
# Section Level Filler Generation (Legacy Compatibility)
# ----------------------------------------------------------------------

DEFAULT_PASSENGER_HOURS: List[int] = [0, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23]
ALL_24_HOURS: List[int] = list(range(24))


def generate_filler_passages(
    sec_cfg: PilotSectionConfig,
    target_date: date,
    needed_count: int,
    seed: int = 42,
    config: Optional[FillerConfig] = None,
) -> List[TrainPassage]:
    """Legacy section-level filler generator."""
    if needed_count <= 0:
        return []

    cfg = config or FillerConfig()
    date_seed = seed + int(target_date.strftime("%Y%m%d")) + hash(sec_cfg.section_id) % 10000
    rng = random.Random(date_seed)

    fillers: List[TrainPassage] = []
    transit_mins = max(10.0, (sec_cfg.distance_km / sec_cfg.max_speed_kmh) * 60.0 * 1.3)

    goods_count = max(1, int(needed_count * cfg.goods_ratio))

    if cfg.restrict_passenger_to_operational_hours or cfg.night_maintenance_corridor:
        p_hours = cfg.passenger_operational_hours or DEFAULT_PASSENGER_HOURS
    else:
        p_hours = cfg.passenger_operational_hours or ALL_24_HOURS

    if cfg.restrict_goods_to_operational_hours:
        g_hours = cfg.goods_operational_hours or DEFAULT_PASSENGER_HOURS
    else:
        g_hours = cfg.goods_operational_hours or ALL_24_HOURS

    for i in range(needed_count):
        is_goods = i < goods_count
        source = "synthetic_goods" if is_goods else "synthetic_fill"
        t_type = TrainType.FREIGHT if is_goods else rng.choice([
            TrainType.PASSENGER, TrainType.SUBURBAN, TrainType.MAIL_EXPRESS, TrainType.SUPERFAST
        ])

        allowed_hours = g_hours if is_goods else p_hours
        hour = rng.choice(allowed_hours)
        minute = rng.randint(0, 59)
        t_enter = time(hour, minute)

        ref = target_date
        dt_exit = datetime.combine(ref, t_enter) + timedelta(minutes=int(transit_mins * rng.uniform(0.9, 1.4)))
        t_exit = dt_exit.time()

        prefix = "GDS" if is_goods else "FLR"
        t_num = f"{prefix}-{rng.randint(1000, 9999)}"
        t_name = f"Freight #{t_num}" if is_goods else f"Passenger Service #{t_num}"
        direction = rng.choice(["DN", "UP"])

        p = TrainPassage(
            train_no=t_num,
            train_name=t_name,
            train_type=t_type,
            section_id=sec_cfg.section_id,
            direction=direction,
            running_days=list(range(7)),
            enter_time=t_enter,
            exit_time=t_exit,
            interpolated=True,
            source=source,
        )
        fillers.append(p)

    return fillers


def get_all_passages_for_section(
    sec_cfg: PilotSectionConfig,
    target_date: date,
    snapshot_dir=None,
    seed: int = 42,
    include_fill: bool = True,
    include_goods: bool = True,
    filler_config: Optional[FillerConfig] = None,
) -> Tuple[List[TrainPassage], SectionCoverageSummary]:
    """Legacy section-level get_all_passages_for_section."""
    real_candidates = load_pilot_passages(sec_cfg, snapshot_dir=snapshot_dir)
    real_on_date = [p for p in real_candidates if p.runs_on_date(target_date)]

    target_total = TARGET_DAILY_TRAINS_BY_DENSITY.get(sec_cfg.density_class, 50)
    needed = max(0, target_total - len(real_on_date))

    raw_fillers = generate_filler_passages(sec_cfg, target_date, needed_count=needed, seed=seed, config=filler_config)

    fillers: List[TrainPassage] = []
    for p in raw_fillers:
        if p.source == "synthetic_goods" and include_goods:
            fillers.append(p)
        elif p.source == "synthetic_fill" and include_fill:
            fillers.append(p)

    all_passages = real_on_date + fillers
    all_passages.sort(key=lambda p: (p.enter_time.hour, p.enter_time.minute))

    goods_count = sum(1 for p in fillers if p.source == "synthetic_goods")
    fill_count = sum(1 for p in fillers if p.source == "synthetic_fill")
    real_count = len(real_on_date)
    total_count = len(all_passages)

    cov_ratio = (real_count / total_count) if total_count > 0 else 0.0
    summary = SectionCoverageSummary(
        section_id=sec_cfg.section_id,
        date=str(target_date),
        real_trains=real_count,
        synthetic_fill_trains=fill_count,
        synthetic_goods_trains=goods_count,
        total_trains=total_count,
        coverage_ratio=round(cov_ratio, 4),
        coverage_pct=round(cov_ratio * 100.0, 1),
    )

    return all_passages, summary
