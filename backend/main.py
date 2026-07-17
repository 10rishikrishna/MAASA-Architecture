# backend/main.py
"""
MAASA - Multi-Agent Autonomous Software Architect
FastAPI Application Entrypoint
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from backend.config import settings
from backend.database import init_db
from backend.routers import auth_router, analyze_router, projects_router, chat_router


# ── App Lifecycle ─────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise database tables on startup."""
    try:
        init_db()
        print("[OK] Database tables initialized successfully.")
    except Exception as e:
        print(f"[ERROR] Error initializing database: {e}")
    yield


# ── Application ───────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.PROJECT_NAME,
    description=(
        "Multi-Agent Autonomous Software Architect — "
        "generates full architecture blueprints from a business problem description."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


# ── CORS ──────────────────────────────────────────────────────────────────────
# Allow React dev server (port 5173/3000) and any production domain.
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


# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(auth_router.router,     prefix=settings.API_V1_STR)
app.include_router(analyze_router.router,  prefix=settings.API_V1_STR)
app.include_router(projects_router.router, prefix=settings.API_V1_STR)
app.include_router(chat_router.router,     prefix=settings.API_V1_STR)


# ── Health / Root ─────────────────────────────────────────────────────────────

@app.get("/health", tags=["Health"])
def health_check():
    """Simple liveness check — returns 200 when the server is running."""
    return {"status": "ok", "service": settings.PROJECT_NAME}


@app.get("/", tags=["Health"])
def root():
    return {
        "status": "online",
        "service": settings.PROJECT_NAME,
        "docs_url": "/docs",
    }


if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)
