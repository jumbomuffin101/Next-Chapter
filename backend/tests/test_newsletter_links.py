"""Offline link regression checks; no database or email access."""
from html.parser import HTMLParser
import os
from pathlib import Path
import subprocess
import sys
from urllib.parse import urljoin

import pytest
from backend.app.newsletter.links import frontend_url, require_public_https
from backend.app.newsletter.preview import demo_newsletter
from backend.app.newsletter.provider import Settings
from backend.app.newsletter.render import render


class Links(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.hrefs = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.hrefs.append(dict(attrs)["href"])


def test_local_file_links_and_plain_text(monkeypatch):
    monkeypatch.delenv("NEWSLETTER_APP_URL", raising=False)
    newsletter = demo_newsletter()
    urls = Links(newsletter.html).hrefs
    assert frontend_url() == "http://localhost:5173/"
    assert "Open Next Chapter Dashboard</a>" in newsletter.html
    assert "Open Next Chapter Dashboard: http://localhost:5173/" in newsletter.text
    for suffix in ("", "?section=jobs", "?section=events", "?section=profile"):
        url = "http://localhost:5173/" + suffix
        assert url in urls
        assert urljoin("file:///C:/previews/newsletter.html", url) == url
    assert all(url.startswith(("https://", "http://")) for url in urls)


def test_shared_environment_and_override(monkeypatch):
    monkeypatch.setenv("NEWSLETTER_APP_URL", "https://app.example.org")
    assert Settings.load().app_url == demo_newsletter().content.app_url == "https://app.example.org/"
    assert demo_newsletter(app_url="http://localhost:5173").content.app_url == "http://localhost:5173/"


@pytest.mark.parametrize("module,extra,filename", [
    ("preview", [], "next-chapter-monthly.html"),
    ("monthly", ["--preview", "--month", "2026-10"], "next-chapter-2026-10.html"),
])
def test_cli_previews_use_environment_without_database(tmp_path, module, extra, filename):
    env = {**os.environ, "NEWSLETTER_APP_URL": "https://app.example.org", "DATABASE_URL": "invalid-offline"}
    result = subprocess.run([sys.executable, "-B", "-m", f"backend.app.newsletter.{module}",
                             *extra, "--output-dir", str(tmp_path)],
                            cwd=Path(__file__).resolve().parents[2], env=env, capture_output=True)
    assert result.returncode == 0
    assert 'href="https://app.example.org/"' in (tmp_path / filename).read_text(encoding="utf-8")


@pytest.mark.parametrize("url", ["http://app.example.org", "https://localhost", "https://sub.localhost",
    "https://localhost.", "https://127.0.0.1", "https://10.0.0.1", "https://192.168.1.1",
    "https://[::1]", "https://[fc00::1]", "https://app.local", "https://intranet",
    "https://user:password@app.example.org", "javascript:alert(1)"])
def test_delivery_rejects_nonpublic_or_unsafe_urls(url):
    with pytest.raises(ValueError):
        require_public_https(url)


def test_public_url_and_live_unsubscribe_preserved():
    require_public_https("https://app.example.org/")
    url = "https://api.example.org/newsletter/unsubscribe?token=synthetic-test-token"
    newsletter = render(demo_newsletter().content, unsubscribe_url=url, preview=False)
    assert url in Links(newsletter.html).hrefs
    assert f"Unsubscribe: {url}" in newsletter.text
