from __future__ import annotations

import json
from pathlib import Path

from src.models.preferences import Preferences
from src.models.profile import Profile

LOCAL_PROFILE_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "local_profile.json"


class PrivacyManager:
    """Manages optional local persistence of user profile data."""

    def __init__(self, storage_path: Path | str = LOCAL_PROFILE_PATH):
        self.storage_path = Path(storage_path)

    def is_persisted(self) -> bool:
        return self.storage_path.exists()

    def save_profile(self, profile: Profile, prefs: Preferences) -> None:
        data = {
            "skills": profile.skills,
            "years_experience": profile.years_experience,
            "role_hints": profile.role_hints,
            "summary": profile.summary,
            "preferences": prefs.to_dict(),
        }
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.storage_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def load_profile(self) -> tuple[Profile, Preferences] | None:
        if not self.storage_path.exists():
            return None
        data = json.loads(self.storage_path.read_text(encoding="utf-8"))
        profile = Profile(
            skills=data.get("skills", []),
            years_experience=data.get("years_experience"),
            role_hints=data.get("role_hints", []),
            summary=data.get("summary", ""),
        )
        prefs = Preferences.from_dict(data.get("preferences", {}))
        return profile, prefs

    def delete_all(self) -> bool:
        deleted = False
        if self.storage_path.exists():
            self.storage_path.unlink()
            deleted = True

        cache_db = self.storage_path.parent / "job_cache.db"
        if cache_db.exists():
            cache_db.unlink()
            deleted = True

        return deleted

    def export_profile(self) -> str | None:
        if not self.storage_path.exists():
            return None
        return self.storage_path.read_text(encoding="utf-8")

    def import_profile(self, json_str: str) -> bool:
        try:
            data = json.loads(json_str)
            if "skills" not in data and "preferences" not in data:
                return False
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            self.storage_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            return True
        except (json.JSONDecodeError, TypeError):
            return False
