import { ChangeEvent, FormEvent, useMemo, useState } from "react";
import dayjs from "dayjs";
import { fetchSchedule, submitAssessment, uploadProject, type ScheduleSummary, type UploadResponse } from "./api";

interface UploadFormState {
  name: string;
  deadline: string;
  durationDays: string;
  taskGranularity: "daily" | "weekly" | "monthly";
  file?: File;
}

const initialFormState: UploadFormState = {
  name: "",
  deadline: dayjs().add(90, "day").format("YYYY-MM-DD"),
  durationDays: "",
  taskGranularity: "weekly",
};

function App() {
  const [form, setForm] = useState<UploadFormState>(initialFormState);
  const [uploadResult, setUploadResult] = useState<UploadResponse | null>(null);
  const [responses, setResponses] = useState<string[]>([]);
  const [schedule, setSchedule] = useState<ScheduleSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleInputChange = (event: ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = event.target;
  setForm((prev: UploadFormState) => ({ ...prev, [name]: value }));
  };

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
  setForm((prev: UploadFormState) => ({ ...prev, file }));
  };

  const handleUpload = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!form.file) {
      setError("Please select a PDF textbook before uploading.");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const payload = new FormData();
      payload.append("name", form.name || "Untitled Project");
      payload.append("deadline_date", form.deadline);
      payload.append("task_granularity", form.taskGranularity);
      if (form.durationDays) {
        payload.append("duration_days", form.durationDays);
      }
      payload.append("file", form.file);

      const result = await uploadProject(payload);
      setUploadResult(result);
      setResponses(new Array(result.quiz.questions.length).fill(""));
      setSchedule(null);
    } catch (err) {
      setError("Upload failed. Please verify the API is running and try again.");
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleAssessmentSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!uploadResult) return;

    setLoading(true);
    setError(null);

    try {
      const result = await submitAssessment(uploadResult.project.id, responses);
      setSchedule(result);
    } catch (err) {
      setError("Assessment submission failed. Ensure all questions are answered.");
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleScheduleRefresh = async () => {
    if (!uploadResult) return;
    setLoading(true);
    setError(null);
    try {
      const latest = await fetchSchedule(uploadResult.project.id);
      setSchedule(latest);
    } catch (err) {
      setError("Unable to refresh schedule.");
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const quizQuestions = uploadResult?.quiz.questions ?? [];
  const feasibilityNotes = useMemo(() => uploadResult?.feasibility_notes ?? [], [uploadResult]);

  return (
    <div className="app-shell">
      <header>
        <h1>StudyPath · Adaptive Textbook Planner</h1>
        <p>Upload a textbook, gauge your baseline knowledge, and receive an adaptive study roadmap.</p>
      </header>

      <main>
        <section className="card">
          <h2>1 · Upload Textbook & Timeline</h2>
          <form onSubmit={handleUpload} className="form-grid">
            <label>
              Project Name
              <input name="name" value={form.name} onChange={handleInputChange} placeholder="Modern History Essentials" />
            </label>
            <label>
              Deadline Date
              <input type="date" name="deadline" value={form.deadline} onChange={handleInputChange} required />
            </label>
            <label>
              Total Days (optional)
              <input
                type="number"
                name="durationDays"
                value={form.durationDays}
                onChange={handleInputChange}
                placeholder="90"
                min={14}
              />
            </label>
            <label>
              Task Granularity
              <select name="taskGranularity" value={form.taskGranularity} onChange={handleInputChange}>
                <option value="daily">Daily</option>
                <option value="weekly">Weekly</option>
                <option value="monthly">Monthly</option>
              </select>
            </label>
            <label className="file-input">
              PDF Textbook
              <input type="file" accept="application/pdf" onChange={handleFileChange} required />
            </label>
            <button type="submit" disabled={loading}>
              {loading ? "Processing…" : "Upload & Analyze"}
            </button>
          </form>
          {feasibilityNotes.length > 0 && (
            <div className="alert">
              <h3>Feasibility Warnings</h3>
              <ul>
                {feasibilityNotes.map((note) => (
                  <li key={note}>{note}</li>
                ))}
              </ul>
            </div>
          )}
          {uploadResult && (
            <div className="project-metadata">
              <p>
                <strong>Study Window:</strong>{" "}
                {dayjs(uploadResult.project.start_date).format("MMM D, YYYY")} –
                {" "}
                {dayjs(uploadResult.project.deadline_date).format("MMM D, YYYY")} (
                {uploadResult.project.duration_days ?? dayjs(uploadResult.project.deadline_date).diff(uploadResult.project.start_date, "day") + 1} days)
              </p>
            </div>
          )}
          {uploadResult && (
            <div className="chapter-summary">
              <h3>Extracted Table of Contents</h3>
              <ul>
                {uploadResult.chapter_chunks.map((chapter) => (
                  <li key={`${chapter.title}-${chapter.page_start}`}>
                    <strong>{chapter.title}</strong> · Pages {chapter.page_start}–{chapter.page_end} · ≈{chapter.estimated_minutes} min
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>

        {uploadResult && (
          <section className="card">
            <h2>2 · Baseline Knowledge Check</h2>
            <form onSubmit={handleAssessmentSubmit} className="quiz-grid">
              {quizQuestions.map((question, index) => (
                <label key={index}>
                  <span>
                    Q{index + 1}. {question.question}
                    {question.chapter_reference && <em> · {question.chapter_reference}</em>}
                  </span>
                  {question.choices ? (
                    <select
                      value={responses[index] ?? ""}
                      onChange={(event) =>
                        setResponses((prev: string[]) => {
                          const next = [...prev];
                          next[index] = event.target.value;
                          return next;
                        })
                      }
                      required
                    >
                      <option value="" disabled>
                        Select an answer
                      </option>
                      {question.choices.map((choice) => (
                        <option key={choice} value={choice}>
                          {choice}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <textarea
                      value={responses[index] ?? ""}
                      onChange={(event) =>
                        setResponses((prev: string[]) => {
                          const next = [...prev];
                          next[index] = event.target.value;
                          return next;
                        })
                      }
                      placeholder="Write your short answer"
                      required
                    />
                  )}
                </label>
              ))}
              <button type="submit" disabled={loading}>
                {loading ? "Scoring…" : "Generate Personalized Schedule"}
              </button>
            </form>
          </section>
        )}

        {schedule && (
          <section className="card">
            <div className="card-header">
              <h2>3 · Personalized Study Schedule</h2>
              <button onClick={handleScheduleRefresh} disabled={loading}>
                Refresh
              </button>
            </div>
            <div className="grid-two">
              <div>
                <h3>Timeline</h3>
                <p>
                  Learning Phase: {schedule.learning_phase_weeks} week(s) · Testing Phase: {schedule.testing_phase_weeks} week(s)
                </p>
                <p>Total Weeks: {schedule.total_weeks}</p>
                <p>
                  Total Days: {schedule.project.duration_days ?? dayjs(schedule.project.deadline_date).diff(schedule.project.start_date, "day") + 1}
                </p>
                {schedule.feasibility_alerts.length > 0 && (
                  <div className="alert">
                    <h4>Action Required</h4>
                    <ul>
                      {schedule.feasibility_alerts.map((alert) => (
                        <li key={alert}>{alert}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
              <div>
                <h3>Upcoming Tasks</h3>
                <ul className="task-list">
                  {schedule.tasks.map((task) => (
                    <li key={`${task.task_type}-${task.week}`}>
                      <span className="task-week">Week {task.week}</span>
                      <span className="task-type">{task.task_type}</span>
                      <span className="task-due">Due {dayjs(task.due_date).format("MMM D")}</span>
                      <div className="task-chapters">{task.assigned_chapters.join(", ")}</div>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </section>
        )}

        {error && <div className="error-banner">{error}</div>}
      </main>

      <footer>
        <small>All project data stays on this machine. Integrate your Gemini API key in backend/.env to enable LLM-generated assessments.</small>
      </footer>
    </div>
  );
}

export default App;
