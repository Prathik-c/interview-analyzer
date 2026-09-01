import os
from sqlalchemy import create_engine
from backend.app.db.session import Base
from backend.app.db.models import (
    UserDB, AssessmentSessionDB, QuestionDB, SubmissionDB, FinalEvaluationDB
)
from backend.app.core.security import get_password_hash

def test_sqlite():
    print("--- Testing SQLite Development Fallback ---")
    sqlite_url = "sqlite:///./test_interview.db"
    engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    print("SQLite tables created successfully.")
    
    # Test cleanup
    engine.dispose()
    if os.path.exists("test_interview.db"):
        os.remove("test_interview.db")

    return True

def test_postgres():
    print("--- Testing PostgreSQL Integration ---")
    pg_urls = [
        os.getenv("DATABASE_URL", ""),
        "postgresql+psycopg2://postgres:postgres@localhost:5432/interview_db",
        "postgresql+psycopg2://postgres:123456@localhost:5432/interview_db",
        "postgresql+psycopg2://postgres:root@localhost:5432/interview_db"
    ]
    
    connected_url = None
    for url in pg_urls:
        if not url or not url.startswith("postgresql"):
            continue
        try:
            engine = create_engine(url, pool_pre_ping=True)
            with engine.connect() as conn:
                print(f"Successfully connected to PostgreSQL at: {url.split('@')[-1]}")
                Base.metadata.create_all(bind=engine)
                print("PostgreSQL tables created successfully.")
                connected_url = url
                break
        except Exception as e:
            print(f"PostgreSQL connection attempt failed for {url.split('@')[-1]}: {e}")

    if not connected_url:
        print("PostgreSQL instance not currently active on localhost (SQLite fallback active).")
        return False
    return True

if __name__ == "__main__":
    sqlite_ok = test_sqlite()
    pg_ok = test_postgres()
    print("\nDATABASE TEST SUMMARY:")
    print(f"SQLite Tested: YES | Working: {'YES' if sqlite_ok else 'NO'}")
    print(f"PostgreSQL Tested: YES | Working: {'YES' if pg_ok else 'NO'}")
