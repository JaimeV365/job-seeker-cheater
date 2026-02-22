from __future__ import annotations

import os
from datetime import datetime

from src.models.job import Job
from src.sources.base import BaseConnector
from src.utils.http_client import SafeHttpClient
from src.utils.text import clean_html

BASE_URL = "https://api.adzuna.com/v1/api/jobs"

COUNTRY_CODE_MAP = {
    "UK": "gb", "US": "us", "AU": "au", "BR": "br", "CA": "ca",
    "DE": "de", "FR": "fr", "IN": "in", "NL": "nl", "NZ": "nz",
    "PL": "pl", "SG": "sg", "ZA": "za", "AT": "at", "IT": "it",
    "ES": "es",
}


def _get_credentials() -> tuple[str, str] | None:
    app_id = os.environ.get("ADZUNA_APP_ID", "").strip()
    app_key = os.environ.get("ADZUNA_APP_KEY", "").strip()
    if app_id and app_key:
        return app_id, app_key
    return None


class AdzunaConnector(BaseConnector):
    """Adzuna -- covers UK, US, EU, AU and more. Free API (register at developer.adzuna.com)."""

    name = "adzuna"

    def __init__(self, keywords: str = "", location: str = "", country: str = "UK"):
        self.keywords = keywords
        self.location = location
        self.country = country.upper()

    @staticmethod
    def is_available() -> bool:
        return _get_credentials() is not None

    def fetch_jobs(self) -> list[Job]:
        creds = _get_credentials()
        if not creds:
            return []

        app_id, app_key = creds
        adzuna_country = COUNTRY_CODE_MAP.get(self.country, "gb")

        jobs: list[Job] = []
        max_pages = 3

        with SafeHttpClient() as client:
            for page in range(1, max_pages + 1):
                url = f"{BASE_URL}/{adzuna_country}/search/{page}"
                params: dict = {
                    "app_id": app_id,
                    "app_key": app_key,
                    "results_per_page": 50,
                    "content-type": "application/json",
                }
                if self.keywords:
                    params["what"] = self.keywords
                if self.location:
                    params["where"] = self.location

                resp = client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()

                results = data.get("results", [])
                if not results:
                    break

                for item in results:
                    published = None
                    if item.get("created"):
                        try:
                            published = datetime.fromisoformat(
                                str(item["created"]).replace("Z", "+00:00")
                            )
                        except (ValueError, TypeError):
                            pass

                    location_info = item.get("location", {})
                    display_location = location_info.get("display_name", "") if isinstance(location_info, dict) else ""

                    company_info = item.get("company", {})
                    company_name = company_info.get("display_name", "") if isinstance(company_info, dict) else ""

                    category_info = item.get("category", {})
                    category_tag = category_info.get("tag", "") if isinstance(category_info, dict) else ""

                    salary_min = item.get("salary_min")
                    salary_max = item.get("salary_max")

                    contract_type = item.get("contract_type", "")
                    contract_time = item.get("contract_time", "")

                    redirect_url = item.get("redirect_url", "")

                    tags = []
                    if category_tag:
                        tags.append(category_tag.replace("-", " "))
                    if contract_type:
                        tags.append(contract_type)
                    if contract_time:
                        tags.append(contract_time.replace("_", " "))

                    jobs.append(
                        Job(
                            id=f"adzuna-{item.get('id', '')}",
                            title=item.get("title", ""),
                            company=company_name,
                            description=clean_html(item.get("description", "")),
                            url=redirect_url,
                            source=f"adzuna:{adzuna_country}",
                            location=display_location,
                            remote_type="",
                            salary_min=float(salary_min) if salary_min else None,
                            salary_max=float(salary_max) if salary_max else None,
                            salary_currency="GBP" if adzuna_country == "gb" else "USD",
                            tags=tags,
                            published_at=published,
                        )
                    )

                if len(results) < 50:
                    break

        return jobs
