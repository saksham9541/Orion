"""
traffic/passages.py

TrainPassage domain model and timetable interpolation engine.
Reads timetable snapshots, determines train passage through pilot sections,
interpolates non-stopping pass-through times by track distance, and marks interpolated=True.
Respects running days and calendar dates.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    from zoneinfo import ZoneInfo
    KOLKATA_TZ = ZoneInfo("Asia/Kolkata")
except Exception:
    KOLKATA_TZ = timezone(timedelta(hours=5, minutes=30))

from railopt.models import TrainType
from traffic.section_map import get_pilot_section_config, PilotSectionConfig, StationStopConfig, PILOT_SECTIONS
from traffic.block_sections import BlockSection, build_block_sections

DEFAULT_SNAPSHOT_DIR = Path(__file__).resolve().parent.parent / "data" / "railradar_snapshots"

# Configurable average operating speeds by TrainType in corridor/terminal areas (km/h)
DEFAULT_SPEED_BY_TYPE: Dict[TrainType, float] = {
    TrainType.VANDE_BHARAT: 130.0,
    TrainType.RAJDHANI: 120.0,
    TrainType.SHATABDI: 120.0,
    TrainType.DURONTO: 110.0,
    TrainType.SUPERFAST: 90.0,
    TrainType.MAIL_EXPRESS: 80.0,
    TrainType.GARIB_RATH: 85.0,
    TrainType.PASSENGER: 55.0,
    TrainType.SUBURBAN: 60.0,
    TrainType.FREIGHT: 50.0,
}

# Mapping string train types to TrainType enum
TRAIN_TYPE_MAP: Dict[str, TrainType] = {
    "RAJDHANI": TrainType.RAJDHANI,
    "SHATABDI": TrainType.SHATABDI,
    "VANDE_BHARAT": TrainType.VANDE_BHARAT,
    "DURONTO": TrainType.DURONTO,
    "GARIB_RATH": TrainType.GARIB_RATH,
    "SUPERFAST": TrainType.SUPERFAST,
    "MAIL_EXPRESS": TrainType.MAIL_EXPRESS,
    "PASSENGER": TrainType.PASSENGER,
    "SUBURBAN": TrainType.SUBURBAN,
    "FREIGHT": TrainType.FREIGHT,
}


@dataclass
class TrainPassage:
    """A scheduled or interpolated passage of a train through a track section."""
    train_no: str
    train_name: str
    train_type: TrainType
    section_id: str
    direction: str  # "DN" (from_code -> to_code) or "UP" (to_code -> from_code)
    running_days: List[int]  # 0=Mon, 1=Tue, ..., 6=Sun
    enter_time: time
    exit_time: time
    interpolated: bool = False
    source: str = "timetable_derived"

    def runs_on_date(self, d: date) -> bool:
        """Verify whether this train runs on the specified calendar date."""
        return d.weekday() in self.running_days

    def transit_minutes(self) -> float:
        """Calculate transit time in minutes through the section."""
        ref = date(2000, 1, 1)
        dt_enter = datetime.combine(ref, self.enter_time)
        dt_exit = datetime.combine(ref, self.exit_time)
        if dt_exit <= dt_enter:
            dt_exit += timedelta(days=1)
        return (dt_exit - dt_enter).total_seconds() / 60.0

    def occupies_interval(
        self,
        target_date: date,
        window_start: time,
        window_end: time,
        buffer_minutes: int = 10,
    ) -> bool:
        """
        Check if this train passage (with safety clearance buffer) overlaps a window.
        Handles midnight crossings gracefully.
        """
        if not self.runs_on_date(target_date):
            return False

        ref = target_date
        t_enter = datetime.combine(ref, self.enter_time) - timedelta(minutes=buffer_minutes)
        t_exit = datetime.combine(ref, self.exit_time) + timedelta(minutes=buffer_minutes)
        if self.exit_time <= self.enter_time:
            t_exit += timedelta(days=1)

        w_start = datetime.combine(ref, window_start)
        w_end = datetime.combine(ref, window_end)
        if window_end <= window_start:
            w_end += timedelta(days=1)

        return t_enter < w_end and w_start < t_exit


@dataclass(init=False)
class BlockSectionPassage:
    """
    A scheduled or interpolated occupancy of a specific BlockSection by a train.
    Maintains timezone-aware Asia/Kolkata datetimes, preserving exact calendar dates
    and midnight transitions.
    """
    train_no: str
    train_name: str
    train_type: TrainType
    block_section_id: str
    line: str  # "UP" | "DN"
    enter_datetime: datetime
    exit_datetime: datetime
    enter_time: time
    exit_time: time
    direction: str = "DN"
    interpolated: bool = False
    provenance: str = "hand_written"  # "live" | "hand_written" | "synthetic"
    origin_date: Optional[date] = None
    block_date: Optional[date] = None
    source: str = "timetable_derived"
    running_days: list[int] = field(default_factory=lambda: list(range(7)))

    def __init__(
        self,
        train_no: Optional[str] = None,
        train_number: Optional[str] = None,
        train_name: str = "",
        train_type: Any = TrainType.MAIL_EXPRESS,
        block_section_id: str = "",
        line: str = "DN",
        direction: Optional[str] = None,
        enter_datetime: Optional[datetime] = None,
        exit_datetime: Optional[datetime] = None,
        scheduled_enter: Optional[datetime] = None,
        scheduled_exit: Optional[datetime] = None,
        enter_time: Optional[time] = None,
        exit_time: Optional[time] = None,
        interpolated: bool = False,
        provenance: str = "hand_written",
        origin_date: Optional[date] = None,
        block_date: Optional[date] = None,
        source: str = "timetable_derived",
        running_days: Optional[list[int]] = None,
    ):
        self.train_no = str(train_no or train_number or "")
        self.train_name = train_name
        if isinstance(train_type, str):
            self.train_type = TRAIN_TYPE_MAP.get(train_type.upper(), TrainType.MAIL_EXPRESS)
        else:
            self.train_type = train_type
        self.block_section_id = block_section_id
        self.line = (line or direction or "DN").upper()
        self.direction = (direction or self.line).upper()

        e_dt = enter_datetime or scheduled_enter or datetime.now(KOLKATA_TZ)
        x_dt = exit_datetime or scheduled_exit or (e_dt + timedelta(minutes=10))
        self.enter_datetime = e_dt
        self.exit_datetime = x_dt
        self.enter_time = enter_time or e_dt.time()
        self.exit_time = exit_time or x_dt.time()
        self.interpolated = interpolated
        self.provenance = provenance
        self.origin_date = origin_date or e_dt.date()
        self.block_date = block_date or e_dt.date()
        self.source = source
        self.running_days = running_days if running_days is not None else list(range(7))

    @property
    def train_number(self) -> str:
        return self.train_no

    @property
    def scheduled_enter(self) -> datetime:
        return self.enter_datetime

    @property
    def scheduled_exit(self) -> datetime:
        return self.exit_datetime

    def transit_minutes(self) -> float:
        """Calculate transit time in minutes through the block section."""
        return max(2.0, (self.exit_datetime - self.enter_datetime).total_seconds() / 60.0)

    def occupies_interval(
        self,
        start_dt: datetime,
        end_dt: datetime,
        clearance_minutes: int = 10,
    ) -> bool:
        """Check if passage (+/- clearance buffer) overlaps a datetime interval."""
        c = timedelta(minutes=clearance_minutes)
        return (self.enter_datetime - c) < end_dt and start_dt < (self.exit_datetime + c)


def parse_time_str(val: Optional[str]) -> Optional[time]:
    """Parse 'HH:MM' or 'HH:MM:SS' string into a datetime.time object."""
    if not val:
        return None
    val = val.strip()
    try:
        parts = val.split(":")
        return time(int(parts[0]), int(parts[1]), int(parts[2]) if len(parts) > 2 else 0)
    except Exception:
        return None


def _time_to_minutes(t: time, day: int = 1) -> float:
    """Convert time and run day into cumulative minutes from day 1 00:00."""
    return (day - 1) * 1440.0 + t.hour * 60.0 + t.minute + (t.second / 60.0)


def _minutes_to_time(m: float) -> time:
    """Convert cumulative minutes into a datetime.time object (modulo 24 hours)."""
    norm = int(round(m)) % 1440
    hour = norm // 60
    minute = norm % 60
    return time(hour, minute, 0)


def build_passage_from_timetable(
    timetable_data: dict,
    sec_cfg: PilotSectionConfig,
) -> Optional[TrainPassage]:
    """
    Interpolate or extract enter and exit times for a train passage through sec_cfg.
    Timetables list halts only: interpolates non-stopping stations linearly by distance.
    """
    data = timetable_data.get("data", timetable_data)
    train_info = data.get("train", {})
    train_no = str(train_info.get("number") or data.get("train_number") or "")
    train_name = str(train_info.get("name") or data.get("train_name") or "")
    raw_type = str(train_info.get("type") or data.get("train_type") or "MAIL_EXPRESS").upper()
    train_type = TRAIN_TYPE_MAP.get(raw_type, TrainType.MAIL_EXPRESS)
    running_days = data.get("running_days") or [0, 1, 2, 3, 4, 5, 6]

    route_stops = data.get("route") or []
    if len(route_stops) < 2:
        return None

    # Known corridor anchor distances
    from_code = sec_cfg.from_code
    to_code = sec_cfg.to_code

    # Locate from_code and to_code in timetable halts if present
    codes = [s.get("station_code") for s in route_stops]
    
    # 1. Determine direction
    direction = "DN"
    has_from = from_code in codes
    has_to = to_code in codes

    if has_from and has_to:
        idx_from = codes.index(from_code)
        idx_to = codes.index(to_code)
        direction = "DN" if idx_from < idx_to else "UP"
    elif has_from:
        idx_from = codes.index(from_code)
        direction = "DN" if idx_from < (len(codes) / 2) else "UP"
    elif has_to:
        idx_to = codes.index(to_code)
        direction = "DN" if idx_to > 0 else "UP"

    # Identify preceding halt and succeeding halt around the pilot section based on direction
    enter_code = from_code if direction == "DN" else to_code
    exit_code = to_code if direction == "DN" else from_code

    enter_stop = None
    exit_stop = None
    interpolated_enter = True
    interpolated_exit = True

    # Check for direct halts
    for s in route_stops:
        sc = s.get("station_code")
        if sc == enter_code:
            enter_stop = s
            interpolated_enter = False
        elif sc == exit_code:
            exit_stop = s
            interpolated_exit = False

    # Physical section transit time based on track length and max speed
    transit_mins = max(10.0, (sec_cfg.distance_km / sec_cfg.max_speed_kmh) * 60.0 * 1.15)

    if enter_stop and exit_stop:
        dep_str = enter_stop.get("departure") or enter_stop.get("arrival")
        arr_str = exit_stop.get("arrival") or exit_stop.get("departure")
        t_enter = parse_time_str(dep_str)
        t_exit = parse_time_str(arr_str)
        if t_enter and t_exit:
            min_enter = _time_to_minutes(t_enter)
            min_exit = _time_to_minutes(t_exit)
            if min_exit < min_enter:
                min_exit += 1440.0
            # Sanity check: transit through pilot section should not exceed 2.5x normal transit
            if (min_exit - min_enter) > transit_mins * 3.0:
                min_exit = min_enter + transit_mins
                t_exit = _minutes_to_time(int(min_exit) % 1440)
            return TrainPassage(
                train_no=train_no,
                train_name=train_name,
                train_type=train_type,
                section_id=sec_cfg.section_id,
                direction=direction,
                running_days=running_days,
                enter_time=t_enter,
                exit_time=t_exit,
                interpolated=False,
            )

    if enter_stop and not exit_stop:
        dep_str = enter_stop.get("departure") or enter_stop.get("arrival")
        t_enter = parse_time_str(dep_str) or time(0, 0)
        min_enter = _time_to_minutes(t_enter)
        min_exit = (min_enter + transit_mins) % 1440
        t_exit = _minutes_to_time(int(min_exit))
        return TrainPassage(
            train_no=train_no,
            train_name=train_name,
            train_type=train_type,
            section_id=sec_cfg.section_id,
            direction=direction,
            running_days=running_days,
            enter_time=t_enter,
            exit_time=t_exit,
            interpolated=True,
        )

    if exit_stop and not enter_stop:
        arr_str = exit_stop.get("arrival") or exit_stop.get("departure")
        t_exit = parse_time_str(arr_str) or time(1, 0)
        min_exit = _time_to_minutes(t_exit)
        min_enter = (min_exit - transit_mins) % 1440
        t_enter = _minutes_to_time(int(min_enter))
        return TrainPassage(
            train_no=train_no,
            train_name=train_name,
            train_type=train_type,
            section_id=sec_cfg.section_id,
            direction=direction,
            running_days=running_days,
            enter_time=t_enter,
            exit_time=t_exit,
            interpolated=True,
        )

    # Otherwise, interpolate across bounding halts A and B
    # Find two halts bounding the section
    hA = route_stops[0]
    hB = route_stops[1]

    for i in range(len(route_stops) - 1):
        s1 = route_stops[i]
        s2 = route_stops[i + 1]
        c1 = s1.get("station_code")
        c2 = s2.get("station_code")
        if (c1 == from_code and direction == "DN") or (c1 == to_code and direction == "UP"):
            hA = s1
            hB = s2
            break
        elif (c2 == to_code and direction == "DN") or (c2 == from_code and direction == "UP"):
            hA = s1
            hB = s2
            break

    dA = float(hA.get("distance", 0.0))
    dB = float(hB.get("distance", sec_cfg.distance_km))
    tA_str = hA.get("departure") or hA.get("arrival") or "00:00"
    tB_str = hB.get("arrival") or hB.get("departure") or "01:00"
    dayA = int(hA.get("day", 1))
    dayB = int(hB.get("day", dayA))

    tA = parse_time_str(tA_str) or time(0, 0)
    tB = parse_time_str(tB_str) or time(1, 0)

    minA = _time_to_minutes(tA, dayA)
    minB = _time_to_minutes(tB, dayB)
    if minB <= minA:
        minB += 1440.0

    dist_span = max(1.0, abs(dB - dA))
    leg_duration = minB - minA

    # Distance to pilot section boundaries
    if enter_stop:
        dep_str = enter_stop.get("departure") or enter_stop.get("arrival")
        t_enter = parse_time_str(dep_str) or time(0, 0)
        interpolated_enter = False
    else:
        t_enter = tA
        interpolated_enter = True

    if exit_stop:
        arr_str = exit_stop.get("arrival") or exit_stop.get("departure")
        t_exit = parse_time_str(arr_str) or time(1, 0)
        interpolated_exit = False
    else:
        # Interpolate pass-through time along section distance
        # Standard average speed on section ~70-110 km/h
        transit_time_mins = max(10.0, (sec_cfg.distance_km / sec_cfg.max_speed_kmh) * 60.0 * 1.2)
        min_exit = _time_to_minutes(t_enter) + transit_time_mins
        t_exit = _minutes_to_time(min_exit)
        interpolated_exit = True

    return TrainPassage(
        train_no=train_no,
        train_name=train_name,
        train_type=train_type,
        section_id=sec_cfg.section_id,
        direction=direction,
        running_days=running_days,
        enter_time=t_enter,
        exit_time=t_exit,
        interpolated=(interpolated_enter or interpolated_exit),
    )


def load_pilot_passages(
    sec_cfg: PilotSectionConfig,
    snapshot_dir: Optional[Path] = None,
) -> List[TrainPassage]:
    """
    Load all valid train passages for sec_cfg from available timetable snapshots.
    """
    s_dir = snapshot_dir or DEFAULT_SNAPSHOT_DIR
    passages: List[TrainPassage] = []

    # Look for all train_*_timetable.json in snapshot dir
    timetable_files = list(s_dir.glob("train_*_timetable.json"))
    for tf in timetable_files:
        try:
            with open(tf, "r", encoding="utf-8") as f:
                data = json.load(f)
            p = build_passage_from_timetable(data, sec_cfg)
            if p:
                passages.append(p)
        except Exception:
            continue

    # Sort passages by enter_time
    passages.sort(key=lambda x: (x.enter_time.hour, x.enter_time.minute))
    return passages


def build_block_passages_from_timetable(
    timetable_data: dict,
    block_sections: List[BlockSection],
    target_date: date,
    speed_by_type: Optional[Dict[TrainType, float]] = None,
) -> List[BlockSectionPassage]:
    """
    Computes per-train occupancy for each BlockSection along its specific line:
    - enter = time at from_station
    - exit = time at to_station (interpolated by distance and train speed for non-stopping trains, minimum 2 min).
    - timezone-aware Asia/Kolkata datetimes with timetable day offsets.
    - running days apply to the train's origin departure date.
    - direction derived from station order in timetable route.
    - speed per train type configurable.
    """
    if not block_sections:
        return []

    data = timetable_data.get("data", timetable_data)
    train_info = data.get("train", {})
    train_no = str(train_info.get("number") or data.get("train_number") or "")
    train_name = str(train_info.get("name") or data.get("train_name") or "")
    raw_type = str(train_info.get("type") or data.get("train_type") or "MAIL_EXPRESS").upper()
    train_type = TRAIN_TYPE_MAP.get(raw_type, TrainType.MAIL_EXPRESS)
    prov = timetable_data.get("provenance") or (data.get("meta") or {}).get("provenance", "hand_written")
    running_days = data.get("running_days") or [0, 1, 2, 3, 4, 5, 6]
    route_stops = data.get("route") or []

    if len(route_stops) < 2:
        return []

    pilot_id = block_sections[0].pilot_section_id or "SEC-93135bb9"
    sec_cfg = PILOT_SECTIONS.get(pilot_id, PILOT_SECTIONS["SEC-93135bb9"])
    corridor_stations = {s.code: s for s in sec_cfg.stations}

    speed = (speed_by_type or DEFAULT_SPEED_BY_TYPE).get(train_type, 80.0)

    # 1. Derive direction from station order in route
    matched_stops: List[Tuple[int, dict, StationStopConfig]] = []
    for idx, r in enumerate(route_stops):
        code = r.get("station_code")
        if code in corridor_stations:
            matched_stops.append((idx, r, corridor_stations[code]))

    direction = "DN"
    if len(matched_stops) >= 2:
        if matched_stops[0][2].km_from_start < matched_stops[-1][2].km_from_start:
            direction = "DN"
        else:
            direction = "UP"
    elif len(matched_stops) == 1:
        # Match against origin or destination of entire train
        single_stop_idx = matched_stops[0][0]
        stn_cfg = matched_stops[0][2]
        if single_stop_idx == 0:
            direction = "DN" if stn_cfg.km_from_start == 0.0 else "UP"
        elif single_stop_idx == len(route_stops) - 1:
            direction = "UP" if stn_cfg.km_from_start == 0.0 else "DN"
        else:
            # Check destination code name/region
            dest_code = (route_stops[-1].get("station_code") or "").upper()
            if dest_code in ("NDLS", "DLI", "NZM", "ANVT"):
                direction = "UP"
            else:
                direction = "DN"

    # Filter block sections to matching direction line
    active_sections = [bs for bs in block_sections if bs.line == direction]
    if not active_sections:
        return []

    # 2. Candidate origin dates (accounting for multi-day transit)
    candidate_origin_dates = [
        target_date - timedelta(days=2),
        target_date - timedelta(days=1),
        target_date,
    ]

    passages: List[BlockSectionPassage] = []
    start_of_target = datetime.combine(target_date, time(0, 0), tzinfo=KOLKATA_TZ)
    end_of_target = datetime.combine(target_date + timedelta(days=1), time(0, 0), tzinfo=KOLKATA_TZ)

    for orig_d in candidate_origin_dates:
        # Running days apply to origin departure date
        if orig_d.weekday() not in running_days:
            continue

        # Build timetable timeline for known route stops
        known_stop_times: Dict[str, Tuple[datetime, datetime, float]] = {}  # code -> (arr_dt, dep_dt, km_from_start)
        for r in route_stops:
            code = r.get("station_code")
            arr_t = parse_time_str(r.get("arrival") or r.get("departure")) or time(0, 0)
            dep_t = parse_time_str(r.get("departure") or r.get("arrival")) or time(0, 0)
            day = int(r.get("day", 1))

            dt_arr = datetime.combine(orig_d, arr_t, tzinfo=KOLKATA_TZ) + timedelta(days=day - 1)
            dt_dep = datetime.combine(orig_d, dep_t, tzinfo=KOLKATA_TZ) + timedelta(days=day - 1)
            km = corridor_stations[code].km_from_start if code in corridor_stations else float(r.get("distance", 0.0))
            known_stop_times[code] = (dt_arr, dt_dep, km)

        # Compute enter and exit datetime for every corridor station
        station_times: Dict[str, datetime] = {}
        station_interpolated: Dict[str, bool] = {}

        for code, sc in corridor_stations.items():
            if code in known_stop_times:
                station_times[code] = known_stop_times[code][1]  # Departure time
                station_interpolated[code] = False
            else:
                # Interpolate from nearest known route stops
                # Search for known stop before and after in corridor sequence
                prev_known = None
                next_known = None

                # In direction order:
                for r in route_stops:
                    rc = r.get("station_code")
                    if rc in corridor_stations:
                        r_km = corridor_stations[rc].km_from_start
                        if direction == "DN":
                            if r_km < sc.km_from_start:
                                prev_known = (rc, known_stop_times[rc][1], r_km)
                            elif r_km > sc.km_from_start and next_known is None:
                                next_known = (rc, known_stop_times[rc][0], r_km)
                        else:  # UP
                            if r_km > sc.km_from_start:
                                prev_known = (rc, known_stop_times[rc][1], r_km)
                            elif r_km < sc.km_from_start and next_known is None:
                                next_known = (rc, known_stop_times[rc][0], r_km)

                if prev_known and next_known:
                    _, t1, km1 = prev_known
                    _, t2, km2 = next_known
                    span_km = max(0.5, abs(km2 - km1))
                    frac = min(1.0, max(0.0, abs(sc.km_from_start - km1) / span_km))
                    interp_dt = t1 + (t2 - t1) * frac
                elif prev_known:
                    _, t1, km1 = prev_known
                    dist = abs(sc.km_from_start - km1)
                    interp_dt = t1 + timedelta(hours=dist / speed)
                elif next_known:
                    _, t2, km2 = next_known
                    dist = abs(km2 - sc.km_from_start)
                    interp_dt = t2 - timedelta(hours=dist / speed)
                else:
                    # Anchor to first stop of train
                    first_r = route_stops[0]
                    first_code = first_r.get("station_code")
                    first_dt = known_stop_times.get(first_code, (start_of_target, start_of_target, 0.0))[1]
                    dist = sc.km_from_start
                    interp_dt = first_dt + timedelta(hours=dist / speed)

                station_times[code] = interp_dt
                station_interpolated[code] = True

        # Now evaluate each BlockSection
        for bs in active_sections:
            f_code = bs.from_station
            t_code = bs.to_station

            if f_code not in station_times or t_code not in station_times:
                continue

            enter_dt = station_times[f_code]
            exit_dt = station_times[t_code]

            # In direction of travel, exit must be strictly after enter
            if exit_dt <= enter_dt:
                transit_h = max(2.0 / 60.0, bs.length_km / speed)
                exit_dt = enter_dt + timedelta(hours=transit_h)

            # Minimum transit rule: at least 2 minutes
            if (exit_dt - enter_dt).total_seconds() < 120.0:
                exit_dt = enter_dt + timedelta(seconds=120)

            # Check if occupancy overlaps the target date
            if exit_dt > start_of_target and enter_dt < end_of_target:
                is_interp = station_interpolated.get(f_code, True) or station_interpolated.get(t_code, True)
                passages.append(
                    BlockSectionPassage(
                        train_no=train_no,
                        train_name=train_name,
                        train_type=train_type,
                        block_section_id=bs.id,
                        line=bs.line,
                        enter_datetime=enter_dt,
                        exit_datetime=exit_dt,
                        enter_time=enter_dt.time(),
                        exit_time=exit_dt.time(),
                        interpolated=is_interp,
                        provenance=prov,
                        origin_date=orig_d,
                        block_date=enter_dt.date(),
                        source="timetable_derived",
                    )
                )

    passages.sort(key=lambda p: p.enter_datetime)
    return passages


def load_pilot_block_passages(
    pilot_section_id: str = "SEC-93135bb9",
    target_date: Optional[date] = None,
    snapshot_dir: Optional[Path] = None,
    speed_by_type: Optional[Dict[TrainType, float]] = None,
) -> List[BlockSectionPassage]:
    """
    Load all valid BlockSectionPassage occupancies across all block sections
    for pilot_section_id on target_date.
    """
    s_dir = snapshot_dir or DEFAULT_SNAPSHOT_DIR
    t_date = target_date or date(2026, 11, 1)

    sections = build_block_sections(pilot_section_id, snapshot_dir=s_dir)
    timetable_files = list(s_dir.glob("train_*_timetable.json"))

    all_passages: List[BlockSectionPassage] = []
    for tf in timetable_files:
        try:
            with open(tf, "r", encoding="utf-8") as f:
                data = json.load(f)
            p_list = build_block_passages_from_timetable(
                data, sections, t_date, speed_by_type=speed_by_type
            )
            all_passages.extend(p_list)
        except Exception:
            continue

    all_passages.sort(key=lambda p: (p.block_section_id, p.enter_datetime))
    return all_passages


def get_snapshots_provenance_report(snapshot_dir: Optional[Path] = None) -> dict:
    """
    Scans all snapshot files in snapshot_dir, reporting provenance, snapshot age,
    and exact values for any hand_written (illustrative, not fetched) timetables or coordinates.
    """
    s_dir = snapshot_dir or DEFAULT_SNAPSHOT_DIR
    files = sorted(list(s_dir.glob("*.json"))) if s_dir.exists() else []

    total = len(files)
    prov_counts = {"live": 0, "hand_written": 0}
    items = []
    oldest_ts = None
    newest_ts = None
    hand_written_coords = []
    hand_written_trains = []
    hand_written_pairs = []

    now = datetime.now(timezone.utc)

    for f in files:
        try:
            with open(f, "r", encoding="utf-8") as fp:
                data = json.load(fp)
            prov = data.get("provenance") or (data.get("meta") or {}).get("provenance", "hand_written")
            prov_counts[prov] = prov_counts.get(prov, 0) + 1
            ts_str = data.get("snapshot_timestamp") or (data.get("meta") or {}).get("snapshot_timestamp", "2026-10-30T10:50:00Z")
            illustrative = bool(data.get("illustrative") or (data.get("meta") or {}).get("illustrative", prov == "hand_written"))

            # Calculate age
            age_hours = 0.0
            try:
                dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                age_hours = max(0.0, (now - dt).total_seconds() / 3600.0)
                if oldest_ts is None or dt < oldest_ts:
                    oldest_ts = dt
                if newest_ts is None or dt > newest_ts:
                    newest_ts = dt
            except Exception:
                pass

            if prov == "hand_written":
                if "_route.json" in f.name:
                    stations = (data.get("data") or {}).get("stations", [])
                    for stn in stations:
                        hand_written_coords.append({
                            "code": stn.get("code"),
                            "name": stn.get("name"),
                            "lat": stn.get("lat"),
                            "lon": stn.get("lon"),
                            "distance_km": stn.get("distance_km"),
                            "corridor": (data.get("meta") or {}).get("corridor", ""),
                        })
                elif "_timetable.json" in f.name:
                    t_info = (data.get("data") or {}).get("train", {})
                    hand_written_trains.append({
                        "number": t_info.get("number"),
                        "name": t_info.get("name"),
                        "type": t_info.get("type"),
                        "running_days": (data.get("data") or {}).get("running_days", []),
                    })
                elif "train_between_" in f.name:
                    frm = (data.get("data") or {}).get("from_station")
                    to = (data.get("data") or {}).get("to_station")
                    hand_written_pairs.append(f"{frm}–{to}")

            items.append({
                "filename": f.name,
                "provenance": prov,
                "snapshot_timestamp": ts_str,
                "age_hours": round(age_hours, 1),
                "age_days": round(age_hours / 24.0, 1),
                "illustrative": illustrative,
            })
        except Exception:
            pass

    overall_prov = "live" if (prov_counts.get("live", 0) > 0 and prov_counts.get("hand_written", 0) == 0) else "hand_written"
    has_hand_written = prov_counts.get("hand_written", 0) > 0

    return {
        "total_snapshots": total,
        "provenance_breakdown": prov_counts,
        "overall_provenance": overall_prov,
        "has_hand_written": has_hand_written,
        "ui_label": "illustrative, not fetched" if has_hand_written else "live",
        "oldest_timestamp": oldest_ts.isoformat() if oldest_ts else None,
        "newest_timestamp": newest_ts.isoformat() if newest_ts else None,
        "average_age_days": round(sum(i["age_days"] for i in items) / max(total, 1), 1),
        "hand_written_details": {
            "coordinates": hand_written_coords,
            "timetables": hand_written_trains,
            "station_pairs": hand_written_pairs,
        },
        "snapshots": items,
    }
