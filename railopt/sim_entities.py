"""
RailOpt simulator — core entities and enums.
Mirrors SIH26027_State_Machine_Spec.md Sections 1-3.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class TrainType(str, Enum):
    PASSENGER_PRIORITY = "PASSENGER_PRIORITY"
    EXPRESS = "EXPRESS"
    FREIGHT = "FREIGHT"
    LOCAL = "LOCAL"


class TrainState(str, Enum):
    SCHEDULED = "SCHEDULED"
    APPROACHING = "APPROACHING"
    OCCUPYING = "OCCUPYING"
    DWELLING = "DWELLING"
    HELD = "HELD"
    STRANDED = "STRANDED"
    COMPLETED = "COMPLETED"


class ResourceState(str, Enum):
    AVAILABLE = "AVAILABLE"
    RESERVED = "RESERVED"
    OCCUPIED = "OCCUPIED"
    CLEARING = "CLEARING"
    BLOCKED = "BLOCKED"


class ResourceType(str, Enum):
    BLOCK = "BLOCK"
    JUNCTION = "JUNCTION"
    PLATFORM = "PLATFORM"


class ReservationStatus(str, Enum):
    PROPOSED = "PROPOSED"
    CONFIRMED = "CONFIRMED"
    ACTIVE = "ACTIVE"
    RELEASED = "RELEASED"
    CANCELLED = "CANCELLED"


class DisruptionType(str, Enum):
    SIGNAL_FAILURE = "SIGNAL_FAILURE"
    BLOCK_CLOSURE = "BLOCK_CLOSURE"
    TRAIN_BREAKDOWN = "TRAIN_BREAKDOWN"
    MAINTENANCE_EXTENSION = "MAINTENANCE_EXTENSION"


CLEARANCE_BUFFER = {
    ResourceType.BLOCK: 60,
    ResourceType.JUNCTION: 90,
    ResourceType.PLATFORM: 30,
}
SAFETY_MARGIN = 30

DEFAULT_TRAIN_LENGTH_M = {
    TrainType.PASSENGER_PRIORITY: 400,
    TrainType.EXPRESS: 400,
    TrainType.FREIGHT: 700,
    TrainType.LOCAL: 200,
}

DWELL_TIME_S = {
    TrainType.EXPRESS: 120,
    TrainType.PASSENGER_PRIORITY: 150,
    TrainType.LOCAL: 60,
    TrainType.FREIGHT: 300,
}


def headway_minimum(resource_type: ResourceType) -> int:
    return CLEARANCE_BUFFER[resource_type] + SAFETY_MARGIN


def block_traversal_time(length_m: float, block_max_kmh: float, train_max_kmh: float) -> float:
    speed_kmh = min(block_max_kmh, train_max_kmh)
    speed_ms = speed_kmh * 1000 / 3600
    return length_m / speed_ms


@dataclass
class Resource:
    resource_id: str
    resource_type: ResourceType
    state: ResourceState = ResourceState.AVAILABLE
    occupying_train_id: Optional[str] = None
    reserved_by_train_id: Optional[str] = None
    reservation_window: Optional[tuple] = None
    clearing_since: Optional[float] = None

    length_m: float = 0
    max_speed_kmh: float = 0

    junction_group_state: dict = field(default_factory=dict)
    routes_through: list = field(default_factory=list)

    station_id: Optional[str] = None
    capacity: int = 1
    dwell_required: bool = False

    forced_blocked_until: Optional[float] = None
    active_disruption_id: Optional[str] = None


@dataclass
class Reservation:
    reservation_id: str
    train_id: str
    resource_id: str
    resource_type: ResourceType
    start_time: float
    end_time: float
    status: ReservationStatus = ReservationStatus.PROPOSED


@dataclass
class Disruption:
    disruption_id: str
    type: DisruptionType
    affected_resource_id: str
    start_time: float
    end_time: Optional[float]


@dataclass
class Train:
    train_id: str
    train_type: TrainType
    route: list
    current_resource_id: Optional[str] = None
    position_in_route: int = 0
    state: TrainState = TrainState.SCHEDULED
    scheduled_times: dict = field(default_factory=dict)
    actual_times: dict = field(default_factory=dict)
    delay: float = 0.0
    priority_score: float = 0.0
    locked_assignments: dict = field(default_factory=dict)
    length_m: float = 0.0
    max_speed_kmh: float = 120.0

    def __post_init__(self):
        if not self.length_m:
            self.length_m = DEFAULT_TRAIN_LENGTH_M.get(self.train_type, 400)

    def next_resource_id(self) -> Optional[str]:
        if self.position_in_route + 1 < len(self.route):
            return self.route[self.position_in_route + 1]
        return None

    def compute_delay(self, sim_time: float) -> float:
        if self.current_resource_id and self.current_resource_id in self.scheduled_times:
            sched_entry, _ = self.scheduled_times[self.current_resource_id]
            self.delay = max(0.0, sim_time - sched_entry)
        return self.delay
