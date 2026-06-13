import datetime
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional


def _area_as_int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def mapflow_geojson_to_propertiesjson(geojson: dict) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []

    for feature in geojson.get("features", []):
        props = feature.get("properties", {}) or {}
        geometry = feature.get("geometry", {}) or {}

        raw_coords = geometry.get("coordinates", [])
        coords = raw_coords[0] if raw_coords else []
        if coords:
            lons = [c[0] for c in coords]
            lats = [c[1] for c in coords]
            gps_address = f"{sum(lats)/len(lats):.6f}, {sum(lons)/len(lons):.6f}"
        else:
            gps_address = None

        height = props.get("building_height")
        shape_type = props.get("shape_type", "")
        class_name = props.get("class_name", "")
        area = props.get("area")

        property_dict: Dict[str, Any] = {
            "owner_id": None,
            "ratepayer_id": None,
            "created_by": None,
            "property_code": None,
            "property_use": class_name or "unknown",
            "prop_class": str(props.get("class_id")) if props.get("class_id") else None,
            "serial_no": None,
            "location": None,
            "population_density": None,
            "street_name": None,
            "landmark": None,
            "gps_address": gps_address,
            "no_of_people": 0,
            "no_of_bedrooms": None,
            "no_of_washrooms": 0,
            "no_of_otherrooms": 0,
            "building_type": {"DYNAMIC_GRID": "flat_apartment"}.get(shape_type, "detached"),
            "building height in m": height,
            "building area in m^2": area,
            "no_of_storeys": str(round(height / 3)) if height else None,
            "electoral_area": None,
            "town": None,
            "community": None,
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
        area_int = _area_as_int(area)
        if area_int > 1000:
            property_dict["no_of_washrooms"] = "4"
        elif 700 < area_int < 1000:
            property_dict["no_of_washrooms"] = "3"
        elif area_int > 500:
            property_dict["no_of_washrooms"] = "2"
        else:
            property_dict["no_of_washrooms"] = "1"

        property_dict["no_of_otherrooms"] = str(area_int // 100)
        results.append(property_dict)

    return results


def mapflow_geojson_to_properties(geojson_path: str, output_dir: str = "finaljson_output") -> List[Dict[str, Any]]:
    geojson_path = Path(geojson_path)
    with geojson_path.open("r", encoding="utf-8") as f:
        geojson = json.load(f)

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    results: List[Dict[str, Any]] = []

    for feature in geojson.get("features", []):
        props = feature.get("properties", {}) or {}
        geometry = feature.get("geometry", {}) or {}

        raw_coords = geometry.get("coordinates", [])
        coords = raw_coords[0] if raw_coords else []
        if coords:
            lons = [c[0] for c in coords]
            lats = [c[1] for c in coords]
            gps_address = f"{sum(lats)/len(lats):.6f}, {sum(lons)/len(lons):.6f}"
        else:
            gps_address = None

        height = props.get("building_height")
        shape_type = props.get("shape_type", "")
        class_name = props.get("class_name", "")
        area = props.get("area")

        property_dict: Dict[str, Any] = {
            "owner_id": None,
            "ratepayer_id": None,
            "created_by": None,
            "property_code": None,
            "property_use": class_name or "unknown",
            "prop_class": str(props.get("class_id")) if props.get("class_id") else None,
            "serial_no": None,
            "location": None,
            "population_density": None,
            "street_name": None,
            "landmark": None,
            "gps_address": gps_address,
            "no_of_people": 0,
            "no_of_bedrooms": None,
            "no_of_washrooms": 0,
            "no_of_otherrooms": 0,
            "building_type": {"DYNAMIC_GRID": "flat_apartment"}.get(shape_type, "detached"),
            "building height in m": height,
            "building area in m^2": area,
            "no_of_storeys": str(round(height / 3)) if height else None,
            "electoral_area": None,
            "town": None,
            "community": None,
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

        results.append(property_dict)

    combined_path = Path(output_dir) / "all_buildings.json"
    temp_path = combined_path.with_suffix(combined_path.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    try:
        temp_path.replace(combined_path)
        output_path = combined_path
    except PermissionError:
        fallback_path = Path(output_dir) / f"all_buildings_{datetime.datetime.now():%Y%m%d_%H%M%S}.json"
        temp_path.replace(fallback_path)
        output_path = fallback_path

    return results
