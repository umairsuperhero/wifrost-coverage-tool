import os
import base64
import json
import hashlib
import tempfile
from io import BytesIO
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import numpy as np

# Import existing backend modules
from wifi_frost_defaults import WifrostBTS, WifrostCPE
from kml_parser import parse_kml_or_kmz, KMLData, KMLPoint, KMLPolygon, KMLLineString
from excel_parser import parse_excel_sites
from terrain import fetch_srtm, get_elevation, get_profile, haversine_distance, TerrainGrid
from propagation import (compute_eirp, compute_rssi, okumura_hata, terrain_aware_loss,
                          bearing as calc_bearing, best_sector_for_point, sector_gain)
from heatmap import compute_coverage_grid, coverage_to_geojson
from report import generate_pdf_report
import db

# Base Directory for database
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Load environment variables
load_dotenv()

app = FastAPI(title="WiFrost TVWS RF Coverage API")

# Configure CORS
# CORS_ORIGINS env var overrides defaults (comma-separated URLs).
# Falls back to allowing all localhost ports for local development.
_cors_env = os.getenv("CORS_ORIGINS", "")
if _cors_env:
    origins = [o.strip() for o in _cors_env.split(",") if o.strip()]
else:
    # Allow any localhost port in dev; Firebase domain added if set
    origins = ["http://localhost:3000", "http://localhost:3001",
               "http://localhost:3002", "http://localhost:8000",
               "http://127.0.0.1:3000", "http://127.0.0.1:3001",
               "http://127.0.0.1:3002", "http://127.0.0.1:8000"]

firebase_domain = os.getenv("FIREBASE_HOSTING_DOMAIN")
if firebase_domain:
    origins.append(firebase_domain)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

import hashlib

# In-memory cache for simulation results (keyed by parameter hash)
_simulation_cache: Dict[str, Any] = {}
_CACHE_MAX_SIZE = 20

# Pydantic models for request bodies
class SimulateRequest(BaseModel):
    site_index: int
    frequency_mhz: float
    eirp_dbm: float
    system_margin_db: float
    coverage_probability: str  # e.g., "90%" or "95%"
    model: str  # "terrain_aware" or "flat"
    environment: str = "suburban"
    srtm_key: Optional[str] = None
    gemini_key: Optional[str] = None
    # We also receive the parsed sites context to run calculations
    sites: List[Dict[str, Any]]
    polygons: Optional[List[Dict[str, Any]]] = []
    lines: Optional[List[Dict[str, Any]]] = []
    # Equipment specs overrides
    bts_height: float
    cpe_height: float
    cpe_sensitivity: float
    # Sector antenna configuration
    sector_azimuths: List[float] = [0]
    hpbw_deg: float = 65.0
    vpbw_deg: float = 17.0
    front_to_back_db: float = 25.0

class CpeAnalysisRequest(BaseModel):
    bts_index: int
    sites: List[Dict[str, Any]]
    frequency_mhz: float
    model: str
    environment: str
    bts_height: float
    tx_power_dbm: float
    antenna_gain_dbi: float
    cable_loss_db: float
    rx_gain_dbi: float
    rx_cable_loss_db: float
    rx_sensitivity_dbm: float
    # Sector antenna configuration
    sector_azimuths: List[float] = [0]
    hpbw_deg: float = 65.0
    front_to_back_db: float = 25.0

class GenerateReportRequest(BaseModel):
    project_name: str
    simulation_params: SimulateRequest
    stats: Dict[str, Any]
    plain_english_result: str
    three_scenarios: Optional[Dict[str, Any]] = None
    cpe_results: Optional[List[Dict[str, Any]]] = None

class TerrainProfileRequest(BaseModel):
    bts_latitude: float
    bts_longitude: float
    bts_height: float
    cpe_latitude: float
    cpe_longitude: float
    cpe_height: float
    frequency_mhz: float
    cpe_name: str
    sites: List[Dict[str, Any]]

