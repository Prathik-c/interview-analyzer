import json
from typing import List, Dict, Any
from groq import Groq
from backend.app.core.config import settings
from backend.app.schemas.question import QuestionItem
from backend.app.schemas.interview import AnswerSubmission

SINGLE_QUESTION_NLP_PROMPT = """You are a senior technical interviewer evaluating a single answer.

Input:
- Job Role
- Question & Topic
- Candidate Speech Transcript

Evaluate the technical answer for:
1. Technical Correctness (0-100)
2. Relevance (0-100)
3. Depth & Specificity (0-100)
4. Clarity (0-100)

Output ONLY valid JSON matching this schema:
{
  "technical_score": <int 0-100>,
  "relevance_score": <int 0-100>,
  "depth_score": <int 0-100>,
  "clarity_score": <int 0-100>,
  "overall_nlp_score": <int 0-100>,
  "strengths": ["<strength 1>", "<strength 2>"],
  "knowledge_gaps": ["<gap 1>"],
  "topics_detected": ["<topic 1>", "<topic 2>"],
  "feedback": "<1-2 sentences of constructive feedback>"
}"""

FULL_EVALUATION_PROMPT = """You are a senior technical interviewer and evaluator giving a final interview evaluation.

Output ONLY valid JSON matching this schema:
{
  "overall_score": <int 0-100>,
  "summary": "<2-3 sentence overall assessment>",
  "strengths": ["<strength 1>", "<strength 2>", "<strength 3>"],
  "gaps": ["<gap 1>", "<gap 2>", "<gap 3>"],
  "recommendations": ["<rec 1>", "<rec 2>"],
  "per_question": [
    {
      "question_id": <int>,
      "question": "<string>",
      "score": <int 0-100>,
      "feedback": "<1-2 sentences of specific feedback>"
    }
  ]
}"""

import logging
from backend.app.services.structured_evaluator import structured_evaluator
from backend.app.services.answer_quality import classify_answer

logger = logging.getLogger("nlp_service")

