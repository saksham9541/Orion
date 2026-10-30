"""
traffic/seed_snapshots.py

Populates data/railradar_snapshots/ with realistic RailRadar offline seed snapshots for:
1. Pilot station trains-between (NDLS-GZB and NDLS-MTJ)
2. Corridor route geometries with station coordinates (12302 Howrah Rajdhani, 12952 Mumbai Rajdhani)
3. Timetable schedules with station halts, cumulative distances, and running days

Ensures offline testability without burning live RailRadar API keys.
"""
import json
from pathlib import Path

SNAPSHOT_DIR = Path(__file__).resolve().parent.parent / "data" / "railradar_snapshots"
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)


def generate_seed_snapshots():
    # ------------------------------------------------------------------
    # 1. Route Geometries (GeoJSON LineString with stations)
    # ------------------------------------------------------------------
    route_12302 = {
        "success": True,
        "data": {
            "train_number": "12302",
            "train_name": "Howrah Rajdhani Express",
            "type": "LineString",
            "coordinates": [
                [77.2205, 28.6424],  # NDLS
                [77.2300, 28.6300],  # CSB
                [77.2415, 28.6247],  # TKJ
                [77.2750, 28.6350],  # Yamuna bridge
                [77.3153, 28.6502],  # ANVT
                [77.3592, 28.6728],  # SBB
                [77.4338, 28.6675],  # GZB
                [77.7000, 28.5000],  # towards Aligarh / Kanpur
                [80.3500, 26.4500],  # CNB
            ],
            "stations": [
                {"code": "NDLS", "name": "New Delhi", "lat": 28.6424, "lon": 77.2205, "distance_km": 0.0},
                {"code": "CSB", "name": "Shivaji Bridge", "lat": 28.6300, "lon": 77.2300, "distance_km": 1.5},
                {"code": "TKJ", "name": "Tilak Bridge", "lat": 28.6247, "lon": 77.2415, "distance_km": 2.7},
                {"code": "ANVT", "name": "Anand Vihar", "lat": 28.6502, "lon": 77.3153, "distance_km": 12.5},
                {"code": "SBB", "name": "Sahibabad", "lat": 28.6728, "lon": 77.3592, "distance_km": 15.0},
                {"code": "GZB", "name": "Ghaziabad", "lat": 28.6675, "lon": 77.4338, "distance_km": 19.0},
                {"code": "CNB", "name": "Kanpur Central", "lat": 26.4500, "lon": 80.3500, "distance_km": 440.0},
            ]
        },
        "meta": {"source": "snapshot", "corridor": "Delhi–Howrah Main"}
    }
    with open(SNAPSHOT_DIR / "train_12302_route.json", "w", encoding="utf-8") as f:
        json.dump(route_12302, f, indent=2)

    route_12952 = {
        "success": True,
        "data": {
            "train_number": "12952",
            "train_name": "Mumbai Central Tejas Rajdhani Express",
            "type": "LineString",
            "coordinates": [
                [77.2205, 28.6424],  # NDLS
                [77.2534, 28.5886],  # NZM
                [77.2730, 28.5582],  # OKA
                [77.2917, 28.5034],  # TKD
                [77.3178, 28.4124],  # FDB
                [77.3235, 28.3370],  # BVH
                [77.3298, 28.1458],  # PWL
                [77.4312, 27.7915],  # KSV
                [77.5023, 27.7198],  # CHJ
                [77.6737, 27.4924],  # MTJ
                [77.7200, 27.1800],  # AGC
            ],
            "stations": [
                {"code": "NDLS", "name": "New Delhi", "lat": 28.6424, "lon": 77.2205, "distance_km": 0.0},
                {"code": "NZM", "name": "Hazrat Nizamuddin", "lat": 28.5886, "lon": 77.2534, "distance_km": 7.2},
                {"code": "OKA", "name": "Okhla", "lat": 28.5582, "lon": 77.2730, "distance_km": 10.8},
                {"code": "TKD", "name": "Tuglakabad", "lat": 28.5034, "lon": 77.2917, "distance_km": 17.5},
                {"code": "FDB", "name": "Faridabad", "lat": 28.4124, "lon": 77.3178, "distance_km": 28.5},
                {"code": "BVH", "name": "Ballabgarh", "lat": 28.3370, "lon": 77.3235, "distance_km": 36.8},
                {"code": "PWL", "name": "Palwal", "lat": 28.1458, "lon": 77.3298, "distance_km": 59.8},
                {"code": "KSV", "name": "Kosi Kalan", "lat": 27.7915, "lon": 77.4312, "distance_km": 101.5},
                {"code": "CHJ", "name": "Chata", "lat": 27.7198, "lon": 77.5023, "distance_km": 114.2},
                {"code": "MTJ", "name": "Mathura Jn", "lat": 27.4924, "lon": 77.6737, "distance_km": 141.0},
            ]
        },
        "meta": {"source": "snapshot", "corridor": "Delhi–Mumbai Rajdhani Route"}
    }
    with open(SNAPSHOT_DIR / "train_12952_route.json", "w", encoding="utf-8") as f:
        json.dump(route_12952, f, indent=2)

    # ------------------------------------------------------------------
    # 2. Trains Between Stations
    # ------------------------------------------------------------------
    between_ndls_gzb = {
        "success": True,
        "data": {
            "from_station": "NDLS",
            "to_station": "GZB",
            "trains": [
                {"train_number": "12302", "train_name": "Howrah Rajdhani", "train_type": "RAJDHANI", "departure_time": "16:50", "arrival_time": "17:15", "running_days": [0,1,2,3,4,5,6]},
                {"train_number": "12301", "train_name": "Howrah Rajdhani (Up)", "train_type": "RAJDHANI", "departure_time": "05:35", "arrival_time": "06:00", "running_days": [0,1,2,3,4,5,6]},
                {"train_number": "12004", "train_name": "Lucknow Shatabdi", "train_type": "SHATABDI", "departure_time": "06:10", "arrival_time": "06:42", "running_days": [0,1,2,3,4,5,6]},
                {"train_number": "12003", "train_name": "Lucknow Shatabdi (Up)", "train_type": "SHATABDI", "departure_time": "21:38", "arrival_time": "22:25", "running_days": [0,1,2,3,4,5,6]},
                {"train_number": "12313", "train_name": "Sealdah Rajdhani", "train_type": "RAJDHANI", "departure_time": "16:30", "arrival_time": "16:55", "running_days": [0,1,2,3,4,5,6]},
                {"train_number": "12424", "train_name": "Dibrugarh Rajdhani", "train_type": "RAJDHANI", "departure_time": "16:20", "arrival_time": "16:45", "running_days": [0,1,2,3,4,5,6]},
                {"train_number": "12560", "train_name": "Shiv Ganga Express", "train_type": "SUPERFAST", "departure_time": "20:05", "arrival_time": "20:32", "running_days": [0,1,2,3,4,5,6]},
                {"train_number": "12444", "train_name": "Anand Vihar - Haldia SF", "train_type": "SUPERFAST", "departure_time": "20:20", "arrival_time": "20:47", "running_days": [1]},
            ]
        },
        "meta": {"source": "snapshot"}
    }
    with open(SNAPSHOT_DIR / "train_between_NDLS_GZB.json", "w", encoding="utf-8") as f:
        json.dump(between_ndls_gzb, f, indent=2)

    between_ndls_mtj = {
        "success": True,
        "data": {
            "from_station": "NDLS",
            "to_station": "MTJ",
            "trains": [
                {"train_number": "12952", "train_name": "Mumbai Rajdhani", "train_type": "RAJDHANI", "departure_time": "16:55", "arrival_time": "18:25", "running_days": [0,1,2,3,4,5,6]},
                {"train_number": "12951", "train_name": "Mumbai Rajdhani (Up)", "train_type": "RAJDHANI", "departure_time": "06:50", "arrival_time": "08:32", "running_days": [0,1,2,3,4,5,6]},
                {"train_number": "12002", "train_name": "Bhopal Shatabdi", "train_type": "SHATABDI", "departure_time": "06:00", "arrival_time": "07:19", "running_days": [0,1,2,3,4,5,6]},
                {"train_number": "12001", "train_name": "Bhopal Shatabdi (Up)", "train_type": "SHATABDI", "departure_time": "21:20", "arrival_time": "23:50", "running_days": [0,1,2,3,4,5,6]},
                {"train_number": "22692", "train_name": "Bengaluru Rajdhani", "train_type": "RAJDHANI", "departure_time": "20:45", "arrival_time": "22:20", "running_days": [0,1,2,3,4,5,6]},
                {"train_number": "12954", "train_name": "August Kranti Rajdhani", "train_type": "RAJDHANI", "departure_time": "17:15", "arrival_time": "18:43", "running_days": [0,1,2,3,4,5,6]},
                {"train_number": "12432", "train_name": "Trivandrum Rajdhani", "train_type": "RAJDHANI", "departure_time": "06:16", "arrival_time": "07:55", "running_days": [2,5,6]},
                {"train_number": "12926", "train_name": "Paschim Express", "train_type": "SUPERFAST", "departure_time": "16:35", "arrival_time": "19:10", "running_days": [0,1,2,3,4,5,6]},
            ]
        },
        "meta": {"source": "snapshot"}
    }
    with open(SNAPSHOT_DIR / "train_between_NDLS_MTJ.json", "w", encoding="utf-8") as f:
        json.dump(between_ndls_mtj, f, indent=2)

    # ------------------------------------------------------------------
    # 3. Individual Train Timetables (Halts + Distances)
    # ------------------------------------------------------------------
    timetables = [
        # 12302 Howrah Rajdhani (Down: NDLS -> GZB -> CNB -> HWH)
        {
            "train": {"number": "12302", "name": "Howrah Rajdhani", "type": "RAJDHANI"},
            "running_days": [0, 1, 2, 3, 4, 5, 6],
            "route": [
                {"station_code": "NDLS", "station_name": "New Delhi", "arrival": "16:50", "departure": "16:50", "distance": 0.0, "day": 1},
                {"station_code": "CNB", "station_name": "Kanpur Central", "arrival": "21:32", "departure": "21:37", "distance": 440.0, "day": 1},
                {"station_code": "HWH", "station_name": "Howrah Junction", "arrival": "09:55", "departure": "09:55", "distance": 1450.0, "day": 2},
            ]
        },
        # 12301 Howrah Rajdhani (Up: HWH -> CNB -> GZB -> NDLS)
        {
            "train": {"number": "12301", "name": "Howrah Rajdhani (Up)", "type": "RAJDHANI"},
            "running_days": [0, 1, 2, 3, 4, 5, 6],
            "route": [
                {"station_code": "HWH", "station_name": "Howrah Junction", "arrival": "16:50", "departure": "16:50", "distance": 0.0, "day": 1},
                {"station_code": "CNB", "station_name": "Kanpur Central", "arrival": "00:50", "departure": "00:55", "distance": 1010.0, "day": 2},
                {"station_code": "NDLS", "station_name": "New Delhi", "arrival": "06:00", "departure": "06:00", "distance": 1450.0, "day": 2},
            ]
        },
        # 12004 Lucknow Shatabdi (NDLS -> GZB (halt) -> LKO)
        {
            "train": {"number": "12004", "name": "Lucknow Shatabdi", "type": "SHATABDI"},
            "running_days": [0, 1, 2, 3, 4, 5, 6],
            "route": [
                {"station_code": "NDLS", "station_name": "New Delhi", "arrival": "06:10", "departure": "06:10", "distance": 0.0, "day": 1},
                {"station_code": "GZB", "station_name": "Ghaziabad", "arrival": "06:42", "departure": "06:44", "distance": 19.0, "day": 1},
                {"station_code": "CNB", "station_name": "Kanpur Central", "arrival": "11:20", "departure": "11:25", "distance": 440.0, "day": 1},
                {"station_code": "LKO", "station_name": "Lucknow Ne", "arrival": "12:40", "departure": "12:40", "distance": 512.0, "day": 1},
            ]
        },
        # 12003 Lucknow Shatabdi (Up: LKO -> GZB (halt) -> NDLS)
        {
            "train": {"number": "12003", "name": "Lucknow Shatabdi (Up)", "type": "SHATABDI"},
            "running_days": [0, 1, 2, 3, 4, 5, 6],
            "route": [
                {"station_code": "LKO", "station_name": "Lucknow Ne", "arrival": "15:30", "departure": "15:30", "distance": 0.0, "day": 1},
                {"station_code": "GZB", "station_name": "Ghaziabad", "arrival": "21:38", "departure": "21:40", "distance": 493.0, "day": 1},
                {"station_code": "NDLS", "station_name": "New Delhi", "arrival": "22:25", "departure": "22:25", "distance": 512.0, "day": 1},
            ]
        },
        # 12313 Sealdah Rajdhani (NDLS -> CNB -> SDAH)
        {
            "train": {"number": "12313", "name": "Sealdah Rajdhani", "type": "RAJDHANI"},
            "running_days": [0, 1, 2, 3, 4, 5, 6],
            "route": [
                {"station_code": "NDLS", "station_name": "New Delhi", "arrival": "16:30", "departure": "16:30", "distance": 0.0, "day": 1},
                {"station_code": "CNB", "station_name": "Kanpur Central", "arrival": "21:15", "departure": "21:20", "distance": 440.0, "day": 1},
                {"station_code": "SDAH", "station_name": "Sealdah", "arrival": "10:05", "departure": "10:05", "distance": 1458.0, "day": 2},
            ]
        },
        # 12424 Dibrugarh Rajdhani
        {
            "train": {"number": "12424", "name": "Dibrugarh Rajdhani", "type": "RAJDHANI"},
            "running_days": [0, 1, 2, 3, 4, 5, 6],
            "route": [
                {"station_code": "NDLS", "station_name": "New Delhi", "arrival": "16:20", "departure": "16:20", "distance": 0.0, "day": 1},
                {"station_code": "CNB", "station_name": "Kanpur Central", "arrival": "21:02", "departure": "21:07", "distance": 440.0, "day": 1},
            ]
        },
        # 12560 Shiv Ganga Express (NDLS -> BSBS)
        {
            "train": {"number": "12560", "name": "Shiv Ganga Express", "type": "SUPERFAST"},
            "running_days": [0, 1, 2, 3, 4, 5, 6],
            "route": [
                {"station_code": "NDLS", "station_name": "New Delhi", "arrival": "20:05", "departure": "20:05", "distance": 0.0, "day": 1},
                {"station_code": "CNB", "station_name": "Kanpur Central", "arrival": "01:40", "departure": "01:45", "distance": 440.0, "day": 2},
            ]
        },
        # 12444 Haldia Superfast
        {
            "train": {"number": "12444", "name": "Anand Vihar Haldia SF", "type": "SUPERFAST"},
            "running_days": [1],  # Tuesday only
            "route": [
                {"station_code": "ANVT", "station_name": "Anand Vihar", "arrival": "20:20", "departure": "20:20", "distance": 0.0, "day": 1},
                {"station_code": "GZB", "station_name": "Ghaziabad", "arrival": "20:47", "departure": "20:49", "distance": 13.0, "day": 1},
                {"station_code": "CNB", "station_name": "Kanpur Central", "arrival": "01:10", "departure": "01:15", "distance": 428.0, "day": 2},
            ]
        },
        # 12952 Mumbai Central Tejas Rajdhani (NDLS -> MTJ pass -> KOTA)
        {
            "train": {"number": "12952", "name": "Mumbai Rajdhani", "type": "RAJDHANI"},
            "running_days": [0, 1, 2, 3, 4, 5, 6],
            "route": [
                {"station_code": "NDLS", "station_name": "New Delhi", "arrival": "16:55", "departure": "16:55", "distance": 0.0, "day": 1},
                {"station_code": "KOTA", "station_name": "Kota Junction", "arrival": "21:30", "departure": "21:40", "distance": 465.0, "day": 1},
                {"station_code": "MMCT", "station_name": "Mumbai Central", "arrival": "08:35", "departure": "08:35", "distance": 1384.0, "day": 2},
            ]
        },
        # 12951 Mumbai Rajdhani (Up: MMCT -> KOTA -> MTJ pass -> NDLS)
        {
            "train": {"number": "12951", "name": "Mumbai Rajdhani (Up)", "type": "RAJDHANI"},
            "running_days": [0, 1, 2, 3, 4, 5, 6],
            "route": [
                {"station_code": "MMCT", "station_name": "Mumbai Central", "arrival": "17:00", "departure": "17:00", "distance": 0.0, "day": 1},
                {"station_code": "KOTA", "station_name": "Kota Junction", "arrival": "03:15", "departure": "03:20", "distance": 919.0, "day": 2},
                {"station_code": "NDLS", "station_name": "New Delhi", "arrival": "08:32", "departure": "08:32", "distance": 1384.0, "day": 2},
            ]
        },
        # 12002 Bhopal Shatabdi (NDLS -> MTJ (halt) -> AGC)
        {
            "train": {"number": "12002", "name": "Bhopal Shatabdi", "type": "SHATABDI"},
            "running_days": [0, 1, 2, 3, 4, 5, 6],
            "route": [
                {"station_code": "NDLS", "station_name": "New Delhi", "arrival": "06:00", "departure": "06:00", "distance": 0.0, "day": 1},
                {"station_code": "MTJ", "station_name": "Mathura Junction", "arrival": "07:19", "departure": "07:20", "distance": 141.0, "day": 1},
                {"station_code": "AGC", "station_name": "Agra Cantt", "arrival": "07:50", "departure": "07:55", "distance": 195.0, "day": 1},
            ]
        },
        # 12001 Bhopal Shatabdi (Up: AGC -> MTJ (halt) -> NDLS)
        {
            "train": {"number": "12001", "name": "Bhopal Shatabdi (Up)", "type": "SHATABDI"},
            "running_days": [0, 1, 2, 3, 4, 5, 6],
            "route": [
                {"station_code": "AGC", "station_name": "Agra Cantt", "arrival": "20:30", "departure": "20:35", "distance": 0.0, "day": 1},
                {"station_code": "MTJ", "station_name": "Mathura Junction", "arrival": "21:20", "departure": "21:25", "distance": 54.0, "day": 1},
                {"station_code": "NDLS", "station_name": "New Delhi", "arrival": "23:50", "departure": "23:50", "distance": 195.0, "day": 1},
            ]
        },
        # 22692 Bengaluru Rajdhani (NZM -> AGC)
        {
            "train": {"number": "22692", "name": "Bengaluru Rajdhani", "type": "RAJDHANI"},
            "running_days": [0, 1, 2, 3, 4, 5, 6],
            "route": [
                {"station_code": "NZM", "station_name": "Hazrat Nizamuddin", "arrival": "20:45", "departure": "20:45", "distance": 0.0, "day": 1},
                {"station_code": "AGC", "station_name": "Agra Cantt", "arrival": "22:50", "departure": "22:55", "distance": 188.0, "day": 1},
            ]
        },
        # 12954 August Kranti Rajdhani (NZM -> MTJ (halt) -> KOTA)
        {
            "train": {"number": "12954", "name": "August Kranti Rajdhani", "type": "RAJDHANI"},
            "running_days": [0, 1, 2, 3, 4, 5, 6],
            "route": [
                {"station_code": "NZM", "station_name": "Hazrat Nizamuddin", "arrival": "17:15", "departure": "17:15", "distance": 0.0, "day": 1},
                {"station_code": "MTJ", "station_name": "Mathura Junction", "arrival": "18:43", "departure": "18:45", "distance": 134.0, "day": 1},
                {"station_code": "KOTA", "station_name": "Kota Junction", "arrival": "22:00", "departure": "22:10", "distance": 458.0, "day": 1},
            ]
        },
        # 12432 Trivandrum Rajdhani (NZM -> KOTA)
        {
            "train": {"number": "12432", "name": "Trivandrum Rajdhani", "type": "RAJDHANI"},
            "running_days": [2, 5, 6],  # Tue, Fri, Sat
            "route": [
                {"station_code": "NZM", "station_name": "Hazrat Nizamuddin", "arrival": "06:16", "departure": "06:16", "distance": 0.0, "day": 1},
                {"station_code": "KOTA", "station_name": "Kota Junction", "arrival": "10:40", "departure": "10:50", "distance": 458.0, "day": 1},
            ]
        },
        # 12926 Paschim Express (NDLS -> MTJ -> KOTA)
        {
            "train": {"number": "12926", "name": "Paschim Express", "type": "SUPERFAST"},
            "running_days": [0, 1, 2, 3, 4, 5, 6],
            "route": [
                {"station_code": "NDLS", "station_name": "New Delhi", "arrival": "16:20", "departure": "16:35", "distance": 0.0, "day": 1},
                {"station_code": "FDB", "station_name": "Faridabad", "arrival": "17:01", "departure": "17:03", "distance": 28.5, "day": 1},
                {"station_code": "MTJ", "station_name": "Mathura Junction", "arrival": "19:08", "departure": "19:10", "distance": 141.0, "day": 1},
                {"station_code": "KOTA", "station_name": "Kota Junction", "arrival": "00:10", "departure": "00:20", "distance": 465.0, "day": 2},
            ]
        },
    ]

    for tt in timetables:
        t_num = tt["train"]["number"]
        payload = {
            "success": True,
            "data": tt,
            "meta": {"source": "snapshot"}
        }
        with open(SNAPSHOT_DIR / f"train_{t_num}_timetable.json", "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)


if __name__ == "__main__":
    generate_seed_snapshots()
    print(f"Generated seed snapshots in {SNAPSHOT_DIR}")
