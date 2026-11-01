"""Shared newsletter frontend configuration; safe to import in offline previews."""
import ipaddress
import os
from urllib.parse import urlsplit

from .content import application_url

DEFAULT_FRONTEND_URL = "http://localhost:5173/"


def frontend_url(override=None):
    return application_url(override if override is not None else
                           os.getenv("NEWSLETTER_APP_URL", DEFAULT_FRONTEND_URL))


def require_public_https(value):
    """Reject local destinations without making DNS/network calls."""
    parsed = urlsplit(application_url(value))
    host = (parsed.hostname or "").rstrip(".").lower()
    public = False
    try:
        public = ipaddress.ip_address(host).is_global
    except ValueError:
        public = ("." in host and not host.endswith((".localhost", ".local", ".internal", ".test", ".invalid"))
                  and all(part and all(c.isascii() and (c.isalnum() or c == "-") for c in part)
                          and not part.startswith("-") and not part.endswith("-") for part in host.split(".")))
    if parsed.scheme != "https" or not public:
        raise ValueError("Live delivery requires publicly accessible HTTPS URLs")
