"""
RailOpt — Realistic synthetic data generator.

Generates an Indian Railways maintenance dataset for ML training, demo,
and testing purposes. Models ~Delhi Division topology with realistic
defect distributions, timetable patterns, and block windows.

REAL DATA CALIBRATION NOTES:
- Corridor distances: the Delhi-Howrah Main and Delhi-Mumbai Rajdhani
  Route sections below have been checked against real published rail
  distances (train schedules, Wikipedia line articles). The other 8
  corridors are reasonable geographic approximations that have NOT been
  individually verified — state this distinction plainly if asked which
  numbers are sourced vs assumed.
- REAL_EQUIPMENT_FAILURE_SHARE_PCT below is a real, cited national
  statistic (Lok Sabha data): equipment failure caused only 6.2% of all
  consequential train accidents nationally (55.8% railway-staff failure,
  28.4% non-staff failure). This system only models that 6.2% slice by
  design — the stat doesn't change department/defect generation weights,
  but it's a legitimate, sourced line for a feasibility/impact slide:
  predictive maintenance targets a small but highly preventable share of
  total accident risk.

DEMO DATA CALIBRATION (fix, see the review notes):
- Safety-critical defect share was previously ~34% of all tasks — an
  unrealistic proportion that dragged SLA compliance down to 42-73% on
  screen even on a healthy schedule. The per-department defect weights
  below were rebalanced so SAFETY_CRITICAL_DEFECTS categories
  (RAIL_FRACTURE, RAIL_CRACK, SIGNAL_FAILURE, POINT_FAILURE,
  INTERLOCKING_FAULT, OHE_BREAK, BRIDGE_CORROSION, TRACK_CIRCUIT_FAILURE)
  land around 10-15% of tasks overall, which is the range noted as
  realistic in the review. ALWAYS_EMERGENCY categories (RAIL_FRACTURE,
  OHE_BREAK, INTERLOCKING_FAULT) are kept rare but present within that.
- Block windows previously covered only the next 7 days regardless of
  requested horizon, so a "monthly" plan request and a "weekly" one drew
  from the exact same window pool — a monthly plan was really a weekly
  plan with a different label. generate_full_dataset() now takes a
  window_days parameter (default 30) so a full month of windows exists;
  it's the caller's job (see backend/main.py's /api/plans/generate) to
  filter that pool down to the requested date range/horizon.
- num_tasks: the demo previously seeded 500 tasks against only 7 days of
  windows, producing roughly 1.2x more task-hours of demand than window-
  hours of supply — every plan was structurally oversubscribed. Callers
  should default nearer 150-250 tasks (see /api/demo/setup) now that the
  window pool is 30 days by default; the parameter itself is left
  configurable here rather than hardcoded.

Usage:
    from railopt.synthetic_data import generate_full_dataset
    dataset = generate_full_dataset(seed=42, num_tasks=200, window_days=30)
    # dataset['tasks']         → list[MaintenanceTask]
    # dataset['sections']      → list[Section]
    # dataset['corridors']     → list[Corridor]
    # dataset['train_slots']   → list[TrainSlot]
    # dataset['block_windows'] → list[BlockWindow]
"""

from __future__ import annotations

import json
import random
from datetime import date, datetime, time, timedelta
from typing import Any, Dict

from railopt.models import (
    ASSET_DEPARTMENT_MAP,
    AssetType,
    BlockType,
    BlockWindow,
    Corridor,
    DefectCategory,
    Department,
    MaintenanceTask,
    Section,
    TaskStatus,
    TrafficDensityClass,
    TrainSlot,
    TrainType,
)

# REAL DATA: national accident-cause breakdown, Lok Sabha data via
# DrishtiIAS/CivilsDaily analysis of Ministry of Railways figures.
# Not used in generation weights (see module docstring) — kept here as a
# sourced constant for briefing/report text or feasibility-slide citation.
REAL_EQUIPMENT_FAILURE_SHARE_PCT = 6.2
REAL_RAILWAY_STAFF_FAILURE_SHARE_PCT = 55.8
REAL_NON_STAFF_FAILURE_SHARE_PCT = 28.4


