from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from .models import KnowledgeTier, ProjectStatus, TaskType


class ChapterChunk(BaseModel):
    title: str
    level: int
    page_start: int
    page_end: int
    estimated_minutes: int


class ProjectRead(BaseModel):
    id: int
    name: str
    start_date: date
    deadline_date: date
    duration_days: Optional[int]
    tier: Optional[KnowledgeTier]
    total_pages: Optional[int]
    task_granularity: str
    status: ProjectStatus

    model_config = ConfigDict(from_attributes=True)


class AssessmentCreate(BaseModel):
    responses: List[str] = Field(..., min_length=1)


class AssessmentRead(BaseModel):
    id: int
    project_id: int
    initial_knowledge_tier: KnowledgeTier
    score: float
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)


class ScheduleTask(BaseModel):
    week: int
    task_type: TaskType
    assigned_chapters: List[str]
    due_date: date
    status: str


class ScheduleSummary(BaseModel):
    project: ProjectRead
    learning_phase_weeks: int
    testing_phase_weeks: int
    total_weeks: int
    feasibility_alerts: List[str]
    tasks: List[ScheduleTask]


class KnowledgeQuestion(BaseModel):
    question: str
    choices: Optional[List[str]] = None
    answer: Optional[str] = None
    chapter_reference: Optional[str] = None


class AssessmentQuiz(BaseModel):
    project_id: int
    questions: List[KnowledgeQuestion]


class UploadResponse(BaseModel):
    project: ProjectRead
    chapter_chunks: List[ChapterChunk]
    quiz: AssessmentQuiz
    feasibility_notes: List[str]


class ProgressUpdate(BaseModel):
    status: str
    completion_date: Optional[date] = None
    time_spent_minutes: Optional[int] = None
    notes: Optional[str] = None
    flagged_difficult: Optional[bool] = False


class TestSummary(BaseModel):
    week: int
    questions: List[KnowledgeQuestion]
    recommended_review: List[str]


class WeeklyPlan(BaseModel):
    schedule: ScheduleSummary
    upcoming_test: Optional[TestSummary] = None
