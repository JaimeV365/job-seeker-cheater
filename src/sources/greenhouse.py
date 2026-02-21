from __future__ import annotations

from datetime import datetime
from pathlib import Path

import yaml

from src.models.job import Job
from src.sources.base import BaseConnector
from src.utils.http_client import SafeHttpClient
from src.utils.text import clean_html

BOARD_API = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"


def load_company_slugs() -> list[str]:
    config_path = Path(__file__).resolve().parent.parent.parent / "data" / "greenhouse_companies.yaml"
    if not config_path.exists():
        return []
    with open(config_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("companies", [])


class GreenhouseConnector(BaseConnector):
    name = "greenhouse"

    def __init__(self, slugs: list[str] | None = None):
        self.slugs = slugs or load_company_slugs()

    def fetch_jobs(self) -> list[Job]:
        all_jobs: list[Job] = []

        with SafeHttpClient() as client:
            for slug in self.slugs:
                try:
                    url = BOARD_API.format(slug=slug)
                    resp = client.get(url, params={"content": "true"})
                    if resp.status_code == 404:
                        continue
                    resp.raise_for_status()
                    data = resp.json()
                except Exception:
                    continue

                for item in data.get("jobs", []):
                    published = None
                    if item.get("updated_at"):
                        try:
                            published = datetime.fromisoformat(
                                item["updated_at"].replace("Z", "+00:00")
                            )
                        except (ValueError, TypeError):
                            pass

                    location_parts = []
                    for office in item.get("offices", []):
                        loc = office.get("name", "")
                        if loc:
                            location_parts.append(loc)
                    location = ", ".join(location_parts) if location_parts else ""

                    dept_parts = []
                    for dept in item.get("departments", []):
                        d = dept.get("name", "")
                        if d:
                            dept_parts.append(d.lower())

                    description = ""
                    content = item.get("content", "")
                    if content:
                        description = clean_html(content)

                    apply_url = item.get("absolute_url", "")

                    all_jobs.append(
                        Job(
                            id=f"greenhouse-{slug}-{item['id']}",
                            title=item.get("title", ""),
                            company=slug.replace("-", " ").title(),
                            description=description,
                            url=apply_url,
                            source=f"greenhouse:{slug}",
                            location=location,
                            tags=dept_parts,
                            published_at=published,
                        )
                    )

        return all_jobs
