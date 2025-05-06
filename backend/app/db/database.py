import os
from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import text
import logging

logger = logging.getLogger(__name__)

# Database URL from environment variables
DATABASE_URL = os.getenv("DATABASE_URL")

# Check if DATABASE_URL is set
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set")


# If using Neon PostgreSQL, we need to modify connection string to handle SSL
if "neon.tech" in DATABASE_URL:
    # Ensure SSL mode is used for Neon
    if "?" not in DATABASE_URL:
        DATABASE_URL += "?sslmode=require"
    elif "sslmode=" not in DATABASE_URL:
        DATABASE_URL += "&sslmode=require"

# Create SQLAlchemy engine with appropriate configurations
engine = create_engine(
    DATABASE_URL,
    pool_size=5,        # Adjust based on expected concurrent connections 
    max_overflow=10,    # Allows creating additional connections
    pool_timeout=30,    # Timeout for getting connection from pool
    pool_pre_ping=True  # Check connection is valid before using it
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create base class for models
Base = declarative_base()

# Create metadata object for raw SQL operations
metadata = MetaData()

def get_db():
    """
    Get database session
    
    Yields:
        SQLAlchemy session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def execute_raw_sql(query, params=None):
    """
    Execute raw SQL query
    
    Args:
        query: SQL query string
        params: Parameters for the query
        
    Returns:
        Query result
    """
    with engine.connect() as connection:
        if params:
            result = connection.execute(text(query), params)
        else:
            result = connection.execute(text(query))
        return result
        
def init_db():
    """Initialize database"""
    # Create tables
    Base.metadata.create_all(bind=engine)
    logger.info("Database initialized")