import json
import re

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app, get_posting_service
from app.platforms import REGISTRY
from app.services.posting_service import PostingService
from tests.conftest import VALID_MESSAGE, configured_settings, fake_platform_apis

URL = "https://example.com"


def service_with(settings, failures=None, recorder=None):
    def handler(request: httpx.Request) -> httpx.Response:
        if recorder is not None:
            recorder.append(request)
        return fake_platform_apis(request, failures)

    return PostingService(settings, transport=httpx.MockTransport(handler))


async def test_posts_to_every_platform(settings):
    results = await service_with(settings).post(VALID_MESSAGE, URL)

    assert [r.platform for r in results] == [cls.name for cls in REGISTRY.values()]
    assert len(results) >= 5
    by_name = {r.platform: r for r in results}
    assert all(r.status == "success" and r.error is None for r in results)
    assert by_name["Bluesky"].posted_url == "https://bsky.app/profile/tester.bsky.social/post/3kpost"
    assert by_name["Mastodon"].posted_url == "https://mastodon.social/@tester/1"
    assert by_name["Telegram"].posted_url == "https://t.me/test_channel/42"
    assert by_name["Discord"].posted_url == "https://discord.com/channels/999/777/555"
    assert by_name["DEV Community"].posted_url == "https://dev.to/tester/check-out-1"
    assert by_name["GitHub Gist"].posted_url == "https://gist.github.com/tester/abc"
    # discord isn't public
    assert {r.platform for r in results if r.public_access} == set(by_name) - {"Discord"}
    for r in results:
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", r.date)
        assert re.fullmatch(r"\d{2}:\d{2}:\d{2}", r.time)


async def test_one_failure_does_not_stop_the_others(settings):
    failures = {
        "api.telegram.org": httpx.Response(401, json={"ok": False, "description": "Unauthorized"}),
        "dev.to": httpx.Response(422, json={"error": "Title has already been used in the last five minutes"}),
    }
    results = {r.platform: r for r in await service_with(settings, failures).post(VALID_MESSAGE, URL)}

    assert results["Telegram"].status == "failed"
    assert results["Telegram"].error == "Authentication failed (401): Unauthorized"
    assert results["Telegram"].posted_url is None and results["Telegram"].date is None
    assert results["DEV Community"].error == "HTTP 422: Title has already been used in the last five minutes"
    assert [n for n, r in results.items() if r.status == "success"] == ["Bluesky", "Mastodon", "Discord", "GitHub Gist"]


async def test_network_errors_and_timeouts_are_reported(settings):
    def handler(request):
        if request.url.host == "mastodon.social":
            raise httpx.ConnectTimeout("timed out", request=request)
        if request.url.host == "api.github.com":
            raise httpx.ConnectError("refused", request=request)
        return fake_platform_apis(request)

    service = PostingService(settings, transport=httpx.MockTransport(handler))
    results = {r.platform: r for r in await service.post(VALID_MESSAGE, URL)}

    assert results["Mastodon"].error == "Request timed out after 15s"
    assert results["GitHub Gist"].error == "Network error: ConnectError"
    assert results["Bluesky"].status == "success"


async def test_unexpected_exception_in_a_platform_is_contained(settings, monkeypatch):
    async def boom(self, client, message, url):
        raise RuntimeError("bug")

    monkeypatch.setattr(REGISTRY["discord"], "publish", boom)
    results = {r.platform: r for r in await service_with(settings).post(VALID_MESSAGE, URL)}
    assert results["Discord"].error == "Unexpected error while posting"
    assert results["Mastodon"].status == "success"


async def test_unconfigured_platform_fails_without_calling_its_api():
    requests = []
    settings = configured_settings(mastodon_access_token=None, telegram_channel="")
    results = {r.platform: r for r in await service_with(settings, recorder=requests).post(VALID_MESSAGE, URL)}

    assert results["Mastodon"].error == "Not configured: set MASTODON_ACCESS_TOKEN"
    assert results["Telegram"].error == "Not configured: set TELEGRAM_CHANNEL"
    assert not any(r.url.host in {"mastodon.social", "api.telegram.org"} for r in requests)


async def test_public_access_false_when_posted_page_is_not_reachable(settings):
    failures = {"https://gist.github.com/tester/abc": httpx.Response(404)}
    results = {r.platform: r for r in await service_with(settings, failures).post(VALID_MESSAGE, URL)}
    assert results["GitHub Gist"].status == "success"
    assert results["GitHub Gist"].public_access is False


async def test_enabled_platforms_selects_and_orders_platforms():
    settings = configured_settings(enabled_platforms="mastodon, bluesky, unknown")
    results = await service_with(settings).post(VALID_MESSAGE, URL)
    assert [r.platform for r in results] == ["Mastodon", "Bluesky"]


async def test_request_payloads_follow_each_api(settings):
    requests = []
    message = "Grow your shop online ✨ https://example.com/start today"
    await service_with(settings, recorder=requests).post(message, "https://example.com/start")
    sent = {(r.url.host, r.url.path): r for r in requests if r.method == "POST"}

    record = json.loads(sent[("bsky.social", "/xrpc/com.atproto.repo.createRecord")].content)
    facet = record["record"]["facets"][0]
    raw = message.encode()
    assert raw[facet["index"]["byteStart"]:facet["index"]["byteEnd"]] == b"https://example.com/start"
    assert record["repo"] == "did:plc:abc"

    mastodon = sent[("mastodon.social", "/api/v1/statuses")]
    assert mastodon.headers["Authorization"] == "Bearer mastodon-token"
    assert b"visibility=public" in mastodon.content

    discord = sent[("discord.com", "/api/webhooks/1/token")]
    assert discord.url.params["wait"] == "true"
    assert json.loads(discord.content)["allowed_mentions"] == {"parse": []}

    article = json.loads(sent[("dev.to", "/api/articles")].content)["article"]
    assert article["title"] == "Grow your shop online ✨ today"
    assert article["published"] is True and article["tags"] == ["business", "marketing"]

    gist = json.loads(sent[("api.github.com", "/gists")].content)
    assert gist["public"] is True


def test_endpoint_end_to_end(settings):
    app.dependency_overrides[get_posting_service] = lambda: service_with(
        settings, {"mastodon.social": httpx.Response(503, text="down")}
    )
    try:
        response = TestClient(app).post("/posting", json={"message": VALID_MESSAGE})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert set(body["results"][0]) == {"platform", "status", "posted_url", "public_access", "date", "time", "error"}
    mastodon = next(r for r in body["results"] if r["platform"] == "Mastodon")
    assert mastodon == {"platform": "Mastodon", "status": "failed", "posted_url": None, "public_access": False,
                        "date": None, "time": None, "error": "HTTP 503: Service Unavailable"}


def test_success_is_false_when_every_platform_fails():
    settings = configured_settings(enabled_platforms="mastodon,devto", mastodon_access_token=None, devto_api_key=None)
    app.dependency_overrides[get_posting_service] = lambda: service_with(settings)
    try:
        body = TestClient(app).post("/posting", json={"message": VALID_MESSAGE}).json()
    finally:
        app.dependency_overrides.clear()
    assert body["success"] is False
    assert all(r["status"] == "failed" for r in body["results"])
