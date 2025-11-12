from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from .config import settings

logger = logging.getLogger(__name__)


async def generate_questions(prompt: str, *, fallback: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Generate assessment questions using Groq's chat completions API.

    If the API key is missing or the request fails, return the provided fallback payload.
    """
    api_key = settings.groq_api_key
    if not api_key:
        logger.warning("Groq API key missing; returning fallback questions.")
        return fallback

    mc_count = min(3, settings.assessment_question_count)
    short_count = max(0, settings.assessment_question_count - mc_count)
    system_parts = [
        "You are an assistant that generates textbook-aligned baseline assessment questions.",
        (
            "Always reply with valid JSON matching this schema: "
            "{\"questions\": [{\"question\": str, \"choices\": list[str]|null, \"answer\": str|null, \"chapter_reference\": str|null}]}."
        ),
        f"Return exactly {settings.assessment_question_count} questions.",
        (
            f"Questions 1-{mc_count} must include a 'choices' array with exactly 4 unique options "
            "and set 'answer' to one of those options."
        ),
    ]
    if short_count > 0:
        system_parts.append(
            f"Questions {mc_count + 1}-{mc_count + short_count} must set 'choices' to null and set 'answer' to 'freeform'."
        )
    system_parts.append(
        "Use only the chapter titles provided in the user's prompt for chapter_reference, and avoid any additional commentary."
    )
    system_content = " ".join(system_parts)

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    payload = {
        "model": settings.groq_model,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": system_content},
            {"role": "user", "content": prompt},
        ],
    }

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
        except httpx.HTTPError as exc:  # pragma: no cover - network path
            response_text = exc.response.text if exc.response is not None else "<no-body>"
            logger.error("Groq request failed: %s | body=%s", exc, response_text)
            return fallback

    data = response.json()
    try:
        text = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        logger.error("Unexpected Groq response structure: %s", data)
        return fallback

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        logger.error("Failed to decode Groq JSON: %s | payload=%s", exc, text)
        return fallback

    questions_payload = parsed.get("questions")
    if not isinstance(questions_payload, list):
        logger.error("Groq JSON missing 'questions' list: %s", parsed)
        return fallback

    normalized: list[dict[str, Any]] = []
    for item in questions_payload:
        if not isinstance(item, dict):
            continue
        question = item.get("question")
        if not question:
            continue
        choices_raw = item.get("choices")
        choices: list[str] | None
        if isinstance(choices_raw, list):
            cleaned = [str(choice).strip() for choice in choices_raw if str(choice).strip()]
            choices = cleaned if cleaned else None
        elif isinstance(choices_raw, str):
            stripped = choices_raw.strip()
            choices = [stripped] if stripped else None
        else:
            choices = None

        answer_raw = item.get("answer")
        answer = str(answer_raw).strip() if isinstance(answer_raw, str) else None
        chapter_ref_raw = item.get("chapter_reference")
        chapter_reference = str(chapter_ref_raw).strip() if isinstance(chapter_ref_raw, str) else None

        normalized.append(
            {
                "question": str(question),
                "choices": choices,
                "answer": answer,
                "chapter_reference": chapter_reference,
            }
        )

    if not normalized:
        logger.warning("Groq JSON contained no usable questions; falling back")
        return fallback

    logger.info("Groq response parsed into %d questions.", len(normalized))
    return normalized
