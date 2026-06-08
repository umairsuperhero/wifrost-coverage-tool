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
                          shadowing_margin, EFFECTIVE_EARTH_RADIUS_KM, DEYGOUT_MAX_LOSS_DB)
from terrain import TerrainGrid, get_elevation, get_elevation_np


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


# ── Margin-relative classification (single source of truth) ────────────────────
# Both the heatmap cells AND the CPE dots are classified by how far the MEDIAN RSSI
# clears the link threshold (= receiver sensitivity + system margin). Because the
# map and the CPE points use the same median-RSSI physics and the same threshold,
# a green heatmap cell can never host a red CPE dot — they agree by construction.

GOOD_HEADROOM_DB = 10.0
EXCELLENT_HEADROOM_DB = 20.0


def coverage_tier(rssi: float, threshold_dbm: float) -> int:
    """0 = no link, 1 = marginal (covered), 2 = good, 3 = excellent."""
    headroom = rssi - threshold_dbm
    if headroom >= EXCELLENT_HEADROOM_DB:
        return 3
    if headroom >= GOOD_HEADROOM_DB:
        return 2
    if headroom >= 0.0:
        return 1
    return 0


_TIER_FILL = {3: "#2ecc71", 2: "#27ae60", 1: "#f1c40f", 0: ""}
_TIER_MARKER = {3: "green", 2: "green", 1: "orange", 0: "gray"}
_TIER_LINE = {3: "#27ae60", 2: "#27ae60", 1: "#f39c12", 0: "#95a5a6"}
_TIER_STATUS = {3: "🟢 Excellent", 2: "🟢 Good", 1: "🟡 Marginal", 0: "⛔ No Link"}


def tier_fill_color(tier: int) -> str:
    return _TIER_FILL.get(tier, "")


def tier_marker_color(tier: int) -> str:
    return _TIER_MARKER.get(tier, "gray")


def tier_line_color(tier: int) -> str:
    return _TIER_LINE.get(tier, "#95a5a6")


def tier_status(tier: int) -> str:
    return _TIER_STATUS.get(tier, "⛔ No Link")


# ── Coverage grid ─────────────────────────────────────────────────────────────

# ── Vectorized propagation helpers ─────────────────────────────────────────────

def haversine_distance_np(lat1: float, lon1: float, lat2_arr: np.ndarray, lon2_arr: np.ndarray) -> np.ndarray:
    """Vectorized great-circle distance in kilometres."""
    R = 6371.0
    d_lat = np.radians(lat2_arr - lat1)
    d_lon = np.radians(lon2_arr - lon1)
    a = (np.sin(d_lat / 2.0) ** 2
         + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2_arr))
         * np.sin(d_lon / 2.0) ** 2)
    return R * 2.0 * np.arctan2(np.sqrt(a), np.sqrt(1.0 - a))


def bearing_np(lat1: float, lon1: float, lat2_arr: np.ndarray, lon2_arr: np.ndarray) -> np.ndarray:
    """Vectorized compass bearing in degrees 0-360."""
    dlon = np.radians(lon2_arr - lon1)
    lat1r = np.radians(lat1)
    lat2r = np.radians(lat2_arr)
    x = np.sin(dlon) * np.cos(lat2r)
    y = np.cos(lat1r) * np.sin(lat2r) - np.sin(lat1r) * np.cos(lat2r) * np.cos(dlon)
    return (np.degrees(np.arctan2(x, y)) + 360.0) % 360.0


def sector_gain_np(point_bearing: np.ndarray, sector_azimuth: float,
                   hpbw: float, front_to_back_ratio: float) -> np.ndarray:
    """Vectorized antenna sector gain offset in dB."""
    off_axis = np.abs(point_bearing - sector_azimuth) % 360.0
    off_axis = np.where(off_axis > 180.0, 360.0 - off_axis, off_axis)
    return -np.minimum(12.0 * (off_axis / hpbw) ** 2, front_to_back_ratio)


