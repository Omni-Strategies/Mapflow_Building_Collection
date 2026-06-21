"""
geo_enrichment.py
-----------------
Scans two directories for KML files at startup:

  geo_data/
  ├── electoral_areas/   ← one KML per electoral area (boundary polygons)
  └── communities/       ← one KML per community set (community polygons)

For each building centroid the pipeline will:
  1. Check every electoral-area KML → set "electoral_area" to the first match.
  2. Check every community KML      → set "community" to the first match.

Directory paths can be overridden via environment variables:
  ELECTORAL_AREAS_DIR   (default: <this file's dir>/geo_data/electoral_areas)
  COMMUNITIES_DIR       (default: <this file's dir>/geo_data/communities)
"""

import datetime
import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional
from xml.etree import ElementTree as ET

from shapely.geometry import MultiPolygon, Point, Polygon

import os

# ──────────────────────────────────────────────────────────────────────────────
# Directory configuration
# ──────────────────────────────────────────────────────────────────────────────

_BASE = Path(__file__).parent

ELECTORAL_AREAS_DIR = Path(
    os.environ.get("ELECTORAL_AREAS_DIR", _BASE / "geo_data" / "electoral_areas")
)
COMMUNITIES_DIR = Path(
    os.environ.get("COMMUNITIES_DIR", _BASE / "geo_data" / "communities")
)

_KML_NS = {"kml": "http://www.opengis.net/kml/2.2"}


# ──────────────────────────────────────────────────────────────────────────────
# KML parsing helpers
# ──────────────────────────────────────────────────────────────────────────────

def _parse_coord_string(coord_text: str) -> List[tuple]:
    """Convert a KML <coordinates> text block into (lon, lat) tuples."""
    pairs = []
    for token in coord_text.strip().split():
        parts = token.split(",")
        if len(parts) >= 2:
            try:
                pairs.append((float(parts[0]), float(parts[1])))
            except ValueError:
                pass
    return pairs


def _placemark_to_shapely(placemark) -> Optional[Any]:
    """Return a Shapely Polygon/MultiPolygon from a <Placemark> element."""
    polygons = []
    for poly_el in placemark.findall(".//kml:Polygon", _KML_NS):
        outer_el = poly_el.find(".//kml:outerBoundaryIs//kml:coordinates", _KML_NS)
        if outer_el is None or not outer_el.text:
            continue
        outer_ring = _parse_coord_string(outer_el.text)
        if len(outer_ring) < 3:
            continue
        inner_rings = []
        for inner_el in poly_el.findall(".//kml:innerBoundaryIs//kml:coordinates", _KML_NS):
            if inner_el.text:
                ring = _parse_coord_string(inner_el.text)
                if len(ring) >= 3:
                    inner_rings.append(ring)
        polygons.append(Polygon(outer_ring, inner_rings))

    if not polygons:
        return None
    return polygons[0] if len(polygons) == 1 else MultiPolygon(polygons)


def _simpledata(placemark, field: str) -> Optional[str]:
    """Extract a named <SimpleData> value from a placemark's ExtendedData."""
    for sd in placemark.findall(".//kml:SimpleData", _KML_NS):
        if sd.get("name") == field:
            return sd.text
    return None


