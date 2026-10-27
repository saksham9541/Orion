# Orion Role-Based Access Control (RBAC) Specification

Orion enforces strict Role-Based Access Control on every API endpoint to protect railway operations data and enforce separation of duties.

---

## 1. User Roles & Department Scope

| Role | Department Required? | Description & Authority |
|---|---|---|
| `ADMIN` | No (null) | System administrator. Manages user accounts, resets passwords, triggers demo setup, and manages global system configurations. |
| `CONTROLLER` | No (null) | Railway Section/Division Traffic Controller. Authorizes, generates, approves, and modifies maintenance block plans. Full cross-department operational authority. |
| `DEPT_USER` | **Yes** (`ENGINEERING`, `SNT`, or `TRD`) | Department Maintenance Engineer. Enters and updates defect reports and maintenance tasks **only for their assigned department**. |
| `VIEWER` | No (null) | Read-only observer (management, audit, external inspectors). Can view plans, tasks, statistics, and live train operations. |

---

## 2. Department Mapping

- **`ENGINEERING`**: Track, rails, sleepers, ballast, formations, bridges, turnouts, weld joints.
- **`SNT`** (Signals & Telecommunication): Signals, relays, point machines, axle counters, telecom cables, track circuits, electronic interlocking.
- **`TRD`** (Traction Distribution): Overhead equipment (OHE), power supply, insulators, masts, switching posts.

---

## 3. Endpoint Permissions Matrix

| Endpoint | Method | Required Role | Notes / Constraints |
|---|---|---|---|
| `/api/auth/login` | POST | Public | Authenticates credentials; returns JWT access & refresh tokens. |
| `/api/auth/refresh` | POST | Public | Refreshes expired access token using valid refresh token. |
| `/api/auth/me` | GET | `VIEWER`+ | Returns current authenticated user profile. |
| `/api/health` | GET | Public | Health check (`status`, `models_loaded`, `database_ok`). |
| `/api/tasks` | GET | `VIEWER`+ | Lists maintenance tasks. For `DEPT_USER`, filters to user's department by default. |
| `/api/tasks` | POST | `DEPT_USER`+ | Creates a maintenance task. `DEPT_USER` can only create for their assigned department. |
| `/api/tasks/{task_id}` | GET | `VIEWER`+ | Retrieves task details. `DEPT_USER` restricted to tasks within their department. |
| `/api/tasks/{task_id}/status` | PATCH | `DEPT_USER`+ | Updates task status. `DEPT_USER` restricted to their department. |
| `/api/tasks/complaints` | POST | `DEPT_USER`+ | Ingests inspector free-text complaint into structured task for user's department. |
| `/api/tasks/import` | POST | `DEPT_USER`+ | Imports bulk tasks for user's department. |
| `/api/plans` | GET | `VIEWER`+ | Reads block plans and schedules. |
| `/api/plans/generate` | POST | `CONTROLLER`+ | Generates a new multi-department optimized block plan. |
| `/api/plans/{plan_id}/approve`| POST | `CONTROLLER`+ | Approves a proposed block plan for execution. |
| `/api/plans/{plan_id}/reject` | POST | `CONTROLLER`+ | Rejects a proposed block plan. |
| `/api/plans/{plan_id}/modify` | POST | `CONTROLLER`+ | Modifies assigned block windows. |
| `/api/plans/replan` | POST | `CONTROLLER`+ | Performs emergency re-planning with new constraints. |
| `/api/dashboard/stats` | GET | `VIEWER`+ | Aggregates summary statistics. |
| `/api/network/corridors` | GET | `VIEWER`+ | Network topology corridors. |
| `/api/network/sections` | GET | `VIEWER`+ | Network topology sections. |
| `/api/network/trains/live` | GET | `VIEWER`+ | Real-time passenger train running status and delays (RailRadar). |
| `/api/network/corridors/{id}/heatmap` | GET | `VIEWER`+ | Heatmap overlay of defect density and train delay hotspots. |
| `/api/users` | GET | `ADMIN` | Lists all user accounts. |
| `/api/users` | POST | `ADMIN` | Creates new user account. |
| `/api/users/{user_id}` | PATCH | `ADMIN` | Updates user details or toggles `is_active`. |
| `/api/users/{user_id}/reset-password` | POST | `ADMIN` | Resets a user's password. |
| `/api/demo/setup` | POST | `ADMIN` | Resets and regenerates synthetic dataset (preserves user data). |
| `/api/demo/action` | POST | `VIEWER`+ | Simulates field actions on demo items. |

---

## 4. Security & Auditing Rules

1. **Department Boundary Enforcement**: An `ENGINEERING` user attempting to modify or create an `SNT` task receives `HTTP 403 Forbidden`.
2. **Controller Approval Separation**: Department users cannot self-approve block plans; only traffic controllers and administrators can approve or reject plans.
3. **Audit Immutability**: All plan modifications and approvals record the actor ID and timestamp.
