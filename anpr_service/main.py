"""
ParkMyCar ANPR FastAPI Service.
Main entry point orchestrating the ANPR detection pipeline, camera fleet,
simulation feeds, and automated event forwarding to the ParkMyCar backend API.
"""
import base64
import logging
import os
import threading
import time
from typing import Any, Dict, List, Optional
import urllib.request
import urllib.error
import json

import cv2
from fastapi import FastAPI, File, HTTPException, Header, UploadFile
from fastapi.middleware.cors import CORSMiddleware
import numpy as np
from pydantic import BaseModel, Field

from anpr_service.camera import (
    CameraFeedType,
    CameraFleetManager,
    CameraGateType,
    CameraStatus,
    CameraTelemetry,
    ProcessedPlateEvent,
    SimulationCameraFeed,
)
from anpr_service.config import settings
from anpr_service.detector import BasePlateDetector, create_detector
from anpr_service.ocr import OcrEngine
from anpr_service.synthetic import PlateColorTheme, PlateLayout
from anpr_service.validator import IndianPlateValidator, PlateValidationResult


logging.basicConfig(level=logging.INFO if not settings.DEBUG else logging.DEBUG)
logger = logging.getLogger("anpr_service")

app = FastAPI(
    title=settings.SERVICE_NAME,
    version="1.0.0",
    description="Automatic Number Plate Recognition & Live Occupancy Ingestion Service",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize subsystems
detector = create_detector()
ocr_engine = OcrEngine()
validator = IndianPlateValidator()
fleet_manager = CameraFleetManager(
    facility_id=settings.DEFAULT_FACILITY_ID,
    detector=detector,
    ocr_engine=ocr_engine,
    validator=validator,
    cooldown_seconds=float(settings.GATE_COOLDOWN_SECONDS),
    voting_window_seconds=float(settings.VOTING_WINDOW_SECONDS),
)


def forward_event_to_backend(event: ProcessedPlateEvent) -> None:
    """Dispatches verified ANPR events to the ParkMyCar API."""
    url = f"{settings.PARKMYCAR_API_URL}/anpr/events"
    payload = {
        "facilityId": event.facility_id,
        "cameraId": event.camera_id,
        "gateType": event.gate_type,
        "plateNumber": event.plate_number,
        "confidence": event.confidence,
        "plateCropBase64": event.plate_crop_b64,
        "detectedAt": event.detected_at,
        "processingTimeMs": event.processing_time_ms,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "X-ANPR-Secret": settings.ANPR_SHARED_SECRET,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            logger.info(f"Forwarded event {event.plate_number} to backend: HTTP {resp.status}")
    except Exception as e:
        logger.warning(f"Could not forward event {event.plate_number} to {url}: {e}")


fleet_manager.add_event_listener(forward_event_to_backend)

# Register default simulated cameras
fleet_manager.register_camera(
    camera_id=f"{settings.DEFAULT_FACILITY_ID}-entry-1",
    feed_type=CameraFeedType.SIMULATION,
    gate_type=CameraGateType.ENTRY,
)
fleet_manager.register_camera(
    camera_id=f"{settings.DEFAULT_FACILITY_ID}-exit-1",
    feed_type=CameraFeedType.SIMULATION,
    gate_type=CameraGateType.EXIT,
)
fleet_manager.start_camera(f"{settings.DEFAULT_FACILITY_ID}-entry-1")
fleet_manager.start_camera(f"{settings.DEFAULT_FACILITY_ID}-exit-1")


# --- Request/Response Schemas ---
class RegisterCameraRequest(BaseModel):
    cameraId: str
    feedType: CameraFeedType = CameraFeedType.SIMULATION
    gateType: CameraGateType = CameraGateType.ENTRY
    source: Optional[str] = None
    targetFps: float = 25.0


class SimulateVehicleRequest(BaseModel):
    plateNumber: str
    theme: PlateColorTheme = PlateColorTheme.PRIVATE_WHITE
    layout: PlateLayout = PlateLayout.SINGLE_ROW


class DetectPlateResponse(BaseModel):
    success: bool
    plateNumber: str
    confidence: float
    rawOcrText: str
    plateType: str
    stateCode: Optional[str]
    isValid: bool
    status: str
    reviewReason: Optional[str]
    executionTimeMs: float


# --- Endpoints ---
@app.get("/health")
def health() -> Dict[str, Any]:
    return {
        "status": "healthy",
        "service": settings.SERVICE_NAME,
        "facilityId": settings.DEFAULT_FACILITY_ID,
        "camerasActive": len(fleet_manager.list_cameras()),
        "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


@app.get("/api/v1/cameras")
def list_cameras() -> Dict[str, Any]:
    return {
        "success": True,
        "facilityId": settings.DEFAULT_FACILITY_ID,
        "cameras": [c.__dict__ for c in fleet_manager.list_cameras()],
    }


@app.post("/api/v1/cameras/register")
def register_camera(req: RegisterCameraRequest) -> Dict[str, Any]:
    feed = fleet_manager.register_camera(
        camera_id=req.cameraId,
        feed_type=req.feedType,
        gate_type=req.gateType,
        source=req.source,
        target_fps=req.targetFps,
    )
    return {"success": True, "camera": feed.get_telemetry().__dict__}


@app.post("/api/v1/cameras/{camera_id}/start")
def start_camera(camera_id: str) -> Dict[str, Any]:
    success = fleet_manager.start_camera(camera_id)
    if not success:
        raise HTTPException(status_code=400, detail=f"Failed to start camera {camera_id}")
    return {"success": True, "cameraId": camera_id, "status": "STARTED"}


@app.post("/api/v1/cameras/{camera_id}/stop")
def stop_camera(camera_id: str) -> Dict[str, Any]:
    fleet_manager.stop_camera(camera_id)
    return {"success": True, "cameraId": camera_id, "status": "STOPPED"}


@app.post("/api/v1/cameras/{camera_id}/simulate-vehicle")
def simulate_vehicle(camera_id: str, req: SimulateVehicleRequest) -> Dict[str, Any]:
    feed = fleet_manager.get_camera(camera_id)
    if not feed or not isinstance(feed, SimulationCameraFeed):
        raise HTTPException(status_code=400, detail=f"Camera {camera_id} is not a Simulation feed")

    feed.set_vehicle(
        plate_number=req.plateNumber,
        theme=req.theme,
        layout=req.layout,
    )
    # Process frame through manager pipeline
    frame = feed.read_frame()
    event = None
    if frame is not None:
        event = fleet_manager.process_frame(camera_id, frame)

    return {
        "success": True,
        "cameraId": camera_id,
        "simulatedPlate": req.plateNumber,
        "event": event.__dict__ if event else None,
    }


@app.post("/api/v1/cameras/{camera_id}/clear-vehicle")
def clear_vehicle(camera_id: str) -> Dict[str, Any]:
    feed = fleet_manager.get_camera(camera_id)
    if not feed or not isinstance(feed, SimulationCameraFeed):
        raise HTTPException(status_code=400, detail=f"Camera {camera_id} is not a Simulation feed")

    feed.clear_vehicle()
    return {"success": True, "cameraId": camera_id, "status": "LANE_CLEARED"}


@app.post("/api/v1/detect", response_model=DetectPlateResponse)
async def detect_plate(file: UploadFile = File(...)) -> DetectPlateResponse:
    start_t = time.perf_counter()
    contents = await file.read()
    nparr = np.frombuffer(contents, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if frame is None:
        raise HTTPException(status_code=400, detail="Invalid image payload")

    detections = detector.detect(frame)
    ocr_res = None

    if not detections:
        # Check if the uploaded image itself is an already-cropped plate
        h, w = frame.shape[:2]
        ar = w / float(h) if h > 0 else 0
        if 1.5 <= ar <= 6.5 and (w * h) >= 800:
            direct_ocr = ocr_engine.extract(frame)
            if direct_ocr.raw_text:
                ocr_res = direct_ocr
        
        if not ocr_res:
            return DetectPlateResponse(
                success=False,
                plateNumber="",
                confidence=0.0,
                rawOcrText="",
                plateType="UNKNOWN",
                stateCode=None,
                isValid=False,
                status="REJECTED",
                reviewReason="No plate localized",
                executionTimeMs=round((time.perf_counter() - start_t) * 1000, 2),
            )
    else:
        # Find candidate with valid text
        for det in detections:
            if det.cropped_plate is not None and det.cropped_plate.size > 0:
                res = ocr_engine.extract(det.cropped_plate)
                if res.raw_text:
                    ocr_res = res
                    break

    if not ocr_res or not ocr_res.raw_text:
        return DetectPlateResponse(
            success=False,
            plateNumber="",
            confidence=0.0,
            rawOcrText="",
            plateType="UNKNOWN",
            stateCode=None,
            isValid=False,
            status="REJECTED",
            reviewReason="OCR could not extract characters",
            executionTimeMs=round((time.perf_counter() - start_t) * 1000, 2),
        )

    val_res = validator.validate(ocr_res.raw_text, ocr_res.char_confidences)
    elapsed = round((time.perf_counter() - start_t) * 1000, 2)

    return DetectPlateResponse(
        success=val_res.is_valid,
        plateNumber=val_res.normalized_plate or ocr_res.raw_text,
        confidence=val_res.confidence,
        rawOcrText=ocr_res.raw_text,
        plateType=val_res.plate_type.value,
        stateCode=val_res.state_code,
        isValid=val_res.is_valid,
        status=val_res.status.value,
        reviewReason=val_res.review_reason.value if val_res.review_reason else None,
        executionTimeMs=elapsed,
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.HOST, port=settings.PORT)
