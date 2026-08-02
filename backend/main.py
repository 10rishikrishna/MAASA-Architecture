# backend/main.py
"""
Mosaic Studio - Virtual Architecture Workspace
FastAPI Application Entrypoint
"""
import logging
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from backend.config import settings
from backend.database import init_db
from backend.routers import (
    auth_router,
    analyze_router,
    projects_router,
    chat_router,
    teams_router,
    shares_router,
    apikeys_router,
    audit_router,
)

# ── Structured Logging ────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("mosaic_studio")

# ── App Lifecycle ─────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise database tables and services on startup."""
    try:
        init_db()
        logger.info("Database tables initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
    yield
    logger.info("Mosaic Studio shutting down")


# ── Application ───────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.PROJECT_NAME,
    description=(
        "Mosaic Studio - Virtual Architecture Workspace: "
        "AI-powered platform that generates comprehensive system architecture blueprints "
        "from a business problem description using multiple specialized AI agents."
    ),
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


# ── CORS ──────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request Timing Middleware ──────────────────────────────────────────────────

@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(round(process_time, 4))
    logger.info(
        f"{request.method} {request.url.path} | "
        f"Status: {response.status_code} | "
        f"Time: {process_time:.4f}s"
    )
    return response


# ── Global Exception Handler ──────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Please try again later."},
    )


# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(auth_router.router,     prefix=settings.API_V1_STR)
app.include_router(analyze_router.router,  prefix=settings.API_V1_STR)
app.include_router(projects_router.router, prefix=settings.API_V1_STR)
app.include_router(chat_router.router,     prefix=settings.API_V1_STR)
app.include_router(teams_router.router,    prefix=settings.API_V1_STR)
app.include_router(shares_router.router,   prefix=settings.API_V1_STR)
app.include_router(apikeys_router.router,  prefix=settings.API_V1_STR)
app.include_router(audit_router.router,    prefix=settings.API_V1_STR)


# ── Health / Metrics ──────────────────────────────────────────────────────────

@app.get("/health", tags=["Health"])
def health_check():
    """Liveness + readiness probe — returns service health status."""
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": "2.0.0",
        "observability": {
            "prometheus": f"http://localhost:{settings.PROMETHEUS_PORT}/metrics",
            "grafana": "http://localhost:3000",
            "jaeger": "http://localhost:16686",
        },
    }


@app.get("/", tags=["Health"])
def root():
    return {
        "status": "online",
        "service": settings.PROJECT_NAME,
        "docs_url": "/docs",
        "version": "2.0.0",
    }


@app.get("/metrics", tags=["Observability"])
def metrics():
    """Prometheus-compatible metrics endpoint."""
    return {
        "help": "Use Prometheus client library for detailed metrics",
        "counters": [
            "mosaic_http_requests_total",
            "mosaic_http_request_duration_seconds",
            "mosaic_analysis_started_total",
            "mosaic_analysis_completed_total",
            "mosaic_chat_messages_total",
            "mosaic_auth_login_total",
        ],
        "gauges": [
            "mosaic_active_users",
            "mosaic_active_analyses",
            "mosaic_database_connections",
        ],
    }


if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)
