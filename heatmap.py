import math
import numpy as np
from io import BytesIO
from PIL import Image, ImageDraw
from dataclasses import dataclass, field
from typing import Dict, Any, List, Tuple, Optional

from propagation import (terrain_aware_loss, okumura_hata, compute_eirp, compute_rssi,
                          haversine_distance, bearing, sector_gain,
                          get_sector_gain_for_point, best_sector_for_point)
from terrain import TerrainGrid, get_elevation


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class CoverageGrid:
    rssi_array: np.ndarray
    lats: np.ndarray
    lons: np.ndarray
    stats: Dict[str, Any]
    bts_site: Any
    resolution_m: float
    model: str
    frequency_mhz: float


# ── Colour helpers ────────────────────────────────────────────────────────────

def get_rssi_color(rssi: float) -> str:
    if rssi >= -65.0:
        return "#2ecc71"
    elif rssi >= -75.0:
        return "#27ae60"
    elif rssi >= -85.0:
        return "#f1c40f"
    elif rssi >= -90.0:
        return "#e74c3c"
    return ""


def cpe_status(rssi: float) -> str:
    if rssi >= -65.0:
        return "🟢 Excellent"
    elif rssi >= -75.0:
        return "🟡 Good"
    elif rssi >= -85.0:
        return "🟠 Marginal"
    elif rssi >= -90.0:
        return "🔴 Weak"
    return "⛔ No Link"


def cpe_marker_color(rssi: float) -> str:
    if rssi >= -65.0:
        return "green"
    elif rssi >= -75.0:
        return "orange"
    elif rssi >= -85.0:
        return "lightred"
    elif rssi >= -90.0:
        return "red"
    return "gray"


def cpe_line_color(rssi: float) -> str:
    if rssi >= -65.0:
        return "#27ae60"
    elif rssi >= -75.0:
        return "#f39c12"
    elif rssi >= -85.0:
        return "#e67e22"
    elif rssi >= -90.0:
        return "#e74c3c"
    return "#95a5a6"


# ── Coverage grid ─────────────────────────────────────────────────────────────

def compute_coverage_grid(bts_site: Any, equipment_bts: Any, equipment_cpe: Any,
                          f_mhz: float, bounds: Dict[str, float],
                          terrain_grid: TerrainGrid,
                          resolution_m: float = 100.0,
                          model: str = 'terrain_aware',
                          environment: str = 'open',
                          bts_height_override: Optional[float] = None) -> CoverageGrid:
    """Generate a grid of RSSI values over the bounded area."""
    min_lat = bounds['minLat']
    max_lat = bounds['maxLat']
    min_lon = bounds['minLon']
    max_lon = bounds['maxLon']

    delta_lat = resolution_m / 111320.0
    lat_center = (min_lat + max_lat) / 2.0
    delta_lon = resolution_m / (111320.0 * math.cos(math.radians(lat_center)))

    lats = np.arange(max_lat, min_lat - delta_lat / 2, -delta_lat)
    lons = np.arange(min_lon, max_lon + delta_lon / 2, delta_lon)
    nrows, ncols = len(lats), len(lons)
    rssi_array = np.zeros((nrows, ncols))

    bts_lat = bts_site.latitude
    bts_lon = bts_site.longitude
    bts_height = bts_height_override if bts_height_override is not None else bts_site.height_m
    cpe_height = equipment_cpe.antenna_height_default_m

    eirp_dbm = compute_eirp(equipment_bts.tx_power_dbm,
                             equipment_bts.antenna_gain_dbi,
                             equipment_bts.cable_loss_db)
    rx_gain = equipment_cpe.antenna_gain_dbi
    rx_loss = equipment_cpe.cable_loss_db

    # Sector params (None when omni)
    n_sectors = getattr(equipment_bts, 'default_sectors', 1)
    raw_azimuths = getattr(equipment_bts, 'sector_azimuths', [0])
    hpbw = getattr(equipment_bts, 'horizontal_beamwidth', 90.0)
    ftb = getattr(equipment_bts, 'front_to_back_ratio', 25.0)
    active_azimuths = raw_azimuths[:n_sectors] if n_sectors > 1 else None

    for r in range(nrows):
        lat = lats[r]
        for c in range(ncols):
            lon = lons[c]
            d_km = haversine_distance(bts_lat, bts_lon, lat, lon)
            if d_km < 0.01:
                d_km = 0.01

            if model == 'terrain_aware':
                loss, _, _ = terrain_aware_loss(bts_lat, bts_lon, bts_height,
                                                lat, lon, cpe_height,
                                                f_mhz, terrain_grid, environment)
            else:
                loss = okumura_hata(d_km, f_mhz, bts_height, cpe_height, environment)

            sg_db = 0.0
            if active_azimuths:
                sg_db = get_sector_gain_for_point(bts_lat, bts_lon, lat, lon,
                                                   active_azimuths, hpbw, ftb)
            rssi_array[r, c] = compute_rssi(loss, eirp_dbm, rx_gain, rx_loss, sg_db)

    total_cells = nrows * ncols
    covered_cells = int(np.sum(rssi_array >= -90.0))
    good_cells = int(np.sum(rssi_array >= -75.0))
    excellent_cells = int(np.sum(rssi_array >= -65.0))

    coverage_pct = (covered_cells / total_cells * 100.0) if total_cells > 0 else 0.0
    good_pct = (good_cells / total_cells * 100.0) if total_cells > 0 else 0.0
    excellent_pct = (excellent_cells / total_cells * 100.0) if total_cells > 0 else 0.0

    covered_rssis = rssi_array[rssi_array >= -90.0]
    avg_rssi = float(np.mean(covered_rssis)) if len(covered_rssis) > 0 else -110.0

    max_range_km = 0.0
    for r in range(nrows):
        for c in range(ncols):
            if rssi_array[r, c] >= -90.0:
                dist = haversine_distance(bts_lat, bts_lon, lats[r], lons[c])
                if dist > max_range_km:
                    max_range_km = dist

    stats = {
        "coverage_pct": round(coverage_pct, 1),
        "good_pct": round(good_pct, 1),
        "excellent_pct": round(excellent_pct, 1),
        "avg_rssi": round(avg_rssi, 1),
        "max_range_km": round(max_range_km, 2),
        "total_area_km2": round((nrows * ncols * resolution_m ** 2) / 1e6, 2),
    }

    return CoverageGrid(rssi_array=rssi_array, lats=lats, lons=lons, stats=stats,
                        bts_site=bts_site, resolution_m=resolution_m,
                        model=model, frequency_mhz=f_mhz)


