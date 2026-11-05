from __future__ import annotations

# ==============================================================================
# TECH STACK: [Matcher & Multi-Dimensional Profile Evaluator]
# Evaluates Skills, Experience, Education & CGPA, Projects & Other Activities,
# with semantic / TF-IDF similarity, ML role classification, and ATS scoring.
# ==============================================================================
import os
import re
from typing import Any

# Optional high-efficiency SentenceTransformer loader
_transformer_model = None
try:
    from sentence_transformers import SentenceTransformer, util
    _transformer_model = SentenceTransformer('all-MiniLM-L6-v2')
except Exception:
    _transformer_model = None

from skills import (
    extract_comprehensive_skills,
    extract_education_details,
    extract_experience_details,
    extract_projects_and_activities,
    generate_multi_skill_career_tracks,
    calculate_score_breakdown,
    evaluate_ats_score,
    detect_domain,
)

COMMON_SKILLS = [
    "c", "c++", "c#", "java", "python", "javascript", "typescript",
    "react", "node", "express", "sql", "mongodb", "postgresql", "redis",
    "aws", "docker", "kubernetes", "git", "linux", "html", "css",
    "data structures", "machine learning", "deep learning", "data analysis",
    "pandas", "numpy", "spring boot", "django", "fastapi"
]

SKILL_WEIGHTS = {
    # Core Languages
    "c": 1.4,
    "c++": 1.5,
    "c#": 1.4,
    "java": 1.5,
    "python": 1.5,
    "javascript": 1.4,
    "typescript": 1.4,
    "sql": 1.3,
    # Frameworks & Platforms
    "spring boot": 1.5,
    "react": 1.4,
    "node": 1.3,
    "django": 1.3,
    "fastapi": 1.3,
    # Cloud & DevOps
    "aws": 1.4,
    "docker": 1.3,
    "kubernetes": 1.4,
    "ci/cd": 1.2,
    "linux": 1.2,
    # AI & Data
    "machine learning": 1.8,
    "deep learning": 1.8,
    "data analysis": 1.4,
    "data structures": 1.6,
    "mongodb": 1.2,
    "postgresql": 1.2,
}

# ==============================================================================
# TECH STACK: [Scikit-Learn ML Role Model] - Safe Loading & Fallback
# ==============================================================================
_ml_role_model: Any = None
_ml_role_vectorizer: Any = None
_ml_model_attempted: bool = False


def _load_ml_model():
    global _ml_role_model, _ml_role_vectorizer, _ml_model_attempted
    if _ml_model_attempted:
        return _ml_role_model, _ml_role_vectorizer
    _ml_model_attempted = True
    try:
        import joblib
        base_dir = os.getenv("MODEL_DIR") or os.path.dirname(os.path.abspath(__file__))
        model_path = os.path.join(base_dir, "role_model.pkl")
        vec_path = os.path.join(base_dir, "role_vectorizer.pkl")
        if os.path.isfile(model_path) and os.path.isfile(vec_path):
            _ml_role_model = joblib.load(model_path)
            _ml_role_vectorizer = joblib.load(vec_path)
    except Exception:
        _ml_role_model = None
        _ml_role_vectorizer = None
    return _ml_role_model, _ml_role_vectorizer


def predict_role_with_ml(text: str) -> str | None:
    """
    Predict job role using the trained TF-IDF Logistic Regression ML model.
    Returns None safely if model artifacts are missing or unreadable.
    """
    model, vectorizer = _load_ml_model()
    if model is None or vectorizer is None:
        return None
    try:
        cleaned = text.strip()
        if not cleaned:
            return None
        features = vectorizer.transform([cleaned])
        predicted = model.predict(features)
        if len(predicted) > 0 and predicted[0]:
            role = str(predicted[0]).strip()
            # Validate that predicted role is in valid trained classes
            if hasattr(model, "classes_") and role in model.classes_:
                return role
    except Exception:
        pass
    return None


