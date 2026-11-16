"""Platform registry. New platforms get added to REGISTRY."""

import logging

from app.platforms.base import Platform, PlatformError, PublishResult
from app.platforms.bluesky import BlueskyPlatform
from app.platforms.devto import DevtoPlatform
from app.platforms.discord import DiscordPlatform
from app.platforms.github_gist import GithubGistPlatform
from app.platforms.mastodon import MastodonPlatform
from app.platforms.telegram import TelegramPlatform

logger = logging.getLogger(__name__)

REGISTRY: dict[str, type[Platform]] = {
    "bluesky": BlueskyPlatform,
    "mastodon": MastodonPlatform,
    "telegram": TelegramPlatform,
    "discord": DiscordPlatform,
    "devto": DevtoPlatform,
    "github_gist": GithubGistPlatform,
}


def build_platforms(settings) -> list[Platform]:
    """Platforms from ENABLED_PLATFORMS, in that order."""
    platforms = []
    for name in settings.enabled_platform_names:
        cls = REGISTRY.get(name)
        if cls is None:
            logger.warning("Unknown platform %r in ENABLED_PLATFORMS (known: %s)", name, ", ".join(REGISTRY))
            continue
        platforms.append(cls(settings))
    return platforms


__all__ = ["Platform", "PlatformError", "PublishResult", "REGISTRY", "build_platforms"]
