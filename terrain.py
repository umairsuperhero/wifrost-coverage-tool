import os
import time
import math
import requests
import numpy as np
from dataclasses import dataclass
from typing import List, Tuple, Dict, Any, Optional


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
    """Great-circle distance in kilometres."""
    R = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (math.sin(d_lat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(d_lon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def create_flat_terrain(bounds: Dict[str, float]) -> TerrainGrid:
    min_lat, max_lat = bounds['minLat'], bounds['maxLat']
    min_lon, max_lon = bounds['minLon'], bounds['maxLon']
    ncols, nrows = 10, 10
    array = np.zeros((nrows, ncols))
    cellsize = (max_lon - min_lon) / ncols
    return TerrainGrid(array=array, min_lat=min_lat, max_lat=max_lat,
                       min_lon=min_lon, max_lon=max_lon,
                       ncols=ncols, nrows=nrows, cellsize=cellsize,
                       xllcorner=min_lon, yllcorner=min_lat,
                       nodata_value=-9999.0, is_flat=True)


def fetch_srtm(bounds: Dict[str, float], api_key: str = None) -> TerrainGrid:
    """Fetch SRTM elevation data; falls back to flat terrain on any failure."""
    min_lat, max_lat = bounds['minLat'], bounds['maxLat']
    min_lon, max_lon = bounds['minLon'], bounds['maxLon']

    cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")
    os.makedirs(cache_dir, exist_ok=True)

    cache_key = f"srtm_{min_lat:.4f}_{max_lat:.4f}_{min_lon:.4f}_{max_lon:.4f}"
    npy_path = os.path.join(cache_dir, f"{cache_key}.npy")
    meta_path = os.path.join(cache_dir, f"{cache_key}.meta")

    if os.path.exists(npy_path) and os.path.exists(meta_path):
        try:
            array = np.load(npy_path)
            meta = {}
            with open(meta_path, 'r') as f:
                for line in f:
                    k, v = line.strip().split('=')
                    meta[k] = float(v)
            return TerrainGrid(array=array, min_lat=min_lat, max_lat=max_lat,
                               min_lon=min_lon, max_lon=max_lon,
                               ncols=int(meta['ncols']), nrows=int(meta['nrows']),
                               cellsize=meta['cellsize'],
                               xllcorner=meta['xllcorner'],
                               yllcorner=meta['yllcorner'],
                               nodata_value=meta['nodata_value'],
                               is_flat=False)
        except Exception:
            pass

    if not api_key or api_key.strip() == "":
        return create_flat_terrain(bounds)

    url = "https://portal.opentopography.org/API/globaldem"
    params = {
        "demtype": "SRTMGL1",
        "south": min_lat, "north": max_lat,
        "west": min_lon, "east": max_lon,
        "outputFormat": "AAIGrid",
        "API_Key": api_key,
    }

    try:
        response = None
        for _attempt in range(2):  # 1 retry
            try:
                response = requests.get(url, params=params, timeout=30)
                if response.status_code == 200:
                    break
            except requests.exceptions.Timeout:
                if _attempt == 0:
                    time.sleep(10)  # wait 10s before retry
                    continue
                return create_flat_terrain(bounds)
            except Exception:
                return create_flat_terrain(bounds)
        if response is None or response.status_code != 200:
            return create_flat_terrain(bounds)

        content = response.text
        if "ncols" not in content or "nrows" not in content:
            return create_flat_terrain(bounds)

        lines = content.strip().split('\n')
        header = {}
        data_start_idx = 0
        for i, line in enumerate(lines):
            parts = line.strip().split()
            if (len(parts) == 2
                    and parts[0].lower() in
                    ['ncols', 'nrows', 'xllcorner', 'yllcorner',
                     'cellsize', 'nodata_value']):
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

        import io
        try:
            data_str = '\n'.join(lines[data_start_idx:])
            array = np.loadtxt(io.StringIO(data_str))
        except Exception:
            return create_flat_terrain(bounds)
        if array.shape != (nrows, ncols):
            return create_flat_terrain(bounds)

        np.save(npy_path, array)
        with open(meta_path, 'w') as f:
            f.write(f"ncols={ncols}\nnrows={nrows}\ncellsize={cellsize}\n"
                    f"xllcorner={xllcorner}\nyllcorner={yllcorner}\n"
                    f"nodata_value={nodata_value}\n")

        return TerrainGrid(array=array, min_lat=min_lat, max_lat=max_lat,
                           min_lon=min_lon, max_lon=max_lon,
                           ncols=ncols, nrows=nrows, cellsize=cellsize,
                           xllcorner=xllcorner, yllcorner=yllcorner,
                           nodata_value=nodata_value, is_flat=False)

    except Exception:
        return create_flat_terrain(bounds)


def _pd_isna_check(val: float) -> bool:
    try:
        return math.isnan(val)
    except (TypeError, ValueError):
        return False


def get_elevation(terrain_grid: TerrainGrid, lat: float, lon: float) -> float:
    """Bilinear-interpolated elevation at (lat, lon); returns 0.0 outside grid."""
    if terrain_grid.is_flat:
        return 0.0

    array = terrain_grid.array
    ncols, nrows = terrain_grid.ncols, terrain_grid.nrows
    cellsize = terrain_grid.cellsize
    xllcorner, yllcorner = terrain_grid.xllcorner, terrain_grid.yllcorner
    nodata_value = terrain_grid.nodata_value

    top_lat = yllcorner + nrows * cellsize
    col = (lon - xllcorner) / cellsize
    row = (top_lat - lat) / cellsize

    if col < 0 or col > ncols - 1 or row < 0 or row > nrows - 1:
        return 0.0

    c0 = max(0, min(int(math.floor(col)), ncols - 1))
    c1 = max(0, min(c0 + 1, ncols - 1))
    r0 = max(0, min(int(math.floor(row)), nrows - 1))
    r1 = max(0, min(r0 + 1, nrows - 1))

    dc, dr = col - c0, row - r0

    def clean(v):
        return 0.0 if v == nodata_value or _pd_isna_check(v) else v

    val_top = clean(array[r0, c0]) * (1 - dc) + clean(array[r0, c1]) * dc
    val_bot = clean(array[r1, c0]) * (1 - dc) + clean(array[r1, c1]) * dc
    return float(val_top * (1 - dr) + val_bot * dr)


def get_elevation_np(terrain_grid: TerrainGrid, lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
    """Vectorized bilinear-interpolated elevation lookup on NumPy arrays of lats and lons."""
    if terrain_grid.is_flat:
        return np.zeros_like(lats, dtype=float)

    array = terrain_grid.array
    ncols, nrows = terrain_grid.ncols, terrain_grid.nrows
    cellsize = terrain_grid.cellsize
    xllcorner, yllcorner = terrain_grid.xllcorner, terrain_grid.yllcorner
    nodata_value = terrain_grid.nodata_value

    top_lat = yllcorner + nrows * cellsize
    col = (lons - xllcorner) / cellsize
    row = (top_lat - lats) / cellsize

    # Out of bounds mask
    out_of_bounds = (col < 0) | (col > ncols - 1) | (row < 0) | (row > nrows - 1)

    c0 = np.clip(np.floor(col).astype(int), 0, ncols - 1)
    c1 = np.clip(c0 + 1, 0, ncols - 1)
    r0 = np.clip(np.floor(row).astype(int), 0, nrows - 1)
    r1 = np.clip(r0 + 1, 0, nrows - 1)

    dc = col - c0
    dr = row - r0

    # Retrieve values
    val_r0_c0 = array[r0, c0]
    val_r0_c1 = array[r0, c1]
    val_r1_c0 = array[r1, c0]
    val_r1_c1 = array[r1, c1]

    # Clean nodata / nan values
    v_r0_c0 = np.where((val_r0_c0 == nodata_value) | np.isnan(val_r0_c0), 0.0, val_r0_c0)
    v_r0_c1 = np.where((val_r0_c1 == nodata_value) | np.isnan(val_r0_c1), 0.0, val_r0_c1)
    v_r1_c0 = np.where((val_r1_c0 == nodata_value) | np.isnan(val_r1_c0), 0.0, val_r1_c0)
    v_r1_c1 = np.where((val_r1_c1 == nodata_value) | np.isnan(val_r1_c1), 0.0, val_r1_c1)

    val_top = v_r0_c0 * (1.0 - dc) + v_r0_c1 * dc
    val_bot = v_r1_c0 * (1.0 - dc) + v_r1_c1 * dc
    elevations = val_top * (1.0 - dr) + val_bot * dr

    # Apply out of bounds mask
    elevations = np.where(out_of_bounds, 0.0, elevations)
    return elevations



def get_profile(terrain_grid: TerrainGrid,
                lat1: float, lon1: float,
                lat2: float, lon2: float,
                n_points: int = 200) -> List[Tuple[float, float]]:
    """Return list of (distance_km, elevation_m) along the path."""
    profile = []
    total_dist = haversine_distance(lat1, lon1, lat2, lon2)
    for i in range(n_points):
        t = i / (n_points - 1) if n_points > 1 else 0.0
        lat_t = lat1 + t * (lat2 - lat1)
        lon_t = lon1 + t * (lon2 - lon1)
        profile.append((t * total_dist, get_elevation(terrain_grid, lat_t, lon_t)))
    return profile


# ── Plotly terrain cross-section ──────────────────────────────────────────────

def build_terrain_profile_figure(terrain_grid: TerrainGrid,
                                  bts_lat: float, bts_lon: float,
                                  bts_height_m: float,
                                  rx_lat: float, rx_lon: float,
                                  rx_height_m: float,
                                  f_mhz: float,
                                  cpe_name: str = "CPE",
                                  n_points: int = 200):
    """
    Build a Plotly figure for the terrain cross-section between BTS and a CPE.
    Returns (fig, label_str) where label_str is "✅ Clear LoS" or a diffraction note.
    Returns (None, message) if terrain data is unavailable.
    """
    try:
        import plotly.graph_objects as go
    except ImportError:
        return None, "Plotly not installed — cannot render terrain profile."

    if terrain_grid.is_flat:
        return None, "Terrain profile not available — running without SRTM data."

    profile = get_profile(terrain_grid, bts_lat, bts_lon, rx_lat, rx_lon, n_points)
    if not profile:
        return None, "Could not compute terrain profile."

    distances = [p[0] for p in profile]
    elevations = [p[1] for p in profile]
    total_dist = distances[-1] if distances[-1] > 0 else 1.0

    bts_elev = get_elevation(terrain_grid, bts_lat, bts_lon)
    rx_elev = get_elevation(terrain_grid, rx_lat, rx_lon)
    H_tx = bts_elev + bts_height_m
    H_rx = rx_elev + rx_height_m

    los_heights = [H_tx + (d / total_dist) * (H_rx - H_tx) for d in distances]

    fresnel_upper, fresnel_lower = [], []
    for d in distances:
        d2 = total_dist - d
        if d > 0 and d2 > 0 and f_mhz > 0:
            r1 = 17.3 * math.sqrt((d * d2) / (f_mhz * total_dist))
            fresnel_upper.append(los_heights[distances.index(d)] + r1)
            fresnel_lower.append(los_heights[distances.index(d)] - r1)
        else:
            los_h = los_heights[distances.index(d)]
            fresnel_upper.append(los_h)
            fresnel_lower.append(los_h)

    obstr_x, obstr_y = [], []
    for i, (d, elev) in enumerate(zip(distances, elevations)):
        if elev > los_heights[i]:
            obstr_x.append(d)
            obstr_y.append(elev)

    fig = go.Figure()

    # Fresnel zone band
    fig.add_trace(go.Scatter(
        x=distances + distances[::-1],
        y=fresnel_upper + fresnel_lower[::-1],
        fill='toself',
        fillcolor='rgba(100, 149, 237, 0.12)',
        line=dict(color='rgba(100,149,237,0.3)', width=0),
        name='1st Fresnel Zone',
        hoverinfo='skip',
    ))

    # Terrain (filled area)
    fig.add_trace(go.Scatter(
        x=distances, y=elevations,
        fill='tozeroy',
        fillcolor='rgba(139, 119, 101, 0.45)',
        line=dict(color='rgba(101,80,60,0.9)', width=2),
        name='Terrain Elevation',
    ))

    # LoS line
    fig.add_trace(go.Scatter(
        x=distances, y=los_heights,
        line=dict(color='#2980b9', dash='dash', width=2),
        name='Line of Sight',
    ))

    # Obstructions
    if obstr_x:
        fig.add_trace(go.Scatter(
            x=obstr_x, y=obstr_y,
            mode='markers',
            marker=dict(color='red', size=5, symbol='x'),
            name='Terrain Obstruction',
        ))

    # Annotations
    fig.add_annotation(x=0, y=H_tx,
                       text=f"BTS<br>{H_tx:.0f}m ASL",
                       showarrow=True, arrowhead=2, ax=30, ay=-40,
                       font=dict(size=10))
    fig.add_annotation(x=total_dist, y=H_rx,
                       text=f"{cpe_name}<br>{H_rx:.0f}m ASL",
                       showarrow=True, arrowhead=2, ax=-30, ay=-40,
                       font=dict(size=10))

    fig.update_layout(
        xaxis_title="Distance from BTS (km)",
        yaxis_title="Elevation (m ASL)",
        height=320,
        margin=dict(l=50, r=20, t=20, b=40),
        legend=dict(orientation="h", y=-0.25, x=0),
        plot_bgcolor='rgba(248,249,250,1)',
        paper_bgcolor='white',
    )

    if obstr_x:
        label = f"⚠️ Terrain obstruction detected along path"
    else:
        label = "✅ Clear Line of Sight"

    return fig, label
