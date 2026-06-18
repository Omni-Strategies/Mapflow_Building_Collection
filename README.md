# GeoJSON Plotter

A Python project for Mapflow building analysis with GeoJSON and KML output.

## Overview

This repository provides:
- a script-based workflow for processing an Area of Interest (AOI) with Mapflow
- utilities to convert Mapflow output into GeoJSON, JSON, and KML
- a FastAPI server for integration and automation

## Features

- request Mapflow account credit status
- create Mapflow projects
- estimate processing cost for an AOI
- create Mapflow processing jobs
- download and transform Mapflow building data
- expose a REST API for external clients

## Requirements

- Python 3.8+
- `pip`
- Mapflow API credentials

## Installation

1. Clone the repository:

```bash
git clone <repository-url>
cd geojson_plotter
```

2. Create and activate a virtual environment:

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Windows Command Prompt:

```cmd
.venv\Scripts\activate.bat
```

macOS / Linux:

```bash
source .venv/bin/activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

## Configuration

Create a `.env` file in the project root and add your Mapflow credentials. Example:

```dotenv
MAPFLOW_API_KEY=your_api_key_here
```

> If your code uses a different credential filename or variable name, adjust this accordingly.

## Script Usage

Run the main script:

```bash
python main.py
```

The application will:
- load an AOI GeoJSON file
- check Mapflow account credits
- estimate processing cost
- create a processing job
- wait for the result
- download and convert Mapflow output

## Input GeoJSON

Provide a valid GeoJSON file containing a single polygon feature.
You can place the file anywhere in the repository, then update the path in `main.py` or call `load_aoi_geojson()` with the correct path.

Example GeoJSON:

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "Polygon",
        "coordinates": [
          [
            [lon1, lat1],
            [lon2, lat2],
            [lon3, lat3],
            [lon1, lat1]
          ]
        ]
      }
    }
  ]
}
```

## API Server

Start the FastAPI server with:

```bash
python app.py
```

Or use Uvicorn directly:

```bash
uvicorn routes:app --reload
```

Open the docs at:

- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/redoc`

## API Endpoints

- `GET /credits`
- `POST /projects`
- `POST /processing/cost`
- `POST /processing`
- `GET /processing/{processing_id}/download`
- `GET /processing/history`

## Example Requests

Create a project:

```json
{
  "name": "Downtown Mapflow Project",
  "description": "Project for processing building data"
}
```

Estimate cost:

```json
{
  "provider_name": "Mapbox",
  "wd_id": "8cb13006-a299-4df6-b47d-91bd63de947f",
  "aoi_polygon": {
    "type": "Polygon",
    "coordinates": [
      [
        [lon1, lat1],
        [lon2, lat2],
        [lon3, lat3],
        [lon1, lat1]
      ]
    ]
  }
}
```

Create a processing job:

```json
{
  "project_id": "8ebb9d48-299c-47cb-afa9-e61dc1729f71",
  "name": "Building Analysis",
  "provider_name": "Mapbox",
  "wd_name": "🏠 Buildings",
  "aoi_polygon": {
    "type": "Polygon",
    "coordinates": [
      [
        [lon1, lat1],
        [lon2, lat2],
        [lon3, lat3],
        [lon1, lat1]
      ]
    ]
  }
}
```

## Output

- `geojson_output/`: raw GeoJSON output from Mapflow
- `finaljson_output/`: processed JSON and KML output

## Example Usage

```python
from services.mapflow import MapflowClient
from services.geojson_modifier import mapflow_geojson_to_properties
from services.kml_export import json_to_kml

client = MapflowClient()
aoi_geometry = client.load_aoi_geojson("input.geojson")
project_id = "8ebb9d48-299c-47cb-afa9-e61dc1729f71"
response = client.create_processing(project_id=project_id, name="My Project", aoi_polygon=aoi_geometry)
client.download_results(response.id)
mapflow_geojson_to_properties("geojson_output/all_buildings.geojson")
json_to_kml("finaljson_output/all_buildings.json")
```

## Project Structure

```
.
├── app.py
├── main.py
├── routes.py
├── schema.py
├── requirements.txt
├── services/
│   ├── geojson_modifier.py
│   ├── kml_export.py
│   ├── kml_to_geojson.py
│   └── mapflow.py
├── geojson_output/
├── finaljson_output/
└── README.md
```

## Troubleshooting

"Error loading AOI GeoJSON"
- ensure the input file path is correct
- verify the file contains valid GeoJSON with a single polygon feature

"API key file not found"
- verify your `.env` contains the right variable or credentials file

"Insufficient credits"
- add credits to your Mapflow account before retrying

## License

Add your license information here.

## Support

For Mapflow API issues, visit: https://mapflow.ai/docs
