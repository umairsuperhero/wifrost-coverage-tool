import os
import pandas as pd
from typing import List, Tuple
from kml_parser import KMLData, KMLPoint

def clean_column_name(col: str) -> str:
    """Normalize column names by lowercase, stripping, and replacing underscores with spaces."""
    return str(col).strip().lower().replace('_', ' ')

def parse_excel_sites(filepath: str) -> KMLData:
    """Parse an Excel file containing site parameters and return a KMLData object."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Excel file not found: {filepath}")
        
    try:
        df = pd.read_excel(filepath)
    except Exception as e:
        raise ValueError(f"Failed to read Excel file: {e}")

    # Standardize column mappings
    col_mapping = {}
    for col in df.columns:
        cleaned = clean_column_name(col)
        col_mapping[cleaned] = col

    # Check for required columns: Name, Lat, Lon
    name_col = next((col_mapping[c] for c in ['site name', 'name', 'site', 'nombre'] if c in col_mapping), None)
    lat_col = next((col_mapping[c] for c in ['latitude', 'lat', 'latitud'] if c in col_mapping), None)
    lon_col = next((col_mapping[c] for c in ['longitude', 'lon', 'lng', 'longitud'] if c in col_mapping), None)
    height_col = next((col_mapping[c] for c in ['height m', 'height', 'antenna height', 'altura', 'altura m', 'height_m'] if c in col_mapping), None)
    type_col = next((col_mapping[c] for c in ['type', 'role', 'tipo'] if c in col_mapping), None)

    if not lat_col or not lon_col:
        raise ValueError("Excel file must contain Latitude and Longitude columns.")

    data = KMLData()

    for idx, row in df.iterrows():
        # Get values
        lat_val = row[lat_col]
        lon_val = row[lon_col]
        
        # Check coordinates validity
        try:
            lat = float(lat_val)
            lon = float(lon_val)
        except (ValueError, TypeError):
            # Skip rows with invalid coordinates
            continue

        # Get optional values
        name = str(row[name_col]).strip() if name_col and not pd.isna(row[name_col]) else f"Site {idx + 1}"
        
        # Default site type mapping
        site_type_val = str(row[type_col]).strip().upper() if type_col and not pd.isna(row[type_col]) else "CPE"
        is_bts = "BTS" in site_type_val or "BASE" in site_type_val or "TOWER" in site_type_val or "TORRE" in site_type_val
        site_type = "BTS" if is_bts else "CPE"
        
        # Height mapping
        default_height = 30.0 if is_bts else 10.0
        height = default_height
        if height_col and not pd.isna(row[height_col]):
            try:
                height = float(row[height_col])
            except (ValueError, TypeError):
                pass

        # Identify candidate BTS based on name too
        is_bts_name = False
        bts_keywords = ['hotel', 'edificio', 'pacific', 'trade', 'cafe', 'torre', 'bts', 'base station', 'antena', 'tower']
        for keyword in bts_keywords:
            if keyword in name.lower():
                is_bts_name = True
                
        is_bts_final = is_bts or is_bts_name
        if is_bts_final and site_type == "CPE":
            # If name suggests BTS but type didn't, let's make it a BTS
            site_type = "BTS"
            if height == 10.0:  # If height was default CPE, upgrade to BTS default
                height = 30.0

        data.sites.append(KMLPoint(
            name=name,
            latitude=lat,
            longitude=lon,
            description=f"Excel Row {idx + 1}",
            is_bts_candidate=is_bts_final,
            height_m=height,
            site_type=site_type
        ))

    return data

def generate_excel_template(directory: str) -> str:
    """Generate the template Excel file for sites if it doesn't exist."""
    os.makedirs(directory, exist_ok=True)
    template_path = os.path.join(directory, "sites_template.xlsx")
    
    if not os.path.exists(template_path):
        data = {
            "Site Name": ["Pacific Trade Center", "Hotel Torre Mar", "Rural CPE Customer 1", "Rural CPE Customer 2"],
            "Latitude": [-12.046374, -12.052144, -12.061234, -12.041543],
            "Longitude": [-77.031234, -77.042314, -77.021543, -77.051234],
            "Height_m": [35.0, 30.0, 10.0, 8.0],
            "Type": ["BTS", "BTS", "CPE", "CPE"]
        }
        df = pd.DataFrame(data)
        df.to_excel(template_path, index=False)
        
    return template_path
