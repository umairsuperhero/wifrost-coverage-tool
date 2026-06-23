import os
import requests
from terrain import fetch_srtm
try:
    grid = fetch_srtm({"minLat":-12.1, "maxLat":-11.9, "minLon":-77.1, "maxLon":-76.9}, "")
    print(grid.is_flat)
except Exception as e:
    print(e)
