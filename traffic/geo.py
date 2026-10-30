"""
traffic/geo.py

Track geometry and chainage mapping along pilot railway sections.
Provides:
- Polyline extraction from snapshot route geometry with fallback to station coordinates
- Chainage calculation (km along track from start station)
- locate(section_id, km) -> (lat, lon)
- nearest_chainage(section_id, lat, lon) -> float (km)

Chainage along curved track is labeled approximate.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from traffic.section_map import get_pilot_section_config, PilotSectionConfig

DEFAULT_SNAPSHOT_DIR = Path(__file__).resolve().parent.parent / "data" / "railradar_snapshots"

# Section -> Corridor train route snapshot mapping
PILOT_SECTION_ROUTE_SNAPSHOTS = {
    "SEC-93135bb9": "train_12302_route.json",  # Delhi-Howrah corridor
    "SEC-d4d8b85c": "train_12952_route.json",  # Delhi-Mumbai corridor
}


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great circle distance in kilometers between two points on Earth."""
    r = 6371.0  # Earth radius in kilometers
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return r * c


@dataclass
class SectionPolyline:
    """Polyline geometry and chainage distances for a track section."""
    section_id: str
    name: str
    points: List[Tuple[float, float]]  # List of (lat, lon)
    cumulative_km: List[float] = field(default_factory=list)
    total_length_km: float = 0.0
    is_approximate: bool = True

    def __post_init__(self):
        if not self.cumulative_km and len(self.points) >= 2:
            raw_cum = [0.0]
            for i in range(1, len(self.points)):
                p1 = self.points[i - 1]
                p2 = self.points[i]
                d = haversine_km(p1[0], p1[1], p2[0], p2[1])
                raw_cum.append(raw_cum[-1] + d)

            raw_total = raw_cum[-1]
            target_total = self.total_length_km or raw_total

            # Scale cumulative distances to precisely match the target section track length
            scale = (target_total / raw_total) if raw_total > 0 else 1.0
            self.cumulative_km = [round(c * scale, 3) for c in raw_cum]
            self.total_length_km = target_total


# In-memory cached polylines
_POLYLINE_CACHE: Dict[str, SectionPolyline] = {}


def load_section_polyline(section_id: str, snapshot_dir: Optional[Path] = None) -> SectionPolyline:
    """
    Builds the polyline for a pilot section from:
    1. Snapshot route coordinates (if present)
    2. Fallback to stations list from section_map.py
    """
    if section_id in _POLYLINE_CACHE:
        return _POLYLINE_CACHE[section_id]

    cfg = get_pilot_section_config(section_id)
    if not cfg:
        # Generic fallback for non-pilot section: returns 2-point straight line
        poly = SectionPolyline(
            section_id=section_id,
            name=section_id,
            points=[(28.6424, 77.2205), (28.6675, 77.4338)],
            total_length_km=20.0,
            is_approximate=True,
        )
        _POLYLINE_CACHE[section_id] = poly
        return poly

    s_dir = snapshot_dir or DEFAULT_SNAPSHOT_DIR
    route_file = s_dir / PILOT_SECTION_ROUTE_SNAPSHOTS.get(section_id, "")
    extracted_points: List[Tuple[float, float]] = []

    if route_file.exists():
        try:
            with open(route_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            geo_data = data.get("data", {})
            coords = geo_data.get("coordinates", [])
            # Route coords can be [[lon, lat], ...] or [[lat, lon], ...]
            for c in coords:
                if len(c) >= 2:
                    # Detect lon vs lat by India bounds (lat ~8-36, lon ~68-98)
                    if 60.0 <= c[0] <= 100.0 and 5.0 <= c[1] <= 40.0:
                        lat, lon = c[1], c[0]
                    else:
                        lat, lon = c[0], c[1]
                    extracted_points.append((lat, lon))
        except Exception:
            extracted_points = []

    # If route geometry didn't produce enough points, use station coordinates
    if len(extracted_points) < 2 and cfg.stations:
        extracted_points = [(s.lat, s.lon) for s in cfg.stations]

    # Ensure first point is start station and last point is end station
    if cfg.stations:
        start_pt = (cfg.stations[0].lat, cfg.stations[0].lon)
        end_pt = (cfg.stations[-1].lat, cfg.stations[-1].lon)
        if not extracted_points:
            extracted_points = [start_pt, end_pt]
        else:
            extracted_points[0] = start_pt
            extracted_points[-1] = end_pt

    poly = SectionPolyline(
        section_id=section_id,
        name=cfg.name,
        points=extracted_points,
        total_length_km=cfg.distance_km,
        is_approximate=True,
    )
    _POLYLINE_CACHE[section_id] = poly
    return poly


def locate(section_id: str, km: float) -> Tuple[float, float]:
    """
    Interpolate (lat, lon) on the track polyline for a given chainage (km from start station).
    Returns (lat, lon).
    """
    poly = load_section_polyline(section_id)
    pts = poly.points
    cum = poly.cumulative_km

    if len(pts) < 2 or not cum:
        return (28.6424, 77.2205)

    if km <= cum[0]:
        return pts[0]
    if km >= cum[-1]:
        return pts[-1]

    # Find segment [i-1, i]
    for i in range(1, len(cum)):
        if km <= cum[i]:
            d_start = cum[i - 1]
            d_end = cum[i]
            seg_len = d_end - d_start
            fraction = (km - d_start) / seg_len if seg_len > 0 else 0.0
            p1 = pts[i - 1]
            p2 = pts[i]
            lat = p1[0] + fraction * (p2[0] - p1[0])
            lon = p1[1] + fraction * (p2[1] - p1[1])
            return round(lat, 5), round(lon, 5)

    return pts[-1]


def nearest_chainage(section_id: str, lat: float, lon: float) -> float:
    """
    Finds the nearest track chainage (km from start station) for a given (lat, lon).
    Label: Approximate track distance.
    """
    poly = load_section_polyline(section_id)
    pts = poly.points
    cum = poly.cumulative_km

    if len(pts) < 2:
        return 0.0

    best_dist = float("inf")
    best_chainage = 0.0

    for i in range(len(pts) - 1):
        p1 = pts[i]
        p2 = pts[i + 1]

        # Project point onto segment p1-p2 in Euclidean space (adequate for localized segments)
        dx = p2[1] - p1[1]
        dy = p2[0] - p1[0]
        seg_len_sq = dx * dx + dy * dy

        if seg_len_sq == 0:
            t = 0.0
        else:
            t = max(0.0, min(1.0, ((lon - p1[1]) * dx + (lat - p1[0]) * dy) / seg_len_sq))

        proj_lat = p1[0] + t * dy
        proj_lon = p1[1] + t * dx
        d = haversine_km(lat, lon, proj_lat, proj_lon)

        if d < best_dist:
            best_dist = d
            d_start = cum[i]
            d_end = cum[i + 1]
            best_chainage = d_start + t * (d_end - d_start)

    return round(best_chainage, 2)
