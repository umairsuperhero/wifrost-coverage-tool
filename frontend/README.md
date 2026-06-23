# WiFrost Frontend — Next.js 16

React/TypeScript frontend for the WiFrost TVWS RF Coverage Planning Tool.
Communicates with the FastAPI backend at `http://localhost:8000` (or `NEXT_PUBLIC_API_URL`).

## Quick start

```bash
npm install --legacy-peer-deps
npm run dev -- --port 3001
```

Open **http://localhost:3001**. The FastAPI backend must be running on port 8000 first.

## Environment

```bash
# frontend/.env.local
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000        # local dev
# NEXT_PUBLIC_API_URL=https://your-cloud-run-url  # production
```

See `frontend/.env.example` for the template.

## Stack

| Package | Purpose |
|---|---|
| Next.js 16 (Turbopack) | Framework, SSR + static export |
| React 19 | UI |
| Tailwind CSS 4 | Styling |
| react-leaflet 5 | Interactive map |
| axios | HTTP client |
| lucide-react | Icons |

## Key components

- **`Sidebar`** — file upload, parameters, antenna sector configuration (compass rose + live azimuth sync), and clutter / terrain loaded status indicators.
- **`CompassRose`** — draggable SVG compass sectors with reactive azimuth angle callbacks.
- **`MapInner`** — Leaflet overlay mapping with dynamic sliding legend offset, sector wedges, and path-loss heatmaps.
- **`CpeSummaryBar`** — Pass/marginal/fail client link margin reliability progress indicators.
- **`CpeTable`** — client link budgets styled as a list of selectable compact cards.
- **`TerrainChart`** — Fresnel clearance path elevation SVG chart with full-size center modal backdrop overlay.
- **`LinkBudget`** — transparent FWA path-loss math breakdown.
- **`ResultsBanner`** — outcome description and base64-compiled ReportLab PDF report generation.

## Building for production (Vercel)

```bash
npm run build        # compiles and verifies Next.js application
npx vercel --prod    # deploys optimized build to Vercel production
```

See the root **[DEPLOYMENT.md](file:///Users/umairqayyum/Documents/Software/Anti-Gravity/WiFrost%20Propagation/wifrost-coverage-tool/DEPLOYMENT.md)** for full reproduction steps and environment configurations.
