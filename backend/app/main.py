# app/main.py
import logging
import os
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import API routers
from app.api import plaid, analytics

# Import database
from app.db.database import init_db, engine, Base

# Import models to ensure they're registered with SQLAlchemy
from app.db.models import User, PlaidItem, Account, Transaction, Category, Budget

app = FastAPI(
    title="Personal Budget Tracker API",
    description="API for tracking personal finances using Plaid",
    version="0.1.0"
)

# Add CORS middleware for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update this with your frontend URL in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Check if we have a database URL configured
database_url = os.getenv("DATABASE_URL")
if not database_url:
    logger.warning(
        "DATABASE_URL not set. Using a default local connection string. "
        "For production, set the DATABASE_URL environment variable."
    )

# Register API routers
app.include_router(plaid.router)
app.include_router(analytics.router)

@app.on_event("startup")
async def startup_event():
    """Initialize the database on startup"""
    try:
        # Create database tables
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created")
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")

@app.get("/")
def root():
    """Root endpoint to verify API is running"""
    return {"message": "Personal Budget Tracker API is running", "status": "success"}

@app.get("/health")
def health_check():
    """Health check endpoint for monitoring"""
    return {"status": "healthy"}

