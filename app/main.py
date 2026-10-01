from fastapi import FastAPI, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from . import models, schemas, database

# Initialize the FastAPI App
app = FastAPI(title="Sentinel Telemetry API")

# Dependency to get a database session
def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/")
def read_root():
    return {"status": "Sentinel Telemetry is Online", "version": "1.0.0"}

@app.post("/api/heartbeat")
async def receive_heartbeat(
    request: schemas.HeartbeatRequest, 
    db: Session = Depends(get_db)
):
    db_device = db.query(models.STDevice).filter(
        models.STDevice.st_device_id == request.st_device_id
    ).first()
    
    if not db_device:
        return {"status": "unregistered"}

    db_device.st_last_seen = datetime.now(timezone.utc)

    if request.st_session_id:
        active_session = db.query(models.STSessionActive).filter(
            models.STSessionActive.st_session_id == request.st_session_id
        ).first()
        if active_session:
            active_session.st_last_heartbeat = datetime.now(timezone.utc)

    # --- UPDATED LOGIC HERE ---
    # Find the command
    pending_cmd = db.query(models.STCommand).filter(
        models.STCommand.st_target_device_id == request.st_device_id,
        models.STCommand.st_status == "pending"
    ).first()

    payload_to_send = None
    if pending_cmd:
        payload_to_send = pending_cmd.st_payload
        # IMMEDIATELY mark as 'sent' so it doesn't loop
        pending_cmd.st_status = "sent" 
    # ---------------------------

    db.commit()

    return {
        "status": "success",
        "server_time": datetime.now(timezone.utc),
        "command": payload_to_send
    }

@app.post("/api/event")
async def receive_event(
    request: schemas.EventRequest, 
    db: Session = Depends(get_db)
):
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
            models.STSessionActive.st_session_id == request.st_session_id
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
    db: Session = Depends(get_db)
):
    # Check if the device already exists
    db_device = db.query(models.STDevice).filter(
        models.STDevice.st_device_id == request.st_device_id
    ).first()

    if db_device:
        # Update existing device info (The "Delta" Strategy)
        db_device.st_hostname = request.st_hostname
        db_device.st_payload = request.st_payload
        db_device.st_last_seen = datetime.now(timezone.utc)
        db_device.st_schema_version = request.st_schema_version
        db.commit()
        return {"status": "updated", "device_id": request.st_device_id}

    # Create new device record
    new_device = models.STDevice(
        st_device_id=request.st_device_id,
        st_hostname=request.st_hostname,
        st_platform=request.st_platform,
        st_payload=request.st_payload,
        st_schema_version=request.st_schema_version,
        st_last_seen=datetime.now(timezone.utc)
    )
    db.add(new_device)
    db.commit()
    return {"status": "registered", "device_id": request.st_device_id}

# A simple admin route to "queue up" a command for a device
@app.post("/api/admin/queue_command")
async def queue_command(
    device_id: str, 
    command_text: str, 
    db: Session = Depends(get_db)
):
    # Check if device exists
    device = db.query(models.STDevice).filter(models.STDevice.st_device_id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    new_cmd = models.STCommand(
        st_target_device_id=device_id,
        st_command_type="shell",
        st_payload=command_text,
        st_status="pending"
    )
    db.add(new_cmd)
    db.commit()
    return {"status": "command_queued", "command_id": new_cmd.st_command_id}