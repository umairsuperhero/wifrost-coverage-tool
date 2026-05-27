import os
import math
import json
import datetime
import shutil
import tempfile
from io import BytesIO
import numpy as np
import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium
from dotenv import load_dotenv

# Import our backend modules
from wifi_frost_defaults import WifrostBTS, WifrostCPE
from kml_parser import parse_kml_or_kmz, KMLData, KMLPoint
from excel_parser import parse_excel_sites, generate_excel_template
from terrain import fetch_srtm, get_elevation, get_profile, haversine_distance
from propagation import compute_eirp, compute_rssi, okumura_hata, terrain_aware_loss
from heatmap import compute_coverage_grid, coverage_to_geojson
from ai_interpreter import interpret_question, extract_equipment_params
from report import generate_pdf_report

# 1. Page Configuration and Styling
st.set_page_config(
    page_title="WiFrost TVWS Coverage Planner",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for rich aesthetics
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap');
    
    /* Global Styles */
    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif;
    }
    
    /* Primary Header Styling */
    .main-header {
        background: linear-gradient(135deg, #1B365D 0%, #102A45 100%);
        padding: 20px 25px;
        border-radius: 12px;
        color: white;
        margin-bottom: 25px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    .main-header h1 {
        margin: 0;
        font-size: 28px;
        font-weight: 700;
        letter-spacing: -0.5px;
    }
    .main-header p {
        margin: 5px 0 0 0;
        font-size: 14px;
        opacity: 0.8;
    }
    
    /* Result Banners */
    .banner-success {
        background-color: #d4edda;
        border-left: 6px solid #28a745;
        color: #155724;
        padding: 15px 20px;
        border-radius: 6px;
        margin-bottom: 20px;
        font-weight: 600;
        font-size: 16px;
    }
    .banner-warning {
        background-color: #fff3cd;
        border-left: 6px solid #ffc107;
        color: #856404;
        padding: 15px 20px;
        border-radius: 6px;
        margin-bottom: 20px;
        font-weight: 600;
        font-size: 16px;
    }
    
    /* KPI Cards */
    .kpi-container {
        display: flex;
        justify-content: space-between;
        gap: 15px;
        margin-bottom: 20px;
    }
    .kpi-card {
        background-color: #ffffff;
        border: 1px solid #dfe1e6;
        border-radius: 8px;
        padding: 15px;
        flex: 1;
        text-align: center;
        box-shadow: 0 2px 6px rgba(9, 30, 66, 0.08);
        transition: transform 0.2s ease;
    }
    .kpi-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(9, 30, 66, 0.12);
    }
    .kpi-title {
        font-size: 12px;
        color: #6b778c;
        font-weight: 600;
        text-transform: uppercase;
        margin-bottom: 8px;
        letter-spacing: 0.5px;
    }
    .kpi-value {
        font-size: 24px;
        color: #1b365d;
        font-weight: 700;
    }
    
    /* Custom Legend */
    .legend-container {
        background: white;
        padding: 10px 15px;
        border-radius: 6px;
        border: 1px solid #dfe1e6;
        display: flex;
        align-items: center;
        gap: 20px;
        margin-top: 10px;
        margin-bottom: 20px;
    }
    .legend-item {
        display: flex;
        align-items: center;
        gap: 6px;
        font-size: 13px;
        font-weight: 500;
    }
    .legend-dot {
        width: 12px;
        height: 12px;
        border-radius: 3px;
    }
</style>
""", unsafe_allow_html=True)

# 2. Setup Directories and Files
sample_dir = os.path.join(os.path.dirname(__file__), "sample_data")
cache_dir = os.path.join(os.path.dirname(__file__), "cache")
os.makedirs(sample_dir, exist_ok=True)
os.makedirs(cache_dir, exist_ok=True)
generate_excel_template(sample_dir)

# Auto-copy sample KMZ if missing
original_kmz_path = "/Users/umairqayyum/Documents/Software/wifrost-coverage-tool/SPRBUN TVWS.kmz"
target_kmz_path = os.path.join(sample_dir, "SPRBUN_TVWS.kmz")
if not os.path.exists(target_kmz_path) and os.path.exists(original_kmz_path):
    try:
        shutil.copy2(original_kmz_path, target_kmz_path)
    except Exception:
        pass

# 3. Environment & Key Management
env_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(env_path)

# Initialize Session State values
if 'bts_specs' not in st.session_state:
    st.session_state.bts_specs = WifrostBTS()
if 'cpe_specs' not in st.session_state:
    st.session_state.cpe_specs = WifrostCPE()
if 'custom_datasheet_nulls' not in st.session_state:
    st.session_state.custom_datasheet_nulls = []

# Persistent History loading
if 'history' not in st.session_state:
    st.session_state.history = []
    history_file = os.path.join(cache_dir, "history.json")
    if os.path.exists(history_file):
        try:
            with open(history_file, 'r') as f:
                st.session_state.history = json.load(f)
        except Exception:
            pass

# Function to save API keys to .env
def save_keys(ot_key, gemini_key):
    try:
        with open(env_path, "w") as f:
            f.write(f"OPENTOPOGRAPHY_API_KEY={ot_key.strip()}\n")
            f.write(f"GEMINI_API_KEY={gemini_key.strip()}\n")
        st.sidebar.success("🔑 API Keys saved successfully!")
    except Exception as e:
        st.sidebar.error(f"Could not write to .env: {e}")

# Sidebar Section: Title
st.sidebar.markdown("<h2 style='color:#1B365D; margin-top:0;'>📡 WiFrost Tool Settings</h2>", unsafe_allow_html=True)

# API Keys Configuration
with st.sidebar.expander("🔑 API Keys Setup", expanded=False):
    st.caption("You only need to enter these once. They will be saved to your local project config.")
    ot_key_val = os.getenv("OPENTOPOGRAPHY_API_KEY", "")
    gem_key_val = os.getenv("GEMINI_API_KEY", "")
    
    ot_key_input = st.text_input("OpenTopography API Key", value=ot_key_val, type="password", key="ot_key_input")
    gem_key_input = st.text_input("Gemini API Key", value=gem_key_val, type="password", key="gem_key_input")
    
    if st.button("Save API Keys", use_container_width=True):
        save_keys(ot_key_input, gem_key_input)
        load_dotenv(env_path)

ot_api_key = os.getenv("OPENTOPOGRAPHY_API_KEY", "")
gemini_api_key = os.getenv("GEMINI_API_KEY", "")

# Sidebar Section: Project Files
st.sidebar.markdown("### 📁 Project Files")
kmz_file = st.sidebar.file_uploader("Drop customer KMZ / KML here", type=["kmz", "kml"])
xlsx_file = st.sidebar.file_uploader("Or drop Excel with coordinates", type=["xlsx"])

parsed_data = None
file_loaded = False
error_message = None

if kmz_file is not None:
    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{kmz_file.name.split('.')[-1]}") as tmp:
        tmp.write(kmz_file.getvalue())
        tmp_path = tmp.name
    try:
        parsed_data = parse_kml_or_kmz(tmp_path)
        file_loaded = True
    except Exception as e:
        error_message = f"Could not read KML/KMZ file. Details: {e}"
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
            
elif xlsx_file is not None:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        tmp.write(xlsx_file.getvalue())
        tmp_path = tmp.name
    try:
        parsed_data = parse_excel_sites(tmp_path)
        file_loaded = True
    except Exception as e:
        error_message = f"Could not read Excel file. Details: {e}"
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

if file_loaded and parsed_data:
    bts_candidates = [s for s in parsed_data.sites if s.is_bts_candidate]
    st.sidebar.markdown(f"✅ **Loaded {len(parsed_data.sites)} sites**")
    st.sidebar.caption(f"Found {len(bts_candidates)} candidate BTS sites.")
elif error_message:
    st.sidebar.error(error_message)

# Sidebar Section: Equipment specs
st.sidebar.markdown("### 📡 Equipment Specifications")
equip_tabs = st.sidebar.tabs(["BTS Specs", "CPE Specs", "Upload Datasheet"])

with equip_tabs[0]:
    st.session_state.bts_specs.model_name = st.text_input("BTS Model Name", value=st.session_state.bts_specs.model_name)
    st.session_state.bts_specs.tx_power_dbm = st.number_input("BTS TX Power (dBm)", value=st.session_state.bts_specs.tx_power_dbm, step=1.0)
    st.session_state.bts_specs.antenna_gain_dbi = st.number_input("BTS Antenna Gain (dBi)", value=st.session_state.bts_specs.antenna_gain_dbi, step=1.0)
    st.session_state.bts_specs.cable_loss_db = st.number_input("BTS Cable/Connector Loss (dB)", value=st.session_state.bts_specs.cable_loss_db, step=0.1)
    st.session_state.bts_specs.receiver_sensitivity_dbm = st.number_input("BTS RX Sensitivity (dBm)", value=st.session_state.bts_specs.receiver_sensitivity_dbm, step=1.0)
    
with equip_tabs[1]:
    st.session_state.cpe_specs.model_name = st.text_input("CPE Model Name", value=st.session_state.cpe_specs.model_name)
    st.session_state.cpe_specs.tx_power_dbm = st.number_input("CPE TX Power (dBm)", value=st.session_state.cpe_specs.tx_power_dbm, step=1.0)
    st.session_state.cpe_specs.antenna_gain_dbi = st.number_input("CPE Antenna Gain (dBi)", value=st.session_state.cpe_specs.antenna_gain_dbi, step=1.0)
    st.session_state.cpe_specs.cable_loss_db = st.number_input("CPE Cable/Connector Loss (dB)", value=st.session_state.cpe_specs.cable_loss_db, step=0.1)
    st.session_state.cpe_specs.receiver_sensitivity_dbm = st.number_input("CPE RX Sensitivity (dBm)", value=st.session_state.cpe_specs.receiver_sensitivity_dbm, step=1.0)

with equip_tabs[2]:
    st.markdown("**Extract specs from PDF**")
    custom_pdf = st.file_uploader("Upload PDF Datasheet", type=["pdf"])
    pdf_device_type = st.selectbox("Device Type", ["BTS", "CPE"])
    if custom_pdf is not None:
        if st.button("Parse PDF Specs", use_container_width=True):
            if not gemini_api_key:
                st.error("🔑 Please set your Gemini API Key first.")
            else:
                with st.spinner("Extracting with Gemini..."):
                    try:
                        extracted = extract_equipment_params(custom_pdf.getvalue(), pdf_device_type, gemini_api_key)
                        null_fields = []
                        target = st.session_state.bts_specs if pdf_device_type == "BTS" else st.session_state.cpe_specs
                        for k, v in extracted.items():
                            if v is None:
                                null_fields.append(k)
                            else:
                                setattr(target, k, v)
                        st.session_state.custom_datasheet_nulls = null_fields
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed: {e}")

if st.sidebar.button("Reset Equipment Defaults", use_container_width=True):
    st.session_state.bts_specs = WifrostBTS()
    st.session_state.cpe_specs = WifrostCPE()
    st.session_state.custom_datasheet_nulls = []
    st.rerun()

# Setup simulation run triggers
bts_sites = []
if file_loaded and parsed_data:
    bts_sites = [s for s in parsed_data.sites if s.is_bts_candidate]
    if not bts_sites:
        if not parsed_data.sites:
            st.error("No valid sites were found in the uploaded file. Please check the file format and ensure it contains coordinate data.")
            st.stop()
        parsed_data.sites[0].is_bts_candidate = True
        parsed_data.sites[0].site_type = "BTS"
        bts_sites = [parsed_data.sites[0]]

# Handle history trigger values
if st.session_state.get("load_history_trigger", False) and bts_sites:
    past = st.session_state.loaded_past
    st.session_state.sim_frequency = float(past["frequency_mhz"])
    st.session_state.sim_model = "Terrain-aware (accurate)" if past["model"] == "terrain_aware" else "Flat earth (fast)"
    st.session_state.sim_env = past["env"]
    st.session_state.sim_bts_height = float(past["bts_height"])
    for idx, bts in enumerate(bts_sites):
        if bts.name == past["bts_name"]:
            st.session_state.active_bts_index = idx
            break
    st.session_state.load_history_trigger = False

# Sidebar Section: Simulation Settings
st.sidebar.markdown("### ⚙️ Simulation Settings")
freq_min = min(st.session_state.bts_specs.freq_min_mhz, st.session_state.cpe_specs.freq_min_mhz)
freq_max = max(st.session_state.bts_specs.freq_max_mhz, st.session_state.cpe_specs.freq_max_mhz)

if st.session_state.get('sim_frequency') is None:
    st.session_state.sim_frequency = float((freq_min + freq_max)/2.0)
else:
    st.session_state.sim_frequency = max(float(freq_min), min(float(freq_max), float(st.session_state.sim_frequency)))

selected_frequency = st.sidebar.slider(
    "Frequency (MHz)", 
    float(freq_min), 
    float(freq_max), 
    value=float(st.session_state.sim_frequency), 
    step=1.0,
    key="freq_slider"
)
st.session_state.sim_frequency = selected_frequency

model_options = ["Terrain-aware (accurate)", "Flat earth (fast)"]
model_default_idx = 0
if st.session_state.get('sim_model') == "flat" or st.session_state.get('sim_model') == "Flat earth (fast)":
    model_default_idx = 1
prop_model_ui = st.sidebar.selectbox("Model", model_options, index=model_default_idx, key="model_sel")
st.session_state.sim_model = "terrain_aware" if prop_model_ui == "Terrain-aware (accurate)" else "flat"
prop_model = st.session_state.sim_model

resolution_ui = st.sidebar.selectbox("Heatmap Spacing", ["Standard 100m", "Fine 50m", "Fast 200m"])
resolution_val = 100.0
if "50m" in resolution_ui:
    resolution_val = 50.0
elif "200m" in resolution_ui:
    resolution_val = 200.0

# Sidebar Section: Simulation History
st.sidebar.markdown("### ⏳ Simulation History")
if st.session_state.get('history'):
    history_options = [
        f"{h['bts_name']} @ {int(h['frequency_mhz'])}MHz ({h['timestamp']})"
        for h in st.session_state.history
    ]
    selected_hist_idx = st.sidebar.selectbox("Past Simulations", options=range(len(history_options)), format_func=lambda x: history_options[x], key="hist_sel")
    if st.sidebar.button("Revisit Past Simulation", use_container_width=True):
        st.session_state.loaded_past = st.session_state.history[selected_hist_idx]
        st.session_state.load_history_trigger = True
        st.session_state.simulation_run = True # trigger rendering
        
        # Pull stats straight from history cache to avoid immediate recalculations on click
        past = st.session_state.loaded_past
        # We will trigger the recalculation on the next frame with correct parameters loaded
        st.rerun()
else:
    st.sidebar.caption("No simulations in history.")

# ================= MAIN AREA =================
st.markdown("""
<div class="main-header">
    <div>
        <h1>WiFrost TVWS RF Coverage Planning Tool</h1>
        <p>Interactive tool for sales planning, link budgets, and terrain profile analysis</p>
    </div>
    <div style="font-weight: 700; font-size: 16px; border: 2px solid white; padding: 5px 15px; border-radius: 20px;">
        LATIN AMERICA TVWS RESELLER
    </div>
</div>
""", unsafe_allow_html=True)

if not file_loaded or not parsed_data:
    st.markdown("""
    ### 👋 Welcome, Marcelo!
    
    Get started in 3 simple steps:
    1.  **Upload a KMZ/KML file** or an **Excel file** with site coordinates in the left sidebar.
    2.  Check the preloaded **WiFrost LT100 specifications** in the settings.
    3.  Type a question in plain English/Spanish below or click **Run Simulation** to see the coverage map!
    
    *If you don't have a project file handy, you can download templates from our sample folder below:*
    """)
    col_dl1, col_dl2 = st.columns(2)
    with col_dl1:
        template_file_path = os.path.join(sample_dir, "sites_template.xlsx")
        if os.path.exists(template_file_path):
            with open(template_file_path, "rb") as f:
                st.download_button(label="📄 Download Excel Template (sites_template.xlsx)", data=f.read(), file_name="sites_template.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
    with col_dl2:
        sample_kmz_path = os.path.join(sample_dir, "SPRBUN_TVWS.kmz")
        if os.path.exists(sample_kmz_path):
            with open(sample_kmz_path, "rb") as f:
                st.download_button(label="🌍 Download Sample KMZ Project (SPRBUN_TVWS.kmz)", data=f.read(), file_name="SPRBUN_TVWS.kmz", mime="application/vnd.google-earth.kmz", use_container_width=True)
    st.stop()

# Context details
sites = parsed_data.sites
polygons = parsed_data.polygons
lines = parsed_data.lines

lats = [s.latitude for s in sites]
lons = [s.longitude for s in sites]
for poly in polygons:
    lats.extend([c[1] for c in poly.coordinates])
    lons.extend([c[0] for c in poly.coordinates])
for line in lines:
    lats.extend([c[1] for c in line.coordinates])
    lons.extend([c[0] for c in line.coordinates])

if not lats or not lons:
    st.error("No geographic coordinates found in the uploaded file. Please verify it contains valid site locations.")
    st.stop()
min_lat, max_lat = min(lats), max(lats)
min_lon, max_lon = min(lons), max(lons)

pad_lat = 0.04
pad_lon = 0.04 / math.cos(math.radians((min_lat + max_lat) / 2.0))

proj_bounds = {
    "minLat": min_lat - pad_lat,
    "maxLat": max_lat + pad_lat,
    "minLon": min_lon - pad_lon,
    "maxLon": max_lon + pad_lon
}

with st.spinner("🏔 Loading elevation data..."):
    terrain_grid = fetch_srtm(proj_bounds, ot_api_key)

col_badge1, col_badge2 = st.columns([1, 4])
with col_badge1:
    if terrain_grid.is_flat:
        st.markdown("<span style='background-color:#ffe39b; color:#856404; padding: 4px 10px; border-radius: 12px; font-size:12px; font-weight:600;'>⚠️ Running without terrain data</span>", unsafe_allow_html=True)
    else:
        st.markdown("<span style='background-color:#d4edda; color:#155724; padding: 4px 10px; border-radius: 12px; font-size:12px; font-weight:600;'>🏔 Terrain data loaded</span>", unsafe_allow_html=True)

# Selectors
st.markdown("### 💬 Ask a Question or Configure Simulation")
marcelo_question = st.text_input("Type your question in English or Spanish:", placeholder="e.g. Which site gives the best coverage? OR Compare all sites.", key="question_input")

col_sel1, col_sel2 = st.columns(2)
with col_sel1:
    if 'active_bts_index' not in st.session_state or st.session_state.active_bts_index >= len(bts_sites):
        st.session_state.active_bts_index = 0
    selected_bts_ui = st.selectbox(
        "Select Active Base Station (BTS)",
        options=range(len(bts_sites)),
        index=st.session_state.active_bts_index,
        format_func=lambda x: f"{bts_sites[x].name} (Lat: {bts_sites[x].latitude:.5f}, Lon: {bts_sites[x].longitude:.5f})",
        key="active_bts_sel"
    )
    st.session_state.active_bts_index = selected_bts_ui
    active_bts_site = bts_sites[selected_bts_ui]

with col_sel2:
    if st.session_state.get('sim_bts_height') is None:
        st.session_state.sim_bts_height = float(active_bts_site.height_m)
    bts_height_ovr = st.number_input("Active BTS Antenna Height (m)", min_value=1.0, max_value=200.0, value=float(st.session_state.sim_bts_height), step=1.0, key="bts_height_inp")
    st.session_state.sim_bts_height = bts_height_ovr

# Simulation triggers
run_sim = st.button("▶ Run Simulation", type="primary", use_container_width=True)

if run_sim:
    # 1. AI Question Analysis
    ai_params = None
    if marcelo_question.strip():
        with st.spinner("🤖 AI interpreting..."):
            sites_context_list = [{"name": s.name, "lat": s.latitude, "lon": s.longitude, "height_m": s.height_m} for s in bts_sites]
            ai_params = interpret_question(marcelo_question, sites_context_list, gemini_api_key)
            st.info(f"🤖 **AI Interpreter Action:** {ai_params.get('plain_english_task', 'Running coverage simulation.')}")
            
            selected_frequency = float(ai_params.get("frequency_mhz", selected_frequency))
            prop_model = ai_params.get("model", prop_model)
            if ai_params.get("site_index") is not None:
                site_idx = int(ai_params["site_index"])
                if site_idx < len(bts_sites):
                    active_bts_site = bts_sites[site_idx]
                    st.session_state.active_bts_index = site_idx
                    bts_height_ovr = active_bts_site.height_m

    action = ai_params.get("action", "single_site") if ai_params else "single_site"
    env = ai_params.get("environment", "suburban") if ai_params else "suburban"
    
    # Run
    if action == "compare_all_sites":
        with st.spinner("⏳ Comparing coverage..."):
            site_results = []
            for bts in bts_sites:
                cov_grid = compute_coverage_grid(bts_site=bts, equipment_bts=st.session_state.bts_specs, equipment_cpe=st.session_state.cpe_specs, f_mhz=selected_frequency, bounds=proj_bounds, terrain_grid=terrain_grid, resolution_m=resolution_val, model=prop_model, environment=env)
                site_results.append(cov_grid)
                
            best_idx = int(np.argmax([g.stats['coverage_pct'] for g in site_results]))
            coverage_grid = site_results[best_idx]
            
            all_compares = []
            for i, grid in enumerate(site_results):
                all_compares.append({"name": grid.bts_site.name, "coverage_pct": grid.stats['coverage_pct'], "good_pct": grid.stats['good_pct'], "max_range_km": grid.stats['max_range_km'], "is_best": (i == best_idx)})
            st.session_state.all_compares = all_compares
            st.session_state.active_coverage_grid = coverage_grid
    else:
        with st.spinner("⏳ Simulating coverage..."):
            coverage_grid = compute_coverage_grid(bts_site=active_bts_site, equipment_bts=st.session_state.bts_specs, equipment_cpe=st.session_state.cpe_specs, f_mhz=selected_frequency, bounds=proj_bounds, terrain_grid=terrain_grid, resolution_m=resolution_val, model=prop_model, environment=env, bts_height_override=bts_height_ovr)
            st.session_state.active_coverage_grid = coverage_grid
            st.session_state.all_compares = None

    stats = coverage_grid.stats
    
    # Save parameters to session state
    st.session_state.simulation_run = True
    st.session_state.sim_frequency = selected_frequency
    st.session_state.sim_model = prop_model
    st.session_state.sim_env = env
    st.session_state.sim_bts_height = bts_height_ovr

    # Save to history
    history_entry = {
        "timestamp": datetime.datetime.now().strftime("%H:%M:%S"),
        "bts_name": coverage_grid.bts_site.name,
        "frequency_mhz": float(selected_frequency),
        "model": prop_model,
        "env": env,
        "bts_height": float(bts_height_ovr),
        "coverage_pct": stats['coverage_pct'],
        "good_pct": stats['good_pct'],
        "avg_rssi": stats['avg_rssi']
    }
    st.session_state.history = [h for h in st.session_state.history if not (h["bts_name"] == history_entry["bts_name"] and abs(h["frequency_mhz"] - history_entry["frequency_mhz"]) < 0.1 and abs(h["bts_height"] - history_entry["bts_height"]) < 0.1 and h["model"] == history_entry["model"] and h["env"] == history_entry["env"])]
    st.session_state.history.insert(0, history_entry)
    st.session_state.history = st.session_state.history[:10]
    
    try:
        with open(os.path.join(cache_dir, "history.json"), 'w') as f:
            json.dump(st.session_state.history, f)
    except Exception:
        pass

# Render results
if st.session_state.get("simulation_run", False):
    coverage_grid = st.session_state.active_coverage_grid
    stats = coverage_grid.stats
    
    # 1. Update banners based on results
    if stats['coverage_pct'] >= 85.0:
        st.markdown(f"""
        <div class="banner-success">
            ✅ <b>{coverage_grid.bts_site.name} ({st.session_state.sim_bts_height:.1f}m)</b> covers <b>{stats['coverage_pct']}%</b> of the desired area. Recommended.
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="banner-warning">
            ⚠️ <b>{coverage_grid.bts_site.name}</b> only covers <b>{stats['coverage_pct']}%</b>. Consider increasing height or using an alternative location.
        </div>
        """, unsafe_allow_html=True)
        
    # KPI Metric Cards
    st.markdown(f"""
    <div class="kpi-container">
        <div class="kpi-card">
            <div class="kpi-title">Coverage Area</div>
            <div class="kpi-value">{stats['coverage_pct']}%</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-title">Good Signal</div>
            <div class="kpi-value">{stats['good_pct']}%</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-title">Avg RSSI (Covered)</div>
            <div class="kpi-value">{stats['avg_rssi']} dBm</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-title">Max Covered Range</div>
            <div class="kpi-value">{stats['max_range_km']} km</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # 2. Main Tabbed Layout
    result_tabs = st.tabs(["🗺 Coverage Heatmap", "🏔 Terrain & Site Comparisons", "📡 Client CPE Coverage List"])
    
    with result_tabs[0]:
        # Update Folium Map with Heatmap Overlay
        m_heat = folium.Map(location=[coverage_grid.bts_site.latitude, coverage_grid.bts_site.longitude], zoom_start=13, tiles="OpenStreetMap")
        for poly in polygons:
            folium.Polygon(locations=[[c[1], c[0]] for c in poly.coordinates], color="purple", weight=2, fill=True, fill_color="purple", fill_opacity=0.1).add_to(m_heat)
        for line in lines:
            folium.PolyLine(locations=[[c[1], c[0]] for c in line.coordinates], color="blue", weight=3).add_to(m_heat)
            
        geo_data = coverage_to_geojson(coverage_grid)
        folium.GeoJson(
            geo_data,
            style_function=lambda x: {
                "fillColor": x["properties"]["fill"],
                "color": x["properties"]["fill"],
                "weight": 0,
                "fillOpacity": x["properties"]["fill-opacity"]
            },
            tooltip=folium.GeoJsonTooltip(fields=["rssi"], aliases=["Signal RSSI (dBm):"])
        ).add_to(m_heat)
        
        for idx, site in enumerate(sites):
            is_active_bts = (site.name == coverage_grid.bts_site.name)
            if site.is_bts_candidate:
                icon_color = "red" if is_active_bts else "orange"
                icon_symbol = "tower"
            else:
                icon_color = "cadetblue"
                icon_symbol = "home"
                
            folium.Marker(location=[site.latitude, site.longitude], popup=f"<b>{site.name}</b><br>Type: {site.site_type}", tooltip=f"{site.name}", icon=folium.Icon(color=icon_color, icon=icon_symbol, prefix="fa")).add_to(m_heat)
            
        st.markdown("""
        <div class="legend-container">
            <span style="font-weight:700; color:#1B365D; font-size:13px; margin-right:10px;">Signal Bands:</span>
            <div class="legend-item"><div class="legend-dot" style="background:#2ecc71;"></div> Excellent (≥ -65 dBm)</div>
            <div class="legend-item"><div class="legend-dot" style="background:#27ae60;"></div> Good (-65 to -75 dBm)</div>
            <div class="legend-item"><div class="legend-dot" style="background:#f1c40f;"></div> Marginal (-75 to -85 dBm)</div>
            <div class="legend-item"><div class="legend-dot" style="background:#e74c3c;"></div> Weak (-85 to -90 dBm)</div>
        </div>
        """, unsafe_allow_html=True)
        
        st_map_heat = st_folium(m_heat, height=450, key="heatmap_map", use_container_width=True)
        
    with result_tabs[1]:
        col_out1, col_out2 = st.columns(2)
        with col_out1:
            st.markdown("#### 🏔 Terrain Profile")
            if terrain_grid.is_flat:
                st.info("Flat earth model active. Terrain profile is flat (0m).")
            else:
                non_bts_sites = [s for s in sites if not s.is_bts_candidate]
                if non_bts_sites:
                    target_site = non_bts_sites[0]
                elif len(sites) > 1:
                    other_sites = [s for s in sites if s.name != coverage_grid.bts_site.name]
                    target_site = other_sites[0] if other_sites else sites[0]
                else:
                    target_site = KMLPoint("Edge Point", min_lat, min_lon)
                    
                prof_data = get_profile(terrain_grid, coverage_grid.bts_site.latitude, coverage_grid.bts_site.longitude, target_site.latitude, target_site.longitude)
                df_prof = pd.DataFrame(prof_data, columns=["Distance (km)", "Elevation (m)"])
                st.caption(f"Elevation profile from BTS to {target_site.name}")
                st.line_chart(df_prof.set_index("Distance (km)"))
        with col_out2:
            st.markdown("#### 📊 Comparative Site Stats")
            if st.session_state.all_compares:
                df_compare = pd.DataFrame(st.session_state.all_compares)
                st.dataframe(df_compare.style.highlight_max(subset=["coverage_pct", "good_pct"], color="#d4edda"))
            else:
                st.write("Type a question like *'Compare all sites'* or click the run comparison button below.")
                
    with result_tabs[2]:
        st.markdown("#### 📡 Client CPE Coverage List")
        cpe_sites = [s for s in sites if not s.is_bts_candidate]
        if cpe_sites:
            cpe_data = []
            bts_specs = st.session_state.bts_specs
            cpe_specs = st.session_state.cpe_specs
            eirp = compute_eirp(bts_specs.tx_power_dbm, bts_specs.antenna_gain_dbi, bts_specs.cable_loss_db)
            
            for s in cpe_sites:
                d_km = haversine_distance(coverage_grid.bts_site.latitude, coverage_grid.bts_site.longitude, s.latitude, s.longitude)
                if d_km < 0.01:
                    d_km = 0.01
                    
                if st.session_state.sim_model == "terrain_aware" and not terrain_grid.is_flat:
                    loss_db, _, _ = terrain_aware_loss(coverage_grid.bts_site.latitude, coverage_grid.bts_site.longitude, st.session_state.sim_bts_height, s.latitude, s.longitude, s.height_m, st.session_state.sim_frequency, terrain_grid, st.session_state.sim_env)
                else:
                    loss_db = okumura_hata(d_km, st.session_state.sim_frequency, st.session_state.sim_bts_height, s.height_m, st.session_state.sim_env)
                    
                rssi = compute_rssi(loss_db, eirp, cpe_specs.antenna_gain_dbi, cpe_specs.cable_loss_db)
                margin = rssi - cpe_specs.receiver_sensitivity_dbm
                
                status = "🔴 Fail (No Signal)"
                if margin >= 10.0:
                    status = "🟢 Pass (Excellent)"
                elif margin >= 0.0:
                    status = "🟡 Pass (Marginal)"
                    
                cpe_data.append({
                    "Client Name": s.name,
                    "Distance (km)": round(d_km, 2),
                    "Elevation (m)": round(get_elevation(terrain_grid, s.latitude, s.longitude), 1),
                    "RSSI (dBm)": round(rssi, 1),
                    "Link Margin (dB)": round(margin, 1),
                    "Status": status
                })
                
            df_cpes = pd.DataFrame(cpe_data)
            st.dataframe(df_cpes, use_container_width=True)
            
            towrite = BytesIO()
            df_cpes.to_excel(towrite, index=False, header=True)
            towrite.seek(0)
            st.download_button(label="📥 Download CPE Results (Excel)", data=towrite.getvalue(), file_name=f"CPE_Coverage_Results_{coverage_grid.bts_site.name.replace(' ', '_')}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        else:
            st.info("No CPE sites found in the project file. Upload a KMZ or Excel with both BTS and CPE points to see this list.")

    # 4. Action Buttons & PDF Report
    edge_loss_db = stats["avg_rssi"]
    edge_dist_km = max(0.5, stats["max_range_km"])
    bts_specs = st.session_state.bts_specs
    cpe_specs = st.session_state.cpe_specs
    eirp = compute_eirp(bts_specs.tx_power_dbm, bts_specs.antenna_gain_dbi, bts_specs.cable_loss_db)
    
    if st.session_state.sim_model == "terrain_aware" and not terrain_grid.is_flat:
        edge_loss_db, _, _ = terrain_aware_loss(
            coverage_grid.bts_site.latitude, coverage_grid.bts_site.longitude, st.session_state.sim_bts_height,
            coverage_grid.bts_site.latitude + 0.02, coverage_grid.bts_site.longitude + 0.02, cpe_specs.antenna_height_default_m,
            st.session_state.sim_frequency, terrain_grid, st.session_state.sim_env
        )
    else:
        edge_loss_db = okumura_hata(edge_dist_km, st.session_state.sim_frequency, st.session_state.sim_bts_height, cpe_specs.antenna_height_default_m, st.session_state.sim_env)
        
    edge_rssi_dbm = compute_rssi(edge_loss_db, eirp, cpe_specs.antenna_gain_dbi, cpe_specs.cable_loss_db)
    edge_margin_db = edge_rssi_dbm - cpe_specs.receiver_sensitivity_dbm
    
    rec_text = f"The WiFrost TVWS coverage simulation for {coverage_grid.bts_site.name} at {st.session_state.sim_frequency:.1f} MHz achieves a total area coverage of {stats['coverage_pct']}% with a good signal ratio in {stats['good_pct']}% of cells. The link margin at the outer edge is estimated at {edge_margin_db:.1f} dB, which meets the standard criteria."
    if edge_margin_db < 6.0:
        rec_text += " WARNING: Link margin is critical. Field surveys or taller antennas are recommended."
        
    pdf_buffer = BytesIO()
    generate_pdf_report(
        output_stream=pdf_buffer,
        project_name=f"TVWS Coverage Report - {coverage_grid.bts_site.name}",
        prepared_by=f"Marcelo (WiFrost Sales Eng)",
        coverage_grid=coverage_grid,
        equipment_bts=bts_specs,
        equipment_cpe=cpe_specs,
        model_name="Terrain-Aware Hata" if st.session_state.sim_model == "terrain_aware" else "Flat Hata",
        environment=st.session_state.sim_env,
        edge_loss_db=edge_loss_db,
        edge_rssi_dbm=edge_rssi_dbm,
        edge_margin_db=edge_margin_db,
        conclusion_text=rec_text,
        all_sites_comparison=st.session_state.all_compares
    )
    
    st.markdown("---")
    col_dl_pdf, col_run_all = st.columns([1, 1])
    with col_dl_pdf:
        st.download_button(
            label="📄 Download PDF Link Budget Report",
            data=pdf_buffer.getvalue(),
            file_name=f"WiFrost_TVWS_Report_{coverage_grid.bts_site.name.replace(' ', '_')}.pdf",
            mime="application/pdf",
            use_container_width=True
        )
    with col_run_all:
        if len(bts_sites) > 1:
            if st.button("🔄 Compare All Candidate Sites", use_container_width=True):
                # Trigger a rerun with compare_all_sites action
                st.session_state.question_input = "Compare all sites"
                st.session_state.simulation_run = False # trigger new run
                st.rerun()
