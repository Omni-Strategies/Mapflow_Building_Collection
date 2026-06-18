import json
import time

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from typing import Any, Dict, List, Optional
import json as _json

from pydantic import json
from services.geojson_modifier import mapflow_geojson_to_properties
from services.kml_export import json_to_kml
from services.geojson_modifier import mapflow_geojson_to_propertiesjson
from services.mapflow import MapflowClient
from schema import (
    MapflowCostEstimateRequest,
    MapflowCreditsResponse,
    MapflowProcessingCreateRequest,
    MapflowProcessingCreateResponse,
    MapflowProcessingStatusResponse,
    MapflowProjectCreateRequest,
    MapflowProcessingHistoryResponse,
    MapflowDownloadResponse,
    MapflowDownloadRequest,
    MapflowProjectCreateResponse,
)

app = FastAPI(title="Mapflow API", version="0.1.0")
client: Optional[MapflowClient] = None


def get_mapflow_client() -> MapflowClient:
    global client
    if client is None:
        client = MapflowClient()
    return client


@app.get("/ping")
def ping() -> Dict[str, str]:
    return {"status": "ok", "service": "mapflow-building-collection"}


@app.get("/credits", response_model=MapflowCreditsResponse)
def get_credits() -> MapflowCreditsResponse:
    try:
        return get_mapflow_client().get_credits()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/projects", response_model=MapflowProjectCreateResponse)
def create_project(request: MapflowProjectCreateRequest) -> MapflowProjectCreateResponse:
    try:
        return get_mapflow_client().create_project(name=request.name, description=request.description)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/processing/cost", response_model=dict)
def calculate_cost(request: MapflowCostEstimateRequest) -> dict:
    try:
        cost = get_mapflow_client().calculate_total_cost(
            provider_name=request.provider_name,
            wd_id=request.wd_id,
            aoi_polygon=request.aoi_polygon,
        )
        return {"cost": cost}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@app.post("/processing")
def create_processings(request: MapflowProcessingCreateRequest) -> str:
    client = get_mapflow_client()
    try:
        resp = client.create_processing(
            project_id=request.project_id,
            name=request.name,
            provider_name=request.provider_name,
            wd_name=request.wd_name,
            aoi_polygon=request.aoi_polygon,
        )
    
        return resp.id         
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str("Failed to create processing"))
    
    
    
@app.get("/processing/{processing_id}/status")
def get_status(processing_id: str):
    client = get_mapflow_client()
    status = client.get_processing_status(processing_id)
    return {"status": status.status}

@app.get("/processing/{processing_id}/download", response_model=MapflowDownloadResponse)
def get_processing_result_json(processing_id: str) -> MapflowDownloadResponse:
    try:
        output_path = get_mapflow_client().download_results(processing_id)
        results = mapflow_geojson_to_propertiesjson(output_path)
        return MapflowDownloadResponse(properties=results)  # ← wrap it
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@app.get("/processing/history", response_model=MapflowProcessingHistoryResponse)
def get_processing_history(page: int = 1, per_page: int = 50, status_filter: str = "status=OK") -> MapflowProcessingHistoryResponse:
    try:
        return get_mapflow_client().get_processing_history(page=page, per_page=per_page, status_filter=status_filter)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
