from __future__ import annotations

from datetime import date, datetime
from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from ..assessment import AssessmentQuestion, generate_baseline_assessment, grade_assessment
from ..database import get_session
from ..models import (
    Assessment,
    Chapter,
    KnowledgeTier,
    Project,
    ProjectStatus,
    Task,
    TaskType,
    Test,
)
from ..pdf_processing import persist_upload, summarize_pdf
from ..scheduling import PACE_BY_TIER, build_schedule, evaluate_feasibility
from ..schemas import (
    AssessmentCreate,
    AssessmentQuiz,
    ChapterChunk,
    ProjectRead,
    ScheduleSummary,
    ScheduleTask,
    UploadResponse,
)
from ..storage import load_payload, save_payload

router = APIRouter(prefix="/projects", tags=["projects"])


def _parse_date(raw: str, field_name: str) -> date:
    try:
        return datetime.fromisoformat(raw).date()
    except ValueError as exc:  # pragma: no cover - input validation path
        raise HTTPException(status_code=400, detail=f"Invalid date for {field_name}.") from exc


async def _serialize_project(project: Project) -> ProjectRead:
    return ProjectRead.model_validate(project)


@router.post("", response_model=UploadResponse)
async def create_project(
    *,
    name: str = Form(...),
    deadline_date: str = Form(...),
    task_granularity: str = Form("weekly"),
    duration_days: int | None = Form(None),
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
) -> UploadResponse:
    start_date = date.today()
    deadline = _parse_date(deadline_date, "deadline_date")
    if deadline <= start_date:
        raise HTTPException(status_code=400, detail="Deadline must be in the future.")

    computed_duration = duration_days or (deadline - start_date).days + 1

    project = Project(
        name=name,
        start_date=start_date,
        deadline_date=deadline,
        duration_days=computed_duration,
        task_granularity=task_granularity,
    )
    session.add(project)
    await session.commit()
    await session.refresh(project)

    project_dir = save_payload(project.id, "meta", {"name": name, "created_at": datetime.utcnow().isoformat()}).parent
    pdf_path = project_dir / "source.pdf"
    await persist_upload(file, pdf_path)

    summary = summarize_pdf(pdf_path)
    project.total_pages = summary["total_pages"]

    await session.execute(delete(Chapter).where(Chapter.project_id == project.id))

    for chapter in summary["chapters"]:
        chapter_model = Chapter(
            project_id=project.id,
            chapter_title=chapter.get("title", ""),
            page_start=chapter.get("page_start"),
            page_end=chapter.get("page_end"),
        )
        session.add(chapter_model)

    await session.commit()
    await session.refresh(project)

    default_tier = KnowledgeTier.intermediate
    pace = PACE_BY_TIER[default_tier]
    chapter_chunks: List[ChapterChunk] = []
    for chapter in summary["chapters"]:
        page_count = chapter.get("page_end", 0) - chapter.get("page_start", 0) + 1
        estimated_minutes = page_count * pace["minutes_per_page"]
        chunk = ChapterChunk(
            title=chapter.get("title", ""),
            level=chapter.get("level", 1),
            page_start=chapter.get("page_start", 1),
            page_end=chapter.get("page_end", 1),
            estimated_minutes=estimated_minutes,
        )
        chapter_chunks.append(chunk)

    quiz_questions: List[AssessmentQuestion] = await generate_baseline_assessment(summary["chapters"])
    quiz_payload = [question.__dict__ for question in quiz_questions]
    save_payload(project.id, "baseline_assessment", quiz_payload)

    feasibility = evaluate_feasibility(
        total_pages=project.total_pages or 0,
        tier=default_tier,
        duration_days=project.duration_days or (project.deadline_date - project.start_date).days + 1,
    )

    upload_response = UploadResponse(
        project=await _serialize_project(project),
        chapter_chunks=chapter_chunks,
        quiz=AssessmentQuiz(project_id=project.id, questions=[
            {
                "question": q.question,
                "choices": q.choices,
                "answer": None,
                "chapter_reference": q.chapter_reference,
            }
            for q in quiz_questions
        ]),
        feasibility_notes=feasibility.alerts,
    )
    return upload_response


