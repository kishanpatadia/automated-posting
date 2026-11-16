import json

import httpx
import pytest

from app.config import Settings

VALID_MESSAGE = "Check out our latest business platform and grow your online visibility. https://example.com"


def configured_settings(**overrides) -> Settings:
    """All platforms configured with dummy creds (ignores .env)."""
    values = dict(
        bluesky_handle="tester.bsky.social",
        bluesky_app_password="xxxx-xxxx-xxxx-xxxx",
        mastodon_access_token="mastodon-token",
        telegram_bot_token="123:abc",
        telegram_channel="@test_channel",
        discord_webhook_url="https://discord.com/api/webhooks/1/token",
        discord_guild_id="999",
        devto_api_key="devto-key",
        gist_token="gist-token",
        verify_public_access=True,
    )
    values.update(overrides)
    return Settings(_env_file=None, **values)


def fake_platform_apis(request: httpx.Request, failures: dict[str, httpx.Response] | None = None) -> httpx.Response:
    """Fake responses for all platform APIs + post pages."""
    host, path = request.url.host, request.url.path
    for key, response in (failures or {}).items():
        if key in str(request.url):
            return response

    if request.method == "GET":  # public-access check of the posted URL
        return httpx.Response(200, text="<html>post</html>")
    if host == "bsky.social" and path.endswith("createSession"):
        return httpx.Response(200, json={"accessJwt": "jwt", "did": "did:plc:abc", "handle": "tester.bsky.social"})
    if host == "bsky.social" and path.endswith("createRecord"):
        return httpx.Response(200, json={"uri": "at://did:plc:abc/app.bsky.feed.post/3kpost", "cid": "c"})
    if host == "mastodon.social":
        return httpx.Response(200, json={"id": "1", "url": "https://mastodon.social/@tester/1", "visibility": "public"})
    if host == "api.telegram.org":
        return httpx.Response(
            200, json={"ok": True, "result": {"message_id": 42, "chat": {"id": -1, "username": "test_channel"}}}
        )
    if host == "discord.com":
        return httpx.Response(200, json={"id": "555", "channel_id": "777"})
    if host == "dev.to":
        article = json.loads(request.content)["article"]
        return httpx.Response(201, json={"id": 1, "url": "https://dev.to/tester/check-out-1", "published": article["published"]})
    if host == "api.github.com":
        return httpx.Response(201, json={"html_url": "https://gist.github.com/tester/abc", "public": True})
    return httpx.Response(404, json={"error": "unexpected request"})


@pytest.fixture
def settings() -> Settings:
    return configured_settings()
