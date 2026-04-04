"""Factory functions for creating service instances from CLI context."""

from __future__ import annotations

from wb.auth.profiles import ProfileStore
from wb.client.http import WbHttpClient
from wb.client.promotion import PromotionClient
from wb.core.config import Settings
from wb.core.constants import ANALYTICS_BASE_URL, PROMOTION_BASE_URL, STATISTICS_BASE_URL
from wb.storage.audit import AuditLogger

__all__ = [
    'create_promotion_client',
    'create_portal_client',
    'create_audit_logger',
    'create_campaign_service',
    'create_budget_service',
    'create_stats_service',
    'create_cluster_service',
    'create_bid_service',
    'create_analytics_client',
    'create_analytics_service',
    'create_optimizer_service',
    'create_cache_store',
    'create_cache_service',
    'create_reports_client',
    'create_reports_service',
    'create_statistics_client',
    'create_stock_runway_service',
]


def _get_promotion_token(
        profile_name: str | None = None,
        cli_token: str | None = None,
) -> str:
    """Retrieve the promotion token using the unified priority chain.

    Priority: CLI flag > WB_API_TOKEN env var/.env > profiles.json

    Args:
        profile_name: Profile name, or None for active profile.
        cli_token: Token passed via CLI flag (highest priority).

    Returns:
        Promotion API token string.
    """
    if cli_token:
        return cli_token
    settings = Settings()
    if settings.api_token:
        return settings.api_token
    settings.ensure_config_dir()
    store = ProfileStore(settings.config_dir)
    profile = store.get_profile(profile_name)
    return profile.get_token('promotion')


def create_portal_client(
        profile_name: str | None = None,
        cli_authorizev3: str | None = None,
        cli_cookie: str | None = None,
):
    """Create a PortalClient using the unified priority chain.

    Priority: CLI flags > WB_AUTHORIZEV3/WB_PORTAL_COOKIE env vars/.env > profiles.json

    Both authorizev3 and cookie are required for portal auth.

    Args:
        profile_name: Profile name, or None for active profile.
        cli_authorizev3: authorizev3 value from CLI flag (highest priority).
        cli_cookie: Cookie from CLI flag (highest priority).

    Returns:
        Configured PortalClient instance.

    Raises:
        ConfigError: If no portal credentials found at any level.
        ValidationError: If cookie is missing (required for portal auth).
    """
    from wb.client.portal import PortalClient
    from wb.core.exceptions import ConfigError

    # Priority 1: CLI flags
    if cli_authorizev3 and cli_cookie:
        return PortalClient(authorizev3=cli_authorizev3, cookie=cli_cookie)

    # Priority 2: Env vars / .env (handled by pydantic-settings)
    settings = Settings()
    if settings.authorizev3 and settings.portal_cookie:
        return PortalClient(
            authorizev3=settings.authorizev3,
            cookie=settings.portal_cookie,
        )

    # Priority 3: profiles.json
    settings.ensure_config_dir()
    store = ProfileStore(settings.config_dir)
    profile = store.get_profile(profile_name)
    session = profile.get_portal_session()
    if not session:
        raise ConfigError(
            'No portal credentials found. Set WB_AUTHORIZEV3 + WB_PORTAL_COOKIE '
            'env vars, add them to .env, or run `wb auth login-portal`.'
        )
    cookie = session.get('cookie')
    if not cookie:
        raise ConfigError(
            'Portal cookie is missing from profile. Both authorizev3 and cookie '
            'are required. Re-run `wb auth login-portal` with --cookie.'
        )
    return PortalClient(
        authorizev3=session['authorizev3'],
        cookie=cookie,
    )


def create_audit_logger(profile_name: str | None = None) -> AuditLogger:
    """Create an AuditLogger using the current profile's config directory.

    Args:
        profile_name: Profile name, or None for active profile.

    Returns:
        Configured AuditLogger instance.
    """
    settings = Settings()
    settings.ensure_config_dir()
    return AuditLogger(settings.config_dir)


def create_promotion_client(
        profile_name: str | None = None,
) -> PromotionClient:
    """Create a PromotionClient using the given or active profile's token.

    Args:
        profile_name: Profile name, or None for active profile.

    Returns:
        Configured PromotionClient instance.
    """
    token = _get_promotion_token(profile_name)
    http = WbHttpClient(base_url=PROMOTION_BASE_URL, token=token)
    return PromotionClient(http)


def create_campaign_service(profile_name: str | None = None):
    """Create a CampaignService from profile credentials.

    Args:
        profile_name: Profile name, or None for active profile.
    """
    from wb.services.campaigns import CampaignService
    return CampaignService(create_promotion_client(profile_name))


def create_budget_service(profile_name: str | None = None):
    """Create a BudgetService from profile credentials.

    Args:
        profile_name: Profile name, or None for active profile.
    """
    from wb.services.budgets import BudgetService
    return BudgetService(create_promotion_client(profile_name))


def create_stats_service(profile_name: str | None = None):
    """Create a StatsService from profile credentials.

    Args:
        profile_name: Profile name, or None for active profile.
    """
    from wb.services.stats import StatsService
    return StatsService(create_promotion_client(profile_name))


def create_cluster_service(profile_name: str | None = None):
    """Create a ClusterService from profile credentials.

    Args:
        profile_name: Profile name, or None for active profile.
    """
    from wb.services.clusters import ClusterService
    return ClusterService(create_promotion_client(profile_name))