@app.get("/api/defaults")
def get_defaults():
    """Retrieve pre-loaded WiFrost equipment default parameters."""
    bts = WifrostBTS()
    cpe = WifrostCPE()
    return {
        "bts": {
            "model_name": bts.model_name,
            "manufacturer": bts.manufacturer,
            "tx_power_dbm": bts.tx_power_dbm,
            "antenna_gain_dbi": bts.antenna_gain_dbi,
            "cable_loss_db": bts.cable_loss_db,
            "receiver_sensitivity_dbm": bts.receiver_sensitivity_dbm,
            "freq_min_mhz": bts.freq_min_mhz,
            "freq_max_mhz": bts.freq_max_mhz,
            "antenna_height_default_m": bts.antenna_height_default_m,
            "beamwidth_h_deg": bts.beamwidth_h_deg,
            "beamwidth_v_deg": bts.beamwidth_v_deg,
            "front_to_back_ratio": bts.front_to_back_ratio
        },
        "cpe": {
            "model_name": cpe.model_name,
            "manufacturer": cpe.manufacturer,
            "tx_power_dbm": cpe.tx_power_dbm,
            "antenna_gain_dbi": cpe.antenna_gain_dbi,
            "cable_loss_db": cpe.cable_loss_db,
            "receiver_sensitivity_dbm": cpe.receiver_sensitivity_dbm,
            "freq_min_mhz": cpe.freq_min_mhz,
            "freq_max_mhz": cpe.freq_max_mhz,
            "antenna_height_default_m": cpe.antenna_height_default_m,
            "beamwidth_h_deg": cpe.beamwidth_h_deg,
            "beamwidth_v_deg": cpe.beamwidth_v_deg
        }
    }

