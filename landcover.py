"""
Land-cover clutter from ESA WorldCover 2021 (v200), 10 m global land cover.

The tiles are Cloud-Optimised GeoTIFFs on the public AWS bucket
`esa-worldcover` (eu-central-1). We read only the window covering the
requested bounding box over HTTP via GDAL /vsicurl/, resampled to a small
grid — so a city-sized area costs ~1–2 s and a few hundred KB, never the full
58 MB tile.

Each WorldCover class maps to an excess clutter loss (dB) applied at the
receiver location. This replaces the old single per-scene clutter constant
with a spatially-varying layer, so coverage correctly tightens over forest /
built-up areas and opens up over water / bare ground.

Everything degrades gracefully: if rasterio is missing, the tile 404s (ocean),
or the network fails, fetch_landcover() returns an "unavailable" grid and the
caller falls back to the environment-based clutter constant.
"""
import os
import math
import numpy as np
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

# ── WorldCover class → excess clutter loss (dB) at sub-GHz, receiver clutter ──
# Codes per the ESA WorldCover product user manual.
WORLDCOVER_CLUTTER_DB: Dict[int, float] = {
    10: 14.0,   # Tree cover
    20: 8.0,    # Shrubland
    30: 4.0,    # Grassland
    40: 5.0,    # Cropland
    50: 18.0,   # Built-up
    60: 2.0,    # Bare / sparse vegetation
    70: 1.0,    # Snow and ice
    80: 0.0,    # Permanent water bodies
    90: 3.0,    # Herbaceous wetland
    95: 12.0,   # Mangroves
    100: 2.0,   # Moss and lichen
}

WORLDCOVER_CLASS_NAME: Dict[int, str] = {
    10: "Tree cover", 20: "Shrubland", 30: "Grassland", 40: "Cropland",
    50: "Built-up", 60: "Bare / sparse", 70: "Snow / ice",
    80: "Water", 90: "Wetland", 95: "Mangroves", 100: "Moss / lichen",
}

# WorldCover class → Okumura-Hata environment type (drives the open/suburban/
# urban correction + shadowing sigma). Note we deliberately map water to "open"
# rather than "open_water": the two-ray water model would otherwise be applied
# to land cells in mixed coastal scenes. Pick open_water manually for pure
# over-water links.
WORLDCOVER_ENVIRONMENT: Dict[int, str] = {
    50: "urban",
    10: "vegetation_dense",
    95: "vegetation_dense",
    20: "vegetation_light",
    90: "vegetation_light",
    30: "open",
    40: "open",
    60: "open",
    70: "open",
    80: "open",
    100: "open",
}

_S3_BASE = ("https://esa-worldcover.s3.eu-central-1.amazonaws.com/"
            "v200/2021/map/ESA_WorldCover_10m_2021_v200_{tile}_Map.tif")

# Cap the fetched grid so memory / time stay bounded regardless of area size.
_MAX_DIM = 512


