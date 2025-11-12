import axios from "axios";

const client = axios.create({
  baseURL: "/api",
});

export interface ProjectSummary {
  id: number;
  name: string;
  start_date: string;
  deadline_date: string;
  duration_days?: number | null;
  tier?: string | null;
  total_pages?: number | null;
  task_granularity: string;
  status: string;
}

export interface ChapterChunk {
  title: string;
  level: number;
  page_start: number;
  page_end: number;
  estimated_minutes: number;
}

export interface KnowledgeQuestion {
  question: string;
  choices?: string[];
  answer?: string | null;
  chapter_reference?: string | null;
}

export interface UploadResponse {
  project: ProjectSummary;
  chapter_chunks: ChapterChunk[];
  quiz: {
    project_id: number;
    questions: KnowledgeQuestion[];
  };
  feasibility_notes: string[];
}

export interface ScheduleTask {
  week: number;
  task_type: "Learning" | "Testing";
  assigned_chapters: string[];
  due_date: string;
  status: string;
}

export interface ScheduleSummary {
  project: ProjectSummary;
  learning_phase_weeks: number;
  testing_phase_weeks: number;
  total_weeks: number;
  feasibility_alerts: string[];
  tasks: ScheduleTask[];
}

export async function uploadProject(payload: FormData) {
  const response = await client.post<UploadResponse>("/projects", payload, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return response.data;
}

export async function submitAssessment(projectId: number, responses: string[]) {
  const response = await client.post<ScheduleSummary>(`/projects/${projectId}/assessment`, {
    responses,
  });
  return response.data;
}

export async function fetchSchedule(projectId: number) {
  const response = await client.get<ScheduleSummary>(`/projects/${projectId}/schedule`);
  return response.data;
}
