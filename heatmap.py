import math
import numpy as np
from io import BytesIO
from PIL import Image, ImageDraw
from dataclasses import dataclass, field
from typing import Dict, Any, List, Tuple, Optional
from propagation import terrain_aware_loss, okumura_hata, compute_eirp, compute_rssi, haversine_distance
from terrain import TerrainGrid, get_elevation

@dataclass
class CoverageGrid:
    rssi_array: np.ndarray  # 2D array, row 0 is max_lat (North), col 0 is min_lon (West)
    lats: np.ndarray        # 1D array of latitudes (North to South, decreasing)
    lons: np.ndarray        # 1D array of longitudes (West to East, increasing)
    stats: Dict[str, Any]
    bts_site: Any
    resolution_m: float
    model: str
    frequency_mhz: float

def compute_coverage_grid(bts_site: Any, equipment_bts: Any, equipment_cpe: Any,
                         f_mhz: float, bounds: Dict[str, float], terrain_grid: TerrainGrid, 
                         resolution_m: float = 100.0, model: str = 'terrain_aware',
                         environment: str = 'open', bts_height_override: Optional[float] = None) -> CoverageGrid:
    """
    Generate a grid of RSSI values over the bounded area.
    Returns a CoverageGrid with calculations and stats.
    """
    min_lat = bounds['minLat']
    max_lat = bounds['maxLat']
    min_lon = bounds['minLon']
    max_lon = bounds['maxLon']
    
    # Grid spacing in degrees
    # 1 degree lat = ~111.32 km = 111320 m
    delta_lat = resolution_m / 111320.0
    lat_center = (min_lat + max_lat) / 2.0
    # 1 degree lon = 111320 * cos(lat) m
    delta_lon = resolution_m / (111320.0 * math.cos(math.radians(lat_center)))
    
    # Generate lat/lon vectors.
    # Note: row 0 corresponds to max_lat (North), row N-1 to min_lat (South)
    # col 0 to min_lon (West), col M-1 to max_lon (East)
    lats = np.arange(max_lat, min_lat - delta_lat/2, -delta_lat)
    lons = np.arange(min_lon, max_lon + delta_lon/2, delta_lon)
    
    nrows = len(lats)
    ncols = len(lons)
    rssi_array = np.zeros((nrows, ncols))
    
    bts_lat = bts_site.latitude
    bts_lon = bts_site.longitude
    bts_height = bts_height_override if bts_height_override is not None else bts_site.height_m
    cpe_height = equipment_cpe.antenna_height_default_m
    
    # EIRP and receiver specs
    eirp_dbm = compute_eirp(equipment_bts.tx_power_dbm, equipment_bts.antenna_gain_dbi, equipment_bts.cable_loss_db)
    rx_gain = equipment_cpe.antenna_gain_dbi
    rx_loss = equipment_cpe.cable_loss_db
    rx_sensitivity = equipment_cpe.receiver_sensitivity_dbm # -104 dBm
    
    # Populate the RSSI array
    for r in range(nrows):
        lat = lats[r]
        for c in range(ncols):
            lon = lons[c]
            
            # Distance in km
            d_km = haversine_distance(bts_lat, bts_lon, lat, lon)
            
            # Avoid BTS point exactly (distance = 0)
            if d_km < 0.01:
                # Cap to extremely close values
                d_km = 0.01
                
            if model == 'terrain_aware':
                loss, _, _ = terrain_aware_loss(
                    bts_lat, bts_lon, bts_height,
                    lat, lon, cpe_height,
                    f_mhz, terrain_grid, environment
                )
            else:
                loss = okumura_hata(d_km, f_mhz, bts_height, cpe_height, environment)
                
            rssi = compute_rssi(loss, eirp_dbm, rx_gain, rx_loss)
            rssi_array[r, c] = rssi
            
    # Calculate coverage statistics
    total_cells = nrows * ncols
    covered_cells = np.sum(rssi_array >= -90.0)
    good_cells = np.sum(rssi_array >= -75.0)
    excellent_cells = np.sum(rssi_array >= -65.0)
    
    coverage_pct = (covered_cells / total_cells) * 100.0 if total_cells > 0 else 0.0
    good_pct = (good_cells / total_cells) * 100.0 if total_cells > 0 else 0.0
    excellent_pct = (excellent_cells / total_cells) * 100.0 if total_cells > 0 else 0.0
    
    # Average RSSI of covered locations
    covered_rssis = rssi_array[rssi_array >= -90.0]
    avg_rssi = np.mean(covered_rssis) if len(covered_rssis) > 0 else -110.0
    
    # Max range in km with signal >= -90 dBm
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
        "total_area_km2": round((nrows * ncols * (resolution_m ** 2)) / 1e6, 2)
    }
    
    return CoverageGrid(
        rssi_array=rssi_array,
        lats=lats,
        lons=lons,
        stats=stats,
        bts_site=bts_site,
        resolution_m=resolution_m,
        model=model,
        frequency_mhz=f_mhz
    )

