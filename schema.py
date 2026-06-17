from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, EmailStr, Field

Geometry = Dict[str, Any]


class MapflowProjectCreateRequest(BaseModel):
    name: str = Field(..., example="Downtown Mapflow Project")
    description: str = Field(..., example="Project for processing building data")


class MapflowProjectCreateResponse(BaseModel):
    id: str


class MapflowProcessingHistoryRequest(BaseModel):
    page: int = 1
    per_page: int = Field(50, alias="perPage")
    status_filter: str = Field("status=OK", alias="statusFilter")

    model_config = {"populate_by_name": True}


class MapflowProcessingHistoryResponse(BaseModel):
    total: Optional[int] = None
    items: Optional[List[Dict[str, Any]]] = None

    model_config = {"extra": "allow"}


class MapflowCreditsResponse(BaseModel):
    """User account status with email and remaining credits."""

    email: str
    remainingCredits: int


class MapflowProcessingStatusResponse(BaseModel):
    """Processing status response from v2 API."""

    id: str
    name: str
    status: str
    percentCompleted: Optional[float] = None
    area: Optional[float] = None
    cost: Optional[int] = None
    created: Optional[str] = None
    updated: Optional[str] = None
    vectorLayer: Optional[Dict[str, Any]] = None

    model_config = {"extra": "allow"}


class MapflowCostEstimateRequest(BaseModel):
    provider_name: str = "Mapbox"
    wd_id: str = "8cb13006-a299-4df6-b47d-91bd63de947f"
    area_sq_km: float = 1.5
    aoi_polygon: Optional[Geometry] = None

    model_config = {"populate_by_name": True}


class MapflowCostEstimateResponse(BaseModel):
    """Cost estimate response (API returns a number directly)."""

    cost: int

    model_config = {"extra": "allow"}


class MapflowProcessingCreateRequest(BaseModel):
    project_id: str
    name: str = "Building Analysis"
    provider_name: str = "Mapbox"
    wd_name: str = "🏠 Buildings"
    aoi_polygon: Optional[Geometry] = None

    model_config = {"populate_by_name": True}


class MapflowProcessingCreateResponse(BaseModel):
    id: str

    model_config = {"extra": "allow"}


class MapflowDownloadRequest(BaseModel):
    processing_id: str
    output_dir: str = "geojson_output"


class MapflowDownloadResponse(BaseModel):
    properties: List[Dict[str, Any]]



