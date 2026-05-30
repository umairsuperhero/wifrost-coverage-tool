# Changelog

## [1.6.0] — 2026-05-30

### Added
- **`db.py`** — SQLite-backed simulation history (`data/wifrost.db`); UUID keys, WAL
  mode, MAX_HISTORY=20 auto-trim via `save_run / list_runs / get_run / delete_run`
- **`HistoryPanel.tsx`** — sidebar History tab; shows recent runs with coverage %,
  max range, RSSI; refresh, delete, and reload-into-map buttons
- **Terrain profile in PDF** — `build_pdf_terrain_profile_drawing()` in `report.py`
  renders a vector cross-section with 1st Fresnel zone band, terrain fill, LoS
  line, BTS/CPE antenna poles, and elevation/distance grid; embedded in CPE section
- **`NumberedCanvas`** in `report.py` — "Page X of Y" footer via two-pass rendering
- **`get_elevation_np()`** in `terrain.py` — vectorized bilinear elevation lookup
  accepting NumPy arrays of lats/lons; used by vectorized coverage grid
- History REST endpoints: `GET /api/history`, `GET /api/history/{run_id}`,
  `DELETE /api/history/{run_id}`, `POST /api/history/{run_id}/pdf`
- `history_id` field returned in `/api/simulate` response
- `terrain_loaded` flag returned in simulate and CPE analysis responses
- **Next.js dev proxy** in `next.config.ts` — `/api/*` rewrites to
  `http://127.0.0.1:8000` in dev mode; eliminates CORS friction during development
- **`Tooltip` component** in `Sidebar.tsx` with hover popover for parameter help text
- **Active scenario selector** — clicking a MetricsRow scenario card switches the
  active scenario and updates the map threshold in real time (no re-simulation)
- **GeoJSON client-side filter** in `MapInner.tsx` — map filters by `activeThreshold`
  so scenario switching is instant
- `docker-compose.yml` and `frontend/Dockerfile` for containerised deployment
- **`test_propagation_model.py`** — unit tests for propagation model
- `defusedxml==0.7.1` in `requirements.txt`
- CORS origins extended to include port 3002
- `run.sh` / `run.bat` rewritten for FastAPI + Next.js stack (Streamlit removed)

### Changed
- **`compute_coverage_grid()`** in `heatmap.py` — Python double-loop replaced with
  fully vectorised NumPy operations: `haversine_distance_np`, `bearing_np`,
  `sector_gain_np`, `get_sector_gain_for_point_np`, `deygout_loss_np`; Okumura-Hata
  and two-ray models evaluated element-wise; elevation profiles fetched in one
  `get_elevation_np` batch call; max-range computation vectorised
- **`PathLossResult.total_db`** now includes `clutter_db` (previously omitted —
  underestimated total path loss by up to 10 dB in dense environments)
- **`terrain_aware_loss()`** `hb_eff` lower clamp relaxed 30 m → 10 m (supports
  low-mounted or near-ground CPE installations)
- **Coverage map** in PDF now preserves image aspect ratio (was stretched to fixed
  390×293 px regardless of grid shape)
- **GeoJSON threshold** in `/api/simulate` changed from `thresh_real` → `thresh_best`
  so the frontend can filter dynamically per scenario without re-querying
- **`kml_parser.py`** — `ET.fromstring()` replaced with `defusedxml.fromstring()`
- Sidebar `environment` is now a controlled React state variable

### Fixed
- **`ai_interpreter.py`** — `genai.configure()` wrapped in `threading.Lock` to
  prevent race conditions when multiple requests configure the Gemini client
  concurrently
- **`shadowing_margin()`** — guard for `coverage_probability < 0.50` (previously
  returned an undefined large negative margin)
- **`terrain_aware_loss()`** — `warnings.warn` added when frequency is outside
  Okumura-Hata validity range (150–1500 MHz)
- **`fetch_srtm()`** — 1-retry on network timeout (10 s backoff); `np.loadtxt()`
  replaces slow per-line Python parsing
- **`get_elevation()`** — boundary check `>= ncols-1` → `> ncols-1` to include
  terrain edge cells
- **`compute_cpe_analysis()`** — `'d_km' in dir()` → `'d_km' in locals()` (was
  always `False`, silently zeroing distances on exception path)
- **`ResultsBanner.tsx`** — PDF download errors now surface via toast notification
  instead of a blocking `alert()`

## [1.5.0] — 2026-05-29

