"""
ai/resume_extractor.py
Step 1: Resume parsing.
- extract_text_from_pdf(): pulls raw text out of a resume PDF
- structure_resume(): sends raw text to Groq (Llama), gets back clean structured JSON
Reads GROQ_API_KEY from a .env file at the project root (project/.env).
"""

import json
import os

import pdfplumber
from dotenv import load_dotenv
from groq import Groq

load_dotenv()  # looks for .env in the current working directory (project root)

api_key = os.environ.get("GROQ_API_KEY")
if not api_key:
    raise RuntimeError(
        "GROQ_API_KEY not found. Make sure a .env file exists at your project root "
        "with the line: GROQ_API_KEY=your_key_here"
    )

client = Groq(api_key=api_key)

STRUCTURE_PROMPT = """You are a resume parser. Given raw resume text, extract structured
information and return ONLY valid JSON (no markdown fences, no preamble, no commentary).

Return this exact shape:
{
  "name": string or null,
  "email": string or null,
  "phone": string or null,
  "skills": [string],
  "experience": [
    {
      "title": string,
      "company": string,
      "duration": string,
      "description": string
    }
  ],
  "projects": [
    {
      "name": string,
      "description": string,
      "tech_stack": [string]
    }
  ],
  "education": [
    {
      "degree": string,
      "institution": string,
      "duration": string
    }
  ],
  "total_years_experience": number
}

If a field can't be found, use null or an empty list/array as appropriate. Do not invent
information that isn't in the text.

Resume text:
---
{resume_text}
---
"""


def extract_text_from_pdf(file_path: str) -> str:
    """Extract all text from a PDF resume."""
    text_parts = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
    text = "\n".join(text_parts).strip()
    if not text:
        raise ValueError(
            "No extractable text found in PDF — it may be a scanned image. "
            "OCR support isn't handled here yet."
        )
    return text


def structure_resume(resume_text: str) -> dict:
    """Send raw resume text to Groq and get back structured JSON."""
    prompt = STRUCTURE_PROMPT.replace("{resume_text}", resume_text)

    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        max_tokens=2000,
        temperature=0,
        response_format={"type": "json_object"},  # Groq enforces valid JSON output
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.choices[0].message.content.strip()

    # Defensive strip in case fences slip through anyway
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Groq didn't return valid JSON: {e}\nRaw response: {raw}")


def parse_resume(file_path: str) -> dict:
    """Full pipeline: PDF -> raw text -> structured JSON."""
    text = extract_text_from_pdf(file_path)
    structured = structure_resume(text)
    structured["_raw_text_length"] = len(text)  # useful for debugging extraction quality
    return structured




def generate_initial_questions(job_title: str, resume_data: dict, n_questions: int = 5) -> list[dict]:
    system_prompt = f"""You are an interviewer generating initial interview questions.

Input: a job role and extracted resume information (skills, projects, experience).

Generate exactly {n_questions} questions (3-8) following this mix:
- 40-60% should reference SPECIFIC things in the resume (named projects, tools, claims) — ask them to explain, justify a decision, or go deeper on something they wrote
- 40-60% should test ROLE FUNDAMENTALS not covered by the resume — core concepts someone in this role should know

Rules:
- Do not ask generic/no-context questions like "tell me about yourself"
- Do not ask about tools/skills NOT mentioned in the resume unless it's a core requirement for the role
- Each question must be answerable in a few sentences, not an essay
- Vary difficulty: mix at least one easy warm-up, some medium, one harder

Output ONLY valid JSON matching this schema, no preamble, no markdown fences:
{{
  "questions": [
        {{"id": int, "question": "string", "topic": "string", "source": "resume" | "role"}}
  ]
}}"""

    user_prompt = f"""Job Role: {job_title}
Resume Info: {json.dumps(resume_data)}
Number of questions: {n_questions}"""

    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        max_tokens=2000,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    )

    raw = response.choices[0].message.content.strip()

    try:
        parsed = json.loads(raw)
        return parsed["questions"]
    except (json.JSONDecodeError, KeyError):
        # retry once, or raise — don't silently fail
        raise ValueError(f"Model returned malformed JSON: {raw}")


def generate_evaluation(job_title: str, resume_data: dict, questions: list, answers: list) -> dict:
    """Evaluate the completed interview transcript with Groq."""
    answer_map = {answer["question_id"]: answer["answer"] for answer in answers}
    transcript = [
        {
            "question": question["question"],
            "topic": question.get("topic", ""),
            "answer": answer_map.get(question["id"], "(no answer given)")
        }
        for question in questions
    ]

    system_prompt = """You are an interview evaluator.

Evaluate each answer for correctness, technical accuracy, depth, reasoning, and relevance.
Then give an overall assessment.

Output ONLY valid JSON, no preamble, no markdown fences, matching this schema:
{
  "overall_score": <int 0-10>,
  "summary": "<2-3 sentence overall assessment>",
  "strengths": ["...", "..."],
  "gaps": ["...", "..."],
  "per_question": [
    {"question": "...", "score": <int 0-10>, "feedback": "<1-2 sentences>"}
  ]
}"""
    user_prompt = f"""Job Role: {job_title}
Resume Info: {json.dumps(resume_data)}
Transcript: {json.dumps(transcript)}"""

    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        max_tokens=3000,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    )
    raw = response.choices[0].message.content.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as error:
        raise ValueError(f"Model returned malformed evaluation JSON: {error}") from error