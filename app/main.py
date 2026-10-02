from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from . import models, schemas, database, auth
from .auth import get_db

# Initialize the FastAPI App
app = FastAPI(title="Sentinel Telemetry API")

@app.get("/")
def read_root():
    return {"status": "Sentinel Telemetry is Online", "version": "1.0.0"}

@app.post("/api/heartbeat")
async def receive_heartbeat(
    request: schemas.HeartbeatRequest,
    device: models.STDevice = Depends(auth.require_device),
    db: Session = Depends(get_db)
):
    auth.require_same_device(device, request.st_device_id)
    device.st_last_seen = datetime.now(timezone.utc)

    if request.st_session_id:
        active_session = db.query(models.STSessionActive).filter(
            models.STSessionActive.st_session_id == request.st_session_id,
            models.STSessionActive.st_device_id == device.st_device_id
        ).first()
        if active_session:
            active_session.st_last_heartbeat = datetime.now(timezone.utc)

    db.commit()

    return {
        "status": "success",
        "server_time": datetime.now(timezone.utc),
    }

@app.post("/api/event")
async def receive_event(
    request: schemas.EventRequest,
    device: models.STDevice = Depends(auth.require_device),
    db: Session = Depends(get_db)
):
    auth.require_same_device(device, request.st_device_id)
    # Use UTC for all logic to prevent "naive vs aware" errors
    now_utc = datetime.now(timezone.utc)

    # 1. Start-Session Events
    if request.st_event_type in ["login", "unlock", "switch_back"]:
        new_session = models.STSessionActive(
            st_session_id=request.st_session_id,
            st_device_id=request.st_device_id,
            st_user_name=request.st_user_name,
            st_start_time=now_utc,
            st_last_heartbeat=now_utc
        )
        db.add(new_session)
        db.commit()
        return {"status": "session_started", "id": request.st_session_id}

    # 2. End-Session Events
    elif request.st_event_type in ["logout", "lock", "switch_away"]:
        active_session = db.query(models.STSessionActive).filter(
            models.STSessionActive.st_session_id == request.st_session_id,
            models.STSessionActive.st_device_id == device.st_device_id
        ).first()

        if active_session:
            # Both are now timezone-aware, so subtraction works!
            duration = (now_utc - active_session.st_start_time).total_seconds()

            history_entry = models.STSessionHistory(
                st_device_id=request.st_device_id,
                st_hostname=request.st_hostname,
                st_user_name=request.st_user_name,
                st_start_time=active_session.st_start_time,
                st_end_time=now_utc,
                st_duration_sec=int(duration)
            )
            db.add(history_entry)
            db.delete(active_session)
            db.commit()
            return {"status": "session_archived", "duration": duration}

        return {"status": "ignored", "message": "No active session found"}

    return {"status": "error", "message": "Unknown event type"}

@app.post("/api/register")
async def register_device(
    request: schemas.DeviceRegisterRequest,
    db: Session = Depends(get_db),
    _: None = Depends(auth.require_enrollment)
):
    # Issue a fresh token on every registration (reissued on reimage)
    token = auth.generate_token()
    token_hash = auth.hash_token(token)

    db_device = db.query(models.STDevice).filter(
        models.STDevice.st_device_id == request.st_device_id
    ).first()

    if db_device:
        # Update existing device info (The "Delta" Strategy)
        db_device.st_hostname = request.st_hostname
        db_device.st_payload = request.st_payload
        db_device.st_last_seen = datetime.now(timezone.utc)
        db_device.st_schema_version = request.st_schema_version
        db_device.st_token_hash = token_hash
        db.commit()
        return {"status": "updated", "device_id": request.st_device_id, "device_token": token}

    # Create new device record
    new_device = models.STDevice(
        st_device_id=request.st_device_id,
        st_hostname=request.st_hostname,
        st_platform=request.st_platform,
        st_payload=request.st_payload,
        st_schema_version=request.st_schema_version,
        st_token_hash=token_hash,
        st_last_seen=datetime.now(timezone.utc)
    )
    db.add(new_device)
    db.commit()
    return {"status": "registered", "device_id": request.st_device_id, "device_token": token}
