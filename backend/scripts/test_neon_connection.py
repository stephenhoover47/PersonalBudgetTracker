#!/usr/bin/env python3
"""
Script to test connection to Neon PostgreSQL database.
"""
import os
import sys
import logging
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables
load_dotenv()

def test_connection():
    """Test connection to Neon PostgreSQL database."""
    try:
        # Get database URL from environment
        database_url = os.getenv("DATABASE_URL")
        
        if not database_url:
            logger.error("DATABASE_URL environment variable not set")
            return False
        
        logger.info(f"Testing connection to: {database_url.split('@')[1].split('/')[0]}")
        
        # Create engine with SSL mode for Neon
        if "neon.tech" in database_url:
            if "?" not in database_url:
                database_url += "?sslmode=require"
            elif "sslmode=" not in database_url:
                database_url += "&sslmode=require"
        
        # Create engine
        engine = create_engine(
            database_url,
            pool_pre_ping=True,
            connect_args={"connect_timeout": 10}
        )
        
        # Test connection
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            if result.scalar() == 1:
                logger.info("✅ Successfully connected to Neon PostgreSQL database")
                
                # Get database version
                version = connection.execute(text("SELECT version()")).scalar()
                logger.info(f"Database version: {version}")
                
                return True
    except Exception as e:
        logger.error(f"❌ Failed to connect to database: {str(e)}")
        return False

if __name__ == "__main__":
    if test_connection():
        sys.exit(0)
    else:
        logger.info("""
To set up a Neon PostgreSQL database:
1. Create a free account at https://neon.tech
2. Create a new project and database
3. Get your connection string from the Neon dashboard
4. Update your .env file with:
   DATABASE_URL=postgresql://username:password@endpoint.neon.tech/database?sslmode=require
        """)
        sys.exit(1)