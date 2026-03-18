"""Tests for wb.core.config module."""

import pytest

from wb.core.config import Settings
from wb.domain.enums import OutputFormat, VerbosityLevel


@pytest.fixture(autouse=True)
def _reset_singleton() -> None:
    """Reset the Settings singleton between tests."""
    Settings._instance = None


class TestSettingsDefaults:
    """Tests for Settings default values."""

    def test_active_profile_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv('WB_ACTIVE_PROFILE', raising=False)
        settings = Settings()
        assert settings.active_profile == 'default'

    def test_api_timeout_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv('WB_API_TIMEOUT', raising=False)
        settings = Settings()
        assert settings.api_timeout == 30.0

    def test_max_retries_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv('WB_MAX_RETRIES', raising=False)
        settings = Settings()
        assert settings.max_retries == 3

    def test_retry_base_delay_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv('WB_RETRY_BASE_DELAY', raising=False)
        settings = Settings()
        assert settings.retry_base_delay == 1.0

    def test_output_format_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv('WB_OUTPUT_FORMAT', raising=False)
        settings = Settings()
        assert settings.output_format == OutputFormat.TABLE

    def test_verbosity_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv('WB_VERBOSITY', raising=False)
        settings = Settings()
        assert settings.verbosity == VerbosityLevel.NORMAL


class TestSettingsOverride:
    """Tests for overriding Settings via constructor."""

    def test_override_active_profile(self) -> None:
        settings = Settings(active_profile='staging')
        assert settings.active_profile == 'staging'

    def test_override_api_timeout(self) -> None:
        settings = Settings(api_timeout=60.0)
        assert settings.api_timeout == 60.0

    def test_override_output_format(self) -> None:
        settings = Settings(output_format=OutputFormat.JSON)
        assert settings.output_format == OutputFormat.JSON


class TestEnsureConfigDir:
    """Tests for Settings.ensure_config_dir."""

    def test_creates_directory(self, tmp_path: pytest.TempPathFactory) -> None:
        config_dir = tmp_path / '.wb-cli'
        settings = Settings(config_dir=config_dir)
        result = settings.ensure_config_dir()
        assert config_dir.is_dir()
        assert result == config_dir

    def test_idempotent(self, tmp_path: pytest.TempPathFactory) -> None:
        config_dir = tmp_path / '.wb-cli'
        settings = Settings(config_dir=config_dir)
        settings.ensure_config_dir()
        settings.ensure_config_dir()
        assert config_dir.is_dir()
