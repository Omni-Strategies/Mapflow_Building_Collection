"""
Unit tests for geojson_plotter API.

Run from the geojson_plotter directory:
    pip install pytest pytest-mock httpx fastapi
    pytest tests/test_api.py -v
"""

import json
import sys
import os
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open
import pytest

# Make sure project root is importable
sys.path.insert(0, str(Path(__file__).parent.parent))


# ─────────────────────────────────────────────
# Fixtures & shared test data
# ─────────────────────────────────────────────

SAMPLE_GEOJSON = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [-0.186964, 5.603717],
                        [-0.186800, 5.603717],
                        [-0.186800, 5.603900],
                        [-0.186964, 5.603900],
                        [-0.186964, 5.603717],
                    ]
                ],
            },
            "properties": {
                "building_height": 6.0,
                "shape_type": "DYNAMIC_GRID",
                "class_name": "residential",
                "class_id": 1,
                "area": 120.5,
            },
        },
        {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [-0.187500, 5.604000],
                        [-0.187300, 5.604000],
                        [-0.187300, 5.604200],
                        [-0.187500, 5.604200],
                        [-0.187500, 5.604000],
                    ]
                ],
            },
            "properties": {
                "building_height": None,
                "shape_type": "RECTANGLE",
                "class_name": "",
                "class_id": None,
                "area": None,
            },
        },
    ],
}

SAMPLE_AOI_POLYGON = {
    "type": "Polygon",
    "coordinates": [
        [
            [-0.186964, 5.603717],
            [-0.186800, 5.603717],
            [-0.186800, 5.603900],
            [-0.186964, 5.603900],
            [-0.186964, 5.603717],
        ]
    ],
}


# ─────────────────────────────────────────────
# Tests: geojson_modifier
# ─────────────────────────────────────────────

class TestMapflowGeojsonToPropertiesJson:
    """Tests for the in-memory GeoJSON → property dicts converter."""

    def setup_method(self):
        from services.geojson_modifier import mapflow_geojson_to_propertiesjson
        self.fn = mapflow_geojson_to_propertiesjson

    def test_returns_list_with_correct_length(self):
        result = self.fn(SAMPLE_GEOJSON)
        assert isinstance(result, list)
        assert len(result) == 2

    def test_gps_address_computed_from_coordinates(self):
        result = self.fn(SAMPLE_GEOJSON)
        # First feature has a valid polygon → gps_address should be a non-empty string
        assert result[0]["gps_address"] is not None
        assert "," in result[0]["gps_address"]

    def test_building_height_propagated(self):
        result = self.fn(SAMPLE_GEOJSON)
        assert result[0]["building height in m"] == 6.0

    def test_storeys_calculated_from_height(self):
        result = self.fn(SAMPLE_GEOJSON)
        # 6.0 m / 3 = 2 storeys
        assert result[0]["no_of_storeys"] == "2"

    def test_none_height_gives_none_storeys(self):
        result = self.fn(SAMPLE_GEOJSON)
        assert result[1]["no_of_storeys"] is None

    def test_dynamic_grid_shape_maps_to_flat_apartment(self):
        result = self.fn(SAMPLE_GEOJSON)
        assert result[0]["building_type"] == "flat_apartment"

    def test_other_shape_maps_to_detached(self):
        result = self.fn(SAMPLE_GEOJSON)
        assert result[1]["building_type"] == "detached"

    def test_empty_class_name_falls_back_to_unknown(self):
        result = self.fn(SAMPLE_GEOJSON)
        assert result[1]["property_use"] == "unknown"

    def test_class_name_used_when_present(self):
        result = self.fn(SAMPLE_GEOJSON)
        assert result[0]["property_use"] == "residential"

    def test_prop_class_is_string_when_class_id_present(self):
        result = self.fn(SAMPLE_GEOJSON)
        assert result[0]["prop_class"] == "1"

    def test_prop_class_is_none_when_no_class_id(self):
        result = self.fn(SAMPLE_GEOJSON)
        assert result[1]["prop_class"] is None

    def test_empty_features_returns_empty_list(self):
        result = self.fn({"type": "FeatureCollection", "features": []})
        assert result == []

    def test_feature_with_no_geometry_coords(self):
        geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Polygon", "coordinates": []},
                    "properties": {},
                }
            ],
        }
        result = self.fn(geojson)
        assert result[0]["gps_address"] is None


