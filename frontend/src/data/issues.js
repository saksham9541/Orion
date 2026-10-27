export const DEMO_ISSUES = [
  {
    id: 'RO-ENG-001',
    locationId: 'LDH',
    locationName: 'Ludhiana',
    exactLocation: 'KM 342/1 - 342/5 (Between LDH and PGW)',
    department: 'ENGINEERING',
    severity: 'CRITICAL',
    status: 'NEW',
    type: 'Track condition issue',
    time: '10:42 AM',
    details: {
      what: 'Track condition has deteriorated in the affected section and requires engineering attention.',
      why: [
        { level: 'LIKELY', text: 'Recent inspection observation' },
        { level: 'LIKELY', text: 'Repeated maintenance requirement' },
        { level: 'POSSIBLE', text: 'Increasing risk indicators' }
      ],
      how: [
        { state: 'Reported', active: false },
        { state: 'Detected', active: false },
        { state: 'Analysed', active: false },
        { state: 'Alert Raised', active: true },
        { state: 'Action Required', active: false }
      ],
      impact: 'Potential maintenance block requirement, speed restriction, and operational disruption.',
      seriousness: 'Critical — left unaddressed, this risks an unplanned speed restriction or emergency block within days.',
      recommendation: 'Schedule the required engineering maintenance during the next suitable maintenance window.',
      supporting: 'Last maintenance performed 14 months ago. Risk score 0.85.'
    }
  },
  {
    id: 'RO-SNT-042',
    locationId: 'NDLS',
    locationName: 'Delhi',
    exactLocation: 'KM 12/4 (Approach Signal 4A)',
    department: 'S&T',
    severity: 'HIGH',
    status: 'ACKNOWLEDGED',
    type: 'Signal failure',
    time: '09:15 AM',
    details: {
      what: 'Intermittent signal failure reported at Main Junction approach.',
      why: [
        { level: 'CONFIRMED', text: 'Loss of track circuit continuity' },
        { level: 'POSSIBLE', text: 'Cable degradation' }
      ],
      how: [
        { state: 'Reported', active: false },
        { state: 'Detected', active: false },
        { state: 'Analysed', active: true },
        { state: 'Alert Raised', active: false },
        { state: 'Action Required', active: false }
      ],
      impact: 'Traffic halted in Sector 4 until manual override authorized.',
      seriousness: 'High — active operational impact right now, contained by manual override but not resolved.',
      recommendation: 'Dispatch S&T rapid response team to inspect track joint bonds.',
      supporting: 'Similar failure recorded on adjacent line last week.'
    }
  },
  {
    id: 'RO-TRD-088',
    locationId: 'JP',
    locationName: 'Jaipur',
    exactLocation: 'KM 156/8 - 157/2 (OHE Mast 156/22)',
    department: 'TRD',
    severity: 'MEDIUM',
    status: 'IN PROGRESS',
    type: 'OHE inspection required',
    time: '07:30 AM',
    details: {
      what: 'Minor voltage fluctuations detected on OHE catenary wire.',
      why: [
        { level: 'LIKELY', text: 'Heavy pollution/dust on insulators' }
      ],
      how: [
        { state: 'Reported', active: false },
        { state: 'Detected', active: true },
        { state: 'Analysed', active: false },
        { state: 'Alert Raised', active: false },
        { state: 'Action Required', active: false }
      ],
      impact: 'Low immediate risk. Routine maintenance required.',
      seriousness: 'Medium — no immediate safety concern, but left unresolved could progress to a High-severity fault.',
      recommendation: 'Schedule tower wagon during off-peak hours.',
      supporting: 'No trains currently delayed.'
    }
  }
];
