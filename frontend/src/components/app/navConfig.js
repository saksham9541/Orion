/**
 * Shared Navigation Configuration for Orion Portal Layouts
 *
 * Enforces role-based navigation tab visibility and consistent route matching
 * across Overview, Department Dashboards, Technician Workbench, and Schedule.
 */

export function getPermittedNavTabs(currentUser, role) {
  const roleId = (currentUser?.role || currentUser?.id || role?.id || role || '').toLowerCase()
  const dept = (currentUser?.department || '').toLowerCase()

  const tabs = [{ label: 'Overview', to: '/dashboard' }]

  // Super Admin & Controller have global oversight across all departments
  if (roleId === 'admin' || roleId === 'controller') {
    tabs.push({ label: 'Super Admin', to: '/admin' })
    tabs.push({ label: 'S&T Dept', to: '/snt' })
    tabs.push({ label: 'Engineering', to: '/engineering' })
    tabs.push({ label: 'TRD', to: '/trd' })
    tabs.push({ label: 'Technician', to: '/technician' })
  } else if (roleId === 'engineering' || dept === 'engineering') {
    tabs.push({ label: 'Engineering', to: '/engineering' })
  } else if (roleId === 'snt' || dept === 'snt') {
    tabs.push({ label: 'S&T Dept', to: '/snt' })
  } else if (roleId === 'trd' || dept === 'trd') {
    tabs.push({ label: 'TRD', to: '/trd' })
  } else if (roleId === 'technician') {
    tabs.push({ label: 'Technician', to: '/technician' })
  }

  tabs.push({ label: 'Schedule', to: '/plan' })
  return tabs
}

export function isTabActive(tabTo, pathname) {
  if (tabTo === '/dashboard') return pathname === '/dashboard' || pathname === '/overview'
  return pathname.startsWith(tabTo)
}
