from pathlib import Path

from sqlalchemy import text

from app.database import engine, Base
from app import models

print("Connecting to 'sentinel_db'...")
try:
    # This command tells SQLAlchemy to create all tables defined in models.py
    Base.metadata.create_all(bind=engine)
    # create_all never alters existing tables, so add columns introduced later.
    # ponytail: hand-rolled migration; switch to Alembic once there's a second one.
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE st_devices ADD COLUMN IF NOT EXISTS st_token_hash VARCHAR"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_st_devices_st_token_hash ON st_devices (st_token_hash)"))
        # Reporting function: SELECT * FROM usage_report('2025-08-20', '2025-12-15');
        conn.execute(text(Path(__file__).with_name("usage_report.sql").read_text()))
    print("Success! 'st_' tables and usage_report() are in place.")
except Exception as e:
    print(f"Error: {e}")