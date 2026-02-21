from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from src.models.profile import Profile

_SKILLS_CACHE: dict[str, list[str]] | None = None


def _load_skills_dict() -> dict[str, list[str]]:
    global _SKILLS_CACHE
    if _SKILLS_CACHE is not None:
        return _SKILLS_CACHE
    skills_path = Path(__file__).resolve().parent.parent.parent / "data" / "skills_seed.json"
    with open(skills_path, encoding="utf-8") as f:
        _SKILLS_CACHE = json.load(f)
    return _SKILLS_CACHE


def extract_skills(text: str) -> list[str]:
    skills_dict = _load_skills_dict()
    text_lower = text.lower()
    found: set[str] = set()

    all_skills: list[str] = []
    for category_skills in skills_dict.values():
        all_skills.extend(category_skills)

    # Sort by length descending so multi-word skills match first
    all_skills.sort(key=len, reverse=True)

    for skill in all_skills:
        pattern = r"\b" + re.escape(skill.lower()) + r"\b"
        if re.search(pattern, text_lower):
            found.add(skill.lower())

    return sorted(found)


def extract_years_experience(text: str) -> float | None:
    patterns = [
        r"(\d+)\+?\s*(?:years?|yrs?)\s*(?:of\s+)?(?:experience|exp)",
        r"(?:experience|exp)\s*(?:of\s+)?(\d+)\+?\s*(?:years?|yrs?)",
        r"(\d+)\+?\s*(?:years?|yrs?)\s+in\b",
    ]
    max_years = 0.0
    for pat in patterns:
        for match in re.finditer(pat, text, re.IGNORECASE):
            years = float(match.group(1))
            if years <= 50:
                max_years = max(max_years, years)

    # Also try date-range math: "2015 - 2023", "2015 - Present"
    date_pattern = r"(20\d{2})\s*[-–—]\s*(20\d{2}|[Pp]resent|[Cc]urrent|[Nn]ow)"
    spans: list[float] = []
    for match in re.finditer(date_pattern, text):
        start_year = int(match.group(1))
        end_str = match.group(2)
        if end_str[0].isdigit():
            end_year = int(end_str)
        else:
            end_year = datetime.now().year
        span = end_year - start_year
        if 0 < span <= 50:
            spans.append(span)

    if spans:
        max_years = max(max_years, max(spans))

    return max_years if max_years > 0 else None


def extract_role_hints(text: str) -> list[str]:
    role_patterns = [
        r"\b(senior|sr\.?|lead|principal|staff|chief|head of|director|vp|manager)\s+"
        r"([\w\s]{3,30}?)(?:\n|,|\.|;|\bat\b|\bin\b)",
        r"\b(software engineer|data scientist|product manager|project manager|"
        r"devops engineer|frontend developer|backend developer|full.?stack|"
        r"ux designer|ui designer|data analyst|data engineer|ml engineer|"
        r"machine learning engineer|solutions architect|cloud engineer|"
        r"scrum master|business analyst|consultant|account manager|"
        r"customer success manager|marketing manager|sales manager)\b",
    ]
    roles: set[str] = set()
    for pat in role_patterns:
        for match in re.finditer(pat, text, re.IGNORECASE):
            role = match.group(0).strip().rstrip(".,;")
            if len(role) > 3:
                roles.add(role.lower())

    return sorted(roles)


def build_profile(raw_text: str) -> Profile:
    skills = extract_skills(raw_text)
    years = extract_years_experience(raw_text)
    role_hints = extract_role_hints(raw_text)

    lines = raw_text.split("\n")
    summary = " ".join(lines[:5]).strip()
    if len(summary) > 300:
        summary = summary[:300] + "..."

    return Profile(
        raw_text=raw_text,
        skills=skills,
        years_experience=years,
        role_hints=role_hints,
        summary=summary,
    )