### Added
- **Channel bandwidth selector** in CPE Config — 6 / 12 / 18 / 24 MHz buttons
  auto-compute Rx sensitivity via `kTB + 8 dB NF + 3 dB SNR`:
  6 MHz = −95 dBm · 12 MHz = −92 dBm (default) · 18 MHz = −90 dBm · 24 MHz = −89 dBm
- **PDF coverage image** now includes corner lat/lon labels, north arrow (▲N),
  and a "RF Coverage Model — schematic" watermark

### Changed
- **Map height** `h-[45%]` → `h-[60%]` with `min-h-[360px]`
- **Sector wedges live-sync** — `onSectorChange` callback lifts sector state to
  `page.tsx`; wedges update instantly when the user moves the compass rose or
  types an azimuth, without requiring a re-simulation

### Fixed
- `r2 is not a function` crash in CompassRose — `const r2 = tickOuter` shadowed
  the `r2()` rounding helper inside the tick-mark map; removed the local alias
- CompassRose SVG hydration mismatch — `Math.sin`/`Math.cos` differ in last digit
  between SSR and client; all computed SVG coordinate attributes rounded to 2 dp
- `@tremor/react` removed — requires React 18, project uses React 19, unused

## [1.4.0] — 2026-05-28

### Added
- **CompassRose.tsx** — reusable SVG compass rose component with live drag-to-rotate
  sector wedges, coverage gap warning, and ±5° azimuth snapping
- **Antenna Sectors panel** in sidebar — segmented 1/2/3 sector selector, per-sector
  azimuth inputs synced bidirectionally with the compass rose, equal-spacing
  auto-fill button, collapsible antenna pattern overrides (HPBW/VPBW/F:B)
- **Sector wedge map overlay** — dashed polygon wedges rendered on the Leaflet map
  after simulation, one per sector, using max coverage radius as radius
- **Sector column in CPE table** — shows which sector (S1/S2/S3) serves each CPE,
  color-coded; shows "Gap ⚠" in amber when best sector gain < −20 dB
- **Sector params in API** — `SimulateRequest` and `CpeAnalysisRequest` now accept
  `sector_azimuths`, `hpbw_deg`, `vpbw_deg`, `front_to_back_db`; sector gain
  included in CPE RSSI calculation; `best_sector` and `best_sector_gain_db` returned
  per CPE result; `/api/defaults` returns `front_to_back_ratio`

### Changed
- **WifrostBTS defaults**: `beamwidth_h_deg` 90° → 65°, `beamwidth_v_deg` 15° → 17°,
  `horizontal_beamwidth` 90° → 65°, `default_sectors` 3 → 1, `sector_azimuths`
  [0,120,240] → [0] (single sector default; 65°×3 = 195° — not full 360°)

### Notes
- `sector_gain(90°, az=0, hpbw=65, ftb=25)` = **−23.0 dB** (not −25 dB): the
  parabolic model cap at −25 dB isn't reached until ~92° off-axis with 65° HPBW.
  This is correct behavior, not a bug.

## [1.2.0] — 2026-05-27

### Fixed
- **#1** — Updated `extract_equipment_params` model from `gemini-1.5-pro` to `gemini-3.1-pro`
- **#2** — Updated `interpret_question` and `generate_recommendation` models from
  `gemini-1.5-flash` to `gemini-3.5-flash`; moved `system_instruction` into the
  model constructor (correct API usage) and simplified `generate_content` call
- **#3** — Added `requirements.txt` (missing from repo); pinned all packages with
  `==` for reproducibility; added `branca==0.8.2` explicitly
- **#4** — Expanded `heuristic_interpret_question()` with full Colombian Spanish
  vocabulary: port/industrial, water, frequency-sweep, compare, and report
  keywords; improved action-detection order and plain-English task strings
- **#5** — Updated all package versions to latest stable releases compatible with
  `numpy==1.26.4` (see inline comments in `requirements.txt`)
- **#6** — Added `pointer-events: none` to `.legend-bar` CSS so the signal-quality
  legend no longer blocks map click/zoom interactions in Firefox
- **#7** — Added `_gemini_call_with_retry()` helper with exponential backoff (1 s /
  2 s / 4 s) that retries on 429, 503, ResourceExhausted, quota, and
  rate-limit errors; applied to all three Gemini call sites

## [1.1.0] — 2025-04-01

### Added
- Sectorized antenna support
- CPE link analysis
- Simulation history panel
- AI recommendations (bilingual)
- Site comparison ("compare all") mode
- Terrain elevation profiles
