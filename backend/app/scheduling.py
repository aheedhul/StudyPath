from __future__ import annotations

import math
from collections import deque
from datetime import date, timedelta
from typing import Iterable, List

from .config import settings
from .models import KnowledgeTier, TaskType

PACE_BY_TIER = {
    KnowledgeTier.beginner: {"pages_per_day": 12, "minutes_per_page": 6},
    KnowledgeTier.intermediate: {"pages_per_day": 20, "minutes_per_page": 5},
    KnowledgeTier.advanced: {"pages_per_day": 28, "minutes_per_page": 4},
}


class FeasibilityResult:
    def __init__(self, feasible: bool, alerts: list[str]) -> None:
        self.feasible = feasible
        self.alerts = alerts


def evaluate_feasibility(
    total_pages: int,
    tier: KnowledgeTier,
    duration_days: int,
) -> FeasibilityResult:
    if duration_days <= 0:
        return FeasibilityResult(False, ["Timeline duration must be positive."])

    pace = PACE_BY_TIER.get(tier, PACE_BY_TIER[KnowledgeTier.beginner])
    required_pages_per_day = total_pages / duration_days
    capacity = pace["pages_per_day"]

    alerts: list[str] = []
    feasible = True
    if required_pages_per_day > capacity:
        alerts.append(
            (
                "⚠️ Feasibility Alert: Timeline requires ~{req:.1f} pages/day, but the recommended pace "
                "for {tier} is {cap} pages/day. Consider extending the deadline or reducing scope."
            ).format(req=required_pages_per_day, tier=tier.value, cap=capacity)
        )
        feasible = False

    return FeasibilityResult(feasible, alerts)


def build_schedule(
    *,
    chapters: Iterable[dict],
    start_date: date,
    deadline_date: date,
    tier: KnowledgeTier,
    task_granularity: str,
) -> dict:
    chapters = list(chapters)
    total_pages = sum(chapter.get("page_end", 0) - chapter.get("page_start", 0) + 1 for chapter in chapters)
    duration_days = (deadline_date - start_date).days + 1
    total_weeks = max(1, math.ceil(duration_days / 7))

    learning_weeks_target = max(1, math.ceil(total_weeks * settings.learning_phase_ratio))
    testing_weeks = max(0, total_weeks - learning_weeks_target)

    pace = PACE_BY_TIER.get(tier, PACE_BY_TIER[KnowledgeTier.beginner])
    minutes_per_page = pace["minutes_per_page"]

    chapter_queue = deque(chapters)
    learning_tasks: list[dict] = []
    remaining_pages = total_pages

    for week in range(1, learning_weeks_target + 1):
        if not chapter_queue:
            break

        weekly_chapters: list[dict] = []
        per_week_capacity = pace["pages_per_day"] * 7
        remaining_weeks = learning_weeks_target - week + 1
        average_pages_needed = max(1, math.ceil(remaining_pages / remaining_weeks))
        weekly_page_budget = min(per_week_capacity, average_pages_needed)
        pages_assigned = 0

        while chapter_queue and pages_assigned < weekly_page_budget:
            chapter = chapter_queue[0]
            chapter_pages = chapter.get("page_end", 0) - chapter.get("page_start", 0) + 1
            if pages_assigned + chapter_pages <= weekly_page_budget:
                chapter_queue.popleft()
                chapter = dict(chapter)
                chapter["estimated_minutes"] = chapter_pages * minutes_per_page
                weekly_chapters.append(chapter)
                pages_assigned += chapter_pages
            else:
                break

        if not weekly_chapters and chapter_queue:
            chapter = chapter_queue.popleft()
            chapter_pages = chapter.get("page_end", 0) - chapter.get("page_start", 0) + 1
            chapter = dict(chapter)
            chapter["estimated_minutes"] = chapter_pages * minutes_per_page
            weekly_chapters.append(chapter)
            pages_assigned += chapter_pages

        due_date = min(deadline_date, start_date + timedelta(weeks=week - 1, days=6))
        learning_tasks.append(
            {
                "week": week,
                "task_type": TaskType.learning,
                "assigned_chapters": [chapter["title"] for chapter in weekly_chapters],
                "chapter_payload": weekly_chapters,
                "due_date": due_date,
                "status": "Pending",
            }
        )
        remaining_pages = max(0, remaining_pages - pages_assigned)

    learning_weeks = len(learning_tasks)
    if learning_weeks == 0:
        learning_weeks = 1

    testing_weeks = max(0, total_weeks - learning_weeks)
    testing_tasks: list[dict] = []
    learned_chapter_titles: list[str] = []
    for task in learning_tasks:
        learned_chapter_titles.extend(task["assigned_chapters"])

    for offset in range(testing_weeks):
        week_number = learning_weeks + offset + 1
        window = learned_chapter_titles[: min(len(learned_chapter_titles), learning_weeks + offset * 2)] or learned_chapter_titles
        due_date = min(deadline_date, start_date + timedelta(weeks=week_number - 1, days=6))
        testing_tasks.append(
            {
                "week": week_number,
                "task_type": TaskType.testing,
                "assigned_chapters": window,
                "chapter_payload": [],
                "due_date": due_date,
                "status": "Pending",
            }
        )

    all_tasks = learning_tasks + testing_tasks
    alerts = evaluate_feasibility(total_pages, tier, duration_days).alerts

    return {
        "total_pages": total_pages,
        "duration_days": duration_days,
        "learning_weeks": learning_weeks,
        "testing_weeks": testing_weeks,
        "total_weeks": learning_weeks + testing_weeks,
        "tasks": all_tasks,
        "alerts": alerts,
        "granularity": task_granularity,
    }
