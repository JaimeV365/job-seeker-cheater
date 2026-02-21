from __future__ import annotations

from src.models.job import Job


def deduplicate(jobs: list[Job]) -> list[Job]:
    seen: dict[str, Job] = {}
    for job in jobs:
        key = job.dedup_key
        if key in seen:
            existing = seen[key]
            if _prefer_new(job, existing):
                seen[key] = job
        else:
            seen[key] = job
    return list(seen.values())


def _prefer_new(candidate: Job, existing: Job) -> bool:
    if candidate.description and not existing.description:
        return True
    if candidate.salary_min is not None and existing.salary_min is None:
        return True
    return False
