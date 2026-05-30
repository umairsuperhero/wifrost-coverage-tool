# WiFrost TVWS Coverage Tool

A professional RF coverage planning tool for **TV White Space (TVWS)** wireless networks. Upload a site layout (KMZ, KML, or Excel), configure your WiFrost BTS equipment, and get instant signal heatmaps, link budgets, CPE analysis, terrain elevation profiles, and PDF reports.

Built for WiFrost's TVWS deployments in Latin America, but fully general-purpose for any sub-1 GHz wireless planning scenario.

---

## Features

- **Coverage heatmap** — Okumura-Hata propagation over real SRTM terrain data (or flat-earth mode)
- **Sector antenna modelling** — 1/2/3 configurable sectors with live compass rose, per-sector azimuth, HPBW, VPBW, and front-to-back ratio
- **Live sector wedge preview** — dotted sector outlines on the map update instantly as you adjust azimuth (no re-simulation needed)
- **CPE link budget analysis** — per-client RSSI, margin, path loss, and best-serving sector
- **Terrain elevation profiles** — Fresnel zone cross-section chart for any BTS→CPE path
- **Three scenario view** — Best / Realistic / Conservative coverage toggle, map filters in real time
- **Simulation history** — SQLite-backed run history with reload, compare, and delete
- **PDF reports** — professional link budget reports with heatmap image and terrain cross-section
- **AI interpreter** — ask questions in English or Spanish; powered by Google Gemini with keyword fallback
- **Dark map UI** — Next.js 16 + Tailwind CSS 4 + React-Leaflet on CartoDB Dark Matter tiles

---

## Architecture

```
wifrost-coverage-tool/
├── api.py                  # FastAPI backend — all REST endpoints
├── propagation.py          # Okumura-Hata & two-ray path loss models
├── heatmap.py              # Vectorised NumPy coverage grid computation
├── terrain.py              # SRTM elevation fetch & bilinear interpolation
├── excel_parser.py         # .xlsx site layout parser
├── kml_parser.py           # KMZ / KML site layout parser
├── report.py               # ReportLab PDF generator
├── db.py                   # SQLite simulation history (WAL mode)
├── ai_interpreter.py       # Google Gemini AI question parser
├── wifi_frost_defaults.py  # WiFrost equipment factory defaults
├── simulation_history.py   # History helpers
├── requirements.txt        # Python dependencies
├── run.sh / run.bat        # One-click launchers (Mac/Windows)
└── frontend/               # Next.js React frontend
    ├── app/
    │   ├── page.tsx        # Root page — state orchestration
    │   └── layout.tsx
    └── components/
        ├── Sidebar.tsx     # Parameters panel + file upload
        ├── MapView.tsx     # SSR-safe Leaflet wrapper
        ├── MapInner.tsx    # Leaflet map, markers, heatmap, sector wedges
        ├── CompassRose.tsx # Draggable SVG compass rose
        ├── CpeTable.tsx    # CPE link budget results table
        ├── TerrainChart.tsx# Fresnel elevation profile chart
        ├── ResultsBanner.tsx # Coverage summary + PDF download
        ├── MetricsRow.tsx  # Three-scenario KPI cards
        ├── ModelInfoPanel.tsx # Propagation theory reference
        └── HistoryPanel.tsx   # Simulation history browser
```

---

## Quick Start

### Prerequisites

- **Python 3.10+**
- **Node.js 18+** and **npm**
- An [OpenTopography API key](https://opentopography.org/developers) (free) for real terrain data
- *(Optional)* A [Google Gemini API key](https://aistudio.google.com/app/apikey) for the AI question interpreter

### 1. Clone the repository

```bash
git clone https://github.com/umairsuperhero/wifrost-coverage-tool.git
cd wifrost-coverage-tool
git checkout v2.0-react-frontend
```

### 2. Configure environment

Copy the example env file and fill in your keys:

```bash
cp .env.example .env          # if present, or create .env manually
```

Create a `.env` file in the project root:

```env
OPENTOPOGRAPHY_API_KEY=your_key_here
GEMINI_API_KEY=your_key_here          # optional
```

### 3. Run (one command)

**macOS / Linux:**
```bash
chmod +x run.sh && ./run.sh
```

**Windows:**
```
run.bat
```

The script installs Python dependencies, installs frontend packages, starts the FastAPI backend on port **8000**, and starts the Next.js frontend on port **3000**. Your browser opens automatically.

### 4. Manual start (advanced)

```bash
# Terminal 1 — backend
pip install -r requirements.txt
uvicorn api:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2 — frontend
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

---

## Docker

```bash
docker compose up --build
```

- Backend: `http://localhost:8000`
- Frontend: `http://localhost:3000`

---

## Input File Formats

### KMZ / KML
Google Earth project files. Placemarks are auto-classified as BTS candidates if their name contains keywords like `hotel`, `edificio`, `pacific`, `trade`, `cafe`, `torre`, or `bts`. All other placemarks are treated as CPE client sites.

### Excel (.xlsx)

| Column      | Description                         |
|-------------|-------------------------------------|
| `Site Name` | Unique site identifier              |
| `Latitude`  | Decimal degrees                     |
| `Longitude` | Decimal degrees                     |
| `Height_m`  | Antenna height above ground (metres)|
| `Type`      | `BTS` or `CPE`                      |

A pre-formatted template is available in `sample_data/sites_template.xlsx`.

---

## Propagation Model

The tool implements **Okumura-Hata** path loss (150–1500 MHz) with:

- Real SRTM 30m terrain elevation from [OpenTopography](https://opentopography.org/)
- Effective BTS height correction over terrain profile
- Clutter loss per environment class (Open, Suburban, Urban, Dense Vegetation, etc.)
- Location variability margin (shadowing standard deviation ≈ 8 dB)
- Deygout diffraction loss for obstructed paths
- Sectorized antenna pattern gain (parabolic horizontal + cosine vertical model)

**Flat-earth mode** uses standard Hata formulas with no terrain correction — useful for rapid estimates or when terrain data is unavailable.

---

## API Reference

The FastAPI backend exposes these endpoints:

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/parse-file` | Parse KMZ/KML/Excel site layout |
| `POST` | `/api/simulate` | Run coverage heatmap simulation |
| `POST` | `/api/cpe-analysis` | Run per-CPE link budget analysis |
| `POST` | `/api/terrain-profile` | Fetch BTS→CPE elevation profile |
| `GET`  | `/api/defaults` | WiFrost equipment factory defaults |
| `GET`  | `/api/history` | List simulation history |
| `GET`  | `/api/history/{run_id}` | Get a historical run |
| `DELETE` | `/api/history/{run_id}` | Delete a historical run |
| `POST` | `/api/history/{run_id}/pdf` | Download PDF report for a run |

Interactive docs at [http://localhost:8000/docs](http://localhost:8000/docs).

---

## License

[MIT License](LICENSE) — free to use, modify, and distribute.

---

## Contributing

Pull requests welcome. Please open an issue first to discuss significant changes.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Commit your changes
4. Open a pull request against `v2.0-react-frontend`

---

## Credits

Built with [FastAPI](https://fastapi.tiangolo.com/), [Next.js](https://nextjs.org/), [React-Leaflet](https://react-leaflet.js.org/), [Tailwind CSS](https://tailwindcss.com/), [ReportLab](https://www.reportlab.com/), and [OpenTopography](https://opentopography.org/) SRTM data.

WiFrost TVWS equipment specifications from the [WiFrost TVWS Datasheet 2022](WiFrost%20TVWS%20Datasheet%20-%202022.pdf).
