"""Bluesky via the AT Protocol XRPC API.

Docs: https://docs.bsky.app/docs/advanced-guides/posts
      https://docs.bsky.app/docs/api/com-atproto-server-create-session
"""

from datetime import datetime, timezone

import httpx

from app.platforms.base import Platform, PlatformError, PublishResult


class BlueskyPlatform(Platform):
    name = "Bluesky"
    required_settings = ("bluesky_handle", "bluesky_app_password")

    async def publish(self, client: httpx.AsyncClient, message: str, url: str) -> PublishResult:
        base = self.settings.bluesky_service.rstrip("/")

        session = self.ensure_ok(
            await client.post(
                f"{base}/xrpc/com.atproto.server.createSession",
                json={
                    "identifier": self.settings.bluesky_handle,
                    "password": self.settings.bluesky_app_password,
                },
            )
        )
        token, did = session.get("accessJwt"), session.get("did")
        handle = session.get("handle") or self.settings.bluesky_handle
        if not token or not did:
            raise PlatformError("Login succeeded but no session token was returned.")

        record = {
            "$type": "app.bsky.feed.post",
            "text": message,
            "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "langs": ["en"],
            "facets": [_link_facet(message, url)],
        }
        created = self.ensure_ok(
            await client.post(
                f"{base}/xrpc/com.atproto.repo.createRecord",
                headers={"Authorization": f"Bearer {token}"},
                json={"repo": did, "collection": "app.bsky.feed.post", "record": record},
            )
        )

        uri = created.get("uri", "")  # at://<did>/app.bsky.feed.post/<rkey>
        rkey = uri.rsplit("/", 1)[-1] if uri else None
        if not rkey:
            raise PlatformError("Post was created but no record URI was returned.")
        return PublishResult(posted_url=f"https://bsky.app/profile/{handle}/post/{rkey}", public=True)


def _link_facet(message: str, url: str) -> dict:
    """Link facet so the URL is clickable. Offsets are in UTF-8 bytes."""
    start = len(message[: message.index(url)].encode("utf-8"))
    end = start + len(url.encode("utf-8"))
    return {
        "index": {"byteStart": start, "byteEnd": end},
        "features": [{"$type": "app.bsky.richtext.facet#link", "uri": url}],
    }
