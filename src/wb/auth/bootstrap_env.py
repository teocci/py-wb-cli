"""Environment-variable bootstrap for ``wb auth login`` / ``login-portal``.

After phase A-2, the runtime credential chain is ``CLI flag → active
profile → ConfigError``. Environment variables (and ``.env`` files) are
no longer consulted by service factories — they only feed
:func:`wb auth login` / :func:`wb auth login-portal` so a first-time user
can register a profile without typing the JWT on the command line.

This module isolates that bootstrap-only role behind a tiny pydantic
settings class. Anything outside of :mod:`wb.cli.auth` that imports
``BootstrapEnv`` is doing it wrong.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ['BootstrapEnv']


class BootstrapEnv(BaseSettings):
    """Bootstrap credentials read from ``WB_*`` env vars / ``.env``.

    Attributes:
        api_token: ``WB_API_TOKEN`` — full-scope JWT, applied to every
            token category when the user runs ``wb auth login`` without
            ``--token``.
        analytics_token: ``WB_ANALYTICS_TOKEN`` — dedicated analytics
            token. When set, ``wb auth login --category analytics``
            (without ``--token``) saves it under the analytics category
            only.
        authorizev3: ``WB_AUTHORIZEV3`` — portal authorizev3 header.
            Used by ``wb auth login-portal`` when ``--authorizev3`` is
            omitted.
        portal_cookie: ``WB_PORTAL_COOKIE`` — portal session cookie.
            Used by ``wb auth login-portal`` when ``--cookie`` is
            omitted.
    """

    model_config = SettingsConfigDict(
        env_prefix='WB_',
        env_file='.env',
        env_file_encoding='utf-8',
        extra='ignore',
    )

    api_token: str | None = None
    analytics_token: str | None = None
    authorizev3: str | None = None
    portal_cookie: str | None = None