@router.post("/{project_id}/assessment", response_model=ScheduleSummary)
async def submit_assessment(
    project_id: int,
    payload: AssessmentCreate,
    session: AsyncSession = Depends(get_session),
) -> ScheduleSummary:
    project_result = await session.execute(select(Project).where(Project.id == project_id))
    project = project_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    stored_quiz = load_payload(project_id, "baseline_assessment")
    if not stored_quiz:
        raise HTTPException(status_code=400, detail="Baseline assessment not initialized.")

    questions = [AssessmentQuestion(**item) for item in stored_quiz]
    score, tier = grade_assessment(payload.responses, questions)

    assessment = Assessment(
        project_id=project_id,
        initial_knowledge_tier=tier,
        score=score,
    )
    project.tier = tier
    project.status = ProjectStatus.in_progress
    session.add(assessment)
    session.add(project)
    await session.commit()

    chapters_result = await session.execute(select(Chapter).where(Chapter.project_id == project_id))
    chapters = [chapter for chapter in chapters_result.scalars()]

    schedule = build_schedule(
        chapters=[
            {
                "title": chapter.chapter_title,
                "page_start": chapter.page_start or 1,
                "page_end": chapter.page_end or 1,
            }
            for chapter in chapters
        ],
        start_date=project.start_date,
        deadline_date=project.deadline_date,
        tier=tier,
        task_granularity=project.task_granularity,
    )

    await session.execute(delete(Task).where(Task.project_id == project_id))
    await session.execute(delete(Test).where(Test.project_id == project_id))

    task_models: list[Task] = []
    test_models: list[Test] = []

    for task in schedule["tasks"]:
        task_model = Task(
            project_id=project_id,
            week=task["week"],
            task_type=task["task_type"],
            assigned_chapters=", ".join(task["assigned_chapters"]),
            due_date=task["due_date"],
            status=task["status"],
        )
        task_models.append(task_model)
        if task["task_type"] == TaskType.testing:
            test_model = Test(
                project_id=project_id,
                week=task["week"],
                covered_chapters=", ".join(task["assigned_chapters"]),
                questions_json="[]",
            )
            test_models.append(test_model)

    session.add_all(task_models + test_models)
    await session.commit()

    schedule_summary = ScheduleSummary(
        project=await _serialize_project(project),
        learning_phase_weeks=schedule["learning_weeks"],
        testing_phase_weeks=schedule["testing_weeks"],
        total_weeks=schedule["total_weeks"],
        feasibility_alerts=schedule["alerts"],
        tasks=[
            ScheduleTask(
                week=task["week"],
                task_type=task["task_type"],
                assigned_chapters=task["assigned_chapters"],
                due_date=task["due_date"],
                status=task["status"],
            )
            for task in schedule["tasks"]
        ],
    )
    return schedule_summary


@router.get("/{project_id}", response_model=ProjectRead)
async def get_project(project_id: int, session: AsyncSession = Depends(get_session)) -> ProjectRead:
    result = await session.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")
    return await _serialize_project(project)


@router.get("/{project_id}/schedule", response_model=ScheduleSummary)
async def get_schedule(project_id: int, session: AsyncSession = Depends(get_session)) -> ScheduleSummary:
    project_result = await session.execute(select(Project).where(Project.id == project_id))
    project = project_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    tasks_result = await session.execute(select(Task).where(Task.project_id == project_id))
    tasks = tasks_result.scalars().all()

    if not tasks:
        raise HTTPException(status_code=400, detail="Schedule not generated yet.")

    learning_weeks = sum(1 for task in tasks if task.task_type == TaskType.learning)
    testing_weeks = sum(1 for task in tasks if task.task_type == TaskType.testing)
    total_weeks = learning_weeks + testing_weeks

    feasibility = evaluate_feasibility(
        total_pages=project.total_pages or 0,
        tier=project.tier or KnowledgeTier.intermediate,
        duration_days=project.duration_days or (project.deadline_date - project.start_date).days + 1,
    )

    schedule_summary = ScheduleSummary(
        project=await _serialize_project(project),
        learning_phase_weeks=learning_weeks,
        testing_phase_weeks=testing_weeks,
        total_weeks=total_weeks,
        feasibility_alerts=feasibility.alerts,
        tasks=[
            ScheduleTask(
                week=task.week,
                task_type=task.task_type,
                assigned_chapters=[chapter.strip() for chapter in task.assigned_chapters.split(",") if chapter.strip()],
                due_date=task.due_date,
                status=task.status,
            )
            for task in tasks
        ],
    )
    return schedule_summary
