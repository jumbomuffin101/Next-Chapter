"""Offline configuration tests: synthetic credentials and mocked connections only."""
from pathlib import Path
from unittest.mock import patch

import pytest

from work.database import config
from backend.app.db import get_conn


@pytest.mark.parametrize("scheme", ["postgresql", "postgresql+psycopg", "postgres"])
def test_postgres_urls_use_psycopg_and_preserve_options(monkeypatch, scheme):
    monkeypatch.setenv(
        "DATABASE_URL",
        f"{scheme}://demo:p%40ss%3Aword%2F%25@localhost:5432/tkh"
        "?sslmode=require&application_name=tkh-check",
    )
    assert config.get_database_url().drivername == "postgresql+psycopg"
    with patch("backend.app.db.psycopg.connect") as connect:
        get_conn()
    args, kwargs = connect.call_args
    assert args == ()
    assert kwargs["user"] == "demo"
    assert kwargs["password"] == "p@ss:word/%"
    assert kwargs["dbname"] == "tkh"
    assert kwargs["sslmode"] == "require"
    assert kwargs["application_name"] == "tkh-check"
    assert kwargs["connect_timeout"] == 10


def test_external_url_wins_over_database_dotenv(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://demo:synthetic@localhost/external")
    with patch.object(config, "load_dotenv", wraps=config.load_dotenv) as load:
        url = config.get_database_url()
    load.assert_called_once_with(dotenv_path=config.ENV_PATH, override=False)
    assert url.database == "external"
    assert config.ENV_PATH == Path(__file__).resolve().parents[2] / "work/database/.env"


def test_missing_url_has_clear_error_without_loading_real_dotenv(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with patch.object(config, "load_dotenv"):
        with pytest.raises(RuntimeError, match="DATABASE_URL is required"):
            config.get_database_url()


@pytest.mark.parametrize("value", ["synthetic-secret-not-a-url", "postgresql://demo:synthetic@localhost:bad/tkh"])
def test_invalid_urls_do_not_appear_in_errors(monkeypatch, value):
    monkeypatch.setenv("DATABASE_URL", value)
    with pytest.raises(RuntimeError) as caught:
        config.get_database_url()
    assert value not in str(caught.value)
    assert "synthetic" not in str(caught.value)


def test_sqlite_stays_available_for_offline_schema_generation(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    assert config.get_database_url().drivername == "sqlite"
    with patch("backend.app.db.psycopg.connect") as connect:
        with pytest.raises(RuntimeError, match="requires PostgreSQL"):
            get_conn()
    connect.assert_not_called()
