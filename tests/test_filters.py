from src.matching.filters import apply_hard_filters
from src.models.job import Job
from src.models.preferences import Preferences


def _make_job(**kwargs) -> Job:
    defaults = {
        "id": "test-1",
        "title": "Engineer",
        "company": "TestCo",
        "description": "A job",
        "url": "https://example.com",
        "source": "test",
    }
    defaults.update(kwargs)
    return Job(**defaults)


def test_filter_remote_single():
    jobs = [
        _make_job(id="1", remote_type="remote"),
        _make_job(id="2", remote_type="onsite"),
        _make_job(id="3", remote_type="hybrid"),
    ]
    prefs = Preferences(remote_types=["remote"])
    result = apply_hard_filters(jobs, prefs)
    assert all(j.remote_type in ("remote", "hybrid") for j in result)
    assert any(j.id == "1" for j in result)


def test_filter_remote_multi():
    jobs = [
        _make_job(id="1", remote_type="remote"),
        _make_job(id="2", remote_type="onsite"),
        _make_job(id="3", remote_type="hybrid"),
    ]
    prefs = Preferences(remote_types=["remote", "hybrid"])
    result = apply_hard_filters(jobs, prefs)
    ids = {j.id for j in result}
    assert "1" in ids
    assert "3" in ids


def test_filter_seniority_multi():
    jobs = [
        _make_job(id="1", title="Senior Engineer"),
        _make_job(id="2", title="Lead Engineer"),
        _make_job(id="3", title="Junior Developer"),
        _make_job(id="4", title="Engineer"),  # No seniority keyword
    ]
    prefs = Preferences(seniority_levels=["senior", "lead"])
    result = apply_hard_filters(jobs, prefs)
    ids = {j.id for j in result}
    assert "1" in ids
    assert "2" in ids
    assert "4" in ids  # Ambiguous title included
    assert "3" not in ids  # Junior excluded


def test_filter_location_with_country():
    jobs = [
        _make_job(id="1", location="London, UK"),
        _make_job(id="2", location="London, Canada"),
        _make_job(id="3", location="Worldwide"),
    ]
    prefs = Preferences(locations=["London"], country="UK")
    result = apply_hard_filters(jobs, prefs)
    ids = {j.id for j in result}
    assert "1" in ids
    assert "3" in ids
    assert "2" in ids  # City matches; country not in job listing so included


def test_filter_salary():
    jobs = [
        _make_job(id="1", salary_max=150000),
        _make_job(id="2", salary_max=50000),
        _make_job(id="3"),
    ]
    prefs = Preferences(min_salary=100000)
    result = apply_hard_filters(jobs, prefs)
    ids = {j.id for j in result}
    assert "1" in ids
    assert "3" in ids
    assert "2" not in ids


def test_no_filters():
    jobs = [_make_job(id="1"), _make_job(id="2")]
    prefs = Preferences()
    result = apply_hard_filters(jobs, prefs)
    assert len(result) == 2