@app.post("/api/parse-file")
async def parse_file(file: UploadFile = File(...)):
    """Parse KMZ, KML, or Excel files containing coordinates."""
    # Limit upload size to 50 MB
    MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50 MB
    content_length = file.size
    if content_length and content_length > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail=f"File too large. Maximum size is 50 MB.")
    suffix = os.path.splitext(file.filename)[1].lower()
    if suffix not in ['.kmz', '.kml', '.xlsx']:
        raise HTTPException(status_code=400, detail="Invalid file type. Only .kmz, .kml, and .xlsx files are supported.")
        
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        if suffix in ['.kmz', '.kml']:
            parsed = parse_kml_or_kmz(tmp_path)
        else:
            parsed = parse_excel_sites(tmp_path)
            
        # Serialize KMLData to JSON-compatible dict
        return {
            "sites": [
                {
                    "name": s.name,
                    "latitude": s.latitude,
                    "longitude": s.longitude,
                    "description": s.description,
                    "is_bts_candidate": s.is_bts_candidate,
                    "height_m": s.height_m,
                    "site_type": s.site_type
                }
                for s in parsed.sites
            ],
            "polygons": [
                {
                    "name": p.name,
                    "coordinates": p.coordinates,
                    "description": p.description
                }
                for p in parsed.polygons
            ],
            "lines": [
                {
                    "name": l.name,
                    "coordinates": l.coordinates,
                    "description": l.description
                }
                for l in parsed.lines
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse file: {str(e)}")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

def build_bounding_box(sites, polygons, lines):
    """Calculate the padded bounding box coordinates around the project features."""
    lats = [s["latitude"] for s in sites]
    lons = [s["longitude"] for s in sites]
    for poly in polygons:
        lats.extend([c[1] for c in poly["coordinates"]])
        lons.extend([c[0] for c in poly["coordinates"]])
    for line in lines:
        lats.extend([c[1] for c in line["coordinates"]])
        lons.extend([c[0] for c in line["coordinates"]])
        
    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)
    
    pad_lat = 0.04
    pad_lon = 0.04 / math_cos_radians((min_lat + max_lat) / 2.0)
    
    return {
        "minLat": min_lat - pad_lat,
        "maxLat": max_lat + pad_lat,
        "minLon": min_lon - pad_lon,
        "maxLon": max_lon + pad_lon
    }

def math_cos_radians(deg):
    import math
    return math.cos(math.radians(deg))

@app.post("/api/simulate")
def simulate(req: SimulateRequest):
    """Run coverage grid computation and return GeoJSON + stats."""
    # Find active BTS
    if not req.sites:
        raise HTTPException(status_code=400, detail="No sites provided. Upload a file with at least one site.")
    bts_candidates = [s for s in req.sites if s["is_bts_candidate"]]
    if not bts_candidates:
        # Fallback to first site if none is BTS
        req.sites[0]["is_bts_candidate"] = True
        bts_candidates = [req.sites[0]]
        
    if req.site_index >= len(bts_candidates):
        raise HTTPException(status_code=400, detail=f"Active BTS index {req.site_index} is out of bounds.")
        
    active_bts_dict = bts_candidates[req.site_index]
    # Reconstruct KMLPoint
    active_bts = KMLPoint(
        name=active_bts_dict["name"],
        latitude=active_bts_dict["latitude"],
        longitude=active_bts_dict["longitude"],
        description=active_bts_dict.get("description", ""),
        is_bts_candidate=True,
        height_m=req.bts_height,
        site_type="BTS"
    )
    
    # Bounding box
    bounds = build_bounding_box(req.sites, req.polygons, req.lines)
    
    # Load keys
    srtm_key = req.srtm_key or os.getenv("OPENTOPOGRAPHY_API_KEY", "")
    
    # Fetch terrain
    terrain_grid = fetch_srtm(bounds, srtm_key)
    
    # Equipment specifications from defaults, with overrides
    eb = WifrostBTS()
    eb.antenna_height_default_m = req.bts_height
    # Adjust tx_power_dbm so compute_eirp matches requested eirp_dbm
    eb.tx_power_dbm = req.eirp_dbm - eb.antenna_gain_dbi + eb.cable_loss_db
    # Apply user-specified sector configuration
    eb.default_sectors = len(req.sector_azimuths)
    eb.sector_azimuths = list(req.sector_azimuths)
    eb.horizontal_beamwidth = req.hpbw_deg
    eb.front_to_back_ratio = req.front_to_back_db

    ec = WifrostCPE()
    ec.receiver_sensitivity_dbm = req.cpe_sensitivity
    ec.antenna_height_default_m = req.cpe_height

    env = req.environment

    # Generate standard coverage grid
    resolution_m = 100.0
    grid = compute_coverage_grid(
        bts_site=active_bts,
        equipment_bts=eb,
        equipment_cpe=ec,
        f_mhz=req.frequency_mhz,
        bounds=bounds,
        terrain_grid=terrain_grid,
        resolution_m=resolution_m,
        model=req.model,
        environment=env,
        bts_height_override=req.bts_height
    )
    
    # Generate three scenarios: Best, Realistic, Conservative
    # Realistic uses req.system_margin_db (e.g. 20 dB margin, meaning threshold RSSI = sensitivity + 20)
    # Best uses margin - 5 dB (e.g. 15 dB margin, threshold RSSI = sensitivity + 15)
    # Conservative uses margin + 5 dB (e.g. 25 dB margin, threshold RSSI = sensitivity + 25)
    margin_real = req.system_margin_db
    margin_best = max(0.0, margin_real - 5.0)
    margin_cons = margin_real + 5.0
    
    thresh_real = req.cpe_sensitivity + margin_real
    thresh_best = req.cpe_sensitivity + margin_best
    thresh_cons = req.cpe_sensitivity + margin_cons
    
    total_cells = grid.rssi_array.size
    
    # Compute scenarios coverage percentages
    cov_real = float((np.sum(grid.rssi_array >= thresh_real) / total_cells) * 100.0)
    cov_best = float((np.sum(grid.rssi_array >= thresh_best) / total_cells) * 100.0)
    cov_cons = float((np.sum(grid.rssi_array >= thresh_cons) / total_cells) * 100.0)
    
    good_real = float((np.sum(grid.rssi_array >= thresh_real + 10.0) / total_cells) * 100.0)
    good_best = float((np.sum(grid.rssi_array >= thresh_best + 10.0) / total_cells) * 100.0)
    good_cons = float((np.sum(grid.rssi_array >= thresh_cons + 10.0) / total_cells) * 100.0)
    
    avg_real = float(np.mean(grid.rssi_array[grid.rssi_array >= thresh_real])) if np.any(grid.rssi_array >= thresh_real) else -110.0
    avg_best = float(np.mean(grid.rssi_array[grid.rssi_array >= thresh_best])) if np.any(grid.rssi_array >= thresh_best) else -110.0
    avg_cons = float(np.mean(grid.rssi_array[grid.rssi_array >= thresh_cons])) if np.any(grid.rssi_array >= thresh_cons) else -110.0

    # Format result banner text
    plain_english = f"The site {active_bts.name} ({req.bts_height:.1f}m) covers {cov_real:.1f}% of the desired area at {req.frequency_mhz:.1f} MHz. Recommended."
    if cov_real < 85.0:
        plain_english = f"The site {active_bts.name} only covers {cov_real:.1f}%. Consider increasing height or using an alternative location."
        
    # Generate GeoJSON using threshold_dbm = thresh_best so frontend can filter dynamically
    geojson_data = coverage_to_geojson(grid, threshold_dbm=thresh_best)
    
    # Cache the result for report generation
    cache_key = hashlib.md5(json.dumps({
        "site_index": req.site_index,
        "frequency_mhz": req.frequency_mhz,
        "eirp_dbm": req.eirp_dbm,
        "bts_height": req.bts_height,
        "cpe_height": req.cpe_height,
        "environment": req.environment,
        "model": req.model,
    }, sort_keys=True).encode()).hexdigest()
    
    # Evict oldest entries if cache is full
    if len(_simulation_cache) >= _CACHE_MAX_SIZE:
        oldest_key = next(iter(_simulation_cache))
        del _simulation_cache[oldest_key]
    
    _simulation_cache[cache_key] = {
        "grid": grid,
        "terrain_grid": terrain_grid,
        "eb": eb,
        "ec": ec,
        "active_bts": active_bts,
    }

    # PERSIST TO SQLITE HISTORY
    history_id = None
    try:
        project_name = "WiFrost Project"
        history_id = db.save_run(
            base_dir=BASE_DIR,
            project_name=project_name,
            bts_name=active_bts.name,
            bts_lat=active_bts.latitude,
            bts_lon=active_bts.longitude,
            frequency_mhz=req.frequency_mhz,
            eirp_dbm=req.eirp_dbm,
            environment=req.environment,
            model=req.model,
            coverage_pct=round(cov_real, 1),
            max_range_km=grid.stats["max_range_km"],
            avg_rssi=round(avg_real, 1),
            params=req.dict(),
            stats={
                "coverage_pct": round(cov_real, 1),
                "good_pct": round(good_real, 1),
                "avg_rssi": round(avg_real, 1),
                "max_range_km": grid.stats["max_range_km"],
                "total_area_km2": grid.stats["total_area_km2"]
            },
            result={
                "plain_english_result": plain_english,
                "three_scenarios": {
                    "best": {
                        "coverage_pct": round(cov_best, 1),
                        "good_pct": round(good_best, 1),
                        "avg_rssi": round(avg_best, 1)
                    },
                    "realistic": {
                        "coverage_pct": round(cov_real, 1),
                        "good_pct": round(good_real, 1),
                        "avg_rssi": round(avg_real, 1)
                    },
                    "conservative": {
                        "coverage_pct": round(cov_cons, 1),
                        "good_pct": round(good_cons, 1),
                        "avg_rssi": round(avg_cons, 1)
                    }
                }
            },
            geojson=geojson_data
        )
    except Exception as e:
        print(f"Error saving simulation to history: {e}")

    return {
        "history_id": history_id,
        "coverage_geojson": geojson_data,
        "stats": {
            "coverage_pct": round(cov_real, 1),
            "good_pct": round(good_real, 1),
            "avg_rssi": round(avg_real, 1),
            "max_range_km": grid.stats["max_range_km"],
            "total_area_km2": grid.stats["total_area_km2"],
            "terrain_loaded": not terrain_grid.is_flat
        },
        "plain_english_result": plain_english,
        "three_scenarios": {
            "best": {
                "coverage_pct": round(cov_best, 1),
                "good_pct": round(good_best, 1),
                "avg_rssi": round(avg_best, 1)
            },
            "realistic": {
                "coverage_pct": round(cov_real, 1),
                "good_pct": round(good_real, 1),
                "avg_rssi": round(avg_real, 1)
            },
            "conservative": {
                "coverage_pct": round(cov_cons, 1),
                "good_pct": round(good_cons, 1),
                "avg_rssi": round(avg_cons, 1)
            }
        },
        "terrain_loaded": not terrain_grid.is_flat
    }

@app.post("/api/cpe-analysis")
def cpe_analysis(req: CpeAnalysisRequest):
    """Compute path loss and link budget details for all client CPE sites."""
    if not req.sites:
        raise HTTPException(status_code=400, detail="No sites provided. Upload a file with at least one site.")
    bts_candidates = [s for s in req.sites if s["is_bts_candidate"]]
    if not bts_candidates:
        req.sites[0]["is_bts_candidate"] = True
        bts_candidates = [req.sites[0]]
        
    if req.bts_index >= len(bts_candidates):
        raise HTTPException(status_code=400, detail=f"Active BTS index {req.bts_index} is out of bounds.")
        
    active_bts = bts_candidates[req.bts_index]
    
    # Bounding box
    bounds = build_bounding_box(req.sites, [], [])
    
    # Load key and fetch terrain
    srtm_key = os.getenv("OPENTOPOGRAPHY_API_KEY", "")
    terrain_grid = fetch_srtm(bounds, srtm_key)
    
    cpe_sites = [s for s in req.sites if not s["is_bts_candidate"]]
    cpe_results = []

    eirp = compute_eirp(req.tx_power_dbm, req.antenna_gain_dbi, req.cable_loss_db)
    multi_sector = len(req.sector_azimuths) > 1

    covered_count = 0

    for idx, s in enumerate(cpe_sites):
        d_km = haversine_distance(active_bts["latitude"], active_bts["longitude"], s["latitude"], s["longitude"])
        if d_km < 0.01:
            d_km = 0.01

        cpe_height = s.get("height_m") or 10.0

        if req.model == "terrain_aware" and not terrain_grid.is_flat:
            loss_db, _, _ = terrain_aware_loss(
                active_bts["latitude"], active_bts["longitude"], req.bts_height,
                s["latitude"], s["longitude"], cpe_height,
                req.frequency_mhz, terrain_grid, req.environment
            )
        else:
            loss_db = okumura_hata(d_km, req.frequency_mhz, req.bts_height, cpe_height, req.environment)

        # Sector gain — pick best-serving sector
        pt_bearing = calc_bearing(active_bts["latitude"], active_bts["longitude"],
                                   s["latitude"], s["longitude"])
        best_sec = best_sector_for_point(
            active_bts["latitude"], active_bts["longitude"],
            s["latitude"], s["longitude"],
            req.sector_azimuths, req.hpbw_deg, req.front_to_back_db
        )
        sg_db = sector_gain(pt_bearing, req.sector_azimuths[best_sec],
                            req.hpbw_deg, req.front_to_back_db)

        rssi = compute_rssi(loss_db, eirp, req.rx_gain_dbi, req.rx_cable_loss_db, sg_db)
        margin = rssi - req.rx_sensitivity_dbm

        status = "🔴 Fail (No Signal)"
        if margin >= 10.0:
            status = "🟢 Pass (Excellent)"
            covered_count += 1
        elif margin >= 0.0:
            status = "🟡 Pass (Marginal)"
            covered_count += 1

        cpe_results.append({
            "name": s["name"],
            "distance_km": round(d_km, 2),
            "elevation_m": round(get_elevation(terrain_grid, s["latitude"], s["longitude"]), 1),
            "rssi_dbm": round(rssi, 1),
            "margin_db": round(margin, 1),
            "status": status,
            "latitude": s["latitude"],
            "longitude": s["longitude"],
            "best_sector": best_sec,
            "best_sector_gain_db": round(sg_db, 1),
        })
        
    total_cpes = len(cpe_sites)
    coverage_pct = round((covered_count / total_cpes) * 100.0, 1) if total_cpes > 0 else 0.0
    
    return {
        "cpe_results": cpe_results,
        "summary_stats": {
            "total_cpes": total_cpes,
            "covered_cpes": covered_count,
            "coverage_pct": coverage_pct,
            "terrain_loaded": not terrain_grid.is_flat
        },
        "terrain_loaded": not terrain_grid.is_flat
    }

@app.post("/api/generate-report")
def generate_report(req: GenerateReportRequest):
    """Generate and return a Base64-encoded PDF link budget report."""
    sim_params = req.simulation_params
    
    # Try to use cached simulation data instead of re-running
    cache_key = hashlib.md5(json.dumps({
        "site_index": sim_params.site_index,
        "frequency_mhz": sim_params.frequency_mhz,
        "eirp_dbm": sim_params.eirp_dbm,
        "bts_height": sim_params.bts_height,
        "cpe_height": sim_params.cpe_height,
        "environment": sim_params.environment,
        "model": sim_params.model,
    }, sort_keys=True).encode()).hexdigest()
    
    cached = _simulation_cache.get(cache_key)
    if cached:
        grid = cached["grid"]
        terrain_grid = cached["terrain_grid"]
        eb = cached["eb"]
        ec = cached["ec"]
        active_bts = cached["active_bts"]
        env = sim_params.environment
    else:
        # Fallback: re-run simulation
        if not sim_params.sites:
            raise HTTPException(status_code=400, detail="No sites provided.")
        bts_candidates = [s for s in sim_params.sites if s["is_bts_candidate"]]
        if not bts_candidates:
            sim_params.sites[0]["is_bts_candidate"] = True
            bts_candidates = [sim_params.sites[0]]
            
        active_bts_dict = bts_candidates[sim_params.site_index]
        active_bts = KMLPoint(
            name=active_bts_dict["name"],
            latitude=active_bts_dict["latitude"],
            longitude=active_bts_dict["longitude"],
            description=active_bts_dict.get("description", ""),
            is_bts_candidate=True,
            height_m=sim_params.bts_height,
            site_type="BTS"
        )
        
        bounds = build_bounding_box(sim_params.sites, sim_params.polygons, sim_params.lines)
        srtm_key = sim_params.srtm_key or os.getenv("OPENTOPOGRAPHY_API_KEY", "")
        terrain_grid = fetch_srtm(bounds, srtm_key)
        
        eb = WifrostBTS()
        eb.antenna_height_default_m = sim_params.bts_height
        eb.tx_power_dbm = sim_params.eirp_dbm - eb.antenna_gain_dbi + eb.cable_loss_db

        ec = WifrostCPE()
        ec.receiver_sensitivity_dbm = sim_params.cpe_sensitivity
        ec.antenna_height_default_m = sim_params.cpe_height
        env = sim_params.environment

        grid = compute_coverage_grid(
            bts_site=active_bts,
            equipment_bts=eb,
            equipment_cpe=ec,
            f_mhz=sim_params.frequency_mhz,
            bounds=bounds,
            terrain_grid=terrain_grid,
            resolution_m=100.0,
            model=sim_params.model,
            environment=env,
            bts_height_override=sim_params.bts_height
        )
    
    # Calculate link metrics at cell edge
    eirp = compute_eirp(eb.tx_power_dbm, eb.antenna_gain_dbi, eb.cable_loss_db)
    edge_dist_km = max(0.5, grid.stats["max_range_km"])
    
    # Compute edge loss toward actual cell edge (use bearing from BTS)
    import math as _math
    edge_bearing_rad = _math.radians(45.0)  # NE diagonal as representative edge direction
    edge_lat = active_bts.latitude + (edge_dist_km / 111.32) * _math.cos(edge_bearing_rad)
    edge_lon = active_bts.longitude + (edge_dist_km / (111.32 * _math.cos(_math.radians(active_bts.latitude)))) * _math.sin(edge_bearing_rad)
    
    from propagation import terrain_aware_loss as _tal, shadowing_margin as _sm, ENVIRONMENT_SIGMA
    edge_pl = _tal(
        active_bts.latitude, active_bts.longitude, sim_params.bts_height,
        edge_lat, edge_lon, ec.antenna_height_default_m,
        sim_params.frequency_mhz, terrain_grid, env
    )
    
    edge_loss_db = edge_pl.total_db
    actual_diffraction_db = edge_pl.diffraction_db
    actual_clutter_db = edge_pl.clutter_db
    
    sigma = ENVIRONMENT_SIGMA.get(env, 4.0)
    actual_shadowing_90 = _sm(0.90, sigma)
    
    edge_rssi_dbm = compute_rssi(edge_loss_db, eirp, ec.antenna_gain_dbi, ec.cable_loss_db)
    edge_margin_db = edge_rssi_dbm - ec.receiver_sensitivity_dbm
    
    # PDF generation to memory
    pdf_buffer = BytesIO()
    generate_pdf_report(
        output_stream=pdf_buffer,
        project_name=req.project_name,
        prepared_by="Marcelo (WiFrost Sales Eng)",
        coverage_grid=grid,
        equipment_bts=eb,
        equipment_cpe=ec,
        model_name="Terrain-Aware Hata" if sim_params.model == "terrain_aware" else "Flat Hata",
        environment=env,
        conclusion_text=req.plain_english_result,
        stats=req.stats,
        three_scenarios=req.three_scenarios,
        cpe_results=req.cpe_results,
        frequency_mhz=sim_params.frequency_mhz,
        edge_loss_db=edge_loss_db,
        edge_rssi_dbm=edge_rssi_dbm,
        edge_margin_db=edge_margin_db,
        system_margin_db=sim_params.system_margin_db,
        shadowing_margin_90_db=actual_shadowing_90,
        clutter_db=actual_clutter_db,
        diffraction_db=actual_diffraction_db,
        terrain_grid=terrain_grid,
    )
    
    pdf_bytes = pdf_buffer.getvalue()
    pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")
    
    return {
        "pdf_base64": pdf_base64
    }

@app.post("/api/terrain-profile")
def terrain_profile(req: TerrainProfileRequest):
    """Generate the elevation profile and Fresnel zone coordinates between BTS and CPE."""
    import math
    min_lat = min(req.bts_latitude, req.cpe_latitude) - 0.02
    max_lat = max(req.bts_latitude, req.cpe_latitude) + 0.02
    min_lon = min(req.bts_longitude, req.cpe_longitude) - 0.02
    max_lon = max(req.bts_longitude, req.cpe_longitude) + 0.02
    
    bounds = {
        "minLat": min_lat,
        "maxLat": max_lat,
        "minLon": min_lon,
        "maxLon": max_lon
    }
    
    srtm_key = os.getenv("OPENTOPOGRAPHY_API_KEY", "")
    terrain_grid = fetch_srtm(bounds, srtm_key)
    
    if terrain_grid.is_flat:
        return {
            "profile": [],
            "label": "Terrain profile not available (flat earth mode active)",
            "is_flat": True
        }
        
    n_points = 100
    profile = get_profile(terrain_grid, req.bts_latitude, req.bts_longitude, req.cpe_latitude, req.cpe_longitude, n_points)
    
    distances = [p[0] for p in profile]
    elevations = [p[1] for p in profile]
    total_dist = distances[-1] if distances[-1] > 0 else 1.0
    
    bts_elev = get_elevation(terrain_grid, req.bts_latitude, req.bts_longitude)
    rx_elev = get_elevation(terrain_grid, req.cpe_latitude, req.cpe_longitude)
    H_tx = bts_elev + req.bts_height
    H_rx = rx_elev + req.cpe_height
    
    los_heights = [H_tx + (d / total_dist) * (H_rx - H_tx) for d in distances]
    
    fresnel_upper, fresnel_lower = [], []
    for i, d in enumerate(distances):
        d2 = total_dist - d
        if d > 0 and d2 > 0 and req.frequency_mhz > 0:
            r1 = 17.3 * math.sqrt((d * d2) / (req.frequency_mhz * total_dist))
            fresnel_upper.append(los_heights[i] + r1)
            fresnel_lower.append(los_heights[i] - r1)
        else:
            fresnel_upper.append(los_heights[i])
            fresnel_lower.append(los_heights[i])
            
    obstructed = False
    profile_data = []
    for i in range(len(distances)):
        d = distances[i]
        elev = elevations[i]
        los = los_heights[i]
        if elev > los:
            obstructed = True
        profile_data.append({
            "distance_km": round(d, 3),
            "terrain_m": round(elev, 1),
            "los_m": round(los, 1),
            "fresnel_lower_m": round(fresnel_lower[i], 1),
            "fresnel_upper_m": round(fresnel_upper[i], 1)
        })
        
    label = "⚠️ Terrain obstruction detected along path" if obstructed else "✅ Clear Line of Sight"
    
    return {
        "profile": profile_data,
        "label": label,
        "is_flat": False,
        "bts_elevation": round(bts_elev, 1),
        "cpe_elevation": round(rx_elev, 1),
        "bts_total_height": round(H_tx, 1),
        "cpe_total_height": round(H_rx, 1)
    }

@app.get("/api/history")
def get_history(limit: int = 10):
    """Retrieve the summary of recent simulation runs."""
    try:
        runs = db.list_runs(BASE_DIR, limit=limit)
        return {"runs": runs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve history: {str(e)}")

@app.get("/api/history/{run_id}")
def get_history_detail(run_id: str):
    """Retrieve full details of a specific simulation run."""
    try:
        run = db.get_run(BASE_DIR, run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Simulation run not found.")
        return run
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve simulation detail: {str(e)}")

@app.delete("/api/history/{run_id}")
def delete_history_run(run_id: str):
    """Delete a specific simulation run from history."""
    try:
        success = db.delete_run(BASE_DIR, run_id)
        if not success:
            raise HTTPException(status_code=404, detail="Simulation run not found.")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete simulation run: {str(e)}")

@app.post("/api/history/{run_id}/pdf")
def generate_history_pdf(run_id: str):
    """Generate a PDF report for a saved historical simulation run."""
    try:
        run = db.get_run(BASE_DIR, run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Simulation run not found.")
        
        # Extract params from run history record
        params_dict = run.get("params_json") or {}
        stats_dict = run.get("stats_json") or {}
        result_dict = run.get("result_json") or {}
        
        # Check if we have standard sites in params
        if "sites" not in params_dict:
            raise HTTPException(status_code=400, detail="Cannot generate report: missing sites in saved parameters.")
            
        # Parse active BTS
        bts_candidates = [s for s in params_dict["sites"] if s.get("is_bts_candidate")]
        if not bts_candidates:
            params_dict["sites"][0]["is_bts_candidate"] = True
            bts_candidates = [params_dict["sites"][0]]
            
        site_idx = params_dict.get("site_index", 0)
        if site_idx >= len(bts_candidates):
            site_idx = 0
            
        active_bts_dict = bts_candidates[site_idx]
        active_bts = KMLPoint(
            name=active_bts_dict["name"],
            latitude=active_bts_dict["latitude"],
            longitude=active_bts_dict["longitude"],
            description=active_bts_dict.get("description", ""),
            is_bts_candidate=True,
            height_m=params_dict.get("bts_height", 30.0),
            site_type="BTS"
        )
        
        # Build bounding box
        polys = params_dict.get("polygons", [])
        lines = params_dict.get("lines", [])
        bounds = build_bounding_box(params_dict["sites"], polys, lines)
        
        # Fetch terrain
        srtm_key = params_dict.get("srtm_key") or os.getenv("OPENTOPOGRAPHY_API_KEY", "")
        terrain_grid = fetch_srtm(bounds, srtm_key)
        
        # Reconstruct equipments
        eb = WifrostBTS()
        eb.antenna_height_default_m = params_dict.get("bts_height", 30.0)
        eb.tx_power_dbm = params_dict.get("eirp_dbm", 36.0) - eb.antenna_gain_dbi + eb.cable_loss_db
        # Azimuth and sector beamwidths
        eb.default_sectors = len(params_dict.get("sector_azimuths", [0]))
        eb.sector_azimuths = list(params_dict.get("sector_azimuths", [0]))
        eb.horizontal_beamwidth = params_dict.get("hpbw_deg", 65.0)
        eb.front_to_back_ratio = params_dict.get("front_to_back_db", 25.0)
        
        ec = WifrostCPE()
        ec.receiver_sensitivity_dbm = params_dict.get("cpe_sensitivity", -104.0)
        ec.antenna_height_default_m = params_dict.get("cpe_height", 10.0)
        env = params_dict.get("environment", "suburban")
        
        # Generate simulation grid
        grid = compute_coverage_grid(
            bts_site=active_bts,
            equipment_bts=eb,
            equipment_cpe=ec,
            f_mhz=params_dict.get("frequency_mhz", 470.0),
            bounds=bounds,
            terrain_grid=terrain_grid,
            resolution_m=100.0,
            model=params_dict.get("model", "terrain_aware"),
            environment=env,
            bts_height_override=params_dict.get("bts_height", 30.0)
        )
        
        # Calculate link metrics at cell edge
        eirp = compute_eirp(eb.tx_power_dbm, eb.antenna_gain_dbi, eb.cable_loss_db)
        edge_dist_km = max(0.5, grid.stats["max_range_km"])
        
        import math as _math
        edge_bearing_rad = _math.radians(45.0)
        edge_lat = active_bts.latitude + (edge_dist_km / 111.32) * _math.cos(edge_bearing_rad)
        edge_lon = active_bts.longitude + (edge_dist_km / (111.32 * _math.cos(_math.radians(active_bts.latitude)))) * _math.sin(edge_bearing_rad)
        
        from propagation import terrain_aware_loss as _tal, shadowing_margin as _sm, ENVIRONMENT_SIGMA
        edge_pl = _tal(
            active_bts.latitude, active_bts.longitude, params_dict.get("bts_height", 30.0),
            edge_lat, edge_lon, ec.antenna_height_default_m,
            params_dict.get("frequency_mhz", 470.0), terrain_grid, env
        )
        
        edge_loss_db = edge_pl.total_db
        actual_diffraction_db = edge_pl.diffraction_db
        actual_clutter_db = edge_pl.clutter_db
        
        sigma = ENVIRONMENT_SIGMA.get(env, 4.0)
        actual_shadowing_90 = _sm(0.90, sigma)
        
        edge_rssi_dbm = compute_rssi(edge_loss_db, eirp, ec.antenna_gain_dbi, ec.cable_loss_db)
        edge_margin_db = edge_rssi_dbm - ec.receiver_sensitivity_dbm
        
        pdf_buffer = BytesIO()
        generate_pdf_report(
            output_stream=pdf_buffer,
            project_name=run.get("project") or "WiFrost Project",
            prepared_by="Marcelo (WiFrost Sales Eng)",
            coverage_grid=grid,
            equipment_bts=eb,
            equipment_cpe=ec,
            model_name="Terrain-Aware Hata" if params_dict.get("model") == "terrain_aware" else "Flat Hata",
            environment=env,
            conclusion_text=result_dict.get("plain_english_result", ""),
            stats=stats_dict,
            three_scenarios=result_dict.get("three_scenarios"),
            cpe_results=None,
            frequency_mhz=params_dict.get("frequency_mhz", 470.0),
            edge_loss_db=edge_loss_db,
            edge_rssi_dbm=edge_rssi_dbm,
            edge_margin_db=edge_margin_db,
            system_margin_db=params_dict.get("system_margin_db", 0.0),
            shadowing_margin_90_db=actual_shadowing_90,
            clutter_db=actual_clutter_db,
            diffraction_db=actual_diffraction_db,
            terrain_grid=terrain_grid,
        )
        
        pdf_bytes = pdf_buffer.getvalue()
        pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")
        
        return {
            "pdf_base64": pdf_base64
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate historical PDF report: {str(e)}")
