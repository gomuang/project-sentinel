from app.database import engine, Base
from app import models

print("Connecting to 'sentinel_db'...")
try:
    # This command tells SQLAlchemy to create all tables defined in models.py
    Base.metadata.create_all(bind=engine)
    print("Success! 'st_' tables have been created.")
except Exception as e:
    print(f"Error: {e}")