# ── CPE point-by-point analysis ───────────────────────────────────────────────

def compute_cpe_analysis(bts_site: Any, cpe_sites: List[Any],
                          equipment_bts: Any, equipment_cpe: Any,
                          f_mhz: float, terrain_grid: TerrainGrid,
                          model: str, environment: str,
                          bts_height_override: Optional[float] = None) -> List[Dict[str, Any]]:
    """Compute per-CPE link budget for every CPE site."""
    results = []
    bts_lat = bts_site.latitude
    bts_lon = bts_site.longitude
    bts_height = bts_height_override if bts_height_override is not None else bts_site.height_m

    eirp = compute_eirp(equipment_bts.tx_power_dbm,
                        equipment_bts.antenna_gain_dbi,
                        equipment_bts.cable_loss_db)

    n_sectors = getattr(equipment_bts, 'default_sectors', 1)
    raw_azimuths = getattr(equipment_bts, 'sector_azimuths', [0])
    hpbw = getattr(equipment_bts, 'horizontal_beamwidth', 90.0)
    ftb = getattr(equipment_bts, 'front_to_back_ratio', 25.0)
    active_azimuths = raw_azimuths[:n_sectors] if n_sectors > 1 else None

    for cpe in cpe_sites:
        try:
            d_km = haversine_distance(bts_lat, bts_lon, cpe.latitude, cpe.longitude)
            if d_km < 0.01:
                d_km = 0.01

            pt_bearing = bearing(bts_lat, bts_lon, cpe.latitude, cpe.longitude)

            # Sector analysis
            if active_azimuths:
                best_sec = best_sector_for_point(bts_lat, bts_lon,
                                                  cpe.latitude, cpe.longitude,
                                                  active_azimuths, hpbw, ftb)
                sg_db = sector_gain(pt_bearing, active_azimuths[best_sec], hpbw, ftb)
            else:
                best_sec = 0
                sg_db = 0.0

            # Propagation
            diffraction_loss = 0.0
            if model == 'terrain_aware' and not terrain_grid.is_flat:
                total_loss, base_loss, diffraction_loss = terrain_aware_loss(
                    bts_lat, bts_lon, bts_height,
                    cpe.latitude, cpe.longitude, cpe.height_m,
                    f_mhz, terrain_grid, environment)
                path_loss = total_loss
            else:
                path_loss = okumura_hata(d_km, f_mhz, bts_height,
                                         cpe.height_m, environment)

            rssi = compute_rssi(path_loss, eirp,
                                 equipment_cpe.antenna_gain_dbi,
                                 equipment_cpe.cable_loss_db, sg_db)
            margin = rssi - equipment_cpe.receiver_sensitivity_dbm

            if terrain_grid.is_flat:
                fresnel = "Terrain data not loaded"
            elif diffraction_loss <= 0:
                fresnel = "✅ Clear LoS"
            else:
                fresnel = f"⚠️ {diffraction_loss:.1f} dB diffraction loss"

            results.append({
                "name": cpe.name,
                "lat": cpe.latitude,
                "lon": cpe.longitude,
                "distance_km": round(d_km, 2),
                "bearing_deg": round(pt_bearing, 1),
                "best_sector": best_sec,
                "sector_gain_db": round(sg_db, 1),
                "terrain_loss_db": round(path_loss, 1),
                "path_loss_db": round(path_loss, 1),
                "rssi_dbm": round(rssi, 1),
                "link_margin_db": round(margin, 1),
                "fresnel_clearance": fresnel,
                "status": cpe_status(rssi),
                "marker_color": cpe_marker_color(rssi),
                "line_color": cpe_line_color(rssi),
            })
        except Exception:
            results.append({
                "name": cpe.name,
                "lat": cpe.latitude, "lon": cpe.longitude,
                "distance_km": round(d_km, 2) if 'd_km' in dir() else 0,
                "bearing_deg": 0, "best_sector": 0, "sector_gain_db": 0,
                "terrain_loss_db": 0, "path_loss_db": 0,
                "rssi_dbm": -999, "link_margin_db": -999,
                "fresnel_clearance": "Error computing link",
                "status": "⛔ No Link",
                "marker_color": "gray", "line_color": "#95a5a6",
            })

    return results


