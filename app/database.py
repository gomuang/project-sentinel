import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Load the variables from the .env file
load_dotenv()

# Get the URL we just defined
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")

# Create the engine (the connection pool)
# Note: psycopg2 is used here by default by SQLAlchemy for postgresql://
engine = create_engine(SQLALCHEMY_DATABASE_URL)

# Create a session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# The base class for our database tables
Base = declarative_base()