def get_sector_gain_for_point_np(bts_lat: float, bts_lon: float,
                                 rx_lat: np.ndarray, rx_lon: np.ndarray,
                                 sector_azimuths: List[float],
                                 hpbw: float, front_to_back_ratio: float) -> np.ndarray:
    """Vectorized best-sector gain from BTS toward all grid cells."""
    pt_bearing = bearing_np(bts_lat, bts_lon, rx_lat, rx_lon)
    gains = [sector_gain_np(pt_bearing, az, hpbw, front_to_back_ratio) for az in sector_azimuths]
    return np.maximum.reduce(gains)


def deygout_loss_np(d_arr: np.ndarray, e_arr: np.ndarray,
                    h_tx_asl: float, h_rx_asl: float,
                    f_mhz: float, depth: int = 0) -> float:
    """Recursive Deygout multi-knife-edge diffraction loss (dB), utilizing NumPy slices."""
    if depth >= 3 or len(d_arr) < 3:
        return 0.0

    d_total = d_arr[-1]
    if d_total <= 0:
        return 0.0

    # Intermediate points (exclude start and end)
    d1 = d_arr[1:-1]
    d2 = d_total - d1

    los_h = h_tx_asl + (d1 / d_total) * (h_rx_asl - h_tx_asl)
    h_above = e_arr[1:-1] - los_h

    lambda_m = 300.0 / f_mhz
    d1_m = d1 * 1000.0
    d2_m = d2 * 1000.0

    denom = lambda_m * d1_m * d2_m
    v = np.full_like(h_above, -9999.0)
    valid = denom > 0
    v[valid] = h_above[valid] * np.sqrt(2.0 * (d1_m[valid] + d2_m[valid]) / denom[valid])

    best_idx_rel = np.argmax(v)
    best_v = v[best_idx_rel]
    best_idx = best_idx_rel + 1

    if best_v <= -0.7:
        return 0.0

    term = math.sqrt((best_v - 0.1) ** 2 + 1.0) + best_v - 0.1
    obs_loss = max(0.0, 6.9 + 20.0 * math.log10(term)) if term > 0.0 else 0.0

    # Only recurse when the dominant edge genuinely protrudes above the line of
    # sight (best_v > 0). For a grazing / sub-LoS dominant edge there is just a
    # small single-edge Fresnel loss; recursing there would treat the smooth
    # earth-curvature bulge as a chain of phantom knife edges and pile up tens of
    # dB on a near-line-of-sight path. This MUST match propagation.deygout_loss so
    # the heatmap and the per-CPE link budget stay on identical physics.
    if best_v <= 0.0:
        return min(obs_loss, DEYGOUT_MAX_LOSS_DB)

    obs_elev = e_arr[best_idx]

    left_loss = deygout_loss_np(d_arr[:best_idx + 1], e_arr[:best_idx + 1],
                                 h_tx_asl, obs_elev, f_mhz, depth + 1)

    right_d = d_arr[best_idx:] - d_arr[best_idx]
    right_e = e_arr[best_idx:]
    right_loss = deygout_loss_np(right_d, right_e,
                                  obs_elev, h_rx_asl, f_mhz, depth + 1)

    return min(obs_loss + left_loss + right_loss, DEYGOUT_MAX_LOSS_DB)


# ── Coverage grid ─────────────────────────────────────────────────────────────

