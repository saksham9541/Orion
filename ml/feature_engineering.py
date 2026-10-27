import pandas as pd
import numpy as np
from railopt.models import MaintenanceTask, Section, BlockWindow, get_season, TrainSlot

class TaskFeatureExtractor:
    """Extracts features from maintenance tasks for ML models."""
    def transform(self, tasks: list[MaintenanceTask], sections: dict[str, Section]) -> pd.DataFrame:
        features = []
        for task in tasks:
            section = sections.get(task.section_id)
            
            # Defaults
            traffic_density = "B"
            is_single_line = False
            if section:
                traffic_density = section.traffic_density_class.value
                is_single_line = section.is_single_line
                
            season = get_season(task.reported_date).value
            
            row = {
                "task_id": task.task_id,
                "department": task.department.value,
                "asset_type": task.asset_type.value,
                "defect_category": task.defect_category.value,
                "days_overdue": task.days_overdue,
                "log_days_overdue": np.log1p(max(0, task.days_overdue)),
                "asset_age_years": task.asset_age_years,
                "historical_failure_count": task.historical_failure_count,
                "traffic_density_class": traffic_density,
                "is_safety_critical": int(task.is_safety_critical),
                "is_single_line": int(is_single_line),
                "requires_power_block": int(task.requires_power_block),
                "crew_size_required": task.crew_size_required,
                "season": season,
                "deferred_count": task.deferred_count
            }
            features.append(row)
        
        df = pd.DataFrame(features)
        return df

from datetime import time

def _times_overlap(a_start: time, a_end: time, b_start: time, b_end: time) -> bool:
    """Check if two time ranges overlap, handling midnight crossing."""
    from datetime import datetime, date as date_cls
    ref = date_cls(2000, 1, 1)
    def to_range(s, e):
        s_dt = datetime.combine(ref, s)
        e_dt = datetime.combine(ref, e)
        if e_dt <= s_dt:
            e_dt = e_dt.replace(day=2)  # crosses midnight
        return s_dt, e_dt
    a_s, a_e = to_range(a_start, a_end)
    b_s, b_e = to_range(b_start, b_end)
    return a_s < b_e and b_s < a_e

class BlockWindowFeatureExtractor:
    """Extracts features from block windows for impact prediction."""
    def transform(self, windows: list[BlockWindow], sections: dict[str, Section], timetable_data: dict = None, train_slots: list[TrainSlot] = None) -> pd.DataFrame:
        features = []
        for window in windows:
            section = sections.get(window.section_id)
            
            # Defaults
            traffic_density = "B"
            is_single_line = False
            alt_routes = 0
            if section:
                traffic_density = section.traffic_density_class.value
                is_single_line = section.is_single_line
                alt_routes = len(section.alternate_routes)
                
            day_of_week = window.date.weekday()
            is_weekend = int(day_of_week >= 5)
            start_hour = window.start_time.hour
            
            trains_in_window = 0
            if train_slots:
                for slot in train_slots:
                    if slot.section_id == window.section_id:
                        if _times_overlap(window.start_time, window.end_time, slot.arrival_time, slot.departure_time):
                            trains_in_window += 1
            
            row = {
                "window_id": window.window_id,
                "section_traffic_density": traffic_density,
                "block_duration_hours": window.duration_hours,
                "block_start_hour": start_hour,
                "day_of_week": day_of_week,
                "is_single_line": int(is_single_line),
                "trains_in_window": trains_in_window,
                "alternate_routes_count": alt_routes,
                "is_weekend": is_weekend
            }
            features.append(row)
            
        return pd.DataFrame(features)