# ──────────────────────────────────────────────────────────────────────────────
# Directory scanners – cached per process
# ──────────────────────────────────────────────────────────────────────────────
@lru_cache(maxsize=1)
def _load_electoral_areas() -> List[Dict[str, Any]]:
    """
    Scan ELECTORAL_AREAS_DIR for *.kml files.

    Each KML is expected to contain one or more <Placemark> elements whose
    <name> tag (or a <SimpleData name="..."> field) identifies the area.

    Returns a list of:
      {"name": str, "geometry": Shapely geometry, "source_file": str}
    """
    if not ELECTORAL_AREAS_DIR.exists():
        raise FileNotFoundError(
            f"Electoral areas directory not found: {ELECTORAL_AREAS_DIR}\n"
            "Create it and add at least one .kml boundary file, "
            "or set the ELECTORAL_AREAS_DIR environment variable."
        )

    entries: List[Dict[str, Any]] = []
    kml_files = sorted(ELECTORAL_AREAS_DIR.glob("*.kml"))

    if not kml_files:
        raise FileNotFoundError(
            f"No .kml files found in electoral areas directory: {ELECTORAL_AREAS_DIR}"
        )

    for kml_path in kml_files:
        tree = ET.parse(kml_path)
        root = tree.getroot()

        # Derive a fallback name from the filename (e.g. "Okaikwei_North_Boundary.kml"
        # → "Okaikwei North")
        stem = kml_path.stem  # e.g. "Okaikwei_North_Boundary"
        # Strip common suffixes like _Boundary, _boundary, _area, _Area
        for suffix in ("_Boundary", "_boundary", "_Area", "_area", "_District", "_district"):
            stem = stem.replace(suffix, "")
        filename_name = stem.replace("_", " ").strip()

        for placemark in root.findall(".//kml:Placemark", _KML_NS):
            geom = _placemark_to_shapely(placemark)
            if geom is None:
                continue

            # Check Community first (Okaikwei North KML stores the name here),
            # then fall back to <name> tag, then other SimpleData fields,
            # then the filename stem.
            name = _simpledata(placemark, "Community") or _simpledata(placemark, "community")

            if not name:
                name_el = placemark.find("kml:name", _KML_NS)
                name = (name_el.text.strip() if name_el is not None and name_el.text else None)

            if not name:
                for field in ("name", "Name", "District", "district", "Area", "area",
                              "Electoral_Area", "electoral_area"):
                    name = _simpledata(placemark, field)
                    if name:
                        break

            if not name:
                name = filename_name

            entries.append({
                "name": name,
                "geometry": geom,
                "source_file": kml_path.name,
            })

    return entries

@lru_cache(maxsize=1)
def _load_communities() -> List[Dict[str, Any]]:
    """
    Scan COMMUNITIES_DIR for *.kml files.

    Each KML may contain multiple <Placemark> elements, one per community.
    The community name is read from <SimpleData name="Community"> first,
    then falls back to the placemark's <name> tag.

    Returns a list of:
      {"name": str, "geometry": Shapely geometry, "source_file": str}
    """
    if not COMMUNITIES_DIR.exists():
        raise FileNotFoundError(
            f"Communities directory not found: {COMMUNITIES_DIR}\n"
            "Create it and add at least one .kml community file, "
            "or set the COMMUNITIES_DIR environment variable."
        )

    entries: List[Dict[str, Any]] = []
    kml_files = sorted(COMMUNITIES_DIR.glob("*.kml"))

    if not kml_files:
        raise FileNotFoundError(
            f"No .kml files found in communities directory: {COMMUNITIES_DIR}"
        )

    for kml_path in kml_files:
        tree = ET.parse(kml_path)
        root = tree.getroot()

        for placemark in root.findall(".//kml:Placemark", _KML_NS):
            geom = _placemark_to_shapely(placemark)
            if geom is None:
                continue

            # Try known SimpleData community name fields first
            name = None
            for field in ("Community", "community", "Name", "name"):
                name = _simpledata(placemark, field)
                if name:
                    break

            # Fall back to <name> tag
            if not name:
                name_el = placemark.find("kml:name", _KML_NS)
                if name_el is not None and name_el.text:
                    name = name_el.text.strip()

            if not name:
                name = kml_path.stem.replace("_", " ")

            entries.append({
                "name": name,
                "geometry": geom,
                "source_file": kml_path.name,
            })

    return entries


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────

def get_electoral_area(lon: float, lat: float) -> Optional[str]:
    """
    Return the name of the first electoral-area boundary that contains
    the point (lon, lat), or None if no boundary matches.
    Scans every KML in ELECTORAL_AREAS_DIR.
    """
    pt = Point(lon, lat)
    for entry in _load_electoral_areas():
        if entry["geometry"].contains(pt):
            return entry["name"]
    return None




def enrich_with_geo(lon: float, lat: float) -> Dict[str, Optional[str]]:
    """
    Returns {"electoral_area": str|None, "community": str|None} for a point.

    Both lookups are independent:
    - electoral_area is matched against every boundary KML in ELECTORAL_AREAS_DIR.
    - community      is matched against every community KML in COMMUNITIES_DIR.

    This means a building near an edge may have a community but no electoral
    area (or vice versa) if the two datasets don't align perfectly — which is
    common with GSS data.
    """
    return {
        "electoral_area": get_electoral_area(lon, lat),
  
    }


def list_loaded_electoral_areas() -> List[str]:
    """Return the names of all electoral areas loaded from ELECTORAL_AREAS_DIR."""
    return [e["name"] for e in _load_electoral_areas()]





# ──────────────────────────────────────────────────────────────────────────────
# Shared internal helpers
# ──────────────────────────────────────────────────────────────────────────────

