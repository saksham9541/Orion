import { Navigate, Route, Routes } from 'react-router-dom'
import ErrorBoundary from '@/components/common/ErrorBoundary'
import { AppStateProvider } from '@/state/AppState'
import { NotificationProvider } from '@/state/NotificationContext'
import { LiveSyncProvider } from '@/state/LiveSyncStore'
import Landing from '@/pages/Landing'
import Login from '@/pages/Login'
import AdminDashboard from '@/pages/admin/AdminDashboard'
import EngineeringDashboard from '@/pages/department/EngineeringDashboard'
import SntDashboard from '@/pages/department/SntDashboard'
import TrdDashboard from '@/pages/department/TrdDashboard'
import TechnicianDashboard from '@/pages/department/TechnicianDashboard'
import AccessRestricted from '@/pages/AccessRestricted'
import AppShell from '@/components/app/AppShell'
import Dashboard from '@/pages/Dashboard'
import Simulator from '@/pages/Simulator'
import BlockPlan from '@/pages/BlockPlan'
import Tasks from '@/pages/Tasks'
import Network from '@/pages/Network'
import Sources from '@/pages/Sources'
import Assistant from '@/pages/Assistant'

export default function App() {
  return (
    <ErrorBoundary>
      <AppStateProvider>
        <NotificationProvider>
          <LiveSyncProvider>
            <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<Login />} />
      <Route path="/restricted" element={<AccessRestricted />} />
      
      <>
        <Route path="/admin/*" element={<AdminDashboard />} />
        <Route path="/controller/*" element={<Navigate to="/dashboard" replace />} />
        <Route path="/engineering/*" element={<EngineeringDashboard />} />
        <Route path="/snt/*" element={<SntDashboard />} />
        <Route path="/trd/*" element={<TrdDashboard />} />
        <Route path="/technician/*" element={<TechnicianDashboard />} />
      </>

      <Route element={<AppShell />}>
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/overview" element={<Dashboard />} />
        <Route path="/simulate" element={<Simulator />} />
        <Route path="/plan" element={<BlockPlan />} />
        <Route path="/tasks" element={<Tasks />} />
        <Route path="/network" element={<Network />} />
        <Route path="/sources" element={<Sources />} />
        <Route path="/assistant" element={<Assistant />} />
        <Route path="/briefing" element={<Assistant />} />
        <Route path="/simulator" element={<Simulator />} />
      </Route>

      {/* Legacy /app/* path aliases for demo steps & dashboard links */}
      <Route path="/app/plan" element={<Navigate to="/plan" replace />} />
      <Route path="/app/tasks" element={<Navigate to="/tasks" replace />} />
      <Route path="/app/network" element={<Navigate to="/network" replace />} />
      <Route path="/app/dashboard" element={<Navigate to="/dashboard" replace />} />
      <Route path="/app/simulate" element={<Navigate to="/simulate" replace />} />
      <Route path="/app/simulator" element={<Navigate to="/simulate" replace />} />
      <Route path="/app/*" element={<Navigate to="/dashboard" replace />} />
      
      <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </LiveSyncProvider>
      </NotificationProvider>
      </AppStateProvider>
    </ErrorBoundary>
  )
}