# ─────────────────────────────────────────────
# Tests: kml_export
# ─────────────────────────────────────────────

class TestJsonToKml:
    """Tests for the JSON → KML exporter."""

    def setup_method(self):
        from services.kml_export import json_to_kml
        self.fn = json_to_kml

    def _make_buildings_file(self, tmp_path, buildings):
        p = tmp_path / "all_buildings.json"
        p.write_text(json.dumps(buildings), encoding="utf-8")
        return str(p)

    def test_creates_kml_file(self, tmp_path):
        buildings = [{"gps_address": "5.603717, -0.186964", "building_type": "detached"}]
        src = self._make_buildings_file(tmp_path, buildings)
        out = self.fn(src, output_dir=str(tmp_path))
        assert out.exists()
        assert out.suffix == ".kml"

    def test_kml_contains_placemark_for_each_building(self, tmp_path):
        buildings = [
            {"gps_address": "5.603717, -0.186964", "building_type": "detached"},
            {"gps_address": "5.604000, -0.187500", "building_type": "flat_apartment"},
        ]
        src = self._make_buildings_file(tmp_path, buildings)
        out = self.fn(src, output_dir=str(tmp_path))
        content = out.read_text(encoding="utf-8")
        assert content.count("<Placemark>") == 2

    def test_kml_has_valid_coordinates_tag(self, tmp_path):
        buildings = [{"gps_address": "5.603717, -0.186964"}]
        src = self._make_buildings_file(tmp_path, buildings)
        out = self.fn(src, output_dir=str(tmp_path))
        content = out.read_text(encoding="utf-8")
        assert "<coordinates>" in content

    def test_kml_skips_coordinates_when_no_gps(self, tmp_path):
        buildings = [{"gps_address": None, "building_type": "detached"}]
        src = self._make_buildings_file(tmp_path, buildings)
        out = self.fn(src, output_dir=str(tmp_path))
        content = out.read_text(encoding="utf-8")
        # Point/coordinates should not appear when gps_address is None
        assert "<Point>" not in content

    def test_empty_buildings_list_produces_valid_kml(self, tmp_path):
        src = self._make_buildings_file(tmp_path, [])
        out = self.fn(src, output_dir=str(tmp_path))
        content = out.read_text(encoding="utf-8")
        assert "<Document>" in content
        assert "<Placemark>" not in content


# ─────────────────────────────────────────────
# Tests: MapflowClient (unit – mocked HTTP)
# ─────────────────────────────────────────────

@pytest.fixture
def mock_client(monkeypatch):
    """Return a MapflowClient with a real api_key injected, no .env required."""
    monkeypatch.setenv("MAPFLOW_API_KEY", "test_key_abc123")
    from services.mapflow import MapflowClient
    client = MapflowClient.__new__(MapflowClient)
    client.api_key = "test_key_abc123"
    client.base_url = "https://api.mapflow.ai/rest"
    client.headers = {
        "Authorization": "Basic test_key_abc123",
        "Content-Type": "application/json",
    }
    return client


class TestMapflowClientGetCredits:
    def test_returns_credits_response(self, mock_client):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"email": "test@example.com", "remainingCredits": 500}
        mock_resp.raise_for_status = MagicMock()

        with patch("services.mapflow.requests.get", return_value=mock_resp):
            result = mock_client.get_credits()

        assert result.email == "test@example.com"
        assert result.remainingCredits == 500

    def test_missing_credits_defaults_to_zero(self, mock_client):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"email": "test@example.com"}
        mock_resp.raise_for_status = MagicMock()

        with patch("services.mapflow.requests.get", return_value=mock_resp):
            result = mock_client.get_credits()

        assert result.remainingCredits == 0


class TestMapflowClientCreateProject:
    def test_returns_project_id(self, mock_client):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"id": "proj-123"}
        mock_resp.raise_for_status = MagicMock()

        with patch("services.mapflow.requests.post", return_value=mock_resp):
            result = mock_client.create_project(name="Test", description="Desc")

        assert result.id == "proj-123"


