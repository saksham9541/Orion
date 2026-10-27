Please create the interactive Leaflet map component for the frontend dashboard based on the user's advice.

1. **Create `frontend/src/components/NetworkMap.jsx`**
   - Import `MapContainer`, `TileLayer`, `Polyline`, `Popup` from `react-leaflet`.
   - Also import `L` (leaflet core).
   - Base map URL: `"https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"`
   - Create a helper to generate fake polyline geometry based on `start_km` and `end_km`:
     ```javascript
     // Fake geometry per corridor (e.g., Delhi to Mumbai approx)
     const CORRIDOR_POINTS = {
       "C-NDLS-BCT": [[28.61, 77.23], [27.17, 78.00], [23.25, 77.41], [19.07, 72.87]], // Delhi to Mumbai
       "C-HWH-CSTM": [[22.57, 88.36], [21.25, 81.62], [21.14, 79.08], [19.07, 72.87]], // Howrah to Mumbai
       // Fallback for any other ID
       "DEFAULT": [[22.5, 79.0], [21.0, 78.0], [20.0, 77.0]]
     };

     // Interpolate a segment along the polyline based on a fraction (km / total_km)
     // You can approximate this easily for the visual effect:
     // If you don't want to do complex interpolation, just map the section to a small line segment near the corridor path.
     ```
   - *Alternative simpler geometry*: Just hardcode 10 straight lines for the 10 corridors across India.
     ```javascript
     const getCorridorBaseLine = (id) => {
        // Return a static array of [lat, lng] for the base line of the corridor
        const lines = {
           "C-0": [[28.6, 77.2], [19.0, 72.8]], // Delhi-Mumbai
           "C-1": [[28.6, 77.2], [22.5, 88.3]], // Delhi-Howrah
           "C-2": [[19.0, 72.8], [13.0, 80.2]], // Mumbai-Chennai
           "C-3": [[22.5, 88.3], [13.0, 80.2]], // Howrah-Chennai
           "C-4": [[28.6, 77.2], [13.0, 80.2]], // Delhi-Chennai
        };
        // Use a hash of the string to pick one if not matching
        const key = "C-" + (id.charCodeAt(id.length-1) % 5);
        return lines[key] || lines["C-0"];
     };

     const getBlockSegment = (corridorId, startKm, endKm) => {
         const baseLine = getCorridorBaseLine(corridorId);
         // Extremely simple fake interpolation: assume corridor is 1000km long.
         // (startKm / 1000) fraction along the line.
         const startFrac = Math.min(startKm / 1000, 1.0);
         const endFrac = Math.min((endKm || (startKm + 5)) / 1000, 1.0);
         
         const latDiff = baseLine[1][0] - baseLine[0][0];
         const lngDiff = baseLine[1][1] - baseLine[0][1];

         return [
             [baseLine[0][0] + (latDiff * startFrac), baseLine[0][1] + (lngDiff * startFrac)],
             [baseLine[0][0] + (latDiff * endFrac), baseLine[0][1] + (lngDiff * endFrac)]
         ];
     };
     ```
   - Render the baselines in gray `color="#555" weight={2}`.
   - Render the blocks on top using `getBlockSegment(b.corridor_id, b.start_km, b.end_km)`.
   - Color blocks by severity: `EMERGENCY: "#e53935", HIGH: "#fb8c00", MEDIUM: "#fdd835", LOW: "#43a047"`.
   - Make it interactive (Popup with block details).

2. **Update `frontend/src/pages/Dashboard.jsx`**
   - Add the `NetworkMap` component prominently at the top of the dashboard.
   - Fetch the block data using `api.get('/map/blocks?plan_id=' + latestPlanId)`.

3. **CSS classes**
   - Ensure the map container has a height defined (e.g. `height: 500px, width: 100%`).
   - Import `leaflet/dist/leaflet.css`.
