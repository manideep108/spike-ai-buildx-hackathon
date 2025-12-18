"""
FastAPI application entry point.
Multi-agent AI backend for Spike AI BuildX Hackathon.
"""

import logging
import sys
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import router
from config.settings import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)

logger = logging.getLogger(__name__)

# Create FastAPI application
app = FastAPI(
    title="Spike AI Hackathon - Multi-Agent Backend",
    description="Production-ready multi-agent AI backend for analytics and SEO queries",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(router)


@app.on_event("startup")
async def startup_event():
    """Application startup event."""
    logger.info("=" * 70)
    logger.info("SPIKE AI HACKATHON - MULTI-AGENT BACKEND")
    logger.info("=" * 70)
    logger.info(f"Server: {settings.server_host}:{settings.server_port}")
    logger.info(f"LiteLLM Model: {settings.litellm_model}")
    logger.info(f"GA4 Property: {settings.default_ga4_property_id or 'Not configured'}")
    logger.info(f"Sheets ID: {settings.sheets_spreadsheet_id or 'Not configured'}")
    if settings.demo_mode:
        logger.warning("⚠️  DEMO MODE ENABLED - Using mock data for failed API calls")
    logger.info("System ready - Listening for queries...")
    logger.info("=" * 70)


@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event."""
    logger.info("=" * 70)
    logger.info("Shutting down Multi-Agent Backend - Goodbye!")
    logger.info("=" * 70)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Spike AI Hackathon - Multi-Agent Backend",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "query": "/query",
            "health": "/health",
            "docs": "/docs",
        }
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host=settings.server_host,
        port=settings.server_port,
        reload=False,
    )
