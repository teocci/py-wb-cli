"""Application settings loaded from environment variables and .env files.

Uses pydantic-settings to provide validated, typed configuration with
automatic environment variable binding via the ``WB_`` prefix.
"""

__all__ = ['Settings']

from pathlib import Path
from threading import Lock
from typing import ClassVar

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from wb.core.constants import (
    CONFIG_DIR_NAME,
    DEFAULT_MAX_RETRIES,
    DEFAULT_PROFILE_NAME,
    DEFAULT_RETRY_BASE_DELAY,
    DEFAULT_TIMEOUT,
)
from wb.domain.enums import OutputFormat, VerbosityLevel


class Settings(BaseSettings):
    """Global CLI settings sourced from environment and ``.env`` files.

    Attributes:
        active_profile: Name of the active credential profile.
        config_dir: Directory for CLI configuration and audit logs.
        api_timeout: HTTP request timeout in seconds.
        max_retries: Maximum number of retry attempts for failed requests.
        retry_base_delay: Base delay in seconds for exponential backoff.
        output_format: Default output rendering format.
        verbosity: Default verbosity level.
    """

    model_config = SettingsConfigDict(
        env_prefix='WB_',
        env_file='.env',
        env_file_encoding='utf-8',
        extra='ignore',
    )

    active_profile: str = DEFAULT_PROFILE_NAME
    config_dir: Path = Field(
        default_factory=lambda: Path.home() / CONFIG_DIR_NAME,
    )
    api_timeout: float = DEFAULT_TIMEOUT
    max_retries: int = DEFAULT_MAX_RETRIES
    retry_base_delay: float = DEFAULT_RETRY_BASE_DELAY
    output_format: OutputFormat = OutputFormat.TABLE
    verbosity: VerbosityLevel = VerbosityLevel.NORMAL

    # ── Singleton ──────────────────────────────────────────────────────
    _instance: ClassVar['Settings | None'] = None
    _lock: ClassVar[Lock] = Lock()

    @classmethod
    def get_settings(cls) -> 'Settings':
        """Return the singleton Settings instance, creating it on first call.

        Returns:
            The shared Settings instance.
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    # ── Helpers ────────────────────────────────────────────────────────
    def ensure_config_dir(self) -> Path:
        """Create the configuration directory if it does not exist.

        Returns:
            The resolved configuration directory path.
        """
        self.config_dir.mkdir(parents=True, exist_ok=True)
        return self.config_dir
