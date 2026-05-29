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

- **`Sidebar`** — file upload, simulation params, antenna sector config (compass rose + azimuth inputs), channel bandwidth selector
- **`CompassRose`** — draggable SVG sector wedges with live azimuth sync to the map
- **`MapInner`** — Leaflet map with coverage heatmap overlay, sector wedge polygons, BTS/CPE markers
- **`CpeTable`** — per-CPE link analysis with Sector column and Gap ⚠ detection
- **`ResultsBanner`** — simulation outcome summary + PDF report download

## Building for production (Firebase Hosting)

```bash
npm run build        # outputs to /out (static export)
firebase deploy --only hosting
```

See `DEPLOYMENT.md` at the repo root for the full Cloud Run + Firebase flow.
