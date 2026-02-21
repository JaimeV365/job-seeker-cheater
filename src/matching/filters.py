from __future__ import annotations

from src.models.job import Job
from src.models.preferences import Preferences


def apply_hard_filters(jobs: list[Job], prefs: Preferences) -> list[Job]:
    filtered = jobs

    if prefs.remote_type:
        filtered = [j for j in filtered if _matches_remote(j, prefs.remote_type)]

    if prefs.locations:
        filtered = [j for j in filtered if _matches_location(j, prefs.locations)]

    if prefs.min_salary is not None:
        filtered = [j for j in filtered if _meets_salary(j, prefs.min_salary)]

    if prefs.seniority:
        filtered = [j for j in filtered if _matches_seniority(j, prefs.seniority)]

    return filtered


def _matches_remote(job: Job, wanted: str) -> bool:
    if not wanted:
        return True
    if wanted == "remote":
        return job.remote_type == "remote" or "remote" in job.location.lower()
    if wanted == "hybrid":
        return job.remote_type in ("hybrid", "remote", "")
    if wanted == "onsite":
        return job.remote_type in ("onsite", "")
    return True


def _matches_location(job: Job, locations: list[str]) -> bool:
    if not locations:
        return True
    job_loc = job.location.lower()
    if not job_loc or job_loc in ("worldwide", "anywhere", "global"):
        return True
    return any(loc.lower() in job_loc for loc in locations)


def _meets_salary(job: Job, min_salary: float) -> bool:
    if job.salary_max is not None:
        return job.salary_max >= min_salary
    if job.salary_min is not None:
        return job.salary_min >= min_salary
    # No salary data -- include by default to avoid false negatives
    return True


def _matches_seniority(job: Job, wanted: str) -> bool:
    if not wanted:
        return True
    title_lower = job.title.lower()
    seniority_lower = wanted.lower()

    seniority_keywords = {
        "junior": ["junior", "jr", "entry", "graduate", "intern"],
        "mid": ["mid", "intermediate"],
        "senior": ["senior", "sr"],
        "lead": ["lead", "principal", "staff"],
        "executive": ["director", "vp", "head", "chief", "cto", "cfo", "ceo"],
    }

    keywords = seniority_keywords.get(seniority_lower, [seniority_lower])
    return any(kw in title_lower for kw in keywords) or not any(
        kw in title_lower
        for kws in seniority_keywords.values()
        for kw in kws
    )
