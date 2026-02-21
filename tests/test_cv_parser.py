import pytest

from src.cv.parser import parse_cv, parse_txt


def test_parse_txt():
    content = b"John Doe\nSoftware Engineer\n5 years experience in Python"
    result = parse_txt(content)
    assert "John Doe" in result
    assert "Software Engineer" in result
    assert "Python" in result


def test_parse_cv_txt():
    content = b"Senior Data Scientist with 8 years experience"
    result = parse_cv("resume.txt", content)
    assert "Senior Data Scientist" in result
    assert "8 years" in result


def test_parse_cv_unsupported():
    with pytest.raises(ValueError, match="Unsupported file type"):
        parse_cv("resume.jpg", b"data")


def test_parse_txt_unicode():
    content = "Expérience en développement Python".encode("utf-8")
    result = parse_txt(content)
    assert "Python" in result


def test_parse_txt_whitespace_collapsed():
    content = b"Hello     World\n\n\n\n\nTest"
    result = parse_txt(content)
    assert "Hello World" in result
    assert "\n\n\n" not in result
