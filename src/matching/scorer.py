from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from src.models.job import Job
from src.models.profile import Profile
from src.models.preferences import Preferences
from src.utils.text import normalize_for_matching

WEIGHTS = {
    "text_similarity": 0.35,
    "skill_overlap": 0.30,
    "preference_fit": 0.20,
    "recency": 0.15,
}


def score_jobs(
    jobs: list[Job],
    profile: Profile,
    prefs: Preferences,
) -> list[tuple[Job, float, dict[str, float]]]:
    if not jobs or profile.is_empty:
        return [(j, 0.0, {}) for j in jobs]

    cv_text = normalize_for_matching(profile.raw_text)
    job_texts = [normalize_for_matching(j.title + " " + j.description) for j in jobs]

    text_sims = _compute_text_similarities(cv_text, job_texts)
    profile_skills = profile.skills_lower()

    results: list[tuple[Job, float, dict[str, float]]] = []

    for i, job in enumerate(jobs):
        scores: dict[str, float] = {}

        scores["text_similarity"] = text_sims[i]
        scores["skill_overlap"] = _skill_overlap_score(job, profile_skills)
        scores["preference_fit"] = _preference_fit_score(job, prefs)
        scores["recency"] = _recency_score(job)

        total = sum(WEIGHTS[k] * scores[k] for k in WEIGHTS)
        results.append((job, total, scores))

    results.sort(key=lambda x: x[1], reverse=True)
    return results


def _compute_text_similarities(cv_text: str, job_texts: list[str]) -> list[float]:
    if not cv_text.strip() or not job_texts:
        return [0.0] * len(job_texts)

    corpus = [cv_text] + job_texts
    try:
        vectorizer = TfidfVectorizer(max_features=5000, stop_words="english")
        tfidf_matrix = vectorizer.fit_transform(corpus)
        sims = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:]).flatten()
        return [float(s) for s in sims]
    except ValueError:
        return [0.0] * len(job_texts)


def _skill_overlap_score(job: Job, profile_skills: set[str]) -> float:
    if not profile_skills:
        return 0.0
    job_tags = {t.lower() for t in job.tags}
    job_desc_lower = job.description.lower()

    matches = 0
    for skill in profile_skills:
        if skill in job_tags or skill in job_desc_lower:
            matches += 1

    if not profile_skills:
        return 0.0
    return min(matches / len(profile_skills), 1.0)


def _preference_fit_score(job: Job, prefs: Preferences) -> float:
    score = 0.0
    checks = 0

    if prefs.target_titles:
        checks += 1
        title_lower = job.title.lower()
        if any(t.lower() in title_lower for t in prefs.target_titles):
            score += 1.0

    if prefs.remote_type:
        checks += 1
        if job.remote_type == prefs.remote_type:
            score += 1.0
        elif job.remote_type == "remote" and prefs.remote_type in ("hybrid", ""):
            score += 0.5

    if prefs.locations:
        checks += 1
        job_loc = job.location.lower()
        if any(loc.lower() in job_loc for loc in prefs.locations):
            score += 1.0
        elif job_loc in ("worldwide", "anywhere", "global", ""):
            score += 0.7

    if prefs.industries:
        checks += 1
        job_text = (job.title + " " + job.description + " " + " ".join(job.tags)).lower()
        if any(ind.lower() in job_text for ind in prefs.industries):
            score += 1.0

    return score / max(checks, 1)


def _recency_score(job: Job) -> float:
    if not job.published_at:
        return 0.3

    now = datetime.now(timezone.utc)
    pub = job.published_at
    if pub.tzinfo is None:
        pub = pub.replace(tzinfo=timezone.utc)

    age = now - pub
    if age < timedelta(days=1):
        return 1.0
    if age < timedelta(days=3):
        return 0.9
    if age < timedelta(days=7):
        return 0.7
    if age < timedelta(days=14):
        return 0.5
    if age < timedelta(days=30):
        return 0.3
    return 0.1