# ──────────────────────────────────────────────────────────────────────
# Network topology data (loosely modeled on Delhi Division, NR)
# ──────────────────────────────────────────────────────────────────────

_CORRIDOR_DEFS = [
    {
        "name": "Delhi–Howrah Main",
        "zone": "Northern Railway",
        "division": "Delhi Division",
        # Distances checked against real train-schedule data (Railmitra) and
        # the Delhi–Moradabad line article (Wikipedia): New Delhi–Moradabad
        # totals ~166 km on the real line. Hapur–Moradabad corrected from an
        # earlier estimate of 95.0 km to 104.0 km to match.
        "sections": [
            ("New Delhi", "Ghaziabad", 19.0, 130, TrafficDensityClass.A_SPECIAL),
            ("Ghaziabad", "Hapur", 40.0, 110, TrafficDensityClass.A),
            ("Hapur", "Moradabad", 104.0, 110, TrafficDensityClass.B),
            ("Moradabad", "Bareilly", 90.0, 110, TrafficDensityClass.B),
        ],
    },
    {
        "name": "Delhi–Mumbai Rajdhani Route",
        "zone": "Western Railway",
        "division": "Delhi Division",
        # Distances checked against real published Indian Railways segment
        # distances (New Delhi–Mathura, Mathura–Agra, Agra–Gwalior,
        # Gwalior–Jhansi) — these four numbers were already accurate.
        "sections": [
            ("New Delhi", "Mathura Jn", 141.0, 130, TrafficDensityClass.A_SPECIAL),
            ("Mathura Jn", "Agra Cantt", 54.0, 130, TrafficDensityClass.A),
            ("Agra Cantt", "Gwalior", 118.0, 130, TrafficDensityClass.A),
            ("Gwalior", "Jhansi", 98.0, 130, TrafficDensityClass.B),
        ],
    },
    {
        "name": "Delhi–Amritsar Main",
        "zone": "Northern Railway",
        "division": "Delhi Division",
        "sections": [
            ("New Delhi", "Panipat", 90.0, 130, TrafficDensityClass.A_SPECIAL),
            ("Panipat", "Ambala", 76.0, 130, TrafficDensityClass.A),
            ("Ambala", "Ludhiana", 120.0, 110, TrafficDensityClass.A),
            ("Ludhiana", "Amritsar", 138.0, 110, TrafficDensityClass.B),
        ],
    },
    {
        "name": "Delhi–Kalka Suburban",
        "zone": "Northern Railway",
        "division": "Delhi Division",
        "sections": [
            ("New Delhi", "Sonipat", 42.0, 110, TrafficDensityClass.A),
            ("Sonipat", "Panipat", 48.0, 110, TrafficDensityClass.B),
            ("Panipat", "Karnal", 33.0, 100, TrafficDensityClass.C),
        ],
    },
    {
        "name": "Delhi–Meerut RRTS",
        "zone": "Northern Railway",
        "division": "Delhi Division",
        "sections": [
            ("Delhi Sarai Rohilla", "Ghaziabad", 25.0, 160, TrafficDensityClass.A_SPECIAL),
            ("Ghaziabad", "Murad Nagar", 18.0, 160, TrafficDensityClass.A),
            ("Murad Nagar", "Meerut", 30.0, 160, TrafficDensityClass.A),
        ],
    },
    {
        "name": "Delhi–Rewari",
        "zone": "Northern Railway",
        "division": "Delhi Division",
        "sections": [
            ("Delhi Cantt", "Gurugram", 25.0, 110, TrafficDensityClass.A),
            ("Gurugram", "Rewari", 58.0, 110, TrafficDensityClass.B),
        ],
    },
    {
        "name": "Delhi–Rohtak",
        "zone": "Northern Railway",
        "division": "Delhi Division",
        "sections": [
            ("Delhi Jn", "Bahadurgarh", 21.0, 100, TrafficDensityClass.B),
            ("Bahadurgarh", "Rohtak", 46.0, 100, TrafficDensityClass.C),
        ],
    },
    {
        "name": "Delhi–Saharanpur",
        "zone": "Northern Railway",
        "division": "Delhi Division",
        "sections": [
            ("Old Delhi", "Meerut", 71.0, 100, TrafficDensityClass.B),
            ("Meerut", "Muzaffarnagar", 60.0, 100, TrafficDensityClass.C),
            ("Muzaffarnagar", "Saharanpur", 45.0, 100, TrafficDensityClass.C),
        ],
    },
    {
        "name": "Delhi–Chennai Rajdhani",
        "zone": "Northern Railway",
        "division": "Delhi Division",
        "sections": [
            ("New Delhi", "Mathura Jn", 141.0, 130, TrafficDensityClass.A_SPECIAL),
            ("Mathura Jn", "Agra Fort", 58.0, 130, TrafficDensityClass.A),
            ("Agra Fort", "Jhansi", 198.0, 110, TrafficDensityClass.B),
        ],
    },
    {
        "name": "Delhi–Jaipur",
        "zone": "North Western Railway",
        "division": "Delhi Division",
        "sections": [
            ("Delhi Cantt", "Alwar", 153.0, 110, TrafficDensityClass.B),
            ("Alwar", "Jaipur", 155.0, 110, TrafficDensityClass.B),
        ],
    },
]

