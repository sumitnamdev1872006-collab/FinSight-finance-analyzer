"""
FinSight — ai_service.py
Optional AI-powered summary using an LLM API.

The AI receives only a short text summary of the analysis results.
It returns a plain-language explanation with general observations.

IMPORTANT: This feature provides educational observations only.
It does NOT provide financial advice, investment recommendations,
or guaranteed outcomes of any kind.

If the API key is not set, the function returns None gracefully
and the app continues working with Python-generated insights.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")


def get_ai_summary(analysis_text: str) -> str | None:
    """
    Send a short summary of the user's finances to an LLM.
    Returns the AI's plain-language response, or None if unavailable.
    """
    if not OPENAI_API_KEY:
        return None

    try:
        import httpx

        prompt = (
            "The following is a summary of a user's personal finance data for a student project.\n\n"
            f"{analysis_text}\n\n"
            "Give a short, simple explanation (3-4 sentences) of this person's spending pattern "
            "and 2 general suggestions for managing expenses better. "
            "Do NOT recommend any specific investment, stock, or financial product. "
            "Keep the language simple and suitable for a student."
        )

        response = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 300,
                "temperature": 0.5,
            },
            timeout=15,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()

    except Exception as e:
        # AI failure must never crash the app
        return None
