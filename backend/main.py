from __future__ import annotations

import json
import os
import re
import shutil
import sys
import time
import urllib.parse
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (OSError, ValueError, AttributeError):
        pass


from logger import logger

def _log(msg: object) -> None:
    logger.info(str(msg))


# ==============================================================================
# TECH STACK OVERVIEW - BACKEND:
# - Web Framework: FastAPI (Uvicorn ASGI Server)
# - Request/Response Validation: Pydantic
# - Generative AI / LLM: Google Gemini 2.5 Flash (google-genai SDK)
# - PDF Text Extraction: pdfminer.six + pypdf (via pdf_parser module)
# - Job Search Integrations: JSearch API (via RapidAPI) & Adzuna India API (via Requests)
# - Domain Matching & Taxonomy: Heuristic NLP engine (via skills module)
# - Authentication: Session & Token-based Auth Store (auth_store module)
# ==============================================================================

# --- [TECH STACK: Requests] HTTP client for External Job APIs (JSearch / Adzuna) ---
import requests
from dotenv import load_dotenv

# --- [TECH STACK: FastAPI] High-performance Web Framework & Middleware ---
from fastapi import FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# --- [TECH STACK: Google Gemini] LLM API for deep resume analysis & roadmaps ---
from google import genai
from google.genai import types
from pathlib import Path

# --- [TECH STACK: pdfminer.six & pypdf] Robust text extraction & validation ---
from pdf_parser import (
    MAX_PDF_FILE_SIZE_BYTES,
    CorruptedPDFError,
    EmptyPDFError,
    EncryptedPDFError,
    ExcessivePageCountError,
    FileSizeLimitExceededError,
    InvalidPDFSignatureError,
    PDFProcessingError,
    ScannedPDFError,
    extract_pdf_text,
    extract_pdf_text_from_bytes,
)

# --- [TECH STACK: Pydantic] Data validation and schema definition ---
from pydantic import BaseModel, Field

# --- [TECH STACK: Auth Store] Local user registration & session management ---
import auth_store

# --- [TECH STACK: Heuristic & NLP Skills Engine] Domain detection & role taxonomy ---
from skills import (
    DOMAIN_PROFILES,
    _NON_RESUME_SIGNALS,
    _RESUME_SIGNALS,
    compute_missing_skills,
    detect_domain,
    evaluate_ats_score,
    extract_professional_skills,
    infer_roles_from_skills,
    merge_recommended_roles,
    sanitize_skills,
)

# --- [TECH STACK: ML Role Matcher & Evaluator] ---
import matcher

_BACKEND_DIR = Path(__file__).resolve().parent
load_dotenv(_BACKEND_DIR / ".env")

# --- [TECH STACK: Environment Variables / Config] ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "").strip()
RAPIDAPI_HOST = os.getenv("RAPIDAPI_HOST", "jsearch.p.rapidapi.com").strip()
ADZUNA_APP_ID = os.getenv("ADZUNA_APP_ID", "").strip()
ADZUNA_APP_KEY = os.getenv("ADZUNA_APP_KEY", "").strip()
JOBS_PER_ROLE = 4
JOB_API_TIMEOUT = 30
MAX_JOB_ROLES = 5
INVALID_PDF_TEXT_ERROR = (
    "Unable to read text from this PDF. It may be scanned or image-only. "
    "Please upload a text-based PDF exported from Word, Google Docs, or a resume builder."
)
_PLACEHOLDER_KEYS = {
    "your_gemini_api_key",
    "your_rapidapi_key",
    "your_adzuna_app_id",
    "your_adzuna_app_key",
}


def _is_real_key(value: str | None) -> bool:
    key = (value or "").strip()
    if len(key) < 12:
        return False
    return key.lower() not in _PLACEHOLDER_KEYS and not key.lower().startswith("your_")


# ==============================================================================
# TECH STACK: [Google Gemini 2.5 Flash] - LLM client initialization via google-genai SDK
# ==============================================================================
_genai_client = (
    genai.Client(
        api_key=GEMINI_API_KEY.strip(),
        http_options=types.HttpOptions(timeout=120_000),
    )
    if _is_real_key(GEMINI_API_KEY)
    else None
)

_TRANSIENT_GEMINI_MARKERS = (
    "ssl",
    "eof",
    "unexpected_eof",
    "connecterror",
    "connectionreset",
    "remoteprotocolerror",
    "server disconnected",
    "timed out",
    "timeout",
    "temporarily unavailable",
    "503",
    "429",
)


def _is_transient_gemini_error(exc: BaseException) -> bool:
    blob = f"{type(exc).__name__} {exc}".lower()
    return any(marker in blob for marker in _TRANSIENT_GEMINI_MARKERS)

import database
import s3_storage

_cors_env = os.getenv("CORS_ORIGINS", "").strip()
_frontend_url = os.getenv("FRONTEND_URL", "").strip()
ALLOWED_ORIGINS: list[str] = [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://localhost:3002",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
    "http://127.0.0.1:3002",
]

if _cors_env:
    for orig in _cors_env.split(","):
        clean = orig.strip().rstrip("/")
        if clean and clean not in ALLOWED_ORIGINS:
            ALLOWED_ORIGINS.append(clean)

if _frontend_url:
    for orig in _frontend_url.split(","):
        clean = orig.strip().rstrip("/")
        if clean and clean not in ALLOWED_ORIGINS:
            ALLOWED_ORIGINS.append(clean)

# Cloud preview regex: auto-permits Vercel, Netlify, and Render dynamic preview domains
_cors_regex_env = os.getenv(
    "CORS_ORIGIN_REGEX",
    r"^https:\/\/.*\.vercel\.app$|^https:\/\/.*\.netlify\.app$|^https:\/\/.*\.onrender\.com$",
).strip()
_allow_origin_regex = _cors_regex_env if _cors_regex_env else None

# Handle if wildcard '*' was specified in CORS_ORIGINS
if "*" in ALLOWED_ORIGINS or _cors_env == "*":
    ALLOWED_ORIGINS = [orig for orig in ALLOWED_ORIGINS if orig != "*"]
    _allow_origin_regex = ".*"

# Optional: Resolve Frontend static build folder for unified/single-container hosting
_FRONTEND_BUILD_DIR = os.getenv("FRONTEND_BUILD_DIR", "").strip()
if not _FRONTEND_BUILD_DIR:
    for _candidate_path in [
        _BACKEND_DIR.parent / "frontend" / "build",
        _BACKEND_DIR / "frontend_build",
        Path("/app/frontend/build"),
        Path("/app/build"),
    ]:
        if _candidate_path.is_dir() and (_candidate_path / "index.html").is_file():
            _FRONTEND_BUILD_DIR = str(_candidate_path)
            break

_spa_build_path = Path(_FRONTEND_BUILD_DIR) if _FRONTEND_BUILD_DIR else None
_spa_index_file = (_spa_build_path / "index.html") if _spa_build_path else None

# ==============================================================================
# TECH STACK: [FastAPI] - Application instance, OpenAPI documentation & CORS Middleware
# ==============================================================================
INVALID_RESUME_ERROR = "Invalid document type. Please upload a valid resume."

