"""
RailOpt — Core domain models for maintenance block planning.

Defines the unified data schema that normalizes defect/maintenance records
from TMS (Track), SMMS (Signal & Telecom), and TDMS (Traction Distribution)
into a single comparable format, along with corridor, timetable, and block
planning models.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# ──────────────────────────────────────────────────────────────────────
# Enumerations
# ──────────────────────────────────────────────────────────────────────

class UserRole(str, Enum):
    ADMIN = "ADMIN"
    CONTROLLER = "CONTROLLER"
    DEPT_USER = "DEPT_USER"
    VIEWER = "VIEWER"

class Department(str, Enum):
    """Three maintenance departments of Indian Railways."""
    ENGINEERING = "ENGINEERING"   # Track, bridges, earthwork, formation
    SNT = "SNT"                   # Signals & Telecommunication
    TRD = "TRD"                   # Traction Distribution (OHE, power supply)


class AssetType(str, Enum):
    """Asset types across all three departments."""
    # Engineering
    RAIL = "RAIL"
    SLEEPER = "SLEEPER"
    BALLAST = "BALLAST"
    BRIDGE = "BRIDGE"
    LEVEL_CROSSING = "LEVEL_CROSSING"
    TRACK_BED = "TRACK_BED"
    FORMATION = "FORMATION"
    TURNOUT = "TURNOUT"
    WELD_JOINT = "WELD_JOINT"
    # S&T
    SIGNAL_POST = "SIGNAL_POST"
    RELAY = "RELAY"
    POINT_MACHINE = "POINT_MACHINE"
    AXLE_COUNTER = "AXLE_COUNTER"
    TELECOM_CABLE = "TELECOM_CABLE"
    TRACK_CIRCUIT = "TRACK_CIRCUIT"
    INTERLOCKING = "INTERLOCKING"
    LED_SIGNAL = "LED_SIGNAL"
    # TRD
    OHE_WIRE = "OHE_WIRE"
    INSULATOR = "INSULATOR"
    MAST = "MAST"
    TRANSFORMER = "TRANSFORMER"
    CIRCUIT_BREAKER = "CIRCUIT_BREAKER"
    PANTOGRAPH_ZONE = "PANTOGRAPH_ZONE"
    FEEDER = "FEEDER"


# Mapping: which assets belong to which department
ASSET_DEPARTMENT_MAP: dict[AssetType, Department] = {
    # Engineering
    AssetType.RAIL: Department.ENGINEERING,
    AssetType.SLEEPER: Department.ENGINEERING,
    AssetType.BALLAST: Department.ENGINEERING,
    AssetType.BRIDGE: Department.ENGINEERING,
    AssetType.LEVEL_CROSSING: Department.ENGINEERING,
    AssetType.TRACK_BED: Department.ENGINEERING,
    AssetType.FORMATION: Department.ENGINEERING,
    AssetType.TURNOUT: Department.ENGINEERING,
    AssetType.WELD_JOINT: Department.ENGINEERING,
    # S&T
    AssetType.SIGNAL_POST: Department.SNT,
    AssetType.RELAY: Department.SNT,
    AssetType.POINT_MACHINE: Department.SNT,
    AssetType.AXLE_COUNTER: Department.SNT,
    AssetType.TELECOM_CABLE: Department.SNT,
    AssetType.TRACK_CIRCUIT: Department.SNT,
    AssetType.INTERLOCKING: Department.SNT,
    AssetType.LED_SIGNAL: Department.SNT,
    # TRD
    AssetType.OHE_WIRE: Department.TRD,
    AssetType.INSULATOR: Department.TRD,
    AssetType.MAST: Department.TRD,
    AssetType.TRANSFORMER: Department.TRD,
    AssetType.CIRCUIT_BREAKER: Department.TRD,
    AssetType.PANTOGRAPH_ZONE: Department.TRD,
    AssetType.FEEDER: Department.TRD,
}


class DefectCategory(str, Enum):
    """Categorized defect types across departments."""
    # Engineering defect categories
    RAIL_FRACTURE = "RAIL_FRACTURE"
    RAIL_CRACK = "RAIL_CRACK"
    GAUGE_IRREGULARITY = "GAUGE_IRREGULARITY"
    ALIGNMENT_DEFECT = "ALIGNMENT_DEFECT"
    CROSS_LEVEL_DEFECT = "CROSS_LEVEL_DEFECT"
    SLEEPER_DAMAGE = "SLEEPER_DAMAGE"
    BALLAST_DEFICIENCY = "BALLAST_DEFICIENCY"
    BRIDGE_CORROSION = "BRIDGE_CORROSION"
    WELD_DEFECT = "WELD_DEFECT"
    FORMATION_FAILURE = "FORMATION_FAILURE"
    LEVEL_CROSSING_DEFECT = "LEVEL_CROSSING_DEFECT"
    # S&T defect categories
    SIGNAL_FAILURE = "SIGNAL_FAILURE"
    RELAY_MALFUNCTION = "RELAY_MALFUNCTION"
    POINT_FAILURE = "POINT_FAILURE"
    TRACK_CIRCUIT_FAILURE = "TRACK_CIRCUIT_FAILURE"
    CABLE_DAMAGE = "CABLE_DAMAGE"
    INTERLOCKING_FAULT = "INTERLOCKING_FAULT"
    AXLE_COUNTER_ERROR = "AXLE_COUNTER_ERROR"
    # TRD defect categories
    OHE_SAG = "OHE_SAG"
    OHE_BREAK = "OHE_BREAK"
    INSULATOR_DAMAGE = "INSULATOR_DAMAGE"
    MAST_TILT = "MAST_TILT"
    TRANSFORMER_FAULT = "TRANSFORMER_FAULT"
    FEEDER_TRIP = "FEEDER_TRIP"
    PANTOGRAPH_SCRATCH = "PANTOGRAPH_SCRATCH"
    # Cross-department / environmental
    WATERLOGGING = "WATERLOGGING"
    EMBANKMENT_SLIP = "EMBANKMENT_SLIP"


class DefectSeverity(str, Enum):
    """Unified severity levels — used as ML model output class."""
    EMERGENCY = "EMERGENCY"   # Immediate attention, safety threat
    HIGH = "HIGH"             # Fix within 7 days
    MEDIUM = "MEDIUM"         # Scheduled window within 30 days
    LOW = "LOW"               # Deferrable, planned maintenance


class TaskStatus(str, Enum):
    """Lifecycle status of a maintenance task."""
    DRAFT = "DRAFT"               # Created by user/dept, not yet submitted
    SUBMITTED = "SUBMITTED"       # Submitted for ML scoring & verification
    SCORED = "SCORED"             # ML scoring & criticality calculated
    UNVERIFIED = "UNVERIFIED"     # Complaint submitted, waiting for technician verification
    PENDING = "PENDING"           # Verified and awaiting scheduling
    SCHEDULED = "SCHEDULED"       # Assigned to a block
    IN_PROGRESS = "IN_PROGRESS"   # Work underway
    COMPLETED = "COMPLETED"       # Work finished
    DEFERRED = "DEFERRED"         # Postponed to next cycle
    ESCALATED = "ESCALATED"       # Auto-escalated by SLA engine
    CANCELLED = "CANCELLED"       # Cancelled by user/controller
    REJECTED = "REJECTED"         # Found to be fake/invalid by technician


class BlockType(str, Enum):
    """Types of maintenance blocks on Indian Railways."""
    TRAFFIC_BLOCK = "TRAFFIC_BLOCK"     # Complete train suspension
    NON_TRAFFIC = "NON_TRAFFIC"         # Work between trains
    POWER_BLOCK = "POWER_BLOCK"         # OHE power disconnection (TRD)
    COMBINED = "COMBINED"               # Traffic + Power block together


class TrainType(str, Enum):
    """Train categories for timetable and impact analysis."""
    RAJDHANI = "RAJDHANI"
    SHATABDI = "SHATABDI"
    DURONTO = "DURONTO"
    VANDE_BHARAT = "VANDE_BHARAT"
    GARIB_RATH = "GARIB_RATH"
    SUPERFAST = "SUPERFAST"
    MAIL_EXPRESS = "MAIL_EXPRESS"
    PASSENGER = "PASSENGER"
    FREIGHT = "FREIGHT"
    SUBURBAN = "SUBURBAN"
    MILITARY = "MILITARY"


class TrafficDensityClass(str, Enum):
    """Section traffic density classification."""
    A_SPECIAL = "A_SPECIAL"   # > 60 trains/day
    A = "A"                   # 40-60 trains/day
    B = "B"                   # 20-40 trains/day
    C = "C"                   # 10-20 trains/day
    D = "D"                   # < 10 trains/day


class PlanHorizon(str, Enum):
    """Planning horizons."""
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"


class PlanStatus(str, Enum):
    """Lifecycle status for a block plan."""
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    MODIFIED = "MODIFIED"


class Season(str, Enum):
    """Indian seasons for risk adjustment."""
    SUMMER = "SUMMER"           # Mar-May: rail buckling risk
    EXTREME_HEAT = "EXTREME_HEAT"  # May-Jun: peak heat, OHE sag
    MONSOON = "MONSOON"         # Jul-Sep: formation, earthwork risk
    POST_MONSOON = "POST_MONSOON"  # Oct-Nov: track settling
    WINTER = "WINTER"           # Dec-Jan: fog, visibility issues
    FOG = "FOG"                 # Dec-Feb: dense fog belt (North India)


# ──────────────────────────────────────────────────────────────────────
# SLA / Safety Constants
# ──────────────────────────────────────────────────────────────────────

# Maximum deferral window (hours) by severity — exceeding triggers escalation
MAX_DEFERRAL_HOURS: dict[DefectSeverity, int] = {
    DefectSeverity.EMERGENCY: 24,
    DefectSeverity.HIGH: 168,       # 7 days
    DefectSeverity.MEDIUM: 720,     # 30 days
    DefectSeverity.LOW: 2160,       # 90 days
}

# Safety-critical defect categories — always get floor severity of HIGH
SAFETY_CRITICAL_DEFECTS: set[DefectCategory] = {
    DefectCategory.RAIL_FRACTURE,
    DefectCategory.RAIL_CRACK,
    DefectCategory.SIGNAL_FAILURE,
    DefectCategory.POINT_FAILURE,
    DefectCategory.INTERLOCKING_FAULT,
    DefectCategory.OHE_BREAK,
    DefectCategory.BRIDGE_CORROSION,
    DefectCategory.TRACK_CIRCUIT_FAILURE,
}

# Defects that are always EMERGENCY
ALWAYS_EMERGENCY: set[DefectCategory] = {
    DefectCategory.RAIL_FRACTURE,
    DefectCategory.OHE_BREAK,
    DefectCategory.INTERLOCKING_FAULT,
}


def get_season(d: date) -> Season:
    """Determine Indian Railways season from date."""
    month = d.month
    if month in (3, 4):
        return Season.SUMMER
    elif month in (5, 6):
        return Season.EXTREME_HEAT
    elif 7 <= month <= 9:
        return Season.MONSOON
    elif month in (10, 11):
        return Season.POST_MONSOON
    elif month in (12, 1):
        return Season.FOG
    else:
        return Season.WINTER


# ──────────────────────────────────────────────────────────────────────
# Domain Models
# ──────────────────────────────────────────────────────────────────────

class Section(BaseModel):
    """A track section between two points on a corridor."""
    section_id: str = Field(default_factory=lambda: f"SEC-{uuid.uuid4().hex[:8]}")
    corridor_id: str
    name: str                                  # e.g. "Ghaziabad–Hapur"
    start_station: str
    end_station: str
    start_km: float
    end_km: float
    length_km: float = 0.0
    max_speed_kmh: float = 110.0
    is_single_line: bool = False
    electrified: bool = True
    traffic_density_class: TrafficDensityClass = TrafficDensityClass.B
    daily_train_count: int = 30
    alternate_routes: list[str] = Field(default_factory=list)  # section IDs

    def model_post_init(self, __context: object) -> None:
        if self.length_km == 0.0:
            self.length_km = abs(self.end_km - self.start_km)


class Corridor(BaseModel):
    """A railway corridor — a logical grouping of contiguous sections."""
    corridor_id: str = Field(default_factory=lambda: f"COR-{uuid.uuid4().hex[:8]}")
    name: str                                  # e.g. "Delhi–Howrah Main"
    division: str                              # e.g. "Delhi Division"
    zone: str                                  # e.g. "Northern Railway"
    sections: list[Section] = Field(default_factory=list)
    source: str = "synthetic"                  # "synthetic" | "user"
    total_length_km: float = 0.0
    is_rajdhani_route: bool = False            # Strategic route flag

    def model_post_init(self, __context: object) -> None:
        if self.total_length_km == 0.0 and self.sections:
            self.total_length_km = sum(s.length_km for s in self.sections)


class MaintenanceTask(BaseModel):
    """
    Unified maintenance task record — the core entity of the system.
    Normalizes records from TMS (Engineering), SMMS (S&T), and TDMS (TRD)
    into a single comparable schema.
    """
    task_id: str = Field(default_factory=lambda: f"MT-{uuid.uuid4().hex[:8]}")
    source_system: str = ""                    # "TMS" | "SMMS" | "TDMS"
    source_record_id: str = ""                 # Original ID in source system
    source: str = "synthetic"                  # "synthetic" | "user"

    # Department & asset identification
    department: Department
    asset_type: AssetType
    asset_id: str = ""                         # Specific asset identifier
    defect_category: DefectCategory
    raw_severity: str = ""                     # Original severity from source system

    # Location
    corridor_id: str
    section_id: str
    km_location: float                         # Kilometer marker
    km_start: float = 0.0                      # Start of affected stretch
    km_end: float = 0.0                        # End of affected stretch

    # Timing
    reported_date: date
    due_date: Optional[date] = None
    days_overdue: int = 0

    # Characteristics
    inspector_remarks: str = ""                # Free-text field notes
    is_safety_critical: bool = False
    requires_power_block: bool = False         # True for TRD/OHE work
    requires_traffic_block: bool = True
    crew_size_required: int = 4
    tools_special: list[str] = Field(default_factory=list)

    # Asset metadata
    asset_age_years: float = 0.0
    historical_failure_count: int = 0          # At this location
    last_maintenance_date: Optional[date] = None

    # ML-filled fields (populated by the ML engine)
    ml_criticality_score: float = 0.0          # 0-100, cross-dept comparable
    ml_predicted_severity: Optional[DefectSeverity] = None
    ml_predicted_duration_hours: float = 0.0
    ml_duration_confidence_lower: float = 0.0  # P25
    ml_duration_confidence_upper: float = 0.0  # P75
    ml_shap_values: dict[str, float] = Field(default_factory=dict)

    # Scheduling
    estimated_duration_hours: float = 2.0      # Manual estimate
    status: TaskStatus = TaskStatus.PENDING
    assigned_block_id: Optional[str] = None
    deferred_count: int = 0                    # Times deferred previously

    # Issue tracking & notifications
    department_designated: Optional[str] = None
    created_by: Optional[str] = None
    created_by_department: Optional[str] = None
    created_at: Optional[datetime] = None


    def model_post_init(self, __context: object) -> None:
        if self.km_end == 0.0:
            self.km_end = self.km_location
        if self.km_start == 0.0:
            self.km_start = self.km_location
        if self.defect_category in SAFETY_CRITICAL_DEFECTS:
            self.is_safety_critical = True
        if self.department == Department.TRD:
            self.requires_power_block = True


class TrainSlot(BaseModel):
    """A train's scheduled passage through a section."""
    train_number: str
    train_name: str = ""
    train_type: TrainType
    corridor_id: str
    section_id: str
    arrival_time: time                         # At section start
    departure_time: time                       # From section end
    days_of_week: list[int] = Field(default_factory=lambda: list(range(7)))  # 0=Mon


