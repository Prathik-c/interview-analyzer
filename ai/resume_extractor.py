"""
Step 1: Resume parsing.
- extract_text_from_pdf(): pulls raw text out of a resume PDF
- structure_resume(): sends raw text to Groq (Llama), gets back clean structured JSON
"""

import json
import os

import pdfplumber
from groq import Groq

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

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
        model="llama-3.3-70b-versatile",
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