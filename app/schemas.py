from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime

# 1. Device Registration (The "Identity" Contract)
class DeviceRegisterRequest(BaseModel):
    st_device_id: str = Field(..., description="Mac Serial or Windows Service Tag")
    st_hostname: str
    st_platform: str = Field(..., pattern="^(macOS|Windows)$")
    st_payload: Dict[str, Any] = Field(default_factory=dict)
    st_schema_version: int = 1

# 2. Heartbeat (The "Proof of Life" Contract)
class HeartbeatRequest(BaseModel):
    st_device_id: str
    st_hostname: str
    st_session_id: Optional[str] = None # Optional because a PC can pulse while locked

# 3. Event (The "Usage" Contract)
class EventRequest(BaseModel):
    st_device_id: str
    st_hostname: str
    st_user_name: str
    st_event_type: str = Field(..., description="login, logout, lock, unlock, switch_away, switch_back")
    st_session_id: str
    st_platform: str
    # Metadata for OS-specific nuances (e.g., 'lid_closed' vs 'button_pressed')
    st_event_metadata: Optional[Dict[str, Any]] = None