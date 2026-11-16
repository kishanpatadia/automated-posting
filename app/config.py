"""Settings loaded from env vars / .env"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # General
    enabled_platforms: str = Field(
        default="bluesky,mastodon,telegram,discord,devto,github_gist",
        description="Comma-separated list of platforms to post to, in order.",
    )
    request_timeout_seconds: float = 15.0
    timezone: str = "Asia/Kolkata"
    verify_public_access: bool = True

    # Bluesky (AT Protocol)
    bluesky_service: str = "https://bsky.social"
    bluesky_handle: str | None = None
    bluesky_app_password: str | None = None

    # Mastodon
    mastodon_instance_url: str = "https://mastodon.social"
    mastodon_access_token: str | None = None

    # Telegram
    telegram_bot_token: str | None = None
    telegram_channel: str | None = None  # e.g. "@my_public_channel"

    # Discord
    discord_webhook_url: str | None = None
    discord_guild_id: str | None = None  # optional, for the message link

    # DEV Community (Forem)
    devto_api_key: str | None = None
    devto_tags: str = "business,marketing"

    # GitHub Gist
    gist_token: str | None = None

    @property
    def enabled_platform_names(self) -> list[str]:
        return [name.strip().lower() for name in self.enabled_platforms.split(",") if name.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
