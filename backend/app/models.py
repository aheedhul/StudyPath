from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel


class KnowledgeTier(str, Enum):
    beginner = "Beginner"
    intermediate = "Intermediate"
    advanced = "Advanced"


class ProjectStatus(str, Enum):
    not_started = "NotStarted"
    in_progress = "InProgress"
    completed = "Completed"
    on_hold = "OnHold"


class TaskType(str, Enum):
    learning = "Learning"
    testing = "Testing"


class Project(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    upload_date: datetime = Field(default_factory=datetime.utcnow)
    start_date: date = Field(default_factory=date.today)
    deadline_date: date
    duration_days: Optional[int] = None
    tier: Optional[KnowledgeTier] = Field(default=None)
    total_pages: Optional[int] = None
    task_granularity: str = Field(default="weekly")
    status: ProjectStatus = Field(default=ProjectStatus.not_started)


class Chapter(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id")
    chapter_title: str
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    estimated_reading_time: Optional[int] = None
    priority: Optional[int] = None
    complexity_score: Optional[float] = None


class Task(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id")
    week: int
    task_type: TaskType
    assigned_chapters: str
    due_date: date
    status: str = Field(default="Pending")
    completion_date: Optional[date] = None


class Assessment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id")
    initial_knowledge_tier: KnowledgeTier
    score: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class Test(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id")
    week: int
    covered_chapters: str
    questions_json: str
    user_score: Optional[float] = None
    weak_topics: Optional[str] = None
    test_date: datetime = Field(default_factory=datetime.utcnow)


class UserProgress(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    task_id: int = Field(foreign_key="task.id")
    completion_status: str
    time_spent_minutes: Optional[int] = None
    notes: Optional[str] = None
    flagged_difficult: bool = Field(default=False)
