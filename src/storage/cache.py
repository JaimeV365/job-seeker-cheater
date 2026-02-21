from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from src.models.job import Job

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "job_cache.db"
DEFAULT_TTL_SECONDS = 3600


class JobCache:
    """SQLite cache for job listings only. Never stores personal data."""

    def __init__(self, db_path: Path | str = DEFAULT_DB_PATH, ttl: int = DEFAULT_TTL_SECONDS):
        self.db_path = Path(db_path)
        self.ttl = ttl
        self._ensure_table()

    def _conn(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        return sqlite3.connect(str(self.db_path))

    def _ensure_table(self) -> None:
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    cached_at REAL NOT NULL
                )
            """)

    def get_jobs(self, source: str) -> list[Job] | None:
        cutoff = time.time() - self.ttl
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT data FROM jobs WHERE id LIKE ? AND cached_at > ?",
                (f"{source}-%", cutoff),
            ).fetchall()
        if not rows:
            return None
        return [_dict_to_job(json.loads(row[0])) for row in rows]

    def store_jobs(self, jobs: list[Job]) -> None:
        with self._conn() as conn:
            now = time.time()
            for job in jobs:
                conn.execute(
                    "INSERT OR REPLACE INTO jobs (id, data, cached_at) VALUES (?, ?, ?)",
                    (job.id, json.dumps(_job_to_dict(job)), now),
                )

    def clear(self) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM jobs")

    def clear_expired(self) -> int:
        cutoff = time.time() - self.ttl
        with self._conn() as conn:
            cursor = conn.execute("DELETE FROM jobs WHERE cached_at < ?", (cutoff,))
            return cursor.rowcount


def _job_to_dict(job: Job) -> dict:
    return {
        "id": job.id,
        "title": job.title,
        "company": job.company,
        "description": job.description,
        "url": job.url,
        "source": job.source,
        "location": job.location,
        "remote_type": job.remote_type,
        "salary_min": job.salary_min,
        "salary_max": job.salary_max,
        "salary_currency": job.salary_currency,
        "seniority": job.seniority,
        "tags": job.tags,
        "published_at": job.published_at.isoformat() if job.published_at else None,
    }


def _dict_to_job(d: dict) -> Job:
    from datetime import datetime
    published = None
    if d.get("published_at"):
        try:
            published = datetime.fromisoformat(d["published_at"])
        except (ValueError, TypeError):
            pass
    return Job(
        id=d["id"],
        title=d["title"],
        company=d["company"],
        description=d["description"],
        url=d["url"],
        source=d["source"],
        location=d.get("location", ""),
        remote_type=d.get("remote_type", ""),
        salary_min=d.get("salary_min"),
        salary_max=d.get("salary_max"),
        salary_currency=d.get("salary_currency", ""),
        seniority=d.get("seniority", ""),
        tags=d.get("tags", []),
        published_at=published,
    )