# Defect distributions per department (weighted choices).
#
# DEMO DATA FIX: rebalanced so SAFETY_CRITICAL_DEFECTS categories
# (RAIL_FRACTURE, RAIL_CRACK for Engineering; SIGNAL_FAILURE, POINT_FAILURE,
# INTERLOCKING_FAULT, TRACK_CIRCUIT_FAILURE for S&T; OHE_BREAK for TRD) sit
# around 10-15% of tasks overall instead of the previous ~34%. See the
# module docstring for the worked-out math per department.
#
# Engineering: RAIL_CRACK(10) + RAIL_FRACTURE(3) + BRIDGE_CORROSION(1) = 14%
# of ENG tasks → 0.50 * 0.14 = 7.0% of all tasks.
_ENG_DEFECTS = [
    (DefectCategory.GAUGE_IRREGULARITY, 18),
    (DefectCategory.ALIGNMENT_DEFECT, 14),
    (DefectCategory.SLEEPER_DAMAGE, 14),
    (DefectCategory.BALLAST_DEFICIENCY, 14),
    (DefectCategory.CROSS_LEVEL_DEFECT, 10),
    (DefectCategory.WELD_DEFECT, 8),
    (DefectCategory.RAIL_CRACK, 10),          # safety-critical
    (DefectCategory.FORMATION_FAILURE, 5),
    (DefectCategory.RAIL_FRACTURE, 3),        # safety-critical, always-emergency
    (DefectCategory.LEVEL_CROSSING_DEFECT, 3),
    (DefectCategory.BRIDGE_CORROSION, 1),     # safety-critical
]

# S&T: TRACK_CIRCUIT_FAILURE(4) + SIGNAL_FAILURE(4) + POINT_FAILURE(2) +
# INTERLOCKING_FAULT(2) = 12% of SNT tasks → 0.30 * 0.12 = 3.6% of all tasks.
_SNT_DEFECTS = [
    (DefectCategory.RELAY_MALFUNCTION, 36),
    (DefectCategory.CABLE_DAMAGE, 32),
    (DefectCategory.AXLE_COUNTER_ERROR, 20),
    (DefectCategory.TRACK_CIRCUIT_FAILURE, 4),   # safety-critical
    (DefectCategory.SIGNAL_FAILURE, 4),          # safety-critical
    (DefectCategory.POINT_FAILURE, 2),           # safety-critical
    (DefectCategory.INTERLOCKING_FAULT, 2),      # safety-critical, always-emergency
]