class LiveTrainStatus(BaseModel):
    """
    Live position/delay snapshot for one REAL train, pulled from RailRadar.

    This is a separate live layer, not a replacement for TrainSlot: TrainSlot
    holds the synthetic/scheduled timetable used by the ML + optimizer
    pipeline, while LiveTrainStatus holds real delay/status for a curated
    set of real train numbers (see railopt.real_train_registry), resolved
    against whichever corridor_id exists in the current run.
    """
    train_number: str
    train_name: str = ""
    corridor_id: str = ""            # resolved via real_train_registry
    section_id: str = ""             # best-effort only — not guaranteed accurate
    delay_minutes: float = 0.0
    status: str = "UNKNOWN"          # e.g. RUNNING / DELAYED / TERMINATED
    last_updated: datetime = Field(default_factory=datetime.now)
    source: str = "RAILRADAR"


class BlockWindow(BaseModel):
    """An available time window for maintenance on a section."""
    window_id: str = Field(default_factory=lambda: f"BW-{uuid.uuid4().hex[:8]}")
    corridor_id: str
    section_id: str
    date: date
    start_time: time
    end_time: time
    duration_hours: float = 0.0
    block_type: BlockType = BlockType.TRAFFIC_BLOCK
    max_tasks: int = 5                         # Max tasks in this window

    # ML-filled fields
    ml_traffic_impact_score: float = 0.0       # 0-100
    ml_trains_affected: int = 0
    ml_cumulative_delay_minutes: float = 0.0

    def model_post_init(self, __context: object) -> None:
        if self.duration_hours == 0.0:
            start_dt = datetime.combine(self.date, self.start_time)
            end_dt = datetime.combine(self.date, self.end_time)
            if end_dt < start_dt:  # Crosses midnight
                end_dt += timedelta(days=1)
            self.duration_hours = (end_dt - start_dt).total_seconds() / 3600


