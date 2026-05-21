import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from config import settings
from routers import auth, streamers, leads, payouts, schedule, tools, users
from posting import router as posting_router

BASE_DIR = Path(__file__).resolve().parent

# Ensure uploads directory exists before mounting
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from posting.scheduler import start_scheduler, shutdown_scheduler
    await start_scheduler()
    yield
    await shutdown_scheduler()


app = FastAPI(
    title="StreamX API",
    version="1.0.0",
    description="Backend for StreamX streamer management platform",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ─── CORS ─────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers ──────────────────────────────────────────────────────────────────

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(streamers.router, prefix="/api/streamers", tags=["streamers"])
app.include_router(leads.router, prefix="/api/leads", tags=["leads"])
app.include_router(payouts.router, prefix="/api/payouts", tags=["payouts"])
app.include_router(schedule.router, prefix="/api/schedule", tags=["schedule"])
app.include_router(tools.router, prefix="/api/tools", tags=["tools"])
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(posting_router.router, prefix="/api/admin", tags=["posting"])

# Serve uploaded images
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")


# ─── Health check ─────────────────────────────────────────────────────────────

@app.get("/health", tags=["system"])
async def health():
    return {"status": "ok", "version": "1.0.0"}


@app.get("/", include_in_schema=False)
async def root():
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.get("/admin", include_in_schema=False)
@app.get("/admin.html", include_in_schema=False)
async def admin_page():
    return FileResponse(BASE_DIR / "static" / "admin.html")


@app.get("/admin-login", include_in_schema=False)
@app.get("/admin-login.html", include_in_schema=False)
async def admin_login_page():
    return FileResponse(BASE_DIR / "static" / "admin-login.html")