class TestMapflowClientCalculateCost:

    def test_uses_geometry_when_aoi_provided(self, mock_client):
        mock_resp = MagicMock()
        mock_resp.json.return_value = 99
        mock_resp.raise_for_status = MagicMock()

        with patch("services.mapflow.requests.post", return_value=mock_resp) as mock_post:
            mock_client.calculate_total_cost(aoi_polygon=SAMPLE_AOI_POLYGON)
            payload = mock_post.call_args[1]["json"]
            assert "geometry" in payload
        


class TestMapflowClientGetProcessingStatus:
    def test_returns_status_response(self, mock_client):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "id": "proc-456",
            "name": "Test",
            "status": "OK",
            "percentCompleted": 100.0,
        }
        mock_resp.raise_for_status = MagicMock()

        with patch("services.mapflow.requests.get", return_value=mock_resp):
            result = mock_client.get_processing_status("proc-456")

        assert result.id == "proc-456"
        assert result.status == "OK"


class TestMapflowClientDownloadResults:
    def test_returns_parsed_geojson(self, mock_client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = SAMPLE_GEOJSON

        with patch("services.mapflow.requests.get", return_value=mock_resp):
            result = mock_client.download_results("proc-456")

        assert result["type"] == "FeatureCollection"
        assert len(result["features"]) == 2

    def test_raises_on_non_200(self, mock_client):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.text = "Not found"

        with patch("services.mapflow.requests.get", return_value=mock_resp):
            with pytest.raises(RuntimeError, match="Failed to download results"):
                mock_client.download_results("bad-id")


class TestMapflowClientWaitForProcessing:
    def test_returns_ok_when_status_is_ok(self, mock_client):
        ok_status = MagicMock()
        ok_status.status = "OK"

        with patch.object(mock_client, "get_processing_status", return_value=ok_status):
            result = mock_client.wait_for_processing("proc-789", poll_interval=0)

        assert result == "OK"

    def test_raises_on_failed_status(self, mock_client):
        failed_status = MagicMock()
        failed_status.status = "FAILED"

        with patch.object(mock_client, "get_processing_status", return_value=failed_status):
            with pytest.raises(Exception, match="FAILED"):
                mock_client.wait_for_processing("proc-789", poll_interval=0)

    def test_raises_on_timeout(self, mock_client):
        running_status = MagicMock()
        running_status.status = "RUNNING"

        with patch.object(mock_client, "get_processing_status", return_value=running_status):
            with pytest.raises(Exception, match="timed out"):
                mock_client.wait_for_processing("proc-789", poll_interval=1, timeout=2)


# ─────────────────────────────────────────────
# Tests: FastAPI routes (integration – TestClient)
# ─────────────────────────────────────────────

@pytest.fixture
def test_app(monkeypatch):
    """
    routes.py creates `client = MapflowClient()` at import time (module level).
    We patch the already-created `routes.client` object directly so no real
    HTTP calls or credentials are needed.
    """
    monkeypatch.setenv("MAPFLOW_API_KEY", "test_key_abc123")
    import routes as routes_module
    mock_client = MagicMock()
    # Replace the module-level client in-place
    monkeypatch.setattr(routes_module, "client", mock_client)
    yield routes_module.app, mock_client


class TestGetCreditsRoute:
    def test_returns_200_with_credits(self, test_app):
        from fastapi.testclient import TestClient
        from schema import MapflowCreditsResponse
        app, mock_client = test_app
        mock_client.get_credits.return_value = MapflowCreditsResponse(
            email="test@example.com", remainingCredits=300
        )
        client = TestClient(app)
        resp = client.get("/credits")
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "test@example.com"
        assert data["remainingCredits"] == 300

    def test_returns_500_on_exception(self, test_app):
        from fastapi.testclient import TestClient
        app, mock_client = test_app
        mock_client.get_credits.side_effect = RuntimeError("API down")
        client = TestClient(app)
        resp = client.get("/credits")
        assert resp.status_code == 500


class TestCreateProjectRoute:
    def test_returns_project_id(self, test_app):
        from fastapi.testclient import TestClient
        from schema import MapflowProjectCreateResponse
        app, mock_client = test_app
        mock_client.create_project.return_value = MapflowProjectCreateResponse(id="proj-999")
        client = TestClient(app)
        resp = client.post("/projects", json={"name": "Test", "description": "Desc"})
        assert resp.status_code == 200
        assert resp.json()["id"] == "proj-999"



