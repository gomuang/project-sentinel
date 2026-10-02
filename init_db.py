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
    print("Success! 'st_' tables have been created.")
except Exception as e:
    print(f"Error: {e}")