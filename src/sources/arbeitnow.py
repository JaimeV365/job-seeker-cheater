from __future__ import annotations

from datetime import datetime, timezone

from src.models.job import Job
from src.sources.base import BaseConnector
from src.utils.http_client import SafeHttpClient
from src.utils.text import clean_html

API_URL = "https://www.arbeitnow.com/api/job-board-api"


class ArbeitnowConnector(BaseConnector):
    name = "arbeitnow"

    def fetch_jobs(self) -> list[Job]:
        all_jobs: list[Job] = []
        page = 1
        max_pages = 3

        with SafeHttpClient() as client:
            while page <= max_pages:
                resp = client.get(API_URL, params={"page": page})
                resp.raise_for_status()
                data = resp.json()

                items = data.get("data", [])
                if not items:
                    break

                for item in items:
                    published = None
                    if item.get("created_at"):
                        try:
                            ts = item["created_at"]
                            if isinstance(ts, (int, float)):
                                published = datetime.fromtimestamp(ts, tz=timezone.utc)
                            else:
                                published = datetime.fromisoformat(str(ts))
                        except (ValueError, TypeError, OSError):
                            pass

                    tags = [t.strip().lower() for t in item.get("tags", []) if t]
                    remote_flag = item.get("remote", False)
                    remote_type = "remote" if remote_flag else ""

                    all_jobs.append(
                        Job(
                            id=f"arbeitnow-{item.get('slug', item.get('url', ''))}",
                            title=item.get("title", ""),
                            company=item.get("company_name", ""),
                            description=clean_html(item.get("description", "")),
                            url=item.get("url", ""),
                            source="arbeitnow",
                            location=item.get("location", ""),
                            remote_type=remote_type,
                            tags=tags,
                            published_at=published,
                        )
                    )

                if not data.get("links", {}).get("next"):
                    break
                page += 1

        return all_jobs
