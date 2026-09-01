import json
from typing import List, Dict, Any
from groq import Groq
from backend.app.core.config import settings
from backend.app.schemas.question import QuestionItem

class QuestionService:
    def __init__(self):
        self.api_key = settings.GROQ_API_KEY
        self.client = Groq(api_key=self.api_key) if self.api_key and not self.api_key.startswith("gsk_demo") else None

    def generate_initial_question(self, job_title: str, resume_data: Dict[str, Any]) -> QuestionItem:
        """Generate initial Question 1 based on candidate resume claims or core role fundamentals."""
        skills = resume_data.get("skills", [])
        top_skill = skills[0] if skills else "software engineering"

        if not self.client:
            return QuestionItem(
                id=1,
                question=f"Can you explain your experience with {top_skill} and a key technical challenge you solved using it?",
                topic=top_skill,
                difficulty="EASY",
                source="resume",
                strategy="WARM_UP",
                reason="Initial resume-focused warm-up question."
            )

        system_prompt = f"""You are an expert technical interviewer generating Question 1 of an adaptive interview.

Input: job role and extracted resume information.

Generate Question 1:
- Reference a SPECIFIC skill, project, or tool from the candidate's resume if available.
- If resume is minimal, ask a core fundamental question for a {job_title}.
- Keep it clear, engaging, and answerable in 1-3 minutes.

Output ONLY valid JSON matching this schema:
{{
  "question": "string",
  "topic": "string",
  "difficulty": "EASY" | "MEDIUM",
  "source": "resume" | "role"
}}"""

        user_prompt = f"Job Role: {job_title}\nResume Info: {json.dumps(resume_data)}"

        try:
            response = self.client.chat.completions.create(
                model=settings.GROQ_LLM_MODEL,
                max_tokens=1000,
                temperature=0,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            )
            raw = response.choices[0].message.content.strip()
            parsed = json.loads(raw)
            return QuestionItem(
                id=1,
                question=parsed.get("question", f"Can you describe your experience with {top_skill}?"),
                topic=parsed.get("topic", top_skill),
                difficulty=parsed.get("difficulty", "EASY"),
                source=parsed.get("source", "resume"),
                strategy="WARM_UP",
                reason="Initial adaptive interview question."
            )
        except Exception as e:
            print(f"Error generating Question 1 via Groq: {e}")
            return QuestionItem(
                id=1,
                question=f"Can you walk me through your experience working with {top_skill}?",
                topic=top_skill,
                difficulty="EASY",
                source="resume",
                strategy="WARM_UP",
                reason=f"Fallback question: {e}"
            )

question_service = QuestionService()
