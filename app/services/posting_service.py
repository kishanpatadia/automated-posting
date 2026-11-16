"""Posts a message to all enabled platforms in parallel."""

import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

from app.platforms import Platform, PlatformError, build_platforms
from app.schemas import PlatformResult

logger = logging.getLogger(__name__)

USER_AGENT = "automated-posting/1.0"


class PostingService:
    def __init__(self, settings, platforms: list[Platform] | None = None, transport=None) -> None:
        self.settings = settings
        self.platforms = platforms if platforms is not None else build_platforms(settings)
        self.transport = transport  # MockTransport in tests
        self.tz = ZoneInfo(settings.timezone)

    async def post(self, message: str, url: str) -> list[PlatformResult]:
        async with httpx.AsyncClient(
            timeout=self.settings.request_timeout_seconds,
            headers={"User-Agent": USER_AGENT},
            transport=self.transport,
        ) as client:
            # return_exceptions=True so one bad platform can't kill the whole batch
            outcomes = await asyncio.gather(
                *(self._post_one(client, p, message, url) for p in self.platforms),
                return_exceptions=True,
            )

        results = []
        for platform, outcome in zip(self.platforms, outcomes):
            if isinstance(outcome, BaseException):
                logger.exception("Unhandled error for %s", platform.name, exc_info=outcome)
                outcome = _failed(platform, "Unexpected internal error")
            results.append(outcome)
        return results

    async def _post_one(self, client: httpx.AsyncClient, platform: Platform, message: str, url: str) -> PlatformResult:
        missing = platform.missing_settings()
        if missing:
            return _failed(platform, f"Not configured: set {', '.join(missing)}")

        try:
            published = await platform.publish(client, message, url)
        except PlatformError as exc:
            error = str(exc)
        except httpx.TimeoutException:
            error = f"Request timed out after {self.settings.request_timeout_seconds:g}s"
        except httpx.RequestError as exc:
            error = f"Network error: {exc.__class__.__name__}"
        except Exception:  # noqa: BLE001
            logger.exception("Unexpected error while posting to %s", platform.name)
            error = "Unexpected error while posting"
        else:
            now = datetime.now(self.tz)
            public = published.public and bool(published.posted_url)
            if public and self.settings.verify_public_access:
                public = await self._is_publicly_reachable(client, published.posted_url)
            logger.info("Posted to %s: %s (public=%s)", platform.name, published.posted_url, public)
            return PlatformResult(
                platform=platform.name,
                status="success",
                posted_url=published.posted_url,
                public_access=public,
                date=now.strftime("%Y-%m-%d"),
                time=now.strftime("%H:%M:%S"),
            )

        logger.warning("Posting to %s failed: %s", platform.name, error)
        return _failed(platform, error)

    @staticmethod
    async def _is_publicly_reachable(client: httpx.AsyncClient, url: str) -> bool:
        """Anonymous GET on the posted URL to check it is actually public."""
        try:
            response = await client.get(url, follow_redirects=True)
            return response.status_code < 400
        except httpx.HTTPError:
            return False


def _failed(platform: Platform, error: str) -> PlatformResult:
    return PlatformResult(platform=platform.name, status="failed", error=error)
