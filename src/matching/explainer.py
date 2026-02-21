from __future__ import annotations

from src.models.job import Job
from src.models.profile import Profile
from src.models.preferences import Preferences


def explain_match(
    job: Job,
    profile: Profile,
    prefs: Preferences,
    scores: dict[str, float],
) -> dict[str, list[str]]:
    reasons: list[str] = []
    gaps: list[str] = []

    job_text_lower = (job.title + " " + job.description).lower()

    # Skill matches
    profile_skills = profile.skills_lower()
    job_tags = {t.lower() for t in job.tags}
    matched_skills = profile_skills & job_tags
    if matched_skills:
        display = sorted(matched_skills)[:8]
        reasons.append(f"Your skills match: {', '.join(display)}")

    # Required skills check
    if prefs.required_skills:
        required_lower = {s.lower() for s in prefs.required_skills}
        met = required_lower & job_tags
        missing = required_lower - job_tags
        if met:
            reasons.append(f"Has your required skills: {', '.join(sorted(met)[:5])}")
        if missing:
            found_in_desc = {s for s in missing if s in job_text_lower}
            still_missing = missing - found_in_desc
            if found_in_desc:
                reasons.append(f"Description mentions: {', '.join(sorted(found_in_desc)[:5])}")
            if still_missing:
                gaps.append(f"May not require: {', '.join(sorted(still_missing)[:5])}")

    # Title match
    if prefs.target_titles:
        title_lower = job.title.lower()
        for target in prefs.target_titles:
            if target.lower() in title_lower:
                reasons.append(f"Title matches your target: '{target}'")
                break

    # Text similarity
    sim_score = scores.get("text_similarity", 0)
    if sim_score > 0.3:
        reasons.append(f"Strong CV-to-job text similarity ({sim_score:.0%})")
    elif sim_score > 0.15:
        reasons.append(f"Moderate text similarity ({sim_score:.0%})")

    # Remote match
    if prefs.remote_type and job.remote_type == prefs.remote_type:
        reasons.append(f"Matches your {prefs.remote_type} preference")

    # Salary
    if job.salary_min and prefs.min_salary:
        if job.salary_min >= prefs.min_salary:
            reasons.append(f"Salary meets your minimum ({job.display_salary})")
        else:
            gaps.append(f"Salary may be below your minimum ({job.display_salary})")

    # Experience gap warning
    if profile.years_experience:
        desc = job.description.lower()
        import re
        exp_matches = re.findall(r"(\d+)\+?\s*(?:years?|yrs?)", desc)
        for m in exp_matches:
            required_years = float(m)
            if required_years > profile.years_experience + 2:
                gaps.append(f"Asks for {int(required_years)}+ years (you have ~{int(profile.years_experience)})")
                break

    if not reasons:
        reasons.append("General match based on overall profile fit")

    return {"reasons": reasons, "gaps": gaps}
