from datetime import datetime, timedelta, timezone

from src.matching.scorer import score_jobs
from src.models.job import Job
from src.models.profile import Profile
from src.models.preferences import Preferences


def _make_job(title: str, desc: str, tags: list[str] | None = None, **kwargs) -> Job:
    return Job(
        id=f"test-{title}",
        title=title,
        company="TestCo",
        description=desc,
        url="https://example.com",
        source="test",
        tags=tags or [],
        **kwargs,
    )


def test_score_jobs_basic():
    profile = Profile(
        raw_text="Experienced Python developer with 5 years in machine learning and data science.",
        skills=["python", "machine learning", "data science"],
    )
    prefs = Preferences(target_titles=["Data Scientist"])

    jobs = [
        _make_job("Data Scientist", "Looking for ML expert with Python and data science skills", ["python", "machine learning"]),
        _make_job("Marketing Manager", "Lead our marketing team. SEO and content strategy.", ["seo", "marketing"]),
    ]

    results = score_jobs(jobs, profile, prefs)

    assert len(results) == 2
    # Data Scientist should rank higher
    assert results[0][0].title == "Data Scientist"
    assert results[0][1] > results[1][1]


def test_score_jobs_empty_profile():
    profile = Profile()
    prefs = Preferences()
    jobs = [_make_job("Engineer", "Build things")]
    results = score_jobs(jobs, profile, prefs)
    assert len(results) == 1
    assert results[0][1] == 0.0


def test_score_jobs_recency_bonus():
    profile = Profile(raw_text="Python developer", skills=["python"])
    prefs = Preferences()

    recent = _make_job(
        "Python Dev A", "Python development role",
        ["python"], published_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    old = _make_job(
        "Python Dev B", "Python development role",
        ["python"], published_at=datetime.now(timezone.utc) - timedelta(days=60),
    )

    results = score_jobs([old, recent], profile, prefs)
    # Recent job should score higher (same content, different recency)
    assert results[0][0].title == "Python Dev A"
