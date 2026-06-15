import math
import numpy as np
from typing import List, Tuple, Optional
from terrain import TerrainGrid, get_profile, get_elevation, haversine_distance

try:
    from scipy.stats import norm as _scipy_norm
    _HAS_SCIPY = True
except ImportError:
    _HAS_SCIPY = False


# ── Model constants (documented so the physics is auditable) ───────────────────

# 4/3-earth effective radius (km). Used to add the earth-curvature "bulge" to a
# terrain profile so that beyond-horizon paths are correctly obstructed instead of
# appearing as clear line-of-sight. a_e = (4/3) * 6371 km ≈ 8493 km.
EFFECTIVE_EARTH_RADIUS_KM = 8493.0

# Maximum diffraction loss attributed to a single Deygout obstruction chain (dB).
# Raised from the original 30 dB so that horizon/curvature shadowing can dominate
# at long range (a deeply obstructed path should not look only ~30 dB down).
DEYGOUT_MAX_LOSS_DB = 40.0

# Open-area Hata correction is capped (dB). The full Hata open correction is
# ~27 dB at 600 MHz; real deployments rarely realise the full value (scattered
# clutter, imperfect siting), so it is capped for a defensible, slightly
# conservative estimate. Tunable.
OPEN_AREA_CORRECTION_CAP_DB = 20.0

# Effective BTS height is clamped to this range (m) before entering Hata, which is
# only valid for 30–200 m base heights. The low clamp also avoids log10 of tiny/
# negative effective heights over high terrain.
HB_EFF_MIN_M = 10.0
HB_EFF_MAX_M = 200.0


# Effective BTS height limits for Hata (legacy fallback)
HB_EFF_MIN_M = 10.0
HB_EFF_MAX_M = 200.0

try:
    from itmlogic.preparatory_subroutines.qlrps import qlrps
    from itmlogic.preparatory_subroutines.qlrpfl import qlrpfl
    from itmlogic.statistics.avar import avar
    HAS_ITMLOGIC = True
except ImportError:
    HAS_ITMLOGIC = False


# ── Environment tables ────────────────────────────────────────────────────────

ENVIRONMENT_CLUTTER_LOSS: dict = {
    "open_water":        0,
    "open":              3,
    "port_industrial":  12,
    "suburban":          8,
    "vegetation_light":  6,
    "vegetation_dense": 15,
    "urban":             8,
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
                point_elevation: float, mdt_deg: float,
                hpbw: float, vpbw: float, front_to_back_ratio: float) -> float:
    """Return antenna gain offset in dB (0 = on-axis, negative = off-axis)."""
    off_axis_h = abs(point_bearing - sector_azimuth) % 360
    if off_axis_h > 180:
        off_axis_h = 360 - off_axis_h
    h_loss = 12.0 * (off_axis_h / hpbw) ** 2
    
    off_axis_v = point_elevation - (-mdt_deg)
    v_loss = 12.0 * (off_axis_v / vpbw) ** 2
    
    return -min(h_loss + v_loss, front_to_back_ratio)


def get_sector_gain_for_point(bts_lat: float, bts_lon: float, bts_z_asl: float,
                               rx_lat: float, rx_lon: float, rx_z_asl: float,
                               sector_azimuths: List[float], mdt_deg: float,
                               hpbw: float, vpbw: float, front_to_back_ratio: float) -> float:
    """Return the best-sector gain (dB) from BTS toward a given point."""
    pt_bearing = bearing(bts_lat, bts_lon, rx_lat, rx_lon)
    dist_m = haversine_distance(bts_lat, bts_lon, rx_lat, rx_lon) * 1000.0
    pt_elevation = math.degrees(math.atan2(rx_z_asl - bts_z_asl, dist_m)) if dist_m > 0 else 0.0
    return max(sector_gain(pt_bearing, az, pt_elevation, mdt_deg, hpbw, vpbw, front_to_back_ratio)
               for az in sector_azimuths)


def best_sector_for_point(bts_lat: float, bts_lon: float, bts_z_asl: float,
                           rx_lat: float, rx_lon: float, rx_z_asl: float,
                           sector_azimuths: List[float], mdt_deg: float,
                           hpbw: float, vpbw: float, front_to_back_ratio: float) -> int:
    """Return the 0-based index of the sector that best serves the given point."""
    pt_bearing = bearing(bts_lat, bts_lon, rx_lat, rx_lon)
    dist_m = haversine_distance(bts_lat, bts_lon, rx_lat, rx_lon) * 1000.0
    pt_elevation = math.degrees(math.atan2(rx_z_asl - bts_z_asl, dist_m)) if dist_m > 0 else 0.0
    gains = [sector_gain(pt_bearing, az, pt_elevation, mdt_deg, hpbw, vpbw, front_to_back_ratio)
             for az in sector_azimuths]
    return gains.index(max(gains))


# ── Shadowing margin ──────────────────────────────────────────────────────────

def shadowing_margin(coverage_probability: float, sigma_db: float) -> float:
    """One-sided log-normal shadowing margin (dB) for a given location probability."""
    if coverage_probability < 0.50:
        return 0.0  # no margin needed below 50% probability
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
    # Probability below 0.50 or above 0.99 — use 90% as safe default
    if coverage_probability < 0.50:
        return 0.0  # no margin needed below 50% probability
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


# ── ITM Longley-Rice ──────────────────────────────────────────────────────────

