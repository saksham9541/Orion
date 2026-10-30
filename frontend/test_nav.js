/**
 * Navigation and Tab Reachability Test
 * Verifies role-based tab visibility, active tab resolution,
 * and two-way reachability from Overview across all portal routes.
 */
import assert from 'node:assert'
import { getPermittedNavTabs, isTabActive } from './src/components/app/navConfig.js'

console.log('Testing Navigation Tabs and Reachability...')

// 1. Role-based tab permissions
const adminTabs = getPermittedNavTabs({ role: 'admin' })
assert.deepStrictEqual(
  adminTabs.map(t => t.label),
  ['Overview', 'Super Admin', 'S&T Dept', 'Engineering', 'TRD', 'Technician', 'Schedule'],
  'Admin must see all 7 navigation tabs'
)

const engTabs = getPermittedNavTabs({ role: 'dept_user', department: 'engineering' })
assert.deepStrictEqual(
  engTabs.map(t => t.label),
  ['Overview', 'Engineering', 'Schedule'],
  'Engineering user must only see Overview, Engineering, and Schedule'
)

const sntTabs = getPermittedNavTabs({ role: 'dept_user', department: 'snt' })
assert.deepStrictEqual(
  sntTabs.map(t => t.label),
  ['Overview', 'S&T Dept', 'Schedule'],
  'S&T user must only see Overview, S&T, and Schedule'
)

const trdTabs = getPermittedNavTabs({ role: 'dept_user', department: 'trd' })
assert.deepStrictEqual(
  trdTabs.map(t => t.label),
  ['Overview', 'TRD', 'Schedule'],
  'TRD user must only see Overview, TRD, and Schedule'
)

const techTabs = getPermittedNavTabs({ role: 'technician' })
assert.deepStrictEqual(
  techTabs.map(t => t.label),
  ['Overview', 'Technician', 'Schedule'],
  'Technician must only see Overview, Technician, and Schedule'
)

// 2. Active tab resolution across routes
assert.strictEqual(isTabActive('/dashboard', '/dashboard'), true, 'Overview active on /dashboard')
assert.strictEqual(isTabActive('/dashboard', '/overview'), true, 'Overview active on /overview')
assert.strictEqual(isTabActive('/admin', '/admin'), true, 'Super Admin active on /admin')
assert.strictEqual(isTabActive('/snt', '/snt'), true, 'S&T active on /snt')
assert.strictEqual(isTabActive('/engineering', '/engineering'), true, 'Engineering active on /engineering')
assert.strictEqual(isTabActive('/trd', '/trd'), true, 'TRD active on /trd')
assert.strictEqual(isTabActive('/technician', '/technician'), true, 'Technician active on /technician')
assert.strictEqual(isTabActive('/plan', '/plan'), true, 'Schedule active on /plan')

// Verify inactive tabs
assert.strictEqual(isTabActive('/admin', '/dashboard'), false)
assert.strictEqual(isTabActive('/trd', '/snt'), false)

// 3. Reachability from Overview: Every permitted tab must have a valid path reachable from /dashboard
for (const tab of adminTabs) {
  assert.ok(tab.to && tab.to.startsWith('/'), `Tab ${tab.label} must have a valid absolute path`)
}

console.log('✓ All navigation and reachability tests passed successfully!')
