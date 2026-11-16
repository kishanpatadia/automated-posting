"""Base class for platform integrations."""

from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx


class PlatformError(Exception):
    """Error message shown in the API response for a platform."""


@dataclass
class PublishResult:
    posted_url: str | None
    public: bool


class Platform(ABC):
    """Base platform. Subclasses implement publish()."""

    name: str  # shown in the response
    required_settings: tuple[str, ...] = ()  # Settings fields needed to post

    def __init__(self, settings) -> None:
        self.settings = settings

    def missing_settings(self) -> list[str]:
        return [key.upper() for key in self.required_settings if not getattr(self.settings, key, None)]

    @abstractmethod
    async def publish(self, client: httpx.AsyncClient, message: str, url: str) -> PublishResult:
        """Post the message. Raise PlatformError on failure."""

    def ensure_ok(self, response: httpx.Response) -> dict:
        """Return JSON body or raise PlatformError with the API error message."""
        try:
            body = response.json()
        except ValueError:
            body = {}

        if response.is_success:
            return body if isinstance(body, dict) else {"data": body}

        detail = _error_text(body) or response.reason_phrase or "Unknown error"
        if response.status_code in (401, 403):
            raise PlatformError(f"Authentication failed ({response.status_code}): {detail}")
        if response.status_code == 429:
            raise PlatformError(f"Rate limited by the platform (429): {detail}")
        raise PlatformError(f"HTTP {response.status_code}: {detail}")


def _error_text(body) -> str | None:
    if not isinstance(body, dict):
        return None
    for key in ("message", "error_description", "description", "error"):
        value = body.get(key)
        if isinstance(value, str) and value:
            return value
    errors = body.get("errors")
    if isinstance(errors, list) and errors:
        return "; ".join(str(e.get("message", e)) if isinstance(e, dict) else str(e) for e in errors)
    return None


def headline(message: str, url: str, limit: int = 80) -> str:
    """Message text without the link, trimmed for titles."""
    text = " ".join(message.replace(url, "").split()).strip(" -–:|")
    if len(text) <= limit:
        return text
    return text[: limit - 1].rsplit(" ", 1)[0].rstrip(",.;:") + "…"
