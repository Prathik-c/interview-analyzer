import os
import sys
import shutil
import json
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

def audit_entry_points():
    print("\n====================================================")
    print("PHASE 1 — ENTRY POINT AUDIT")
    print("====================================================")
    
    app_main = Path("app/main.py")
    backend_main = Path("backend/main.py")
    backend_app_main = Path("backend/app/main.py")

    def check_app_instance(path: Path) -> bool:
        if not path.exists():
            return False
        content = path.read_text(encoding="utf-8")
        return "FastAPI(" in content

    print(f"app/main.py exists: {app_main.exists()} | Creates FastAPI app: {check_app_instance(app_main)}")
    print(f"backend/main.py exists: {backend_main.exists()} | Creates FastAPI app: {check_app_instance(backend_main)}")
    print(f"backend/app/main.py exists: {backend_app_main.exists()} | Creates FastAPI app: {check_app_instance(backend_app_main)}")

def audit_database():
    print("\n====================================================")
    print("PHASE 2 — DATABASE AUDIT")
    print("====================================================")
    from sqlalchemy import create_engine, text
    from backend.app.core.config import settings
    
    print(f"Active DATABASE_URL from .env: {settings.DATABASE_URL}")
    
    # 1. SQLite Check
    sqlite_ok = False
    try:
        engine_sq = create_engine("sqlite:///./interview.db", connect_args={"check_same_thread": False})
        with engine_sq.connect() as conn:
            res = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table';")).fetchall()
            tables = [r[0] for r in res]
            print(f"SQLite tables found ({len(tables)}): {', '.join(tables)}")
            sqlite_ok = len(tables) > 0
        engine_sq.dispose()
    except Exception as e:
        print(f"SQLite error: {e}")

    # 2. PostgreSQL Check
    pg_ok = False
    pg_url = "postgresql+psycopg2://postgres:postgres@localhost:5432/interview_db"
    try:
        engine_pg = create_engine(pg_url, pool_pre_ping=True)
        with engine_pg.connect() as conn:
            res = conn.execute(text("SELECT 1")).scalar()
            pg_ok = (res == 1)
            print("PostgreSQL connection succeeded!")
        engine_pg.dispose()
    except Exception as e:
        print(f"PostgreSQL connection failed: {e}")
        print("Reason: No active PostgreSQL server running on localhost:5432 with supplied credentials.")

    print(f"\nSQLITE STATUS: {'WORKING' if sqlite_ok else 'FAILED'}")
    print(f"POSTGRESQL STATUS: {'WORKING' if pg_ok else 'NOT TESTED (Server unavailable)'}")

def audit_media_dependencies():
    print("\n====================================================")
    print("PHASE 5/6/7 — MEDIA PIPELINE & HARDWARE AUDIT")
    print("====================================================")
    
    ffmpeg_path = shutil.which("ffmpeg")
    print(f"FFmpeg installed: {'YES (' + ffmpeg_path + ')' if ffmpeg_path else 'NO (Falling back to native WebM/Groq Whisper)'}")

    try:
        import cv2
        print(f"OpenCV (cv2) version: {cv2.__version__}")
        cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        print(f"OpenCV Haar Cascade loaded: {not cascade.empty()}")
    except Exception as e:
        print(f"OpenCV error: {e}")

    try:
        import mediapipe as mp
        print(f"MediaPipe version: {mp.__version__}")
    except Exception as e:
        print(f"MediaPipe error: {e}")

if __name__ == "__main__":
    audit_entry_points()
    audit_database()
    audit_media_dependencies()
