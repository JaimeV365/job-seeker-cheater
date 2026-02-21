from unittest.mock import patch, MagicMock
import json

from src.sources.remotive import RemotiveConnector
from src.sources.arbeitnow import ArbeitnowConnector
from src.sources.greenhouse import GreenhouseConnector
from src.sources.normalizer import deduplicate_jobs
from src.models.job import Job


MOCK_REMOTIVE_RESPONSE = {
    "jobs": [
        {
            "id": 1,
            "title": "Backend Engineer",
            "company_name": "TestCo",
            "description": "<p>Build APIs</p>",
            "url": "https://example.com/1",
            "candidate_required_location": "Worldwide",
            "tags": ["python", "django"],
            "salary": "80000 - 120000",
            "publication_date": "2026-01-15T00:00:00",
        }
    ]
}

MOCK_ARBEITNOW_RESPONSE = {
    "data": [
        {
            "slug": "backend-eng-testco",
            "title": "Backend Engineer",
            "company_name": "TestCo",
            "description": "Build APIs with Python",
            "url": "https://example.com/2",
            "location": "Berlin",
            "remote": True,
            "tags": ["python", "fastapi"],
            "created_at": 1705276800,
        }
    ],
    "links": {},
}

MOCK_GREENHOUSE_RESPONSE = {
    "jobs": [
        {
            "id": 99,
            "title": "Data Scientist",
            "content": "<p>ML role</p>",
            "absolute_url": "https://boards.greenhouse.io/testco/99",
            "updated_at": "2026-01-20T12:00:00Z",
            "offices": [{"name": "London"}],
            "departments": [{"name": "Engineering"}],
        }
    ]
}


def _mock_response(data: dict, status_code: int = 200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = data
    resp.raise_for_status.return_value = None
    return resp


@patch("src.sources.remotive.SafeHttpClient")
def test_remotive_fetch(mock_client_cls):
    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.get.return_value = _mock_response(MOCK_REMOTIVE_RESPONSE)
    mock_client_cls.return_value = mock_client

    connector = RemotiveConnector()
    jobs = connector.fetch_jobs()

    assert len(jobs) == 1
    assert jobs[0].title == "Backend Engineer"
    assert jobs[0].company == "TestCo"
    assert jobs[0].source == "remotive"
    assert jobs[0].remote_type == "remote"
    assert jobs[0].salary_min is not None


@patch("src.sources.arbeitnow.SafeHttpClient")
def test_arbeitnow_fetch(mock_client_cls):
    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.get.return_value = _mock_response(MOCK_ARBEITNOW_RESPONSE)
    mock_client_cls.return_value = mock_client

    connector = ArbeitnowConnector()
    jobs = connector.fetch_jobs()

    assert len(jobs) == 1
    assert jobs[0].title == "Backend Engineer"
    assert jobs[0].source == "arbeitnow"
    assert jobs[0].remote_type == "remote"


@patch("src.sources.greenhouse.SafeHttpClient")
def test_greenhouse_fetch(mock_client_cls):
    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.get.return_value = _mock_response(MOCK_GREENHOUSE_RESPONSE)
    mock_client_cls.return_value = mock_client

    connector = GreenhouseConnector(slugs=["testco"])
    jobs = connector.fetch_jobs()

    assert len(jobs) == 1
    assert jobs[0].title == "Data Scientist"
    assert jobs[0].location == "London"
    assert "greenhouse" in jobs[0].source
