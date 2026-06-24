"""
LeadForge POC — FastAPI Backend
Main application entry point
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
import sys

from app.core.config import settings
from app.db.database import init_db
from app.api import (
    auth_router, companies_router, ai_router,
    pipeline_router, campaigns_router, dashboard_router,
    apollo_router_obj, ncua_router,
)
from app.api.company_scrape import router as company_scrape_router
from app.api.gmail_auth import router as gmail_router

logger.remove()
logger.add(sys.stdout,
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}",
    level=settings.LOG_LEVEL)

app = FastAPI(
    title="LeadForge API",
    description="AI-powered Fintech B2B Intelligence Platform — with live NCUA & CUNA data",
    version="1.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Existing routes
app.include_router(auth_router,       prefix="/api/auth",      tags=["Auth"])
app.include_router(companies_router,  prefix="/api/companies", tags=["Companies"])
app.include_router(ai_router,         prefix="/api/ai",        tags=["AI Engine"])
app.include_router(pipeline_router,   prefix="/api/pipeline",  tags=["Pipeline"])
app.include_router(campaigns_router,  prefix="/api/campaigns", tags=["Campaigns"])
app.include_router(dashboard_router,  prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(apollo_router_obj, prefix="/api/apollo",    tags=["Apollo"])

# NEW: NCUA public API + CUNA intelligence routes
app.include_router(ncua_router,       prefix="/api/ncua",      tags=["NCUA + CUNA"])

# NEW: Company URL scraper (Settings auto-fill) + Gmail OAuth + outreach send
app.include_router(company_scrape_router, tags=["Settings"])
app.include_router(gmail_router,          tags=["Gmail"])


@app.get("/health", tags=["System"])
async def health_check():
    return {"status": "ok", "version": "1.1.0"}


@app.on_event("startup")
async def startup():
    logger.info("LeadForge starting — creating DB tables...")
    init_db()
    logger.info("Ready. NCUA API: /api/ncua/search  CUNA priorities: /api/ncua/cuna/priorities")
    logger.info("Swagger docs: http://localhost:8000/docs")
