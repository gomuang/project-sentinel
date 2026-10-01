from sqlalchemy import Column, String, DateTime, Boolean, Integer, BigInteger, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from .database import Base
import datetime
import uuid

class STDevice(Base):
    __tablename__ = "st_devices"

    # Hardware Serial Number as the Primary Key
    st_device_id = Column(String, primary_key=True, index=True)
    st_hostname = Column(String, index=True)
    st_platform = Column(String)  # 'macOS' or 'Windows'
    st_is_active_asset = Column(Boolean, default=True)
    
    # Delta Hardware storage (JSONB for flexible telemetry)
    st_payload = Column(JSONB, default={})
    
    st_schema_version = Column(Integer, default=1)
    st_last_seen = Column(DateTime(timezone=True), default=datetime.datetime.now)

class STSessionActive(Base):
    __tablename__ = "st_sessions_active"

    # Unique ID for the "Active Slice"
    st_session_id = Column(String, primary_key=True, index=True)
    st_device_id = Column(String, ForeignKey("st_devices.st_device_id"))
    st_user_name = Column(String)
    
    st_start_time = Column(DateTime(timezone=True), default=datetime.datetime.now)
    st_last_heartbeat = Column(DateTime(timezone=True), default=datetime.datetime.now)

class STSessionHistory(Base):
    __tablename__ = "st_sessions_history"

    st_history_id = Column(BigInteger, primary_key=True, autoincrement=True)
    st_device_id = Column(String, index=True)
    st_hostname = Column(String)
    st_user_name = Column(String)
    
    st_start_time = Column(DateTime(timezone=True))
    st_end_time = Column(DateTime(timezone=True))
    st_duration_sec = Column(Integer)

class STCommand(Base):
    __tablename__ = "st_commands"

    # Unique ID for each remote command
    st_command_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    st_target_device_id = Column(String, ForeignKey("st_devices.st_device_id"))
    st_command_type = Column(String) # e.g., 'shell', 'inventory_update'
    st_payload = Column(String)      # The actual script or instruction
    st_status = Column(String, default="pending") # pending, sent, completed