def get_rssi_color(rssi: float) -> str:
    """Return Hex color corresponding to RSSI bands."""
    if rssi >= -65.0:
        return "#2ecc71"  # Excellent (Vibrant Green)
    elif rssi >= -75.0:
        return "#27ae60"  # Good (Darker Green)
    elif rssi >= -85.0:
        return "#f1c40f"  # Marginal (Yellow/Amber)
    elif rssi >= -90.0:
        return "#e74c3c"  # Weak (Red)
    return ""  # No signal (transparent)

def coverage_to_geojson(coverage_grid: CoverageGrid, threshold_dbm: float = -90.0) -> Dict[str, Any]:
    """
    Convert the CoverageGrid to a GeoJSON FeatureCollection of rectangular cell features.
    Filters out cells below the threshold to keep the payload lightweight.
    """
    features = []
    lats = coverage_grid.lats
    lons = coverage_grid.lons
    rssi_array = coverage_grid.rssi_array
    
    # Calculate cell step size in degrees
    # Avoid zero division
    n_lats = len(lats)
    n_lons = len(lons)
    
    d_lat = abs(lats[0] - lats[1]) if n_lats > 1 else 0.001
    d_lon = abs(lons[1] - lons[0]) if n_lons > 1 else 0.001
    
    # Generate rectangular polygons
    for r in range(n_lats):
        lat = lats[r]
        for c in range(n_lons):
            rssi = rssi_array[r, c]
            if rssi >= threshold_dbm:
                color = get_rssi_color(rssi)
                if not color:
                    continue
                
                # Rectangular cell coordinates
                # KML/GeoJSON polygons are closed: 5 coordinates representing 4 vertices, starting/ending at same point
                # Lon, Lat order
                west = lons[c] - d_lon / 2.0
                east = lons[c] + d_lon / 2.0
                south = lats[r] - d_lat / 2.0
                north = lats[r] + d_lat / 2.0
                
                coords = [[
                    [west, south],
                    [east, south],
                    [east, north],
                    [west, north],
                    [west, south]
                ]]
                
                features.append({
                    "type": "Feature",
                    "properties": {
                        "rssi": round(rssi, 1),
                        "fill": color,
                        "fill-opacity": 0.4,
                        "stroke": False,
                        "weight": 0
                    },
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": coords
                    }
                })
                
    return {
        "type": "FeatureCollection",
        "features": features
    }

def coverage_to_image(coverage_grid: CoverageGrid) -> bytes:
    """
    Create a static PNG representation of the coverage grid for inclusion in the PDF report.
    Returns bytes of the PNG image.
    """
    rssi_array = coverage_grid.rssi_array
    nrows, ncols = rssi_array.shape
    
    # Create an RGB image of the grid
    img = Image.new('RGB', (ncols, nrows), color=(255, 255, 255))
    pixels = img.load()
    
    for r in range(nrows):
        for c in range(ncols):
            rssi = rssi_array[r, c]
            if rssi >= -65.0:
                color = (46, 204, 113)  # Excellent (#2ecc71)
            elif rssi >= -75.0:
                color = (39, 174, 96)   # Good (#27ae60)
            elif rssi >= -85.0:
                color = (241, 196, 15)  # Marginal (#f1c40f)
            elif rssi >= -90.0:
                color = (231, 76, 60)   # Weak (#e74c3c)
            else:
                color = (245, 246, 250) # Very light grey for no signal background
            pixels[c, r] = color
            
    # Resize image to make it larger and look smoother
    # We can use bilinear resampling
    new_w = max(400, ncols * 4)
    new_h = max(400, nrows * 4)
    img_large = img.resize((new_w, new_h), Image.Resampling.BILINEAR)
    
    # Draw simple legend on the image
    draw = ImageDraw.Draw(img_large)
    # We don't draw text using custom fonts to avoid dependency issues on Marcelo's machine.
    # A simple border makes it look clean.
    draw.rectangle([0, 0, new_w - 1, new_h - 1], outline=(120, 120, 120), width=2)
    
    # Save to buffer
    buf = BytesIO()
    img_large.save(buf, format='PNG')
    return buf.getvalue()
