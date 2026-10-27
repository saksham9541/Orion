# Goal Description

Implement a 3-tier Role-Based Access Control (RBAC) system with a secure Login page. The system will restrict access and views based on three specific roles: Super Admin, Department Admin, and Maintenance Technician.

## User Review Required

> [!IMPORTANT]
> **Authentication Method**: Since this is for a hackathon, I will implement a **mock, stateless JWT token authentication system** with hardcoded demo users for the 3 roles rather than standing up a full PostgreSQL/identity server. This provides the exact UX you need for the demo without adding huge backend overhead. Is this acceptable?
>
> **Demo Users to be created:**
> - `admin@railopt.gov.in` (Role: Super Admin)
> - `trd@railopt.gov.in`, `snt@railopt.gov.in`, `eng@railopt.gov.in` (Role: Department Admin)
> - `tech@railopt.gov.in` (Role: Technician)
> (Password for all will be `password123`)

## Proposed Changes

### Backend

#### [MODIFY] backend/schemas.py
- Add `LoginRequest` and `LoginResponse` models.
- Add `User` schema containing `role` and `department`.

#### [MODIFY] railopt/models.py
- Add `UserRole` Enum (`SUPER_ADMIN`, `DEPT_ADMIN`, `TECHNICIAN`).

#### [MODIFY] backend/main.py
- Add `POST /api/auth/login` endpoint that validates credentials against the mock user list and returns a simple signed token.
- Add `get_current_user` FastAPI dependency to decode the token and verify permissions.
- **Protect Endpoints**: 
  - Restrict `/api/dashboard/stats`, `/api/plans/generate`, and `/api/demo/setup` to exclude Technicians.
  - Automatically filter dashboard stats by `department` if the logged-in user is a `DEPT_ADMIN`.
- Add `PUT /api/tasks/{task_id}/status` endpoint so technicians can update tasks.

### Frontend

#### [NEW] frontend/src/context/AuthContext.jsx
- Create a React Context to store the logged-in user state (`user`, `role`, `token`) and provide `login()`/`logout()` functions.

#### [NEW] frontend/src/pages/Login.jsx
- Create a polished, modern login page with email and password fields.

#### [NEW] frontend/src/components/ProtectedRoute.jsx
- A wrapper component that redirects unauthorized users back to `/login` or shows an "Access Denied" message if they try to access a page above their clearance.

#### [MODIFY] frontend/src/App.jsx
- Wrap the app in `<AuthProvider>`.
- Restructure routing so `/login` doesn't show the sidebar.
- Protect `/` (Dashboard) and `/plans` for Admins only.
- Add a new restricted home for Technicians (e.g. `/technician` or redirecting them straight to a simplified `/tasks` view).

#### [MODIFY] frontend/src/api.js
- Add an Axios interceptor to automatically attach `Authorization: Bearer <token>` to all outgoing API requests.

## Verification Plan

### Manual Verification
1. I will start the frontend and backend.
2. You will be able to navigate to `http://localhost:5173/` and be forced to log in.
3. Logging in as `tech@railopt.gov.in` will restrict you from seeing the main optimization dashboard, but allow you to view/update tasks.
4. Logging in as `trd@railopt.gov.in` will show you the dashboard, but filtered *only* for Traction department metrics.
5. Logging in as `admin@railopt.gov.in` will grant full access.
