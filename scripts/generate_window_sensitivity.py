"""
scripts/generate_window_sensitivity.py

Calculates and prints the Window Sensitivity Report across pilot sections:
(a) Real trains only
(b) Real + synthetic passenger fill
(c) Real + fill + goods (with default protected corridor hours)
(d) Real + fill + goods (unrestricted 24h uniform)
"""
import sys
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from traffic.section_map import get_pilot_sections
from traffic.fill import get_all_passages_for_section, FillerConfig
from traffic.window_finder import find_free_windows, WindowFinderConfig

target_d = date(2026, 11, 1)  # standard pilot test date
pilot_sections = get_pilot_sections()

print("=" * 70)
print("PILOT SECTION WINDOW SENSITIVITY & FILLER RULE REPORT")
print("Target Date: 2026-11-01 (Sunday)")
print("=" * 70)

for sec_id, sec_cfg in pilot_sections.items():
    print(f"\nSECTION: {sec_cfg.name} ({sec_id})")
    print(f"Distance: {sec_cfg.distance_km} km | Max Speed: {sec_cfg.max_speed_kmh} km/h | Density Class: {sec_cfg.density_class}")
    print("-" * 70)

    # (a) Real trains only
    p_real, cov_real = get_all_passages_for_section(sec_cfg, target_d, include_fill=False, include_goods=False)
    w_real = find_free_windows(sec_cfg, target_d, passages=p_real)

    # (b) Real + synthetic_fill
    p_fill, cov_fill = get_all_passages_for_section(sec_cfg, target_d, include_fill=True, include_goods=False)
    w_fill = find_free_windows(sec_cfg, target_d, passages=p_fill)

    # (c) Real + fill + goods (default protected corridor hours 05:00-23:59)
    cfg_prot = FillerConfig(restrict_passenger_to_operational_hours=True)
    p_full, cov_full = get_all_passages_for_section(sec_cfg, target_d, include_fill=True, include_goods=True, filler_config=cfg_prot)
    w_full = find_free_windows(sec_cfg, target_d, passages=p_full)

    # (d) Real + fill + goods (unrestricted 24h uniform random)
    cfg_unrest = FillerConfig(restrict_passenger_to_operational_hours=False, restrict_goods_to_operational_hours=False)
    p_unrest, cov_unrest = get_all_passages_for_section(sec_cfg, target_d, include_fill=True, include_goods=True, filler_config=cfg_unrest)
    w_unrest = find_free_windows(sec_cfg, target_d, passages=p_unrest)

    print(f"Variant (a) Real Trains Only:")
    print(f"  Daily Trains: {cov_real.total_trains} | Real: {cov_real.real_trains} | Coverage: {cov_real.coverage_pct}%")
    print(f"  Free Windows ({len(w_real)}):")
    for w in w_real:
        print(f"    - [{w.start_time.strftime('%H:%M')} – {w.end_time.strftime('%H:%M')}] duration: {w.duration_hours:.2f}h")

    print(f"\nVariant (b) Real + Passenger Filler:")
    print(f"  Daily Trains: {cov_fill.total_trains} | Real: {cov_fill.real_trains} | Fill: {cov_fill.synthetic_fill_trains} | Coverage: {cov_fill.coverage_pct}%")
    print(f"  Free Windows ({len(w_fill)}):")
    for w in w_fill:
        print(f"    - [{w.start_time.strftime('%H:%M')} – {w.end_time.strftime('%H:%M')}] duration: {w.duration_hours:.2f}h")

    print(f"\nVariant (c) Real + Fill + Goods (Default Protected Corridor Block Hours):")
    print(f"  Daily Trains: {cov_full.total_trains} | Real: {cov_full.real_trains} | Fill: {cov_full.synthetic_fill_trains} | Goods: {cov_full.synthetic_goods_trains} | Coverage: {cov_full.coverage_pct}%")
    print(f"  Free Windows ({len(w_full)}):")
    for w in w_full:
        print(f"    - [{w.start_time.strftime('%H:%M')} – {w.end_time.strftime('%H:%M')}] duration: {w.duration_hours:.2f}h")

    print(f"\nVariant (d) Real + Fill + Goods (Unrestricted 24h Uniform Distribution):")
    print(f"  Daily Trains: {cov_unrest.total_trains} | Real: {cov_unrest.real_trains} | Fill: {cov_unrest.synthetic_fill_trains} | Goods: {cov_unrest.synthetic_goods_trains} | Coverage: {cov_unrest.coverage_pct}%")
    print(f"  Free Windows ({len(w_unrest)}):")
    for w in w_unrest:
        print(f"    - [{w.start_time.strftime('%H:%M')} – {w.end_time.strftime('%H:%M')}] duration: {w.duration_hours:.2f}h")

print("=" * 70)
