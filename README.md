# Resume Analyzer

**Resume Analyzer** is a full-stack career intelligence platform that scores resumes, extracts skills from real PDF content, maps realistic target roles, and surfaces live India job openings. Analysis is driven by the exact text extracted from each uploaded resume — not generic templates.

**Live app (local):** `http://localhost:3000` · **API docs:** `http://127.0.0.1:8000/docs`

---

## Core Features

| Feature | Description |
| --- | --- |
| **ATS Scoring** | Domain-aware ATS score (0–100) calibrated to resume content |
| **Dynamic Skill Extraction** | Skills pulled only from evidenced resume text; PII and contact noise filtered out |
| **Realistic Role Matching** | Target roles matched to actual experience depth (fresher, non-IT, IT, cloud, commerce, etc.) |
| **Skill Gap Analysis** | Missing competencies identified relative to the candidate's target role |
| **Learning Roadmap** | Step-by-step milestones in the dashboard PDF report |
| **Live Job Matches** | 4 India openings per recommended role via JSearch (RapidAPI) or Adzuna |
| **PDF Career Report** | Branded export with profile, skills, roadmap, and clickable **Apply** links |
| **Multi-Domain Support** | IT, Cloud & DevOps, Network, Commerce, Healthcare, Education, Management, and more |

---

## What I Used

Everything this project is built with — languages, libraries, APIs, and tooling.

### Languages & runtimes

| Item | Role |
| --- | --- |
| **Python 3.11+** | Backend API and resume analysis |
| **JavaScript (ES6+)** | Frontend UI |
| **HTML / CSS** | Layout and styling |
| **JSON** | API payloads and Gemini structured output |

### Frontend stack

| Item | Role |
| --- | --- |
| **React 19** | UI framework (Create React App / `react-scripts`) |
| **Axios** | HTTP client for analyze + stats APIs |
| **react-dropzone** | PDF upload drag-and-drop |
| **lucide-react** | Icons |
| **jsPDF + jspdf-autotable** | Client-side career report PDF |
| **Bootstrap 5.3** (CDN) | Layout grid and base components |
| **DM Sans + Nunito** (Google Fonts) | Typography |
| **serve** | Fast static hosting of the production build (`start:quick`) |
| **cross-env** | Cross-platform build/start env flags |

### Backend stack

| Item | Role |
| --- | --- |
| **FastAPI** | REST API |
| **Uvicorn** | ASGI server |
| **Pydantic** | Request/response models |
| **python-multipart** | PDF file uploads |
| **python-dotenv** | Load `backend/.env` secrets |
| **Requests** | JSearch / Adzuna HTTP calls |
| **pdfminer.six** | Primary PDF text extraction |
| **pypdf** | Fallback PDF text extraction |

### AI & external APIs

| Item | Role |
| --- | --- |
| **Google Gemini 2.5 Flash** (`google-genai`) | Resume analysis, ATS score, skills, gaps, roadmap |
| **JSearch** via **RapidAPI** | Live India job listings (primary) |
| **Adzuna India API** | Optional alternate job provider |

### Dev & delivery tools

| Item | Role |
| --- | --- |
| **Git + GitHub** | Version control and hosting |
| **Node.js + npm** | Frontend package management |
| **Python venv** | Isolated backend dependencies |
| **quick-start.sh / .bat** | One-command local startup |
| **Cursor** | Development environment |

### Environment variables (local only)

| Variable | Used for |
| --- | --- |
| `GEMINI_API_KEY` | Google Gemini analysis |
| `RAPIDAPI_KEY` | JSearch jobs |
| `RAPIDAPI_HOST` | RapidAPI host (`jsearch.p.rapidapi.com`) |
| `ADZUNA_APP_ID` / `ADZUNA_APP_KEY` | Optional Adzuna jobs |
| `REACT_APP_API_URL` | Frontend → backend URL (production) |

> **Never commit `backend/.env`.** Copy `.env.example`, add keys locally, keep secrets out of Git.

---

## System Architecture

```text
[ User ]
   │
   ▼  Upload PDF resume

┌─────────────────────────────┐
│   React Frontend            │
│   Resume Analyzer UI        │
│   Dashboard + PDF Export    │
└──────────────▲──────────────┘
               │
               ▼
┌─────────────────────────────┐
│   FastAPI Backend           │
│   PDF parse · AI analyze    │
│   Job fetch · Stats API     │
└──────────────┬──────────────┘
               │
      ┌────────┴────────┐
      ▼                 ▼
 Google Gemini      JSearch / Adzuna
 (resume analysis)  (live India jobs)
```

---

## Tech Stack (summary)

| Layer | Technologies |
| --- | --- |
| **Frontend** | React 19, Axios, jsPDF, lucide-react, react-dropzone, Bootstrap 5, Google Fonts |
| **Backend** | Python, FastAPI, Uvicorn, Pydantic, Requests, python-dotenv |
| **PDF Parsing** | pdfminer.six, pypdf |
| **AI** | Google Gemini 2.5 Flash (`google-genai`) with retries + local fallback |
| **Jobs** | JSearch via RapidAPI, Adzuna India API |

---

## Quick Start

From the project root:

```bash
# Windows (Git Bash)
bash quick-start.sh

# Windows (CMD)
quick-start.bat
```

This will:

1. Create the Python virtual environment (if needed)
2. Install frontend dependencies (if needed)
3. Build the frontend (first run only)
4. Start the API on `http://127.0.0.1:8000`
5. Serve the app on `http://localhost:3000`

---

## Manual Setup

### 1. Backend

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate

