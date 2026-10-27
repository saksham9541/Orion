/**
 * Indian Railway Network Infrastructure & Fleet Registry
 * Strict geographic boundaries: Only within the Republic of India.
 * No tracks or trains rendered across foreign nations (China, Pakistan, Nepal, etc.)
 */

export const INDIAN_STATIONS = [
  { id: 'NDLS', name: 'New Delhi', lat: 28.6435, lng: 77.2197, zone: 'NR' },
  { id: 'LDH', name: 'Ludhiana Jn', lat: 30.9010, lng: 75.8573, zone: 'NR' },
  { id: 'ASR', name: 'Amritsar Jn', lat: 31.6336, lng: 74.8737, zone: 'NR' },
  { id: 'JAT', name: 'Jammu Tawi', lat: 32.7060, lng: 74.8797, zone: 'NR' },
  { id: 'JP', name: 'Jaipur Jn', lat: 26.9196, lng: 75.7878, zone: 'NWR' },
  { id: 'AII', name: 'Ajmer Jn', lat: 26.4499, lng: 74.6399, zone: 'NWR' },
  { id: 'ADI', name: 'Ahmedabad Jn', lat: 23.0225, lng: 72.5714, zone: 'WR' },
  { id: 'BCT', name: 'Mumbai Central', lat: 18.9696, lng: 72.8205, zone: 'WR' },
  { id: 'CSMT', name: 'Mumbai CSMT', lat: 18.9400, lng: 72.8354, zone: 'CR' },
  { id: 'PUNE', name: 'Pune Jn', lat: 18.5204, lng: 73.8567, zone: 'CR' },
  { id: 'LKO', name: 'Lucknow Charbagh', lat: 26.8302, lng: 80.9151, zone: 'NR' },
  { id: 'CNB', name: 'Kanpur Central', lat: 26.4499, lng: 80.3319, zone: 'NCR' },
  { id: 'PRYJ', name: 'Prayagraj Jn', lat: 25.4358, lng: 81.8463, zone: 'NCR' },
  { id: 'BSB', name: 'Varanasi Jn', lat: 25.3176, lng: 82.9739, zone: 'NER' },
  { id: 'PNBE', name: 'Patna Jn', lat: 25.5941, lng: 85.1376, zone: 'ECR' },
  { id: 'HWH', name: 'Howrah (Kolkata)', lat: 22.5831, lng: 88.3426, zone: 'ER' },
  { id: 'GHY', name: 'Guwahati', lat: 26.1445, lng: 91.7362, zone: 'NFR' },
  { id: 'BPL', name: 'Bhopal Jn', lat: 23.2599, lng: 77.4126, zone: 'WCR' },
  { id: 'NGP', name: 'Nagpur Jn', lat: 21.1458, lng: 79.0882, zone: 'CR' },
  { id: 'R', name: 'Raipur Jn', lat: 21.2514, lng: 81.6296, zone: 'SECR' },
  { id: 'BBS', name: 'Bhubaneswar', lat: 20.2961, lng: 85.8245, zone: 'ECoR' },
  { id: 'VSKP', name: 'Visakhapatnam', lat: 17.6868, lng: 83.2185, zone: 'ECoR' },
  { id: 'SC', name: 'Secunderabad', lat: 17.4399, lng: 78.5011, zone: 'SCR' },
  { id: 'BZA', name: 'Vijayawada Jn', lat: 16.5062, lng: 80.6480, zone: 'SCR' },
  { id: 'MAS', name: 'Chennai Central', lat: 13.0827, lng: 80.2707, zone: 'SR' },
  { id: 'SBC', name: 'Bengaluru City', lat: 12.9779, lng: 77.5713, zone: 'SWR' },
  { id: 'MAQ', name: 'Mangaluru Jn', lat: 12.8703, lng: 74.8806, zone: 'SR' },
  { id: 'ERS', name: 'Kochi (Ernakulam)', lat: 9.9816, lng: 76.2999, zone: 'SR' },
  { id: 'TVC', name: 'Thiruvananthapuram', lat: 8.5241, lng: 76.9366, zone: 'SR' },
]

