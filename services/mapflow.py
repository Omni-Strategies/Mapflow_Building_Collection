import json
import os
from pathlib import Path
from time import sleep, time, sleep
from typing import Any, Dict, Optional, Tuple

import requests
from dotenv import load_dotenv

try:
    from schema import (
        Geometry,
        MapflowCreditsResponse,
        MapflowProcessingCreateRequest,
        MapflowProcessingCreateResponse,
        MapflowProcessingHistoryResponse,
        MapflowProcessingStatusResponse,
        MapflowProjectCreateRequest,
        MapflowProjectCreateResponse,
    )
except ModuleNotFoundError:
    from ..schema import (
        Geometry,
        MapflowCreditsResponse,
        MapflowProcessingCreateRequest,
        MapflowProcessingCreateResponse,
        MapflowProcessingHistoryResponse,
        MapflowProcessingStatusResponse,
        MapflowProjectCreateRequest,
        MapflowProjectCreateResponse,
    )

BASE_URL = "https://api.mapflow.ai/rest"
# Prefer dotenv file by default (load vars from .env), fallback to plain key file if necessary
DEFAULT_KEY_FILE = ".env"


def read_key(key_file: Optional[str] = None) -> str:
    """Load the Mapflow API key.

    Priority:
    1. Load environment variables from the specified dotenv file (default: .env).
    2. Read `MAPFLOW_API_KEY` or `Mapflow_API_Key` from environment.
    3. If the specified file exists and isn't a dotenv file, read its raw contents (legacy txt file).
    """
    if key_file is None:
        key_file = DEFAULT_KEY_FILE

    key_path = Path(key_file)

    # Try to load variables from the provided dotenv (or from a discovered .env)
    if key_path.exists():
        load_dotenv(dotenv_path=key_path, override=False)
    else:
        # Attempt to load a .env from current working directory or parents
        load_dotenv(override=False)

    key = os.getenv("Mapflow_API_Key") or os.getenv("MAPFLOW_API_KEY")
    if key:
        return key.strip()

    # Legacy fallback: if a plain file was provided (e.g., Mapflow_API_key.txt), read it
    if key_path.exists() and key_path.suffix != ".env":
        return key_path.read_text(encoding="utf-8").strip()

    raise FileNotFoundError(
        f"Mapflow API key not found. Create '{key_file}' with MAPFLOW_API_KEY or set the env var."
    )


