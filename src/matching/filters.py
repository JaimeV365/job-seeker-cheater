from __future__ import annotations

from src.models.job import Job
from src.models.preferences import Preferences


def apply_hard_filters(jobs: list[Job], prefs: Preferences) -> list[Job]:
    filtered = jobs

    if prefs.remote_types:
        filtered = [j for j in filtered if _matches_remote(j, prefs.remote_types)]

    if prefs.locations:
        filtered = [j for j in filtered if _matches_location(j, prefs.locations, prefs.country)]

    if prefs.min_salary is not None:
        filtered = [j for j in filtered if _meets_salary(j, prefs.min_salary)]

    if prefs.seniority_levels:
        filtered = [j for j in filtered if _matches_seniority(j, prefs.seniority_levels)]

    return filtered


def _matches_remote(job: Job, wanted: list[str]) -> bool:
    if not wanted:
        return True
    job_remote = job.remote_type.lower()
    job_loc = job.location.lower()

    for w in wanted:
        if w == "remote" and (job_remote == "remote" or "remote" in job_loc):
            return True
        if w == "hybrid" and job_remote in ("hybrid", "remote"):
            return True
        if w == "onsite" and job_remote in ("onsite", ""):
            return True
    return False


def _matches_location(job: Job, locations: list[str], country: str = "") -> bool:
    if not locations:
        return True
    job_loc = job.location.lower()
    if not job_loc or job_loc in ("worldwide", "anywhere", "global"):
        return True

    loc_match = any(loc.lower() in job_loc for loc in locations)
    if loc_match and country:
        country_lower = country.lower()
        country_aliases = _country_aliases(country_lower)
        if any(alias in job_loc for alias in country_aliases):
            return True
        # City matched but no country info in listing -- include it anyway
        return loc_match
    return loc_match


def _country_aliases(country: str) -> list[str]:
    aliases = {
        "uk": ["uk", "united kingdom", "england", "scotland", "wales", "britain"],
        "us": ["us", "usa", "united states", "america"],
        "de": ["germany", "deutschland", "de"],
        "ca": ["canada", "ca"],
        "fr": ["france", "fr"],
        "es": ["spain", "españa", "es"],
        "au": ["australia", "au"],
        "nl": ["netherlands", "holland", "nl"],
        "ie": ["ireland", "ie"],
        "se": ["sweden", "se"],
    }
    return aliases.get(country.lower(), [country.lower()])


def _meets_salary(job: Job, min_salary: float) -> bool:
    if job.salary_max is not None:
        return job.salary_max >= min_salary
    if job.salary_min is not None:
        return job.salary_min >= min_salary
    return True


def _matches_seniority(job: Job, wanted: list[str]) -> bool:
    if not wanted:
        return True
    title_lower = job.title.lower()

    seniority_keywords = {
        "junior": ["junior", "jr", "entry", "graduate", "intern"],
        "mid": ["mid", "intermediate"],
        "senior": ["senior", "sr"],
        "lead": ["lead", "principal", "staff"],
        "executive": ["director", "vp", "head", "chief", "cto", "cfo", "ceo"],
    }

    for level in wanted:
        keywords = seniority_keywords.get(level.lower(), [level.lower()])
        if any(kw in title_lower for kw in keywords):
            return True

    # No seniority keyword found in title -- include if title is ambiguous
    has_any_seniority = any(
        kw in title_lower
        for kws in seniority_keywords.values()
        for kw in kws
    )
    return not has_any_seniority
