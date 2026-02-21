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


def test_filter_remote():
    jobs = [
        _make_job(id="1", remote_type="remote"),
        _make_job(id="2", remote_type="onsite"),
        _make_job(id="3", remote_type="hybrid"),
    ]
    prefs = Preferences(remote_type="remote")
    result = apply_hard_filters(jobs, prefs)
    assert all(j.remote_type == "remote" for j in result)


def test_filter_location():
    jobs = [
        _make_job(id="1", location="London, UK"),
        _make_job(id="2", location="Berlin, Germany"),
        _make_job(id="3", location="Worldwide"),
    ]
    prefs = Preferences(locations=["London"])
    result = apply_hard_filters(jobs, prefs)
    assert len(result) == 2  # London + Worldwide


def test_filter_salary():
    jobs = [
        _make_job(id="1", salary_max=150000),
        _make_job(id="2", salary_max=50000),
        _make_job(id="3"),  # No salary data -- included by default
    ]
    prefs = Preferences(min_salary=100000)
    result = apply_hard_filters(jobs, prefs)
    ids = {j.id for j in result}
    assert "1" in ids  # High salary
    assert "3" in ids  # No data (included)
    assert "2" not in ids  # Below minimum


def test_no_filters():
    jobs = [_make_job(id="1"), _make_job(id="2")]
    prefs = Preferences()
    result = apply_hard_filters(jobs, prefs)
    assert len(result) == 2
