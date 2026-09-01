import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from backend.app.main import app

def run_api_audit():
    client = TestClient(app)
    print("=== API AUDIT VERIFICATION ===")

    # 1. Health Endpoint
    res = client.get("/api/health")
    assert res.status_code == 200
    print("[OK] GET /api/health -> 200 OK")

    # 2. Register
    reg_payload = {
        "name": "Audit User",
        "email": "audit_user@example.com",
        "password": "password123"
    }
    res = client.post("/api/auth/register", json=reg_payload)
    if res.status_code == 400 and "already exists" in res.text:
        print("[OK] User already registered, proceeding to login.")
    else:
        assert res.status_code == 201
        print("[OK] POST /api/auth/register -> 201 Created")

    # 3. Login
    login_payload = {
        "email": "audit_user@example.com",
        "password": "password123"
    }
    res = client.post("/api/auth/login", json=login_payload)
    assert res.status_code == 200
    token = res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("[OK] POST /api/auth/login -> 200 OK (JWT Received)")

    # 4. Current User /me
    res = client.get("/api/auth/me", headers=headers)
    assert res.status_code == 200
    assert res.json()["email"] == "audit_user@example.com"
    print("[OK] GET /api/auth/me -> 200 OK")

    # 5. Start Session without file
    res = client.post("/api/interview/start", json={"selected_role": "Backend Developer"}, headers=headers)
    assert res.status_code == 200
    session_id = res.json()["session_id"]
    print(f"[OK] POST /api/interview/start -> 200 OK (Session: {session_id})")

    # 6. Get Session
    res = client.get(f"/api/interview/session/{session_id}", headers=headers)
    assert res.status_code == 200
    print(f"[OK] GET /api/interview/session/{{session_id}} -> 200 OK")

    # 7. Answer Question 1
    ans_payload = {
        "session_id": session_id,
        "question_id": 1,
        "answer": "I have experience with Python, FastAPI, PostgreSQL, Redis, and Docker."
    }
    res = client.post("/api/interview/answer", json=ans_payload, headers=headers)
    assert res.status_code == 200
    print("[OK] POST /api/interview/answer -> 200 OK (Adaptive Next Question Generated)")

    # 8. Evaluate Session
    res = client.post(f"/api/interview/evaluate?session_id={session_id}", headers=headers)
    assert res.status_code == 200
    print("[OK] POST /api/interview/evaluate -> 200 OK")

    # 9. Get Results
    res = client.get(f"/api/results/{session_id}", headers=headers)
    assert res.status_code == 200
    print("[OK] GET /api/results/{{session_id}} -> 200 OK")

    print("\n=== ALL ACTIVE API ROUTES VERIFIED & AUDITED SUCCESSFULLY! ===")

if __name__ == "__main__":
    run_api_audit()
