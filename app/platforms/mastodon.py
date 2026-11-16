"""Mastodon status API.

Docs: https://docs.joinmastodon.org/methods/statuses/#create
"""

import hashlib

import httpx

from app.platforms.base import Platform, PlatformError, PublishResult


class MastodonPlatform(Platform):
    name = "Mastodon"
    required_settings = ("mastodon_instance_url", "mastodon_access_token")

    async def publish(self, client: httpx.AsyncClient, message: str, url: str) -> PublishResult:
        base = self.settings.mastodon_instance_url.rstrip("/")
        body = self.ensure_ok(
            await client.post(
                f"{base}/api/v1/statuses",
                headers={
                    "Authorization": f"Bearer {self.settings.mastodon_access_token}",
                    # avoids duplicate toots on retry (key valid for 1h)
                    "Idempotency-Key": hashlib.sha256(message.encode()).hexdigest(),
                },
                data={"status": message, "visibility": "public"},
            )
        )
        posted_url = body.get("url") or body.get("uri")
        if not posted_url:
            raise PlatformError("Status was created but no URL was returned.")
        return PublishResult(posted_url=posted_url, public=body.get("visibility") == "public")
