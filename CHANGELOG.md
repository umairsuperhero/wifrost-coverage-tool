# Changelog

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
