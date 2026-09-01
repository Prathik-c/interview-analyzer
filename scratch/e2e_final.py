"""Full end-to-end pipeline test against the live server."""
import sys
import json
import requests
from pathlib import Path

BASE = "http://localhost:8000/api"
ROLE = "Full Stack Developer"
RESUME_PATH = Path("scratch/test_resume.pdf")
WAV_PATH = Path("scratch/test_audio.wav")

results = []

def check(label, condition, detail=""):
    symbol = "PASS" if condition else "FAIL"
    msg = "  [{}] {}".format(symbol, label)
    if detail:
        msg += " -> {}".format(detail)
    print(msg)
    results.append((label, condition))
    return condition

def section(title):
    print("\n=== {} ===".format(title))

# STEP 1: Health
section("STEP 1: Health Check")
try:
    r = requests.get("{}/health".format(BASE), timeout=5)
    check("Health 200", r.status_code == 200, r.text[:60])
except Exception as e:
    check("Health 200", False, str(e))
    sys.exit(1)

# STEP 2: Resume Upload
section("STEP 2: Resume Upload -> Session Creation")
session_id = None
questions = []
try:
    with open(RESUME_PATH, "rb") as f:
        r = requests.post(
            "{}/resume/upload".format(BASE),
            files={"file": ("test_resume.pdf", f, "application/pdf")},
            data={"selected_role": ROLE},
            timeout=90
        )
    check("POST /resume/upload 200", r.status_code == 200, "status={}".format(r.status_code))
    if r.status_code == 200:
        data = r.json()
        session_id = data.get("session_id")
        questions = data.get("questions", [])
        check("session_id returned", bool(session_id), str(session_id))
        check("Questions >= 1", len(questions) >= 1, "{} questions".format(len(questions)))
        check("resume_data extracted", bool(data.get("resume_data")))
        print("  session_id: {}".format(session_id))
        for i, q in enumerate(questions[:3]):
            print("  Q{}: {}".format(i + 1, q["question"][:70]))
    else:
        print("  Error: {}".format(r.text[:300]))
        sys.exit(1)
except Exception as e:
    check("Resume upload", False, str(e))
    sys.exit(1)

# STEP 3: DB persistence check
section("STEP 3: Session Persisted in Database")
try:
    r = requests.get("{}/interview/session/{}".format(BASE, session_id), timeout=10)
    check("GET /session 200", r.status_code == 200)
    if r.status_code == 200:
        s = r.json()
        check("status=active", s.get("status") == "active", s.get("status"))
        check("questions in DB", len(s.get("questions", [])) >= 1)
except Exception as e:
    check("Session DB check", False, str(e))

# STEP 4: Text answers
section("STEP 4: Text Answer Submissions")
ANSWERS = [
    "I have four years building full-stack apps with React FastAPI and PostgreSQL deploying on AWS with Docker.",
    "For optimization I use EXPLAIN ANALYZE proper indexing Redis caching and connection pooling.",
    "I containerize with Docker orchestrate with Kubernetes and use Helm charts for zero downtime deployments.",
    "My debugging uses structured logs distributed tracing with Jaeger and isolated reproduction environments.",
    "I follow SOLID principles write pytest tests conduct code reviews and maintain clear API documentation."
]
submitted = 0
for i, q in enumerate(questions):
    qid = q["id"]
    answer = ANSWERS[i % len(ANSWERS)]
    try:
        r = requests.post(
            "{}/interview/answer".format(BASE),
            json={"session_id": session_id, "question_id": qid, "answer": answer},
            timeout=15
        )
        if r.status_code == 200:
            submitted += 1
        check("Q{} answer (id={})".format(i + 1, qid), r.status_code == 200,
              "status={}".format(r.status_code))
    except Exception as e:
        check("Q{} answer".format(i + 1), False, str(e))
check("All questions submitted", submitted == len(questions),
      "{}/{}".format(submitted, len(questions)))

