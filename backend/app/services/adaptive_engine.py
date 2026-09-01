import json
from typing import Dict, Any, List
from groq import Groq
from backend.app.core.config import settings
from backend.app.schemas.question import AdaptiveEngineDecision, QuestionItem

ADAPTIVE_SYSTEM_PROMPT = """You are an adaptive technical interview engine for an AI interviewer platform.

Your task is to analyze the candidate's answer to the previous question and adaptively decide the NEXT question.

RULES FOR DIFFICULTY & TOPIC SELECTION:
1. Technical difficulty MUST depend on TECHNICAL CORRECTNESS & RELEVANCE (NLP Score) and content of the answer.
2. If the candidate gave a STRONG answer (NLP Score >= 80):
   - Increase difficulty level (EASY -> MEDIUM, MEDIUM -> HARD).
   - Ask a deeper follow-up question or explore advanced architectural concepts.
3. If the candidate gave a WEAK answer (NLP Score < 65):
   - Reduce difficulty level (HARD -> MEDIUM, MEDIUM -> EASY).
   - Target the candidate's exact knowledge gap or test fundamental principles.
4. If the candidate explicitly mentioned a technology, framework, or tool in their answer (e.g. "I used Docker and Kubernetes"):
   - Generate a contextual follow-up specifically probing that mentioned technology!
5. Do NOT adjust technical difficulty based on candidate speaking speed or head movement.

Output ONLY valid JSON matching this schema:
{
  "next_difficulty": "EASY" | "MEDIUM" | "HARD",
  "question_strategy": "FOLLOW_UP" | "NEW_TOPIC" | "REMEDIAL",
  "target_topic": "string",
  "reason": "1 sentence explanation of why this question was selected",
  "next_question": "string containing the full question text"
}"""

class AdaptiveEngine:
    def __init__(self):
        self.api_key = settings.GROQ_API_KEY
        self.client = Groq(api_key=self.api_key) if self.api_key and not self.api_key.startswith("gsk_demo") else None

    def decide_next_question(
        self,
        session_id: str,
        role: str,
        resume_context: Dict[str, Any],
        current_question: Dict[str, Any],
        transcript: str,
        nlp_score: int,
        speech_score: int,
        video_score: int,
        technical_strengths: List[str],
        knowledge_gaps: List[str],
        mentioned_topics: List[str],
        difficulty_level: str,
        question_number: int
    ) -> AdaptiveEngineDecision:
        """Evaluate previous performance and adaptively generate the next question."""
        
        # Rule-based difficulty progression logic
        if nlp_score >= 80:
            if difficulty_level == "EASY":
                target_difficulty = "MEDIUM"
            elif difficulty_level == "MEDIUM":
                target_difficulty = "HARD"
            else:
                target_difficulty = "HARD"
            default_strategy = "FOLLOW_UP"
        elif nlp_score < 65:
            if difficulty_level == "HARD":
                target_difficulty = "MEDIUM"
            else:
                target_difficulty = "EASY"
            default_strategy = "REMEDIAL"
        else:
            target_difficulty = difficulty_level
            default_strategy = "NEW_TOPIC"

        if not self.client:
            # Fallback static adaptive generation if Groq client not active
            if knowledge_gaps and nlp_score < 65:
                gap = knowledge_gaps[0]
                reason = f"Candidate demonstrated a knowledge gap in {gap}."
                next_q = f"Could you walk me through the core fundamentals of {gap} and how you would apply it in a {role} role?"
                strategy = "REMEDIAL"
                topic = gap
            elif mentioned_topics:
                top = mentioned_topics[0]
                reason = f"Candidate mentioned experience with {top}."
                next_q = f"You mentioned working with {top}. Can you explain how you configured and optimized it in your project?"
                strategy = "FOLLOW_UP"
                topic = top
            else:
                reason = f"Candidate showed {target_difficulty.lower()} mastery level in previous technical question."
                next_q = f"In system design for a {role}, how do you handle asynchronous task processing and message queues?"
                strategy = default_strategy
                topic = "System Architecture"

            return AdaptiveEngineDecision(
                next_difficulty=target_difficulty,
                question_strategy=strategy,
                target_topic=topic,
                reason=reason,
                next_question=next_q
            )

        payload = {
            "session_id": session_id,
            "role": role,
            "resume_context": resume_context,
            "current_question": current_question,
            "transcript": transcript,
            "nlp_score": nlp_score,
            "speech_score": speech_score,
            "video_score": video_score,
            "technical_strengths": technical_strengths,
            "knowledge_gaps": knowledge_gaps,
            "mentioned_topics": mentioned_topics,
            "current_difficulty": difficulty_level,
            "recommended_next_difficulty": target_difficulty,
            "question_number": question_number
        }

        user_prompt = f"Adaptive Interview State:\n{json.dumps(payload, indent=2)}"

        try:
            response = self.client.chat.completions.create(
                model=settings.GROQ_LLM_MODEL,
                max_tokens=1500,
                temperature=0,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": ADAPTIVE_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ]
            )
            raw = response.choices[0].message.content.strip()
            parsed = json.loads(raw)
            return AdaptiveEngineDecision(
                next_difficulty=parsed.get("next_difficulty", target_difficulty),
                question_strategy=parsed.get("question_strategy", default_strategy),
                target_topic=parsed.get("target_topic", "Technical"),
                reason=parsed.get("reason", "Adaptive LLM decision based on candidate performance."),
                next_question=parsed.get("next_question", f"Can you elaborate further on {role} technical concepts?")
            )
        except Exception as e:
            print(f"Adaptive engine Groq error: {e}")
            return AdaptiveEngineDecision(
                next_difficulty=target_difficulty,
                question_strategy=default_strategy,
                target_topic="Software Engineering",
                reason=f"Fallback adaptive decision due to API timeout: {e}",
                next_question=f"For a {role} position, how do you approach debugging production incidents?"
            )

adaptive_engine = AdaptiveEngine()
