from __future__ import annotations

from datetime import datetime

from src.models.job import Job
from src.sources.base import BaseConnector
from src.utils.http_client import SafeHttpClient
from src.utils.text import clean_html

API_URL = "https://remotive.com/api/remote-jobs"


class RemotiveConnector(BaseConnector):
    name = "remotive"

    def __init__(self, search: str = ""):
        self.search = search

    def fetch_jobs(self) -> list[Job]:
        params = {}
        if self.search:
            params["search"] = self.search

        with SafeHttpClient() as client:
            resp = client.get(API_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

        jobs: list[Job] = []
        for item in data.get("jobs", []):
            published = None
            if item.get("publication_date"):
                try:
                    published = datetime.fromisoformat(
                        item["publication_date"].replace("Z", "+00:00")
                    )
                except (ValueError, TypeError):
                    pass

            tags = [t.strip().lower() for t in item.get("tags", []) if t]

            salary_text = item.get("salary", "")
            salary_min, salary_max = _parse_salary(salary_text)

            jobs.append(
                Job(
                    id=f"remotive-{item['id']}",
                    title=item.get("title", ""),
                    company=item.get("company_name", ""),
                    description=clean_html(item.get("description", "")),
                    url=item.get("url", ""),
                    source="remotive",
                    location=item.get("candidate_required_location", "Worldwide"),
                    remote_type="remote",
                    salary_min=salary_min,
                    salary_max=salary_max,
                    tags=tags,
                    published_at=published,
                )
            )
        return jobs


def _parse_salary(text: str) -> tuple[float | None, float | None]:
    if not text:
        return None, None
    import re

    numbers = re.findall(r"[\d,]+", text.replace(",", ""))
    nums = []
    for n in numbers:
        try:
            val = float(n.replace(",", ""))
            if val > 100:
                nums.append(val)
        except ValueError:
            continue
    if len(nums) >= 2:
        return min(nums), max(nums)
    if len(nums) == 1:
        return nums[0], None
    return None, None