def _area_as_int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _centroid_from_coords(coords: list) -> Optional[tuple]:
    """Return (lon, lat) centroid of a polygon ring, or None if empty."""
    if not coords:
        return None
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    return sum(lons) / len(lons), sum(lats) / len(lats)


# ──────────────────────────────────────────────────────────────────────────────
# Pipeline functions
# ──────────────────────────────────────────────────────────────────────────────

def _build_property_dict(
    props: dict,
    coords: list,
    full: bool = True,
) -> Dict[str, Any]:
    """
    Shared builder for a property dict. full=True includes all fields;
    full=False returns only the minimal set used by the _min variant.
    """
    centroid = _centroid_from_coords(coords)
    if centroid:
        lon, lat = centroid
        gps_address = f"{lat:.6f}, {lon:.6f}"
        geo = enrich_with_geo(lon, lat)
    else:
        gps_address = None
        geo = {"electoral_area": None, "community": None}

    height = props.get("building_height")
    shape_type = props.get("shape_type", "")
    class_name = props.get("class_name", "")
    area = props.get("area")
    area_int = _area_as_int(area)

    no_of_washrooms = (
        "4" if area_int > 1000
        else "3" if 700 < area_int < 1000
        else "2" if area_int > 500
        else "1"
    )

    shared: Dict[str, Any] = {
        "property_use": class_name or "unknown",
        "prop_class": str(props.get("class_id")) if props.get("class_id") else None,
        "gps_address": gps_address,
        "no_of_people": 0,
        "no_of_bedrooms": None,
        "no_of_washrooms": no_of_washrooms,
        "no_of_otherrooms": str(area_int // 100),
        "building_type": {"DYNAMIC_GRID": "flat_apartment"}.get(shape_type, "detached"),
        "building height in m": height,
        "building area in m^2": area,
        "no_of_storeys": str(round(height / 3)) if height else None,
        "electoral_area": geo["electoral_area"],
        "community": None,
    }

    if not full:
        return shared

    return {
        "owner_id": None,
        "ratepayer_id": None,
        "created_by": None,
        "property_code": None,
        **shared,
        "serial_no": None,
        "location": None,
        "population_density": None,
        "street_name": None,
        "landmark": None,
        "town": None,
        "ownership_type": None,
        "permit_status": None,
        "sanitation_facility_avail": None,
        "sources_of_water": None,
        "waste_disposal_method": None,
        "parcel_no": None,
        "house_no": None,
        "acct_no": None,
        "division_no": None,
        "rating_zone": None,
        "rateable_value": None,
        "lvd_val_no": None,
    }


def mapflow_geojson_to_propertiesjson(geojson: dict) -> List[Dict[str, Any]]:
    results = []
    for feature in geojson.get("features", []):
        props = feature.get("properties", {}) or {}
        geometry = feature.get("geometry", {}) or {}
        raw_coords = geometry.get("coordinates", [])
        coords = raw_coords[0] if raw_coords else []
        results.append(_build_property_dict(props, coords, full=True))
    return results


def mapflow_geojson_to_properties_json_min(geojson: dict) -> List[Dict[str, Any]]:
    results = []
    for feature in geojson.get("features", []):
        props = feature.get("properties", {}) or {}
        geometry = feature.get("geometry", {}) or {}
        raw_coords = geometry.get("coordinates", [])
        coords = raw_coords[0] if raw_coords else []
        results.append(_build_property_dict(props, coords, full=False))
    return results


def mapflow_geojson_to_properties(
    geojson_path: str, output_dir: str = "finaljson_output"
) -> List[Dict[str, Any]]:
    geojson_path = Path(geojson_path)
    with geojson_path.open("r", encoding="utf-8") as f:
        geojson = json.load(f)

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    results = []

    for feature in geojson.get("features", []):
        props = feature.get("properties", {}) or {}
        geometry = feature.get("geometry", {}) or {}
        raw_coords = geometry.get("coordinates", [])
        coords = raw_coords[0] if raw_coords else []
        results.append(_build_property_dict(props, coords, full=True))

    combined_path = Path(output_dir) / "all_buildings.json"
    temp_path = combined_path.with_suffix(combined_path.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    try:
        temp_path.replace(combined_path)
    except PermissionError:
        fallback = (
            Path(output_dir)
            / f"all_buildings_{datetime.datetime.now():%Y%m%d_%H%M%S}.json"
        )
        temp_path.replace(fallback)

    return results
