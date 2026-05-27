import math
import numpy as np
from typing import Dict, Any, List, Tuple
from terrain import TerrainGrid, get_profile, get_elevation, haversine_distance

def okumura_hata(d_km: float, f_mhz: float, hb_m: float, hm_m: float = 2.0, environment: str = 'open') -> float:
    """
    Compute path loss in dB using the Okumura-Hata model.
    Valid for: f 150-1500 MHz, hb 30-200m, hm 1-10m, d 1-20km
    """
    # Enforce realistic bounds to avoid math errors (e.g. log of 0 or negative numbers)
    d_km = max(0.01, d_km)
    hb_m = max(1.0, hb_m)  # Avoid log10(0) if height is 0
    hm_m = max(1.0, hm_m)
    
    # a(hm) correction factor for mobile antenna height
    a_hm = (1.1 * math.log10(f_mhz) - 0.7) * hm_m - (1.56 * math.log10(f_mhz) - 0.8)
    
    # Base urban loss
    loss = 69.55 + 26.16 * math.log10(f_mhz) - 13.82 * math.log10(hb_m) - a_hm + (44.9 - 6.55 * math.log10(hb_m)) * math.log10(d_km)
    
    # Environment corrections
    if environment == 'open':
        # Open (rural) area correction
        correction = 4.78 * (math.log10(f_mhz))**2 - 18.33 * math.log10(f_mhz) + 40.94
        loss -= correction
    elif environment == 'suburban':
        # Suburban correction
        correction = 2.0 * (math.log10(f_mhz / 28.0))**2 + 5.4
        loss -= correction
        
    # Free Space Path Loss (FSPL) floor (path loss can never be less than free space)
    fspl = 20.0 * math.log10(d_km) + 20.0 * math.log10(f_mhz) + 32.44
    loss = max(loss, fspl)
    
    return float(loss)


def terrain_aware_loss(bts_lat: float, bts_lon: float, bts_height_m: float, 
                       rx_lat: float, rx_lon: float, rx_height_m: float,
                       f_mhz: float, terrain_grid: TerrainGrid, environment: str = 'open') -> Tuple[float, float, float]:
    """
    Compute path loss combining Okumura-Hata and Deygout knife-edge diffraction.
    Returns a tuple of (total_loss_db, base_loss_db, diffraction_loss_db).
    """
    # 1. Distance between BTS and CPE
    d_total = haversine_distance(bts_lat, bts_lon, rx_lat, rx_lon)
    
    # 2. Get base Okumura-Hata loss
    base_loss = okumura_hata(d_total, f_mhz, bts_height_m, rx_height_m, environment)
    
    if terrain_grid.is_flat or d_total <= 0.05:
        # If terrain grid is flat or distance is extremely small, no diffraction loss
        return base_loss, base_loss, 0.0

    # 3. Get terrain profile
    # Using 100 points for performance, or 200 for fine resolution
    n_points = 100
    profile = get_profile(terrain_grid, bts_lat, bts_lon, rx_lat, rx_lon, n_points=n_points)
    
    # BTS and RX elevations
    elev_bts = get_elevation(terrain_grid, bts_lat, bts_lon)
    elev_rx = get_elevation(terrain_grid, rx_lat, rx_lon)
    
    # Absolute transmitter and receiver heights above sea level
    H_tx = elev_bts + bts_height_m
    H_rx = elev_rx + rx_height_m
    
    # Wavelength in meters
    c = 3e8
    wavelength = 300.0 / f_mhz  # f_mhz is in MHz, so lambda = 300 / f_mhz
    
    max_v = -9999.0
    dominant_loss = 0.0
    
    # 4. For each terrain sample point (excluding end points), compute diffraction parameter v
    for i in range(1, n_points - 1):
        dist_from_bts, terrain_elev = profile[i]
        
        # Distances to obstacle (d1) and from obstacle to receiver (d2) in km
        d1 = dist_from_bts
        d2 = d_total - dist_from_bts
        
        if d1 <= 0 or d2 <= 0:
            continue
            
        # Height of Line of Sight (LOS) line at this point
        LOS_height = H_tx + (d1 / d_total) * (H_rx - H_tx)
        
        # Obstacle clearance (height of obstacle above LOS line)
        h = terrain_elev - LOS_height
        
        # First Fresnel zone radius at this point
        # r1 = 17.3 * sqrt(d1*d2/(f_mhz*(d1+d2))) where d1, d2 are in km
        r1 = 17.3 * math.sqrt((d1 * d2) / (f_mhz * d_total))
        
        # Compute diffraction parameter v
        # v = h * sqrt(2 * (d1 + d2) / (lambda * d1 * d2 * 1000))
        # because d1 and d2 inside the sqrt need to be in meters
        v = h * math.sqrt(2.0 * d_total / (wavelength * d1 * d2 * 1000.0))
        
        if v > max_v:
            max_v = v

    # 5. Apply Deygout method
    diffraction_loss = 0.0
    if max_v > -0.7:
        # J(v) = 6.9 + 20 * log10(sqrt((v - 0.1)^2 + 1) + v - 0.1)
        term1 = (max_v - 0.1)**2 + 1.0
        term2 = math.sqrt(term1) + max_v - 0.1
        diffraction_loss = 6.9 + 20.0 * math.log10(term2)
        # Loss must be non-negative
        diffraction_loss = max(0.0, diffraction_loss)
        
    total_loss = base_loss + diffraction_loss
    return total_loss, base_loss, diffraction_loss

def compute_eirp(tx_power_dbm: float, tx_gain_dbi: float, tx_cable_loss_db: float) -> float:
    """Calculate the Equivalent Isotropically Radiated Power (EIRP)."""
    return tx_power_dbm + tx_gain_dbi - tx_cable_loss_db

def compute_rssi(path_loss_db: float, eirp_dbm: float, rx_gain_dbi: float, rx_cable_loss_db: float) -> float:
    """Calculate the Received Signal Strength Indicator (RSSI) at the CPE."""
    return eirp_dbm - path_loss_db + rx_gain_dbi - rx_cable_loss_db