def itm_longley_rice(profile_m: List[float], dz_m: float,
                     f_mhz: float, hb_m: float, hm_m: float) -> Tuple[float, float]:
    """
    Calculates ITM Longley-Rice path loss over irregular terrain.
    Returns: (free_space_loss_db, attenuation_relative_to_free_space_db)
    """
    if not HAS_ITMLOGIC:
        # Graceful fallback to pure FSPL if library is missing
        d_km = max(0.001, (len(profile_m) - 1) * dz_m / 1000.0)
        fspl = 20.0 * math.log10(d_km) + 20.0 * math.log10(f_mhz) + 32.44
        return fspl, 0.0

    N = len(profile_m) - 1
    elev_profile = [float(N), float(dz_m)] + [float(e) for e in profile_m]
    
    # 5 = Continental Temperate climate. 
    # 301.0 = Average surface refractivity
    # 15.0 = Average ground dielectric, 0.005 = Average ground conductivity
    prop = {
        'kwx': 0, 'mdp': -1, 'lvar': 0,
        'pfl': elev_profile,
        'hg': [float(hb_m), float(hm_m)],
        'mdvarx': 5,
        'klimx': 5
    }
    
    # 1 = Vertical polarization
    wn, gme, ens, zgnd = qlrps(float(f_mhz), 0.0, 301.0, 1, 15.0, 0.005)
    prop.update({'wn': wn, 'gme': gme, 'ens': ens, 'zgnd': zgnd})
    
    prop = qlrpfl(prop)
    # 0.0 means 50% reliability and confidence (median loss)
    fs, prop = avar(0.0, 0.0, 0.0, prop)
    
    dist_km = prop['dist'] / 1000.0
    fspl = 32.4 + 20 * math.log10(max(f_mhz, 1.0)) + 20 * math.log10(max(dist_km, 0.001))
    
    diffraction = prop['aref'] + fs
    return fspl, diffraction


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
        """Total path loss: base propagation + diffraction + clutter."""
        return self.base_db + self.diffraction_db + self.clutter_db

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
                       environment: str = 'open',
                       clutter_db_override: Optional[float] = None) -> PathLossResult:
    """
    Path loss using corrected Okumura-Hata (effective height above CPE ground)
    plus full Deygout multi-edge diffraction.
    Returns PathLossResult — backward-compatible: unpack as (total, base, diffraction).
    """
    d_total = haversine_distance(bts_lat, bts_lon, rx_lat, rx_lon)

    # Warn if frequency is outside Okumura-Hata validity range
    if f_mhz < 150.0 or f_mhz > 1500.0:
        import warnings
        warnings.warn(
            f"Frequency {f_mhz} MHz is outside Okumura-Hata validity range (150-1500 MHz). "
            "Results may be unreliable.",
            UserWarning,
            stacklevel=2
        )

    bts_ground = get_elevation(terrain_grid, bts_lat, bts_lon) if not terrain_grid.is_flat else 0.0
    rx_ground  = get_elevation(terrain_grid, rx_lat,  rx_lon)  if not terrain_grid.is_flat else 0.0
    bts_asl = bts_ground + bts_height_m
    rx_asl  = rx_ground  + rx_height_m

    # Effective BTS height: antenna ASL minus CPE ground elevation, clamped to the
    # Hata-valid range [HB_EFF_MIN_M, HB_EFF_MAX_M].
    hb_eff = float(max(HB_EFF_MIN_M, min(HB_EFF_MAX_M, bts_asl - rx_ground)))
    hm_eff = max(1.0, rx_height_m)

    # Clutter: per-pixel land-cover value when supplied (keeps the CPE link
    # budget identical to the heatmap), else the environment constant.
    if clutter_db_override is not None:
        clutter_db = float(clutter_db_override)
    else:
        clutter_db = float(ENVIRONMENT_CLUTTER_LOSS.get(environment, 3))

    if d_total <= 0.05:
        fspl = 20.0 * math.log10(max(d_total, 0.001)) + 20.0 * math.log10(f_mhz) + 32.44
        return PathLossResult(fspl, 0.0, clutter_db, bts_height_m, environment)

    if environment == 'open_water':
        # Pure over-water link uses two-ray ground reflection model
        base_loss = water_path_loss(max(d_total, 0.01), f_mhz, bts_height_m, rx_height_m)
        diffraction = 0.0
    elif terrain_grid.is_flat:
        # Fall back to FSPL if no terrain data is loaded (clutter is still applied)
        base_loss = 20.0 * math.log10(max(d_total, 0.001)) + 20.0 * math.log10(f_mhz) + 32.44
        diffraction = 0.0
    else:
        # Full ITM Longley-Rice deterministic terrain physics
        raw_profile = get_profile(terrain_grid, bts_lat, bts_lon, rx_lat, rx_lon, n_points=100)
        elevations = [e for d, e in raw_profile]
        dz_m = (d_total * 1000.0) / (len(elevations) - 1)
        
        try:
            base_loss, diffraction = itm_longley_rice(elevations, dz_m, f_mhz, bts_height_m, rx_height_m)
        except Exception:
            # Fallback to FSPL if ITM matrix math fails on an edge case
            base_loss = 20.0 * math.log10(max(d_total, 0.001)) + 20.0 * math.log10(f_mhz) + 32.44
            diffraction = 0.0

    return PathLossResult(base_loss, diffraction, clutter_db, bts_height_m, environment)


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
