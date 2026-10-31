import uuid
import os
from datetime import datetime
from typing import List, Dict, Any

from railopt.models import MaintenanceTask, Department, AssetType, DefectCategory, TaskStatus, Section

class BaseAdapter:
    def _resolve_section(self, km_location: float, corridor_id: str, sections: list[Section]) -> tuple[str, str]:
        if not sections:
            return (corridor_id or "default_corridor", "default_section")
        
        filtered = [s for s in sections if s.corridor_id == corridor_id] if corridor_id else sections
        if not filtered:
            return (corridor_id or "default_corridor", "default_section")
            
        for s in filtered:
            if min(s.start_km, s.end_km) <= km_location <= max(s.start_km, s.end_km):
                return (s.corridor_id, s.section_id)
                
        return (filtered[0].corridor_id, filtered[0].section_id)


class TMSAdapter(BaseAdapter):
    """Adapter for Track Management System records."""
    def parse(self, raw_records: List[Dict[str, Any]], corridor_id: str = None, sections: list[Section] = None) -> List[MaintenanceTask]:
        tasks = []
        # Mapping TMS defect codes to unified DefectCategory
        defect_map = {
            "RF-001": DefectCategory.RAIL_FRACTURE,
            "RC-001": DefectCategory.RAIL_CRACK,
            "GI-001": DefectCategory.GAUGE_IRREGULARITY,
            "SD-001": DefectCategory.SLEEPER_DAMAGE,
            "BD-001": DefectCategory.BALLAST_DEFICIENCY
        }
        
        for r in raw_records:
            cat = defect_map.get(r.get("defect_code", ""), DefectCategory.ALIGNMENT_DEFECT)
            
            # Asset type mapping based on category
            if cat in [DefectCategory.RAIL_FRACTURE, DefectCategory.RAIL_CRACK]:
                asset = AssetType.RAIL
            elif cat == DefectCategory.SLEEPER_DAMAGE:
                asset = AssetType.SLEEPER
            elif cat == DefectCategory.BALLAST_DEFICIENCY:
                asset = AssetType.BALLAST
            else:
                asset = AssetType.TRACK_BED
                
            reported_date = datetime.strptime(r.get("inspection_date", "2023-01-01"), "%Y-%m-%d").date()
            km_loc = float(r.get("km_from", 0.0))
            corr_id, sec_id = self._resolve_section(km_loc, corridor_id, sections)

            tasks.append(MaintenanceTask(
                source_system="TMS",
                source_record_id=r.get("track_id", f"TMS-{uuid.uuid4().hex[:6]}"),
                department=Department.ENGINEERING,
                asset_type=asset,
                defect_category=cat,
                raw_severity=r.get("priority", "P3"),
                corridor_id=corr_id,
                section_id=sec_id,
                km_location=km_loc,
                km_start=km_loc,
                km_end=float(r.get("km_to", 0.0)),
                reported_date=reported_date,
                inspector_remarks=f"{r.get('inspector_name', 'Unknown')}: {r.get('remarks', '')}"
            ))
        return tasks


class SMMSAdapter(BaseAdapter):
    """Adapter for Signal Maintenance Management System records."""
    def parse(self, raw_records: List[Dict[str, Any]], corridor_id: str = None, sections: list[Section] = None) -> List[MaintenanceTask]:
        tasks = []
        defect_map = {
            "SIGNAL": DefectCategory.SIGNAL_FAILURE,
            "RELAY": DefectCategory.RELAY_MALFUNCTION,
            "POINT": DefectCategory.POINT_FAILURE,
            "TRACK_CIRCUIT": DefectCategory.TRACK_CIRCUIT_FAILURE,
            "CABLE": DefectCategory.CABLE_DAMAGE
        }
        
        for r in raw_records:
            fault = r.get("fault_type", "SIGNAL")
            cat = defect_map.get(fault, DefectCategory.SIGNAL_FAILURE)
            
            if cat == DefectCategory.SIGNAL_FAILURE:
                asset = AssetType.SIGNAL_POST
            elif cat == DefectCategory.RELAY_MALFUNCTION:
                asset = AssetType.RELAY
            elif cat == DefectCategory.POINT_FAILURE:
                asset = AssetType.POINT_MACHINE
            elif cat == DefectCategory.TRACK_CIRCUIT_FAILURE:
                asset = AssetType.TRACK_CIRCUIT
            else:
                asset = AssetType.TELECOM_CABLE
                
            reported_date = datetime.strptime(r.get("report_date", "2023-01-01"), "%Y-%m-%d").date()
            corr_id, sec_id = self._resolve_section(0.0, corridor_id, sections)

            tasks.append(MaintenanceTask(
                source_system="SMMS",
                source_record_id=r.get("equipment_id", f"SMMS-{uuid.uuid4().hex[:6]}"),
                department=Department.SNT,
                asset_type=asset,
                defect_category=cat,
                raw_severity=r.get("severity_class", "Minor"),
                corridor_id=corr_id,
                section_id=sec_id,
                km_location=0.0,  # Specific to station mostly
                reported_date=reported_date,
                inspector_remarks=f"{r.get('reported_by', 'Unknown')} at {r.get('location_station', 'Unknown')}: {r.get('description', '')}"
            ))
        return tasks


