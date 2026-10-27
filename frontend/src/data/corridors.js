/**
 * Corridor + source-system reference data.
 *
 * Stands in for what the ETL layer would normalise out of COA. Station codes
 * and the corridor shapes follow the Delhi–Howrah and Delhi–Mumbai trunk
 * routes so the demo reads as a real division to anyone who knows the network.
 */

/**
 * `trafficProfile` is twelve two-hour buckets across the day, starting at
 * 00:00: the share of that corridor's daily train movements falling in each
 * bucket, on a 0-100 scale. Nights are the trough and the morning peak the
 * crest — which is why block windows cluster where they do.
 */
export const corridors = [
  {
    id: 'C-NDLS-GZB',
    name: 'NDLS – GZB',
    long: 'New Delhi – Ghaziabad',
    sections: ['NDLS–SBB', 'SBB–SHDM', 'SHDM–GZB'],
    routeKm: 26,
    trainsPerDay: 312,
    goodsShare: 0.21,
    trafficProfile: [38, 22, 26, 64, 96, 88, 74, 79, 91, 86, 72, 52],
  },
  {
    id: 'C-GZB-ALJN',
    name: 'GZB – ALJN',
    long: 'Ghaziabad – Aligarh',
    sections: ['GZB–DER', 'DER–KRJ', 'KRJ–ALJN'],
    routeKm: 126,
    trainsPerDay: 188,
    goodsShare: 0.38,
    trafficProfile: [44, 26, 24, 55, 78, 82, 69, 58, 63, 72, 61, 48],
  },
  {
    id: 'C-ALJN-CNB',
    name: 'ALJN – CNB',
    long: 'Aligarh – Kanpur Central',
    sections: ['ALJN–TDL', 'TDL–ETW', 'ETW–CNB'],
    routeKm: 288,
    trainsPerDay: 164,
    goodsShare: 0.44,
    trafficProfile: [39, 24, 21, 46, 70, 76, 64, 52, 57, 66, 54, 45],
  },
  {
    id: 'C-BCT-BSR',
    name: 'BCT – BSR',
    long: 'Mumbai Central – Vasai Road',
    sections: ['BCT–BVI', 'BVI–BSR'],
    routeKm: 61,
    trainsPerDay: 274,
    goodsShare: 0.12,
    trafficProfile: [33, 20, 25, 72, 99, 92, 84, 68, 72, 86, 88, 59],
  },
  {
    id: 'C-BSR-ST',
    name: 'BSR – ST',
    long: 'Vasai Road – Surat',
    sections: ['BSR–PLG', 'PLG–BL', 'BL–ST'],
    routeKm: 202,
    trainsPerDay: 142,
    goodsShare: 0.49,
    trafficProfile: [36, 24, 17, 41, 63, 71, 60, 51, 55, 61, 49, 44],
  },
]

export const sourceSystems = [
  {
    id: 'TMS',
    name: 'TMS',
    long: 'Track Management System',
    dept: 'ENG',
    feeds: 'Track geometry defects, rail flaws, overdue tamping',
    records: 1284,
    lastSync: '04:15',
    status: 'synced',
    freeTextShare: 0.34,
  },
  {
    id: 'SMMS',
    name: 'SMMS',
    long: 'Signalling Maintenance & Management System',
    dept: 'SNT',
    feeds: 'Point machine faults, track circuit failures, cable defects',
    records: 946,
    lastSync: '04:15',
    status: 'synced',
    freeTextShare: 0.51,
  },
  {
    id: 'TDMS',
    name: 'TDMS',
    long: 'Traction Distribution Management System',
    dept: 'TRD',
    feeds: 'OHE wear, insulator faults, feeder and SSP defects',
    records: 733,
    lastSync: '04:16',
    status: 'synced',
    freeTextShare: 0.42,
  },
  {
    id: 'COA',
    name: 'COA',
    long: 'Control Office Application',
    dept: null,
    feeds: 'Corridor block calendar, working timetable, goods forecast',
    records: 5107,
    lastSync: '04:22',
    status: 'partial',
    freeTextShare: 0.03,
  },
]
