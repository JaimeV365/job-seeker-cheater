from __future__ import annotations

from src.models.job import Job
from src.sources.base import BaseConnector
from src.sources.remotive import RemotiveConnector
from src.sources.arbeitnow import ArbeitnowConnector
from src.sources.greenhouse import GreenhouseConnector


def get_all_connectors() -> list[BaseConnector]:
    return [
        RemotiveConnector(),
        ArbeitnowConnector(),
        GreenhouseConnector(),
    ]


def fetch_all_jobs(connectors: list[BaseConnector] | None = None) -> list[Job]:
    if connectors is None:
        connectors = get_all_connectors()

    all_jobs: list[Job] = []
    errors: list[str] = []

    for connector in connectors:
        try:
            jobs = connector.fetch_jobs()
            all_jobs.extend(jobs)
        except Exception as e:
            errors.append(f"{connector.name}: {e}")

    return all_jobs


def deduplicate_jobs(jobs: list[Job]) -> list[Job]:
    seen: dict[str, Job] = {}
    for job in jobs:
        key = job.dedup_key
        if key not in seen:
            seen[key] = job
    return list(seen.values())
