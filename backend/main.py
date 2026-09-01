"""
Backend Application Entry Point
Exposes the FastAPI application instance from backend.app.main:app
Run command: uvicorn backend.app.main:app --reload
"""
from backend.app.main import app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True)
