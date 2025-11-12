from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Iterable

from .config import settings
from .llm import generate_questions
from .models import KnowledgeTier


@dataclass
class AssessmentQuestion:
    question: str
    choices: list[str] | None
    answer: str
    chapter_reference: str | None = None


def _fallback_questions(chapter_titles: list[str]) -> list[AssessmentQuestion]:
    templates = [
        "Summarize the primary theme presented in {chapter}.",
        "Which key event is highlighted in {chapter}?",
        "Identify one critical figure discussed in {chapter} and their role.",
        "Explain why the concepts in {chapter} are foundational for the rest of the book.",
        "List one cause and effect pair described in {chapter}.",
    ]
    random.shuffle(templates)

    questions: list[AssessmentQuestion] = []
    for idx, chapter in enumerate(chapter_titles[: settings.assessment_question_count]):
        template = templates[idx % len(templates)]
        question_text = template.format(chapter=chapter)
        questions.append(
            AssessmentQuestion(
                question=question_text,
                choices=None,
                answer="freeform",
                chapter_reference=chapter,
            )
        )
    return questions


async def generate_baseline_assessment(
    chapters: Iterable[dict],
) -> list[AssessmentQuestion]:
    chapter_titles = [chapter["title"] for chapter in chapters if chapter.get("title")]
    fallback = _fallback_questions(chapter_titles)

    prompt = (
        "Generate {count} baseline multiple-choice or short-answer questions using the first {window} "
        "chapters: {chapters}. Each question should probe core concepts and include the chapter reference."
    ).format(
        count=settings.assessment_question_count,
        window=settings.assessment_question_chapter_window,
        chapters=", ".join(chapter_titles[: settings.assessment_question_chapter_window]),
    )

    raw = await generate_questions(prompt, fallback=[question.__dict__ for question in fallback])

    if not raw:
        return fallback

    questions: list[AssessmentQuestion] = []
    for item in raw:
        question = item.get("question") or item.get("prompt")
        answer = item.get("answer") or "freeform"
        choices = item.get("choices")
        chapter_reference = item.get("chapter_reference")
        if not question:
            continue
        questions.append(
            AssessmentQuestion(
                question=question,
                choices=choices,
                answer=answer,
                chapter_reference=chapter_reference,
            )
        )

    return questions or fallback


def grade_assessment(answers: list[str], ground_truth: list[AssessmentQuestion]) -> tuple[float, KnowledgeTier]:
    if not answers or not ground_truth:
        return 0.0, KnowledgeTier.beginner

    total = min(len(answers), len(ground_truth))
    correct = 0
    for response, question in zip(answers, ground_truth):
        expected = question.answer
        if expected.lower() == "freeform":
            # Freeform answers default to neutral credit
            correct += 0.5
            continue

        if response.strip().lower() == expected.strip().lower():
            correct += 1

    score = (correct / total) * 100

    if score <= 40:
        tier = KnowledgeTier.beginner
    elif score <= 70:
        tier = KnowledgeTier.intermediate
    else:
        tier = KnowledgeTier.advanced

    return score, tier