class NLPService:
    def __init__(self):
        self.api_key = settings.GROQ_API_KEY
        self.client = Groq(api_key=self.api_key) if self.api_key and not self.api_key.startswith("gsk_demo") else None
        self.structured_evaluator = structured_evaluator
        if getattr(settings, "STRUCTURED_EVALUATION_ENABLED", True):
            logger.info("Structured evaluation enabled (Zero-Cost Local Layer)")
        else:
            logger.info("Structured evaluation disabled via configuration")

    def evaluate_single_answer(
        self,
        job_title: str,
        question: QuestionItem,
        transcript: str,
        resume_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Evaluate a single question answer via Groq LLM with optional local structured evaluation layer."""
        quality = classify_answer(transcript or "")
        if quality in ("no_speech", "non_answer"):
            feedback = (
                "No speech was detected for this answer."
                if quality == "no_speech"
                else "The question was not answered."
            )
            empty_structured = {
                "technical_correctness": 0,
                "relevance": 0,
                "completeness": 0,
                "major_misconception": False,
                "needs_followup": True,
                "structured_score": 0
            }
            return {
                "technical_score": 0,
                "relevance_score": 0,
                "depth_score": 0,
                "clarity_score": 0,
                "overall_nlp_score": 0,
                "combined_nlp_score": 0,
                "evaluation_method": "rule_based",
                "feedback": feedback,
                "strengths": [],
                "knowledge_gaps": ["Question was left unanswered."],
                "topics_detected": [],
                "structured_evaluation": empty_structured if getattr(settings, "STRUCTURED_EVALUATION_ENABLED", True) else None,
                "structured_score": 0 if getattr(settings, "STRUCTURED_EVALUATION_ENABLED", True) else None,
                "major_misconception": False,
                "needs_followup": True
            }

        # Step 1: Run primary Groq evaluation
        groq_result: Optional[Dict[str, Any]] = None
        if not self.client:
            groq_result = {
                "technical_score": None,
                "relevance_score": None,
                "depth_score": None,
                "clarity_score": None,
                "overall_nlp_score": None,
                "evaluation_status": "evaluation_failed",
                "evaluation_error": "Groq client not configured or API key missing.",
                "strengths": [],
                "knowledge_gaps": ["Groq API key not configured."],
                "topics_detected": [question.topic] if question.topic else [],
                "feedback": "NLP evaluation unavailable: Groq API key not configured."
            }
        else:
            user_prompt = f"""Job Role: {job_title}
Question: {question.question} (Topic: {question.topic})
Resume Context: {json.dumps(resume_context)}
Candidate Transcript: {transcript}"""

            groq_result = None
            last_err = None
            for attempt in range(2):
                try:
                    response = self.client.chat.completions.create(
                        model=settings.GROQ_LLM_MODEL,
                        max_tokens=1500,
                        temperature=0,
                        response_format={"type": "json_object"},
                        messages=[
                            {"role": "system", "content": SINGLE_QUESTION_NLP_PROMPT},
                            {"role": "user", "content": user_prompt}
                        ]
                    )
                    raw = response.choices[0].message.content.strip()
                    parsed = json.loads(raw)
                    if "overall_nlp_score" not in parsed:
                        parsed["overall_nlp_score"] = int((
                            parsed.get("technical_score", 80) * 0.4 +
                            parsed.get("relevance_score", 80) * 0.2 +
                            parsed.get("depth_score", 80) * 0.2 +
                            parsed.get("clarity_score", 80) * 0.2
                        ))
                    groq_result = parsed
                    break
                except Exception as e:
                    last_err = e
                    if attempt == 0:
                        logger.warning(f"[Groq API Error in evaluate_single_answer attempt 1] {type(e).__name__}: {e}. Retrying once...")
                    else:
                        error_msg = f"[Groq API Error in evaluate_single_answer attempt 2] {type(e).__name__}: {e}"
                        logging.error(error_msg, exc_info=True)
                        logger.error(error_msg, exc_info=True)

            if not groq_result:
                groq_result = {
                    "technical_score": None,
                    "relevance_score": None,
                    "depth_score": None,
                    "clarity_score": None,
                    "overall_nlp_score": None,
                    "evaluation_status": "evaluation_failed",
                    "evaluation_error": str(last_err),
                    "strengths": [],
                    "knowledge_gaps": [],
                    "topics_detected": [question.topic] if question.topic else [],
                    "feedback": f"NLP evaluation unavailable: {last_err}"
                }

        # Step 2: Run secondary local structured evaluation if enabled
        structured_res = None
        enabled = getattr(settings, "STRUCTURED_EVALUATION_ENABLED", True)
        if enabled and self.structured_evaluator:
            try:
                logger.info(f"Structured evaluation started for question: {question.question[:50]}...")
                structured_res = self.structured_evaluator.evaluate(
                    job_role=job_title,
                    question=question,
                    candidate_answer=transcript
                )
                logger.info(
                    f"Structured evaluation completed: score={structured_res.get('structured_score')}, "
                    f"misconception={structured_res.get('major_misconception')}"
                )
            except Exception as e:
                logger.error(f"Structured evaluation failed — using Groq fallback: {e}")
                structured_res = None
        elif not enabled:
            logger.info("Structured evaluation disabled — using Groq only")

        # Step 3: Combine scores without inventing numbers
        groq_score = groq_result.get("overall_nlp_score")
        struct_score = structured_res.get("structured_score") if structured_res else None

        if groq_score is not None and struct_score is not None:
            weight = getattr(settings, "STRUCTURED_EVALUATION_WEIGHT", 0.25)
            groq_weight = 1.0 - weight
            combined_score = int(round(groq_weight * groq_score + weight * struct_score))
            eval_method = "combined"
        elif groq_score is not None:
            combined_score = groq_score
            eval_method = "groq_only"
        elif struct_score is not None:
            combined_score = struct_score
            eval_method = "local_only"
        else:
            combined_score = None
            eval_method = "evaluation_failed"

        groq_result["combined_nlp_score"] = combined_score
        groq_result["evaluation_method"] = eval_method

        if structured_res:
            groq_result["structured_evaluation"] = structured_res
            groq_result["structured_score"]      = struct_score
            groq_result["major_misconception"]   = structured_res.get("major_misconception", False)
            groq_result["needs_followup"]        = structured_res.get("needs_followup", False)
            groq_result["covered_concepts"]    = structured_res.get("covered_concepts", [])
            groq_result["missing_concepts"]    = structured_res.get("missing_concepts", [])
            groq_result["partial_concepts"]    = structured_res.get("partial_concepts", [])
            groq_result["misconceptions"]      = structured_res.get("misconceptions", [])
            groq_result["reasoning_summary"]   = structured_res.get("reasoning_summary", "")
            groq_result["evidence"]            = structured_res.get("evidence", [])
        else:
            groq_result["structured_evaluation"] = None
            groq_result["structured_score"]      = None
            groq_result["major_misconception"]   = False
            groq_result["needs_followup"]        = False
            groq_result["covered_concepts"]      = []
            groq_result["missing_concepts"]      = []
            groq_result["partial_concepts"]      = []
            groq_result["misconceptions"]        = []
            groq_result["reasoning_summary"]     = ""
            groq_result["evidence"]              = []

        return groq_result

    def evaluate_interview_transcript(
        self,
        job_title: str,
        resume_data: Dict[str, Any],
        questions: List[QuestionItem],
        submissions: Dict[int, AnswerSubmission]
    ) -> Dict[str, Any]:
        """Evaluate entire interview transcript for final report generation."""
        transcript_items = []
        for q in questions:
            sub = submissions.get(q.id)
            answer_text = sub.transcript if (sub and sub.transcript) else (sub.answer_text if sub else "(No answer provided)")
            transcript_items.append({
                "question_id": q.id,
                "question": q.question,
                "topic": q.topic,
                "answer": answer_text
            })

        if not self.client:
            per_q = []
            for item in transcript_items:
                per_q.append({
                    "question_id": item["question_id"],
                    "question": item["question"],
                    "score": None,
                    "feedback": "NLP evaluation unavailable: Groq API key not configured."
                })
            return {
                "overall_score": None,
                "evaluation_status": "evaluation_failed",
                "summary": "Automated NLP evaluation unavailable: Groq API key not configured.",
                "strengths": [],
                "gaps": [],
                "recommendations": ["Configure GROQ_API_KEY in .env and retry evaluation."],
                "per_question": per_q
            }

        user_prompt = f"Job Role: {job_title}\nResume Info: {json.dumps(resume_data)}\nTranscript: {json.dumps(transcript_items)}"

        last_err = None
        for attempt in range(2):
            try:
                response = self.client.chat.completions.create(
                    model=settings.GROQ_LLM_MODEL,
                    max_tokens=3000,
                    temperature=0,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": FULL_EVALUATION_PROMPT},
                        {"role": "user", "content": user_prompt}
                    ]
                )
                raw = response.choices[0].message.content.strip()
                return json.loads(raw)
            except Exception as e:
                last_err = e
                if attempt == 0:
                    logger.warning(f"[Groq API Error in evaluate_interview_transcript attempt 1] {type(e).__name__}: {e}. Retrying once...")
                else:
                    error_msg = f"[Groq API Error in evaluate_interview_transcript attempt 2] {type(e).__name__}: {e}"
                    logging.error(error_msg, exc_info=True)
                    logger.error(error_msg, exc_info=True)

        # Fallback when Groq fails after retry: do NOT return fake scores
        per_q = []
        for item in transcript_items:
            per_q.append({
                "question_id": item["question_id"],
                "question": item["question"],
                "score": None,
                "feedback": f"NLP evaluation unavailable due to provider error: {last_err}"
            })
        return {
            "overall_score": None,
            "evaluation_status": "evaluation_failed",
            "summary": f"Automated NLP evaluation failed ({last_err}).",
            "strengths": [],
            "gaps": [],
            "recommendations": ["Re-attempt interview or verify LLM configuration."],
            "per_question": per_q
        }

nlp_service = NLPService()