# TRD: OHE_BREAK(5) = 5% of TRD tasks → 0.20 * 0.05 = 1.0% of all tasks.
# Already low pre-fix; left unchanged.
_TRD_DEFECTS = [
    (DefectCategory.OHE_SAG, 30),
    (DefectCategory.INSULATOR_DAMAGE, 25),
    (DefectCategory.PANTOGRAPH_SCRATCH, 15),
    (DefectCategory.MAST_TILT, 10),
    (DefectCategory.FEEDER_TRIP, 10),
    (DefectCategory.OHE_BREAK, 5),  # safety-critical, always-emergency
    (DefectCategory.TRANSFORMER_FAULT, 5),
]

# Overall expected safety-critical share with the department mix below
# (50% ENG / 30% SNT / 20% TRD): 7.0 + 3.6 + 1.0 = 11.6% of all tasks.

_ENG_REMARKS = [
    "Rail crack detected near km {km:.1f}, 2mm deep, fishplate showing wear",
    "Gauge irregularity observed, 5mm wider than standard",
    "Alignment defect at curve, rail shifted 3mm",
    "Multiple damaged sleepers in stretch km {km:.1f}-{km2:.1f}",
    "Ballast deficiency, shoulder width below 350mm",
    "Cross level defect, 8mm difference observed",
    "Weld joint showing surface crack, needs ultrasonic testing",
    "Rail fracture detected, emergency fishplate applied",
    "Formation slump after heavy rain, track geometry affected",
    "Bridge girder showing corrosion, rivet heads wasted",
    "Level crossing gate mechanism stiff, road surface uneven",
]

_SNT_REMARKS = [
    "Relay {relay_id} showing intermittent contact failure, cleaned but recurrence likely",
    "Track circuit dropping at km {km:.1f}, bonding checked, insulation resistance low",
    "Signal aspect blank on post {post}, lamp tested OK, feed issue suspected",
    "Cable damage found during patrolling, rodent bite at km {km:.1f}",
    "Point machine not detecting, adjustment done, motor current high",
    "Axle counter resetting frequently, wheel sensor cleaned",
    "Interlocking logic discrepancy found during testing",
]

_TRD_REMARKS = [
    "OHE sag measured at {sag}mm, exceeds 50mm limit at mast {mast}",
    "Insulator surface flashed, creepage path compromised",
    "Pantograph scratch marks observed on contact wire at km {km:.1f}",
    "Mast tilted {deg}° from vertical, foundation inspection needed",
    "Feeder tripped at SP {sp}, auto-recloser operated {n} times",
    "OHE contact wire broken between masts {m1} and {m2}, emergency repair done",
    "Transformer oil level low, DGA test recommended",
]


def _weighted_choice(items: list[tuple]) -> Any:
    """Pick from list of (item, weight) tuples."""
    population, weights = zip(*items)
    return random.choices(population, weights=weights, k=1)[0]


def _make_remark(template: str, km: float) -> str:
    """Fill in a remark template with realistic values."""
    return template.format(
        km=km,
        km2=km + random.uniform(0.1, 0.5),
        relay_id=f"R{random.randint(100,999)}",
        post=f"S{random.randint(1,50)}",
        sag=random.randint(55, 120),
        mast=f"M{random.randint(1,200)}",
        deg=random.randint(2, 8),
        sp=f"SP{random.randint(1,20)}",
        n=random.randint(2, 5),
        m1=f"M{random.randint(1,200)}",
        m2=f"M{random.randint(1,200)}",
    )


# ──────────────────────────────────────────────────────────────────────
# Main generator
# ──────────────────────────────────────────────────────────────────────

