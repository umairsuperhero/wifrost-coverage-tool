import math
import numpy as np
from typing import List, Tuple
from terrain import TerrainGrid, get_profile, get_elevation, haversine_distance


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


# ── Propagation models ────────────────────────────────────────────────────────

def okumura_hata(d_km: float, f_mhz: float, hb_m: float,
                 hm_m: float = 2.0, environment: str = 'open') -> float:
    """Compute path loss (dB) using Okumura-Hata model."""
    d_km = max(0.01, d_km)
    hb_m = max(1.0, hb_m)
    hm_m = max(1.0, hm_m)

    a_hm = (1.1 * math.log10(f_mhz) - 0.7) * hm_m - (1.56 * math.log10(f_mhz) - 0.8)
    loss = (69.55 + 26.16 * math.log10(f_mhz) - 13.82 * math.log10(hb_m) - a_hm
            + (44.9 - 6.55 * math.log10(hb_m)) * math.log10(d_km))

    if environment == 'open':
        loss -= 4.78 * (math.log10(f_mhz)) ** 2 - 18.33 * math.log10(f_mhz) + 40.94
    elif environment == 'suburban':
        loss -= 2.0 * (math.log10(f_mhz / 28.0)) ** 2 + 5.4

    fspl = 20.0 * math.log10(d_km) + 20.0 * math.log10(f_mhz) + 32.44
    return float(max(loss, fspl))


def terrain_aware_loss(bts_lat: float, bts_lon: float, bts_height_m: float,
                       rx_lat: float, rx_lon: float, rx_height_m: float,
                       f_mhz: float, terrain_grid: TerrainGrid,
                       environment: str = 'open') -> Tuple[float, float, float]:
    """
    Path loss combining Okumura-Hata and Deygout knife-edge diffraction.
    Returns (total_loss_db, base_loss_db, diffraction_loss_db).
    """
    d_total = haversine_distance(bts_lat, bts_lon, rx_lat, rx_lon)
    base_loss = okumura_hata(d_total, f_mhz, bts_height_m, rx_height_m, environment)

    if terrain_grid.is_flat or d_total <= 0.05:
        return base_loss, base_loss, 0.0

    n_points = 100
    profile = get_profile(terrain_grid, bts_lat, bts_lon, rx_lat, rx_lon, n_points=n_points)

    elev_bts = get_elevation(terrain_grid, bts_lat, bts_lon)
    elev_rx = get_elevation(terrain_grid, rx_lat, rx_lon)
    H_tx = elev_bts + bts_height_m
    H_rx = elev_rx + rx_height_m
    wavelength = 300.0 / f_mhz

    max_v = -9999.0
    for i in range(1, n_points - 1):
        dist_from_bts, terrain_elev = profile[i]
        d1 = dist_from_bts
        d2 = d_total - dist_from_bts
        if d1 <= 0 or d2 <= 0:
            continue
        LOS_height = H_tx + (d1 / d_total) * (H_rx - H_tx)
        h = terrain_elev - LOS_height
        v = h * math.sqrt(2.0 * d_total / (wavelength * d1 * d2 * 1000.0))
        if v > max_v:
            max_v = v

    diffraction_loss = 0.0
    if max_v > -0.7:
        term2 = math.sqrt((max_v - 0.1) ** 2 + 1.0) + max_v - 0.1
        if term2 > 0:
            diffraction_loss = max(0.0, 6.9 + 20.0 * math.log10(term2))

    return base_loss + diffraction_loss, base_loss, diffraction_loss


# ── Link budget ───────────────────────────────────────────────────────────────

def compute_eirp(tx_power_dbm: float, tx_gain_dbi: float,
                 tx_cable_loss_db: float) -> float:
    """Calculate EIRP in dBm."""
    return tx_power_dbm + tx_gain_dbi - tx_cable_loss_db


def compute_rssi(path_loss_db: float, eirp_dbm: float,
                 rx_gain_dbi: float, rx_cable_loss_db: float,
                 sector_gain_db: float = 0.0) -> float:
    """Calculate RSSI at the CPE, optionally including sector antenna gain."""
    return eirp_dbm - path_loss_db + rx_gain_dbi - rx_cable_loss_db + sector_gain_db
