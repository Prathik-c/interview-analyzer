from fastapi import APIRouter
from backend.app.api.routes import auth, health, resume, interview, results

api_router = APIRouter(prefix="/api")

api_router.include_router(auth.router, tags=["Authentication"])
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(resume.router, tags=["Resume"])
api_router.include_router(interview.router, tags=["Interview"])
api_router.include_router(results.router, tags=["Results"])
