from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Job:
    id: str
    title: str
    company: str
    description: str
    url: str
    source: str
    location: str = ""
    remote_type: str = ""  # "remote", "hybrid", "onsite", ""
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str = ""
    seniority: str = ""
    tags: list[str] = field(default_factory=list)
    published_at: datetime | None = None
    fetched_at: datetime = field(default_factory=_utcnow)

    @property
    def display_salary(self) -> str:
        if self.salary_min and self.salary_max:
            cur = self.salary_currency or "USD"
            return f"{cur} {self.salary_min:,.0f} - {self.salary_max:,.0f}"
        if self.salary_min:
            cur = self.salary_currency or "USD"
            return f"{cur} {self.salary_min:,.0f}+"
        return ""

    @property
    def dedup_key(self) -> str:
        title_norm = self.title.lower().strip()
        company_norm = self.company.lower().strip()
        return f"{company_norm}::{title_norm}"
