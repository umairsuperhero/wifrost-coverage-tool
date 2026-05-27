"""
Simulation history management.
Saves JSON metadata + optional PNG map + PDF report.
Keeps only the 10 most-recent entries.
"""
import os
import json
import datetime
from typing import Optional, List, Dict, Any

MAX_HISTORY = 10


def _dirs(base_dir: str):
    hist = os.path.join(base_dir, "simulations")
    maps = os.path.join(hist, "maps")
    reports = os.path.join(hist, "reports")
    for d in (hist, maps, reports):
        os.makedirs(d, exist_ok=True)
    return hist, maps, reports


def save_simulation(base_dir: str,
                    timestamp: datetime.datetime,
                    data: Dict[str, Any],
                    pdf_bytes: Optional[bytes] = None,
                    map_png_bytes: Optional[bytes] = None) -> str:
    """
    Persist one simulation entry.
    Returns the path of the saved JSON file.
    """
    hist, maps_dir, reports_dir = _dirs(base_dir)
    ts = timestamp.strftime("%Y-%m-%d_%H-%M-%S")

    pdf_path = ""
    if pdf_bytes:
        pdf_path = os.path.join(reports_dir, f"{ts}.pdf")
        try:
            with open(pdf_path, 'wb') as f:
                f.write(pdf_bytes)
        except Exception:
            pdf_path = ""

    map_path = ""
    if map_png_bytes:
        map_path = os.path.join(maps_dir, f"{ts}.png")
        try:
            with open(map_path, 'wb') as f:
                f.write(map_png_bytes)
        except Exception:
            map_path = ""

    record = {**data, "pdf_path": pdf_path, "map_image_path": map_path}
    json_path = os.path.join(hist, f"{ts}.json")
    try:
        with open(json_path, 'w') as f:
            json.dump(record, f, indent=2, default=str)
    except Exception:
        pass

    _trim(hist, maps_dir, reports_dir)
    return json_path


def load_history(base_dir: str) -> List[Dict[str, Any]]:
    """Return list of saved simulation records, newest first."""
    hist, _, _ = _dirs(base_dir)
    entries = []
    for fname in sorted(
            (f for f in os.listdir(hist) if f.endswith('.json')),
            reverse=True):
        try:
            with open(os.path.join(hist, fname)) as f:
                entries.append(json.load(f))
        except Exception:
            pass
    return entries[:MAX_HISTORY]


def _trim(hist_dir: str, maps_dir: str, reports_dir: str):
    """Delete oldest entries so at most MAX_HISTORY remain."""
    files = sorted(f for f in os.listdir(hist_dir) if f.endswith('.json'))
    while len(files) > MAX_HISTORY:
        oldest = files.pop(0)
        ts = oldest.replace('.json', '')
        for path in (
            os.path.join(hist_dir, oldest),
            os.path.join(reports_dir, f"{ts}.pdf"),
            os.path.join(maps_dir, f"{ts}.png"),
        ):
            try:
                os.remove(path)
            except FileNotFoundError:
                pass
