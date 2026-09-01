from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.app.core.config import settings
from backend.app.api.router import api_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Clean Architecture AI-Powered Multimodal Interview Performance Analyser API with Adaptive AI Engine & PostgreSQL Persistence",
    version="2.0.0"
)

# CORS Middleware Setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Mount Static Frontend Assets & Uploads
app.mount("/assets", StaticFiles(directory=settings.FRONTEND_DIR), name="frontend-assets")
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

# Include Centralized API Router (/api)
app.include_router(api_router)

# Page Routes for Single Page Application navigation
@app.get("/", include_in_schema=False)
async def home_page():
    return FileResponse(settings.FRONTEND_DIR / "index.html")

@app.get("/resume", include_in_schema=False)
async def resume_page():
    return FileResponse(settings.FRONTEND_DIR / "index.html")

@app.get("/interview", include_in_schema=False)
async def interview_page():
    return FileResponse(settings.FRONTEND_DIR / "interview.html")

@app.get("/results", include_in_schema=False)
async def results_page():
    return FileResponse(settings.FRONTEND_DIR / "results.html")