def generate_full_dataset(
    seed: int = 42,
    num_tasks: int = 200,
    window_days: int = 30,
) -> dict[str, list]:
    """
    Generate a complete synthetic dataset.

    Args:
        seed: RNG seed for reproducibility.
        num_tasks: total maintenance tasks to generate. DEMO DATA FIX:
            default lowered from 500 to 200 (the suggested 150-250 range)
            now that window_days defaults to 30 instead of 7 — the old
            500-task/7-day combination produced ~1.2x more demand than
            supply, so every generated plan was structurally oversubscribed.
        window_days: how many days of block windows to generate per
            section, starting today. DEMO DATA FIX: default raised from a
            hardcoded 7 to 30, so a MONTHLY plan request actually has a
            different (larger) window pool than a WEEKLY one instead of
            silently drawing from the same 7 days. Callers that only want a
            weekly plan should filter the returned block_windows down to
            the desired date range themselves (see backend/main.py's
            /api/plans/generate, which now does this using the request's
            horizon/start_date/end_date).

    Returns dict with keys:
        'corridors'     → list[Corridor]
        'sections'      → list[Section]
        'tasks'         → list[MaintenanceTask]
        'train_slots'   → list[TrainSlot]
        'block_windows' → list[BlockWindow]

    All values are Pydantic model instances (not dicts).
    """
    random.seed(seed)
    today = date.today()

    # ── 1. Build network topology ────────────────────────────────────
    corridors: list[Corridor] = []
    sections: list[Section] = []

    for cdef in _CORRIDOR_DEFS:
        corridor = Corridor(
            name=cdef["name"],
            zone=cdef["zone"],
            division=cdef["division"],
        )
        start_km = 0.0
        for start_stn, end_stn, length_km, max_spd, density in cdef["sections"]:
            end_km = start_km + length_km
            section = Section(
                corridor_id=corridor.corridor_id,
                name=f"{start_stn}–{end_stn}",
                start_station=start_stn,
                end_station=end_stn,
                start_km=round(start_km, 1),
                end_km=round(end_km, 1),
                max_speed_kmh=max_spd,
                is_single_line=(density in (TrafficDensityClass.C, TrafficDensityClass.D)),
                electrified=True,
                traffic_density_class=density,
                daily_train_count={
                    TrafficDensityClass.A_SPECIAL: random.randint(60, 80),
                    TrafficDensityClass.A: random.randint(40, 60),
                    TrafficDensityClass.B: random.randint(20, 40),
                    TrafficDensityClass.C: random.randint(10, 20),
                    TrafficDensityClass.D: random.randint(3, 10),
                }[density],
            )
            sections.append(section)
            corridor.sections.append(section)
            start_km = end_km

        corridors.append(corridor)

    # ── 2. Generate maintenance tasks ────────────────────────────────
    tasks: list[MaintenanceTask] = []

    for _ in range(num_tasks):
        # Department distribution: 50% Eng, 30% S&T, 20% TRD
        r = random.random()
        if r < 0.50:
            dept = Department.ENGINEERING
            defect = _weighted_choice(_ENG_DEFECTS)
            remark_template = random.choice(_ENG_REMARKS)
        elif r < 0.80:
            dept = Department.SNT
            defect = _weighted_choice(_SNT_DEFECTS)
            remark_template = random.choice(_SNT_REMARKS)
        else:
            dept = Department.TRD
            defect = _weighted_choice(_TRD_DEFECTS)
            remark_template = random.choice(_TRD_REMARKS)

        valid_assets = [a for a, d in ASSET_DEPARTMENT_MAP.items() if d == dept]
        asset = random.choice(valid_assets)
        section = random.choice(sections)
        km = round(section.start_km + random.random() * section.length_km, 1)

        # Days overdue: exponential (most recent, some very old)
        days_overdue = int(random.expovariate(1 / 8.0))
        reported_date = today - timedelta(days=days_overdue + random.randint(1, 14))

        # Duration estimates by type
        base_duration = {
            Department.ENGINEERING: random.uniform(1.5, 4.0),
            Department.SNT: random.uniform(1.0, 3.0),
            Department.TRD: random.uniform(1.0, 3.5),
        }[dept]

        task = MaintenanceTask(
            source_system={"ENGINEERING": "TMS", "SNT": "SMMS", "TRD": "TDMS"}[dept.value],
            department=dept,
            asset_type=asset,
            defect_category=defect,
            corridor_id=section.corridor_id,
            section_id=section.section_id,
            km_location=km,
            reported_date=reported_date,
            due_date=reported_date + timedelta(days=random.choice([7, 14, 30])),
            days_overdue=days_overdue,
            inspector_remarks=_make_remark(remark_template, km),
            asset_age_years=round(random.uniform(1.0, 35.0), 1),
            historical_failure_count=random.randint(0, 6),
            crew_size_required=random.choice([2, 3, 4, 6, 8]),
            estimated_duration_hours=round(base_duration, 1),
        )
        tasks.append(task)

    # ── 3. Generate train timetable ──────────────────────────────────
    train_slots: list[TrainSlot] = []

    _TRAIN_TEMPLATES = [
        (TrainType.RAJDHANI, [6, 16, 20], ["Rajdhani Express"]),
        (TrainType.SHATABDI, [6, 7, 17, 18], ["Shatabdi Express"]),
        (TrainType.SUPERFAST, [8, 10, 14, 22], ["Superfast Express"]),
        (TrainType.MAIL_EXPRESS, list(range(5, 24)), ["Mail Express"]),
        (TrainType.PASSENGER, list(range(4, 22, 3)), ["Passenger"]),
        (TrainType.FREIGHT, [0, 1, 2, 3, 23], ["Goods Train"]),
        (TrainType.SUBURBAN, list(range(5, 23)), ["Suburban Local"]),
    ]

    for section in sections:
        # Number of trains scales with traffic density
        num_trains = {
            TrafficDensityClass.A_SPECIAL: random.randint(10, 15),
            TrafficDensityClass.A: random.randint(6, 10),
            TrafficDensityClass.B: random.randint(4, 7),
            TrafficDensityClass.C: random.randint(2, 4),
            TrafficDensityClass.D: random.randint(1, 3),
        }[section.traffic_density_class]

        for _ in range(num_trains):
            tt = random.choice(_TRAIN_TEMPLATES)
            train_type, possible_hours, names = tt
            hour = random.choice(possible_hours)
            minute = random.randint(0, 59)
            arr = time(hour, minute)
            # Transit time based on section length and speed
            transit_minutes = max(
                10,
                int((section.length_km / section.max_speed_kmh) * 60 * random.uniform(1.1, 1.4)),
            )
            dep_dt = datetime.combine(today, arr) + timedelta(minutes=transit_minutes)
            dep = dep_dt.time()

            slot = TrainSlot(
                train_number=str(random.randint(10000, 99999)),
                train_name=f"{random.choice(names)} {random.randint(1,50)}",
                train_type=train_type,
                corridor_id=section.corridor_id,
                section_id=section.section_id,
                arrival_time=arr,
                departure_time=dep,
            )
            train_slots.append(slot)

    # ── 4. Generate block windows ────────────────────────────────────
    # DEMO DATA FIX: window_days now defaults to 30 (was hardcoded 7), so
    # MONTHLY plan requests actually have more windows to draw from than
    # WEEKLY ones. See the window_days parameter doc above.
    block_windows: list[BlockWindow] = []

    for section in sections:
        for day_offset in range(window_days):
            window_date = today + timedelta(days=day_offset)
            is_weekend = window_date.weekday() >= 5

            # Night window (standard: 00:00-04:30 or 00:00-05:00)
            if section.traffic_density_class in (TrafficDensityClass.A_SPECIAL, TrafficDensityClass.A):
                # Short night window on busy sections
                end_hour = 4 if not is_weekend else 5
            else:
                # Longer window on less busy sections
                end_hour = 5 if not is_weekend else 6

            night_window = BlockWindow(
                corridor_id=section.corridor_id,
                section_id=section.section_id,
                date=window_date,
                start_time=time(0, 30),
                end_time=time(end_hour, 0),
                block_type=BlockType.TRAFFIC_BLOCK,
                max_tasks=4 if section.traffic_density_class == TrafficDensityClass.A_SPECIAL else 6,
            )
            block_windows.append(night_window)

            # Daytime window on low-traffic sections
            if section.traffic_density_class in (TrafficDensityClass.C, TrafficDensityClass.D):
                day_window = BlockWindow(
                    corridor_id=section.corridor_id,
                    section_id=section.section_id,
                    date=window_date,
                    start_time=time(10, 0),
                    end_time=time(13, 0),
                    block_type=BlockType.TRAFFIC_BLOCK,
                    max_tasks=5,
                )
                block_windows.append(day_window)

            # Weekend extra window on medium sections
            if is_weekend and section.traffic_density_class == TrafficDensityClass.B:
                weekend_extra = BlockWindow(
                    corridor_id=section.corridor_id,
                    section_id=section.section_id,
                    date=window_date,
                    start_time=time(9, 0),
                    end_time=time(12, 0),
                    block_type=BlockType.TRAFFIC_BLOCK,
                    max_tasks=5,
                )
                block_windows.append(weekend_extra)

    return {
        "corridors": corridors,
        "sections": sections,
        "tasks": tasks,
        "train_slots": train_slots,
        "block_windows": block_windows,
    }