class TDMSAdapter(BaseAdapter):
    """Adapter for Traction Distribution Management System records."""
    def parse(self, raw_records: List[Dict[str, Any]], corridor_id: str = None, sections: list[Section] = None) -> List[MaintenanceTask]:
        tasks = []
        defect_map = {
            "OHE_SAG": DefectCategory.OHE_SAG,
            "OHE_BREAK": DefectCategory.OHE_BREAK,
            "INSULATOR_FLASH": DefectCategory.INSULATOR_DAMAGE,
            "MAST_TILT": DefectCategory.MAST_TILT,
            "FEEDER_FAULT": DefectCategory.FEEDER_TRIP
        }
        
        for r in raw_records:
            mode = r.get("failure_mode", "OHE_SAG")
            cat = defect_map.get(mode, DefectCategory.OHE_SAG)
            
            if cat in [DefectCategory.OHE_SAG, DefectCategory.OHE_BREAK]:
                asset = AssetType.OHE_WIRE
            elif cat == DefectCategory.INSULATOR_DAMAGE:
                asset = AssetType.INSULATOR
            elif cat == DefectCategory.MAST_TILT:
                asset = AssetType.MAST
            else:
                asset = AssetType.FEEDER

            reported_date = datetime.strptime(r.get("detection_date", "2023-01-01"), "%Y-%m-%d").date()
            corr_id, sec_id = self._resolve_section(0.0, corridor_id, sections)

            tasks.append(MaintenanceTask(
                source_system="TDMS",
                source_record_id=r.get("ohe_section", f"TDMS-{uuid.uuid4().hex[:6]}"),
                department=Department.TRD,
                asset_type=asset,
                defect_category=cat,
                raw_severity=str(r.get("priority_level", "3")),
                corridor_id=corr_id,
                section_id=sec_id,
                km_location=0.0,
                reported_date=reported_date,
                inspector_remarks=f"Mast {r.get('mast_number', '')} / Feeder {r.get('feeder_id', '')}: {r.get('notes', '')}",
                requires_power_block=True
            ))
        return tasks


class COAAdapter(BaseAdapter):
    """Adapter for Control Office Application records."""
    def parse(self, raw_records: List[Dict[str, Any]], corridor_id: str = None, sections: list[Section] = None) -> List[Any]:
        # Implementation placeholder for timetable integration
        return []


class DataIntegrationService:
    """Service to orchestrate parsing from all sub-systems."""
    def __init__(self):
        self.tms_adapter = TMSAdapter()
        self.smms_adapter = SMMSAdapter()
        self.tdms_adapter = TDMSAdapter()
        self.coa_adapter = COAAdapter()

        # RailRadar live train status client
        from railopt.railradar_client import RailRadarClient
        keys_str = os.environ.get("RAILRADAR_API_KEYS", "")
        keys = [k.strip() for k in keys_str.split(",") if k.strip()]
        base_url = os.environ.get("RAILRADAR_BASE_URL", "https://api.railradar.in/v1")
        self.railradar_adapter = RailRadarClient(keys=keys if keys else None, base_url=base_url)
        
    def integrate_maintenance_data(
        self, 
        tms_data: List[Dict[str, Any]], 
        smms_data: List[Dict[str, Any]], 
        tdms_data: List[Dict[str, Any]],
        corridor_id: str = None,
        sections: list[Section] = None
    ) -> List[MaintenanceTask]:
        
        tasks = []
        tasks.extend(self.tms_adapter.parse(tms_data, corridor_id, sections))
        tasks.extend(self.smms_adapter.parse(smms_data, corridor_id, sections))
        tasks.extend(self.tdms_adapter.parse(tdms_data, corridor_id, sections))
        
        # Here we could perform deduplication and cross-department validation
        return tasks

if __name__ == "__main__":
    tms_sample = [{
        "track_id": "TRK-001",
        "defect_code": "RF-001",
        "km_from": 105.5,
        "km_to": 105.5,
        "priority": "P1",
        "inspector_name": "R. Kumar",
        "inspection_date": "2023-10-15",
        "remarks": "Major rail fracture spotted"
    }]
    
    smms_sample = [{
        "equipment_id": "SIG-42",
        "fault_type": "SIGNAL",
        "location_station": "Ghaziabad",
        "severity_class": "Critical",
        "reported_by": "S. Singh",
        "report_date": "2023-10-16",
        "description": "Aspect blank on up line"
    }]
    
    tdms_sample = [{
        "ohe_section": "SEC-009",
        "component_type": "Insulator",
        "failure_mode": "INSULATOR_FLASH",
        "priority_level": 1,
        "detection_date": "2023-10-14",
        "mast_number": "M-120",
        "feeder_id": "F-02",
        "notes": "Flashed insulator leading to power trip"
    }]
    
    service = DataIntegrationService()
    integrated_tasks = service.integrate_maintenance_data(tms_sample, smms_sample, tdms_sample)
    
    for task in integrated_tasks:
        print(f"Task: {task.task_id} | Dept: {task.department.value} | Cat: {task.defect_category.value} | Remarks: {task.inspector_remarks}")
