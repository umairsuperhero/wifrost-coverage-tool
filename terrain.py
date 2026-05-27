import os
import math
import requests
import numpy as np
from dataclasses import dataclass
from typing import List, Tuple, Dict, Any

@dataclass
class TerrainGrid:
    array: np.ndarray
    min_lat: float
    max_lat: float
    min_lon: float
    max_lon: float
    ncols: int
    nrows: int
    cellsize: float
    xllcorner: float
    yllcorner: float
    nodata_value: float = -9999.0
    is_flat: bool = False

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two points in kilometers."""
    R = 6371.0  # Earth's radius in km
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (math.sin(d_lat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def create_flat_terrain(bounds: Dict[str, float]) -> TerrainGrid:
    """Create a flat TerrainGrid (all elevations = 0) as a fallback."""
    min_lat = bounds['minLat']
    max_lat = bounds['maxLat']
    min_lon = bounds['minLon']
    max_lon = bounds['maxLon']
    
    # Create a small 10x10 zero grid
    ncols, nrows = 10, 10
    array = np.zeros((nrows, ncols))
    cellsize = (max_lon - min_lon) / ncols
    
    return TerrainGrid(
        array=array,
        min_lat=min_lat,
        max_lat=max_lat,
        min_lon=min_lon,
        max_lon=max_lon,
        ncols=ncols,
        nrows=nrows,
        cellsize=cellsize,
        xllcorner=min_lon,
        yllcorner=min_lat,
        nodata_value=-9999.0,
        is_flat=True
    )

def fetch_srtm(bounds: Dict[str, float], api_key: str = None) -> TerrainGrid:
    """
    Fetch SRTM elevation data for the bounding box.
    Caches the parsed array and metadata locally to avoid redundant API calls.
    """
    min_lat = bounds['minLat']
    max_lat = bounds['maxLat']
    min_lon = bounds['minLon']
    max_lon = bounds['maxLon']
    
    # 1. Round bounding box to 4 decimal places for stable file cache keys
    cache_dir = os.path.join(os.path.dirname(__file__), "cache")
    os.makedirs(cache_dir, exist_ok=True)
    
    cache_key = f"srtm_{min_lat:.4f}_{max_lat:.4f}_{min_lon:.4f}_{max_lon:.4f}"
    npy_path = os.path.join(cache_dir, f"{cache_key}.npy")
    meta_path = os.path.join(cache_dir, f"{cache_key}.meta")
    
    # Check cache
    if os.path.exists(npy_path) and os.path.exists(meta_path):
        try:
            array = np.load(npy_path)
            with open(meta_path, 'r') as f:
                meta = {}
                for line in f:
                    k, v = line.strip().split('=')
                    meta[k] = float(v)
            return TerrainGrid(
                array=array,
                min_lat=min_lat,
                max_lat=max_lat,
                min_lon=min_lon,
                max_lon=max_lon,
                ncols=int(meta['ncols']),
                nrows=int(meta['nrows']),
                cellsize=meta['cellsize'],
                xllcorner=meta['xllcorner'],
                yllcorner=meta['yllcorner'],
                nodata_value=meta['nodata_value'],
                is_flat=False
            )
        except Exception:
            # If cache reading fails, we proceed to fetch
            pass
            
    # 2. If API Key is missing, fallback immediately to flat terrain
    if not api_key or api_key.strip() == "":
        return create_flat_terrain(bounds)

    # 3. Call OpenTopography API
    url = "https://portal.opentopography.org/API/globaldem"
    params = {
        "demtype": "SRTMGL1",
        "south": min_lat,
        "north": max_lat,
        "west": min_lon,
        "east": max_lon,
        "outputFormat": "AAIGrid",
        "API_Key": api_key
    }
    
    try:
        response = requests.get(url, params=params, timeout=30)
        if response.status_code != 200:
            # Log error internally and fallback
            return create_flat_terrain(bounds)
            
        content = response.text
        if "ncols" not in content or "nrows" not in content:
            # The API might return an error message in the text
            return create_flat_terrain(bounds)
            
        # Parse AAIGrid format
        lines = content.strip().split('\n')
        header = {}
        data_start_idx = 0
        for i in range(len(lines)):
            parts = lines[i].strip().split()
            if len(parts) == 2 and parts[0].lower() in ['ncols', 'nrows', 'xllcorner', 'yllcorner', 'cellsize', 'nodata_value']:
                header[parts[0].lower()] = float(parts[1])
            else:
                data_start_idx = i
                break
                
        ncols = int(header.get('ncols', 1201))
        nrows = int(header.get('nrows', 1201))
        cellsize = header.get('cellsize', 0.000277778)
        xllcorner = header.get('xllcorner', min_lon)
        yllcorner = header.get('yllcorner', min_lat)
        nodata_value = header.get('nodata_value', -9999.0)
        
        # Load the grid data rows
        data_rows = []
        for line in lines[data_start_idx:]:
            line_stripped = line.strip()
            if line_stripped:
                # Split and convert to floats/ints
                data_rows.append(list(map(float, line_stripped.split())))
                
        array = np.array(data_rows)
        
        # Verify sizes match
        if array.shape != (nrows, ncols):
            # If shape mismatch, fallback
            return create_flat_terrain(bounds)
            
        # Cache the result
        np.save(npy_path, array)
        with open(meta_path, 'w') as f:
            f.write(f"ncols={ncols}\n")
            f.write(f"nrows={nrows}\n")
            f.write(f"cellsize={cellsize}\n")
            f.write(f"xllcorner={xllcorner}\n")
            f.write(f"yllcorner={yllcorner}\n")
            f.write(f"nodata_value={nodata_value}\n")
            
        return TerrainGrid(
            array=array,
            min_lat=min_lat,
            max_lat=max_lat,
            min_lon=min_lon,
            max_lon=max_lon,
            ncols=ncols,
            nrows=nrows,
            cellsize=cellsize,
            xllcorner=xllcorner,
            yllcorner=yllcorner,
            nodata_value=nodata_value,
            is_flat=False
        )
        
    except Exception:
        return create_flat_terrain(bounds)

def get_elevation(terrain_grid: TerrainGrid, lat: float, lon: float) -> float:
    """
    Query the elevation of a specific coordinate using bilinear interpolation.
    Returns 0.0 if the point is outside the grid bounds.
    """
    if terrain_grid.is_flat:
        return 0.0
        
    array = terrain_grid.array
    ncols = terrain_grid.ncols
    nrows = terrain_grid.nrows
    cellsize = terrain_grid.cellsize
    xllcorner = terrain_grid.xllcorner
    yllcorner = terrain_grid.yllcorner
    nodata_value = terrain_grid.nodata_value
    
    # Upper latitude edge
    top_lat = yllcorner + nrows * cellsize
    
    # Calculate float indices
    col = (lon - xllcorner) / cellsize
    row = (top_lat - lat) / cellsize
    
    # Check bounds (with 0.5 padding for boundary pixels)
    if col < 0 or col >= ncols - 1 or row < 0 or row >= nrows - 1:
        return 0.0
        
    # Get floor and ceil indices
    c0 = int(math.floor(col))
    c1 = c0 + 1
    r0 = int(math.floor(row))
    r1 = r0 + 1
    
    # Check bounds again to be safe
    c0 = max(0, min(c0, ncols - 1))
    c1 = max(0, min(c1, ncols - 1))
    r0 = max(0, min(r0, nrows - 1))
    r1 = max(0, min(r1, nrows - 1))
    
    # Bilinear weights
    dc = col - c0
    dr = row - r0
    
    # Get corner values
    val_00 = array[r0, c0]
    val_01 = array[r0, c1]
    val_10 = array[r1, c0]
    val_11 = array[r1, c1]
    
    # Handle nodata values by replacing them with 0.0 or nearby valid values
    def clean_val(v):
        return 0.0 if v == nodata_value or pd_isna_check(v) else v
        
    val_00 = clean_val(val_00)
    val_01 = clean_val(val_01)
    val_10 = clean_val(val_10)
    val_11 = clean_val(val_11)
    
    # Interpolate
    val_top = val_00 * (1.0 - dc) + val_01 * dc
    val_bottom = val_10 * (1.0 - dc) + val_11 * dc
    
    val = val_top * (1.0 - dr) + val_bottom * dr
    return float(val)

def pd_isna_check(val):
    try:
        return math.isnan(val)
    except (TypeError, ValueError):
        return False

def get_profile(terrain_grid: TerrainGrid, lat1: float, lon1: float, lat2: float, lon2: float, n_points: int = 200) -> List[Tuple[float, float]]:
    """
    Generate a list of (distance_km, elevation_m) tuples along the path between two coordinates.
    """
    profile = []
    total_dist = haversine_distance(lat1, lon1, lat2, lon2)
    
    for i in range(n_points):
        t = i / (n_points - 1) if n_points > 1 else 0.0
        lat_t = lat1 + t * (lat2 - lat1)
        lon_t = lon1 + t * (lon2 - lon1)
        
        dist = t * total_dist
        elev = get_elevation(terrain_grid, lat_t, lon_t)
        profile.append((dist, elev))
        
    return profile
