from __future__ import annotations

from datetime import datetime
from pathlib import Path

import yaml

from src.models.job import Job
from src.sources.base import BaseConnector
from src.utils.http_client import SafeHttpClient
from src.utils.text import clean_html

POSTINGS_API = "https://api.lever.co/v0/postings/{site}"


def load_company_slugs() -> list[str]:
    config_path = Path(__file__).resolve().parent.parent.parent / "data" / "lever_companies.yaml"
    if not config_path.exists():
        return []
    with open(config_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("companies", []) if data else []


class LeverConnector(BaseConnector):
    """Lever -- free, no auth. Many tech companies use Lever for their career boards."""

    name = "lever"

    def __init__(self, slugs: list[str] | None = None):
        self.slugs = slugs or load_company_slugs()

    def fetch_jobs(self) -> list[Job]:
        all_jobs: list[Job] = []

        with SafeHttpClient() as client:
            for slug in self.slugs:
                try:
                    url = POSTINGS_API.format(site=slug)
                    resp = client.get(url, params={"mode": "json"})
                    if resp.status_code == 404:
                        continue
                    resp.raise_for_status()
                    postings = resp.json()
                except Exception:
                    continue

                if not isinstance(postings, list):
                    continue

                for item in postings:
                    published = None
                    if item.get("createdAt"):
                        try:
                            ts = item["createdAt"]
                            if isinstance(ts, (int, float)):
                                published = datetime.fromtimestamp(ts / 1000, tz=__import__("datetime").timezone.utc)
                            else:
                                published = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
                        except (ValueError, TypeError, OSError):
                            pass

                    categories = item.get("categories", {}) or {}
                    location = categories.get("location", "") or ""
                    commitment = categories.get("commitment", "") or ""
                    team = categories.get("team", "") or ""
                    department = categories.get("department", "") or ""

                    tags = [t.lower() for t in [commitment, team, department] if t]

                    description_plain = item.get("descriptionPlain", "")
                    if not description_plain:
                        description_plain = clean_html(item.get("description", "") or "")

                    lists_section = ""
                    for lst in item.get("lists", []):
                        header = lst.get("text", "")
                        content = lst.get("content", "")
                        if content:
                            lists_section += f"\n{header}\n{clean_html(content)}"

                    full_description = description_plain
                    if lists_section:
                        full_description += lists_section

                    apply_url = item.get("hostedUrl", "") or item.get("applyUrl", "")

                    all_jobs.append(
                        Job(
                            id=f"lever-{slug}-{item.get('id', '')}",
                            title=item.get("text", ""),
                            company=slug.replace("-", " ").title(),
                            description=full_description.strip(),
                            url=apply_url,
                            source=f"lever:{slug}",
                            location=location,
                            tags=tags,
                            published_at=published,
                        )
                    )

        return all_jobs