# ──────────────────────────────────────────────────────────────────────
# Persistence
# ──────────────────────────────────────────────────────────────────────

def save_dataset(dataset: dict, path: str) -> None:
    """Save dataset to JSON (serializes Pydantic models)."""
    serialized = {}
    for key, items in dataset.items():
        serialized[key] = [
            item.model_dump(mode="json") if hasattr(item, "model_dump") else item
            for item in items
        ]

    with open(path, "w") as f:
        json.dump(serialized, f, indent=2, default=str)


def load_dataset(path: str) -> dict:
    """Load dataset from JSON back into Pydantic models."""
    with open(path, "r") as f:
        data = json.load(f)

    return {
        "corridors": [Corridor(**c) for c in data.get("corridors", [])],
        "sections": [Section(**s) for s in data.get("sections", [])],
        "tasks": [MaintenanceTask(**t) for t in data.get("tasks", [])],
        "train_slots": [TrainSlot(**t) for t in data.get("train_slots", [])],
        "block_windows": [BlockWindow(**b) for b in data.get("block_windows", [])],
    }


# ──────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    dataset = generate_full_dataset(num_tasks=100)
    print(f"Generated:")
    print(f"  {len(dataset['corridors'])} corridors")
    print(f"  {len(dataset['sections'])} sections")
    print(f"  {len(dataset['tasks'])} tasks")
    print(f"  {len(dataset['train_slots'])} train slots")
    print(f"  {len(dataset['block_windows'])} block windows")

    # Department distribution check
    dept_counts = {}
    for t in dataset["tasks"]:
        dept_counts[t.department.value] = dept_counts.get(t.department.value, 0) + 1
    print(f"\nDepartment distribution:")
    for dept, count in sorted(dept_counts.items()):
        print(f"  {dept}: {count} ({count/len(dataset['tasks'])*100:.0f}%)")

    # Safety-critical share check
    from railopt.models import SAFETY_CRITICAL_DEFECTS
    safety_count = sum(1 for t in dataset["tasks"] if t.defect_category in SAFETY_CRITICAL_DEFECTS)
    print(f"\nSafety-critical share: {safety_count}/{len(dataset['tasks'])} "
          f"({safety_count/len(dataset['tasks'])*100:.1f}%)")