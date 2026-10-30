# Orion Task Status Buckets & Lifecycle Stages Specification

This document defines the single source of truth for task classification, dashboard metric buckets, and lifecycle pipeline stages across the Orion platform.

---

## 1. Core Principles & Invariants

To eliminate count discrepancies across dashboard cards, journey boards, and department views, every maintenance task status maps to **exactly one metric bucket** and **exactly one pipeline stage**.

### Enforced Invariants
1. **Bucket Partition Invariant**:  
   $$\text{Total Tasks} = \text{Pending} + \text{Active / Scheduled} + \text{Resolved}$$
2. **Pipeline Stage Invariant**:  
   $$\text{Total Tasks} = \text{Intake} + \text{Planning} + \text{Execution} + \text{Resolution}$$
3. **Department Additivity**:  
   $$\text{Total Tasks} = \sum_{\text{dept} \in \{\text{ENG}, \text{SNT}, \text{TRD}\}} \text{Department Total}$$
4. **Acknowledgement Exclusion**:  
   Tasks with status `AWAITING_ACKNOWLEDGEMENT` or `awaiting_acknowledgement = true` are excluded from all operational counts until acknowledged.

---

## 2. Status-to-Bucket & Status-to-Stage Mapping Table

Every one of the 22 `TaskStatus` values is strictly categorized below:

| `TaskStatus` | Metric Bucket | Pipeline Stage | Operational Description |
|---|---|---|---|
| `DRAFT` | `pending` | `intake` | Created by user/dept, not yet submitted. |
| `SUBMITTED` | `pending` | `intake` | Submitted for verification and intake review. |
| `REPORTED` | `pending` | `intake` | Reported from field inspection or user defect complaint. |
| `UNVERIFIED` | `pending` | `intake` | Defect logged, awaiting technician site verification. |
| `DEFERRED` | `pending` | `intake` | Work postponed to next planning cycle. |
| `ESCALATED` | `pending` | `intake` | Deferral limit exceeded; escalated by SLA engine. |
| `PENDING` | `pending` | `planning` | Defect verified; awaiting corridor slot scheduling. |
| `SCORED` | `pending` | `planning` | Priority and duration attributes verified. |
| `WINDOWS_PROPOSED` | `active_scheduled` | `planning` | Candidate timetable windows generated. |
| `WINDOW_SELECTED` | `active_scheduled` | `planning` | Preferred maintenance window selected by department. |
| `APPROVED` | `active_scheduled` | `execution` | Block window approved by section controller. |
| `READY` | `active_scheduled` | `execution` | Pre-start safety checklist verified; ready for crew. |
| `SCHEDULED` | `active_scheduled` | `execution` | Assigned to confirmed weekly block schedule. |
| `IN_PROGRESS` | `active_scheduled` | `execution` | Track possession active; field work underway. |
| `SUSPENDED` | `active_scheduled` | `execution` | Work temporarily paused due to site or weather event. |
| `OVERRUN` | `active_scheduled` | `execution` | Work exceeding planned window boundary; alert active. |
| `COMPLETED` | `resolved` | `resolution` | Work finished, track inspected, speed restriction clear. |
| `ABORTED` | `resolved` | `resolution` | Possession cancelled mid-execution with abort code. |
| `CANCELLED` | `resolved` | `resolution` | Request cancelled before execution. |
| `REJECTED` | `resolved` | `resolution` | Defect rejected as invalid or duplicate by technician. |
| `AWAITING_ACK` | `pending` | `intake` | Reported defect awaiting second-pair-of-eyes acknowledgement (excluded from operational counts). |
| `DECLINED` | `resolved` | `resolution` | Report declined with reason during acknowledgement review. |

---

## 3. Backend Source of Truth Endpoint

### `GET /api/dashboard/counts`
- **Query Parameters**:
  - `department` *(optional)*: Filter to a specific department (`ENGINEERING`, `SNT`, `TRD`). If omitted, returns global totals and per-department breakdowns.
- **Response Schema**:
```json
{
  "total": 27,
  "pending": 26,
  "active_scheduled": 1,
  "resolved": 0,
  "buckets": {
    "pending": 26,
    "active_scheduled": 1,
    "resolved": 0
  },
  "pipeline_stages": {
    "intake": 0,
    "planning": 26,
    "execution": 1,
    "resolution": 0
  },
  "by_department": {
    "ENGINEERING": { "total": 35, "pending": 30, "active_scheduled": 4, "resolved": 1, ... },
    "SNT": { "total": 29, "pending": 24, "active_scheduled": 3, "resolved": 2, ... },
    "TRD": { "total": 27, "pending": 26, "active_scheduled": 1, "resolved": 0, ... }
  }
}
```

---

## 4. Frontend Integration

All dashboards consume counts directly from `/api/dashboard/counts`:
- **Overview Dashboard (`/dashboard`)**: Displays network-wide total and bucket counts.
- **Department Dashboards (`/engineering`, `/snt`, `/trd`)**: Display department-scoped total, pending, active, and resolved cards, and matching column headers on the Journey Board.
- **Technician Workbench (`/technician`)**: Displays operational order totals matching active execution counts.
- **Schedule (`/plan`)**: Displays scheduled block and task counts consistent with the planning and execution buckets.
