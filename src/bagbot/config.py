"""Configuration loading for bagbot.

Settings come from environment variables, optionally backed by a local
``.env`` file (see ``.env.example``). Secrets are never hardcoded.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

_TRUE_VALUES = {"1", "true", "yes", "on"}

DEFAULT_KRAKEN_BASE_URL = "https://api.kraken.com"


def parse_bool(value: str | None, default: bool) -> bool:
    """Parse a truthy/falsy env var string, falling back to ``default``."""
    if value is None:
        return default
    return value.strip().lower() in _TRUE_VALUES


@dataclass(frozen=True)
class Settings:
    """Runtime settings for the bot."""

    api_key: str | None = None
    api_secret: str | None = None
    dry_run: bool = True
    base_url: str = DEFAULT_KRAKEN_BASE_URL

    @property
    def has_credentials(self) -> bool:
        return bool(self.api_key) and bool(self.api_secret)


def load_settings(env_file: str | None = ".env", environ: dict | None = None) -> Settings:
    """Build :class:`Settings` from the environment (and optional .env file).

    Pass ``environ`` (and ``env_file=None``) in tests to avoid touching the
    real process environment.
    """
    if env_file:
        load_dotenv(env_file)
    env = os.environ if environ is None else environ
    return Settings(
        api_key=env.get("KRAKEN_API_KEY") or None,
        api_secret=env.get("KRAKEN_API_SECRET") or None,
        dry_run=parse_bool(env.get("BAGBOT_DRY_RUN"), True),
        base_url=env.get("KRAKEN_BASE_URL", DEFAULT_KRAKEN_BASE_URL).rstrip("/"),
    )