class ScheduledBlock(BaseModel):
    """A finalized maintenance block in a plan — may contain tasks from multiple depts."""
    block_id: str = Field(default_factory=lambda: f"SB-{uuid.uuid4().hex[:8]}")
    window_id: str                             # Which BlockWindow this uses
    corridor_id: str
    section_id: str
    section_name: str = ""
    date: date
    start_time: time
    end_time: time
    duration_hours: float = 0.0
    block_type: BlockType = BlockType.TRAFFIC_BLOCK
    source: str = "synthetic"                  # "synthetic" | "user"

    # Tasks assigned
    task_ids: list[str] = Field(default_factory=list)
    departments: list[Department] = Field(default_factory=list)
    is_merged: bool = False                    # Multi-department block

    # Impact metrics
    trains_affected: int = 0
    cumulative_delay_minutes: float = 0.0
    total_criticality_score: float = 0.0       # Sum of task criticalities

    # Justification
    justification: str = ""                    # Why these tasks, why this window
    merge_savings_hours: float = 0.0           # Hours saved vs. separate blocks


class BlockPlan(BaseModel):
    """The output: an optimized maintenance block schedule."""
    plan_id: str = Field(default_factory=lambda: f"BP-{uuid.uuid4().hex[:8]}")
    horizon: PlanHorizon
    start_date: date
    end_date: date
    created_at: datetime = Field(default_factory=datetime.now)
    source: str = "synthetic"                  # "synthetic" | "user"

    # The schedule
    scheduled_blocks: list[ScheduledBlock] = Field(default_factory=list)

    # Metrics
    total_tasks_scheduled: int = 0
    total_tasks_deferred: int = 0
    total_block_hours: float = 0.0
    total_merge_savings_hours: float = 0.0
    total_trains_affected: int = 0
    sla_compliance_pct: float = 100.0
    departments_summary: dict[str, int] = Field(default_factory=dict)

    # Solver diagnostics (Add 7)
    solver_status: str = ""
    solve_time_ms: float = 0.0

    # Approval workflow (Add 3)
    status: PlanStatus = PlanStatus.DRAFT
    approved_by: str = ""
    override_log: list[dict] = Field(default_factory=list)

    # Deferred tasks
    deferred_task_ids: list[str] = Field(default_factory=list)
    escalated_task_ids: list[str] = Field(default_factory=list)

    def compute_metrics(self, tasks: list[MaintenanceTask]) -> None:
        """Compute summary metrics from scheduled blocks."""
        self.total_tasks_scheduled = sum(
            len(b.task_ids) for b in self.scheduled_blocks
        )
        self.total_block_hours = sum(
            b.duration_hours for b in self.scheduled_blocks
        )
        self.total_merge_savings_hours = sum(
            b.merge_savings_hours for b in self.scheduled_blocks
        )
        self.total_trains_affected = sum(
            b.trains_affected for b in self.scheduled_blocks
        )
        # BUG FIX: this was never set, so it silently stayed at the
        # Pydantic default of 0 regardless of how many tasks were actually
        # deferred — inconsistent with sla_compliance_pct below, which
        # correctly reflects unscheduled safety-critical tasks.
        self.total_tasks_deferred = len(self.deferred_task_ids)

        # Department breakdown
        dept_counts: dict[str, int] = {}
        for block in self.scheduled_blocks:
            for dept in block.departments:
                dept_counts[dept.value] = dept_counts.get(dept.value, 0) + len([
                    tid for tid in block.task_ids
                    if any(t.task_id == tid and t.department == dept for t in tasks)
                ])
        self.departments_summary = dept_counts

        # SLA compliance
        total_critical = len([
            t for t in tasks if t.is_safety_critical and t.status != TaskStatus.COMPLETED
        ])
        scheduled_critical = len([
            t for t in tasks
            if t.is_safety_critical and t.status == TaskStatus.SCHEDULED
        ])
        if total_critical > 0:
            self.sla_compliance_pct = round(
                (scheduled_critical / total_critical) * 100, 1
            )


