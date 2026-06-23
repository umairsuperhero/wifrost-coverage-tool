"""
Deploy smoke test — runs offline (flat terrain, no network), fast.

Its job is to catch the class of failure where a refactor removes a symbol that
a still-deploying module imports (e.g. the `okumura_hata` removal that left
`api.py`/`heatmap.py` non-importable while Render kept serving a stale build).

Run locally or in CI BEFORE deploy:
    python test_smoke.py        # exits non-zero on any failure

This intentionally avoids SRTM/WorldCover/basemap network calls so it stays
deterministic and fast in CI.
"""
import sys


def test_entrypoint_imports():
    """The Docker entrypoint is `uvicorn api:app`; api + its deps must import."""
    import propagation  # noqa: F401
    import terrain  # noqa: F401
    import landcover  # noqa: F401
    import heatmap  # noqa: F401
    import report  # noqa: F401
    import api  # noqa: F401
    assert hasattr(api, "app"), "FastAPI app object missing"


def test_okumura_hata_ordering():
    """Legacy/flat-model path: urban >= suburban >= open at a reference link."""
    from propagation import okumura_hata
    o = okumura_hata(2.0, 500.0, 30.0, 2.0, "open")
    s = okumura_hata(2.0, 500.0, 30.0, 2.0, "suburban")
    u = okumura_hata(2.0, 500.0, 30.0, 2.0, "urban")
    assert u >= s >= o, f"environment ordering wrong: open={o} suburban={s} urban={u}"


def test_coverage_grid_runs_offline():
    """Exercise the grid kernel end-to-end on flat terrain (no network)."""
    import numpy as np
    from terrain import create_flat_terrain
    from heatmap import compute_coverage_grid
    from wifi_frost_defaults import WifrostBTS, WifrostCPE
    from kml_parser import KMLPoint

    bounds = {"minLat": 3.85, "maxLat": 3.95, "minLon": -77.12, "maxLon": -77.02}
    terrain_grid = create_flat_terrain(bounds)
    bts = KMLPoint(name="BTS", latitude=3.90, longitude=-77.07, description="",
                   is_bts_candidate=True, height_m=30.0, site_type="BTS")
    grid = compute_coverage_grid(
        bts_site=bts, equipment_bts=WifrostBTS(), equipment_cpe=WifrostCPE(),
        f_mhz=500.0, bounds=bounds, terrain_grid=terrain_grid,
        resolution_m=200.0, model="terrain_aware", environment="suburban",
    )
    assert grid.rssi_array.size > 0
    assert np.isfinite(grid.rssi_array).all(), "non-finite RSSI in coverage grid"
    assert "coverage_pct" in grid.stats


def test_cpe_analysis_runs_offline():
    """Exercise the /api/cpe-analysis kernel offline (flat terrain, stubbed land cover).

    Guards the class of bug where the endpoint references a name it never imported.
    This caught `NameError: name 'math' is not defined` in api.cpe_analysis (the MDT
    vertical-angle line), which 500'd every CPE analysis on the branch.
    """
    import numpy as np
    import api
    from terrain import create_flat_terrain

    # Keep it offline: no SRTM download, no WorldCover fetch.
    api.fetch_srtm = lambda bounds, key="": create_flat_terrain(bounds)

    class _NoLandcover:
        available = False

        def recommend_environment(self, default="suburban"):
            return default

        def get_clutter_db_np(self, lats, lons, default):
            return np.full(len(lats), default)

    api.fetch_landcover = lambda bounds: _NoLandcover()

    req = api.CpeAnalysisRequest(
        bts_index=-1,
        sites=[
            {"name": "BTS", "latitude": 40.015, "longitude": -105.27,
             "is_bts_candidate": True, "height_m": 30.0, "site_type": "BTS"},
            {"name": "CPE-1", "latitude": 40.005, "longitude": -105.26,
             "is_bts_candidate": False, "height_m": 6.0, "site_type": "CPE"},
        ],
        frequency_mhz=570.0, model="terrain_aware", environment="open",
        bts_height=30.0, tx_power_dbm=30.0, antenna_gain_dbi=12.0, cable_loss_db=1.0,
        rx_gain_dbi=10.0, rx_cable_loss_db=0.5, rx_sensitivity_dbm=-90.0,
    )
    result = api.cpe_analysis(req)  # must not raise (NameError, etc.)
    assert result is not None


def main():
    failures = []
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS  {name}")
            except Exception as e:  # noqa: BLE001
                failures.append((name, e))
                print(f"FAIL  {name}: {type(e).__name__}: {e}")
    if failures:
        print(f"\n{len(failures)} smoke test(s) failed.")
        sys.exit(1)
    print("\nAll smoke tests passed.")


if __name__ == "__main__":
    main()
