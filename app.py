import os
import math
import json
import datetime
import shutil
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO

import numpy as np
import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium
from dotenv import load_dotenv
import plotly.graph_objects as go

from wifi_frost_defaults import WifrostBTS, WifrostCPE
from kml_parser import parse_kml_or_kmz, KMLData, KMLPoint
from excel_parser import parse_excel_sites, generate_excel_template
from terrain import fetch_srtm, get_elevation, get_profile, haversine_distance, build_terrain_profile_figure
from propagation import (compute_eirp, compute_rssi, okumura_hata, terrain_aware_loss,
                          bearing, sector_gain, get_sector_gain_for_point, best_sector_for_point)
from heatmap import (compute_coverage_grid, coverage_to_geojson, compute_cpe_analysis,
                      coverage_to_image, cpe_status, cpe_marker_color, cpe_line_color)
from ai_interpreter import interpret_question, extract_equipment_params, generate_recommendation
from report import generate_pdf_report
from simulation_history import save_simulation, load_history

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="WiFrost TVWS Coverage Planner",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Outfit', sans-serif; }
.main-header {
    background: linear-gradient(135deg,#1B365D 0%,#102A45 100%);
    padding:20px 25px; border-radius:12px; color:white;
    margin-bottom:25px; box-shadow:0 4px 15px rgba(0,0,0,.1);
    display:flex; align-items:center; justify-content:space-between;
}
.main-header h1 { margin:0; font-size:28px; font-weight:700; letter-spacing:-.5px; }
.main-header p  { margin:5px 0 0 0; font-size:14px; opacity:.8; }
.banner-success {
    background:#d4edda; border-left:6px solid #28a745; color:#155724;
    padding:15px 20px; border-radius:6px; margin-bottom:20px;
    font-weight:600; font-size:16px;
}
.banner-warning {
    background:#fff3cd; border-left:6px solid #ffc107; color:#856404;
    padding:15px 20px; border-radius:6px; margin-bottom:20px;
    font-weight:600; font-size:16px;
}
.kpi-container { display:flex; justify-content:space-between; gap:15px; margin-bottom:20px; }
.kpi-card {
    background:#fff; border:1px solid #dfe1e6; border-radius:8px;
    padding:15px; flex:1; text-align:center;
    box-shadow:0 2px 6px rgba(9,30,66,.08); transition:transform .2s;
}
.kpi-card:hover { transform:translateY(-2px); box-shadow:0 4px 12px rgba(9,30,66,.12); }
.kpi-title { font-size:12px; color:#6b778c; font-weight:600; text-transform:uppercase;
             margin-bottom:8px; letter-spacing:.5px; }
.kpi-value { font-size:24px; color:#1b365d; font-weight:700; }
.legend-container {
    background:white; padding:10px 15px; border-radius:6px;
    border:1px solid #dfe1e6; display:flex; align-items:center;
    gap:20px; margin-top:10px; margin-bottom:20px;
}
.legend-item { display:flex; align-items:center; gap:6px; font-size:13px; font-weight:500; }
.legend-dot  { width:12px; height:12px; border-radius:3px; }
.summary-bar {
    background:#f4f5f7; border-radius:8px; padding:12px 18px;
    font-size:14px; font-weight:600; color:#1B365D; margin-bottom:12px;
}
.rec-card {
    background:#eaf4fb; border-left:5px solid #2980b9; border-radius:8px;
    padding:16px 20px; margin-top:12px;
}
.hist-card {
    background:#fff; border:1px solid #dfe1e6; border-radius:8px;
    padding:10px 14px; margin-bottom:8px; cursor:pointer;
}
</style>
""", unsafe_allow_html=True)

# ── Directories & .env ────────────────────────────────────────────────────────

_BASE = os.path.dirname(os.path.abspath(__file__))
sample_dir = os.path.join(_BASE, "sample_data")
cache_dir  = os.path.join(_BASE, "cache")
sim_dir    = os.path.join(_BASE, "simulations")
for _d in (sample_dir, cache_dir, sim_dir):
    os.makedirs(_d, exist_ok=True)

try:
    generate_excel_template(sample_dir)
except Exception:
    pass

env_path = os.path.join(_BASE, ".env")
if os.path.exists(env_path):
    load_dotenv(env_path)
else:
    load_dotenv()

# ── Session state defaults ────────────────────────────────────────────────────

_DEFAULTS = {
    'bts_specs': WifrostBTS(),
    'cpe_specs': WifrostCPE(),
    'custom_datasheet_nulls': [],
    'history': [],
    'mode': 'coverage',          # 'coverage' | 'cpe_analysis'
    'simulation_run': False,
    'active_coverage_grid': None,
    'cpe_results': None,
    'all_compares': None,
    'active_bts_index': 0,
    'sim_frequency': 570.0,
    'sim_model': 'terrain_aware',
    'sim_env': 'open',
    'sim_bts_height': 30.0,
    'selected_cpe_name': None,
    'ai_recommendation': None,
    'loaded_past': None,
}
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# Load persisted history on first run
if not st.session_state.history:
    try:
        st.session_state.history = load_history(_BASE)
    except Exception:
        pass

# ── Helpers ───────────────────────────────────────────────────────────────────

def save_keys(ot_key: str, gemini_key: str):
    try:
        with open(env_path, "w") as f:
            f.write(f"OPENTOPOGRAPHY_API_KEY={ot_key.strip()}\n")
            f.write(f"GEMINI_API_KEY={gemini_key.strip()}\n")
        st.sidebar.success("🔑 API Keys saved.")
    except Exception as e:
        st.sidebar.error(f"Could not save keys: {e}")


def make_sector_polygon(lat, lon, azimuth_deg, hpbw_deg, radius_km=2.5, n_pts=30):
    """Return [[lat, lon], ...] polygon for a sector wedge."""
    points = [[lat, lon]]
    start = azimuth_deg - hpbw_deg / 2
    end   = azimuth_deg + hpbw_deg / 2
    for i in range(n_pts + 1):
        angle = math.radians(start + (end - start) * i / n_pts)
        dlat = radius_km * math.cos(angle) / 111.32
        dlon = radius_km * math.sin(angle) / (111.32 * math.cos(math.radians(lat)))
        points.append([lat + dlat, lon + dlon])
    points.append([lat, lon])
    return points


def _sector_colors():
    return ["#e74c3c", "#3498db", "#2ecc71"]


def build_cpe_excel(cpe_results, bts_name, frequency_mhz, model_name, env_name) -> bytes:
    """Generate 3-sheet Excel for CPE results."""
    df = pd.DataFrame([{
        "Name": r["name"],
        "Distance (km)": r["distance_km"],
        "Bearing (°)": r["bearing_deg"],
        "Best Sector": r["best_sector"] + 1,
        "Sector Gain (dB)": r["sector_gain_db"],
        "Path Loss (dB)": r["path_loss_db"],
        "RSSI (dBm)": r["rssi_dbm"],
        "Link Margin (dB)": r["link_margin_db"],
        "LoS / Fresnel": r["fresnel_clearance"],
        "Status": r["status"],
    } for r in cpe_results])

    counts = {"🟢 Excellent": 0, "🟡 Good": 0, "🟠 Marginal": 0,
              "🔴 Weak": 0, "⛔ No Link": 0}
    for r in cpe_results:
        s = r["status"]
        if s in counts:
            counts[s] += 1
    total = len(cpe_results)
    covered = sum(v for k, v in counts.items() if k != "⛔ No Link")
    df_sum = pd.DataFrame([
        {"Metric": "BTS Site", "Value": bts_name},
        {"Metric": "Frequency (MHz)", "Value": frequency_mhz},
        {"Metric": "Model", "Value": model_name},
        {"Metric": "Environment", "Value": env_name},
        {"Metric": "Total CPE Sites", "Value": total},
        {"Metric": "Covered Sites", "Value": covered},
        {"Metric": "Coverage %", "Value": f"{100*covered/max(total,1):.1f}%"},
    ] + [{"Metric": k, "Value": v} for k, v in counts.items()])

    df_budget = pd.DataFrame([{
        "Name": r["name"],
        "EIRP (dBm)": round(r["path_loss_db"] + r["rssi_dbm"] - r["sector_gain_db"], 1),
        "Path Loss (dB)": r["path_loss_db"],
        "Sector Gain (dB)": r["sector_gain_db"],
        "RSSI (dBm)": r["rssi_dbm"],
        "Link Margin (dB)": r["link_margin_db"],
        "Fresnel / LoS": r["fresnel_clearance"],
    } for r in cpe_results])

    buf = BytesIO()
    with pd.ExcelWriter(buf, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='CPE Coverage Results', index=False)
        df_sum.to_excel(writer, sheet_name='Summary Statistics', index=False)
        df_budget.to_excel(writer, sheet_name='Link Budget Details', index=False)
    return buf.getvalue()

# ── Sidebar ───────────────────────────────────────────────────────────────────

st.sidebar.markdown("<h2 style='color:#1B365D;margin-top:0;'>📡 WiFrost Tool Settings</h2>",
                    unsafe_allow_html=True)

# API Keys
with st.sidebar.expander("🔑 API Keys Setup", expanded=False):
    st.caption("Saved to local .env file — enter once.")
    ot_key_val  = os.getenv("OPENTOPOGRAPHY_API_KEY", "")
    gem_key_val = os.getenv("GEMINI_API_KEY", "")
    ot_key_in  = st.text_input("OpenTopography API Key", value=ot_key_val,
                                type="password", key="ot_key_input")
    gem_key_in = st.text_input("Gemini API Key", value=gem_key_val,
                                type="password", key="gem_key_input")
    if st.button("Save API Keys", use_container_width=True):
        save_keys(ot_key_in, gem_key_in)
        load_dotenv(env_path, override=True)

ot_api_key     = os.getenv("OPENTOPOGRAPHY_API_KEY", "")
gemini_api_key = os.getenv("GEMINI_API_KEY", "")

# Project files
st.sidebar.markdown("### 📁 Project Files")
kmz_file  = st.sidebar.file_uploader("Drop customer KMZ / KML here", type=["kmz", "kml"])
xlsx_file = st.sidebar.file_uploader("Or drop Excel with coordinates", type=["xlsx"])

parsed_data = None
file_loaded = False
error_message = None

if kmz_file is not None:
    tmp_suffix = f".{kmz_file.name.split('.')[-1]}"
    with tempfile.NamedTemporaryFile(delete=False, suffix=tmp_suffix) as tmp:
        tmp.write(kmz_file.getvalue())
        tmp_path = tmp.name
    try:
        parsed_data = parse_kml_or_kmz(tmp_path)
        file_loaded = True
    except Exception as e:
        error_message = f"Could not read KML/KMZ: {e}"
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass

elif xlsx_file is not None:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        tmp.write(xlsx_file.getvalue())
        tmp_path = tmp.name
    try:
        parsed_data = parse_excel_sites(tmp_path)
        file_loaded = True
    except Exception as e:
        error_message = f"Could not read Excel: {e}"
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass

if file_loaded and parsed_data:
    bts_candidates = [s for s in parsed_data.sites if s.is_bts_candidate]
    st.sidebar.markdown(f"✅ **Loaded {len(parsed_data.sites)} sites**")
    st.sidebar.caption(f"Found {len(bts_candidates)} candidate BTS sites.")
elif error_message:
    st.sidebar.error(error_message)

# Equipment specs
st.sidebar.markdown("### 📡 Equipment Specifications")
equip_tabs = st.sidebar.tabs(["BTS Specs", "CPE Specs", "Upload Datasheet"])

with equip_tabs[0]:
    st.session_state.bts_specs.model_name = st.text_input(
        "BTS Model Name", value=st.session_state.bts_specs.model_name)
    st.session_state.bts_specs.tx_power_dbm = st.number_input(
        "BTS TX Power (dBm)", value=st.session_state.bts_specs.tx_power_dbm, step=1.0)
    st.session_state.bts_specs.antenna_gain_dbi = st.number_input(
        "BTS Antenna Gain (dBi)", value=st.session_state.bts_specs.antenna_gain_dbi, step=1.0)
    st.session_state.bts_specs.cable_loss_db = st.number_input(
        "BTS Cable Loss (dB)", value=st.session_state.bts_specs.cable_loss_db, step=0.1)
    st.session_state.bts_specs.receiver_sensitivity_dbm = st.number_input(
        "BTS RX Sensitivity (dBm)",
        value=st.session_state.bts_specs.receiver_sensitivity_dbm, step=1.0)

    st.markdown("**🔄 Sector Configuration**")
    preset = st.selectbox("Sector Preset",
                          ["3-sector 0/120/240°", "2-sector 0/180°", "Single omni", "Custom"],
                          key="sector_preset")
    if preset == "3-sector 0/120/240°":
        st.session_state.bts_specs.default_sectors = 3
        st.session_state.bts_specs.sector_azimuths = [0, 120, 240]
    elif preset == "2-sector 0/180°":
        st.session_state.bts_specs.default_sectors = 2
        st.session_state.bts_specs.sector_azimuths = [0, 180, 240]
    elif preset == "Single omni":
        st.session_state.bts_specs.default_sectors = 1
        st.session_state.bts_specs.sector_azimuths = [0, 120, 240]

    n_sec = st.radio("Number of sectors", [1, 2, 3],
                     index=[1,2,3].index(st.session_state.bts_specs.default_sectors),
                     horizontal=True, key="n_sectors_radio")
    st.session_state.bts_specs.default_sectors = n_sec

    for i in range(n_sec):
        default_az = st.session_state.bts_specs.sector_azimuths[i] if i < len(st.session_state.bts_specs.sector_azimuths) else i * (360 // n_sec)
        az = st.number_input(f"Sector {i+1} Azimuth (°)", min_value=0, max_value=359,
                             value=int(default_az), step=5, key=f"az_{i}")
        st.session_state.bts_specs.sector_azimuths[i] = az

    st.session_state.bts_specs.horizontal_beamwidth = st.slider(
        "Horizontal Beamwidth (°)", 60, 120,
        int(st.session_state.bts_specs.horizontal_beamwidth), 5)
    st.session_state.bts_specs.front_to_back_ratio = st.slider(
        "Front-to-Back Ratio (dB)", 20, 30,
        int(st.session_state.bts_specs.front_to_back_ratio), 1)

with equip_tabs[1]:
    st.session_state.cpe_specs.model_name = st.text_input(
        "CPE Model Name", value=st.session_state.cpe_specs.model_name)
    st.session_state.cpe_specs.tx_power_dbm = st.number_input(
        "CPE TX Power (dBm)", value=st.session_state.cpe_specs.tx_power_dbm, step=1.0)
    st.session_state.cpe_specs.antenna_gain_dbi = st.number_input(
        "CPE Antenna Gain (dBi)", value=st.session_state.cpe_specs.antenna_gain_dbi, step=1.0)
    st.session_state.cpe_specs.cable_loss_db = st.number_input(
        "CPE Cable Loss (dB)", value=st.session_state.cpe_specs.cable_loss_db, step=0.1)
    st.session_state.cpe_specs.receiver_sensitivity_dbm = st.number_input(
        "CPE RX Sensitivity (dBm)",
        value=st.session_state.cpe_specs.receiver_sensitivity_dbm, step=1.0)

with equip_tabs[2]:
    st.markdown("**Extract specs from PDF**")
    custom_pdf = st.file_uploader("Upload PDF Datasheet", type=["pdf"])
    pdf_device_type = st.selectbox("Device Type", ["BTS", "CPE"])
    if custom_pdf is not None:
        if st.button("Parse PDF Specs", use_container_width=True):
            if not gemini_api_key:
                st.error("🔑 Please set your Gemini API Key first.")
            else:
                with st.spinner("Extracting with Gemini…"):
                    try:
                        extracted = extract_equipment_params(
                            custom_pdf.getvalue(), pdf_device_type, gemini_api_key)
                        target = (st.session_state.bts_specs
                                  if pdf_device_type == "BTS"
                                  else st.session_state.cpe_specs)
                        null_fields = []
                        for k, v in extracted.items():
                            if v is None:
                                null_fields.append(k)
                            else:
                                try:
                                    setattr(target, k, v)
                                except AttributeError:
                                    pass
                        st.session_state.custom_datasheet_nulls = null_fields
                        st.rerun()
                    except Exception as e:
                        st.error(f"PDF parsing failed: {e}")

if st.sidebar.button("Reset Equipment Defaults", use_container_width=True):
    st.session_state.bts_specs = WifrostBTS()
    st.session_state.cpe_specs = WifrostCPE()
    st.session_state.custom_datasheet_nulls = []
    st.rerun()

# Analysis mode toggle
st.sidebar.markdown("### 🗺️ Analysis Mode")
mode_choice = st.sidebar.radio(
    "Select mode",
    ["🗺 Coverage Map", "📍 CPE Link Analysis"],
    index=0 if st.session_state.mode == 'coverage' else 1,
    key="mode_radio",
)
st.session_state.mode = 'coverage' if "Coverage" in mode_choice else 'cpe_analysis'

# Simulation settings
st.sidebar.markdown("### ⚙️ Simulation Settings")
freq_min = min(st.session_state.bts_specs.freq_min_mhz,
               st.session_state.cpe_specs.freq_min_mhz)
freq_max = max(st.session_state.bts_specs.freq_max_mhz,
               st.session_state.cpe_specs.freq_max_mhz)

if st.session_state.sim_frequency is None:
    st.session_state.sim_frequency = float((freq_min + freq_max) / 2)
st.session_state.sim_frequency = max(float(freq_min),
                                      min(float(freq_max),
                                          float(st.session_state.sim_frequency)))

selected_frequency = st.sidebar.slider(
    "Frequency (MHz)", float(freq_min), float(freq_max),
    value=float(st.session_state.sim_frequency), step=1.0, key="freq_slider")
st.session_state.sim_frequency = selected_frequency

model_options = ["Terrain-aware (accurate)", "Flat earth (fast)"]
model_default_idx = 1 if st.session_state.sim_model == "flat" else 0
prop_model_ui = st.sidebar.selectbox("Model", model_options,
                                      index=model_default_idx, key="model_sel")
st.session_state.sim_model = ("terrain_aware"
                               if prop_model_ui == "Terrain-aware (accurate)"
                               else "flat")
prop_model = st.session_state.sim_model

env_options = {"Open / Rural": "open", "Suburban": "suburban", "Urban": "urban"}
env_ui = st.sidebar.selectbox("Environment",
                               list(env_options.keys()), key="env_sel")
sim_env = env_options[env_ui]

resolution_ui = st.sidebar.selectbox(
    "Heatmap Spacing", ["Standard 100m", "Fine 50m", "Fast 200m"],
    key="res_sel")
resolution_val = 50.0 if "50m" in resolution_ui else (200.0 if "200m" in resolution_ui else 100.0)

# Recent simulations sidebar
with st.sidebar.expander("📋 Recent Simulations", expanded=False):
    hist_entries = st.session_state.history
    if not hist_entries:
        st.caption("No simulations saved yet.")
    else:
        for idx, entry in enumerate(hist_entries):
            label = (f"**{entry.get('bts_site', '—')}** · "
                     f"{entry.get('frequency_mhz', '?')}MHz · "
                     f"{entry.get('coverage_pct', '?')}% · "
                     f"{entry.get('timestamp', '')[:10]}")
            if st.button(label, key=f"hist_btn_{idx}", use_container_width=True):
                st.session_state.loaded_past = entry
                st.session_state.simulation_run = True
                st.rerun()

# ── BTS site list ─────────────────────────────────────────────────────────────

bts_sites = []
if file_loaded and parsed_data:
    bts_sites = [s for s in parsed_data.sites if s.is_bts_candidate]
    if not bts_sites:
        if not parsed_data.sites:
            st.error("No valid sites found in the uploaded file. Please check the format.")
            st.stop()
        parsed_data.sites[0].is_bts_candidate = True
        parsed_data.sites[0].site_type = "BTS"
        bts_sites = [parsed_data.sites[0]]

# ── Main area ─────────────────────────────────────────────────────────────────

st.markdown("""
<div class="main-header">
  <div>
    <h1>WiFrost TVWS RF Coverage Planning Tool</h1>
    <p>Interactive tool for sales planning, link budgets, and terrain profile analysis</p>
  </div>
  <div style="font-weight:700;font-size:16px;border:2px solid white;
              padding:5px 15px;border-radius:20px;">
    LATIN AMERICA TVWS RESELLER
  </div>
</div>
""", unsafe_allow_html=True)

# Welcome screen
if not file_loaded or not parsed_data:
    st.markdown("""
### 👋 Welcome, Marcelo!

Get started in 3 simple steps:
1. **Upload a KMZ/KML file** or an **Excel file** in the sidebar.
2. Check the WiFrost LT100 specs and sector configuration.
3. Choose **Coverage Map** or **CPE Link Analysis** mode, then click Run!
""")
    col_dl1, col_dl2 = st.columns(2)
    with col_dl1:
        tpl = os.path.join(sample_dir, "sites_template.xlsx")
        if os.path.exists(tpl):
            with open(tpl, "rb") as f:
                st.download_button("📄 Download Excel Template", data=f.read(),
                                   file_name="sites_template.xlsx",
                                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                   use_container_width=True)
    with col_dl2:
        kmz = os.path.join(sample_dir, "SPRBUN_TVWS.kmz")
        if os.path.exists(kmz):
            with open(kmz, "rb") as f:
                st.download_button("🌍 Download Sample KMZ", data=f.read(),
                                   file_name="SPRBUN_TVWS.kmz",
                                   mime="application/vnd.google-earth.kmz",
                                   use_container_width=True)
    st.stop()

# Extract geodata
try:
    sites    = parsed_data.sites
    polygons = parsed_data.polygons
    lines    = parsed_data.lines

    lats = [s.latitude  for s in sites]
    lons = [s.longitude for s in sites]
    for poly in polygons:
        lats.extend(c[1] for c in poly.coordinates)
        lons.extend(c[0] for c in poly.coordinates)
    for line in lines:
        lats.extend(c[1] for c in line.coordinates)
        lons.extend(c[0] for c in line.coordinates)

    if not lats or not lons:
        st.error("No geographic coordinates found in the file.")
        st.stop()

    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)
    pad_lat = 0.04
    pad_lon = 0.04 / math.cos(math.radians((min_lat + max_lat) / 2))
    proj_bounds = {"minLat": min_lat - pad_lat, "maxLat": max_lat + pad_lat,
                   "minLon": min_lon - pad_lon, "maxLon": max_lon + pad_lon}
except Exception as e:
    st.error(f"Could not process the uploaded file: {e}")
    st.stop()

# Terrain
try:
    with st.spinner("🏔 Loading elevation data…"):
        terrain_grid = fetch_srtm(proj_bounds, ot_api_key)
except Exception:
    from terrain import create_flat_terrain
    terrain_grid = create_flat_terrain(proj_bounds)

col_badge1, _ = st.columns([1, 4])
with col_badge1:
    if terrain_grid.is_flat:
        st.markdown("<span style='background:#ffe39b;color:#856404;padding:4px 10px;"
                    "border-radius:12px;font-size:12px;font-weight:600;'>"
                    "⚠️ Running without terrain data</span>", unsafe_allow_html=True)
    else:
        st.markdown("<span style='background:#d4edda;color:#155724;padding:4px 10px;"
                    "border-radius:12px;font-size:12px;font-weight:600;'>"
                    "🏔 Terrain data loaded</span>", unsafe_allow_html=True)

# BTS / height selectors
st.markdown("### 💬 Ask a Question or Configure Simulation")
marcelo_question = st.text_input(
    "Type your question in English or Spanish:",
    placeholder="e.g. Compare all sites  OR  Analyse CPE sites at 600 MHz",
    key="question_input")

col_sel1, col_sel2 = st.columns(2)
with col_sel1:
    if 'active_bts_index' not in st.session_state or st.session_state.active_bts_index >= len(bts_sites):
        st.session_state.active_bts_index = 0
    selected_bts_ui = st.selectbox(
        "Select Active Base Station (BTS)",
        options=range(len(bts_sites)),
        index=st.session_state.active_bts_index,
        format_func=lambda x: f"{bts_sites[x].name} (Lat:{bts_sites[x].latitude:.5f},"
                               f" Lon:{bts_sites[x].longitude:.5f})",
        key="active_bts_sel")
    st.session_state.active_bts_index = selected_bts_ui
    active_bts_site = bts_sites[selected_bts_ui]

with col_sel2:
    if st.session_state.sim_bts_height is None:
        st.session_state.sim_bts_height = float(active_bts_site.height_m)
    bts_height_ovr = st.number_input(
        "BTS Antenna Height (m)", min_value=1.0, max_value=200.0,
        value=float(st.session_state.sim_bts_height), step=1.0, key="bts_height_inp")
    st.session_state.sim_bts_height = bts_height_ovr

cpe_sites = [s for s in sites if not s.is_bts_candidate]

# Run buttons
col_run1, col_run2, col_run3 = st.columns([2, 2, 1])
with col_run1:
    if st.session_state.mode == 'coverage':
        run_sim = st.button("▶ Run Simulation", type="primary", use_container_width=True)
    else:
        run_sim = False
with col_run2:
    if st.session_state.mode == 'cpe_analysis':
        run_cpe = st.button("📍 Run CPE Link Analysis", type="primary", use_container_width=True)
    else:
        run_cpe = False
with col_run3:
    run_compare = False
    if len(bts_sites) > 1:
        run_compare = st.button("⚡ Compare All", use_container_width=True)

# ── AI question parsing ───────────────────────────────────────────────────────

ai_params = None
if (run_sim or run_cpe or run_compare) and marcelo_question.strip():
    with st.spinner("🤖 AI interpreting…"):
        try:
            sites_ctx = [{"name": s.name, "lat": s.latitude,
                           "lon": s.longitude, "height_m": s.height_m}
                         for s in bts_sites]
            ai_params = interpret_question(marcelo_question, sites_ctx, gemini_api_key)
            st.info(f"🤖 {ai_params.get('plain_english_task', 'Running simulation…')}")
            selected_frequency = float(ai_params.get("frequency_mhz", selected_frequency))
            prop_model = ai_params.get("model", prop_model)
            sim_env    = ai_params.get("environment", sim_env)
            if ai_params.get("site_index") is not None:
                idx = int(ai_params["site_index"])
                if idx < len(bts_sites):
                    active_bts_site = bts_sites[idx]
                    st.session_state.active_bts_index = idx
        except Exception:
            pass

# ── Coverage simulation ───────────────────────────────────────────────────────

if run_sim:
    try:
        with st.spinner("⏳ Running coverage simulation…"):
            coverage_grid = compute_coverage_grid(
                bts_site=active_bts_site,
                equipment_bts=st.session_state.bts_specs,
                equipment_cpe=st.session_state.cpe_specs,
                f_mhz=selected_frequency,
                bounds=proj_bounds,
                terrain_grid=terrain_grid,
                resolution_m=resolution_val,
                model=prop_model,
                environment=sim_env,
                bts_height_override=bts_height_ovr,
            )
        st.session_state.active_coverage_grid = coverage_grid
        st.session_state.cpe_results = None
        st.session_state.all_compares = None
        st.session_state.simulation_run = True
        st.session_state.sim_frequency = selected_frequency
        st.session_state.sim_model = prop_model
        st.session_state.sim_env = sim_env
        st.session_state.sim_bts_height = bts_height_ovr

        # AI recommendation
        if gemini_api_key:
            with st.spinner("💡 Generating recommendation…"):
                try:
                    rec = generate_recommendation({
                        "bts_site": active_bts_site.name,
                        "frequency_mhz": selected_frequency,
                        "coverage_pct": coverage_grid.stats['coverage_pct'],
                        "good_pct": coverage_grid.stats['good_pct'],
                        "avg_rssi_dbm": coverage_grid.stats['avg_rssi'],
                        "max_range_km": coverage_grid.stats['max_range_km'],
                        "model": prop_model,
                        "environment": sim_env,
                        "total_cpe_sites": len(cpe_sites),
                    }, gemini_api_key)
                    st.session_state.ai_recommendation = rec
                except Exception:
                    st.session_state.ai_recommendation = None

        # Save history entry
        try:
            ts = datetime.datetime.now()
            hist_data = {
                "timestamp": ts.isoformat(),
                "project_name": getattr(parsed_data, 'name', 'Untitled'),
                "bts_site": active_bts_site.name,
                "frequency_mhz": selected_frequency,
                "eirp_dbm": round(compute_eirp(
                    st.session_state.bts_specs.tx_power_dbm,
                    st.session_state.bts_specs.antenna_gain_dbi,
                    st.session_state.bts_specs.cable_loss_db), 1),
                "model_used": prop_model,
                "coverage_pct": coverage_grid.stats['coverage_pct'],
                "good_signal_pct": coverage_grid.stats['good_pct'],
                "avg_rssi_dbm": coverage_grid.stats['avg_rssi'],
                "total_cpe_sites": len(cpe_sites),
                "plain_english_result": (
                    f"{coverage_grid.stats['coverage_pct']}% coverage, "
                    f"avg RSSI {coverage_grid.stats['avg_rssi']} dBm"),
            }
            map_png = coverage_to_image(coverage_grid)
            save_simulation(_BASE, ts, hist_data, map_png_bytes=map_png)
            st.session_state.history = load_history(_BASE)
        except Exception:
            pass
    except Exception as e:
        st.error(f"Simulation failed: {e}")

# ── CPE link analysis ─────────────────────────────────────────────────────────

if run_cpe:
    if not cpe_sites:
        st.warning("No CPE sites found in the project file. Please upload a file with both BTS and CPE points.")
    else:
        try:
            with st.spinner(f"📍 Analysing {len(cpe_sites)} CPE sites…"):
                results = compute_cpe_analysis(
                    bts_site=active_bts_site,
                    cpe_sites=cpe_sites,
                    equipment_bts=st.session_state.bts_specs,
                    equipment_cpe=st.session_state.cpe_specs,
                    f_mhz=selected_frequency,
                    terrain_grid=terrain_grid,
                    model=prop_model,
                    environment=sim_env,
                    bts_height_override=bts_height_ovr,
                )
            st.session_state.cpe_results = results
            st.session_state.active_coverage_grid = None
            st.session_state.all_compares = None
            st.session_state.simulation_run = True
            st.session_state.sim_frequency = selected_frequency
            st.session_state.sim_model = prop_model
            st.session_state.sim_env = sim_env
            st.session_state.sim_bts_height = bts_height_ovr

            # AI recommendation
            if gemini_api_key:
                with st.spinner("💡 Generating recommendation…"):
                    try:
                        covered = [r for r in results if r["rssi_dbm"] >= -90]
                        rec = generate_recommendation({
                            "bts_site": active_bts_site.name,
                            "frequency_mhz": selected_frequency,
                            "total_cpe_sites": len(results),
                            "covered_cpe_sites": len(covered),
                            "excellent": sum(1 for r in results if r["rssi_dbm"] >= -65),
                            "good": sum(1 for r in results if -75 <= r["rssi_dbm"] < -65),
                            "marginal": sum(1 for r in results if -85 <= r["rssi_dbm"] < -75),
                            "weak": sum(1 for r in results if -90 <= r["rssi_dbm"] < -85),
                            "no_link": sum(1 for r in results if r["rssi_dbm"] < -90),
                        }, gemini_api_key)
                        st.session_state.ai_recommendation = rec
                    except Exception:
                        st.session_state.ai_recommendation = None

            # Save history
            try:
                ts = datetime.datetime.now()
                covered_count = sum(1 for r in results if r["rssi_dbm"] >= -90)
                hist_data = {
                    "timestamp": ts.isoformat(),
                    "project_name": "CPE Analysis",
                    "bts_site": active_bts_site.name,
                    "frequency_mhz": selected_frequency,
                    "eirp_dbm": round(compute_eirp(
                        st.session_state.bts_specs.tx_power_dbm,
                        st.session_state.bts_specs.antenna_gain_dbi,
                        st.session_state.bts_specs.cable_loss_db), 1),
                    "model_used": prop_model,
                    "coverage_pct": round(100 * covered_count / max(len(results), 1), 1),
                    "total_cpe_sites": len(results),
                    "covered_cpe_sites": covered_count,
                    "plain_english_result": f"{covered_count}/{len(results)} CPE sites covered",
                }
                save_simulation(_BASE, ts, hist_data)
                st.session_state.history = load_history(_BASE)
            except Exception:
                pass
        except Exception as e:
            st.error(f"CPE analysis failed: {e}")

# ── Compare all sites ─────────────────────────────────────────────────────────

if run_compare:
    if len(bts_sites) < 2:
        st.warning("Need at least 2 BTS candidate sites to compare.")
    elif not cpe_sites:
        st.warning("No CPE sites found — please upload a file with CPE points.")
    else:
        try:
            with st.spinner(f"⚡ Comparing {len(bts_sites)} BTS sites across {len(cpe_sites)} CPE points…"):
                compare_results = {}

                def _run_one(bts):
                    return bts.name, compute_cpe_analysis(
                        bts_site=bts,
                        cpe_sites=cpe_sites,
                        equipment_bts=st.session_state.bts_specs,
                        equipment_cpe=st.session_state.cpe_specs,
                        f_mhz=selected_frequency,
                        terrain_grid=terrain_grid,
                        model=prop_model,
                        environment=sim_env,
                        bts_height_override=bts_height_ovr,
                    )

                with ThreadPoolExecutor(max_workers=min(len(bts_sites), 4)) as ex:
                    futures = {ex.submit(_run_one, b): b for b in bts_sites}
                    for fut in as_completed(futures):
                        try:
                            name, res = fut.result()
                            compare_results[name] = res
                        except Exception:
                            pass

            st.session_state.all_compares = compare_results
            st.session_state.simulation_run = True
        except Exception as e:
            st.error(f"Comparison failed: {e}")

# ══════════════════════════════════════════════════════
#  RENDER RESULTS
# ══════════════════════════════════════════════════════

if not st.session_state.simulation_run:
    st.stop()

# ── History replay ────────────────────────────────────────────────────────────

if st.session_state.loaded_past and not run_sim and not run_cpe and not run_compare:
    past = st.session_state.loaded_past
    st.info(f"📋 Showing history entry: **{past.get('bts_site','?')}** · "
            f"{past.get('frequency_mhz','?')} MHz · {past.get('timestamp','')[:10]}")
    if past.get('map_image_path') and os.path.exists(past['map_image_path']):
        st.image(past['map_image_path'], caption="Saved coverage map", use_column_width=True)
    st.markdown(f"**Result:** {past.get('plain_english_result', '—')}")
    col_hist1, col_hist2 = st.columns(2)
    with col_hist1:
        if past.get('pdf_path') and os.path.exists(past['pdf_path']):
            with open(past['pdf_path'], 'rb') as f:
                st.download_button("📄 Download Report", data=f.read(),
                                   file_name="WiFrost_Report.pdf",
                                   mime="application/pdf",
                                   use_container_width=True)
    with col_hist2:
        if st.button("🔄 Re-run this simulation", use_container_width=True):
            st.session_state.sim_frequency = float(past.get('frequency_mhz', 570))
            st.session_state.sim_model = past.get('model_used', 'terrain_aware')
            st.session_state.loaded_past = None
            st.rerun()
    st.stop()

# ── Coverage map mode ─────────────────────────────────────────────────────────

if (st.session_state.mode == 'coverage'
        and st.session_state.active_coverage_grid is not None):

    coverage_grid = st.session_state.active_coverage_grid
    stats = coverage_grid.stats

    # Banner
    if stats['coverage_pct'] >= 85.0:
        st.markdown(f'<div class="banner-success">✅ <b>{coverage_grid.bts_site.name}'
                    f' ({st.session_state.sim_bts_height:.1f}m)</b> covers '
                    f'<b>{stats["coverage_pct"]}%</b> of the desired area. Recommended.</div>',
                    unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="banner-warning">⚠️ <b>{coverage_grid.bts_site.name}</b>'
                    f' only covers <b>{stats["coverage_pct"]}%</b>. '
                    f'Consider increasing height or choosing another site.</div>',
                    unsafe_allow_html=True)

    # KPI cards
    st.markdown(f"""
<div class="kpi-container">
  <div class="kpi-card"><div class="kpi-title">Coverage Area</div>
    <div class="kpi-value">{stats['coverage_pct']}%</div></div>
  <div class="kpi-card"><div class="kpi-title">Good Signal</div>
    <div class="kpi-value">{stats['good_pct']}%</div></div>
  <div class="kpi-card"><div class="kpi-title">Avg RSSI (Covered)</div>
    <div class="kpi-value">{stats['avg_rssi']} dBm</div></div>
  <div class="kpi-card"><div class="kpi-title">Max Covered Range</div>
    <div class="kpi-value">{stats['max_range_km']} km</div></div>
</div>""", unsafe_allow_html=True)

    result_tabs = st.tabs(["🗺 Coverage Heatmap", "🏔 Terrain & Comparisons",
                            "📡 Client CPE List"])

    with result_tabs[0]:
        try:
            bts_lat = coverage_grid.bts_site.latitude
            bts_lon = coverage_grid.bts_site.longitude
            m_heat = folium.Map(location=[bts_lat, bts_lon],
                                zoom_start=13, tiles="OpenStreetMap")

            # Sector wedges
            n_sec = st.session_state.bts_specs.default_sectors
            sec_colors = _sector_colors()
            if n_sec == 1:
                folium.Circle(location=[bts_lat, bts_lon],
                              radius=2500, color='red', fill=True,
                              fill_opacity=0.08, weight=1).add_to(m_heat)
            else:
                azimuths = st.session_state.bts_specs.sector_azimuths[:n_sec]
                hpbw = st.session_state.bts_specs.horizontal_beamwidth
                for i, az in enumerate(azimuths):
                    poly_pts = make_sector_polygon(bts_lat, bts_lon, az, hpbw)
                    c = sec_colors[i % len(sec_colors)]
                    folium.Polygon(locations=poly_pts, color=c, weight=1,
                                   fill=True, fill_color=c,
                                   fill_opacity=0.18,
                                   tooltip=f"Sector {i+1} ({az}°)").add_to(m_heat)

            for poly in polygons:
                folium.Polygon(
                    locations=[[c[1], c[0]] for c in poly.coordinates],
                    color="purple", weight=2, fill=True, fill_opacity=0.1
                ).add_to(m_heat)
            for line in lines:
                folium.PolyLine(
                    locations=[[c[1], c[0]] for c in line.coordinates],
                    color="blue", weight=3
                ).add_to(m_heat)

            folium.GeoJson(
                coverage_to_geojson(coverage_grid),
                style_function=lambda x: {
                    "fillColor": x["properties"]["fill"],
                    "color":     x["properties"]["fill"],
                    "weight": 0,
                    "fillOpacity": x["properties"]["fill-opacity"],
                },
                tooltip=folium.GeoJsonTooltip(
                    fields=["rssi"], aliases=["Signal RSSI (dBm):"]),
            ).add_to(m_heat)

            for site in sites:
                is_active = site.name == coverage_grid.bts_site.name
                if site.is_bts_candidate:
                    ic, is_ = ("red" if is_active else "orange"), "tower"
                else:
                    ic, is_ = "cadetblue", "home"
                folium.Marker(
                    location=[site.latitude, site.longitude],
                    popup=f"<b>{site.name}</b><br>{site.site_type}",
                    tooltip=site.name,
                    icon=folium.Icon(color=ic, icon=is_, prefix="fa"),
                ).add_to(m_heat)

            st.markdown("""
<div class="legend-container">
  <span style="font-weight:700;color:#1B365D;font-size:13px;margin-right:10px;">Signal Bands:</span>
  <div class="legend-item"><div class="legend-dot" style="background:#2ecc71;"></div> Excellent (≥ -65 dBm)</div>
  <div class="legend-item"><div class="legend-dot" style="background:#27ae60;"></div> Good (-65 to -75 dBm)</div>
  <div class="legend-item"><div class="legend-dot" style="background:#f1c40f;"></div> Marginal (-75 to -85 dBm)</div>
  <div class="legend-item"><div class="legend-dot" style="background:#e74c3c;"></div> Weak (-85 to -90 dBm)</div>
</div>""", unsafe_allow_html=True)

            st_folium(m_heat, height=450, key="heatmap_map", use_container_width=True)
        except Exception as e:
            st.error(f"Could not render coverage map: {e}")

    with result_tabs[1]:
        col_t1, col_t2 = st.columns(2)
        with col_t1:
            st.markdown("#### 🏔 Terrain Profile")
            if terrain_grid.is_flat:
                st.info("Flat earth model — no terrain profile available.")
            else:
                try:
                    target = (cpe_sites[0] if cpe_sites
                              else KMLPoint("Edge", min_lat, min_lon))
                    fig, lbl = build_terrain_profile_figure(
                        terrain_grid,
                        coverage_grid.bts_site.latitude,
                        coverage_grid.bts_site.longitude,
                        st.session_state.sim_bts_height,
                        target.latitude, target.longitude,
                        target.height_m,
                        st.session_state.sim_frequency,
                        cpe_name=target.name,
                    )
                    if fig:
                        st.caption(f"{lbl} — Profile to {target.name}")
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.info(lbl)
                except Exception as e:
                    st.warning(f"Terrain profile error: {e}")
        with col_t2:
            st.markdown("#### 📊 Site Comparison")
            if st.session_state.all_compares:
                rows = []
                for name, res in st.session_state.all_compares.items():
                    cov = sum(1 for r in res if r["rssi_dbm"] >= -90)
                    rows.append({"Site": name,
                                 "Covered": cov,
                                 "Coverage %": f"{100*cov/max(len(res),1):.1f}%"})
                st.dataframe(pd.DataFrame(rows), use_container_width=True)
            else:
                st.caption("Click ⚡ Compare All to populate this table.")

    with result_tabs[2]:
        st.markdown("#### 📡 Client CPE Coverage List")
        if cpe_sites:
            try:
                eirp = compute_eirp(st.session_state.bts_specs.tx_power_dbm,
                                    st.session_state.bts_specs.antenna_gain_dbi,
                                    st.session_state.bts_specs.cable_loss_db)
                cpe_rows = []
                for s in cpe_sites:
                    d_km = haversine_distance(
                        coverage_grid.bts_site.latitude,
                        coverage_grid.bts_site.longitude,
                        s.latitude, s.longitude)
                    d_km = max(d_km, 0.01)
                    if (st.session_state.sim_model == 'terrain_aware'
                            and not terrain_grid.is_flat):
                        loss, _, _ = terrain_aware_loss(
                            coverage_grid.bts_site.latitude,
                            coverage_grid.bts_site.longitude,
                            st.session_state.sim_bts_height,
                            s.latitude, s.longitude, s.height_m,
                            st.session_state.sim_frequency,
                            terrain_grid, st.session_state.sim_env)
                    else:
                        loss = okumura_hata(d_km, st.session_state.sim_frequency,
                                            st.session_state.sim_bts_height,
                                            s.height_m, st.session_state.sim_env)
                    rssi   = compute_rssi(loss, eirp,
                                          st.session_state.cpe_specs.antenna_gain_dbi,
                                          st.session_state.cpe_specs.cable_loss_db)
                    margin = rssi - st.session_state.cpe_specs.receiver_sensitivity_dbm
                    cpe_rows.append({
                        "Client Name": s.name,
                        "Distance (km)": round(d_km, 2),
                        "Elevation (m)": round(get_elevation(terrain_grid, s.latitude, s.longitude), 1),
                        "RSSI (dBm)": round(rssi, 1),
                        "Link Margin (dB)": round(margin, 1),
                        "Status": cpe_status(rssi),
                    })
                df_cpes = pd.DataFrame(cpe_rows)
                st.dataframe(df_cpes, use_container_width=True)

                towrite = BytesIO()
                df_cpes.to_excel(towrite, index=False)
                towrite.seek(0)
                st.download_button(
                    "📥 Download CPE Results (Excel)",
                    data=towrite.getvalue(),
                    file_name=f"CPE_{coverage_grid.bts_site.name.replace(' ','_')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            except Exception as e:
                st.error(f"Could not build CPE list: {e}")
        else:
            st.info("No CPE sites found. Upload a file with both BTS and CPE points.")

    # PDF report
    try:
        st.markdown("---")
        edge_dist_km = max(0.5, stats["max_range_km"])
        bts_specs = st.session_state.bts_specs
        cpe_specs = st.session_state.cpe_specs
        eirp = compute_eirp(bts_specs.tx_power_dbm, bts_specs.antenna_gain_dbi,
                             bts_specs.cable_loss_db)
        if st.session_state.sim_model == 'terrain_aware' and not terrain_grid.is_flat:
            edge_loss, _, _ = terrain_aware_loss(
                coverage_grid.bts_site.latitude, coverage_grid.bts_site.longitude,
                st.session_state.sim_bts_height,
                coverage_grid.bts_site.latitude + 0.02,
                coverage_grid.bts_site.longitude + 0.02,
                cpe_specs.antenna_height_default_m,
                st.session_state.sim_frequency, terrain_grid, st.session_state.sim_env)
        else:
            edge_loss = okumura_hata(edge_dist_km, st.session_state.sim_frequency,
                                     st.session_state.sim_bts_height,
                                     cpe_specs.antenna_height_default_m,
                                     st.session_state.sim_env)
        edge_rssi   = compute_rssi(edge_loss, eirp,
                                    cpe_specs.antenna_gain_dbi, cpe_specs.cable_loss_db)
        edge_margin = edge_rssi - cpe_specs.receiver_sensitivity_dbm
        rec_text = (f"Coverage {stats['coverage_pct']}% at {st.session_state.sim_frequency:.1f} MHz. "
                    f"Link margin at edge: {edge_margin:.1f} dB.")
        if edge_margin < 6:
            rec_text += " WARNING: Link margin is critical. Field surveys recommended."

        pdf_buf = BytesIO()
        generate_pdf_report(
            output_stream=pdf_buf,
            project_name=f"TVWS Coverage — {coverage_grid.bts_site.name}",
            prepared_by="Marcelo (WiFrost Sales Eng)",
            coverage_grid=coverage_grid,
            equipment_bts=bts_specs,
            equipment_cpe=cpe_specs,
            model_name="Terrain-Aware Hata" if st.session_state.sim_model == 'terrain_aware' else "Flat Hata",
            environment=st.session_state.sim_env,
            edge_loss_db=edge_loss,
            edge_rssi_dbm=edge_rssi,
            edge_margin_db=edge_margin,
            conclusion_text=rec_text,
            all_sites_comparison=None,
        )

        col_pdf, col_cmp = st.columns(2)
        with col_pdf:
            st.download_button(
                "📄 Download PDF Report",
                data=pdf_buf.getvalue(),
                file_name=f"WiFrost_{coverage_grid.bts_site.name.replace(' ','_')}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        with col_cmp:
            if len(bts_sites) > 1:
                if st.button("🔄 Compare All Candidate Sites", use_container_width=True):
                    st.session_state.question_input = "Compare all sites"
                    st.rerun()
    except Exception as e:
        st.error(f"Could not generate PDF report: {e}")

# ── CPE analysis mode ─────────────────────────────────────────────────────────

elif (st.session_state.mode == 'cpe_analysis'
      and st.session_state.cpe_results is not None):

    results = st.session_state.cpe_results

    # Summary bar
    total   = len(results)
    exc     = sum(1 for r in results if r["rssi_dbm"] >= -65)
    good    = sum(1 for r in results if -75 <= r["rssi_dbm"] < -65)
    marg    = sum(1 for r in results if -85 <= r["rssi_dbm"] < -75)
    weak    = sum(1 for r in results if -90 <= r["rssi_dbm"] < -85)
    nolink  = sum(1 for r in results if r["rssi_dbm"] < -90)
    covered = exc + good + marg + weak
    st.markdown(
        f'<div class="summary-bar">'
        f'📡 <b>{covered} of {total} CPE sites covered</b> &nbsp;|&nbsp; '
        f'🟢 {exc} Excellent &nbsp;|&nbsp; 🟡 {good} Good &nbsp;|&nbsp; '
        f'🟠 {marg} Marginal &nbsp;|&nbsp; 🔴 {weak} Weak &nbsp;|&nbsp; '
        f'⛔ {nolink} No Link'
        f'</div>', unsafe_allow_html=True)

    # Map
    try:
        bts_lat = active_bts_site.latitude
        bts_lon = active_bts_site.longitude
        m_cpe = folium.Map(location=[bts_lat, bts_lon],
                           zoom_start=13, tiles="OpenStreetMap")

        # Sector wedges
        n_sec = st.session_state.bts_specs.default_sectors
        sec_colors = _sector_colors()
        if n_sec == 1:
            folium.Circle(location=[bts_lat, bts_lon], radius=2500,
                          color='red', fill=True, fill_opacity=0.08, weight=1).add_to(m_cpe)
        else:
            azimuths = st.session_state.bts_specs.sector_azimuths[:n_sec]
            hpbw = st.session_state.bts_specs.horizontal_beamwidth
            for i, az in enumerate(azimuths):
                poly_pts = make_sector_polygon(bts_lat, bts_lon, az, hpbw)
                c = sec_colors[i % len(sec_colors)]
                folium.Polygon(locations=poly_pts, color=c, weight=1,
                               fill=True, fill_color=c, fill_opacity=0.18,
                               tooltip=f"Sector {i+1} ({az}°)").add_to(m_cpe)

        # BTS marker
        folium.Marker(
            location=[bts_lat, bts_lon],
            popup=f"<b>BTS: {active_bts_site.name}</b>",
            tooltip=active_bts_site.name,
            icon=folium.Icon(color='red', icon='tower', prefix='fa'),
        ).add_to(m_cpe)

        # CPE markers + lines
        for r in results:
            popup_html = (
                f"<b>{r['name']}</b><br>"
                f"Distance: {r['distance_km']} km &nbsp; Bearing: {r['bearing_deg']}°<br>"
                f"Sector: {r['best_sector']+1} &nbsp; Sector Gain: {r['sector_gain_db']} dB<br>"
                f"Path Loss: {r['terrain_loss_db']} dB<br>"
                f"<b>RSSI: {r['rssi_dbm']} dBm</b><br>"
                f"Link Margin: {r['link_margin_db']} dB<br>"
                f"LoS: {r['fresnel_clearance']}<br>"
                f"Status: {r['status']}"
            )
            folium.Marker(
                location=[r['lat'], r['lon']],
                popup=folium.Popup(popup_html, max_width=280),
                tooltip=f"{r['name']} — {r['rssi_dbm']} dBm",
                icon=folium.Icon(color=r['marker_color'], icon='wifi', prefix='fa'),
            ).add_to(m_cpe)
            folium.PolyLine(
                locations=[[bts_lat, bts_lon], [r['lat'], r['lon']]],
                color=r['line_color'], weight=1.5, opacity=0.7,
            ).add_to(m_cpe)

        map_data = st_folium(m_cpe, height=420, key="cpe_map", use_container_width=True)

        # Detect clicked CPE
        try:
            clicked = map_data.get("last_object_clicked_popup") or ""
            if clicked:
                for r in results:
                    if r['name'] in clicked:
                        st.session_state.selected_cpe_name = r['name']
                        break
        except Exception:
            pass

    except Exception as e:
        st.error(f"Could not render CPE map: {e}")

    # Results table
    try:
        df_results = pd.DataFrame([{
            "#": i + 1,
            "Name": r["name"],
            "Distance (km)": r["distance_km"],
            "Sector": r["best_sector"] + 1,
            "RSSI (dBm)": r["rssi_dbm"],
            "Margin (dB)": r["link_margin_db"],
            "LoS": r["fresnel_clearance"],
            "Status": r["status"],
        } for i, r in enumerate(results)])

        # Row selection via selectbox for terrain cross-section
        cpe_names = [r['name'] for r in results]
        sel_name = st.selectbox(
            "Select CPE for terrain cross-section ↓",
            options=["— none —"] + cpe_names,
            index=0, key="cpe_select_box")
        if sel_name != "— none —":
            st.session_state.selected_cpe_name = sel_name

        st.dataframe(df_results, use_container_width=True, height=280)

        # Download
        try:
            xl_bytes = build_cpe_excel(
                results, active_bts_site.name,
                st.session_state.sim_frequency,
                "Terrain-Aware Hata" if st.session_state.sim_model == 'terrain_aware' else "Flat Hata",
                st.session_state.sim_env)
            st.download_button(
                "📥 Download CPE Results (Excel — 3 sheets)",
                data=xl_bytes,
                file_name=f"CPE_Analysis_{active_bts_site.name.replace(' ','_')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True)
        except Exception as e:
            st.warning(f"Excel export error: {e}")
    except Exception as e:
        st.error(f"Could not build results table: {e}")

    # Terrain cross-section (Part 6)
    sel = st.session_state.selected_cpe_name
    if sel:
        sel_r = next((r for r in results if r['name'] == sel), None)
        if sel_r:
            with st.expander(f"📊 Terrain profile — {sel}", expanded=True):
                try:
                    fig, lbl = build_terrain_profile_figure(
                        terrain_grid,
                        active_bts_site.latitude, active_bts_site.longitude,
                        st.session_state.sim_bts_height,
                        sel_r['lat'], sel_r['lon'],
                        next((c.height_m for c in cpe_sites if c.name == sel), 10.0),
                        st.session_state.sim_frequency,
                        cpe_name=sel,
                    )
                    if fig:
                        st.caption(lbl)
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.info(lbl)
                except Exception as e:
                    st.warning(f"Terrain profile error: {e}")

# ── Compare all sites (Part 5) ────────────────────────────────────────────────

if st.session_state.all_compares:
    st.markdown("---")
    st.markdown("### ⚡ Compare All BTS Candidate Sites")

    comp = st.session_state.all_compares
    bts_names = list(comp.keys())
    cpe_name_set = [r['name'] for r in next(iter(comp.values()))]

    # Per-CPE comparison table
    try:
        rows = []
        for cpe_n in cpe_name_set:
            row = {"CPE": cpe_n}
            best_rssi = -999
            best_site = ""
            for bts_n, res in comp.items():
                match = next((r for r in res if r['name'] == cpe_n), None)
                v = match['rssi_dbm'] if match else -999
                row[bts_n] = v
                if v > best_rssi:
                    best_rssi = v
                    best_site = bts_n
            # Advantage over second-best
            rssis = sorted([row[b] for b in bts_names], reverse=True)
            row["Best Site ★"] = best_site
            row["Margin Adv (dB)"] = round(rssis[0] - rssis[1], 1) if len(rssis) > 1 else 0
            rows.append(row)

        df_comp = pd.DataFrame(rows)

        # Totals row
        totals = {"CPE": "✅ Covered / Total"}
        for bts_n, res in comp.items():
            cov = sum(1 for r in res if r['rssi_dbm'] >= -90)
            totals[bts_n] = f"{cov}/{len(res)}"
        totals["Best Site ★"] = ""
        totals["Margin Adv (dB)"] = ""
        df_comp = pd.concat([df_comp, pd.DataFrame([totals])], ignore_index=True)

        st.dataframe(df_comp, use_container_width=True, height=300)
    except Exception as e:
        st.warning(f"Comparison table error: {e}")

    # Plotly stacked bar chart
    try:
        fig_bar = go.Figure()
        status_labels = ["🟢 Excellent", "🟡 Good", "🟠 Marginal", "🔴 Weak"]
        bar_colors    = ["#27ae60", "#f39c12", "#e67e22", "#e74c3c"]

        for stat, color in zip(status_labels, bar_colors):
            counts = []
            for bts_n, res in comp.items():
                if stat == "🟢 Excellent":
                    counts.append(sum(1 for r in res if r['rssi_dbm'] >= -65))
                elif stat == "🟡 Good":
                    counts.append(sum(1 for r in res if -75 <= r['rssi_dbm'] < -65))
                elif stat == "🟠 Marginal":
                    counts.append(sum(1 for r in res if -85 <= r['rssi_dbm'] < -75))
                else:
                    counts.append(sum(1 for r in res if -90 <= r['rssi_dbm'] < -85))
            fig_bar.add_trace(go.Bar(
                name=stat,
                x=bts_names,
                y=counts,
                marker_color=color,
            ))

        fig_bar.update_layout(
            barmode='stack',
            title="CPE Site Coverage by Signal Quality",
            xaxis_title="BTS Candidate Site",
            yaxis_title="Number of CPE Sites",
            height=320,
            margin=dict(l=50, r=20, t=40, b=40),
            legend=dict(orientation="h", y=-0.25),
        )
        st.plotly_chart(fig_bar, use_container_width=True)
    except Exception as e:
        st.warning(f"Comparison chart error: {e}")

# ── AI recommendation (Part 4) ────────────────────────────────────────────────

rec = st.session_state.ai_recommendation
if rec and (rec.get("english") or rec.get("spanish")):
    with st.expander("💡 Recommendation for customer proposal", expanded=False):
        st.markdown('<div class="rec-card">', unsafe_allow_html=True)
        if rec.get("english"):
            st.markdown("**English**")
            st.code(rec["english"], language=None)
        if rec.get("spanish"):
            st.markdown("**Español**")
            st.code(rec["spanish"], language=None)
        st.markdown("</div>", unsafe_allow_html=True)
        st.caption("Click the copy icon on either text block to copy to clipboard.")
