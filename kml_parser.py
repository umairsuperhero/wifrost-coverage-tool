import zipfile
import re
import os
import xml.etree.ElementTree as ET
try:
    from defusedxml.ElementTree import fromstring
except ImportError:
    from xml.etree.ElementTree import fromstring
from dataclasses import dataclass, field
from typing import List, Tuple, Optional

@dataclass
class KMLPoint:
    name: str
    latitude: float
    longitude: float
    description: str = ""
    is_bts_candidate: bool = False
    height_m: float = 30.0  # default height in meters
    site_type: str = "CPE"  # default type

@dataclass
class KMLPolygon:
    name: str
    coordinates: List[Tuple[float, float]]  # List of (longitude, latitude)
    description: str = ""

@dataclass
class KMLLineString:
    name: str
    coordinates: List[Tuple[float, float]]  # List of (longitude, latitude)
    description: str = ""

@dataclass
class KMLData:
    sites: List[KMLPoint] = field(default_factory=list)
    polygons: List[KMLPolygon] = field(default_factory=list)
    lines: List[KMLLineString] = field(default_factory=list)

def clean_tag(tag: str) -> str:
    """Strip namespace from XML tags."""
    return tag.split('}')[-1] if '}' in tag else tag

def parse_coordinates(coords_text: str) -> List[Tuple[float, float]]:
    """Parse KML coordinate string into list of (lon, lat) tuples."""
    coords = []
    # Coordinates in KML are space-separated strings of lon,lat,alt or lon,lat
    parts = coords_text.strip().split()
    for part in parts:
        subparts = part.strip().split(',')
        if len(subparts) >= 2:
            try:
                lon = float(subparts[0])
                lat = float(subparts[1])
                coords.append((lon, lat))
            except ValueError:
                continue
    return coords

def is_bts_name_or_style(name: str, style_url: str) -> bool:
    """Determine if a site is a BTS candidate based on its name or style URL."""
    name_lower = name.lower()
    # Check name keywords
    bts_keywords = ['hotel', 'edificio', 'pacific', 'trade', 'cafe', 'torre', 'bts', 'base station', 'antena', 'tower']
    for keyword in bts_keywords:
        if keyword in name_lower:
            return True
    
    # Check style URL for yellow pushpin
    if style_url:
        style_lower = style_url.lower()
        if 'ylw-pushpin' in style_lower or 'yellow' in style_lower or 'pushpin' in style_lower:
            return True
            
    return False

def parse_kml_content(kml_content: bytes) -> KMLData:
    """Parse KML XML content and extract points, polygons, and lines."""
    data = KMLData()
    try:
        root = fromstring(kml_content)
    except ET.ParseError as e:
        raise ValueError(f"Failed to parse KML XML: {e}")

    # Use a recursive helper to traverse elements and find Placemarks
    # This handles any nested Folder structure
    def traverse(element):
        tag = clean_tag(element.tag)
        if tag == "Placemark":
            parse_placemark(element, data)
        else:
            for child in element:
                traverse(child)

    traverse(root)
    return data

def parse_placemark(element: ET.Element, data: KMLData):
    """Parse a KML Placemark element and populate KMLData."""
    name = ""
    description = ""
    style_url = ""
    
    # Extract name, description, styleUrl
    for child in element:
        tag = clean_tag(child.tag)
        if tag == "name":
            name = (child.text or "").strip()
        elif tag == "description":
            description = (child.text or "").strip()
        elif tag == "styleUrl":
            style_url = (child.text or "").strip()

    # Find geometries inside Placemark
    for child in element:
        tag = clean_tag(child.tag)
        if tag == "Point":
            coords_elem = child.find(".//{*}coordinates")
            if coords_elem is not None and coords_elem.text:
                coords = parse_coordinates(coords_elem.text)
                if coords:
                    lon, lat = coords[0]
                    # Determine if BTS candidate
                    is_bts = is_bts_name_or_style(name, style_url)
                    site_type = "BTS" if is_bts else "CPE"
                    # Default height: 30m for BTS, 10m for CPE
                    height = 30.0 if is_bts else 10.0
                    data.sites.append(KMLPoint(
                        name=name or f"Site {len(data.sites) + 1}",
                        latitude=lat,
                        longitude=lon,
                        description=description,
                        is_bts_candidate=is_bts,
                        height_m=height,
                        site_type=site_type
                    ))
        elif tag == "Polygon":
            coords_elem = child.find(".//{*}coordinates")
            if coords_elem is not None and coords_elem.text:
                coords = parse_coordinates(coords_elem.text)
                if coords:
                    data.polygons.append(KMLPolygon(
                        name=name or f"Polygon {len(data.polygons) + 1}",
                        coordinates=coords,
                        description=description
                    ))
        elif tag == "LineString":
            coords_elem = child.find(".//{*}coordinates")
            if coords_elem is not None and coords_elem.text:
                coords = parse_coordinates(coords_elem.text)
                if coords:
                    data.lines.append(KMLLineString(
                        name=name or f"Line {len(data.lines) + 1}",
                        coordinates=coords,
                        description=description
                    ))

def parse_kml_or_kmz(filepath: str) -> KMLData:
    """Parse a KML or KMZ file and return a KMLData object."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    # Check if KMZ (zip file)
    if zipfile.is_zipfile(filepath):
        with zipfile.ZipFile(filepath, 'r') as archive:
            # Find the main .kml file (usually doc.kml)
            kml_files = [f for f in archive.namelist() if f.endswith('.kml')]
            if not kml_files:
                raise ValueError("No .kml files found inside KMZ archive.")
            # Sort to prioritize doc.kml if multiple
            kml_files.sort(key=lambda x: 0 if x == 'doc.kml' else 1)
            with archive.open(kml_files[0]) as f:
                content = f.read()
                return parse_kml_content(content)
    else:
        # Standard KML file
        with open(filepath, 'rb') as f:
            content = f.read()
            return parse_kml_content(content)
