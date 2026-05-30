import math
import numpy as np
from io import BytesIO
from PIL import Image, ImageDraw
from dataclasses import dataclass, field
from typing import Dict, Any, List, Tuple, Optional

from propagation import (terrain_aware_loss, okumura_hata, compute_eirp, compute_rssi,
                          haversine_distance, bearing, sector_gain,
                          get_sector_gain_for_point, best_sector_for_point,
                          PathLossResult, ENVIRONMENT_SIGMA, ENVIRONMENT_CLUTTER_LOSS,
                          shadowing_margin)
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
    return ""  # below -85 dBm = below minimum coverage threshold


def cpe_status(rssi: float) -> str:
    if rssi >= -65.0:
        return "🟢 Excellent"
    elif rssi >= -75.0:
        return "🟡 Good"
    elif rssi >= -85.0:
        return "🟠 Marginal"
    return "⛔ No Link"


def cpe_marker_color(rssi: float) -> str:
    if rssi >= -65.0:
        return "green"
    elif rssi >= -75.0:
        return "orange"
    elif rssi >= -85.0:
        return "lightred"
    return "gray"


def cpe_line_color(rssi: float) -> str:
    if rssi >= -65.0:
        return "#27ae60"
    elif rssi >= -75.0:
        return "#f39c12"
    elif rssi >= -85.0:
        return "#e67e22"
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

    # Sector params. Apply the directional pattern for ANY configured sector
    # (including a single panel) so the heat-map agrees with the CPE analysis
    # and the compass rose. A single 65° sector is NOT omnidirectional.
    n_sectors = getattr(equipment_bts, 'default_sectors', 1)
    raw_azimuths = getattr(equipment_bts, 'sector_azimuths', [0])
    hpbw = getattr(equipment_bts, 'horizontal_beamwidth', 90.0)
    ftb = getattr(equipment_bts, 'front_to_back_ratio', 25.0)
    active_azimuths = raw_azimuths[:max(1, n_sectors)] if raw_azimuths else None

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
    covered_cells = int(np.sum(rssi_array >= -85.0))
    good_cells = int(np.sum(rssi_array >= -75.0))
    excellent_cells = int(np.sum(rssi_array >= -65.0))

    coverage_pct = (covered_cells / total_cells * 100.0) if total_cells > 0 else 0.0
    good_pct = (good_cells / total_cells * 100.0) if total_cells > 0 else 0.0
    excellent_pct = (excellent_cells / total_cells * 100.0) if total_cells > 0 else 0.0

    covered_rssis = rssi_array[rssi_array >= -85.0]
    avg_rssi = float(np.mean(covered_rssis)) if len(covered_rssis) > 0 else -110.0

    max_range_km = 0.0
    for r in range(nrows):
        for c in range(ncols):
            if rssi_array[r, c] >= -85.0:
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
                          bts_height_override: Optional[float] = None,
                          system_margin_db: float = 18.0) -> List[Dict[str, Any]]:
    """Compute per-CPE link budget for every CPE site (three-scenario output)."""
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

    sigma = ENVIRONMENT_SIGMA.get(environment, 4.0)
    shad_90 = shadowing_margin(0.90, sigma)
    shad_95 = shadowing_margin(0.95, sigma)
    clutter = float(ENVIRONMENT_CLUTTER_LOSS.get(environment, 3))

    for cpe in cpe_sites:
        try:
            d_km = haversine_distance(bts_lat, bts_lon, cpe.latitude, cpe.longitude)
            if d_km < 0.01:
                d_km = 0.01

            pt_bearing = bearing(bts_lat, bts_lon, cpe.latitude, cpe.longitude)

            if active_azimuths:
                best_sec = best_sector_for_point(bts_lat, bts_lon,
                                                  cpe.latitude, cpe.longitude,
                                                  active_azimuths, hpbw, ftb)
                sg_db = sector_gain(pt_bearing, active_azimuths[best_sec], hpbw, ftb)
            else:
                best_sec = 0
                sg_db = 0.0

            # Always use terrain_aware_loss to get PathLossResult
            pl_result = terrain_aware_loss(
                bts_lat, bts_lon, bts_height,
                cpe.latitude, cpe.longitude, cpe.height_m,
                f_mhz, terrain_grid, environment)

            diffraction_loss = pl_result.diffraction_db
            eff_hb = pl_result.effective_hb_m

            # Optimistic: base + diffraction (no margins)
            rssi_opt = compute_rssi(pl_result.total_db, eirp,
                                    equipment_cpe.antenna_gain_dbi,
                                    equipment_cpe.cable_loss_db, sg_db)
            # Realistic: + shadowing 90% + system margin
            rssi_real = compute_rssi(pl_result.total_db + shad_90 + system_margin_db,
                                     eirp, equipment_cpe.antenna_gain_dbi,
                                     equipment_cpe.cable_loss_db, sg_db)
            # Pessimistic: + clutter + shadowing 95% + system margin
            rssi_pess = compute_rssi(pl_result.total_db + clutter + shad_95 + system_margin_db,
                                     eirp, equipment_cpe.antenna_gain_dbi,
                                     equipment_cpe.cable_loss_db, sg_db)

            # Use realistic RSSI as the primary displayed value
            rssi = rssi_real
            margin = rssi - equipment_cpe.receiver_sensitivity_dbm

            if terrain_grid.is_flat:
                fresnel = "Terrain data not loaded"
            elif diffraction_loss <= 0:
                fresnel = "✅ Clear LoS"
            else:
                fresnel = f"⚠️ {diffraction_loss:.1f} dB diffraction"

            results.append({
                "name": cpe.name,
                "lat": cpe.latitude,
                "lon": cpe.longitude,
                "distance_km": round(d_km, 2),
                "bearing_deg": round(pt_bearing, 1),
                "best_sector": best_sec,
                "sector_gain_db": round(sg_db, 1),
                "terrain_loss_db": round(pl_result.total_db, 1),
                "path_loss_db": round(pl_result.total_db, 1),
                "base_loss_db": round(pl_result.base_db, 1),
                "diffraction_db": round(diffraction_loss, 1),
                "clutter_db": round(clutter, 1),
                "shadowing_margin_90_db": round(shad_90, 1),
                "shadowing_margin_95_db": round(shad_95, 1),
                "system_margin_db": round(system_margin_db, 1),
                "effective_hb_m": round(eff_hb, 1),
                "rssi_dbm": round(rssi, 1),               # realistic (primary)
                "rssi_optimistic_dbm": round(rssi_opt, 1),
                "rssi_realistic_dbm": round(rssi_real, 1),
                "rssi_pessimistic_dbm": round(rssi_pess, 1),
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
                "base_loss_db": 0, "diffraction_db": 0,
                "clutter_db": 0, "shadowing_margin_90_db": 0,
                "shadowing_margin_95_db": 0, "system_margin_db": system_margin_db,
                "effective_hb_m": 0,
                "rssi_dbm": -999, "rssi_optimistic_dbm": -999,
                "rssi_realistic_dbm": -999, "rssi_pessimistic_dbm": -999,
                "link_margin_db": -999,
                "fresnel_clearance": "Error computing link",
                "status": "⛔ No Link",
                "marker_color": "gray", "line_color": "#95a5a6",
            })

    return results


