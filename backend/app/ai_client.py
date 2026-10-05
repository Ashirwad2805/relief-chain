import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

MODEL = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free")


def _fallback_reply(prompt: str) -> str:
    cleaned_prompt = (prompt or "").strip()
    if not cleaned_prompt:
        return "Please send a question about relief operations, logistics, or resource planning."

    lowered = cleaned_prompt.lower()
    if any(keyword in lowered for keyword in [
        "hospital",
        "camp",
        "water",
        "food",
        "supply",
        "route",
        "logistics",
        "medicine",
        "resource",
        "evac",
    ]):
        return (
            "I’m running in offline mode right now because the AI provider is not configured. "
            "Please check OPENROUTER_API_KEY or use the dashboard tools to review camp capacity, "
            "resource flow, and logistics priority decisions."
        )

    return (
        "I’m currently in offline fallback mode because no OpenRouter API key is configured. "
        "You can still review relief planning, camp capacity, resource routing, and logistics priorities "
        "while the backend environment is updated with OPENROUTER_API_KEY."
    )


def ask_ai(prompt: str) -> str:
    cleaned_prompt = (prompt or "").strip()
    if not cleaned_prompt:
        return _fallback_reply(cleaned_prompt)

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return _fallback_reply(cleaned_prompt)

    try:
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
        )
        res = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": cleaned_prompt}],
        )
        content = res.choices[0].message.content
        return content.strip() if content else _fallback_reply(cleaned_prompt)
    except Exception:
        return _fallback_reply(cleaned_prompt)