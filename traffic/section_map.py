"""
traffic/section_map.py

Pilot section registry and real station code mapping for Indian Railways pilot sections:
1. New Delhi – Ghaziabad (SEC-93135bb9)
2. New Delhi – Mathura Jn (SEC-d4d8b85c)

Designed with dataclass configs so new sections can be easily added by configuration.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class StationStopConfig:
    """Represents a physical railway station or junction stop along a section."""
    code: str
    name: str
    km_from_start: float
    lat: float
    lon: float


@dataclass
class PilotSectionConfig:
    """Configuration for a pilot track section with real station codes and geometry attributes."""
    section_id: str
    name: str
    corridor_name: str
    from_code: str
    to_code: str
    distance_km: float
    max_speed_kmh: float
    density_class: str
    has_alternate_route: bool
    alternate_route_penalty_minutes: float
    stations: List[StationStopConfig] = field(default_factory=list)

    @property
    def station_codes(self) -> List[str]:
        return [s.code for s in self.stations]


# ----------------------------------------------------------------------
# Pilot Section Definitions
# ----------------------------------------------------------------------

PILOT_SECTIONS: Dict[str, PilotSectionConfig] = {
    "SEC-93135bb9": PilotSectionConfig(
        section_id="SEC-93135bb9",
        name="New Delhi–Ghaziabad",
        corridor_name="Delhi–Howrah Main",
        from_code="NDLS",
        to_code="GZB",
        distance_km=19.0,
        max_speed_kmh=130.0,
        density_class="A_SPECIAL",
        has_alternate_route=True,
        alternate_route_penalty_minutes=22.0,  # via DLI-DSA-GZB loop
        stations=[
            StationStopConfig(code="NDLS", name="New Delhi", km_from_start=0.0, lat=28.6424, lon=77.2205),
            StationStopConfig(code="CSB", name="Shivaji Bridge", km_from_start=1.5, lat=28.6300, lon=77.2300),
            StationStopConfig(code="TKJ", name="Tilak Bridge", km_from_start=2.7, lat=28.6247, lon=77.2415),
            StationStopConfig(code="ANVT", name="Anand Vihar Terminal", km_from_start=12.5, lat=28.6502, lon=77.3153),
            StationStopConfig(code="SBB", name="Sahibabad Junction", km_from_start=15.0, lat=28.6728, lon=77.3592),
            StationStopConfig(code="GZB", name="Ghaziabad Junction", km_from_start=19.0, lat=28.6675, lon=77.4338),
        ],
    ),
    "SEC-d4d8b85c": PilotSectionConfig(
        section_id="SEC-d4d8b85c",
        name="New Delhi–Mathura Jn",
        corridor_name="Delhi–Mumbai Rajdhani Route",
        from_code="NDLS",
        to_code="MTJ",
        distance_km=141.0,
        max_speed_kmh=130.0,
        density_class="A_SPECIAL",
        has_alternate_route=True,
        alternate_route_penalty_minutes=45.0,  # via Aligarh-Mitawali detour
        stations=[
            StationStopConfig(code="NDLS", name="New Delhi", km_from_start=0.0, lat=28.6424, lon=77.2205),
            StationStopConfig(code="NZM", name="Hazrat Nizamuddin", km_from_start=7.2, lat=28.5886, lon=77.2534),
            StationStopConfig(code="OKA", name="Okhla", km_from_start=10.8, lat=28.5582, lon=77.2730),
            StationStopConfig(code="TKD", name="Tuglakabad", km_from_start=17.5, lat=28.5034, lon=77.2917),
            StationStopConfig(code="FDB", name="Faridabad", km_from_start=28.5, lat=28.4124, lon=77.3178),
            StationStopConfig(code="BVH", name="Ballabgarh", km_from_start=36.8, lat=28.3370, lon=77.3235),
            StationStopConfig(code="PWL", name="Palwal", km_from_start=59.8, lat=28.1458, lon=77.3298),
            StationStopConfig(code="KSV", name="Kosi Kalan", km_from_start=101.5, lat=27.7915, lon=77.4312),
            StationStopConfig(code="CHJ", name="Chata", km_from_start=114.2, lat=27.7198, lon=77.5023),
            StationStopConfig(code="MTJ", name="Mathura Junction", km_from_start=141.0, lat=27.4924, lon=77.6737),
        ],
    ),
}

# Alias mapping by normalized name or station pair
_NAME_TO_PILOT_ID = {
    "NEW DELHI-GHAZIABAD": "SEC-93135bb9",
    "NEW DELHI–GHAZIABAD": "SEC-93135bb9",
    "NDLS-GZB": "SEC-93135bb9",
    "NEW DELHI-MATHURA JN": "SEC-d4d8b85c",
    "NEW DELHI–MATHURA JN": "SEC-d4d8b85c",
    "NEW DELHI-MATHURA": "SEC-d4d8b85c",
    "NDLS-MTJ": "SEC-d4d8b85c",
}


def get_pilot_sections() -> Dict[str, PilotSectionConfig]:
    """Return all configured pilot section specifications."""
    return PILOT_SECTIONS


def is_pilot_section(section_id_or_name: str) -> bool:
    """Check if a section is within the real timetable pilot scope."""
    if not section_id_or_name:
        return False
    if section_id_or_name in PILOT_SECTIONS:
        return True
    norm = section_id_or_name.strip().upper().replace(" ", "")
    for k, v in _NAME_TO_PILOT_ID.items():
        if k.replace(" ", "") == norm:
            return True
    return False


def get_pilot_section_config(section_id_or_name: str) -> Optional[PilotSectionConfig]:
    """Retrieve the pilot section configuration if recognized."""
    if not section_id_or_name:
        return None
    if section_id_or_name in PILOT_SECTIONS:
        return PILOT_SECTIONS[section_id_or_name]
    norm = section_id_or_name.strip().upper().replace(" ", "")
    for k, sid in _NAME_TO_PILOT_ID.items():
        if k.replace(" ", "") == norm:
            return PILOT_SECTIONS[sid]
    return None
