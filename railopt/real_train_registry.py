"""
RailOpt — Curated real train numbers mapped to synthetic corridor names.

Corridor NAMES are stable across /api/demo/setup runs; corridor_id is a
random UUID regenerated each run, so this registry keys on name and gets
resolved against app.state.corridors at sync time.

Fill these in with real train numbers that actually run each named route.
Leave a corridor's list empty if you don't want it live-tracked.
"""

REAL_TRAIN_REGISTRY: dict[str, list[str]] = {
    "Delhi–Howrah Main": ["12302", "12301", "12313"],       
    "Delhi–Mumbai Rajdhani Route": ["12951", "12952", "12953"], 
    "Delhi–Amritsar Main": ["12013", "12014"],
    "Delhi–Kalka Suburban": ["12005", "12011"],
    "Delhi–Meerut RRTS": [], 
    "Delhi–Rewari": ["14323", "04499"],
    "Delhi–Rohtak": ["14731"],
    "Delhi–Saharanpur": ["14545"],
    "Delhi–Chennai Rajdhani": ["12434", "12433"],
    "Delhi–Jaipur": ["12986", "12015"],
}


def resolve_train_corridor_map(corridors: list) -> dict[str, str]:
    """train_number -> current-run corridor_id, built from the name registry."""
    name_to_id = {c.name: c.corridor_id for c in corridors}
    result: dict[str, str] = {}
    for corridor_name, train_numbers in REAL_TRAIN_REGISTRY.items():
        corridor_id = name_to_id.get(corridor_name)
        if not corridor_id:
            continue
        for tn in train_numbers:
            result[tn] = corridor_id
    return result