export const INDIAN_RAIL_CORRIDORS = [
  // 1. Delhi - Ludhiana - Amritsar - Jammu (Northern Trunk)
  {
    id: 'COR-NDLS-ASR-JAT',
    name: 'Northern Trunk (Delhi–Amritsar–Jammu)',
    color: '#38bdf8',
    coords: [
      [28.6435, 77.2197], // NDLS
      [28.9845, 77.1025], // Sonipat
      [29.3909, 76.9635], // Panipat
      [29.6857, 76.9905], // Karnal
      [30.1727, 76.8404], // Kurukshetra
      [30.3610, 76.8485], // Ambala Cantt
      [30.9010, 75.8573], // Ludhiana
      [31.3260, 75.5762], // Jalandhar
      [31.6336, 74.8737], // Amritsar
      [32.2689, 75.6499], // Pathankot
      [32.7060, 74.8797], // Jammu Tawi
    ],
  },
  // 2. Delhi - Jaipur - Ajmer - Ahmedabad (North-Western Trunk)
  {
    id: 'COR-NDLS-JP-ADI',
    name: 'North-Western Trunk (Delhi–Jaipur–Ahmedabad)',
    color: '#eab308',
    coords: [
      [28.6435, 77.2197], // NDLS
      [28.4595, 77.0266], // Gurugram
      [28.1920, 76.6191], // Rewari
      [27.5530, 76.6346], // Alwar
      [27.0504, 76.5744], // Bandikui
      [26.9196, 75.7878], // Jaipur
      [26.4499, 74.6399], // Ajmer
      [25.7314, 73.6166], // Marwar
      [25.2215, 73.2386], // Falna
      [24.4820, 72.7811], // Abu Road
      [24.1724, 72.4346], // Palanpur
      [23.5880, 72.3693], // Mehsana
      [23.0225, 72.5714], // Ahmedabad
    ],
  },
  // 3. Delhi - Mathura - Kota - Vadodara - Mumbai (Western Trunk / Rajdhani Route)
  {
    id: 'COR-NDLS-KOTA-BCT',
    name: 'Western Trunk (Delhi–Kota–Vadodara–Mumbai)',
    color: '#06b6d4',
    coords: [
      [28.6435, 77.2197], // NDLS
      [28.1487, 77.3260], // Faridabad
      [27.4924, 77.6737], // Mathura
      [27.2152, 77.5030], // Bharatpur
      [25.9928, 76.3533], // Sawai Madhopur
      [25.1825, 75.8398], // Kota
      [24.2345, 75.8200], // Shamgarh
      [23.5878, 75.3340], // Nagda
      [23.3344, 75.0376], // Ratlam
      [22.8028, 74.2562], // Dahod
      [22.3072, 73.1812], // Vadodara
      [21.6948, 73.0135], // Bharuch
      [21.1702, 72.8311], // Surat
      [20.6100, 72.9258], // Valsad
      [20.3893, 72.9106], // Vapi
      [19.8245, 72.7533], // Palghar
      [19.3813, 72.8311], // Vasai Road
      [19.1860, 72.8485], // Borivali
      [18.9696, 72.8205], // Mumbai Central
    ],
  },
  // 4. Ahmedabad - Vadodara - Surat (Gujarat Coastal Link)
  {
    id: 'COR-ADI-BRC-ST',
    name: 'Gujarat Coastal (Ahmedabad–Surat)',
    color: '#f97316',
    coords: [
      [23.0225, 72.5714], // Ahmedabad
      [22.5560, 72.9515], // Anand
      [22.3072, 73.1812], // Vadodara
      [21.6948, 73.0135], // Bharuch
      [21.1702, 72.8311], // Surat
    ],
  },
  // 5. Delhi - Kanpur - Prayagraj - Varanasi - Howrah (Eastern Trunk / Grand Chord)
  {
    id: 'COR-NDLS-CNB-HWH',
    name: 'Eastern Trunk (Delhi–Kanpur–Gaya–Howrah)',
    color: '#10b981',
    coords: [
      [28.6435, 77.2197], // NDLS
      [28.6692, 77.4538], // Ghaziabad
      [27.8974, 78.0880], // Aligarh
      [27.2062, 78.2415], // Tundla
      [26.7725, 79.0320], // Etawah
      [26.4499, 80.3319], // Kanpur Central
      [25.9220, 80.8120], // Fatehpur
      [25.4358, 81.8463], // Prayagraj
      [25.2818, 83.1189], // Pt Deen Dayal Upadhyaya
      [24.9536, 84.0298], // Sasaram
      [24.7914, 85.0002], // Gaya
      [24.4673, 85.5939], // Koderma
      [23.7957, 86.4304], // Dhanbad
      [23.6889, 86.9661], // Asansol
      [23.2324, 87.8615], // Bardhaman
      [22.5831, 88.3426], // Howrah
    ],
  },
  // 6. Delhi - Moradabad - Bareilly - Lucknow - Varanasi (Northern Mainline)
  {
    id: 'COR-NDLS-LKO-BSB',
    name: 'Awadh Mainline (Delhi–Lucknow–Varanasi)',
    color: '#ec4899',
    coords: [
      [28.6435, 77.2197], // NDLS
      [28.6692, 77.4538], // Ghaziabad
      [28.8386, 78.7733], // Moradabad
      [28.3670, 79.4304], // Bareilly
      [27.8785, 79.9135], // Shahjahanpur
      [26.8302, 80.9151], // Lucknow
      [26.5432, 81.8745], // Sultanpur
      [25.3176, 82.9739], // Varanasi
      [25.2818, 83.1189], // Pt Deen Dayal Upadhyaya
    ],
  },
  // 7. Delhi - Agra - Gwalior - Jhansi - Bhopal - Nagpur (Grand Trunk North-South)
  {
    id: 'COR-NDLS-BPL-NGP',
    name: 'Grand Trunk North (Delhi–Bhopal–Nagpur)',
    color: '#a855f7',
    coords: [
      [28.6435, 77.2197], // NDLS
      [27.4924, 77.6737], // Mathura
      [27.1593, 78.0064], // Agra Cantt
      [26.2183, 78.1828], // Gwalior
      [25.4484, 78.5685], // Jhansi
      [24.1685, 78.1925], // Bina
      [23.2599, 77.4126], // Bhopal
      [22.6139, 77.7642], // Itarsi
      [21.6425, 78.1250], // Betul
      [21.1458, 79.0882], // Nagpur
    ],
  },
  // 8. Nagpur - Balharshah - Kazipet - Vijayawada - Chennai (Grand Trunk South)
  {
    id: 'COR-NGP-BZA-MAS',
    name: 'Grand Trunk South (Nagpur–Vijayawada–Chennai)',
    color: '#06b6d4',
    coords: [
      [21.1458, 79.0882], // Nagpur
      [20.7453, 78.6022], // Sewagram
      [19.8553, 79.3524], // Balharshah
      [18.7750, 79.5210], // Ramagundam
      [17.9689, 79.5941], // Kazipet
      [17.4399, 78.5011], // Secunderabad (branch)
      [16.5062, 80.6480], // Vijayawada
      [15.5057, 80.0499], // Ongole
      [14.4426, 79.9865], // Nellore
      [14.1463, 79.8504], // Gudur
      [13.0827, 80.2707], // Chennai Central
    ],
  },
  // 9. Mumbai - Nashik - Bhusawal - Nagpur - Raipur - Howrah (Trans-India Mainline)
  {
    id: 'COR-CSMT-NGP-HWH',
    name: 'Central Trans-India (Mumbai–Nagpur–Howrah)',
    color: '#f43f5e',
    coords: [
      [18.9400, 72.8354], // Mumbai CSMT
      [19.2403, 73.1305], // Kalyan
      [19.6890, 73.5350], // Igatpuri
      [19.9615, 73.8217], // Nashik
      [20.2505, 74.4419], // Manmad
      [21.0455, 75.7885], // Bhusawal
      [20.7002, 77.0082], // Akola
      [20.8656, 77.7289], // Badnera (Amravati)
      [20.7453, 78.6022], // Wardha
      [21.1458, 79.0882], // Nagpur
      [21.4598, 80.1961], // Gondia
      [21.1904, 81.2849], // Durg
      [21.2514, 81.6296], // Raipur
      [22.0797, 82.1409], // Bilaspur
      [21.8554, 84.0062], // Jharsuguda
      [22.2604, 84.8536], // Rourkela
      [22.7011, 85.6267], // Chakradharpur
      [22.7719, 86.1953], // Tatanagar
      [22.3396, 87.3256], // Kharagpur
      [22.5831, 88.3426], // Howrah
    ],
  },
  // 10. Howrah - Bhubaneswar - Visakhapatnam - Vijayawada - Chennai (East Coast)
  {
    id: 'COR-HWH-BBS-MAS',
    name: 'East Coast Mainline (Howrah–Visakhapatnam–Chennai)',
    color: '#38bdf8',
    coords: [
      [22.5831, 88.3426], // Howrah
      [22.3396, 87.3256], // Kharagpur
      [21.4934, 86.9135], // Balasore
      [21.0543, 86.4962], // Bhadrak
      [20.4625, 85.8828], // Cuttack
      [20.2961, 85.8245], // Bhubaneswar
      [20.1873, 85.7336], // Khurda Road
      [19.3150, 84.7941], // Brahmapur
      [18.1067, 83.3956], // Vizianagaram
      [17.6868, 83.2185], // Visakhapatnam
      [17.0005, 81.8040], // Rajahmundry
      [16.5062, 80.6480], // Vijayawada
      [13.0827, 80.2707], // Chennai Central
    ],
  },
  // 11. Mumbai - Pune - Solapur - Guntakal - Chennai & Bengaluru (South-Western)
  {
    id: 'COR-BCT-PUNE-MAS',
    name: 'South-Western Trunk (Mumbai–Pune–Chennai)',
    color: '#fb923c',
    coords: [
      [18.9696, 72.8205], // Mumbai
      [18.5204, 73.8567], // Pune
      [18.4658, 74.5828], // Daund
      [17.6599, 75.9064], // Solapur
      [17.0560, 76.9926], // Wadi
      [16.2120, 77.3439], // Raichur
      [15.1678, 77.3686], // Guntakal
      [14.4673, 78.8242], // Kadapa
      [13.6288, 79.4192], // Renigunta (Tirupati)
      [13.0827, 80.2707], // Chennai Central
    ],
  },
  // 12. Guntakal - Bengaluru - Mysuru
  {
    id: 'COR-GTL-SBC',
    name: 'Deccan South (Guntakal–Bengaluru–Mysuru)',
    color: '#eab308',
    coords: [
      [15.1678, 77.3686], // Guntakal
      [14.4137, 77.7126], // Dharmavaram
      [13.4325, 77.6540], // Hindupur
      [12.9779, 77.5713], // Bengaluru
      [12.2958, 76.6394], // Mysuru
    ],
  },
  // 13. Chennai - Bengaluru - Coimbatore - Kochi - Trivandrum
  {
    id: 'COR-MAS-SBC-ERS-TVC',
    name: 'Southern Peninsular (Chennai–Coimbatore–Kochi–Trivandrum)',
    color: '#22c55e',
    coords: [
      [13.0827, 80.2707], // Chennai
      [12.9986, 78.1882], // Bangarapet
      [12.5694, 78.5772], // Jolarpettai
      [11.6643, 78.1460], // Salem
      [11.3410, 77.7172], // Erode
      [11.0168, 76.9558], // Coimbatore
      [10.7867, 76.6548], // Palakkad
      [10.7600, 76.2800], // Shoranur
      [10.5276, 76.2144], // Thrissur
      [9.9816, 76.2999],  // Ernakulam / Kochi
      [9.5916, 76.5222],  // Kottayam
      [8.8932, 76.6141],  // Kollam
      [8.5241, 76.9366],  // Thiruvananthapuram
    ],
  },
  // 14. Konkan Railway (Mumbai - Goa - Mangaluru - Kerala)
  {
    id: 'COR-KONKAN',
    name: 'Konkan Railway (Mumbai–Goa–Mangaluru)',
    color: '#06b6d4',
    coords: [
      [18.9696, 72.8205], // Mumbai
      [18.4388, 73.1189], // Roha
      [17.7183, 73.3892], // Khed
      [17.5323, 73.5186], // Chiplun
      [16.9902, 73.3120], // Ratnagiri
      [15.2743, 73.9803], // Madgaon (Goa)
      [14.8185, 74.1350], // Karwar
      [13.3409, 74.7421], // Udupi
      [12.8703, 74.8806], // Mangaluru
      [11.8745, 75.3704], // Kannur
      [11.2588, 75.7804], // Kozhikode
      [10.7600, 76.2800], // Shoranur
    ],
  },
  // 15. Kolkata - Malda - New Jalpaiguri - Guwahati - Dibrugarh (Northeast Frontier)
  {
    id: 'COR-HWH-GHY-DBRG',
    name: 'Northeast Frontier (Kolkata–Guwahati–Dibrugarh)',
    color: '#10b981',
    coords: [
      [22.5831, 88.3426], // Howrah
      [23.6693, 87.6938], // Bolpur
      [25.0108, 88.1411], // Malda Town
      [26.0967, 87.9405], // Kishanganj
      [26.6853, 88.4419], // New Jalpaiguri
      [26.3452, 89.4641], // New Cooch Behar
      [26.5024, 90.5574], // New Bongaigaon
      [26.4385, 91.6267], // Rangiya
      [26.1445, 91.7362], // Guwahati
      [25.7538, 93.1706], // Lumding
      [25.9068, 93.7274], // Dimapur
      [27.4728, 94.9120], // Dibrugarh
    ],
  },
]

