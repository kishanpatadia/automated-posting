"""Telegram Bot API (bot must be admin of the channel).

Docs: https://core.telegram.org/bots/api#sendmessage
"""

import httpx

from app.platforms.base import Platform, PlatformError, PublishResult

API_BASE = "https://api.telegram.org"


class TelegramPlatform(Platform):
    name = "Telegram"
    required_settings = ("telegram_bot_token", "telegram_channel")

    async def publish(self, client: httpx.AsyncClient, message: str, url: str) -> PublishResult:
        response = await client.post(
            f"{API_BASE}/bot{self.settings.telegram_bot_token}/sendMessage",
            json={"chat_id": self.settings.telegram_channel, "text": message},
        )
        body = self.ensure_ok(response)
        if not body.get("ok"):
            raise PlatformError(body.get("description") or "Telegram rejected the message.")

        result = body.get("result") or {}
        message_id = result.get("message_id")
        username = (result.get("chat") or {}).get("username")
        if username and message_id:
            # public channel -> t.me link
            return PublishResult(posted_url=f"https://t.me/{username}/{message_id}", public=True)
        # private channel, no public link
        return PublishResult(posted_url=None, public=False)
