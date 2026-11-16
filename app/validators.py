"""Validation for the posting message and its CTA link."""

import ipaddress
import re
from urllib.parse import urlsplit

MAX_MESSAGE_LENGTH = 200

# matches scheme://... and bare www. links
_LINK_PATTERN = re.compile(r"(?i)(?:\b[a-z][a-z0-9+.-]*://|\bwww\.)[^\s<>\"']+")
_TRAILING_PUNCTUATION = ".,;:!?)]}'\""
_HOST_LABEL = re.compile(r"^(?!-)[a-z0-9-]{1,63}(?<!-)$", re.IGNORECASE)
_TLD = re.compile(r"^(?:[a-z]{2,63}|xn--[a-z0-9-]{1,59})$", re.IGNORECASE)


def find_links(message: str) -> list[str]:
    """All links found in the message (trailing punctuation stripped)."""
    return [match.group(0).rstrip(_TRAILING_PUNCTUATION) for match in _LINK_PATTERN.finditer(message)]


def validate_cta_url(url: str) -> str | None:
    """Returns an error string, or None if the URL is ok."""
    if url.lower().startswith("www."):
        return f"The link '{url}' must start with http:// or https://."

    parts = urlsplit(url)
    if parts.scheme.lower() not in {"http", "https"}:
        return f"The link '{url}' must use http:// or https://."

    try:
        host = parts.hostname
        parts.port  # ValueError if port is out of range
    except ValueError:
        return f"The link '{url}' has an invalid port."

    if not host:
        return f"The link '{url}' has no domain name."
    if parts.username or parts.password:
        return f"The link '{url}' must not contain a username or password."

    try:
        ipaddress.ip_address(host)
        return f"The link '{url}' must use a domain name, not an IP address."
    except ValueError:
        pass

    labels = host.rstrip(".").split(".")
    if len(labels) < 2 or len(host) > 253:
        return f"The link '{url}' does not have a valid domain name."
    if not all(_HOST_LABEL.match(label) for label in labels) or not _TLD.match(labels[-1]):
        return f"The link '{url}' does not have a valid domain name."

    return None


def validate_message(message: str) -> tuple[str, str]:
    """Returns (message, cta_url). Raises ValueError on invalid input."""
    cleaned = message.strip()
    if not cleaned:
        raise ValueError("Message must not be empty.")
    if len(cleaned) > MAX_MESSAGE_LENGTH:
        raise ValueError(
            f"Message must not exceed {MAX_MESSAGE_LENGTH} characters (got {len(cleaned)})."
        )

    links = find_links(cleaned)
    if not links:
        raise ValueError("Message must include exactly one CTA link (http:// or https://).")
    if len(links) > 1:
        raise ValueError(f"Message must include exactly one CTA link (found {len(links)}).")

    error = validate_cta_url(links[0])
    if error:
        raise ValueError(error)

    if cleaned.replace(links[0], "").strip() == "":
        raise ValueError("Message must contain some text besides the link.")

    return cleaned, links[0]
