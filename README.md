# StudyPath · Adaptive Textbook Learning System

StudyPath is an end-to-end demo that helps a learner turn a PDF textbook into a personalised study roadmap. The workflow is:

1. Upload a textbook PDF and desired completion deadline.
2. Let the backend extract the table of contents and generate a baseline quiz (via Groq or local fallbacks).
3. Answer the quiz so StudyPath gauges baseline knowledge.
4. Receive a tailored learning + testing schedule that balances feasibility with your knowledge tier.

The stack is intentionally split:

- **Backend:** FastAPI + SQLModel, asynchronous SQLite storage, PDF processing via `PyPDF2`/`pdfplumber`, Groq integration for question generation.
- **Frontend:** React (Vite + TypeScript) with a single-page wizard to upload, assess, and review the schedule.

All data stays local on disk under the backend directory (`studypath.db`, uploaded PDFs, JSON payloads). You control when and whether to use Groq.

---

## 1. Repository Layout

```
backend/
  app/
    assessment.py         Quiz generation + grading heuristic
    config.py             Pydantic settings (env-driven config)
    database.py           Async SQLModel engine/session helpers
   llm.py                Groq chat completion wrapper with fallback
    main.py               FastAPI entry point + router wiring
    models.py             SQLModel ORM definitions (projects, tasks…)
    pdf_processing.py     Table-of-contents extraction + storage
    routers/projects.py   Upload + assessment REST endpoints
    scheduling.py         Feasibility logic + two-phase plan builder
    schemas.py            Pydantic response/request models
    storage.py            Local JSON persistence helpers
  requirements.txt        Backend dependencies
  .env.example            Template for environment variables
frontend/
  src/App.tsx             Multi-step UI (upload → quiz → schedule)
  src/api.ts              Axios client + TS interfaces
  src/styles.css          Minimal styling tokens
  package.json            Frontend dependencies + scripts
reference_*.py            Prior RAG/Groq snippets for reference
ww2_history.pdf           Sample PDF for demoing the workflow
```

---

## 2. Prerequisites

- **Python** 3.10 or newer (tested with 3.11).
- **Node.js** 18+ (bundled with npm).
- **PowerShell** (steps use Windows syntax; adapt if using another shell).
- Optional but recommended: a Groq API key (https://console.groq.com/keys).

Check versions quickly:

```powershell
python --version
node --version
npm --version
```

---

## 3. Backend Setup (FastAPI)

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
```

### Configure Environment Variables

1. Copy the template:

   ```powershell
   copy .env.example .env
   ```

2. Open `.env` and update as needed:

   ```dotenv
   STUDYPATH_GROQ_API_KEY=your_groq_api_key_here
   STUDYPATH_GROQ_MODEL=llama-3.1-70b-versatile
   STUDYPATH_DATABASE_URL=sqlite+aiosqlite:///./studypath.db
   STUDYPATH_DATA_DIR=./data
   ``

   - Set `STUDYPATH_GROQ_API_KEY` (or export `GROQ_API_KEY`) so StudyPath can call Groq's chat completions API.
   - Adjust `STUDYPATH_GROQ_MODEL` if you prefer a different Groq-served model.
   - If the key is blank, StudyPath falls back to deterministic prompts.

3. Start the API:

   ```powershell
   uvicorn app.main:app --reload --port 8000
   ```

   Expected log snippet:

   ```
   INFO:app.main:Initializing database...
   INFO:app.main:Startup complete.
   INFO:     Uvicorn running on http://127.0.0.1:8000
   ```

The API namespace lives under `/api`. Key routes:

- `POST /api/projects` (multipart) — upload PDF + metadata.
- `POST /api/projects/{id}/assessment` — submit quiz answers and trigger schedule.
- `GET /api/projects/{id}/schedule` — retrieve saved tasks.
- `GET /api/health` — health check.

---

## 4. Frontend Setup (Vite + React)

Open a new terminal so the backend keeps running, then:

```powershell
cd frontend
npm install
npm run dev
```

Vite prints a local URL (default `http://localhost:5173`). The dev server proxies `/api/*` to `http://localhost:8000`, so keep the backend alive while using the UI.

---

## 5. Using StudyPath

1. **Upload & Timeline**
   - Fill in project name, select a future deadline (or override total days), pick task granularity, and upload a searchable PDF.
   - The backend saves the PDF under `backend/data/project_<id>/` and extracts its table of contents. If the PDF lacks a ToC, it falls back to 15-page chunks.
   - Any feasibility alerts (e.g., unrealistic pace) appear immediately.

2. **Baseline Knowledge Check**
   - The UI presents 5–7 questions from the first chapters. With Groq enabled these come from the model; otherwise deterministic fallback prompts are used.
   - Answer freeform or multiple-choice items and submit.

3. **Personalised Schedule**
   - StudyPath classifies you into Beginner/Intermediate/Advanced tiers and builds a two-phase plan: ~70% learning weeks, ~30% testing weeks.
   - Learning weeks list chapter assignments sized to your pace. Testing weeks gradually expand coverage for review quizzes.
   - Refresh pulls the stored plan via REST if you revisit later.

Data artefacts:

- `backend/studypath.db` — SQLite database with projects, chapters, tasks.
- `backend/data/project_<id>/source.pdf` — original upload.
- `backend/data/project_<id>/baseline_assessment.json` — cached quiz prompts.

---

## 6. Extending StudyPath

- **Assignments & Progress:** Add PATCH endpoints to mark tasks complete, capture time spent, and feed adaptive pacing adjustments.
- **Testing Engine:** Generate weekly quizzes (during the testing phase) using Groq grounded in stored chapter text snippets.
- **OCR Pipeline:** Integrate an OCR pre-processing step to support image-based PDFs seamlessly.
- **Authentication:** Wrap the API with auth if you plan to deploy beyond a local environment.
- **Export:** Provide calendar exports (ICS) so learners can sync tasks with their personal calendars.

---

## 7. Reference Code & Groq Integration

- `backend/app/llm.py` mirrors the structure from the provided `reference_main.py`, but targets Groq's OpenAI-compatible endpoint. If `STUDYPATH_GROQ_API_KEY` (or `GROQ_API_KEY`) is blank, it warns and returns fallback prompts so the flow never breaks.
- If you are migrating from another provider, adjust the payload or model name in `llm.py` to match the new endpoint.

With this scaffold in place you can iterate quickly, knowing the upload → assessment → schedule loop is already wired end-to-end. Happy building!
