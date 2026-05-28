# WiFrost Coverage Tool — CLAUDE.md

## Project overview

WiFrost is a Streamlit-based TVWS (TV White Space) coverage planning tool.
Marcelo, a sales engineer, uses it to simulate radio propagation, compare BTS
sites, generate link-budget reports, and get AI-powered recommendations.

## Architecture

| File | Role |
|---|---|
| `app.py` | Streamlit UI — all pages and layout |
| `ai_interpreter.py` | Gemini API calls: PDF parsing, question interpretation, recommendations |
| `propagation.py` | ITM / flat-Earth RF propagation models |
| `heatmap.py` | Coverage grid computation and CPE analysis |
| `terrain.py` | SRTM tile fetch and interpolation |
| `kml_parser.py` | KMZ/KML site ingestion |
| `excel_parser.py` | Excel site-list ingestion |
| `report.py` | ReportLab PDF generation |
| `simulation_history.py` | JSON-backed run history |
| `wifi_frost_defaults.py` | Equipment/scenario default values |

## Running the app

```bash
source venv/bin/activate
streamlit run app.py
```

## Dependencies

See `requirements.txt`. Key constraints:
- `numpy==1.26.4` pinned — NumPy 2.0 has untested breaking changes.
- `scipy==1.13.1` — last release compatible with numpy <2.0.
- `pandas==2.2.3` — last of 2.2.x, confirmed numpy 1.x compatible.

## AI / Gemini notes

`ai_interpreter.py` uses `google-generativeai` (legacy SDK).
Models as of v1.2.0:
- `gemini-3.1-pro` — multimodal PDF datasheet extraction
- `gemini-3.5-flash` — question interpretation and bilingual recommendations

All Gemini calls go through `_gemini_call_with_retry()` (3 attempts,
exponential backoff on 429 / 503 / ResourceExhausted).

## Version

Current: **v1.2.0**
