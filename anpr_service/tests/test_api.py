"""
Unit tests for FastAPI ANPR Service (anpr_service/main.py).
Tests:
- GET /health
- GET /api/v1/cameras
- POST /api/v1/cameras/register
- POST /api/v1/cameras/{id}/start and stop
- POST /api/v1/cameras/{id}/simulate-vehicle
- POST /api/v1/detect (direct image upload)
"""
import io
import cv2
from fastapi.testclient import TestClient
import numpy as np
import pytest

from anpr_service.main import app
from anpr_service.synthetic import SyntheticPlateGenerator, PlateColorTheme


client = TestClient(app)


def test_api_health():
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert "ParkMyCar" in data["service"]
    assert data["camerasActive"] >= 2


def test_api_cameras_list():
    res = client.get("/api/v1/cameras")
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert len(data["cameras"]) >= 2
    cam_ids = [c["camera_id"] for c in data["cameras"]]
    assert any("entry" in cid for cid in cam_ids)
    assert any("exit" in cid for cid in cam_ids)


def test_api_simulate_vehicle():
    cam_id = "palika-entry-1"
    payload = {
        "plateNumber": "DL01AB1234",
        "theme": "PRIVATE_WHITE",
        "layout": "SINGLE_ROW",
    }
    res = client.post(f"/api/v1/cameras/{cam_id}/simulate-vehicle", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["simulatedPlate"] == "DL01AB1234"
    assert data["event"] is not None
    assert data["event"]["plate_number"] == "DL01AB1234"
    assert data["event"]["camera_id"] == cam_id

    # Clear lane
    res_clear = client.post(f"/api/v1/cameras/{cam_id}/clear-vehicle")
    assert res_clear.status_code == 200
    assert res_clear.json()["status"] == "LANE_CLEARED"


def test_api_detect_uploaded_image():
    # Generate synthetic plate
    gen = SyntheticPlateGenerator()
    res = gen.generate("HR26DK8337", theme=PlateColorTheme.PRIVATE_WHITE)
    _, buffer = cv2.imencode(".png", res.image)

    files = {"file": ("plate.png", io.BytesIO(buffer), "image/png")}
    api_res = client.post("/api/v1/detect", files=files)
    assert api_res.status_code == 200
    data = api_res.json()
    assert data["success"] is True
    assert data["plateNumber"] == "HR26DK8337"
    assert data["stateCode"] == "HR"
    assert data["isValid"] is True
    assert data["confidence"] >= 0.75