# ── GeoJSON export ────────────────────────────────────────────────────────────

def coverage_to_geojson(coverage_grid: CoverageGrid,
                         threshold_dbm: float = -85.0) -> Dict[str, Any]:
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
    """Render RSSI grid as a PNG with coordinate labels for PDF embedding."""
    rssi_array = coverage_grid.rssi_array
    nrows, ncols = rssi_array.shape

    # Colour map
    COLOR_ABOVE = (245, 246, 250)   # below threshold — light grey background
    grid_img = Image.new('RGB', (ncols, nrows), color=COLOR_ABOVE)
    pixels = grid_img.load()
    for r in range(nrows):
        for c in range(ncols):
            rssi = rssi_array[r, c]
            if rssi >= -65.0:
                pixels[c, r] = (46, 204, 113)
            elif rssi >= -75.0:
                pixels[c, r] = (39, 174, 96)
            elif rssi >= -85.0:
                pixels[c, r] = (241, 196, 15)

    # Scale up for legibility in PDF
    new_w = max(480, ncols * 4)
    new_h = max(480, nrows * 4)
    img = grid_img.resize((new_w, new_h), Image.Resampling.NEAREST)

    draw = ImageDraw.Draw(img)

    # Border
    draw.rectangle([0, 0, new_w - 1, new_h - 1], outline=(80, 80, 80), width=2)

    # Coordinate labels at corners (lat/lon from grid)
    lats = coverage_grid.lats
    lons = coverage_grid.lons
    if len(lats) > 0 and len(lons) > 0:
        lat_n = f"{lats[0]:.4f}°N"
        lat_s = f"{lats[-1]:.4f}°N"
        lon_w = f"{lons[0]:.4f}°W" if lons[0] < 0 else f"{lons[0]:.4f}°E"
        lon_e = f"{lons[-1]:.4f}°W" if lons[-1] < 0 else f"{lons[-1]:.4f}°E"

        label_color = (60, 60, 60)
        pad = 6
        # Top-left
        draw.text((pad, pad), f"{lat_n}  {lon_w}", fill=label_color)
        # Top-right
        tr_text = f"{lat_n}  {lon_e}"
        draw.text((new_w - len(tr_text) * 6 - pad, pad), tr_text, fill=label_color)
        # Bottom-left
        draw.text((pad, new_h - 16), f"{lat_s}  {lon_w}", fill=label_color)
        # Center top — schematic note
        note = "RF Coverage Model — schematic (no basemap)"
        draw.text((new_w // 2 - len(note) * 3, new_h - 16), note, fill=(120, 120, 120))

    # North arrow (top-right corner)
    ax, ay = new_w - 30, 30
    draw.line([(ax, ay + 20), (ax, ay - 5)], fill=(40, 40, 40), width=2)
    draw.polygon([(ax - 5, ay), (ax + 5, ay), (ax, ay - 12)], fill=(40, 40, 40))
    draw.text((ax - 4, ay + 22), "N", fill=(40, 40, 40))

    buf = BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()
