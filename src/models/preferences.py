from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Preferences:
    target_titles: list[str] = field(default_factory=list)
    required_skills: list[str] = field(default_factory=list)
    nice_to_have_skills: list[str] = field(default_factory=list)
    locations: list[str] = field(default_factory=list)
    country: str = ""  # ISO-style: "UK", "US", "DE", "CA", etc.
    remote_types: list[str] = field(default_factory=list)  # ["remote", "hybrid", "onsite"]
    seniority_levels: list[str] = field(default_factory=list)  # ["senior", "lead"]
    min_salary: float | None = None
    salary_currency: str = "USD"
    industries: list[str] = field(default_factory=list)
    also_remote_in: list[str] = field(default_factory=list)  # extra countries for remote-only

    # Legacy single-value compat
    @property
    def remote_type(self) -> str:
        return self.remote_types[0] if self.remote_types else ""

    @property
    def seniority(self) -> str:
        return self.seniority_levels[0] if self.seniority_levels else ""

    def to_dict(self) -> dict:
        return {
            "target_titles": self.target_titles,
            "required_skills": self.required_skills,
            "nice_to_have_skills": self.nice_to_have_skills,
            "locations": self.locations,
            "country": self.country,
            "remote_types": self.remote_types,
            "seniority_levels": self.seniority_levels,
            "min_salary": self.min_salary,
            "salary_currency": self.salary_currency,
            "industries": self.industries,
            "also_remote_in": self.also_remote_in,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Preferences:
        # Handle legacy single-value fields from old saved profiles
        d = dict(data)
        if "remote_type" in d and "remote_types" not in d:
            val = d.pop("remote_type")
            d["remote_types"] = [val] if val else []
        elif "remote_type" in d:
            d.pop("remote_type")
        if "seniority" in d and "seniority_levels" not in d:
            val = d.pop("seniority")
            d["seniority_levels"] = [val] if val else []
        elif "seniority" in d:
            d.pop("seniority")
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})
