from __future__ import annotations

import re
import html


def clean_html(raw: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", raw, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return collapse_whitespace(text)


def collapse_whitespace(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def normalize_for_matching(text: str) -> str:
    text = clean_html(text)
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s\-\+\#\.]", " ", text)
    return collapse_whitespace(text)