def calculate_similarity(resume_text: str, job_description: str) -> float:
    """
    Calculate semantic similarity score (0-100) between resume and job description.
    Uses SentenceTransformer if available, or token-level Jaccard similarity.
    """
    if _transformer_model is not None:
        try:
            embeddings = _transformer_model.encode([resume_text, job_description])
            similarity = util.cos_sim(embeddings[0], embeddings[1])
            return round(float(similarity[0][0]) * 100, 2)
        except Exception:
            pass

    # High-accuracy token fallback
    tokens_r = set(re.findall(r"\b[a-zA-Z0-9+#]{2,}\b", resume_text.lower()))
    tokens_j = set(re.findall(r"\b[a-zA-Z0-9+#]{2,}\b", job_description.lower()))
    if not tokens_j:
        return 50.0
    intersection = tokens_r & tokens_j
    union = tokens_r | tokens_j
    jaccard = len(intersection) / len(union) if union else 0.0
    scaled = min(98.0, 30.0 + jaccard * 120.0)
    return round(scaled, 2)


def skill_gap_analysis(resume_text: str, job_description: str) -> dict[str, Any]:
    """
    Perform deep skill gap analysis identifying matched skills, missing skills,
    and individual skill match scores.
    """
    resume_skills_data = extract_comprehensive_skills(resume_text)
    jd_skills_data = extract_comprehensive_skills(job_description)

    resume_all = {s.lower(): s for s in resume_skills_data["all_skills"]}
    jd_all = {s.lower(): s for s in jd_skills_data["all_skills"]}

    matched_keys = set(resume_all.keys()) & set(jd_all.keys())
    missing_keys = set(jd_all.keys()) - set(resume_all.keys())

    matched_skills = [jd_all[k] for k in matched_keys]
    missing_skills = [jd_all[k] for k in missing_keys]

    skill_scores: dict[str, float] = {}
    for k, skill_name in jd_all.items():
        if k in matched_keys:
            skill_scores[skill_name] = 100.0
        else:
            if _transformer_model is not None:
                try:
                    s_emb = _transformer_model.encode(skill_name)
                    r_emb = _transformer_model.encode(resume_text[:2000])
                    sim = util.cos_sim(s_emb, r_emb)
                    skill_scores[skill_name] = round(float(sim[0][0]) * 100, 2)
                    continue
                except Exception:
                    pass
            skill_scores[skill_name] = 20.0

    return {
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "skill_match_scores": skill_scores,
    }


def weighted_skill_match(resume_skills: list[str], job_description: str) -> tuple[float, list[str]]:
    """
    Calculate weighted skill match score against a job description.
    """
    jd_lower = job_description.lower()
    resume_lower = {s.lower() for s in resume_skills}

    total_weight = 0.0
    matched_weight = 0.0
    matched_skills = []

    for skill, weight in SKILL_WEIGHTS.items():
        if skill in jd_lower:
            total_weight += weight
            if skill in resume_lower or any(skill in r for r in resume_lower):
                matched_weight += weight
                matched_skills.append(skill.title())

    if total_weight == 0.0:
        return 75.0, resume_skills[:4]

    score = (matched_weight / total_weight) * 100
    return round(score, 2), matched_skills


