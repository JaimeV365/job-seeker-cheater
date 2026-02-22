from __future__ import annotations

import os
from datetime import datetime

from src.models.job import Job
from src.sources.base import BaseConnector
from src.utils.http_client import SafeHttpClient
from src.utils.text import clean_html

API_URL = "https://www.reed.co.uk/api/1.0/search"
DETAIL_URL = "https://www.reed.co.uk/api/1.0/jobs"


def _get_api_key() -> str | None:
    return os.environ.get("REED_API_KEY", "").strip() or None


class ReedConnector(BaseConnector):
    """Reed.co.uk -- UK's largest job board.  Free API (register at reed.co.uk/developers)."""

    name = "reed"

    def __init__(self, keywords: str = "", location: str = ""):
        self.keywords = keywords
        self.location = location

    @staticmethod
    def is_available() -> bool:
        return _get_api_key() is not None

    def fetch_jobs(self) -> list[Job]:
        api_key = _get_api_key()
        if not api_key:
            return []

        jobs: list[Job] = []
        results_to_skip = 0
        max_results = 200

        with SafeHttpClient() as client:
            while results_to_skip < max_results:
                params: dict = {
                    "resultsToTake": 100,
                    "resultsToSkip": results_to_skip,
                }
                if self.keywords:
                    params["keywords"] = self.keywords
                if self.location:
                    params["locationName"] = self.location

                resp = client.get(
                    API_URL,
                    params=params,
                    auth=(api_key, ""),
                )
                resp.raise_for_status()
                data = resp.json()

                results = data.get("results", [])
                if not results:
                    break

                for item in results:
                    published = None
                    if item.get("date"):
                        try:
                            published = datetime.fromisoformat(
                                str(item["date"]).replace("Z", "+00:00")
                            )
                        except (ValueError, TypeError):
                            pass

                    salary_min = item.get("minimumSalary")
                    salary_max = item.get("maximumSalary")
                    currency = item.get("currency", "GBP") or "GBP"

                    job_url = item.get("jobUrl", "")
                    if not job_url and item.get("jobId"):
                        job_url = f"https://www.reed.co.uk/jobs/{item['jobId']}"

                    jobs.append(
                        Job(
                            id=f"reed-{item.get('jobId', '')}",
                            title=item.get("jobTitle", ""),
                            company=item.get("employerName", ""),
                            description=clean_html(item.get("jobDescription", "")),
                            url=job_url,
                            source="reed",
                            location=item.get("locationName", ""),
                            remote_type="",
                            salary_min=float(salary_min) if salary_min else None,
                            salary_max=float(salary_max) if salary_max else None,
                            salary_currency=currency,
                            published_at=published,
                        )
                    )

                if len(results) < 100:
                    break
                results_to_skip += 100

        return jobs