@dataclass
class LandCoverGrid:
    """Categorical land-cover grid (WorldCover class codes) over a bbox."""
    array: np.ndarray          # uint8 class codes, row 0 = north edge
    min_lat: float
    max_lat: float
    min_lon: float
    max_lon: float
    nrows: int
    ncols: int
    available: bool = False    # False ⇒ caller should use fallback clutter
    diag: str = ""             # short reason when unavailable (for ops/debug)

    def get_clutter_db_np(self, lats: np.ndarray, lons: np.ndarray,
                          fallback_db: float) -> np.ndarray:
        """
        Nearest-neighbour clutter loss (dB) for arrays of lats/lons.
        Cells with no data (class 0, e.g. ocean tiles) use ``fallback_db``.
        """
        lats = np.asarray(lats, dtype=float)
        lons = np.asarray(lons, dtype=float)
        if not self.available or self.nrows == 0 or self.ncols == 0:
            return np.full(lats.shape, fallback_db, dtype=float)

        # Map lat/lon → row/col (row 0 = max_lat / north).
        lat_span = max(self.max_lat - self.min_lat, 1e-9)
        lon_span = max(self.max_lon - self.min_lon, 1e-9)
        rows = ((self.max_lat - lats) / lat_span * self.nrows).astype(int)
        cols = ((lons - self.min_lon) / lon_span * self.ncols).astype(int)
        rows = np.clip(rows, 0, self.nrows - 1)
        cols = np.clip(cols, 0, self.ncols - 1)

        classes = self.array[rows, cols]
        out = np.full(classes.shape, fallback_db, dtype=float)
        for code, loss in WORLDCOVER_CLUTTER_DB.items():
            out[classes == code] = loss
        # class 0 (nodata) keeps fallback_db
        return out

    def class_histogram(self) -> Dict[str, float]:
        """Percent of valid cells per class name — handy for UI / debugging."""
        if not self.available:
            return {}
        valid = self.array[self.array != 0]
        if valid.size == 0:
            return {}
        vals, counts = np.unique(valid, return_counts=True)
        total = float(valid.size)
        return {
            WORLDCOVER_CLASS_NAME.get(int(v), str(int(v))): round(c / total * 100.0, 1)
            for v, c in zip(vals.tolist(), counts.tolist())
        }

    def recommend_environment(self, default: str = "suburban") -> str:
        """Area-weighted dominant Okumura-Hata environment from land cover.

        Sums the area of each class's mapped environment and returns the largest,
        so the model's open/suburban/urban correction matches what's actually on
        the ground instead of relying on an error-prone manual pick. Returns
        ``default`` when no land-cover data is available.
        """
        if not self.available:
            return default
        valid = self.array[self.array != 0]
        if valid.size == 0:
            return default
        vals, counts = np.unique(valid, return_counts=True)
        env_area: Dict[str, int] = {}
        for v, c in zip(vals.tolist(), counts.tolist()):
            env = WORLDCOVER_ENVIRONMENT.get(int(v))
            if env:
                env_area[env] = env_area.get(env, 0) + int(c)
        if not env_area:
            return default
        return max(env_area.items(), key=lambda kv: kv[1])[0]


def _unavailable(bounds: Dict[str, float], diag: str = "") -> LandCoverGrid:
    return LandCoverGrid(
        array=np.zeros((1, 1), dtype=np.uint8),
        min_lat=bounds["minLat"], max_lat=bounds["maxLat"],
        min_lon=bounds["minLon"], max_lon=bounds["maxLon"],
        nrows=0, ncols=0, available=False, diag=diag,
    )


def _ca_bundle() -> Optional[str]:
    """Path to a CA cert bundle for GDAL/libcurl HTTPS.

    Slim container images often omit system CA certs, which breaks GDAL's
    /vsicurl HTTPS even though Python's requests works (it bundles certifi).
    Point GDAL at certifi's bundle so S3 reads succeed everywhere.
    """
    try:
        import certifi
        return certifi.where()
    except Exception:
        return None


def _tile_name(lat0: int, lon0: int) -> str:
    ns = "N" if lat0 >= 0 else "S"
    ew = "E" if lon0 >= 0 else "W"
    return f"{ns}{abs(lat0):02d}{ew}{abs(lon0):03d}"


def _tiles_for_bounds(min_lat, max_lat, min_lon, max_lon) -> List[Tuple[int, int]]:
    """SW corners (multiples of 3°) of every WorldCover tile touching the bbox."""
    lat_start = int(math.floor(min_lat / 3.0) * 3)
    lat_end = int(math.floor((max_lat - 1e-9) / 3.0) * 3)
    lon_start = int(math.floor(min_lon / 3.0) * 3)
    lon_end = int(math.floor((max_lon - 1e-9) / 3.0) * 3)
    tiles = []
    lat0 = lat_start
    while lat0 <= lat_end:
        lon0 = lon_start
        while lon0 <= lon_end:
            tiles.append((lat0, lon0))
            lon0 += 3
        lat0 += 3
    return tiles