app = FastAPI(
    title="Resume Analyzer API",
    version="4.2",
    description="Full-stack AI Career Intelligence Engine powered by FastAPI & Google Gemini",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=_allow_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount React static files if frontend build exists
if _spa_build_path and (_spa_build_path / "static").is_dir():
    app.mount("/static", StaticFiles(directory=str(_spa_build_path / "static")), name="frontend_static")


@app.middleware("http")
async def request_logging_middleware(request, call_next):
    start_time = time.time()
    try:
        response = await call_next(request)
        duration_ms = (time.time() - start_time) * 1000
        logger.info(f"{request.method} {request.url.path} - {response.status_code} ({duration_ms:.1f}ms)")
        return response
    except Exception as exc:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(f"{request.method} {request.url.path} - Exception: {type(exc).__name__} ({duration_ms:.1f}ms)")
        raise


@app.on_event("startup")
def on_app_startup():
    database.init_db()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

_DATA_DIR = Path(os.getenv("DATA_DIR", str(_BACKEND_DIR)))
try:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
except OSError:
    pass

_STATS_FILE = _DATA_DIR / "platform_stats.json"
_analysis_count = 0


def _load_stats() -> dict[str, Any]:
    global _analysis_count
    if _STATS_FILE.is_file():
        try:
            data = json.loads(_STATS_FILE.read_text(encoding="utf-8"))
            _analysis_count = int(data.get("total_analyses", 0))
            return data
        except (json.JSONDecodeError, OSError, TypeError, ValueError):
            pass
    return {"total_analyses": 0}


def _save_stats() -> None:
    try:
        _STATS_FILE.write_text(
            json.dumps({"total_analyses": _analysis_count}, indent=2),
            encoding="utf-8",
        )
    except OSError:
        pass


def _increment_analysis_count() -> int:
    global _analysis_count
    _analysis_count += 1
    _save_stats()
    return _analysis_count


_load_stats()

PLATFORM_FEATURES = [
    {
        "id": "ats",
        "title": "ATS Scoring Engine",
        "description": "Domain-aware scoring calibrated to your resume content with recruiter-grade precision.",
        "icon": "target",
    },
    {
        "id": "skills",
        "title": "Skill Extraction",
        "description": "Professional competencies extracted cleanly — no contact metadata noise.",
        "icon": "layers",
    },
    {
        "id": "jobs",
        "title": "Live Job Matches",
        "description": "Real-time India openings mapped to your recommended career roles via JSearch.",
        "icon": "briefcase",
    },
    {
        "id": "roadmap",
        "title": "Career Roadmap",
        "description": "Personalized learning milestones delivered in your downloadable PDF report.",
        "icon": "route",
    },
    {
        "id": "domains",
        "title": "Multi-Domain Support",
        "description": "IT, Cloud, Commerce, Healthcare, Education, and more — not just tech roles.",
        "icon": "globe",
    },
    {
        "id": "secure",
        "title": "Secure Processing",
        "description": "Resumes are analyzed in-memory and never stored after your session ends.",
        "icon": "shield",
    },
]

GEMINI_RESUME_SCHEMA = {
    "type": "object",
    "properties": {
        "is_valid_resume": {"type": "boolean"},
        "error": {"type": "string"},
        "candidate_domain": {"type": "string"},
        "ats_score": {"type": "integer", "minimum": 0, "maximum": 100},
        "target_role": {"type": "string"},
        "current_skills": {"type": "array", "items": {"type": "string"}},
        "missing_skills": {"type": "array", "items": {"type": "string"}},
        "custom_roadmap": {"type": "array", "items": {"type": "string"}},
        "career_suggestions": {"type": "string"},
    },
    "required": ["is_valid_resume"],
}

class GeminiServiceError(RuntimeError):
    """Raised when external Gemini service request fails or returns invalid structure."""
    pass


class GeminiAnalysisOutput(BaseModel):
    is_valid_resume: bool
    error: str | None = None
    candidate_domain: str | None = None
    ats_score: int = Field(default=50, ge=0, le=100)
    target_role: str | None = None
    current_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    custom_roadmap: list[str] = Field(default_factory=list)
    career_suggestions: str | None = None


# ==============================================================================
# TECH STACK: [Pydantic] - Data Validation & Serialization Models
# ==============================================================================
class FetchJobsRequest(BaseModel):
    recommended_roles: list[str] = Field(default_factory=list)


class RegisterRequest(BaseModel):
    name: str = ""
    email: str = ""
    password: str = ""
    phone: str = ""


class LoginRequest(BaseModel):
    email: str = ""
    password: str = ""



def _normalize_resume_text(text: str) -> str:
    if not text:
        return ""
    return text.encode("utf-8", errors="replace").decode("utf-8", errors="replace").strip()


def _job_record(
    role_category: str,
    company_name: str,
    job_title: str,
    location: str,
    redirect_url: str,
    employment_type: str = "Full-time",
) -> dict[str, Any]:
    url = (redirect_url or "").strip()
    if not url or url == "#" or not (url.startswith("http://") or url.startswith("https://")):
        query = f"{job_title} {company_name} jobs India"
        url = f"https://www.google.com/search?q={urllib.parse.quote(query)}&ibp=htl;jobs"

    portal = "Direct Apply"
    lower_url = url.lower()
    if "linkedin.com" in lower_url:
        portal = "LinkedIn"
    elif "naukri.com" in lower_url:
        portal = "Naukri"
    elif "indeed.com" in lower_url:
        portal = "Indeed"
    elif "foundit.in" in lower_url:
        portal = "Foundit"
    elif "google.com" in lower_url:
        portal = "Google Jobs"

    return {
        "role_category": role_category,
        "company_name": company_name,
        "job_title": job_title,
        "location": location,
        "redirect_url": url,
        "employer_name": company_name,
        "job_apply_link": url,
        "job_employment_type": employment_type,
        "portal": portal,
    }


def jobs_provider_status() -> dict[str, Any]:
    has_jsearch = _is_real_key(RAPIDAPI_KEY)
    has_adzuna = _is_real_key(ADZUNA_APP_ID) and _is_real_key(ADZUNA_APP_KEY)
    any_prov = has_jsearch or has_adzuna
    return {
        "jsearch_configured": has_jsearch,
        "adzuna_configured": has_adzuna,
        "any_provider": any_prov,
        "provider_name": "JSearch" if has_jsearch else ("Adzuna" if has_adzuna else "Not configured (Live APIs require RAPIDAPI_KEY or ADZUNA credentials)"),
    }


def ai_provider_status() -> dict[str, Any]:
    return {
        "gemini_configured": _genai_client is not None,
        "analysis_mode": "gemini" if _genai_client is not None else "heuristic",
    }


def get_direct_portal_search_links(role_category: str) -> list[dict[str, str]]:
    role_clean = role_category.strip() or "Software Engineer"
    slug = re.sub(r"[^a-z0-9]+", "-", role_clean.lower()).strip("-")
    encoded_role = urllib.parse.quote(role_clean)
    return [
        {
            "portal": "LinkedIn",
            "url": f"https://www.linkedin.com/jobs/search/?keywords={encoded_role}&location=India",
            "label": f"Search '{role_clean}' on LinkedIn India",
        },
        {
            "portal": "Naukri",
            "url": f"https://www.naukri.com/{slug}-jobs-in-india",
            "label": f"Search '{role_clean}' on Naukri.com",
        },
        {
            "portal": "Indeed",
            "url": f"https://in.indeed.com/jobs?q={encoded_role}&l=India",
            "label": f"Search '{role_clean}' on Indeed India",
        },
        {
            "portal": "Foundit",
            "url": f"https://www.foundit.in/srp/results?query={encoded_role}&locations=India",
            "label": f"Search '{role_clean}' on Foundit",
        },
        {
            "portal": "Google Jobs",
            "url": f"https://www.google.com/search?q={urllib.parse.quote(role_clean + ' jobs India')}&ibp=htl;jobs",
            "label": f"Search '{role_clean}' on Google Jobs",
        },
    ]


# ==============================================================================
# TECH STACK: [JSearch API via RapidAPI] - Live real-time India job market search
# ==============================================================================
def fetch_jsearch_jobs(role_category: str, limit: int = JOBS_PER_ROLE) -> list[dict[str, Any]]:
    if not _is_real_key(RAPIDAPI_KEY):
        return []
    query = f"{role_category} in India"
    out: list[dict[str, Any]] = []
    try:
        host = RAPIDAPI_HOST.strip().lower().rstrip("/")
        if host.startswith("http://") or host.startswith("https://"):
            base_url = host
        else:
            base_url = f"https://{host}"
        r = requests.get(
            f"{base_url}/search",
            headers={
                "X-RapidAPI-Key": RAPIDAPI_KEY,
                "X-RapidAPI-Host": RAPIDAPI_HOST,
            },
            params={
                "query": query,
                "page": "1",
                "num_pages": "1",
                "country": "in",
            },
            timeout=(5, 15),
        )
        if r.status_code == 429:
            _log(f"[JSearch] Rate limit exceeded (429) for '{role_category}'")
            return []
        r.raise_for_status()
        seen_keys: set[str] = set()
        for j in (r.json().get("data") or []):
            if len(out) >= limit:
                break
            apply_link = (j.get("job_apply_link") or j.get("job_google_link") or "").strip()
            if not apply_link or not (apply_link.startswith("http://") or apply_link.startswith("https://")):
                continue
            comp = (j.get("employer_name") or "Hiring Company").strip()
            title = (j.get("job_title") or role_category).strip()
            dedup_key = f"{comp.lower()}::{title.lower()}"
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)

            city = j.get("job_city") or ""
            country = j.get("job_country") or "India"
            loc = ", ".join(x for x in [city, country] if x) or "India"
            out.append(
                _job_record(
                    role_category=role_category,
                    company_name=comp,
                    job_title=title,
                    location=loc,
                    redirect_url=apply_link,
                    employment_type=j.get("job_employment_type") or "Full-time",
                )
            )
    except requests.exceptions.Timeout:
        _log(f"[JSearch] Request timed out for role: {role_category}")
    except Exception as exc:
        _log(f"[JSearch] {type(exc).__name__}: {exc!r}")
    return out[:limit]