/**
 * Curated live Indian fleet of trains positioned strictly along Indian railway tracks.
 * Matches the user reference image (media_1793128237164_fb163c31.jpg) with colorful
 * trains in cyan, orange, yellow, pink, and emerald.
 */
export const ACTIVE_INDIAN_FLEET = [
  // Western Corridors
  { number: '12951', name: 'Mumbai Rajdhani', lat: 26.4210, lng: 76.8120, speed: 128, color: '#38bdf8', status: 'ON TIME', route: 'NDLS → MMCT' },
  { number: '12952', name: 'Mumbai Rajdhani (Up)', lat: 21.8410, lng: 73.0512, speed: 124, color: '#38bdf8', status: 'ON TIME', route: 'MMCT → NDLS' },
  { number: '12953', name: 'August Kranti Tejas', lat: 24.8120, lng: 75.6120, speed: 130, color: '#06b6d4', status: 'ON TIME', route: 'MMCT → NZM' },
  { number: '20901', name: 'Vande Bharat Express', lat: 20.9120, lng: 72.8940, speed: 145, color: '#00f0ff', status: 'ON TIME', route: 'MMCT → GNC' },
  { number: '12009', name: 'Mumbai-Ahmedabad Shatabdi', lat: 22.1240, lng: 73.1250, speed: 120, color: '#f59e0b', status: 'ON TIME', route: 'MMCT → ADI' },
  { number: '12903', name: 'Golden Temple Mail', lat: 27.2140, lng: 77.5810, speed: 95, color: '#f97316', status: 'DELAYED 14m', route: 'MMCT → ASR' },
  { number: '12925', name: 'Paschim Express', lat: 23.4120, lng: 75.1120, speed: 105, color: '#ec4899', status: 'ON TIME', route: 'BDTS → ASR' },
  { number: '12979', name: 'Jaipur Superfast', lat: 28.0120, lng: 76.7120, speed: 110, color: '#eab308', status: 'ON TIME', route: 'BDTS → JP' },

  // Eastern Corridors (Delhi - Kanpur - Kolkata)
  { number: '12301', name: 'Howrah Rajdhani', lat: 26.0210, lng: 81.1240, speed: 130, color: '#38bdf8', status: 'ON TIME', route: 'HWH → NDLS' },
  { number: '12302', name: 'Howrah Rajdhani (Up)', lat: 24.3120, lng: 85.8120, speed: 125, color: '#38bdf8', status: 'DELAYED 8m', route: 'NDLS → HWH' },
  { number: '22436', name: 'Vande Bharat (Varanasi)', lat: 26.1120, lng: 81.4120, speed: 155, color: '#00f0ff', status: 'ON TIME', route: 'NDLS → BSB' },
  { number: '12305', name: 'Kolkata Rajdhani', lat: 25.1240, lng: 83.6120, speed: 122, color: '#10b981', status: 'ON TIME', route: 'HWH → NDLS' },
  { number: '12313', name: 'Sealdah Rajdhani', lat: 23.5120, lng: 87.2120, speed: 130, color: '#06b6d4', status: 'ON TIME', route: 'SDAH → NDLS' },
  { number: '12801', name: 'Purushottam Express', lat: 24.9120, lng: 84.4120, speed: 100, color: '#f59e0b', status: 'ON TIME', route: 'PURI → NDLS' },
  { number: '12393', name: 'Sampoorna Kranti', lat: 25.8120, lng: 82.2120, speed: 115, color: '#ec4899', status: 'ON TIME', route: 'RJPB → NDLS' },
  { number: '12417', name: 'Prayagraj Express', lat: 26.7120, lng: 79.6120, speed: 120, color: '#f97316', status: 'ON TIME', route: 'PRYJ → NDLS' },

  // Northern Corridors (Delhi - Ludhiana - Amritsar)
  { number: '12013', name: 'Amritsar Shatabdi', lat: 30.6120, lng: 76.3120, speed: 130, color: '#eab308', status: 'ON TIME', route: 'NDLS → ASR' },
  { number: '12014', name: 'Amritsar Shatabdi (Up)', lat: 31.1240, lng: 75.7120, speed: 125, color: '#eab308', status: 'ON TIME', route: 'ASR → NDLS' },
  { number: '22439', name: 'Vande Bharat (Katra)', lat: 31.9120, lng: 75.4120, speed: 140, color: '#00f0ff', status: 'ON TIME', route: 'NDLS → SVDK' },
  { number: '12425', name: 'Jammu Rajdhani', lat: 29.8120, lng: 76.9120, speed: 120, color: '#38bdf8', status: 'ON TIME', route: 'NDLS → JAT' },
  { number: '12005', name: 'Kalka Shatabdi', lat: 30.1120, lng: 76.9120, speed: 115, color: '#10b981', status: 'ON TIME', route: 'NDLS → KLK' },

  // Grand Trunk North-South (Delhi - Bhopal - Nagpur - Chennai)
  { number: '12434', name: 'Chennai Rajdhani', lat: 25.1120, lng: 78.4120, speed: 130, color: '#38bdf8', status: 'ON TIME', route: 'NZM → MAS' },
  { number: '12433', name: 'Chennai Rajdhani (Up)', lat: 17.1240, lng: 80.1120, speed: 128, color: '#38bdf8', status: 'ON TIME', route: 'MAS → NZM' },
  { number: '12615', name: 'Grand Trunk Express', lat: 22.1240, lng: 78.3120, speed: 105, color: '#f59e0b', status: 'DELAYED 20m', route: 'MAS → NDLS' },
  { number: '12621', name: 'Tamil Nadu Express', lat: 19.1240, lng: 79.4120, speed: 118, color: '#f97316', status: 'ON TIME', route: 'MAS → NDLS' },
  { number: '12626', name: 'Kerala Express', lat: 23.8120, lng: 77.9120, speed: 110, color: '#22c55e', status: 'ON TIME', route: 'NDLS → TVC' },
  { number: '20805', name: 'Vande Bharat (Secunderabad)', lat: 18.4120, lng: 79.6120, speed: 140, color: '#00f0ff', status: 'ON TIME', route: 'SC → VSKP' },

  // Trans-Central (Mumbai - Nagpur - Raipur - Howrah)
  { number: '12859', name: 'Gitanjali Express', lat: 21.1920, lng: 79.8120, speed: 110, color: '#ec4899', status: 'ON TIME', route: 'CSMT → HWH' },
  { number: '12860', name: 'Gitanjali Express (Up)', lat: 22.4120, lng: 83.8120, speed: 108, color: '#ec4899', status: 'ON TIME', route: 'HWH → CSMT' },
  { number: '12261', name: 'Mumbai-Howrah Duronto', lat: 20.8120, lng: 76.5120, speed: 125, color: '#10b981', status: 'ON TIME', route: 'CSMT → HWH' },
  { number: '12810', name: 'Howrah-Mumbai Mail', lat: 22.1120, lng: 82.8120, speed: 102, color: '#f59e0b', status: 'ON TIME', route: 'HWH → CSMT' },
  { number: '20826', name: 'Vande Bharat (Bilaspur)', lat: 21.3120, lng: 81.4120, speed: 135, color: '#00f0ff', status: 'ON TIME', route: 'BSP → NGP' },

  // East Coast & South
  { number: '12841', name: 'Coromandel Express', lat: 19.8120, lng: 85.1120, speed: 120, color: '#f97316', status: 'ON TIME', route: 'HWH → MAS' },
  { number: '12842', name: 'Coromandel Express (Up)', lat: 15.1120, lng: 80.1120, speed: 118, color: '#f97316', status: 'ON TIME', route: 'MAS → HWH' },
  { number: '22807', name: 'Vande Bharat (Puri)', lat: 21.8120, lng: 86.8120, speed: 140, color: '#00f0ff', status: 'ON TIME', route: 'HWH → PURI' },
  { number: '22691', name: 'Bengaluru Rajdhani', lat: 16.1120, lng: 77.8120, speed: 130, color: '#38bdf8', status: 'ON TIME', route: 'SBC → NZM' },
  { number: '12027', name: 'Shatabdi Express', lat: 13.1120, lng: 78.4120, speed: 115, color: '#eab308', status: 'ON TIME', route: 'MAS → SBC' },
  { number: '20607', name: 'Vande Bharat (Mysuru)', lat: 12.8120, lng: 77.9120, speed: 135, color: '#00f0ff', status: 'ON TIME', route: 'MAS → MYS' },

  // Konkan & Kerala
  { number: '12431', name: 'Trivandrum Rajdhani', lat: 15.8120, lng: 73.8120, speed: 120, color: '#38bdf8', status: 'ON TIME', route: 'TVC → NZM' },
  { number: '12432', name: 'Trivandrum Rajdhani (Up)', lat: 11.6120, lng: 75.6120, speed: 115, color: '#38bdf8', status: 'ON TIME', route: 'NZM → TVC' },
  { number: '22229', name: 'Vande Bharat (Goa)', lat: 17.2120, lng: 73.4120, speed: 130, color: '#00f0ff', status: 'ON TIME', route: 'CSMT → MAO' },
  { number: '16345', name: 'Netravati Express', lat: 13.7120, lng: 74.6120, speed: 90, color: '#22c55e', status: 'ON TIME', route: 'LTT → TVC' },

  // Northeast Frontier
  { number: '12423', name: 'Dibrugarh Rajdhani', lat: 26.2120, lng: 89.8120, speed: 120, color: '#38bdf8', status: 'ON TIME', route: 'DBRG → NDLS' },
  { number: '12424', name: 'Dibrugarh Rajdhani (Up)', lat: 25.6120, lng: 88.0120, speed: 118, color: '#38bdf8', status: 'ON TIME', route: 'NDLS → DBRG' },
  { number: '22227', name: 'Vande Bharat (Guwahati)', lat: 26.3120, lng: 90.9120, speed: 130, color: '#00f0ff', status: 'ON TIME', route: 'NJP → GHY' },

  // Freight & Dedicated Freight Corridors (DFCCIL)
  { number: 'WDFC-801', name: 'Western DFC Container Freight', lat: 25.6120, lng: 74.8120, speed: 85, color: '#10b981', status: 'ON TIME', route: 'Dadri → JNPT' },
  { number: 'EDFC-402', name: 'Eastern DFC Heavy Haul Coal', lat: 25.0120, lng: 82.8120, speed: 75, color: '#f59e0b', status: 'ON TIME', route: 'Ludhiana → Sonnagar' },
  { number: 'AUTO-109', name: 'Maruti Car Carrier Rake', lat: 27.8120, lng: 76.9120, speed: 80, color: '#ec4899', status: 'ON TIME', route: 'Gurgaon → Chennai' },
  { number: 'RO-RO-22', name: 'Konkan Ro-Ro Truck Carrier', lat: 16.4120, lng: 73.6120, speed: 70, color: '#38bdf8', status: 'ON TIME', route: 'Kolad → Surathkal' },
]
