"""Discord channel webhook.

Docs: https://discord.com/developers/docs/resources/webhook#execute-webhook
"""

import httpx

from app.platforms.base import Platform, PlatformError, PublishResult


class DiscordPlatform(Platform):
    name = "Discord"
    required_settings = ("discord_webhook_url",)

    async def publish(self, client: httpx.AsyncClient, message: str, url: str) -> PublishResult:
        # wait=true -> response includes the created message
        body = self.ensure_ok(
            await client.post(
                self.settings.discord_webhook_url,
                params={"wait": "true"},
                json={"content": message, "allowed_mentions": {"parse": []}},
            )
        )
        message_id, channel_id = body.get("id"), body.get("channel_id")
        if not message_id:
            raise PlatformError("Message was sent but no message id was returned.")

        guild_id = body.get("guild_id") or self.settings.discord_guild_id
        posted_url = (
            f"https://discord.com/channels/{guild_id}/{channel_id}/{message_id}"
            if guild_id and channel_id
            else None
        )
        # only server members can see it, so never public
        return PublishResult(posted_url=posted_url, public=False)
