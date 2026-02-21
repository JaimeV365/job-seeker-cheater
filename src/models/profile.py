from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Profile:
    raw_text: str = ""
    skills: list[str] = field(default_factory=list)
    years_experience: float | None = None
    role_hints: list[str] = field(default_factory=list)
    summary: str = ""

    @property
    def is_empty(self) -> bool:
        return not self.raw_text.strip()

    def skills_lower(self) -> set[str]:
        return {s.lower() for s in self.skills}
