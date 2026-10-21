"""
Application configuration for Bidstanza.

All runtime settings are read from environment variables (and a local `.env` file)
using pydantic-settings, which validates and type-converts each value at startup.
A misconfigured deployment therefore fails fast with a clear error, rather than
breaking later in the middle of a request. Settings are exposed through the cached
`get_settings()` function so the `.env` file is parsed exactly once per process,
and so tests can override values by clearing the cache.
"""

from datetime import timedelta
from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed view over the environment. Field names map to UPPER_CASE env vars."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # unrelated env vars on the machine shouldn't crash startup
    )

    # --- database ---
    database_url: str
    test_database_url: str | None = None
    db_pool_size: int = Field(default=10, ge=1)
    db_max_overflow: int = Field(default=20, ge=0)
    db_pool_timeout: int = Field(default=30, ge=1)  # seconds to wait for a free connection

    # --- auth ---
    jwt_secret: SecretStr  # required; SecretStr keeps it out of logs and reprs
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(default=60, ge=1)

    # --- auction engine ---
    soft_close_window_s: int = Field(default=60, ge=0)
    soft_close_extension_s: int = Field(default=60, ge=0)
    settle_interval_s: float = Field(default=1.0, gt=0)
    ws_send_timeout_s: float = Field(default=2.0, gt=0)

    @property
    def soft_close_window(self) -> timedelta:
        """A bid arriving within this long of `ends_at` triggers an extension."""
        return timedelta(seconds=self.soft_close_window_s)

    @property
    def soft_close_extension(self) -> timedelta:
        """How far past 'now' `ends_at` is pushed when a soft-close bid lands."""
        return timedelta(seconds=self.soft_close_extension_s)

    @property
    def access_token_ttl(self) -> timedelta:
        """Lifetime of a JWT access token."""
        return timedelta(minutes=self.access_token_expire_minutes)


@lru_cache
def get_settings() -> Settings:
    """Build Settings once and reuse it. Tests can call `get_settings.cache_clear()`."""
    return Settings()
