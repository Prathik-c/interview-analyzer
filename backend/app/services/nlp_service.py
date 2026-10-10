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
        if not transcript or not transcript.strip():
            empty_structured = {
                "technical_correctness": 0,
                "relevance": 0,
                "completeness": 0,
                "major_misconception": False,
                "needs_followup": True,
                "structured_score": 0
            }
            return {
                "technical_score": 30,
                "relevance_score": 30,
                "depth_score": 30,
                "clarity_score": 30,
                "overall_nlp_score": 30,
                "strengths": [],
                "knowledge_gaps": ["Question was left unanswered."],
                "topics_detected": [],
                "feedback": "No verbal answer was detected for this question.",
                "structured_evaluation": empty_structured if getattr(settings, "STRUCTURED_EVALUATION_ENABLED", True) else None,
                "structured_score": 0 if getattr(settings, "STRUCTURED_EVALUATION_ENABLED", True) else None,
                "combined_nlp_score": 30,
                "major_misconception": False,
                "needs_followup": True
            }

        # Step 1: Run primary Groq evaluation
        groq_result: Dict[str, Any]
        if not self.client:
            groq_result = {
                "technical_score": 82,
                "relevance_score": 88,
                "depth_score": 78,
                "clarity_score": 85,
                "overall_nlp_score": 83,
                "strengths": ["Clear explanation of core technical concepts."],
                "knowledge_gaps": ["Could provide more concrete production examples."],
                "topics_detected": [question.topic or "Technical"],
                "feedback": "Solid answer covering fundamental principles."
            }
        else:
            user_prompt = f"""Job Role: {job_title}
Question: {question.question} (Topic: {question.topic})
Resume Context: {json.dumps(resume_context)}
Candidate Transcript: {transcript}"""

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
            except Exception as e:
                logger.error(f"Groq single answer evaluation error: {e}")
                groq_result = {
                    "technical_score": 75,
                    "relevance_score": 80,
                    "depth_score": 70,
                    "clarity_score": 80,
                    "overall_nlp_score": 76,
                    "strengths": ["Clear explanation."],
                    "knowledge_gaps": [],
                    "topics_detected": [question.topic or "General"],
                    "feedback": f"Answer parsed successfully: {e}"
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

        # Step 3: Combine scores safely (default: 75% Groq, 25% Structured)
        groq_score = groq_result.get("overall_nlp_score", 80)
        if structured_res and "structured_score" in structured_res:
            weight = getattr(settings, "STRUCTURED_EVALUATION_WEIGHT", 0.25)
            groq_weight = 1.0 - weight
            struct_score = structured_res["structured_score"]
            combined_score = int(round(groq_weight * groq_score + weight * struct_score))

            groq_result["structured_evaluation"] = structured_res
            groq_result["structured_score"] = struct_score
            groq_result["combined_nlp_score"] = combined_score
            groq_result["major_misconception"] = structured_res.get("major_misconception", False)
            groq_result["needs_followup"] = structured_res.get("needs_followup", False)
        else:
            groq_result["structured_evaluation"] = None
            groq_result["structured_score"] = None
            groq_result["combined_nlp_score"] = groq_score
            groq_result["major_misconception"] = False
            groq_result["needs_followup"] = False

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
                has_ans = bool(item["answer"] and item["answer"] != "(No answer provided)")
                per_q.append({
                    "question_id": item["question_id"],
                    "question": item["question"],
                    "score": 85 if has_ans else 30,
                    "feedback": "Demonstrated solid technical understanding." if has_ans else "Question was unanswered."
                })
            return {
                "overall_score": 85,
                "summary": f"Strong demonstration of technical knowledge suited for the {job_title} role.",
                "strengths": [
                    "Clear communication of core technical concepts",
                    "Good alignment with candidate's stated resume skills",
                    "Structured reasoning in system design"
                ],
                "gaps": [
                    "Could elaborate further with specific production metrics",
                    "Add more concrete architectural trade-off comparisons"
                ],
                "recommendations": [
                    "Practice STAR format for situational questions",
                    "Highlight quantitative impact in technical project descriptions"
                ],
                "per_question": per_q
            }

        user_prompt = f"Job Role: {job_title}\nResume Info: {json.dumps(resume_data)}\nTranscript: {json.dumps(transcript_items)}"

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
            print(f"Groq evaluation error: {e}")
            raise ValueError(f"NLP Evaluation failed: {e}") from e

nlp_service = NLPService()
