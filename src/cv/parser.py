from __future__ import annotations

import io
from pathlib import Path

from src.utils.text import collapse_whitespace


def parse_pdf(file_bytes: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(file_bytes))
    pages = [page.extract_text() or "" for page in reader.pages]
    return collapse_whitespace("\n".join(pages))


def parse_docx(file_bytes: bytes) -> str:
    from docx import Document

    doc = Document(io.BytesIO(file_bytes))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return collapse_whitespace("\n".join(paragraphs))


def parse_txt(file_bytes: bytes) -> str:
    text = file_bytes.decode("utf-8", errors="replace")
    return collapse_whitespace(text)


def parse_html(file_bytes: bytes) -> str:
    from src.utils.text import clean_html

    raw = file_bytes.decode("utf-8", errors="replace")
    return collapse_whitespace(clean_html(raw))


def parse_cv(filename: str, file_bytes: bytes) -> str:
    ext = Path(filename).suffix.lower()
    parsers = {
        ".pdf": parse_pdf,
        ".docx": parse_docx,
        ".txt": parse_txt,
        ".html": parse_html,
        ".htm": parse_html,
    }
    parser = parsers.get(ext)
    if parser is None:
        raise ValueError(f"Unsupported file type: {ext}. Use PDF, DOCX, TXT, or HTML.")
    return parser(file_bytes)
