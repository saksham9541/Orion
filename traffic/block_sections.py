"""
traffic/block_sections.py

Block-section topology for Indian Railways corridors.
In real IR operations, absolute block signaling / automatic block territory is
partitioned into station-to-station block sections (or automatic signal blocks),
segregated by directional lines (UP: towards Delhi/origin, DN: away from Delhi/origin).

Tasks, maintenance possessions, and timetable occupancies occur at the BlockSection level,
preventing artificial saturation of multi-station stretches.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from traffic.section_map import PILOT_SECTIONS, PilotSectionConfig, StationStopConfig

DEFAULT_SNAPSHOT_DIR = Path("data/railradar_snapshots")
LONG_BLOCK_THRESHOLD_KM = 25.0
BUSY_OCCUPANCY_SHARE_THRESHOLD = 0.60  # >60% of 1440 minutes occupied


@dataclass
class SplitPoint:
    """An intermediate split point (e.g., intermediate block hut / automatic signal post / cabin)."""
    code: str
    name: str
    km: float
    source: str = "none"


@dataclass
class BlockSection:
    """
    Physical block section between two adjacent stations or block posts along a specific track line.
    """
    id: str  # Deterministic MD5 of f"{from_station}|{to_station}|{line}"
    from_station: str
    to_station: str
    start_km: float
    end_km: float
    line: str  # "UP" | "DN"
    length_km: float
    max_speed: float
    tracks: int  # 2 for standard double-line territory (1 track in each direction)
    split_points_source: str
    station_list_source: str  # "live_timetable" | "hand_written"
    pilot_section_id: str = "SEC-93135bb9"
    name: str = ""
    is_long: bool = False
    is_busy: bool = False
    split_points: List[SplitPoint] = field(default_factory=list)

    def __post_init__(self):
        if not self.name:
            self.name = f"{self.from_station}–{self.to_station} ({self.line})"
        if self.length_km <= 0:
            self.length_km = round(abs(self.end_km - self.start_km), 2)
        if self.length_km > LONG_BLOCK_THRESHOLD_KM:
            self.is_long = True


def make_block_section_id(from_station: str, to_station: str, line: str) -> str:
    """Deterministic 8-hex MD5 identifier for a block section and line."""
    norm = f"{from_station.strip().upper()}|{to_station.strip().upper()}|{line.strip().upper()}"
    return f"BLK-{hashlib.md5(norm.encode('utf-8')).hexdigest()[:8]}"


# Optional intermediate split points configuration for long blocks
OPTIONAL_SPLIT_POINTS: Dict[str, List[SplitPoint]] = {
    # PWL (59.8) to KSV (101.5) on NDLS-MTJ has Hodal (HDL) at km 80.5
    "PWL–KSV": [
        SplitPoint(code="HDL", name="Hodal", km=80.5, source="calibrated_intermediate_halt")
    ],
    "KSV–PWL": [
        SplitPoint(code="HDL", name="Hodal", km=80.5, source="calibrated_intermediate_halt")
    ],
}


def _extract_live_station_list(
    from_code: str, to_code: str, snapshot_dir: Path
) -> Optional[List[StationStopConfig]]:
    """
    Scans live snapshots for an all-stops train with per-stop distances.
    Returns None if no live all-stops snapshot is present.
    """
    if not snapshot_dir.exists():
        return None

    for f in snapshot_dir.glob("*_timetable.json"):
        try:
            with open(f, "r", encoding="utf-8") as fp:
                data = json.load(fp)
            prov = data.get("provenance") or (data.get("meta") or {}).get("provenance")
            if prov != "live":
                continue
            route = (data.get("data") or {}).get("route", [])
            codes = [r.get("station_code") for r in route if r.get("station_code")]
            if from_code in codes and to_code in codes:
                i1, i2 = codes.index(from_code), codes.index(to_code)
                sub_route = route[min(i1, i2) : max(i1, i2) + 1]
                if len(sub_route) >= 4:  # At least intermediate stops
                    stops = []
                    base_dist = sub_route[0].get("distance", 0.0)
                    for r in sub_route:
                        stops.append(
                            StationStopConfig(
                                code=r.get("station_code"),
                                name=r.get("station_name", r.get("station_code")),
                                km_from_start=round(abs(r.get("distance", 0.0) - base_dist), 2),
                                lat=r.get("lat", 0.0),
                                lon=r.get("lon", 0.0),
                            )
                        )
                    return stops
        except Exception:
            pass
    return None


def build_block_sections(
    pilot_section_id: str = "SEC-93135bb9",
    snapshot_dir: Optional[Path] = None,
    split_long_blocks: bool = False,
) -> List[BlockSection]:
    """
    Build ordered block sections for the specified pilot section.
    
    Source preference:
    (a) live all-stops-train timetable snapshot with per-stop distance.
    (b) calibrated pilot stations list marked provenance="hand_written".
    
    Each adjacent station pair generates two directional BlockSection objects:
    - DOWN ('DN'): away from origin (NDLS -> GZB, increasing chainage)
    - UP ('UP'): towards origin (GZB -> NDLS, decreasing chainage)
    """
    cfg = PILOT_SECTIONS.get(pilot_section_id)
    if not cfg:
        # Default to NDLS-GZB if not found
        cfg = PILOT_SECTIONS["SEC-93135bb9"]
        pilot_section_id = "SEC-93135bb9"

    s_dir = snapshot_dir or DEFAULT_SNAPSHOT_DIR
    live_stations = _extract_live_station_list(cfg.from_code, cfg.to_code, s_dir)

    if live_stations and len(live_stations) >= 2:
        stations = live_stations
        station_list_source = "live_timetable"
    else:
        stations = cfg.stations
        station_list_source = "hand_written"

    block_sections: List[BlockSection] = []

    # Sort stations strictly by km_from_start
    ordered_stations = sorted(stations, key=lambda s: s.km_from_start)

    for i in range(len(ordered_stations) - 1):
        s_from = ordered_stations[i]
        s_to = ordered_stations[i + 1]

        seg_length = round(abs(s_to.km_from_start - s_from.km_from_start), 2)
        pair_key = f"{s_from.code}–{s_to.code}"
        rev_pair_key = f"{s_to.code}–{s_from.code}"

        splits = OPTIONAL_SPLIT_POINTS.get(pair_key, []) or OPTIONAL_SPLIT_POINTS.get(rev_pair_key, [])
        splits_source = splits[0].source if splits else "none"

        # Check if splitting is requested for long blocks
        if split_long_blocks and splits and seg_length > LONG_BLOCK_THRESHOLD_KM:
            # Subdivide block by split point
            sub_points = [
                (s_from.code, s_from.km_from_start),
                (splits[0].code, splits[0].km),
                (s_to.code, s_to.km_from_start),
            ]
            for j in range(len(sub_points) - 1):
                p1_code, p1_km = sub_points[j]
                p2_code, p2_km = sub_points[j + 1]
                sub_len = round(abs(p2_km - p1_km), 2)

                # DN Line
                block_sections.append(
                    BlockSection(
                        id=make_block_section_id(p1_code, p2_code, "DN"),
                        from_station=p1_code,
                        to_station=p2_code,
                        start_km=min(p1_km, p2_km),
                        end_km=max(p1_km, p2_km),
                        line="DN",
                        length_km=sub_len,
                        max_speed=cfg.max_speed_kmh,
                        tracks=2,
                        split_points_source=splits_source,
                        station_list_source=station_list_source,
                        pilot_section_id=pilot_section_id,
                        split_points=splits,
                    )
                )
                # UP Line
                block_sections.append(
                    BlockSection(
                        id=make_block_section_id(p2_code, p1_code, "UP"),
                        from_station=p2_code,
                        to_station=p1_code,
                        start_km=min(p1_km, p2_km),
                        end_km=max(p1_km, p2_km),
                        line="UP",
                        length_km=sub_len,
                        max_speed=cfg.max_speed_kmh,
                        tracks=2,
                        split_points_source=splits_source,
                        station_list_source=station_list_source,
                        pilot_section_id=pilot_section_id,
                        split_points=splits,
                    )
                )
        else:
            # Standard station-to-station block section
            # 1. DN line (s_from -> s_to)
            block_sections.append(
                BlockSection(
                    id=make_block_section_id(s_from.code, s_to.code, "DN"),
                    from_station=s_from.code,
                    to_station=s_to.code,
                    start_km=s_from.km_from_start,
                    end_km=s_to.km_from_start,
                    line="DN",
                    length_km=seg_length,
                    max_speed=cfg.max_speed_kmh,
                    tracks=2,
                    split_points_source=splits_source,
                    station_list_source=station_list_source,
                    pilot_section_id=pilot_section_id,
                    split_points=splits,
                )
            )

            # 2. UP line (s_to -> s_from)
            block_sections.append(
                BlockSection(
                    id=make_block_section_id(s_to.code, s_from.code, "UP"),
                    from_station=s_to.code,
                    to_station=s_from.code,
                    start_km=s_from.km_from_start,
                    end_km=s_to.km_from_start,
                    line="UP",
                    length_km=seg_length,
                    max_speed=cfg.max_speed_kmh,
                    tracks=2,
                    split_points_source=splits_source,
                    station_list_source=station_list_source,
                    pilot_section_id=pilot_section_id,
                    split_points=splits,
                )
            )

    return block_sections


# In-memory registry cache
_REGISTRY: Dict[str, BlockSection] = {}


def get_all_pilot_block_sections(
    pilot_section_id: str = "SEC-93135bb9"
) -> List[BlockSection]:
    """Retrieve block sections for a pilot section."""
    sections = build_block_sections(pilot_section_id)
    for bs in sections:
        _REGISTRY[bs.id] = bs
    return sections


def get_block_sections_for_corridor(
    corridor_id: str = "PILOT_NDLS_GZB",
    pilot_section_id: str = "SEC-93135bb9"
) -> List[BlockSection]:
    """Alias for retrieving block sections for a pilot section / corridor."""
    return get_all_pilot_block_sections(pilot_section_id)


def get_block_section_by_id(block_id: str) -> Optional[BlockSection]:
    """Find a block section by its full BLK-xxx ID or 8-char hex."""
    if not block_id:
        return None
    if block_id in _REGISTRY:
        return _REGISTRY[block_id]
    # Ensure all pilot sections are built into registry
    for p_id in PILOT_SECTIONS:
        get_all_pilot_block_sections(p_id)
    if block_id in _REGISTRY:
        return _REGISTRY[block_id]
    for k, v in _REGISTRY.items():
        if k == block_id or k.replace("BLK-", "") == block_id.replace("BLK-", ""):
            return v
    return None


def find_block_section_for_chainage(
    chainage_km: float, line: str = "DN", pilot_section_id: str = "SEC-93135bb9"
) -> Optional[BlockSection]:
    """Find which block section contains a given chainage location on a specific line."""
    sections = get_all_pilot_block_sections(pilot_section_id)
    target_line = line.strip().upper()
    if target_line not in ("UP", "DN"):
        target_line = "DN"

    for bs in sections:
        if bs.line == target_line and (bs.start_km <= chainage_km <= bs.end_km):
            return bs
    # Fallback to closest
    if sections:
        line_sections = [s for s in sections if s.line == target_line]
        if line_sections:
            return min(
                line_sections,
                key=lambda s: min(abs(s.start_km - chainage_km), abs(s.end_km - chainage_km)),
            )
    return None
