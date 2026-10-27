/**
 * Indian Railway Network Infrastructure & Fleet Registry
 * Strict geographic boundaries: Only within the Republic of India.
 * No tracks or trains rendered across foreign nations (China, Pakistan, Nepal, etc.)
 */

export const INDIAN_STATIONS = [
  { id: 'NDLS', name: 'Delhi', lat: 28.6435, lng: 77.2197, zone: 'NR' },
  { id: 'LDH', name: 'Ludhiana', lat: 30.9010, lng: 75.8573, zone: 'NR' },
  { id: 'ASR', name: 'Amritsar', lat: 31.6336, lng: 74.8737, zone: 'NR' },
  { id: 'JP', name: 'Jaipur', lat: 26.9196, lng: 75.7878, zone: 'NWR' },
  { id: 'LKO', name: 'Lucknow', lat: 26.8302, lng: 80.9151, zone: 'NR' },
  { id: 'BCT', name: 'Mumbai', lat: 18.9696, lng: 72.8205, zone: 'WR' },
  { id: 'HWH', name: 'Kolkata', lat: 22.5831, lng: 88.3426, zone: 'ER' },
  { id: 'MAS', name: 'Chennai', lat: 13.0827, lng: 80.2707, zone: 'SR' },
  { id: 'SBC', name: 'Bengaluru', lat: 12.9779, lng: 77.5713, zone: 'SWR' },
  { id: 'SC', name: 'Hyderabad', lat: 17.4399, lng: 78.5011, zone: 'SCR' },
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

export const ACTIVE_INDIAN_FLEET = []

