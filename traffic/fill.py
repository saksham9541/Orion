"""
traffic/fill.py

Generates labeled synthetic filler passages (source="synthetic_fill" and source="synthetic_goods")
so total daily trains match the track section's density class.
Exposes coverage metric: real_trains / total_trains per section.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Dict, List, Tuple

from railopt.models import TrafficDensityClass, TrainType
from traffic.passages import TrainPassage, load_pilot_passages
from traffic.section_map import get_pilot_section_config, PilotSectionConfig

TARGET_DAILY_TRAINS_BY_DENSITY: Dict[str, int] = {
    "A_SPECIAL": 70,
    "A": 50,
    "B": 30,
    "C": 15,
    "D": 6,
}


@dataclass
class FillerConfig:
    """
    Configuration for synthetic filler train generation.

    Default rationale:
    - passenger_operational_hours: defaults to [0, 5, 6, ..., 23] (excluding 01:00-04:59).
      Rationale: Indian Railways passenger timetables intentionally clear trunk corridors
      between 01:00 and 04:30 for engineering maintenance blocks.
    - goods_operational_hours: defaults to all 24 hours (0..23).
      Rationale: Freight paths run around the clock without fixed passenger schedules.
    """
    passenger_operational_hours: Optional[List[int]] = None
    goods_operational_hours: Optional[List[int]] = None
    goods_ratio: float = 0.28
    restrict_passenger_to_operational_hours: bool = True
    restrict_goods_to_operational_hours: bool = False


DEFAULT_PASSENGER_HOURS: List[int] = [0, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23]
ALL_24_HOURS: List[int] = list(range(24))


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


def generate_filler_passages(
    sec_cfg: PilotSectionConfig,
    target_date: date,
    needed_count: int,
    seed: int = 42,
    config: Optional[FillerConfig] = None,
) -> List[TrainPassage]:
    """
    Generate synthetic filler and goods train passages to reach the section density target.
    Passages are tagged as either 'synthetic_fill' or 'synthetic_goods'.
    Operational hours and goods hours are configurable.
    """
    if needed_count <= 0:
        return []

    cfg = config or FillerConfig()

    # Deterministic seed based on section and date for stability
    date_seed = seed + int(target_date.strftime("%Y%m%d")) + hash(sec_cfg.section_id) % 10000
    rng = random.Random(date_seed)

    fillers: List[TrainPassage] = []
    transit_mins = max(10.0, (sec_cfg.distance_km / sec_cfg.max_speed_kmh) * 60.0 * 1.3)

    goods_count = max(1, int(needed_count * cfg.goods_ratio))
    passenger_count = needed_count - goods_count

    # Determine allowable hours
    if cfg.restrict_passenger_to_operational_hours:
        p_hours = cfg.passenger_operational_hours or DEFAULT_PASSENGER_HOURS
    else:
        p_hours = cfg.passenger_operational_hours or ALL_24_HOURS

    if cfg.restrict_goods_to_operational_hours:
        g_hours = cfg.goods_operational_hours or DEFAULT_PASSENGER_HOURS
    else:
        g_hours = cfg.goods_operational_hours or ALL_24_HOURS

    # Distribute throughout the allowable hours
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
            running_days=list(range(7)),  # Runs daily
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
    """
    Returns train passages for a section on target_date, with configurable inclusion
    of synthetic filler passenger trains and synthetic goods trains.
    """
    real_candidates = load_pilot_passages(sec_cfg, snapshot_dir=snapshot_dir)
    real_on_date = [p for p in real_candidates if p.runs_on_date(target_date)]

    target_total = TARGET_DAILY_TRAINS_BY_DENSITY.get(sec_cfg.density_class, 50)
    needed = max(0, target_total - len(real_on_date))

    raw_fillers = generate_filler_passages(sec_cfg, target_date, needed_count=needed, seed=seed, config=filler_config)

    # Filter according to flags
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