def compute_coverage_grid(bts_site: Any, equipment_bts: Any, equipment_cpe: Any,
                          f_mhz: float, bounds: Dict[str, float],
                          terrain_grid: TerrainGrid,
                          resolution_m: float = 100.0,
                          model: str = 'terrain_aware',
                          environment: str = 'open',
                          bts_height_override: Optional[float] = None,
                          landcover_grid: Any = None) -> CoverageGrid:
    """Generate a grid of RSSI values over the bounded area using parallel vectorized operations.

    If ``landcover_grid`` is provided and available, clutter loss varies per cell
    from ESA WorldCover land cover; otherwise a single environment-based clutter
    constant is used. The CPE link budget applies clutter the same way (at the
    receiver location), so the map and the per-CPE dots stay consistent.
    """
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

    # Vectorized computation of distances & bearings (meshgrid)
    lons_2d, lats_2d = np.meshgrid(lons, lats)
    distances_km = haversine_distance_np(bts_lat, bts_lon, lats_2d, lons_2d)
    
    # Clamp distance to 0.01 km minimum
    distances_km_clamped = np.maximum(0.01, distances_km)
    
    # Calculate ground heights
    bts_ground = get_elevation(terrain_grid, bts_lat, bts_lon) if not terrain_grid.is_flat else 0.0
    bts_asl = bts_ground + bts_height
    
    # Vectorized effective heights above CPE ground
    if not terrain_grid.is_flat:
        rx_grounds = get_elevation_np(terrain_grid, lats_2d, lons_2d)
    else:
        rx_grounds = np.zeros_like(lats_2d)
        
    hb_effs = np.clip(bts_asl - rx_grounds, 10.0, 200.0)
    hm_effs = np.maximum(1.0, cpe_height)

    # Initialize loss array
    loss_array = np.zeros((nrows, ncols))

    # Base propagation loss (Hata / two-ray)
    if environment == 'open_water':
        # Two-ray ground-reflection model vectorized
        two_ray = 40.0 * np.log10(distances_km_clamped * 1000.0) - 20.0 * np.log10(hb_effs) - 20.0 * np.log10(hm_effs)
        fspl = 20.0 * np.log10(distances_km_clamped) + 20.0 * math.log10(f_mhz) + 32.44
        loss_array = np.maximum(two_ray, fspl)
    else:
        # Okumura-Hata model vectorized
        a_hm = (1.1 * math.log10(f_mhz) - 0.7) * hm_effs - (1.56 * math.log10(f_mhz) - 0.8)
        loss = (69.55 + 26.16 * math.log10(f_mhz) - 13.82 * np.log10(hb_effs) - a_hm
                + (44.9 - 6.55 * np.log10(hb_effs)) * np.log10(distances_km_clamped))
        
        if environment in ('open', 'open_water'):
            raw_corr = 4.78 * (math.log10(f_mhz)) ** 2 - 18.33 * math.log10(f_mhz) + 40.94
            loss -= min(raw_corr, 20.0)
        elif environment in ('suburban', 'vegetation_light', 'vegetation_dense', 'port_industrial'):
            loss -= 2.0 * (math.log10(f_mhz / 28.0)) ** 2 + 5.4
            
        fspl = 20.0 * np.log10(distances_km_clamped) + 20.0 * math.log10(f_mhz) + 32.44
        loss_array = np.maximum(loss, fspl)

    # Clutter loss — per-pixel from land cover when available, else a single
    # environment constant. Applied at the receiver (cell) location.
    env_clutter_db = float(ENVIRONMENT_CLUTTER_LOSS.get(environment, 3))
    if landcover_grid is not None and getattr(landcover_grid, "available", False):
        clutter_array = landcover_grid.get_clutter_db_np(lats_2d, lons_2d, env_clutter_db)
    else:
        clutter_array = env_clutter_db
    loss_array += clutter_array

    # Terrain-aware model: compute per-cell diffraction loss. This runs even when
    # SRTM terrain is unavailable (is_flat) because the earth-curvature bulge alone
    # still imposes a realistic radio horizon; with terrain loaded it also captures
    # hill/ridge obstruction. The pure flat model (model != 'terrain_aware') skips
    # this for a quick, horizon-unlimited estimate.
    if model == 'terrain_aware':
        # Precompute profile coordinates for all cells
        t_points = np.linspace(0, 1.0, 100) # (100,)
        
        # 3D coordinate grids of shape (nrows, ncols, 100)
        lats_3d = bts_lat + t_points[np.newaxis, np.newaxis, :] * (lats_2d[:, :, np.newaxis] - bts_lat)
        lons_3d = bts_lon + t_points[np.newaxis, np.newaxis, :] * (lons_2d[:, :, np.newaxis] - bts_lon)
        
        # Get elevations for all profile points at once (O(1) database/cache roundtrip)
        elevations_flat = get_elevation_np(terrain_grid, lats_3d.ravel(), lons_3d.ravel())
        elevations_3d = elevations_flat.reshape(nrows, ncols, 100)

        diffraction_array = np.zeros((nrows, ncols))
        rx_asls = rx_grounds + cpe_height

        for r in range(nrows):
            for c in range(ncols):
                dist_km = distances_km[r, c]
                if dist_km <= 0.05:
                    continue
                d_arr = dist_km * t_points
                # Add earth-curvature bulge so beyond-horizon paths are correctly
                # obstructed (realistic radio horizon) rather than appearing as LoS.
                bulge = (d_arr * (dist_km - d_arr)) / (2.0 * EFFECTIVE_EARTH_RADIUS_KM) * 1000.0
                e_arr = elevations_3d[r, c] + bulge
                diffraction_array[r, c] = deygout_loss_np(d_arr, e_arr, bts_asl, rx_asls[r, c], f_mhz)
                
        loss_array += diffraction_array

    # Sector Gain
    sg_db = np.zeros((nrows, ncols))
    if active_azimuths:
        sg_db = get_sector_gain_for_point_np(bts_lat, bts_lon, lats_2d, lons_2d,
                                             active_azimuths, hpbw, ftb)

    # Final RSSI array
    rssi_array = eirp_dbm - loss_array + rx_gain - rx_loss + sg_db

    # Compute statistics
    total_cells = nrows * ncols
    covered_cells = int(np.sum(rssi_array >= -85.0))
    good_cells = int(np.sum(rssi_array >= -75.0))
    excellent_cells = int(np.sum(rssi_array >= -65.0))

    coverage_pct = (covered_cells / total_cells * 100.0) if total_cells > 0 else 0.0
    good_pct = (good_cells / total_cells * 100.0) if total_cells > 0 else 0.0
    excellent_pct = (excellent_cells / total_cells * 100.0) if total_cells > 0 else 0.0

    covered_rssis = rssi_array[rssi_array >= -85.0]
    avg_rssi = float(np.mean(covered_rssis)) if len(covered_rssis) > 0 else -110.0

    # Max range calculation (fast vectorized)
    if covered_cells > 0:
        max_range_km = float(np.max(distances_km[rssi_array >= -85.0]))
    else:
        max_range_km = 0.0

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


