"""
Orion — Real-Time Notification & WebSocket Connection Manager.
Handles:
- Active WebSocket connection tracking by user_id and department
- Real-time notification dispatching to online users
- Persistence of notifications in the database for offline users
- Recipient resolution (Super Admin + designated department users)
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any

from fastapi import WebSocket
from sqlalchemy.orm import Session

from backend.database import NotificationRecord, UserRecord, utc_now

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages active WebSocket connections grouped by user_id and department."""

    def __init__(self):
        # user_id -> list of active WebSocket connections
        self.active_connections: Dict[str, List[WebSocket]] = {}
        # user_id -> user metadata (role, department, email)
        self.user_meta: Dict[str, Dict[str, Any]] = {}

    async def connect(
        self,
        websocket: WebSocket,
        user_id: str,
        role: str,
        department: Optional[str] = None,
        email: Optional[str] = None,
        subprotocol: Optional[str] = None,
    ):
        await websocket.accept(subprotocol=subprotocol)
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)
        self.user_meta[user_id] = {
            "role": role.lower() if role else "",
            "department": department.upper() if department else None,
            "email": email or "",
        }
        logger.info(
            "WebSocket connected: user_id=%s, role=%s, dept=%s (active sockets: %d)",
            user_id,
            role,
            department,
            len(self.active_connections[user_id]),
        )

    def disconnect(self, websocket: WebSocket, user_id: str):
        if user_id in self.active_connections:
            if websocket in self.active_connections[user_id]:
                self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
                self.user_meta.pop(user_id, None)
        logger.info("WebSocket disconnected: user_id=%s", user_id)

    async def send_personal_message(self, message: dict, user_id: str):
        sockets = self.active_connections.get(user_id, [])
        dead_sockets = []
        for socket in sockets:
            try:
                await socket.send_json(message)
            except Exception as e:
                logger.warning("Failed to send message to socket for user %s: %s", user_id, e)
                dead_sockets.append(socket)
        for dead in dead_sockets:
            if dead in sockets:
                sockets.remove(dead)

    async def broadcast_to_users(self, message: dict, user_ids: List[str]):
        for uid in user_ids:
            if uid in self.active_connections:
                await self.send_personal_message(message, uid)

    async def broadcast_to_all(self, message: dict):
        """Broadcasts a payload to every active WebSocket connection."""
        for uid in list(self.active_connections.keys()):
            await self.send_personal_message(message, uid)

    def is_user_online(self, user_id: str) -> bool:
        return bool(self.active_connections.get(user_id))


manager = ConnectionManager()


def resolve_issue_recipients(
    session: Session,
    department_designated: Optional[str],
    creator_id: Optional[str] = None,
    creator_email: Optional[str] = None,
) -> List[UserRecord]:
    """
    Recipients:
    (a) All users with role ADMIN or SUPER_ADMIN
    (b) All users where user.department == department_designated
    Excluding the creator (by user_id or email).
    """
    users = session.query(UserRecord).filter(UserRecord.is_active == True).all()
    recipients = []
    dept_norm = (department_designated or "").strip().upper()

    for u in users:
        u_role = (u.role or "").strip().lower()
        u_dept = (u.department or "").strip().upper()

        is_super_admin = u_role in ("admin", "super_admin")
        is_designated_dept = bool(dept_norm and (u_dept == dept_norm))

        # Do not send defect notification back to pure field technicians
        if u_role == "technician" and ((creator_id and str(u.id) == str(creator_id)) or (creator_email and u.email and creator_email.strip().lower() == u.email.strip().lower())):
            continue

        if is_super_admin or is_designated_dept:
            recipients.append(u)

    return recipients


async def dispatch_issue_alert(
    session: Session,
    issue_id: str,
    title: str,
    message: str,
    severity: str,
    department_designated: Optional[str],
    creator_id: Optional[str] = None,
    creator_email: Optional[str] = None,
) -> List[NotificationRecord]:
    """
    Persists a NotificationRecord for every eligible recipient and
    immediately broadcasts the alert payload over WebSocket to online recipients.
    """
    recipients = resolve_issue_recipients(
        session=session,
        department_designated=department_designated,
        creator_id=creator_id,
        creator_email=creator_email,
    )

    created_notifs: List[NotificationRecord] = []
    now = utc_now()

    for r in recipients:
        notif = NotificationRecord(
            id=str(uuid.uuid4()),
            issue_id=issue_id,
            recipient_user_id=r.id,
            type="ISSUE_RAISED",
            title=title,
            message=message,
            severity=severity.upper(),
            created_at=now,
            read_at=None,
            acknowledged_at=None,
        )
        session.add(notif)
        created_notifs.append(notif)

    session.commit()

    # Broadcast over WebSocket to any recipients currently connected
    for notif in created_notifs:
        payload = {
            "type": notif.type,
            "notification": {
                "id": notif.id,
                "issue_id": notif.issue_id,
                "recipient_user_id": notif.recipient_user_id,
                "type": notif.type,
                "title": notif.title,
                "message": notif.message,
                "severity": notif.severity,
                "department_designated": department_designated,
                "created_by": creator_email,
                "created_at": notif.created_at.isoformat() if notif.created_at else now.isoformat(),
                "read_at": None,
                "acknowledged_at": None,
            }
        }
        await manager.send_personal_message(payload, notif.recipient_user_id)

    return created_notifs