class EarlyWarning(BaseModel):
    """Proactive risk alert from the early warning agent."""
    warning_id: str = Field(default_factory=lambda: f"EW-{uuid.uuid4().hex[:8]}")
    corridor_id: str
    section_id: str
    asset_type: AssetType
    risk_level: DefectSeverity
    message: str
    trend_data: dict[str, float] = Field(default_factory=dict)
    recommended_action: str = ""
    estimated_failure_window_days: int = 0
    created_at: datetime = Field(default_factory=datetime.now)


class AgentProposal(BaseModel):
    """A block request proposal from a department agent."""
    proposal_id: str = Field(default_factory=lambda: f"AP-{uuid.uuid4().hex[:8]}")
    department: Department
    task_ids: list[str]
    preferred_window_id: str
    corridor_id: str
    section_id: str
    preferred_date: date
    preferred_start_time: time
    preferred_end_time: time
    priority_justification: str = ""
    is_negotiable: bool = True                 # Can this be moved?
    alternative_window_ids: list[str] = Field(default_factory=list)


class NegotiationResult(BaseModel):
    """Outcome of multi-agent negotiation for a contested corridor window."""
    result_id: str = Field(default_factory=lambda: f"NR-{uuid.uuid4().hex[:8]}")
    window_id: str
    corridor_id: str
    section_id: str
    date: date
    proposals_received: list[str] = Field(default_factory=list)     # proposal IDs
    accepted_proposals: list[str] = Field(default_factory=list)
    rejected_proposals: list[str] = Field(default_factory=list)
    is_merged: bool = False
    resolution_method: str = ""                # "merged" | "priority_override" | "rescheduled"
    justification: str = ""


class SimulationReport(BaseModel):
    """Output of the what-if simulator."""
    report_id: str = Field(default_factory=lambda: f"SR-{uuid.uuid4().hex[:8]}")
    plan_id: str
    total_trains_simulated: int = 0
    trains_affected: int = 0
    trains_delayed: int = 0
    average_delay_minutes: float = 0.0
    max_delay_minutes: float = 0.0
    cumulative_delay_minutes: float = 0.0
    punctuality_before_pct: float = 100.0
    punctuality_after_pct: float = 100.0
    corridors_most_affected: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)