class MapflowClient:
    """Mapflow API client using Bearer token authentication and v2 endpoints."""

    def __init__(self, api_key: Optional[str] = None, key_file: Optional[str] = None, base_url: str = BASE_URL) -> None:
        api_key = read_key()
        if api_key:
            self.api_key = api_key.strip()
        else:
            self.api_key = read_key(key_file)
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Basic {self.api_key}",
            "Content-Type": "application/json",
        }
    
    def wait_for_processing(self, processing_id: str, poll_interval: int = 10, timeout: int = 600) -> str:
        elapsed = 0
        while elapsed < timeout:
            status_response = self.get_processing_status(processing_id)
            status = status_response.status
            print(f"Processing status: {status} ({elapsed}s elapsed)")
            
            if status == "OK":                          # ← was "FINISHED"
                return status
            if status in ("FAILED", "CANCELLED", "ERROR"):
                raise Exception(f"Processing ended with status: {status}")
            
            sleep(poll_interval)
            elapsed += poll_interval
        
        raise Exception(f"Processing timed out after {timeout}s")


    def load_aoi_geojson(self, path: str = "aoi_input/input.geojson") -> Dict[str, Any]:
        aoi_path = Path(path)
        if not aoi_path.exists():
            raise FileNotFoundError(f"AOI GeoJSON file not found: {aoi_path}")

        with aoi_path.open("r", encoding="utf-8") as f:
            aoi_data = json.load(f)

        return aoi_data["features"][0]["geometry"]

    def create_project(self, name: str = "Downtown Mapflow Project", description: str = "Project for processing building data") -> MapflowProjectCreateResponse:
        request = MapflowProjectCreateRequest(name=name, description=description)
        resp = self._post("/projects", request.model_dump())
        return MapflowProjectCreateResponse.model_validate(resp)

    def get_processing_history(self, page: int = 1, per_page: int = 50, status_filter: str = "status=OK") -> MapflowProcessingHistoryResponse:
        """Get processing history with pagination and filtering."""
        payload = {
            "page": page,
            "perPage": per_page,
            "sort": "created:desc",
            "filter": status_filter,
        }
        resp = self._post("/processings/stats", payload)
        return MapflowProcessingHistoryResponse.model_validate(resp)

    def get_credits(self) -> MapflowCreditsResponse:
        resp = self._get("/user/status")
        return MapflowCreditsResponse(
            email=resp.get("email"),
            remainingCredits=resp.get("remainingCredits", 0),
        )

    def get_processing_status(self, processing_id: str) -> MapflowProcessingStatusResponse:
        """Get processing status and details."""
        resp = self._get(f"/processings/{processing_id}/v2")
        return MapflowProcessingStatusResponse.model_validate(resp)

    def calculate_total_cost(self, provider_name: str = "Mapbox", wd_id: str = "8cb13006-a299-4df6-b47d-91bd63de947f", aoi_polygon: Optional[Geometry] = None) -> int: 
        """Estimate processing cost in credits.

        Returns the estimated cost as an integer (credits).
        """
        payload = {
            "wdId": wd_id,
        }
        try:
            if aoi_polygon is not None and len(aoi_polygon.get("coordinates", [])) > 0:
                payload["geometry"] = aoi_polygon
        except Exception as e:
            print(f"Error occurred while processing AOI geometry: {e}")
            
        payload["params"] = {
                "sourceParams": {
                    "dataProvider": {
                        "providerName": provider_name,
                        "zoom": 18,
                    }
                }
            }
        print(payload)
        cost = self._post("/processing/cost/v2", payload, headers=self.headers)
        # API returns cost as a number directly
        return int(cost) if isinstance(cost, (int, float)) else cost

    def create_processing(
        self,
        project_id: str,
        name: str = "Building Analysis",
        provider_name: str = "Mapbox",
        wd_name: str = "🏠 Buildings",
        aoi_polygon: Optional[Geometry] = None,
    ) -> MapflowProcessingCreateResponse:
        """Create and run an imagery analysis processing (v2 API)."""
        request = MapflowProcessingCreateRequest(
            project_id=project_id,
            name=name,
            provider_name=provider_name,
            wd_name=wd_name,
            aoi_polygon=aoi_polygon,
        )
        payload = {
            "name": request.name,
            "projectId": request.project_id,
            "wdName": request.wd_name,  
            "params": {
                "sourceParams": {
                    "dataProvider": {
                        "providerName": request.provider_name,
                        "zoom": 18,
                    }
                }
            },
            "blocks": [
                {"name": "Heights", "enabled": True},
                {"name": "Simplification", "enabled": True},
                {"name": "Classification", "enabled": True},
            ],
        }
        try:
            if request.aoi_polygon is not None:
                # Handle both bare Geometry and FeatureCollection inputs
                if request.aoi_polygon.get("type") == "FeatureCollection":
                    geometry = request.aoi_polygon["features"][0]["geometry"]
                else:
                    geometry = request.aoi_polygon

                if len(geometry.get("coordinates", [])) > 0:
                    payload["geometry"] = geometry
        except Exception as e:
            print(f"Error occurred while processing AOI geometry: {e}")

        resp = self._post("/processings/v2", payload)
        return MapflowProcessingCreateResponse.model_validate(resp)

    def download_results(self, processing_id: str) -> dict:
        import tempfile, json, os
        
        with requests.get(
            f"{self.base_url}/processings/{processing_id}/result",
            headers=self.headers,
            timeout=(10, None),  # no read timeout
            stream=True,
        ) as response:
            if response.status_code != 200:
                raise RuntimeError(f"Failed to download results: {response.status_code} {response.text}")
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=".geojson") as tmp:
                for chunk in response.iter_content(chunk_size=8192):
                    tmp.write(chunk)
                tmp_path = tmp.name
        
        with open(tmp_path) as f:
            geojson = json.load(f)
        os.unlink(tmp_path)
        return geojson

    def _get(self, path: str) -> Dict[str, Any]:
        response = requests.get(f"{self.base_url}{path}", headers=self.headers)
        response.raise_for_status()
        return response.json()

    def _post(self, path: str, payload: Dict[str, Any], headers: Dict[str, str] = None) -> Dict[str, Any]:
        response = requests.post(f"{self.base_url}{path}", headers=headers or self.headers, json=payload, timeout=(10, None))
        response.raise_for_status()
        return response.json()
