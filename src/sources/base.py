from __future__ import annotations

from abc import ABC, abstractmethod

from src.models.job import Job


class BaseConnector(ABC):
    """Abstract base for all job source connectors."""

    name: str = "unknown"

    @abstractmethod
    def fetch_jobs(self) -> list[Job]:
        """Fetch jobs from the source. Must use SafeHttpClient for all requests."""
        ...

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} source={self.name!r}>"