def generate_learning_roadmap(missing_skills: list[str]) -> list[str]:
    """
    Generate actionable step-by-step career milestone roadmap for missing skills.
    """
    roadmap: list[str] = []
    for skill in missing_skills:
        sl = skill.lower()
        if "c++" in sl or "c " in sl:
            roadmap.append("Master modern C++ (C++17/20), STL containers, smart pointers, and multithreading.")
        elif "python" in sl:
            roadmap.append("Complete advanced Python: OOP, asynchronous programming, and REST API development (FastAPI/Django).")
        elif "java" in sl or "spring" in sl:
            roadmap.append("Build a production-grade Spring Boot microservices backend with JPA & PostgreSQL.")
        elif "react" in sl:
            roadmap.append("Develop a full-stack responsive web application with React 19, state management, and API integration.")
        elif "aws" in sl or "cloud" in sl:
            roadmap.append("Earn the AWS Certified Cloud Practitioner / Solutions Architect Associate certification.")
        elif "docker" in sl or "kubernetes" in sl:
            roadmap.append("Containerize multi-container web apps with Docker and deploy them on a Kubernetes cluster.")
        elif "sql" in sl:
            roadmap.append("Practice complex SQL queries: window functions, index optimization, and relational database schema design.")
        elif "machine learning" in sl or "ai" in sl:
            roadmap.append("Implement end-to-end ML models: data preprocessing with Pandas, model training with Scikit-Learn/PyTorch, and FastAPI deployment.")
        elif "data structures" in sl:
            roadmap.append("Solve 50+ core DSA problems (Trees, Graphs, Dynamic Programming) on LeetCode/HackerRank.")
        else:
            roadmap.append(f"Deepen practical hands-on experience and build a portfolio project demonstrating {skill}.")
    return roadmap


def evaluate_full_candidate_profile(
    resume_text: str,
    job_description: str | None = None,
) -> dict[str, Any]:
    """
    Comprehensive multi-dimensional evaluator analyzing:
    1. Skills across IT and Non-IT domains
    2. Experience (years, seniority tier, internships)
    3. Education & CGPA/GPA/CPA (degree, grades, academic standing)
    4. Projects & Extracurricular Activities (projects, certifications, hackathons, open source)
    5. Multi-Skill Career Tracks across all strong skill sets
    6. Transparent, explainable ATS evaluation breakdown
    """
    domain = detect_domain(resume_text)
    skills_data = extract_comprehensive_skills(resume_text, domain=domain)
    edu_data = extract_education_details(resume_text)
    exp_data = extract_experience_details(resume_text)
    proj_data = extract_projects_and_activities(resume_text)

    # Calculate explainable ATS evaluation
    ats_evaluation = evaluate_ats_score(
        resume_text,
        domain=domain,
        job_description=job_description,
    )

    career_tracks = generate_multi_skill_career_tracks(
        matched_skills=skills_data["all_skills"],
        experience_info=exp_data,
        domain=domain,
    )

    # Safe ML model prediction
    ml_pred = predict_role_with_ml(resume_text)
    recommended_roles = career_tracks["recommended_roles"]
    if ml_pred and ml_pred not in recommended_roles:
        recommended_roles = [ml_pred] + recommended_roles

    return {
        "domain": domain,
        "skills_data": skills_data,
        "education_data": edu_data,
        "experience_data": exp_data,
        "projects_data": proj_data,
        "career_tracks": career_tracks["career_tracks"],
        "recommended_roles": recommended_roles,
        "ml_predicted_role": ml_pred,
        "ats_evaluation": ats_evaluation,
        "score_breakdown": {
            "overall_ats_score": ats_evaluation["overall_ats_score"],
            "general_quality_score": ats_evaluation["general_quality_score"],
            "skill_coverage_score": ats_evaluation["skill_coverage_score"],
            "practical_evidence_score": ats_evaluation["practical_evidence_score"],
            "job_compatibility_score": ats_evaluation.get("job_compatibility_score"),
            "weights": ats_evaluation["scoring_weights"],
        },
        "overall_ats_score": ats_evaluation["overall_ats_score"],
    }


def predict_job_role(resume_text: str) -> str:
    """
    Predict primary recommended job role using trained ML classifier with fallback
    to multi-dimensional career tracks evaluator.
    """
    ml_role = predict_role_with_ml(resume_text)
    if ml_role:
        return ml_role
    eval_result = evaluate_full_candidate_profile(resume_text)
    roles = eval_result["recommended_roles"]
    return roles[0] if roles else "Software Developer"
