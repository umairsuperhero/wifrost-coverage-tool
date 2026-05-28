# Changelog

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