# ==============================================================================
# TECH STACK: [Adzuna India API] - Alternative live job search provider
# ==============================================================================
def fetch_adzuna_jobs(role_category: str, limit: int = JOBS_PER_ROLE) -> list[dict[str, Any]]:
    if not (_is_real_key(ADZUNA_APP_ID) and _is_real_key(ADZUNA_APP_KEY)):
        return []
    out: list[dict[str, Any]] = []
    try:
        r = requests.get(
            "https://api.adzuna.com/v1/api/jobs/in/search/1",
            params={
                "app_id": ADZUNA_APP_ID,
                "app_key": ADZUNA_APP_KEY,
                "what": role_category,
                "results_per_page": limit,
            },
            timeout=(5, 15),
        )
        if r.status_code == 429:
            _log(f"[Adzuna] Rate limit exceeded (429) for '{role_category}'")
            return []
        r.raise_for_status()
        seen_keys: set[str] = set()
        for j in (r.json().get("results") or []):
            if len(out) >= limit:
                break
            apply_link = (j.get("redirect_url") or "").strip()
            if not apply_link or not (apply_link.startswith("http://") or apply_link.startswith("https://")):
                continue
            comp = ((j.get("company") or {}).get("display_name") or "Hiring Company").strip()
            title = (j.get("title") or role_category).strip()
            dedup_key = f"{comp.lower()}::{title.lower()}"
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)

            loc_obj = j.get("location") or {}
            loc = loc_obj.get("display_name") or "India"
            out.append(
                _job_record(
                    role_category=role_category,
                    company_name=comp,
                    job_title=title,
                    location=loc,
                    redirect_url=apply_link,
                    employment_type=j.get("contract_type") or "Full-time",
                )
            )
    except requests.exceptions.Timeout:
        _log(f"[Adzuna] Request timed out for role: {role_category}")
    except Exception as exc:
        _log(f"[Adzuna] {type(exc).__name__}: {exc!r}")
    return out[:limit]


def fetch_india_jobs_for_role(role_category: str, limit: int = JOBS_PER_ROLE) -> list[dict[str, Any]]:
    seen: set[str] = set()
    merged: list[dict[str, Any]] = []
    if _is_real_key(RAPIDAPI_KEY) or (_is_real_key(ADZUNA_APP_ID) and _is_real_key(ADZUNA_APP_KEY)):
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [
                pool.submit(fetch_jsearch_jobs, role_category, limit),
                pool.submit(fetch_adzuna_jobs, role_category, limit),
            ]
            for future in as_completed(futures):
                try:
                    for job in future.result():
                        url = job.get("redirect_url") or ""
                        if url in seen or url == "#":
                            continue
                        seen.add(url)
                        merged.append(job)
                        if len(merged) >= limit:
                            return merged[:limit]
                except Exception as exc:
                    _log(f"[fetch_jobs] provider execution error: {type(exc).__name__}: {exc!r}")

    return merged[:limit]


def fetch_jobs_for_roles(
    roles: list[str],
    per_role_limit: int = JOBS_PER_ROLE,
) -> dict[str, list[dict[str, Any]]]:
    role_names = [str(role).strip() for role in roles if str(role).strip()][:MAX_JOB_ROLES]
    if not role_names:
        return {}
    grouped: dict[str, list[dict[str, Any]]] = {}
    with ThreadPoolExecutor(max_workers=min(len(role_names), 5)) as pool:
        futures = {
            pool.submit(fetch_india_jobs_for_role, role_name, per_role_limit): role_name
            for role_name in role_names
        }
        for future in as_completed(futures):
            role_name = futures[future]
            grouped[role_name] = future.result()
    return grouped


def _heuristic_is_resume(text: str) -> bool:
    normalized = _normalize_resume_text(text)
    if len(normalized) < 35:
        return False
    lower = normalized.lower()
    non_resume_hits = sum(1 for sig in _NON_RESUME_SIGNALS if sig in lower)
    resume_hits = sum(1 for sig in _RESUME_SIGNALS if sig in lower)
    if non_resume_hits >= 2 and resume_hits < 1:
        return False
    has_contact = bool(
        re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", normalized)
        or re.search(r"(?:\+91[\-\s]?)?[6-9]\d{9}", normalized)
    )
    has_experience_block = any(
        k in lower
        for k in ("experience", "education", "skills", "project", "internship", "work", "employment", "responsibilities")
    )
    has_company_marker = any(
        marker in lower
        for marker in (" pvt", " ltd", " limited", " technologies", " solutions", " infotech", " services")
    )
    has_work_timeline = bool(
        re.search(r"\b(19|20)\d{2}\s*[-–—to]{1,3}\s*((19|20)\d{2}|present|current)\b", lower)
    )
    if has_contact and (has_experience_block or has_company_marker or has_work_timeline):
        return True
    if resume_hits >= 2:
        return True
    if len(normalized) >= 80 and (resume_hits >= 1 or has_experience_block):
        return True
    return False


