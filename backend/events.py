"""
Orion Real-Time Event Bus and Server-Sent Events (SSE) Broadcaster (Item B1).

Guarantees:
- Publishes an event after every task create/update/transition in the commit path.
- Events carry: event_id, type, task_id, new_status, department, block_section, version, timestamp, actor, details.
- Strict role- and department-scoping:
  - ADMIN and CONTROLLER receive all events.
  - DEPT_USER and TECHNICIAN receive events for their designated department only (plus global events).
- In-memory event replay buffer for reconnecting clients using Last-Event-ID.
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections import deque
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional, Set

from backend.auth import User, UserRole

logger = logging.getLogger(__name__)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class OrionEventBus:
    """In-memory event broadcaster with role/department filtering and reconnect replay."""

    def __init__(self, max_buffer_size: int = 100):
        self._max_buffer_size = max_buffer_size
        self._history: deque[dict[str, Any]] = deque(maxlen=max_buffer_size)
        self._subscribers: Set[asyncio.Queue] = set()
        self._subscriber_filters: Dict[asyncio.Queue, Dict[str, Any]] = {}
        self._version_counter: int = 0
        self._lock = asyncio.Lock()

    def _next_version(self) -> int:
        self._version_counter += 1
        return self._version_counter

    def is_event_permitted(self, event: dict[str, Any], user_role: str, user_dept: Optional[str]) -> bool:
        """Enforces role- and department-scoping rules."""
        role_norm = (user_role or "").strip().lower()
        dept_norm = (user_dept or "").strip().upper() if user_dept else None

        # Super Admin and Controller have complete network visibility
        if role_norm in ("admin", "super_admin", "controller"):
            return True

        # Department users & technicians only receive events for their department
        event_dept = event.get("department")
        if event_dept is not None:
            event_dept_norm = str(event_dept).strip().upper()
            return bool(dept_norm and dept_norm == event_dept_norm)

        # Global events with no specific department attached are sent to all
        return True

    def publish_sync(
        self,
        event_type: str,
        task_id: Optional[str] = None,
        new_status: Optional[str] = None,
        department: Optional[str] = None,
        block_section: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
        actor: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Synchronously builds and queues an event. Safe to call from synchronous endpoint handlers.
        """
        dept_str = None
        if department is not None:
            dept_str = getattr(department, "value", str(department)).upper()

        event = {
            "event_id": str(uuid.uuid4()),
            "type": event_type,
            "task_id": task_id,
            "new_status": getattr(new_status, "value", str(new_status)) if new_status else None,
            "department": dept_str,
            "block_section": block_section,
            "timestamp": utc_now_iso(),
            "version": self._next_version(),
            "actor": actor,
            "details": details or {},
        }

        self._history.append(event)
        logger.info(
            "EventBus published: type=%s, task=%s, status=%s, dept=%s, ver=%d",
            event["type"],
            event["task_id"],
            event["new_status"],
            event["department"],
            event["version"],
        )

        # Dispatch to active queues
        dead_queues = []
        for q in list(self._subscribers):
            filt = self._subscriber_filters.get(q, {})
            u_role = filt.get("role", "")
            u_dept = filt.get("department")
            if self.is_event_permitted(event, u_role, u_dept):
                try:
                    q.put_nowait(event)
                except asyncio.QueueFull:
                    logger.warning("Subscriber queue full; dropping oldest event for subscriber")
                except Exception as e:
                    logger.debug("Error putting to subscriber queue: %s", e)
                    dead_queues.append(q)

        for dq in dead_queues:
            self._subscribers.discard(dq)
            self._subscriber_filters.pop(dq, None)

        return event

    async def sse_generator(
        self,
        user: User,
        last_event_id: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Streams Server-Sent Events to a connected client.
        Supports replay from last_event_id and periodic keepalive.
        """
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        u_role = getattr(user.role, "value", str(user.role)).lower()
        u_dept = getattr(user.department, "value", str(user.department)).upper() if user.department else None

        self._subscribers.add(queue)
        self._subscriber_filters[queue] = {"role": u_role, "department": u_dept}

        try:
            # 1. Send initial connection confirmation
            init_payload = {
                "type": "CONNECTED",
                "connected_at": utc_now_iso(),
                "user_role": u_role,
                "department": u_dept,
            }
            yield f"event: connected\ndata: {json.dumps(init_payload)}\n\n"

            # 2. Replay buffered events if last_event_id is provided
            if last_event_id:
                replaying = False
                for past_event in list(self._history):
                    if replaying:
                        if self.is_event_permitted(past_event, u_role, u_dept):
                            data_str = json.dumps(past_event)
                            yield f"id: {past_event['event_id']}\nevent: {past_event['type']}\ndata: {data_str}\n\n"
                    elif past_event["event_id"] == last_event_id:
                        replaying = True

            # 3. Main event stream loop with keepalive ping every 15s
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    data_str = json.dumps(event)
                    yield f"id: {event['event_id']}\nevent: {event['type']}\ndata: {data_str}\n\n"
                except asyncio.TimeoutError:
                    # Keepalive comment to prevent intermediate proxies / browser timeouts
                    yield f": keepalive {utc_now_iso()}\n\n"

        except asyncio.CancelledError:
            logger.info("SSE client disconnected: user=%s", user.email)
        finally:
            self._subscribers.discard(queue)
            self._subscriber_filters.pop(queue, None)


# Global singleton event bus
event_bus = OrionEventBus()