# STEP 5: WAV recording for Q1
section("STEP 5: Recording Upload -> Speech + Video Metrics")
first_qid = questions[0]["id"]
try:
    with open(WAV_PATH, "rb") as f:
        r = requests.post(
            "{}/interview/{}/recording".format(BASE, session_id),
            files={"video": ("question_{}.wav".format(first_qid), f, "audio/wav")},
            data={"question_id": first_qid},
            timeout=90
        )
    check("POST /recording 200", r.status_code == 200, "status={}".format(r.status_code))
    if r.status_code == 200:
        rd = r.json()
        sm = rd.get("speech_metrics") or {}
        vm = rd.get("video_metrics") or {}
        check("speech_metrics returned", bool(sm), str(sm))
        check("video_metrics returned", bool(vm), str(vm))
        check("speech_score in sm", "speech_score" in sm)
        check("video_score in vm", "video_score" in vm)
        print("  Speech: WPM={} Fillers={} Score={}".format(
            sm.get("words_per_minute"), sm.get("filler_word_count"), sm.get("speech_score")))
        print("  Video:  FaceVis={} Posture={} Score={}".format(
            vm.get("face_visibility_score"), vm.get("posture_score"), vm.get("video_score")))
    else:
        print("  Error: {}".format(r.text[:200]))
except Exception as e:
    check("Recording upload", False, str(e))

# STEP 6: Multimodal Evaluation
section("STEP 6: POST /evaluate -> NLP + Multimodal Score")
try:
    r = requests.post(
        "{}/interview/evaluate?session_id={}".format(BASE, session_id),
        timeout=120
    )
    check("POST /evaluate 200", r.status_code == 200, "status={}".format(r.status_code))
    if r.status_code == 200:
        ev = r.json().get("evaluation", {})
        check("overall_score", "overall_score" in ev, str(ev.get("overall_score")))
        check("nlp_score", "nlp_score" in ev, str(ev.get("nlp_score")))
        check("speech_score", "speech_score" in ev, str(ev.get("speech_score")))
        check("video_score", "video_score" in ev, str(ev.get("video_score")))
        check("summary", bool(ev.get("summary")))
        per_q = ev.get("per_question", [])
        check("per_question >= 1", len(per_q) >= 1, "{} items".format(len(per_q)))
        print("  Overall={}/100  NLP={}% Speech={}% Video={}%".format(
            ev.get("overall_score"), ev.get("nlp_score"),
            ev.get("speech_score"), ev.get("video_score")))
        summary_text = str(ev.get("summary", ""))
        print("  Summary: {}".format(summary_text[:120]))
    else:
        print("  Error: {}".format(r.text[:300]))
except Exception as e:
    check("Evaluation", False, str(e))

# STEP 7: Results endpoint
section("STEP 7: GET /results/{id}")
try:
    r = requests.get("{}/results/{}".format(BASE, session_id), timeout=10)
    check("GET /results 200", r.status_code == 200, "status={}".format(r.status_code))
    if r.status_code == 200:
        rd = r.json()
        check("evaluation in results", bool(rd.get("evaluation")))
        check("session_id matches", rd.get("session_id") == session_id)
        check("selected_role correct", rd.get("selected_role") == ROLE)
except Exception as e:
    check("Results endpoint", False, str(e))

# STEP 8: Final DB status
section("STEP 8: Session Status = completed in DB")
try:
    r = requests.get("{}/interview/session/{}".format(BASE, session_id), timeout=10)
    if r.status_code == 200:
        s = r.json()
        check("status=completed", s.get("status") == "completed", s.get("status"))
        check("evaluation stored in session", bool(s.get("evaluation")))
except Exception as e:
    check("Final DB check", False, str(e))

# SUMMARY
total = len(results)
passed = sum(1 for _, ok in results if ok)
failed = total - passed
print("\n=== SUMMARY ===")
print("Total: {}  Passed: {}  Failed: {}".format(total, passed, failed))
if failed:
    print("Failed checks:")
    for label, ok in results:
        if not ok:
            print("  - {}".format(label))
else:
    print("ALL CHECKS PASSED")
print("Completed session_id: {}".format(session_id))
sys.exit(0 if failed == 0 else 1)
