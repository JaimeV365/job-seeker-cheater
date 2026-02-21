import pytest

from src.utils.http_client import (
    SafeHttpClient,
    PrivacyViolationError,
    register_personal_fragments,
    _check_payload,
)


def test_no_fragments_registered():
    register_personal_fragments([])
    _check_payload("anything goes here", "test")


def test_blocks_cv_fragment_in_url():
    register_personal_fragments([
        "John Doe Senior Software Engineer with extensive experience",
    ])
    with pytest.raises(PrivacyViolationError):
        _check_payload(
            "https://api.example.com?q=john doe senior software engineer with extensive experience",
            "URL",
        )


def test_blocks_cv_fragment_in_params():
    register_personal_fragments([
        "Experienced Python developer specializing in machine learning",
    ])
    with pytest.raises(PrivacyViolationError):
        _check_payload(
            "{'query': 'experienced python developer specializing in machine learning'}",
            "query params",
        )


def test_allows_safe_requests():
    register_personal_fragments([
        "John Doe Senior Software Engineer with extensive experience",
    ])
    # Normal job API URL should pass
    _check_payload("https://remotive.com/api/remote-jobs", "URL")
    _check_payload("https://www.arbeitnow.com/api/job-board-api", "URL")


def test_short_fragments_ignored():
    register_personal_fragments(["short", "tiny"])
    # Fragments under 12 chars are ignored for privacy safety
    _check_payload("This contains short and tiny words", "test")


def test_cleanup():
    register_personal_fragments(["a very long fragment that should be tracked carefully"])
    register_personal_fragments([])  # Clear
    _check_payload("a very long fragment that should be tracked carefully", "test")