def _strip_llm_json(raw: str) -> str:
    text = (raw or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```\s*$", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text.strip()


def _roadmap_strings_to_objects(steps: list[Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for index, item in enumerate(steps or [], start=1):
        line = str(item).strip()
        if not line:
            continue
        title = line.split(":", 1)[0].strip() if ":" in line else f"Milestone {index}"
        out.append(
            {
                "step": index,
                "title": title[:120],
                "focus": line,
                "project_idea": line,
            }
        )
    return out


def _generate_structured_ai_suggestions(
    domain: str,
    target_role: str,
    ats_score: int,
    current_skills: list[str],
    missing_skills: list[str],
    extracted_text: str = "",
) -> tuple[str, list[dict[str, Any]]]:
    clean_role = target_role or "Software Professional"
    primary_skills = current_skills[:5] if current_skills else ["Core Technical Competencies"]
    skills_str = ", ".join(primary_skills)
    top_gaps = missing_skills[:4] if missing_skills else ["Cloud Architecture & CI/CD"]
    gaps_str = ", ".join(top_gaps)

    # 1. Target Role & Profile Positioning
    positioning_points = [
        f"Role Alignment: Your demonstrated skills in {skills_str} establish a strong technical baseline for {clean_role} positions in {domain}.",
        f"Summary Statement: Add a crisp 2-line summary at the top of your resume: '{clean_role} proficient in {primary_skills[0] if primary_skills else 'software engineering'} with demonstrated project experience in modern {domain} workflows.'",
        f"Domain Authority: Frame academic coursework and personal projects around industry use-cases to showcase commercial readiness.",
    ]

    # 2. High-Priority Technical Skills to Bridge
    skills_points = [
        f"Priority Competencies: Fast-track hands-on proficiency in {top_gaps[0] if top_gaps else 'System Design'}{f' and {top_gaps[1]}' if len(top_gaps) > 1 else ''} to directly match modern {clean_role} job listings.",
        f"Evidence-Based Learning: Rather than theoretical tutorials, build production-grade modules demonstrating these missing tools in your active GitHub repositories.",
    ]
    if len(top_gaps) > 2:
        skills_points.append(f"Secondary Tooling: Explore {', '.join(top_gaps[2:])} to broaden your versatility for full-stack and cloud-native workflows.")

    # 3. ATS Optimization & Bullet-Point Formulation
    ats_points = [
        "Google XYZ Formula: Format all project and experience bullet points as 'Accomplished [X], measured by [Y]%, by implementing [Z]' to maximize recruiter and ATS scoring.",
        f"Power Verbs: Start every description with strong action verbs (e.g., 'Architected', 'Engineered', 'Optimized', 'Automated', 'Scaled') instead of passive statements ('Worked on', 'Responsible for').",
        f"Keyword Prominence: Ensure high-priority keywords ({clean_role}, {primary_skills[0] if primary_skills else 'Python'}, {primary_skills[1] if len(primary_skills) > 1 else 'SQL'}) appear prominently in the top 35% of your resume.",
    ]

    # 4. Tailored Capstone Project Blueprint
    role_lower = clean_role.lower()
    if any(k in role_lower for k in ("java", "spring")):
        project_title = "Enterprise Microservices E-Commerce / Banking Backend"
        project_desc = "Architect a decoupled microservices application using Spring Boot, Spring Cloud Gateway, Kafka event streams, PostgreSQL, Redis caching, and Docker Compose."
    elif any(k in role_lower for k in ("python", "data", "ai", "machine learning", "ml")):
        project_title = "End-to-End AI Analytics & RAG Knowledge Engine"
        project_desc = "Develop an automated data pipeline and REST API with FastAPI, Vector DB (Chroma/FAISS), PyTorch/Pandas, and an interactive analytics dashboard."
    elif any(k in role_lower for k in ("frontend", "react", "web", "full stack")):
        project_title = "Real-Time Collaborative SaaS Platform"
        project_desc = "Build a responsive web application using React/Next.js, TypeScript, WebSocket state sync, Tailwind CSS, PostgreSQL/MongoDB, and secure JWT auth."
    elif any(k in role_lower for k in ("cloud", "devops", "sre")):
        project_title = "Multi-Cloud GitOps Infrastructure & Kubernetes Pipeline"
        project_desc = "Provision infrastructure using Terraform, automate CI/CD deployments via GitHub Actions, and configure Kubernetes Helm charts with Prometheus/Grafana monitoring."
    else:
        project_title = f"Production-Grade {clean_role} Portfolio Capstone"
        project_desc = f"Build an end-to-end full-lifecycle application showcasing core competencies in {skills_str}, comprehensive testing, and clean modular architecture."

    project_points = [
        f"Recommended Blueprint: {project_title}.",
        f"Technical Scope: {project_desc}",
        "Production Readiness: Include unit tests, Docker containerization, API documentation (Swagger/Postman), and a live deployment link.",
    ]

    # 5. Interview Readiness & Portfolio Strategy
    interview_points = [
        f"Core Technical Rounds: Prepare depth in Data Structures, OOP/System Design, and database query optimization commonly evaluated for {clean_role}.",
        "GitHub Hygiene: Maintain clear repository READMEs with architectural diagrams, animated demo GIFs, setup instructions, and clean Git commit messages.",
        "Scenario-Based Questions: Prepare STAR (Situation, Task, Action, Result) stories highlighting technical trade-offs, debugging challenges, and team collaboration.",
    ]

    structured_suggestions = [
        {
            "category": "positioning",
            "icon": "target",
            "title": "Target Role & Professional Positioning",
            "points": positioning_points,
        },
        {
            "category": "skills",
            "icon": "zap",
            "title": "High-Priority Technical Skills to Bridge",
            "points": skills_points,
        },
        {
            "category": "ats",
            "icon": "file-text",
            "title": "ATS Optimization & Bullet-Point Formulation",
            "points": ats_points,
        },
        {
            "category": "project",
            "icon": "layers",
            "title": "Recommended Capstone Project Idea",
            "points": project_points,
        },
        {
            "category": "interview",
            "icon": "briefcase",
            "title": "Interview Readiness & Portfolio Strategy",
            "points": interview_points,
        },
    ]

    formatted_lines: list[str] = []
    for item in structured_suggestions:
        formatted_lines.append(f"• {item['title']}:")
        for pt in item["points"]:
            formatted_lines.append(f"   - {pt}")
        formatted_lines.append("")

    formatted_text = "\n".join(formatted_lines).strip()
    return formatted_text, structured_suggestions


def _map_analysis_response(raw: dict[str, Any], extracted_text: str) -> dict[str, Any]:
    if not raw.get("is_valid_resume", False):
        return {"error": raw.get("error") or INVALID_RESUME_ERROR}

    domain = str(
        raw.get("candidate_domain") or raw.get("detected_domain") or detect_domain(extracted_text)
    ).strip()
    target_role = str(raw.get("target_role") or raw.get("predicted_role") or "").strip()
    metadata = _extract_candidate_details(extracted_text)
    current_skills = sanitize_skills(
        [str(s).strip() for s in (raw.get("current_skills") or raw.get("matched_skills") or []) if str(s).strip()],
        metadata,
    )
    missing_skills = sanitize_skills(
        [str(s).strip() for s in (raw.get("missing_skills") or []) if str(s).strip()],
        metadata,
    )
    roadmap_lines = [str(s).strip() for s in (raw.get("custom_roadmap") or []) if str(s).strip()]
    if not roadmap_lines:
        legacy = raw.get("learning_roadmap") or []
        roadmap_lines = [
            str(item.get("focus") or item.get("title") or "").strip()
            for item in legacy
            if isinstance(item, dict) and str(item.get("focus") or item.get("title") or "").strip()
        ]

    try:
        ats_score = int(raw.get("ats_score", 0))
    except (TypeError, ValueError):
        ats_score = 0
    ats_score = max(0, min(100, ats_score))

    if not target_role:
        skill_roles = infer_roles_from_skills(current_skills, domain)
        target_role = skill_roles[0] if skill_roles else "Graduate Trainee"

    skill_roles = infer_roles_from_skills(current_skills, domain)
    recommended_roles = merge_recommended_roles([target_role], skill_roles, limit=6)
    if not recommended_roles:
        recommended_roles = [target_role]

    learning_roadmap = _roadmap_strings_to_objects(roadmap_lines)
    suggestion_text, structured_suggestions = _generate_structured_ai_suggestions(
        domain, target_role, ats_score, current_skills, missing_skills, extracted_text
    )

    return {
        "is_valid_resume": True,
        "detected_domain": domain,
        "candidate_domain": domain,
        "ats_score": ats_score,
        "predicted_role": target_role,
        "target_role": target_role,
        "recommended_roles": recommended_roles,
        "matched_skills": current_skills,
        "current_skills": current_skills,
        "missing_skills": missing_skills,
        "custom_roadmap": roadmap_lines,
        "learning_roadmap": learning_roadmap,
        "custom_suggestion": suggestion_text,
        "career_suggestions": suggestion_text,
        "structured_suggestions": structured_suggestions,
    }


def _build_text_only_analysis(extracted_text: str, job_description: str | None = None) -> dict[str, Any]:
    if not _heuristic_is_resume(extracted_text):
        return {"error": INVALID_RESUME_ERROR}

    text = _normalize_resume_text(extracted_text)
    lower = text.lower()
    domain = detect_domain(text)
    profile = DOMAIN_PROFILES[domain]
    roles = list(profile["roles"])
    metadata = _extract_candidate_details(text)

    # Explainable multi-factor ATS evaluation
    ats_eval = evaluate_ats_score(text, domain=domain, job_description=job_description)
    ats_score = ats_eval["overall_ats_score"]
    current_skills = sanitize_skills(ats_eval["evidenced_skills"], metadata)

    # ML role classification with heuristic fallback
    ml_role = matcher.predict_role_with_ml(text)
    if ml_role:
        target_role = ml_role
    else:
        role_scores: list[tuple[str, int]] = []
        for role in roles:
            role_tokens = [t for t in re.findall(r"[a-z]+", role.lower()) if len(t) > 3]
            depth = sum(1 for t in role_tokens if t in lower)
            depth += sum(1 for skill in current_skills if any(tok in skill.lower() for tok in role_tokens))
            role_scores.append((role, depth))
        role_scores.sort(key=lambda item: item[1], reverse=True)
        target_role = role_scores[0][0] if role_scores else "Graduate Trainee"

        if any(k in lower for k in ("fresher", "intern", "trainee", "student", "graduate", "pursuing")):
            entry_roles = [r for r in roles if any(k in r.lower() for k in ("intern", "trainee", "junior", "associate", "graduate"))]
            if entry_roles:
                target_role = entry_roles[0]

    missing_skills = compute_missing_skills(current_skills, domain)

    roadmap_lines: list[str] = []
    if missing_skills:
        roadmap_lines.append(
            f"Step 1: Build hands-on practice in {missing_skills[0]} using a project referenced in your resume narrative."
        )
        if len(missing_skills) > 1:
            roadmap_lines.append(
                f"Step 2: Strengthen {missing_skills[1]} through coursework or workplace evidence aligned with {target_role}."
            )
        if len(missing_skills) > 2:
            roadmap_lines.append(
                f"Step 3: Prepare for {target_role} interviews by documenting outcomes for {', '.join(current_skills[:3]) or 'your listed experience'}."
            )
    else:
        roadmap_lines.append(
            f"Step 1: Refine resume bullets to quantify outcomes tied to {target_role}."
        )
        roadmap_lines.append(
            f"Step 2: Apply to entry-level {domain} roles that match the experience depth shown in your resume."
        )

    payload = {
        "is_valid_resume": True,
        "candidate_domain": domain,
        "ats_score": ats_score,
        "target_role": target_role,
        "current_skills": current_skills,
        "missing_skills": missing_skills,
        "custom_roadmap": roadmap_lines,
    }
    mapped = _map_analysis_response(payload, text)
    mapped["_source"] = "heuristic"
    mapped["scoring_breakdown"] = {
        "overall_ats_score": ats_eval["overall_ats_score"],
        "general_quality_score": ats_eval["general_quality_score"],
        "skill_coverage_score": ats_eval["skill_coverage_score"],
        "practical_evidence_score": ats_eval["practical_evidence_score"],
        "job_compatibility_score": ats_eval.get("job_compatibility_score"),
        "weights": ats_eval["scoring_weights"],
    }
    mapped["evidence_explanations"] = ats_eval["evidence_explanations"]
    mapped["scoring_weights"] = ats_eval["scoring_weights"]
    mapped["disclaimer"] = ats_eval["disclaimer"]
    if ats_eval.get("job_specific_analysis"):
        mapped["job_specific_analysis"] = ats_eval["job_specific_analysis"]
    if ml_role:
        mapped["ml_predicted_role"] = ml_role
    return mapped


# ==============================================================================
# TECH STACK: [Google Gemini 2.5 Flash] - LLM Structured Generation & Deep Resume Analysis
# ==============================================================================
def analyze_resume_with_gemini(extracted_text: str) -> dict[str, Any]:
    if _genai_client is None:
        raise RuntimeError("GEMINI_API_KEY missing")

    bounded_text = _normalize_resume_text(extracted_text)[:12000]
    prompt = f"""You are a resume analysis engine for Indian job seekers.

STRICT CONTEXT BOUNDING:
You must base your entire analysis ONLY on the exact resume text between the markers below.
Do NOT invent, guess, or assume any technical competencies, certifications, employers, projects, or past roles.
If a skill, tool, certification, or competency is not explicitly stated in the resume text, it must NOT appear in current_skills.
Do NOT import skills from job titles alone unless the underlying tool or competency is explicitly written in the text.

DOCUMENT VALIDATION:
If the text is not an authentic resume or CV (notes, articles, assignments, blank text), set is_valid_resume to false and error to exactly:
"Invalid document type. Please upload a valid resume."
When invalid, return only is_valid_resume and error.

ROLE REALISM:
Analyze the actual depth of projects, internships, education, and employment in the resume text.
Assign a realistic target_role proportional to demonstrated depth.
A student with only basic HTML must NOT receive Principal Architect or Senior roles; use titles such as Junior Frontend Intern or Web Developer Trainee.
For non-IT or fresher backgrounds, identify the true industry domain (Marketing, Commerce, Core Engineering, Healthcare, Education, etc.).
Extract transferable soft skills only when explicitly evidenced in the text and map a logical realistic path.

GAP MATCHING:
missing_skills must list competencies required for target_role that are absent from the resume text.
custom_roadmap must be 3 to 5 step-by-step milestone strings that directly close those specific gaps using only resume context.

OUTPUT:
Return ONLY valid JSON matching this schema:
{{
  "is_valid_resume": true,
  "candidate_domain": "string",
  "ats_score": integer 0-100,
  "target_role": "string",
  "current_skills": ["strings explicitly evidenced in resume"],
  "missing_skills": ["strings required for target_role but absent from resume"],
  "custom_roadmap": ["step-by-step milestone strings"]
}}

--- RESUME TEXT START ---
{bounded_text}
--- RESUME TEXT END ---"""

    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            response = _genai_client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_json_schema=GEMINI_RESUME_SCHEMA,
                    temperature=0.1,
                ),
            )
            cleaned = _strip_llm_json(response.text or "")
            parsed = json.loads(cleaned)
            # Validate output using stable Pydantic schema
            validated = GeminiAnalysisOutput.model_validate(parsed)
            mapped = _map_analysis_response(validated.model_dump(), bounded_text)
            if mapped.get("error"):
                return mapped
            mapped["_source"] = "gemini"
            return mapped
        except json.JSONDecodeError as e:
            _log(f"[Gemini] JSONDecodeError: {e!r}")
            raise GeminiServiceError(f"Gemini returned unparsable JSON: {e!r}") from e
        except Exception as e:
            last_error = e
            _log(f"[Gemini] attempt {attempt}/3 {type(e).__name__}: {e!r}")
            if _is_transient_gemini_error(e) and attempt < 3:
                time.sleep(min(8.0, 1.5 * (2 ** (attempt - 1))))
                continue
            break

    safe_detail = str(last_error or "unknown error").encode("ascii", "backslashreplace").decode("ascii")
    raise GeminiServiceError(f"Gemini analysis failed: {safe_detail[:500]}")


def analyze_resume(extracted_text: str, job_description: str | None = None) -> dict[str, Any]:
    text = _normalize_resume_text(extracted_text)
    if _genai_client is not None:
        try:
            gemini_res = analyze_resume_with_gemini(text)
            if gemini_res.get("error"):
                return gemini_res

            domain = gemini_res.get("candidate_domain") or detect_domain(text)
            ats_eval = evaluate_ats_score(text, domain=domain, job_description=job_description)
            gemini_res["scoring_breakdown"] = {
                "overall_ats_score": gemini_res.get("ats_score", ats_eval["overall_ats_score"]),
                "general_quality_score": ats_eval["general_quality_score"],
                "skill_coverage_score": ats_eval["skill_coverage_score"],
                "practical_evidence_score": ats_eval["practical_evidence_score"],
                "job_compatibility_score": ats_eval.get("job_compatibility_score"),
                "weights": ats_eval["scoring_weights"],
            }
            gemini_res["evidence_explanations"] = ats_eval["evidence_explanations"]
            gemini_res["scoring_weights"] = ats_eval["scoring_weights"]
            gemini_res["disclaimer"] = ats_eval["disclaimer"]
            if ats_eval.get("job_specific_analysis"):
                gemini_res["job_specific_analysis"] = ats_eval["job_specific_analysis"]
            return gemini_res
        except Exception as exc:
            _log(f"[analyze] External Gemini service unavailable ({type(exc).__name__}: {exc}), cleanly falling back to local heuristic analyzer.")
    return _build_text_only_analysis(text, job_description=job_description)


_LOCATION_MARKERS = (
    "india", "bengaluru", "bangalore", "mumbai", "delhi", "chennai", "hyderabad",
    "pune", "kolkata", "noida", "gurugram", "gurgaon", "address", "street", "road",
    "pincode", "pin code", "karnataka", "maharashtra", "tamil nadu", "telangana",
    "andhra", "kerala", "gujarat", "rajasthan", "uttar pradesh", "west bengal",
)

_SECTION_HEADERS = (
    "experience", "education", "skills", "summary", "objective", "projects",
    "certifications", "contact", "profile", "resume", "curriculum vitae",
    "work history", "technical skills", "personal details", "professional",
    "employment", "achievements", "hobbies", "references", "declaration",
)


def _looks_like_location(line: str) -> bool:
    lower = line.lower().strip()
    if any(marker in lower for marker in _LOCATION_MARKERS):
        return True
    if re.search(r"\b\d{5,6}\b", line):
        return True
    if "," in line:
        parts = [p.strip().lower() for p in line.split(",") if p.strip()]
        if len(parts) >= 2 and any("india" in p or p in ("in", "ind") for p in parts):
            return True
        if len(parts) >= 2 and all(len(p) < 30 for p in parts):
            geo_words = ("city", "state", "district", "taluk", "region")
            if any(any(g in p for g in geo_words) for p in parts):
                return True
    return False


def _looks_like_person_name(line: str) -> bool:
    cleaned = line.strip()
    if not cleaned or len(cleaned) > 55:
        return False
    if "@" in cleaned or re.search(r"\d", cleaned):
        return False
    lower = cleaned.lower()
    if any(header in lower for header in _SECTION_HEADERS):
        return False
    if _looks_like_location(cleaned):
        return False
    if any(w in lower for w in ("college", "university", "institute", "school", "ltd", "pvt", "inc")):
        return False
    words = cleaned.split()
    if len(words) < 1 or len(words) > 5:
        return False
    if not all(re.match(r"^[A-Za-z][A-Za-z.'-]*$", word) for word in words):
        return False
    titled = sum(1 for word in words if word[0].isupper())
    if len(words) >= 2 and titled < max(1, len(words) - 1):
        return False
    return True


def _name_from_email(email: str) -> str | None:
    if not email or email.lower() == "not found":
        return None
    local = email.split("@")[0].lower()
    local = re.sub(r"\d+", " ", local)
    local = re.sub(r"(edu|gmail|yahoo|hotmail|outlook|mail|co|in)\b", "", local)
    local = re.sub(r"[._+\-]+", " ", local).strip()
    if len(local) < 2:
        return None
    parts = [p.capitalize() for p in local.split() if len(p) >= 2]
    if parts:
        return " ".join(parts[:4])
    return local.capitalize()


def _extract_candidate_details(resume_text: str) -> dict[str, str]:
    lines = [ln.strip() for ln in resume_text.splitlines() if ln.strip()]
    email_match = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", resume_text)
    phone_match = re.search(r"(?:\+91[\-\s]?)?[6-9]\d{9}", resume_text)
    email = email_match.group(0) if email_match else "Not found"
    phone = phone_match.group(0) if phone_match else "Not found"
    probable_name = "Not found"
    college = "Not found"

    for ln in lines[:15]:
        if _looks_like_person_name(ln):
            probable_name = ln
            break

    if probable_name == "Not found":
        email_name = _name_from_email(email)
        if email_name:
            probable_name = email_name

    for ln in lines:
        lower = ln.lower()
        if any(k in lower for k in ("college", "university", "institute", "school of")):
            college = ln
            break

    return {
        "candidate_name": probable_name,
        "candidate_email": email,
        "candidate_phone": phone,
        "candidate_college": college,
    }


def _build_jobs_payload(recommended_roles: list[str]) -> dict[str, Any]:
    jobs_by_role = fetch_jobs_for_roles(recommended_roles, JOBS_PER_ROLE)
    total = sum(len(v) for v in jobs_by_role.values())
    provider = jobs_provider_status()
    message = None
    if total == 0:
        if not provider["any_provider"]:
            message = (
                "Live job search APIs (JSearch / Adzuna) are not configured. "
                "Explore live openings directly on LinkedIn, Naukri, or Indeed using verified portal search links."
            )
        else:
            message = "No active India openings found matching your recommended roles right now. Try checking job portals directly."

    portal_links: dict[str, list[dict[str, str]]] = {}
    for r in recommended_roles:
        portal_links[r] = get_direct_portal_search_links(r)

    return {
        "jobs_by_role": jobs_by_role,
        "jobs": jobs_by_role.get(recommended_roles[0], []) if recommended_roles else [],
        "jobs_count": total,
        "jobs_provider": provider,
        "jobs_message": message,
        "portal_search_links": portal_links,
    }


@app.get("/")
def root(request: Request):
    accept = request.headers.get("accept", "")
    if "text/html" in accept and "application/json" not in accept and _spa_index_file and _spa_index_file.is_file():
        return FileResponse(str(_spa_index_file))
    return {
        "service": "Resume Analyzer",
        "tagline": "Career Intelligence Platform",
        "health": "/health",
        "ready": "/ready",
        "stats": "/api/platform-stats",
        "features": "/api/features",
        "analyze": "POST /analyze",
        "fetch_jobs": "POST /api/fetch-jobs",
        "explore_jobs": "GET /api/explore-jobs",
    }


@app.get("/api/explore-jobs")
def api_explore_jobs(role: str = "Software Engineer", domain: str = "IT & Software"):
    roles = [role]
    profile = DOMAIN_PROFILES.get(domain)
    if profile:
        for r in profile.get("roles", []):
            if r != role and len(roles) < 4:
                roles.append(r)
    else:
        for r in ["Full Stack Developer", "Data Analyst", "Cloud & DevOps Engineer"]:
            if r != role and len(roles) < 4:
                roles.append(r)
    payload = _build_jobs_payload(roles)
    return {"roles": roles, "domain": domain, **payload}


@app.get("/api/platform-stats")
def platform_stats():
    provider = jobs_provider_status()
    return {
        "total_analyses": _analysis_count,
        "domains_supported": len(DOMAIN_PROFILES),
        "job_roles_per_scan": MAX_JOB_ROLES,
        "jobs_per_role": JOBS_PER_ROLE,
        "live_jobs_enabled": provider["any_provider"],
        "jobs_provider": provider,
        "ai_provider": ai_provider_status(),
    }


@app.get("/api/features")
def platform_features():
    return {"features": PLATFORM_FEATURES}


@app.post("/api/auth/register")
def auth_register(body: RegisterRequest):
    try:
        user = auth_store.register_user(body.name, body.email, body.password, body.phone)
        return {"ok": True, "message": "Registered successfully. You can now sign in.", "user": user}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.post("/api/auth/login")
@app.post("/api/auth/signin")
def auth_login(body: LoginRequest):
    try:
        result = auth_store.login_user(body.email, body.password)
        return {"ok": True, "message": "Signed in successfully.", **result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e



@app.get("/api/auth/me")
def auth_me(authorization: str | None = Header(default=None)):
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    user = auth_store.get_user_by_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Not signed in.")
    return {"ok": True, "user": user}


@app.post("/api/auth/logout")
def auth_logout(authorization: str | None = Header(default=None)):
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    auth_store.logout(token)
    return {"ok": True, "message": "Signed out."}


@app.get("/health")
def health():
    ml_model, _ = matcher._load_ml_model()
    return {
        "status": "ok",
        "service": "Resume Analyzer",
        "version": "4.2",
        "environment": os.getenv("APP_ENV", os.getenv("ENVIRONMENT", "development")),
        "database_status": {
            "configured": database.is_database_configured(),
            "type": "relational_db" if database.is_database_configured() else "json_fallback",
        },
        "s3_storage_status": {
            "enabled": s3_storage.is_s3_enabled(),
        },
        "parser_status": {
            "pdfminer_ready": True,
            "pypdf_ready": True,
            "max_file_size_mb": MAX_PDF_FILE_SIZE_BYTES // (1024 * 1024),
        },
        "ml_model_status": {
            "loaded": ml_model is not None,
            "classes": list(ml_model.classes_) if ml_model is not None and hasattr(ml_model, "classes_") else [],
        },
        "jobs_provider": jobs_provider_status(),
        "ai_provider": ai_provider_status(),
    }


@app.get("/ready")
@app.get("/api/ready")
def readiness():
    ml_model, _ = matcher._load_ml_model()
    return {
        "status": "ready",
        "core_service": "ok",
        "parser_ready": True,
        "local_nlp_engine": "ready",
        "ml_model_loaded": ml_model is not None,
        "optional_integrations": {
            "gemini_ai": "configured" if _genai_client is not None else "unconfigured_using_local_fallback",
            "jsearch_jobs": "configured" if _is_real_key(RAPIDAPI_KEY) else "unconfigured",
            "adzuna_jobs": "configured" if (_is_real_key(ADZUNA_APP_ID) and _is_real_key(ADZUNA_APP_KEY)) else "unconfigured",
        },
    }


@app.get("/analyze")
def analyze_get_info():
    return {"detail": "Use POST with multipart form field 'file' (PDF) and optional 'job_description'.", "field": "file"}


@app.get("/api/analyze")
def analyze_get_info_compat():
    return analyze_get_info()


@app.post("/api/fetch-jobs")
def api_fetch_jobs(body: FetchJobsRequest):
    roles = [str(r).strip() for r in (body.recommended_roles or []) if str(r).strip()][:5]
    if not roles:
        raise HTTPException(status_code=400, detail="recommended_roles must be a non-empty list.")
    payload = _build_jobs_payload(roles)
    return {"recommended_roles": roles, **payload}


async def _analyze_impl(file: UploadFile, job_description: str | None = None) -> dict[str, Any]:
    # Prevent path traversal and sanitize filename
    clean_fname = Path(file.filename or "").name.lower()
    if not clean_fname.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF uploads are supported.")

    # Validate media type if provided
    valid_content_types = {
        "application/pdf",
        "application/x-pdf",
        "application/acrobat",
        "applications/vnd.pdf",
        "text/pdf",
        "application/octet-stream",
        "binary/octet-stream",
    }
    if file.content_type and file.content_type.lower() not in valid_content_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file content-type '{file.content_type}'. Expected PDF document.",
        )

    # Validate job description input length
    if job_description and len(job_description) > 25000:
        raise HTTPException(
            status_code=400,
            detail="Job description exceeds maximum allowed length (25,000 characters).",
        )

    # Read bytes into memory with size boundary enforcement to protect against memory exhaustion
    try:
        data = await file.read(MAX_PDF_FILE_SIZE_BYTES + 1)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read upload stream: {type(e).__name__}")

    if len(data) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty (0 bytes).")
    if len(data) > MAX_PDF_FILE_SIZE_BYTES:
        mb_limit = MAX_PDF_FILE_SIZE_BYTES // (1024 * 1024)
        raise HTTPException(status_code=413, detail=f"File exceeds maximum allowed size ({mb_limit}MB).")

    # Safe PDF parsing with independent fallback & explicit error categorization
    try:
        text = _normalize_resume_text(extract_pdf_text_from_bytes(data))
    except EmptyPDFError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except InvalidPDFSignatureError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ExcessivePageCountError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except EncryptedPDFError as e:
        return JSONResponse(status_code=422, content={"error": str(e), "code": "ENCRYPTED_PDF"})
    except ScannedPDFError as e:
        return JSONResponse(status_code=422, content={"error": str(e), "code": "SCANNED_PDF"})
    except (CorruptedPDFError, PDFProcessingError) as e:
        return JSONResponse(status_code=422, content={"error": str(e), "code": "CORRUPTED_PDF"})
    except Exception as e:
        _log(f"[parse] PDF extraction error: {type(e).__name__}: {e!r}")
        return JSONResponse(status_code=422, content={"error": INVALID_PDF_TEXT_ERROR, "code": "UNREADABLE_PDF"})

    if not text:
        return JSONResponse(status_code=422, content={"error": INVALID_PDF_TEXT_ERROR, "code": "EMPTY_EXTRACTED_TEXT"})

    try:
        ai = analyze_resume(text, job_description=job_description)
        if ai.get("error"):
            return JSONResponse(
                status_code=422,
                content={"error": ai["error"]},
            )

        from_gemini = ai.get("_source") == "gemini"
        role = str(ai.get("target_role") or ai.get("predicted_role") or "Graduate Trainee").strip()
        details = _extract_candidate_details(text)
        domain = str(ai.get("candidate_domain") or ai.get("detected_domain") or detect_domain(text)).strip()
        matched = sanitize_skills(
            [str(s).strip() for s in (ai.get("current_skills") or ai.get("matched_skills") or []) if str(s).strip()],
            details,
        )
        if not matched and not from_gemini:
            matched = sanitize_skills(extract_professional_skills(text, domain), details)
        skill_roles = infer_roles_from_skills(matched, domain)
        recommended_roles = merge_recommended_roles(
            [role] + [str(x).strip() for x in (ai.get("recommended_roles") or []) if str(x).strip()],
            skill_roles,
            limit=6,
        )
        if not recommended_roles:
            recommended_roles = [role]

        try:
            ats = int(ai.get("ats_score", 0))
        except (TypeError, ValueError):
            ats = 50
        ats = max(0, min(100, ats))

        missing = sanitize_skills(
            [str(s).strip() for s in (ai.get("missing_skills") or []) if str(s).strip()],
            details,
        )
        if not missing and not from_gemini:
            missing = compute_missing_skills(matched, domain)

        roadmap = ai.get("learning_roadmap") or _roadmap_strings_to_objects(ai.get("custom_roadmap") or [])
        jobs_payload = _build_jobs_payload(recommended_roles)
        _increment_analysis_count()

        # Privacy-conscious logging: log only non-sensitive operational metrics
        _log(f"[analyze] Successfully analyzed resume: {len(text)} chars, domain={domain}, target_role={role}, source={ai.get('_source')}")

        return {
            "ats_score": ats,
            "predicted_role": role,
            "target_role": role,
            "recommended_roles": recommended_roles,
            "matched_skills": matched,
            "current_skills": matched,
            "missing_skills": missing,
            "detected_domain": domain,
            "candidate_domain": domain,
            "custom_roadmap": ai.get("custom_roadmap") or [],
            "learning_roadmap": roadmap,
            "custom_suggestion": str(ai.get("custom_suggestion") or "").strip(),
            "career_suggestions": str(ai.get("career_suggestions") or ai.get("custom_suggestion") or "").strip(),
            "structured_suggestions": ai.get("structured_suggestions") or [],
            "scoring_breakdown": ai.get("scoring_breakdown"),
            "evidence_explanations": ai.get("evidence_explanations") or [],
            "scoring_weights": ai.get("scoring_weights") or {},
            "job_specific_analysis": ai.get("job_specific_analysis"),
            "disclaimer": ai.get("disclaimer"),
            "ml_predicted_role": ai.get("ml_predicted_role"),
            "analysis_source": ai.get("_source", "heuristic"),
            "keywords": matched[:15],
            "candidate_metadata": details,
            "candidate_name": details.get("candidate_name", "Not found"),
            "candidate_email": details.get("candidate_email", "Not found"),
            "candidate_phone": details.get("candidate_phone", "Not found"),
            "candidate_college": details.get("candidate_college", "Not found"),
            **jobs_payload,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[analyze] {type(e).__name__}: {e!r}")
        app_env = os.getenv("APP_ENV", os.getenv("ENVIRONMENT", "development")).lower()
        if app_env == "production":
            safe_detail = "Resume analysis encountered an internal error. Please try again or check document format."
        else:
            safe_detail = str(e).encode("ascii", "backslashreplace").decode("ascii")
            safe_detail = safe_detail[:500] if safe_detail else f"Analysis failed: {type(e).__name__}"
        raise HTTPException(
            status_code=500,
            detail=safe_detail,
        )


@app.post("/analyze")
async def analyze(
    file: UploadFile = File(..., description="PDF resume"),
    job_description: str | None = Form(default=None, description="Optional target job description"),
):
    return await _analyze_impl(file, job_description=job_description)


@app.post("/api/analyze")
async def analyze_compat(
    file: UploadFile = File(..., description="PDF resume"),
    job_description: str | None = Form(default=None, description="Optional target job description"),
):
    return await _analyze_impl(file, job_description=job_description)


# SPA catch-all route for single-container / unified full-stack hosting
if _spa_build_path and _spa_index_file and _spa_index_file.is_file():
    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa_fallback(full_path: str):
        if full_path.startswith(("api/", "health", "ready", "docs", "redoc", "openapi.json", "analyze")):
            raise HTTPException(status_code=404, detail="API endpoint not found")
        candidate = _spa_build_path / full_path
        if full_path and candidate.is_file():
            return FileResponse(str(candidate))
        return FileResponse(str(_spa_index_file))


_provider = jobs_provider_status()
if not _provider["any_provider"]:
    _log(
        "[jobs] No RAPIDAPI_KEY or ADZUNA_APP_ID/KEY in backend/.env — "
        "live India job cards will stay empty until configured."
    )

if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    reload = os.getenv("APP_ENV", os.getenv("ENVIRONMENT", "development")).lower() == "development"
    uvicorn.run("main:app", host=host, port=port, reload=reload)
