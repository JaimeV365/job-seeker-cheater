from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Preferences:
    target_titles: list[str] = field(default_factory=list)
    required_skills: list[str] = field(default_factory=list)
    nice_to_have_skills: list[str] = field(default_factory=list)
    locations: list[str] = field(default_factory=list)
    remote_type: str = ""  # "remote", "hybrid", "onsite", "" (any)
    seniority: str = ""  # "junior", "mid", "senior", "lead", "executive", ""
    min_salary: float | None = None
    salary_currency: str = "USD"
    industries: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "target_titles": self.target_titles,
            "required_skills": self.required_skills,
            "nice_to_have_skills": self.nice_to_have_skills,
            "locations": self.locations,
            "remote_type": self.remote_type,
            "seniority": self.seniority,
            "min_salary": self.min_salary,
            "salary_currency": self.salary_currency,
            "industries": self.industries,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Preferences:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
