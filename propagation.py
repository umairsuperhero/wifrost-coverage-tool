import math
import numpy as np
from typing import List, Tuple
from terrain import TerrainGrid, get_profile, get_elevation, haversine_distance

try:
    from scipy.stats import norm as _scipy_norm
    _HAS_SCIPY = True
except ImportError:
    _HAS_SCIPY = False


# ── Environment tables ────────────────────────────────────────────────────────

ENVIRONMENT_CLUTTER_LOSS: dict = {
    "open_water":        0,
    "open":              3,
    "port_industrial":  12,
    "suburban":          8,
    "vegetation_light":  6,
    "vegetation_dense": 15,
    "urban":            18,
}

ENVIRONMENT_SIGMA: dict = {
    "open_water":       4.0,
    "open":             4.0,
    "suburban":         6.0,
    "vegetation_light": 6.0,
    "vegetation_dense": 8.0,
    "port_industrial": 10.0,
    "urban":            8.0,
}


# ── Bearing & sector helpers ──────────────────────────────────────────────────

def bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return compass bearing in degrees 0-360 from point 1 to point 2."""
    dlon = math.radians(lon2 - lon1)
    lat1r = math.radians(lat1)
    lat2r = math.radians(lat2)
    x = math.sin(dlon) * math.cos(lat2r)
    y = math.cos(lat1r) * math.sin(lat2r) - math.sin(lat1r) * math.cos(lat2r) * math.cos(dlon)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def sector_gain(point_bearing: float, sector_azimuth: float,
                hpbw: float, front_to_back_ratio: float) -> float:
    """Return antenna gain offset in dB (0 = on-axis, negative = off-axis)."""
    off_axis = abs(point_bearing - sector_azimuth) % 360
    if off_axis > 180:
        off_axis = 360 - off_axis
    return -min(12.0 * (off_axis / hpbw) ** 2, front_to_back_ratio)


def get_sector_gain_for_point(bts_lat: float, bts_lon: float,
                               rx_lat: float, rx_lon: float,
                               sector_azimuths: List[float],
                               hpbw: float, front_to_back_ratio: float) -> float:
    """Return the best-sector gain (dB) from BTS toward a given point."""
    pt_bearing = bearing(bts_lat, bts_lon, rx_lat, rx_lon)
    return max(sector_gain(pt_bearing, az, hpbw, front_to_back_ratio)
               for az in sector_azimuths)


def best_sector_for_point(bts_lat: float, bts_lon: float,
                           rx_lat: float, rx_lon: float,
                           sector_azimuths: List[float],
                           hpbw: float, front_to_back_ratio: float) -> int:
    """Return the 0-based index of the sector that best serves the given point."""
    pt_bearing = bearing(bts_lat, bts_lon, rx_lat, rx_lon)
    gains = [sector_gain(pt_bearing, az, hpbw, front_to_back_ratio)
             for az in sector_azimuths]
    return gains.index(max(gains))


# ── Shadowing margin ──────────────────────────────────────────────────────────

def shadowing_margin(coverage_probability: float, sigma_db: float) -> float:
    """One-sided log-normal shadowing margin (dB) for a given location probability."""
    if _HAS_SCIPY:
        return float(_scipy_norm.ppf(coverage_probability) * sigma_db)
    # Piecewise-linear approximation when scipy is unavailable
    z_table = [(0.50, 0.000), (0.75, 0.674), (0.80, 0.842),
               (0.90, 1.282), (0.95, 1.645), (0.99, 2.326)]
    for i in range(len(z_table) - 1):
        p0, z0 = z_table[i]
        p1, z1 = z_table[i + 1]
        if p0 <= coverage_probability <= p1:
            t = (coverage_probability - p0) / (p1 - p0)
            return (z0 + t * (z1 - z0)) * sigma_db
    return 1.282 * sigma_db  # default ~90 %


# ── Water (two-ray) path loss ─────────────────────────────────────────────────

def water_path_loss(d_km: float, f_mhz: float, hb_m: float, hm_m: float = 3.0) -> float:
    """Two-ray ground-reflection model for open water / flat reflective surfaces."""
    d_km = max(0.01, d_km)
    hb_m = max(1.0, hb_m)
    hm_m = max(1.0, hm_m)
    two_ray = 40.0 * math.log10(d_km * 1000.0) - 20.0 * math.log10(hb_m) - 20.0 * math.log10(hm_m)
    fspl = 20.0 * math.log10(d_km) + 20.0 * math.log10(f_mhz) + 32.44
    return float(max(two_ray, fspl))


# ── Diffraction helpers ───────────────────────────────────────────────────────

def _knife_edge_loss(h_m: float, d1_m: float, d2_m: float, f_mhz: float) -> float:
    """ITU-R single knife-edge diffraction loss (dB). h above LoS in m; d1, d2 in m."""
    if d1_m <= 0 or d2_m <= 0 or f_mhz <= 0:
        return 0.0
    lambda_m = 300.0 / f_mhz
    v = h_m * math.sqrt(2.0 * (d1_m + d2_m) / (lambda_m * d1_m * d2_m))
    if v <= -0.7:
        return 0.0
    term = math.sqrt((v - 0.1) ** 2 + 1.0) + v - 0.1
    if term <= 0:
        return 0.0
    return max(0.0, 6.9 + 20.0 * math.log10(term))


_DEYGOUT_MAX_DEPTH = 3


def deygout_loss(profile: List[Tuple[float, float]],
                 h_tx_asl: float, h_rx_asl: float,
                 f_mhz: float, depth: int = 0) -> float:
    """
    Recursive Deygout multi-knife-edge diffraction loss (dB), capped at 30 dB.
    profile: list of (distance_km_from_tx, elevation_m_asl)
    h_tx_asl / h_rx_asl: antenna-tip heights above sea level (m)
    """
    if depth >= _DEYGOUT_MAX_DEPTH or len(profile) < 3:
        return 0.0

    d_total = profile[-1][0]
    if d_total <= 0:
        return 0.0

    # Find the dominant obstacle (highest Fresnel-Kirchhoff v)
    best_v = -9999.0
    best_idx = -1
    for i in range(1, len(profile) - 1):
        d1_km = profile[i][0]
        d2_km = d_total - d1_km
        if d1_km <= 0 or d2_km <= 0:
            continue
        los_h = h_tx_asl + (d1_km / d_total) * (h_rx_asl - h_tx_asl)
        h_above = profile[i][1] - los_h
        lambda_m = 300.0 / f_mhz
        d1_m, d2_m = d1_km * 1000.0, d2_km * 1000.0
        v = h_above * math.sqrt(2.0 * (d1_m + d2_m) / (lambda_m * d1_m * d2_m))
        if v > best_v:
            best_v = v
            best_idx = i

    if best_idx < 0 or best_v <= -0.7:
        return 0.0

    d1_km = profile[best_idx][0]
    d2_km = d_total - d1_km
    los_h = h_tx_asl + (d1_km / d_total) * (h_rx_asl - h_tx_asl)
    h_above = profile[best_idx][1] - los_h
    obs_elev = profile[best_idx][1]

    obs_loss = _knife_edge_loss(h_above, d1_km * 1000.0, d2_km * 1000.0, f_mhz)

    # Recurse into each sub-path
    left_profile = profile[:best_idx + 1]
    left_loss = deygout_loss(left_profile, h_tx_asl, obs_elev, f_mhz, depth + 1)

    right_raw = profile[best_idx:]
    offset = right_raw[0][0]
    right_shifted = [(d - offset, e) for d, e in right_raw]
    right_loss = deygout_loss(right_shifted, obs_elev, h_rx_asl, f_mhz, depth + 1)

    return min(obs_loss + left_loss + right_loss, 30.0)


# ── Okumura-Hata (corrected) ──────────────────────────────────────────────────

def okumura_hata(d_km: float, f_mhz: float, hb_m: float,
                 hm_m: float = 2.0, environment: str = 'open') -> float:
    """Path loss (dB) — Okumura-Hata. Open-area correction capped at 20 dB."""
    d_km = max(0.01, d_km)
    hb_m = max(1.0, hb_m)
    hm_m = max(1.0, hm_m)

    a_hm = (1.1 * math.log10(f_mhz) - 0.7) * hm_m - (1.56 * math.log10(f_mhz) - 0.8)
    loss = (69.55 + 26.16 * math.log10(f_mhz) - 13.82 * math.log10(hb_m) - a_hm
            + (44.9 - 6.55 * math.log10(hb_m)) * math.log10(d_km))

    if environment in ('open', 'open_water'):
        raw_corr = 4.78 * (math.log10(f_mhz)) ** 2 - 18.33 * math.log10(f_mhz) + 40.94
        loss -= min(raw_corr, 20.0)  # cap at 20 dB — the full ~27 dB is never achieved in practice
    elif environment in ('suburban', 'vegetation_light', 'vegetation_dense', 'port_industrial'):
        loss -= 2.0 * (math.log10(f_mhz / 28.0)) ** 2 + 5.4

    fspl = 20.0 * math.log10(d_km) + 20.0 * math.log10(f_mhz) + 32.44
    return float(max(loss, fspl))


# ── Path loss result ──────────────────────────────────────────────────────────

class PathLossResult:
    """
    Detailed path loss breakdown enabling three-scenario analysis.
    Backward-compatible: can be unpacked as (total_db, base_db, diffraction_db).
    """
    __slots__ = ('base_db', 'diffraction_db', 'clutter_db', 'effective_hb_m', 'environment')

    def __init__(self, base_db: float, diffraction_db: float, clutter_db: float,
                 effective_hb_m: float, environment: str = 'open'):
        self.base_db = base_db
        self.diffraction_db = diffraction_db
        self.clutter_db = clutter_db
        self.effective_hb_m = effective_hb_m
        self.environment = environment

    @property
    def total_db(self) -> float:
        """Optimistic total loss: base propagation + diffraction only."""
        return self.base_db + self.diffraction_db

    def scenario_loss(self, system_margin_db: float = 0.0,
                      coverage_probability: float = 0.0,
                      include_clutter: bool = False) -> float:
        """Total loss for a planning scenario (add shadowing + system margin + optional clutter)."""
        sigma = ENVIRONMENT_SIGMA.get(self.environment, 4.0)
        shad = shadowing_margin(coverage_probability, sigma) if coverage_probability > 0 else 0.0
        clutter = self.clutter_db if include_clutter else 0.0
        return self.base_db + self.diffraction_db + clutter + shad + system_margin_db

    def __iter__(self):
        """Backward-compatible iteration: yields (total_db, base_db, diffraction_db)."""
        yield self.total_db
        yield self.base_db
        yield self.diffraction_db


# ── Terrain-aware loss ────────────────────────────────────────────────────────

def terrain_aware_loss(bts_lat: float, bts_lon: float, bts_height_m: float,
                       rx_lat: float, rx_lon: float, rx_height_m: float,
                       f_mhz: float, terrain_grid: TerrainGrid,
                       environment: str = 'open') -> PathLossResult:
    """
    Path loss using corrected Okumura-Hata (effective height above CPE ground)
    plus full Deygout multi-edge diffraction.
    Returns PathLossResult — backward-compatible: unpack as (total, base, diffraction).
    """
    d_total = haversine_distance(bts_lat, bts_lon, rx_lat, rx_lon)

    bts_ground = get_elevation(terrain_grid, bts_lat, bts_lon) if not terrain_grid.is_flat else 0.0
    rx_ground  = get_elevation(terrain_grid, rx_lat,  rx_lon)  if not terrain_grid.is_flat else 0.0
    bts_asl = bts_ground + bts_height_m
    rx_asl  = rx_ground  + rx_height_m

    # Effective BTS height: antenna ASL minus CPE ground elevation, clamped to [30, 200] m
    hb_eff = float(max(30.0, min(200.0, bts_asl - rx_ground)))
    hm_eff = max(1.0, rx_height_m)

    clutter_db = float(ENVIRONMENT_CLUTTER_LOSS.get(environment, 3))

    if environment == 'open_water':
        base_loss = water_path_loss(max(d_total, 0.01), f_mhz, hb_eff, hm_eff)
    else:
        base_loss = okumura_hata(max(d_total, 0.01), f_mhz, hb_eff, hm_eff, environment)

    if terrain_grid.is_flat or d_total <= 0.05:
        return PathLossResult(base_loss, 0.0, clutter_db, hb_eff, environment)

    profile = get_profile(terrain_grid, bts_lat, bts_lon, rx_lat, rx_lon, n_points=100)
    diffraction = deygout_loss(profile, bts_asl, rx_asl, f_mhz)

    return PathLossResult(base_loss, diffraction, clutter_db, hb_eff, environment)


# ── Link budget helpers ───────────────────────────────────────────────────────

def compute_eirp(tx_power_dbm: float, tx_gain_dbi: float,
                 tx_cable_loss_db: float) -> float:
    """Calculate EIRP in dBm."""
    return tx_power_dbm + tx_gain_dbi - tx_cable_loss_db


def compute_rssi(path_loss_db: float, eirp_dbm: float,
                 rx_gain_dbi: float, rx_cable_loss_db: float,
                 sector_gain_db: float = 0.0) -> float:
    """Calculate RSSI at the CPE, optionally including sector antenna gain."""
    return eirp_dbm - path_loss_db + rx_gain_dbi - rx_cable_loss_db + sector_gain_db
