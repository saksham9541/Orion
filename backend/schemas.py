"""RailOpt — Pydantic v2 request/response schemas for the API."""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from railopt.models import (
    BlockPlan,
    EarlyWarning,
    MaintenanceTask,
    PlanHorizon,
    SimulationReport,
    UserRole,
    Department,
)

# ── Auth (JWT & Roles) ──────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: str
    password: str

class User(BaseModel):
    id: Optional[str] = None
    email: str
    role: UserRole
    department: Optional[Department] = None
    name: str
    is_active: bool = True

class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: User

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class CreateUserRequest(BaseModel):
    name: str
    email: str
    password: str
    role: UserRole
    department: Optional[Department] = None

class UpdateUserRequest(BaseModel):
    name: Optional[str] = None
    role: Optional[UserRole] = None
    department: Optional[Department] = None
    is_active: Optional[bool] = None

class ResetPasswordRequest(BaseModel):
    new_password: str




class ImportTasksRequest(BaseModel):
    source_system: str  # TMS | SMMS | TDMS
    records: list[dict]  # Raw records from source system


class ImportTasksResponse(BaseModel):
    imported_count: int
    failed_count: int = 0
    errors: list[str] = []
    tasks: list[MaintenanceTask]


class GeneratePlanRequest(BaseModel):
    horizon: PlanHorizon = PlanHorizon.WEEKLY
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    scheduler_config: Optional[dict] = None  # Override scheduler weights


class GeneratePlanResponse(BaseModel):
    plan: BlockPlan
    warnings: list[EarlyWarning] = []
    metrics: dict = {}


class QueryRequest(BaseModel):
    question: str
    plan_id: Optional[str] = None


class QueryResponse(BaseModel):
    answer: str
    sources: list[str] = []


class ReplanRequest(BaseModel):
    plan_id: str
    new_task: MaintenanceTask


class SimulateResponse(BaseModel):
    report: SimulationReport


# ── Plan Approval Workflow (Add 4) ───────────────────────────────────

class PlanApproveRequest(BaseModel):
    approved_by: str = ""
    comments: str = ""


class PlanRejectRequest(BaseModel):
    rejected_by: str = ""
    reason: str = ""


class PlanModifyRequest(BaseModel):
    modified_by: str = ""
    task_overrides: list[dict] = []  # [{task_id, new_priority, ...}]
    reason: str = ""


# ── Timetable Import (Add 1) ────────────────────────────────────────

class TimetableImportRequest(BaseModel):
    records: list[dict]


class TimetableImportResponse(BaseModel):
    imported_count: int
    failed_count: int = 0


# ── Dashboard ────────────────────────────────────────────────────────

class DashboardStats(BaseModel):
    total_tasks: int
    tasks_by_department: dict[str, int]
    tasks_by_severity: dict[str, int]
    total_plans: int
    latest_plan_id: Optional[str]
    sla_compliance_pct: float
    total_merge_savings_hours: float
    active_alerts: int
    corridors_count: int
    rows_failed_to_load: dict[str, int] = {}


# ── Notifications ───────────────────────────────────────────────────

class NotificationResponse(BaseModel):
    id: str
    issue_id: Optional[str] = None
    recipient_user_id: str
    type: str = "ISSUE_RAISED"
    title: str
    message: str
    severity: str
    created_at: datetime
    read_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class UnreadCountResponse(BaseModel):
    unread_count: int


# ── Multi-Agent System ──────────────────────────────────────────────

class AgentNegotiationRequest(BaseModel):
    horizon: PlanHorizon = PlanHorizon.WEEKLY


class AgentNegotiationResponse(BaseModel):
    plan_id: str
    total_tasks_scheduled: int
    total_merge_savings_hours: float
    agreements_count: int
    merged_blocks_count: int
    conflict_resolutions: list[dict]
    early_warnings_count: int
    summary: dict
    plan: BlockPlan


class AgentStatusResponse(BaseModel):
    agents: list[dict]


