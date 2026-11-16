"""GitHub Gists API (public gist).

Docs: https://docs.github.com/en/rest/gists/gists#create-a-gist
"""

import httpx

from app.platforms.base import Platform, PlatformError, PublishResult, headline


class GithubGistPlatform(Platform):
    name = "GitHub Gist"
    required_settings = ("gist_token",)

    async def publish(self, client: httpx.AsyncClient, message: str, url: str) -> PublishResult:
        body = self.ensure_ok(
            await client.post(
                "https://api.github.com/gists",
                headers={
                    "Authorization": f"Bearer {self.settings.gist_token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                json={
                    "description": headline(message, url),
                    "public": True,
                    "files": {"announcement.md": {"content": message + "\n"}},
                },
            )
        )
        posted_url = body.get("html_url")
        if not posted_url:
            raise PlatformError("Gist was created but no URL was returned.")
        return PublishResult(posted_url=posted_url, public=bool(body.get("public")))