def merge_coverage_grids(grids: List[CoverageGrid], resolution_m: float = 100.0) -> CoverageGrid:
    """Consolidate multiple individual CoverageGrid instances into a single merged grid by taking the max RSSI."""
    if not grids:
        raise ValueError("No coverage grids to merge.")
    
    shape = grids[0].rssi_array.shape
    for g in grids:
        if g.rssi_array.shape != shape:
            raise ValueError("All grids must have the identical shape to be merged.")
            
    merged_rssi = np.full(shape, -999.0)
    for g in grids:
        merged_rssi = np.maximum(merged_rssi, g.rssi_array)
        
    nrows, ncols = shape
    total_cells = nrows * ncols
    covered_cells = int(np.sum(merged_rssi >= -85.0))
    good_cells = int(np.sum(merged_rssi >= -75.0))
    excellent_cells = int(np.sum(merged_rssi >= -65.0))

    coverage_pct = (covered_cells / total_cells * 100.0) if total_cells > 0 else 0.0
    good_pct = (good_cells / total_cells * 100.0) if total_cells > 0 else 0.0
    excellent_pct = (excellent_cells / total_cells * 100.0) if total_cells > 0 else 0.0

    covered_rssis = merged_rssi[merged_rssi >= -85.0]
    avg_rssi = float(np.mean(covered_rssis)) if len(covered_rssis) > 0 else -110.0
    max_range_km = float(max(g.stats["max_range_km"] for g in grids))

    stats = {
        "coverage_pct": round(coverage_pct, 1),
        "good_pct": round(good_pct, 1),
        "excellent_pct": round(excellent_pct, 1),
        "avg_rssi": round(avg_rssi, 1),
        "max_range_km": round(max_range_km, 2),
        "total_area_km2": round((nrows * ncols * resolution_m ** 2) / 1e6, 2),
    }

    class DummyBTS:
        name = "All Towers (Consolidated)"
        latitude = float(np.mean([g.bts_site.latitude for g in grids])) if hasattr(grids[0].bts_site, 'latitude') else 0.0
        longitude = float(np.mean([g.bts_site.longitude for g in grids])) if hasattr(grids[0].bts_site, 'longitude') else 0.0
        height_m = float(np.mean([g.bts_site.height_m for g in grids])) if hasattr(grids[0].bts_site, 'height_m') else 30.0
        is_bts_candidate = True
        site_type = "BTS"

    return CoverageGrid(
        rssi_array=merged_rssi,
        lats=grids[0].lats,
        lons=grids[0].lons,
        stats=stats,
        bts_site=DummyBTS(),
        resolution_m=resolution_m,
        model=grids[0].model,
        frequency_mhz=grids[0].frequency_mhz
    )


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

            # Median (50% locations): deterministic path loss, no shadowing margin.
            # This is the physical signal level — and it is the SAME quantity the
            # heatmap grid plots, so map cells and CPE dots are directly comparable.
            rssi_median = compute_rssi(pl_result.total_db, eirp,
                                       equipment_cpe.antenna_gain_dbi,
                                       equipment_cpe.cable_loss_db, sg_db)
            # Realistic (90% locations): minus shadowing fade margin.
            rssi_real = compute_rssi(pl_result.total_db + shad_90,
                                     eirp, equipment_cpe.antenna_gain_dbi,
                                     equipment_cpe.cable_loss_db, sg_db)
            # Conservative (95% locations): minus clutter + 95% shadowing.
            rssi_pess = compute_rssi(pl_result.total_db + clutter + shad_95,
                                     eirp, equipment_cpe.antenna_gain_dbi,
                                     equipment_cpe.cable_loss_db, sg_db)

            # Primary displayed value = median RSSI. Classification is margin-relative:
            # tier is decided by how far the median clears (sensitivity + system margin),
            # identical to the heatmap. link_margin = median above the receiver floor.
            rssi = rssi_median
            link_threshold = equipment_cpe.receiver_sensitivity_dbm + system_margin_db
            tier = coverage_tier(rssi_median, link_threshold)
            margin = rssi_median - equipment_cpe.receiver_sensitivity_dbm

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
                "rssi_dbm": round(rssi, 1),               # median (primary, matches heatmap)
                "rssi_optimistic_dbm": round(rssi_median, 1),
                "rssi_realistic_dbm": round(rssi_real, 1),
                "rssi_pessimistic_dbm": round(rssi_pess, 1),
                "link_margin_db": round(margin, 1),
                "fresnel_clearance": fresnel,
                "status": tier_status(tier),
                "marker_color": tier_marker_color(tier),
                "line_color": tier_line_color(tier),
            })
        except Exception:
            results.append({
                "name": cpe.name,
                "lat": cpe.latitude, "lon": cpe.longitude,
                "distance_km": round(d_km, 2) if 'd_km' in locals() else 0,
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
        c = 0
        while c < n_lons:
            rssi = rssi_array[r, c]
            if rssi < threshold_dbm:
                c += 1
                continue
            color = tier_fill_color(coverage_tier(rssi, threshold_dbm))
            if not color:
                c += 1
                continue

            # Start of a contiguous run of cells with the same color
            c_start = c
            c += 1
            while c < n_lons:
                next_rssi = rssi_array[r, c]
                if next_rssi < threshold_dbm:
                    break
                next_color = tier_fill_color(coverage_tier(next_rssi, threshold_dbm))
                if next_color != color:
                    break
                c += 1
            c_end = c - 1
            
            # Create a single merged horizontal rectangle polygon
            west = lons[c_start] - d_lon / 2.0
            east = lons[c_end] + d_lon / 2.0
            south = lats[r] - d_lat / 2.0
            north = lats[r] + d_lat / 2.0
            
            coords = [[[west, south], [east, south], [east, north],
                        [west, north], [west, south]]]
            
            # Use mean RSSI of the merged run for properties
            avg_rssi = float(np.mean(rssi_array[r, c_start:c_end + 1]))
            
            features.append({
                "type": "Feature",
                "properties": {
                    "rssi": round(avg_rssi, 1),
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
