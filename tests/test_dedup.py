from src.matching.dedup import deduplicate
from src.models.job import Job


def _make_job(title: str, company: str, source: str, desc: str = "") -> Job:
    return Job(
        id=f"{source}-1",
        title=title,
        company=company,
        description=desc,
        url=f"https://example.com/{source}",
        source=source,
    )


def test_dedup_same_title_company():
    jobs = [
        _make_job("Software Engineer", "Acme", "remotive", "Full desc here"),
        _make_job("Software Engineer", "Acme", "arbeitnow"),
    ]
    result = deduplicate(jobs)
    assert len(result) == 1
    # Keeps the one with description
    assert result[0].description == "Full desc here"


def test_dedup_different_jobs():
    jobs = [
        _make_job("Software Engineer", "Acme", "remotive"),
        _make_job("Data Scientist", "Acme", "remotive"),
        _make_job("Software Engineer", "OtherCo", "arbeitnow"),
    ]
    result = deduplicate(jobs)
    assert len(result) == 3


def test_dedup_case_insensitive():
    jobs = [
        _make_job("Software Engineer", "ACME", "remotive"),
        _make_job("software engineer", "acme", "arbeitnow"),
    ]
    result = deduplicate(jobs)
    assert len(result) == 1


def test_dedup_empty():
    assert deduplicate([]) == []
