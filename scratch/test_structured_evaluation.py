import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.core.config import settings
from backend.app.schemas.question import QuestionItem
from backend.app.services.nlp_service import NLPService
from backend.app.services.structured_evaluator import LocalStructuredEvaluator, structured_evaluator
from backend.app.services.interview_service import interview_service
from backend.app.storage.session_storage import session_storage

def run_tests():
    print("=" * 60)
    print("RUNNING INTERVIEW ANALYZER STRUCTURED EVALUATION TESTS")
    print("=" * 60)

    evaluator = LocalStructuredEvaluator()
    nlp = NLPService()

    # TEST 1: Normal Answer
    print("\n--- TEST 1: Normal Answer ---")
    q1 = QuestionItem(id=1, question="What is the difference between a process and a thread?", topic="Operating Systems")
    ans1 = (
        "A process is an independent executing program with its own dedicated memory space and address space. "
        "A thread is a lightweight unit of execution within a process that shares memory and resources with other threads."
    )
    res1 = nlp.evaluate_single_answer(job_title="Software Engineer", question=q1, transcript=ans1, resume_context={})
    print(f"Technical Score (Groq): {res1['technical_score']}")
    print(f"Overall NLP Score (Groq): {res1['overall_nlp_score']}")
    print(f"Structured Score: {res1.get('structured_score')}")
    print(f"Combined NLP Score: {res1.get('combined_nlp_score')}")
    print(f"Major Misconception: {res1.get('major_misconception')}")
    print(f"Needs Follow-up: {res1.get('needs_followup')}")

    assert "overall_nlp_score" in res1
    assert "combined_nlp_score" in res1
    assert res1.get("structured_score") is not None
    assert res1.get("major_misconception") is False
    print(">>> TEST 1 PASSED!")

    # TEST 2: Empty Answer
    print("\n--- TEST 2: Empty Answer ---")
    res2 = nlp.evaluate_single_answer(job_title="Software Engineer", question=q1, transcript="", resume_context={})
    print(f"Overall NLP Score: {res2['overall_nlp_score']}")
    print(f"Structured Score: {res2.get('structured_score')}")
    print(f"Combined NLP Score: {res2.get('combined_nlp_score')}")
    print(f"Needs Follow-up: {res2.get('needs_followup')}")
    assert res2["overall_nlp_score"] == 30
    assert res2.get("structured_score") == 0
    assert res2.get("combined_nlp_score") == 30
    assert res2.get("needs_followup") is True
    print(">>> TEST 2 PASSED!")

    # TEST 3: Clearly Correct Answer
    print("\n--- TEST 3: Clearly Correct Answer ---")
    struct_res3 = evaluator.evaluate(
        job_role="Software Engineer",
        question=q1,
        candidate_answer="A process has its own isolated memory space. Threads exist within a process and share memory and heap space."
    )
    print(f"Technical Correctness: {struct_res3['technical_correctness']}")
    print(f"Relevance: {struct_res3['relevance']}")
    print(f"Completeness: {struct_res3['completeness']}")
    print(f"Structured Score: {struct_res3['structured_score']}")
    print(f"Misconception: {struct_res3['major_misconception']}")
    assert struct_res3["technical_correctness"] >= 80
    assert struct_res3["relevance"] >= 80
    assert struct_res3["major_misconception"] is False
    print(">>> TEST 3 PASSED!")

    # TEST 4: Answer with Major Misconception
    print("\n--- TEST 4: Answer with Major Misconception ---")
    ans4 = "A thread always has its own completely separate memory from the process and cannot share resources."
    res4 = nlp.evaluate_single_answer(job_title="Software Engineer", question=q1, transcript=ans4, resume_context={})
    print(f"Structured Evaluation: {res4.get('structured_evaluation')}")
    print(f"Major Misconception: {res4.get('major_misconception')}")
    print(f"Needs Follow-up: {res4.get('needs_followup')}")
    assert res4.get("major_misconception") is True
    assert res4.get("needs_followup") is True
    assert res4.get("structured_score") <= 50
    print(">>> TEST 4 PASSED!")

    # TEST 5: Structured Evaluator Disabled
    print("\n--- TEST 5: Structured Evaluator Disabled ---")
    original_enabled = settings.STRUCTURED_EVALUATION_ENABLED
    try:
        settings.STRUCTURED_EVALUATION_ENABLED = False
        res5 = nlp.evaluate_single_answer(job_title="Software Engineer", question=q1, transcript=ans1, resume_context={})
        print(f"Overall NLP Score: {res5['overall_nlp_score']}")
        print(f"Combined NLP Score: {res5['combined_nlp_score']}")
        print(f"Structured Score: {res5.get('structured_score')}")
        assert res5["combined_nlp_score"] == res5["overall_nlp_score"]
        assert res5.get("structured_score") is None
        print(">>> TEST 5 PASSED!")
    finally:
        settings.STRUCTURED_EVALUATION_ENABLED = original_enabled

    # TEST 6: Groq Unavailable / Mock Fallback
    print("\n--- TEST 6: Groq Client None Fallback ---")
    nlp_no_client = NLPService()
    nlp_no_client.client = None
    res6 = nlp_no_client.evaluate_single_answer(job_title="Software Engineer", question=q1, transcript=ans1, resume_context={})
    print(f"Fallback Groq Score: {res6['overall_nlp_score']}")
    print(f"Combined Score: {res6['combined_nlp_score']}")
    assert res6["combined_nlp_score"] is not None
    assert "feedback" in res6
    print(">>> TEST 6 PASSED!")

    # TEST 7: Full 5-Question Interview Simulation
    print("\n--- TEST 7: Full Interview Session Flow ---")
    session = interview_service.create_interview_session(
        selected_role="Software Engineer",
        filename="test_interview.pdf",
        pdf_content=b"%PDF-1.4 test empty resume content",
        user_id="test_user_zero_cost"
    )
    session_id = session.session_id
    print(f"Created session {session_id} with {len(session.questions)} questions.")

    answers = [
        "A process is an independent program with its own address space, while threads share memory within the same process.",
        "REST APIs use standard HTTP verbs like GET, POST, PUT, DELETE and are stateless.",
        "ACID stands for Atomicity, Consistency, Isolation, and Durability in relational database transactions.",
        "Binary search operates on sorted collections with logarithmic time complexity O(log N).",
        "Docker provides OS-level virtualization to package dependencies and code into reproducible lightweight containers."
    ]

    for q_idx in range(1, 6):
        ans_text = answers[q_idx - 1]
        submission_res = interview_service.process_answer_submission(
            session_id=session_id,
            question_id=q_idx,
            user_id="test_user_zero_cost",
            answer_text=ans_text
        )
        print(f"Question {q_idx} submitted. Per-question score: {submission_res['per_question_score']}, NLP score: {submission_res['nlp_score']}")
        assert submission_res["accepted"] is True
        assert "nlp_evaluation" in submission_res
        assert "combined_nlp_score" in submission_res["nlp_evaluation"]

    # Final Evaluation
    eval_session = interview_service.evaluate_session(session_id, user_id="test_user_zero_cost")
    assert eval_session.status == "completed"
    assert eval_session.evaluation is not None
    print(f"Final Evaluation Overall Score: {eval_session.evaluation.overall_score}")
    print(f"Final NLP Score: {eval_session.evaluation.nlp_score}")
    print(f"Final Speech Score: {eval_session.evaluation.speech_score}")
    print(f"Final Video Score: {eval_session.evaluation.video_score}")
    print(f"Per-question count: {len(eval_session.evaluation.per_question)}")
    print(">>> TEST 7 PASSED!")

    print("\n" + "=" * 60)
    print("ALL TESTS COMPLETED SUCCESSFULLY WITH 100% ZERO-COST LOCAL LOGIC!")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()
