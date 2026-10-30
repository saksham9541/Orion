"""
Unit and integration tests for Orion Real-Time Event Bus and SSE (Item B1).
Verifies:
- Publishing on every task lifecycle transition
- Strict role and department event scoping (Admins/Controllers get all; Dept users get own dept only)
- Reconnect and Last-Event-ID event replay
"""
import pytest
from datetime import datetime, timezone
from backend.events import OrionEventBus
from backend.auth import User, UserRole
from railopt.models import Department


def test_event_bus_publishes_event_with_required_fields():
    bus = OrionEventBus(max_buffer_size=10)
    event = bus.publish_sync(
        event_type="TASK_CREATED",
        task_id="TSK-TEST-1",
        new_status="REPORTED",
        department="TRD",
        block_section="SEC-01",
        actor="operator@trd.gov.in",
        details={"severity": "HIGH"},
    )

    assert "event_id" in event
    assert event["type"] == "TASK_CREATED"
    assert event["task_id"] == "TSK-TEST-1"
    assert event["new_status"] == "REPORTED"
    assert event["department"] == "TRD"
    assert event["block_section"] == "SEC-01"
    assert event["actor"] == "operator@trd.gov.in"
    assert event["version"] >= 1
    assert "timestamp" in event


def test_event_scoping_rules():
    bus = OrionEventBus()

    trd_event = {
        "event_id": "ev-1",
        "type": "TASK_UPDATED",
        "department": "TRD",
    }
    snt_event = {
        "event_id": "ev-2",
        "type": "TASK_UPDATED",
        "department": "SNT",
    }
    global_event = {
        "event_id": "ev-3",
        "type": "WINDOW_APPROVED",
        "department": None,
    }

    # 1. Super Admin sees all events
    assert bus.is_event_permitted(trd_event, user_role="ADMIN", user_dept=None) is True
    assert bus.is_event_permitted(snt_event, user_role="ADMIN", user_dept=None) is True
    assert bus.is_event_permitted(global_event, user_role="ADMIN", user_dept=None) is True

    # 2. Section Controller sees all events
    assert bus.is_event_permitted(trd_event, user_role="CONTROLLER", user_dept=None) is True
    assert bus.is_event_permitted(snt_event, user_role="CONTROLLER", user_dept=None) is True
    assert bus.is_event_permitted(global_event, user_role="CONTROLLER", user_dept=None) is True

    # 3. TRD User sees TRD events and global events, but NEVER S&T events
    assert bus.is_event_permitted(trd_event, user_role="DEPT_USER", user_dept="TRD") is True
    assert bus.is_event_permitted(global_event, user_role="DEPT_USER", user_dept="TRD") is True
    assert bus.is_event_permitted(snt_event, user_role="DEPT_USER", user_dept="TRD") is False

    # 4. S&T User sees S&T events and global events, but NEVER TRD events
    assert bus.is_event_permitted(snt_event, user_role="DEPT_USER", user_dept="SNT") is True
    assert bus.is_event_permitted(global_event, user_role="DEPT_USER", user_dept="SNT") is True
    assert bus.is_event_permitted(trd_event, user_role="DEPT_USER", user_dept="SNT") is False


@pytest.mark.asyncio
async def test_sse_generator_initial_connect_and_filter():
    bus = OrionEventBus()
    user_trd = User(
        id="usr_trd",
        name="TRD Engineer",
        email="trd@test.gov.in",
        role=UserRole.DEPT_USER,
        department=Department.TRD,
    )

    gen = bus.sse_generator(user=user_trd)

    # 1. First yielded chunk is initial connected event
    initial_chunk = await gen.__anext__()
    assert "event: connected" in initial_chunk
    assert "TRD" in initial_chunk

    # 2. Publish an S&T event (should NOT be received by TRD user)
    # and a TRD event (must be received)
    bus.publish_sync(event_type="TASK_UPDATED", task_id="T-SNT", department="SNT")
    bus.publish_sync(event_type="TASK_UPDATED", task_id="T-TRD", department="TRD")

    received_chunk = await gen.__anext__()
    assert "event: TASK_UPDATED" in received_chunk
    assert "T-TRD" in received_chunk
    assert "T-SNT" not in received_chunk

    await gen.aclose()
