from __future__ import annotations

import httpx


class PrivacyViolationError(Exception):
    pass


_BLOCKED_PATTERNS: list[str] = []


def register_personal_fragments(fragments: list[str]) -> None:
    """Register CV text fragments that must never appear in outbound requests."""
    _BLOCKED_PATTERNS.clear()
    for frag in fragments:
        cleaned = frag.strip()
        if len(cleaned) >= 12:
            _BLOCKED_PATTERNS.append(cleaned.lower())


def _check_payload(text: str, context: str) -> None:
    if not _BLOCKED_PATTERNS:
        return
    text_lower = text.lower()
    for pattern in _BLOCKED_PATTERNS:
        if pattern in text_lower:
            raise PrivacyViolationError(
                f"Personal data detected in {context}. "
                f"Outbound requests must not contain CV content."
            )


class SafeHttpClient:
    """HTTP client wrapper that blocks requests containing personal data."""

    def __init__(self, timeout: float = 30.0):
        self._client = httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": "JobSeekerCheater/1.0 (local tool)"},
        )

    def get(self, url: str, **kwargs) -> httpx.Response:
        _check_payload(url, "URL")
        params = kwargs.get("params")
        if params:
            _check_payload(str(params), "query params")
        return self._client.get(url, **kwargs)

    def close(self) -> None:
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
