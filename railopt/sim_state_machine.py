"""
RailOpt simulator — state transition logic.
Mirrors SIH26027_State_Machine_Spec.md Section 2 (Block/Junction/Platform lifecycle)
and Section 3 (Train lifecycle), including the guard conditions table.
"""
from __future__ import annotations
from typing import Optional
from .sim_entities import (
    Resource, Train, Disruption, ResourceState, TrainState, ResourceType,
    CLEARANCE_BUFFER, block_traversal_time,
)


class TransitionError(Exception):
    """Raised when a guard condition fails — caller should not proceed."""


def reserve(resource: Resource, train_id: str, start: float, end: float) -> None:
    if resource.state == ResourceState.BLOCKED:
        raise TransitionError(f"{resource.resource_id} is BLOCKED, cannot reserve")
    if resource.state != ResourceState.AVAILABLE:
        raise TransitionError(
            f"{resource.resource_id} is {resource.state}, cannot reserve (must be AVAILABLE)"
        )
    resource.state = ResourceState.RESERVED
    resource.reserved_by_train_id = train_id
    resource.reservation_window = (start, end)


def occupy(resource: Resource, train_id: str, prev_resource: Optional[Resource]) -> None:
    if resource.state != ResourceState.RESERVED or resource.reserved_by_train_id != train_id:
        raise TransitionError(
            f"{resource.resource_id} not RESERVED for {train_id} (state={resource.state})"
        )
    if prev_resource is not None:
        if prev_resource.state not in (ResourceState.CLEARING, ResourceState.AVAILABLE):
            raise TransitionError(
                f"train {train_id} cannot occupy {resource.resource_id}: "
                f"previous resource {prev_resource.resource_id} is still {prev_resource.state}"
            )
    resource.state = ResourceState.OCCUPIED
    resource.occupying_train_id = train_id
    resource.reserved_by_train_id = None


def start_clearing(resource: Resource, sim_time: float) -> None:
    if resource.state != ResourceState.OCCUPIED:
        raise TransitionError(f"{resource.resource_id} not OCCUPIED, cannot start clearing")
    resource.state = ResourceState.CLEARING
    resource.clearing_since = sim_time
    resource.occupying_train_id = None


def try_clear(resource: Resource, sim_time: float) -> bool:
    if resource.state != ResourceState.CLEARING:
        return False
    buffer = CLEARANCE_BUFFER.get(resource.resource_type, 60)
    if resource.clearing_since is not None and sim_time - resource.clearing_since >= buffer:
        resource.state = ResourceState.AVAILABLE
        resource.clearing_since = None
        return True
    return False


def force_block(resource: Resource, disruption: Disruption) -> Optional[str]:
    stranded_train_id = None
    if resource.state == ResourceState.OCCUPIED:
        stranded_train_id = resource.occupying_train_id
    resource.state = ResourceState.BLOCKED
    resource.active_disruption_id = disruption.disruption_id
    resource.forced_blocked_until = disruption.end_time
    return stranded_train_id


def clear_disruption(resource: Resource) -> None:
    if resource.state != ResourceState.BLOCKED:
        return
    resource.state = ResourceState.AVAILABLE
    resource.active_disruption_id = None
    resource.forced_blocked_until = None


def junction_group_key(entry_block_id: str, exit_block_id: str) -> str:
    return f"{entry_block_id}->{exit_block_id}"


def routes_conflict(resource: Resource, route_a: tuple, route_b: tuple) -> bool:
    if route_a == route_b:
        return True
    conflicting_pairs = set(map(tuple, resource.routes_through))
    return (route_a, route_b) in conflicting_pairs or (route_b, route_a) in conflicting_pairs


def train_depart(train: Train) -> None:
    if train.state != TrainState.SCHEDULED:
        raise TransitionError(f"{train.train_id} not SCHEDULED")
    train.state = TrainState.APPROACHING


def train_enter_resource(train: Train, resource_id: str, sim_time: float) -> None:
    train.state = TrainState.OCCUPYING
    train.current_resource_id = resource_id
    entry = train.scheduled_times.get(resource_id, (sim_time, None))
    train.actual_times[resource_id] = (sim_time, train.actual_times.get(resource_id, (None, None))[1])
    train.compute_delay(sim_time)


def train_start_dwell(train: Train) -> None:
    train.state = TrainState.DWELLING


def train_advance(train: Train) -> None:
    train.position_in_route += 1
    if train.position_in_route >= len(train.route):
        train.state = TrainState.COMPLETED
        train.current_resource_id = None
    else:
        train.state = TrainState.APPROACHING
        train.current_resource_id = None


def train_hold(train: Train) -> None:
    if train.state not in (TrainState.APPROACHING, TrainState.OCCUPYING):
        raise TransitionError(f"{train.train_id} cannot be HELD from state {train.state}")
    train.state = TrainState.HELD


def train_strand(train: Train) -> None:
    train.state = TrainState.STRANDED