pip install -r requirements.txt
```

Copy the environment template and add your keys:

```bash
cp .env.example .env
```

```env
GEMINI_API_KEY=your_gemini_api_key
RAPIDAPI_KEY=your_rapidapi_key
RAPIDAPI_HOST=jsearch.p.rapidapi.com

# Optional — Adzuna India jobs
ADZUNA_APP_ID=your_adzuna_app_id
ADZUNA_APP_KEY=your_adzuna_app_key
```

Start the API:

```bash
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

### 2. Frontend

```bash
cd frontend
npm install
npm start
```

**Fast production mode** (pre-built bundle, ~5s startup):

```bash
npm run build:quick
npm run start:quick
```

---

## API Endpoints

| Method | Endpoint | Description |
| --- | --- | --- |
| `GET` | `/health` | Process health, PDF parser status, ML model status, and provider readiness |
| `GET` | `/ready` | Lightweight Kubernetes/container readiness probe (distinguishes core from optional external APIs) |
| `GET` | `/api/platform-stats` | Analysis counts, domain metrics, and provider status |
| `GET` | `/api/features` | Core platform feature catalog |
| `POST` | `/analyze` | Multipart PDF resume upload with optional `job_description` |
| `POST` | `/api/fetch-jobs` | Live job listings matching recommended roles |
| `GET` | `/api/explore-jobs` | Role-based career and job exploration |
| `POST` | `/api/auth/register` | User registration with PBKDF2 password hashing |
| `POST` | `/api/auth/login` | Secure authentication with brute-force lockout protection |
| `GET` | `/api/auth/me` | Bearer token session verification |
| `POST` | `/api/auth/logout` | Session token revocation |

Interactive docs: `http://127.0.0.1:8000/docs`

---

## Automated Testing

### Backend Test Suite
Run the 43 automated pytest unit and integration tests:

```bash
# From workspace root
backend\venv\Scripts\pytest backend\tests -v
```

Tests cover:
- PDF text extraction, signature verification, corrupt/encrypted/scanned document handling
- Parser fallback from pdfminer.six to pypdf
- Evidence-based skill extraction with negative context filtering
- 4-pillar explainable ATS scoring (Quality, Skill Coverage, Practical Evidence, Job Compatibility)
- 3-tier job description compatibility (Explicitly Demonstrated, Potentially Demonstrated, Not Found)
- ML model prediction with graceful heuristic fallback
- Google Gemini structured responses and graceful local NLP fallback on timeout or failure
- Authentication, token verification, session lifecycle, and brute-force lockout protection
- Upload security: media type validation, filename path traversal protection, input size bounds

### Frontend Test Suite
Run Jest unit and component tests:

```bash
cd frontend
npm test -- --watchAll=false
```

---

## Analysis Workflow

1. User uploads a PDF resume
2. Backend extracts text via pdfminer.six / pypdf with fallback
3. Upload is strictly validated for size, magic signature (`%PDF-`), media type, and corruption
4. Multi-factor ATS evaluation calculates:
   - General Resume Quality Score (Structure, impact action verbs, quantified metrics)
   - Domain Competency Coverage (benchmarked to target industry domain)
   - Practical Evidence Score (projects, certifications, quantified outcomes)
   - Job-Specific Compatibility Score (when target JD is provided, with 3-tier requirement breakdown)
5. If Google Gemini is configured, it executes structured analysis; if unavailable or failing, the local heuristic NLP engine automatically takes over without interrupting the user experience
6. Live job listings are searched via JSearch/Adzuna (if configured) or direct career portal search links (LinkedIn, Naukri, Indeed) are provided without fabricating fake listings
7. Results appear on the dashboard; career roadmap and suggestions are included in the downloadable PDF

---

## PDF Report

The **Download Career Report** button generates a styled PDF including:

- Candidate profile (name, email, phone, college)
- ATS score with color-coded badge
- Domain, target role, and recommended roles
- Matched skills and skill gaps
- Career suggestions and learning roadmap
- Live job table with clickable **Apply** links

---

## Project Structure

```text
Resume-scanner--main/
├── backend/
│   ├── main.py              # FastAPI app, Gemini analysis, job APIs
│   ├── skills.py            # Domain profiles, skill extraction
│   ├── pdf_parser.py        # Multi-method PDF text extraction
│   ├── report_generator.py  # Server-side PDF helper
│   ├── .env.example         # Environment template (no secrets)
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.js           # Main UI, navbar, footer, dashboard
│   │   ├── App.css          # Agency-style light theme
│   │   ├── pdfReport.js     # Client-side PDF generator
│   │   ├── LiveJobOpenings.js
│   │   └── TechBackground.js
│   └── package.json
├── quick-start.sh
├── quick-start.bat
└── README.md
```

---

## Cloud Deployment

The repository includes pre-built cloud infrastructure configurations:

- **1-Click Render Blueprint (`render.yaml`):** Deploys both backend (FastAPI) and frontend (React) automatically on Render.
- **Vercel + Render:** Deploy frontend to Vercel and backend to Render with pre-configured CORS and SPA rewrites (`vercel.json`).
- **Single-Container Full-Stack (`Dockerfile`):** Multi-stage build bundling React and FastAPI for Google Cloud Run, AWS App Runner, Fly.io, or Railway (`railway.json`).
- **Docker Compose (`docker-compose.yml`):** Multi-container setup for local staging or VPS deployment (AWS EC2, DigitalOcean).

👉 See [**DEPLOYMENT.md**](./DEPLOYMENT.md) for the complete step-by-step cloud setup and configuration guide.

---

## License

This project is licensed under the **MIT License**.

---

## Support

If this project helped you, consider giving it a star on GitHub:  
https://github.com/theakashsp/Resume-scanner-
