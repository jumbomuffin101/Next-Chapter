"""Small, mockable Resend adapter using the existing httpx dependency."""
from dataclasses import dataclass
import os
import re

import httpx

from .content import application_url
from .links import frontend_url, require_public_https
from .security import signing_key


@dataclass(frozen=True)
class Settings:
    dry_run: bool
    app_url: str
    api_url: str
    sender_email: str
    sender_name: str
    sender_address: str
    allowlist: frozenset[str]
    api_key: str

    @classmethod
    def load(cls):
        return cls(os.getenv("NEWSLETTER_DRY_RUN", "true").lower() != "false",
                   frontend_url(),
                   application_url(os.getenv("NEWSLETTER_PUBLIC_API_URL", "http://localhost:8000")),
                   os.getenv("NEWSLETTER_FROM_EMAIL", ""), os.getenv("NEWSLETTER_FROM_NAME", "The Knowledge House"),
                   os.getenv("NEWSLETTER_POSTAL_ADDRESS", ""),
                   frozenset(e.strip().lower() for e in os.getenv("NEWSLETTER_DEMO_RECIPIENTS", "").split(",") if e.strip()),
                   os.getenv("RESEND_API_KEY", ""))

    def validate_live(self, recipient):
        signing_key()
        if len(os.getenv("ADMIN_TOKEN_SECRET", "")) < 32 or len(os.getenv("ADMIN_PASSWORD", "")) < 12:
            raise ValueError("Configure strong admin authentication before enabling demo email delivery")
        if not self.api_key or not self.sender_address.strip() or not email_valid(self.sender_email):
            raise ValueError("Configure the email provider, verified sender, and sender postal address before delivery")
        if not self.sender_name.strip() or any(c in self.sender_name + self.sender_address for c in "\r\n"):
            raise ValueError("Invalid sender configuration")
        require_public_https(self.app_url)
        require_public_https(self.api_url)
        if recipient.lower() not in self.allowlist:
            raise PermissionError("Recipient is not in the explicit synthetic-demo delivery allowlist")


def email_valid(value):
    return bool(re.fullmatch(r"[^@\s<>]+@[^@\s<>]+\.[^@\s<>]+", value or ""))


@dataclass(frozen=True)
class Message:
    recipient: str
    sender: str
    subject: str
    html: str
    text: str
    unsubscribe_url: str
    idempotency_key: str


class ProviderFailure(Exception):
    def __init__(self, code: str, *, retryable=False, uncertain=False):
        super().__init__(code)  # Never retain provider bodies, email addresses, or credential-bearing exceptions.
        self.code, self.retryable, self.uncertain = code, retryable, uncertain


class ResendAdapter:
    def __init__(self, api_key: str, *, client=None):
        self.api_key = api_key
        self.client = client

    def send(self, message: Message) -> str:
        payload = {"from": message.sender, "to": [message.recipient], "subject": message.subject,
                   "html": message.html, "text": message.text,
                   "headers": {"List-Unsubscribe": f"<{message.unsubscribe_url}>",
                               "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"}}
        headers = {"Authorization": f"Bearer {self.api_key}", "Idempotency-Key": message.idempotency_key}
        try:
            if self.client is None:
                with httpx.Client(timeout=20, follow_redirects=False) as client:
                    response = client.post("https://api.resend.com/emails", json=payload, headers=headers)
            else:
                response = self.client.post("https://api.resend.com/emails", json=payload, headers=headers)
        except httpx.RequestError:
            raise ProviderFailure("provider_network_unknown", uncertain=True) from None
        if response.status_code == 429:
            raise ProviderFailure("provider_rate_limited", retryable=True)
        if response.status_code >= 500:
            raise ProviderFailure("provider_server_unknown", uncertain=True)
        if response.status_code not in (200, 201):
            raise ProviderFailure("provider_rejected")
        try:
            identifier = response.json()["id"]
            if not isinstance(identifier, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,255}", identifier):
                raise ValueError
            return identifier
        except (ValueError, KeyError, TypeError):
            raise ProviderFailure("provider_response_unknown", uncertain=True) from None
