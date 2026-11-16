import pytest
from fastapi.testclient import TestClient

from app.main import app, get_posting_service
from app.schemas import PlatformResult
from tests.conftest import VALID_MESSAGE


class StubService:
    """Fake service, just records calls."""

    def __init__(self) -> None:
        self.calls = []
        self.platforms = []

    async def post(self, message, url):
        self.calls.append((message, url))
        return [PlatformResult(platform="Stub", status="success", posted_url="https://x.test/1", public_access=True,
                               date="2026-11-15", time="10:30:00")]


@pytest.fixture
def stub():
    service = StubService()
    app.dependency_overrides[get_posting_service] = lambda: service
    yield service
    app.dependency_overrides.clear()


@pytest.fixture
def client(stub):
    return TestClient(app)


def errors_of(response):
    assert response.status_code == 422, response.text
    body = response.json()
    assert body["success"] is False
    return " ".join(e["error"] for e in body["errors"])


def test_valid_message_is_accepted_and_link_extracted(client, stub):
    response = client.post("/posting", json={"message": VALID_MESSAGE})
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert stub.calls == [(VALID_MESSAGE, "https://example.com")]


def test_trailing_punctuation_is_not_part_of_the_link(client, stub):
    client.post("/posting", json={"message": "Visit us today at https://example.com/offer."})
    assert stub.calls[0][1] == "https://example.com/offer"


def test_exactly_200_characters_is_allowed(client):
    link = " https://example.com"
    message = "a" * (200 - len(link)) + link
    assert len(message) == 200
    assert client.post("/posting", json={"message": message}).status_code == 200


def test_more_than_200_characters_is_rejected(client):
    message = "a" * 190 + " https://example.com"
    assert "must not exceed 200 characters" in errors_of(client.post("/posting", json={"message": message}))


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("No link in this message at all", "exactly one CTA link"),
        ("Two links https://example.com and https://example.org", "found 2"),
        ("Visit www.example.com for more", "must start with http:// or https://"),
        ("Download ftp://example.com/file now", "must use http:// or https://"),
        ("Bad domain https://localhost:8000/x here", "valid domain name"),
        ("IP link https://192.168.1.10/x here", "not an IP address"),
        ("Odd host https://exa_mple.com here", "valid domain name"),
        ("Bad port https://example.com:99999/x here", "invalid port"),
        ("Creds https://user:pass@example.com here", "username or password"),
        ("https://example.com", "some text besides the link"),
        ("   ", "must not be empty"),
    ],
)
def test_invalid_messages_are_rejected(client, stub, message, expected):
    assert expected in errors_of(client.post("/posting", json={"message": message}))
    assert stub.calls == []


def test_missing_message_field(client):
    body = client.post("/posting", json={}).json()
    assert body["errors"] == [{"field": "message", "error": "This field is required."}]


def test_wrong_type(client):
    assert "valid string" in errors_of(client.post("/posting", json={"message": 123}))


def test_invalid_json(client):
    response = client.post("/posting", content=b"{not json", headers={"Content-Type": "application/json"})
    assert "not valid JSON" in errors_of(response)