# ── GeoJSON export ────────────────────────────────────────────────────────────

def coverage_to_geojson(coverage_grid: CoverageGrid,
                         threshold_dbm: float = -90.0) -> Dict[str, Any]:
    features = []
    lats = coverage_grid.lats
    lons = coverage_grid.lons
    rssi_array = coverage_grid.rssi_array
    n_lats, n_lons = len(lats), len(lons)

    d_lat = abs(lats[0] - lats[1]) if n_lats > 1 else 0.001
    d_lon = abs(lons[1] - lons[0]) if n_lons > 1 else 0.001

    for r in range(n_lats):
        lat = lats[r]
        for c in range(n_lons):
            rssi = rssi_array[r, c]
            if rssi < threshold_dbm:
                continue
            color = get_rssi_color(rssi)
            if not color:
                continue
            west = lons[c] - d_lon / 2.0
            east = lons[c] + d_lon / 2.0
            south = lats[r] - d_lat / 2.0
            north = lats[r] + d_lat / 2.0
            coords = [[[west, south], [east, south], [east, north],
                        [west, north], [west, south]]]
            features.append({
                "type": "Feature",
                "properties": {
                    "rssi": round(rssi, 1),
                    "fill": color,
                    "fill-opacity": 0.4,
                    "stroke": False,
                    "weight": 0,
                },
                "geometry": {"type": "Polygon", "coordinates": coords},
            })

    return {"type": "FeatureCollection", "features": features}


# ── PNG image for PDF ─────────────────────────────────────────────────────────

def coverage_to_image(coverage_grid: CoverageGrid) -> bytes:
    rssi_array = coverage_grid.rssi_array
    nrows, ncols = rssi_array.shape
    img = Image.new('RGB', (ncols, nrows), color=(255, 255, 255))
    pixels = img.load()

    for r in range(nrows):
        for c in range(ncols):
            rssi = rssi_array[r, c]
            if rssi >= -65.0:
                color = (46, 204, 113)
            elif rssi >= -75.0:
                color = (39, 174, 96)
            elif rssi >= -85.0:
                color = (241, 196, 15)
            elif rssi >= -90.0:
                color = (231, 76, 60)
            else:
                color = (245, 246, 250)
            pixels[c, r] = color

    new_w = max(400, ncols * 4)
    new_h = max(400, nrows * 4)
    img_large = img.resize((new_w, new_h), Image.Resampling.BILINEAR)

    draw = ImageDraw.Draw(img_large)
    draw.rectangle([0, 0, new_w - 1, new_h - 1], outline=(120, 120, 120), width=2)

    buf = BytesIO()
    img_large.save(buf, format='PNG')
    return buf.getvalue()
