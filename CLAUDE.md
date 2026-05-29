# WiFrost Coverage Tool — CLAUDE.md

## Architecture

WiFrost v2.0 is a **FastAPI backend + Next.js 16 frontend** TVWS RF coverage planning tool.
The original Streamlit app lives on `main` (v1.2.0). This branch (`v2.0-react-frontend`) is the production path.

### Backend (`/` — Python)

| File | Role |
|---|---|
| `api.py` | FastAPI app — 6 REST endpoints, in-memory simulation cache |
| `propagation.py` | Okumura-Hata path loss, Deygout diffraction, sector gain math |
| `heatmap.py` | Coverage grid (100 m resolution), CPE analysis, GeoJSON export, PNG for PDF |
| `terrain.py` | SRTM tile fetch via OpenTopography API, bilinear interpolation, disk cache |
| `report.py` | 3-page ReportLab PDF: business overview / CPE table / link budget |
| `ai_interpreter.py` | Gemini API: PDF datasheet extraction, question interpretation, recommendations |
| `kml_parser.py` | KMZ/KML ingestion → site objects |
| `excel_parser.py` | Excel/CSV site-list ingestion |
| `wifi_frost_defaults.py` | `WifrostBTS` / `WifrostCPE` dataclasses with defaults |

### Frontend (`frontend/` — TypeScript / Next.js 16)

| Component | Role |
|---|---|
| `app/page.tsx` | Root page — state orchestration, API calls, layout |
| `components/Sidebar.tsx` | File upload, simulation params, antenna sectors panel, channel BW |
| `components/CompassRose.tsx` | SVG compass rose with draggable sector wedges |
| `components/MapView.tsx` + `MapInner.tsx` | Leaflet map, coverage GeoJSON, sector wedge polygons |
| `components/CpeTable.tsx` | CPE link analysis table with Sector column |
| `components/TerrainChart.tsx` | Terrain elevation cross-section |
| `components/ResultsBanner.tsx` | Simulation outcome + PDF download trigger |
| `components/MetricsRow.tsx` | Best / Realistic / Conservative scenario cards |
| `components/ModelInfoPanel.tsx` | Propagation theory reference panel |

## Running locally

```bash
# Backend (Terminal 1)
cd <project-dir>
python3 -m venv venv && venv/bin/pip install -r requirements.txt
venv/bin/python3 -m uvicorn api:app --reload --port 8000

# Frontend (Terminal 2)
cd <project-dir>/frontend
npm install --legacy-peer-deps
npm run dev -- --port 3001
```

Open **http://localhost:3001**. Backend must be on 8000 (CORS allows 3000/3001/8000).

## Key design decisions

- **Sector state lifted to `page.tsx`** via `onSectorChange` — map wedges update live as the user adjusts the compass rose, no re-simulation needed.
- **`PathLossResult` class** stores base + diffraction + clutter separately so three-scenario margins apply without re-running propagation.
- **In-memory simulation cache** in `api.py` keyed by MD5 of params — PDF reuses the last grid instead of re-simulating.
- **Flat-terrain fallback** — if OpenTopography key is absent, `terrain.py` returns `is_flat=True`; diffraction is skipped and the UI shows a notice.
- **Channel bandwidth → Rx sensitivity** auto-computed in Sidebar: `kTB + 8 dB NF + 3 dB SNR` (6 MHz = −95 dBm, 12 MHz = −92 dBm default, 18 = −90, 24 = −89).

## API endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/defaults` | WifrostBTS + WifrostCPE default params |
| POST | `/api/parse-file` | Parse KMZ/KML/Excel → site list |
| POST | `/api/simulate` | Coverage grid + 3-scenario stats + GeoJSON |
| POST | `/api/cpe-analysis` | Per-CPE link budget with sector gain |
| POST | `/api/generate-report` | Base64-encoded 3-page PDF |
| POST | `/api/terrain-profile` | SRTM elevation cross-section |

## Environment variables

```
OPENTOPOGRAPHY_API_KEY=...               # root .env
GEMINI_API_KEY=...                        # root .env
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000   # frontend/.env.local
CORS_ORIGINS=...                          # optional comma-separated override
```

## Dependencies (key constraints)

- `numpy==1.26.4` pinned — NumPy 2.0 has untested breaking changes
- `scipy==1.13.1` — last release compatible with numpy <2.0
- `pandas==2.2.3` — last of 2.2.x, confirmed numpy 1.x compatible
- React 19.x — `@tremor/react` removed (requires React 18, unused in codebase)

## AI / Gemini

`ai_interpreter.py` uses `google-generativeai` (legacy SDK, deprecation warning is cosmetic).
- `gemini-3.1-pro` — multimodal PDF datasheet extraction
- `gemini-3.5-flash` — question interpretation and bilingual recommendations
- All calls go through `_gemini_call_with_retry()` (3 attempts, exponential backoff)

## Version

Current branch: **v2.0-react-frontend** — v1.5.0
Stable Streamlit app: **main** — v1.2.0
