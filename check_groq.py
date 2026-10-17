from groq import Groq
from backend.app.core.config import settings

client = Groq(api_key=settings.GROQ_API_KEY)
r = client.chat.completions.create(
    model=settings.GROQ_LLM_MODEL,
    messages=[{"role": "user", "content": 'Return JSON: {"technical_score": 50, "feedback": "test"}'}],
    temperature=0,
    max_completion_tokens=300,
    response_format={"type": "json_object"},
)
print("model:", settings.GROQ_LLM_MODEL)
print("finish_reason:", r.choices[0].finish_reason)
print("content:", repr(r.choices[0].message.content))
print("usage:", r.usage)