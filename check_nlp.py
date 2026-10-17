from types import SimpleNamespace
from backend.app.services.nlp_service import nlp_service

q = SimpleNamespace(
    id=1,
    question="Explain why normalization of pixel values is important before feeding images into a CNN.",
    topic="Computer Vision",
    difficulty="easy",
    expected_concepts=[],
)

result = nlp_service.evaluate_single_answer(
    job_title="Software Engineer",
    question=q,
    transcript="Normalization scales pixel values, for example to 0 to 1, so training is stable and converges faster.",
    resume_context={},
)

for key in ("evaluation_method", "overall_nlp_score", "combined_nlp_score",
            "structured_score", "evaluation_status", "evaluation_error", "feedback"):
    print(key, "=", result.get(key))
transcripts = [
    "Hmm. Uh, it's a bit confusing. Next question.",
    "Can you describe the... Yeah, different... Hmm...",
    "...",
    "Mm, um, um,",
]

for t in transcripts:
    result = nlp_service.evaluate_single_answer(
        job_title="Software Engineer", question=q, transcript=t, resume_context={},
    )
    print(repr(t))
    for key in ("evaluation_method", "overall_nlp_score", "combined_nlp_score",
                "structured_score", "evaluation_error"):
        print("  ", key, "=", result.get(key))