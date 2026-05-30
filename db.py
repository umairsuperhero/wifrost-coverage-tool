"""
SQLite-based simulation history storage.

Single-file database (wifrost.db) with atomic writes, UUID keys, and
auto-trim to keep only the most recent MAX_HISTORY entries.
"""
import os
import uuid
import json
import sqlite3
import datetime
from typing import Optional, List, Dict, Any

MAX_HISTORY = 20
_DB_NAME = "wifrost.db"


def _db_path(base_dir: str) -> str:
    """Return the path to the SQLite database file."""
    data_dir = os.path.join(base_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, _DB_NAME)


def _get_conn(base_dir: str) -> sqlite3.Connection:
    """Open a connection with WAL mode for better concurrency."""
    path = _db_path(base_dir)
    conn = sqlite3.connect(path, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db(base_dir: str) -> None:
    """Create the simulation_runs table if it doesn't exist."""
    conn = _get_conn(base_dir)
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS simulation_runs (
                id           TEXT PRIMARY KEY,
                created_at   TEXT NOT NULL,
                project      TEXT,
                bts_name     TEXT,
                bts_lat      REAL,
                bts_lon      REAL,
                frequency    REAL,
                eirp_dbm     REAL,
                environment  TEXT,
                model        TEXT,
                coverage_pct REAL,
                max_range_km REAL,
                avg_rssi     REAL,
                params_json  TEXT,
                stats_json   TEXT,
                result_json  TEXT,
                geojson      TEXT
            )
        """)
        conn.commit()
    finally:
        conn.close()


def save_run(
    base_dir: str,
    project_name: str,
    bts_name: str,
    bts_lat: float,
    bts_lon: float,
    frequency_mhz: float,
    eirp_dbm: float,
    environment: str,
    model: str,
    coverage_pct: float,
    max_range_km: float,
    avg_rssi: float,
    params: Dict[str, Any],
    stats: Dict[str, Any],
    result: Dict[str, Any],
    geojson: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Persist one simulation run. Returns the UUID of the saved record.
    Uses INSERT OR REPLACE for atomicity.
    """
    init_db(base_dir)
    run_id = str(uuid.uuid4())
    now = datetime.datetime.utcnow().isoformat() + "Z"

    conn = _get_conn(base_dir)
    try:
        conn.execute(
            """INSERT INTO simulation_runs
               (id, created_at, project, bts_name, bts_lat, bts_lon,
                frequency, eirp_dbm, environment, model,
                coverage_pct, max_range_km, avg_rssi,
                params_json, stats_json, result_json, geojson)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                run_id, now, project_name, bts_name, bts_lat, bts_lon,
                frequency_mhz, eirp_dbm, environment, model,
                coverage_pct, max_range_km, avg_rssi,
                json.dumps(params, default=str),
                json.dumps(stats, default=str),
                json.dumps(result, default=str),
                json.dumps(geojson, default=str) if geojson else None,
            ),
        )
        conn.commit()
        _trim(conn)
    finally:
        conn.close()

    return run_id


def list_runs(base_dir: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Return the most recent N simulation runs (summary only, no geojson)."""
    init_db(base_dir)
    conn = _get_conn(base_dir)
    try:
        rows = conn.execute(
            """SELECT id, created_at, project, bts_name, bts_lat, bts_lon,
                      frequency, eirp_dbm, environment, model,
                      coverage_pct, max_range_km, avg_rssi
               FROM simulation_runs
               ORDER BY created_at DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_run(base_dir: str, run_id: str) -> Optional[Dict[str, Any]]:
    """Return full details for a specific run, including geojson and stats."""
    init_db(base_dir)
    conn = _get_conn(base_dir)
    try:
        row = conn.execute(
            "SELECT * FROM simulation_runs WHERE id = ?", (run_id,)
        ).fetchone()
        if row is None:
            return None
        result = dict(row)
        # Parse JSON fields back into dicts
        for field in ("params_json", "stats_json", "result_json", "geojson"):
            if result.get(field):
                try:
                    result[field] = json.loads(result[field])
                except (json.JSONDecodeError, TypeError):
                    pass
        return result
    finally:
        conn.close()


def delete_run(base_dir: str, run_id: str) -> bool:
    """Delete a specific run. Returns True if a row was deleted."""
    init_db(base_dir)
    conn = _get_conn(base_dir)
    try:
        cursor = conn.execute(
            "DELETE FROM simulation_runs WHERE id = ?", (run_id,)
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def _trim(conn: sqlite3.Connection) -> None:
    """Delete oldest entries so at most MAX_HISTORY remain."""
    conn.execute(
        """DELETE FROM simulation_runs
           WHERE id NOT IN (
               SELECT id FROM simulation_runs
               ORDER BY created_at DESC
               LIMIT ?
           )""",
        (MAX_HISTORY,),
    )
    conn.commit()
