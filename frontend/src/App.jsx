import { Navigate, Route, Routes } from 'react-router-dom'
import { AppStateProvider } from '@/state/AppState'
import { NotificationProvider } from '@/state/NotificationContext'
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

export default function App() {
  return (
    <AppStateProvider>
      <NotificationProvider>
        <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<Login />} />
      <Route path="/restricted" element={<AccessRestricted />} />
      
      <>
        <Route path="/admin/*" element={<AdminDashboard />} />
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
      </Route>
      
      <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      </NotificationProvider>
    </AppStateProvider>
  )
}