def create_bid_service(profile_name: str | None = None):
    """Create a BidService from profile credentials.

    Args:
        profile_name: Profile name, or None for active profile.
    """
    from wb.services.bids import BidService
    return BidService(create_promotion_client(profile_name))


# ── Analytics factories ──────────────────────────────────────────────


def _get_analytics_token(
        profile_name: str | None = None,
        cli_token: str | None = None,
) -> str:
    """Retrieve the analytics token using the unified priority chain.

    Priority: CLI flag > WB_ANALYTICS_TOKEN env var/.env > profiles.json

    Args:
        profile_name: Profile name, or None for active profile.
        cli_token: Token passed via CLI flag (highest priority).

    Returns:
        Analytics API token string.
    """
    if cli_token:
        return cli_token
    settings = Settings()
    if settings.analytics_token:
        return settings.analytics_token
    if settings.api_token:
        return settings.api_token
    settings.ensure_config_dir()
    store = ProfileStore(settings.config_dir)
    profile = store.get_profile(profile_name)
    return profile.get_token('analytics')


def create_analytics_client(
        profile_name: str | None = None,
):
    """Create an AnalyticsClient from profile credentials.

    Args:
        profile_name: Profile name, or None for active profile.

    Returns:
        Configured AnalyticsClient instance.
    """
    from wb.client.analytics import AnalyticsClient
    token = _get_analytics_token(profile_name)
    http = WbHttpClient(base_url=ANALYTICS_BASE_URL, token=token)
    return AnalyticsClient(http)


def create_analytics_service(profile_name: str | None = None):
    """Create an AnalyticsService from profile credentials.

    Args:
        profile_name: Profile name, or None for active profile.
    """
    from wb.services.analytics import AnalyticsService
    return AnalyticsService(create_analytics_client(profile_name))


def create_optimizer_service(profile_name: str | None = None):
    """Create an OptimizerService with all required sub-services.

    Args:
        profile_name: Profile name, or None for active profile.
    """
    from wb.services.optimizer import OptimizerService
    client = create_promotion_client(profile_name)
    return OptimizerService(
        campaign_svc=_lazy_campaign(client),
        bid_svc=_lazy_bid(client),
        cluster_svc=_lazy_cluster(client),
        stats_svc=_lazy_stats(client),
        budget_svc=_lazy_budget(client),
    )


def _lazy_campaign(client):
    from wb.services.campaigns import CampaignService
    return CampaignService(client)


def _lazy_bid(client):
    from wb.services.bids import BidService
    return BidService(client)


def _lazy_cluster(client):
    from wb.services.clusters import ClusterService
    return ClusterService(client)


def _lazy_stats(client):
    from wb.services.stats import StatsService
    return StatsService(client)


def _lazy_budget(client):
    from wb.services.budgets import BudgetService
    return BudgetService(client)


# ── Reports factories ────────────────────────────────────────────────


def create_reports_client(profile_name: str | None = None):
    """Create a ReportsClient from profile credentials.

    Args:
        profile_name: Profile name, or None for active profile.

    Returns:
        Configured ReportsClient instance.
    """
    from wb.client.reports import ReportsClient
    token = _get_analytics_token(profile_name)
    http = WbHttpClient(base_url=ANALYTICS_BASE_URL, token=token)
    return ReportsClient(http)


def create_reports_service(profile_name: str | None = None):
    """Create a ReportsService from profile credentials.

    Args:
        profile_name: Profile name, or None for active profile.

    Returns:
        Configured ReportsService instance.
    """
    from wb.services.reports import ReportsService
    return ReportsService(create_reports_client(profile_name))


def create_statistics_client(profile_name: str | None = None):
    """Create a StatisticsClient using the analytics token.

    Args:
        profile_name: Profile name, or None for active profile.

    Returns:
        Configured StatisticsClient instance.
    """
    from wb.client.statistics import StatisticsClient
    token = _get_analytics_token(profile_name)
    http = WbHttpClient(base_url=STATISTICS_BASE_URL, token=token)
    return StatisticsClient(http)


def create_stock_runway_service(profile_name: str | None = None):
    """Create a ReportsService with a StatisticsClient for runway computation.

    Args:
        profile_name: Profile name, or None for active profile.

    Returns:
        Configured ReportsService with statistics_client injected.
    """
    from wb.services.reports import ReportsService
    reports_client = create_reports_client(profile_name)
    stats_client = create_statistics_client(profile_name)
    return ReportsService(reports_client, stats_client)


# ── Cache factories ───────────────────────────────────────────────────


def create_cache_store(profile_name: str | None = None):
    """Create a CacheStore pointed at the profile config directory.

    Args:
        profile_name: Profile name (unused for path resolution; config_dir
            is global per settings).

    Returns:
        Configured CacheStore instance.
    """
    from wb.core.constants import CACHE_DB_FILE
    from wb.storage.cache import CacheStore
    settings = Settings()
    settings.ensure_config_dir()
    return CacheStore(settings.config_dir / CACHE_DB_FILE)


def create_cache_service(profile_name: str | None = None):
    """Create a CacheService with all required sub-services.

    Args:
        profile_name: Profile name, or None for active profile.

    Returns:
        Configured CacheService instance.
    """
    from wb.services.cache import CacheService
    store = create_cache_store(profile_name)
    client = create_promotion_client(profile_name)
    return CacheService(
        store=store,
        campaign_svc=_lazy_campaign(client),
        stats_svc=_lazy_stats(client),
        cluster_svc=_lazy_cluster(client),
    )
