import json
import tempfile
from pathlib import Path

import pytest

from src.models.preferences import Preferences
from src.models.profile import Profile
from src.storage.privacy import PrivacyManager


@pytest.fixture
def tmp_privacy_mgr(tmp_path):
    return PrivacyManager(storage_path=tmp_path / "test_profile.json")


def test_default_no_persistence(tmp_privacy_mgr):
    assert not tmp_privacy_mgr.is_persisted()


def test_save_and_load(tmp_privacy_mgr):
    profile = Profile(skills=["python", "sql"], years_experience=5, summary="Test")
    prefs = Preferences(target_titles=["Engineer"], remote_type="remote")

    tmp_privacy_mgr.save_profile(profile, prefs)
    assert tmp_privacy_mgr.is_persisted()

    loaded = tmp_privacy_mgr.load_profile()
    assert loaded is not None
    loaded_profile, loaded_prefs = loaded
    assert loaded_profile.skills == ["python", "sql"]
    assert loaded_prefs.target_titles == ["Engineer"]
    assert loaded_prefs.remote_type == "remote"


def test_delete_all(tmp_privacy_mgr):
    profile = Profile(skills=["python"])
    prefs = Preferences()
    tmp_privacy_mgr.save_profile(profile, prefs)

    assert tmp_privacy_mgr.is_persisted()
    tmp_privacy_mgr.delete_all()
    assert not tmp_privacy_mgr.is_persisted()


def test_export_profile(tmp_privacy_mgr):
    profile = Profile(skills=["react"], summary="Frontend dev")
    prefs = Preferences(locations=["London"])
    tmp_privacy_mgr.save_profile(profile, prefs)

    exported = tmp_privacy_mgr.export_profile()
    assert exported is not None
    data = json.loads(exported)
    assert data["skills"] == ["react"]
    assert data["preferences"]["locations"] == ["London"]


def test_import_profile(tmp_privacy_mgr):
    json_str = json.dumps({
        "skills": ["java"],
        "years_experience": 3,
        "role_hints": [],
        "summary": "Java dev",
        "preferences": {"target_titles": ["Developer"]},
    })
    assert tmp_privacy_mgr.import_profile(json_str)
    loaded = tmp_privacy_mgr.load_profile()
    assert loaded is not None
    assert loaded[0].skills == ["java"]


def test_import_invalid_json(tmp_privacy_mgr):
    assert not tmp_privacy_mgr.import_profile("not json")


def test_no_raw_cv_text_in_export(tmp_privacy_mgr):
    """Ensure raw CV text is NOT saved to disk by PrivacyManager."""
    profile = Profile(
        raw_text="This is my secret CV full text that should not be stored",
        skills=["python"],
        summary="Short summary",
    )
    prefs = Preferences()
    tmp_privacy_mgr.save_profile(profile, prefs)

    exported = tmp_privacy_mgr.export_profile()
    assert "This is my secret CV full text" not in exported