def fetch_landcover(bounds: Dict[str, float]) -> LandCoverGrid:
    """
    Fetch ESA WorldCover for the bbox and return a LandCoverGrid.
    Never raises — returns an unavailable grid on any failure so callers can
    fall back to the environment clutter constant.
    """
    min_lat, max_lat = bounds["minLat"], bounds["maxLat"]
    min_lon, max_lon = bounds["minLon"], bounds["maxLon"]
    if max_lat <= min_lat or max_lon <= min_lon:
        return _unavailable(bounds)

    try:
        import rasterio
        from rasterio.windows import from_bounds
        from rasterio.enums import Resampling
    except Exception as e:
        return _unavailable(bounds, f"rasterio import failed: {e}")

    # Local disk cache (helps within a warm instance; Cloud Run disk is ephemeral).
    cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")
    try:
        os.makedirs(cache_dir, exist_ok=True)
        cache_key = f"wc_{min_lat:.4f}_{max_lat:.4f}_{min_lon:.4f}_{max_lon:.4f}.npy"
        cache_path = os.path.join(cache_dir, cache_key)
        if os.path.exists(cache_path):
            arr = np.load(cache_path)
            return LandCoverGrid(array=arr, min_lat=min_lat, max_lat=max_lat,
                                 min_lon=min_lon, max_lon=max_lon,
                                 nrows=arr.shape[0], ncols=arr.shape[1],
                                 available=arr.size > 1 and bool((arr != 0).any()))
    except Exception:
        cache_path = None

    # Target grid: ~ native 10 m but capped to _MAX_DIM per axis.
    lat_span = max_lat - min_lat
    lon_span = max_lon - min_lon
    deg_per_px = 10.0 / 111320.0  # ~10 m
    nrows = int(min(_MAX_DIM, max(2, round(lat_span / deg_per_px))))
    ncols = int(min(_MAX_DIM, max(2, round(lon_span / deg_per_px))))
    out = np.zeros((nrows, ncols), dtype=np.uint8)

    gdal_env = {
        "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
        "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif",
        "GDAL_HTTP_MULTIRANGE": "YES",
        "GDAL_HTTP_TIMEOUT": "30",
        "VSI_CACHE": "TRUE",
    }
    # Slim images may lack system CA certs → GDAL HTTPS to S3 fails. Point
    # GDAL/libcurl at certifi's bundle so /vsicurl works in any container.
    ca = _ca_bundle()
    if ca:
        gdal_env["CURL_CA_BUNDLE"] = ca
        gdal_env["GDAL_HTTP_CAINFO"] = ca

    any_data = False
    tiles = _tiles_for_bounds(min_lat, max_lat, min_lon, max_lon)
    last_err = ""
    tiles_tried = 0
    try:
        with rasterio.Env(**gdal_env):
            for lat0, lon0 in tiles:
                url = "/vsicurl/" + _S3_BASE.format(tile=_tile_name(lat0, lon0))
                t_w, t_s, t_e, t_n = lon0, lat0, lon0 + 3, lat0 + 3
                ov_w, ov_e = max(min_lon, t_w), min(max_lon, t_e)
                ov_s, ov_n = max(min_lat, t_s), min(max_lat, t_n)
                if ov_w >= ov_e or ov_s >= ov_n:
                    continue
                # Output pixel block for this tile's overlap.
                col0 = int(round((ov_w - min_lon) / lon_span * ncols))
                col1 = int(round((ov_e - min_lon) / lon_span * ncols))
                row0 = int(round((max_lat - ov_n) / lat_span * nrows))
                row1 = int(round((max_lat - ov_s) / lat_span * nrows))
                oh, ow = row1 - row0, col1 - col0
                if oh <= 0 or ow <= 0:
                    continue
                tiles_tried += 1
                try:
                    with rasterio.open(url) as ds:
                        win = from_bounds(ov_w, ov_s, ov_e, ov_n, ds.transform)
                        block = ds.read(1, window=win, out_shape=(oh, ow),
                                        resampling=Resampling.nearest)
                    out[row0:row1, col0:col1] = block
                    if block.any():
                        any_data = True
                except Exception as e:
                    # Missing tile (ocean) or read error → leave as nodata.
                    last_err = f"{_tile_name(lat0, lon0)}: {type(e).__name__}: {e}"
                    continue
    except Exception as e:
        return _unavailable(bounds, f"gdal env error: {type(e).__name__}: {e}")

    if not any_data:
        return _unavailable(
            bounds,
            f"no data from {tiles_tried} tile(s); last error: {last_err or 'none (all ocean/empty)'}",
        )

    if cache_path:
        try:
            np.save(cache_path, out)
        except Exception:
            pass

    return LandCoverGrid(array=out, min_lat=min_lat, max_lat=max_lat,
                         min_lon=min_lon, max_lon=max_lon,
                         nrows=nrows, ncols=ncols, available=True)
