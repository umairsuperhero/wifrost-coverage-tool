# WiFrost Frontend — CLAUDE.md

## Key facts for Claude Code

- **Framework**: Next.js 16 with Turbopack dev server
- **React**: 19.x — do NOT add packages requiring React 18
- **API base**: `process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000"` — defined as `API_BASE` constant at the top of each file that makes API calls
- **Map**: react-leaflet 5 + Leaflet 1.x — all map components must be inside `dynamic(() => import(...), { ssr: false })` to avoid `window` errors during SSR
- **Styling**: Tailwind CSS 4 — utility classes only, no custom CSS files beyond `globals.css`
- **No `@tremor/react`** — removed; it requires React 18

## State flow

```
Sidebar (sector state, params)
  └─ onSectorChange(azimuths, hpbw) → page.tsx [liveSector state]
  └─ onSimulate(params) → page.tsx → API calls
       └─ simulationResults, cpeResults → MapView, CpeTable, ResultsBanner
page.tsx passes liveSector → MapView → MapInner (live wedge polygons)
```

## Sector wedge rendering

`MapInner.tsx::sectorPolygon()` converts compass bearings to lat/lon offsets:
- `dLat = (r / 111.32) * cos(bearing_rad)` — North component
- `dLon = (r / (111.32 * cos(btsLat_rad))) * sin(bearing_rad)` — East component

Correct for compass bearings (0° = North, clockwise). Do not change to SVG angle convention.

## CompassRose SVG

All computed SVG coordinate attributes **must** be rounded to 2 decimal places using the `r2()` helper (`Math.round(n * 100) / 100`). This prevents SSR/client hydration mismatches from floating-point precision differences.

Do not add local variables named `r2` inside the component — the name is reserved for the rounding helper.

## Channel bandwidth → sensitivity formula

```
sensitivity_dBm = -174 + 10*log10(BW_Hz) + NF_dB + SNR_min_dB
```
Where NF = 8 dB, SNR_min = 3 dB. Values in `BW_SENSITIVITY` constant in `Sidebar.tsx`.

## Running

```bash
npm install --legacy-peer-deps   # first time
npm run dev -- --port 3001
```
