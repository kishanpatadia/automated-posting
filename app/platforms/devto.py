"""DEV Community (Forem) articles API.

Docs: https://developers.forem.com/api/v1#tag/articles/operation/createArticle
"""

import re

import httpx

from app.platforms.base import Platform, PlatformError, PublishResult, headline


class DevtoPlatform(Platform):
    name = "DEV Community"
    required_settings = ("devto_api_key",)

    async def publish(self, client: httpx.AsyncClient, message: str, url: str) -> PublishResult:
        tags = [re.sub(r"[^a-z0-9]", "", t.lower()) for t in self.settings.devto_tags.split(",")]
        article = {
            "title": headline(message, url, limit=100) or "Announcement",
            "body_markdown": message.replace(url, f"[{url}]({url})"),
            "published": True,
            "tags": [t for t in tags if t][:4],  # max 4 tags
        }
        body = self.ensure_ok(
            await client.post(
                "https://dev.to/api/articles",
                headers={
                    "api-key": self.settings.devto_api_key,
                    "Accept": "application/vnd.forem.api-v1+json",
                },
                json={"article": article},
            )
        )
        posted_url = body.get("url")
        if not posted_url:
            raise PlatformError("Article was created but no URL was returned.")
        return PublishResult(posted_url=posted_url, public=bool(body.get("published", True)))
