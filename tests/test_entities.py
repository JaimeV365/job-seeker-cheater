from src.cv.entities import extract_skills, extract_years_experience, extract_role_hints, build_profile


def test_extract_skills_basic():
    text = "Experienced in Python, JavaScript, and React. Used Django and PostgreSQL daily."
    skills = extract_skills(text)
    assert "python" in skills
    assert "javascript" in skills
    assert "react" in skills
    assert "django" in skills
    assert "postgresql" in skills


def test_extract_skills_multiword():
    text = "Built machine learning models using scikit-learn and deep learning frameworks."
    skills = extract_skills(text)
    assert "machine learning" in skills
    assert "scikit-learn" in skills
    assert "deep learning" in skills


def test_extract_skills_empty():
    skills = extract_skills("No relevant skills mentioned here at all.")
    # May find some, but should not crash
    assert isinstance(skills, list)


def test_extract_years_direct():
    assert extract_years_experience("10 years of experience in software") == 10.0


def test_extract_years_plus():
    assert extract_years_experience("5+ years exp in data science") == 5.0


def test_extract_years_date_range():
    result = extract_years_experience("Software Engineer at Acme Corp 2018 - 2023")
    assert result == 5.0


def test_extract_years_present():
    result = extract_years_experience("Working at Foo Inc 2020 - Present")
    assert result is not None
    assert result >= 5


def test_extract_years_none():
    assert extract_years_experience("No experience info here") is None


def test_extract_role_hints():
    text = "Senior Software Engineer at Google. Previously Lead Data Scientist."
    roles = extract_role_hints(text)
    assert any("senior" in r for r in roles)


def test_build_profile():
    text = (
        "Jane Smith - Senior Data Scientist\n"
        "8 years of experience in machine learning, Python, SQL, and TensorFlow.\n"
        "Previously worked as a Software Engineer at Acme Corp 2015 - 2020."
    )
    profile = build_profile(text)
    assert not profile.is_empty
    assert "python" in profile.skills
    assert "machine learning" in profile.skills
    assert profile.years_experience is not None
    assert profile.years_experience >= 5
    assert len(profile.role_hints) > 0
