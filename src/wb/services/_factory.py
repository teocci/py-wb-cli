"""Factory functions for creating service instances from CLI context."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from wb.auth.profiles import ProfileStore
from wb.client.http import WbHttpClient
from wb.client.promotion import PromotionClient
from wb.core.config import Settings
from wb.core.constants import (
    ANALYTICS_BASE_URL,
    CACHE_DB_FILE,
    DEFAULT_TOKEN_TYPE,
    FINANCE_BASE_URL,
    PRICES_BASE_URL,
    PROMOTION_BASE_URL,
    RATE_LIMIT_DB_FILE,
    RATE_LIMITER_ENV_VAR,
    RATE_LIMITER_MEMORY_VALUE,
    REQUEST_CACHE_DB_FILE,
    REQUEST_CACHE_DISABLED_VALUE,
    REQUEST_CACHE_ENV_VAR,
    RESPONSE_CACHE_DB_FILE,
    RESPONSE_CACHE_RETENTION_DAYS,
    STATISTICS_BASE_URL,
)
from wb.core.exceptions import ConfigError
from wb.storage.audit import AuditLogger
from wb.storage.response_cache import ResponseCache

if TYPE_CHECKING:
    from wb.core.endpoint_budget import EndpointBudget
    from wb.storage.request_cache import RequestCache

__all__ = [
    'ServiceContainer',
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
    'create_prices_service',
    'create_product_service',
    'create_assess_service',
    'create_pulse_service',
    'create_finance_client',
    'create_finance_service',
]


# ── Service container ─────────────────────────────────────────────────────────


class _Container:
    """Module-level cache for Settings and HTTP clients.

    Avoids re-parsing environment variables and re-creating ``httpx.Client``
    instances on every factory call. All access is through class methods.

    The promotion HTTP client is built once with per-path rate limiters from
    :data:`wb.core.rate_limits.ENDPOINT_LIMITS` so preemptive throttling
    applies across all service calls that share the same client.

    Call :meth:`reset` in test teardown to clear all cached state.
    """

    _settings: Settings | None = None
    _http_clients: dict[tuple[str, str], WbHttpClient] = {}
    _response_cache: ResponseCache | None = None
    _endpoint_budget: 'EndpointBudget | None' = None
    _request_cache: 'RequestCache | None' = None

    @classmethod
    def settings(cls) -> Settings:
        """Return the cached Settings instance, creating it on first call.

        Returns:
            Shared Settings object with config dir ensured.
        """
        if cls._settings is None:
            cls._settings = Settings()
            cls._settings.ensure_config_dir()
        return cls._settings

    @classmethod
    def http_client(
            cls,
            base_url: str,
            token: str,
            *,
            with_rate_limits: bool = False,
            token_type: str = DEFAULT_TOKEN_TYPE,
    ) -> WbHttpClient:
        """Return a cached WbHttpClient for the given base URL and token.

        Args:
            base_url: API base URL.
            token: Authorization token.
            with_rate_limits: When True, inject the shared
                :class:`EndpointBudget` so every request consumes /
                writes per-(token, endpoint) state in
                ``~/.wb-cli/rate_limits.db``. Also wires the
                :class:`RequestCache` (I-15) so cacheable read
                endpoints share responses across processes. Only
                advert + analytics clients need this; statistics/prices
                clients skip it since they use different base URLs.
            token_type: Drives bootstrap rate-limit prior selection in
                :func:`wb.core.rate_limits.select_prior`. Defaults to
                :data:`DEFAULT_TOKEN_TYPE` (``'base'``) — the safer
                assumption when no profile information is available
                (env-var-only callers).

        Returns:
            Existing or newly created WbHttpClient.
        """
        key = (base_url, token)
        if key not in cls._http_clients:
            if with_rate_limits:
                from wb.core.rate_limiter import (
                    compute_token_fingerprint,
                    extract_seller_id,
                )
                budget = cls.endpoint_budget()
                token_fp = compute_token_fingerprint(token)
                seller_id = extract_seller_id(token)
                request_cache = cls.request_cache()
            else:
                budget = None
                token_fp = None
                seller_id = None
                request_cache = None
            cls._http_clients[key] = WbHttpClient(
                base_url=base_url,
                token=token,
                budget=budget,
                token_fp=token_fp,
                seller_id=seller_id,
                token_type=token_type,
                request_cache=request_cache,
                no_cache=cls._no_cache_active(),
            )
        return cls._http_clients[key]

    @classmethod
    def _no_cache_active(cls) -> bool:
        """Return True when the request cache should be bypassed.

        Reads :data:`REQUEST_CACHE_ENV_VAR` (``WB_REQUEST_CACHE``) — any
        case-insensitive match of :data:`REQUEST_CACHE_DISABLED_VALUE`
        disables caching for this process. The CLI ``--no-cache`` flag
        sets the env var before constructing the client, so this single
        accessor handles both code paths.
        """
        env_value = (os.environ.get(REQUEST_CACHE_ENV_VAR) or '').lower()
        return env_value == REQUEST_CACHE_DISABLED_VALUE

    @classmethod
    def endpoint_budget(cls):
        """Return the shared :class:`EndpointBudget`, creating on first call.

        One instance per process — all rate-limited HTTP clients in this
        process share it. Cross-process coordination is via the SQLite
        WAL file at ``~/.wb-cli/rate_limits.db``. The
        ``WB_RATE_LIMITER=memory`` env var forces the in-memory fallback
        (diagnostic only — disables cross-process coordination).
        """
        if cls._endpoint_budget is None:
            from wb.core.endpoint_budget import EndpointBudget
            settings = cls.settings()
            db_path = settings.config_dir / RATE_LIMIT_DB_FILE
            env_value = (os.environ.get(RATE_LIMITER_ENV_VAR) or '').lower()
            force_memory = env_value == RATE_LIMITER_MEMORY_VALUE
            cls._endpoint_budget = EndpointBudget(
                db_path=db_path, force_memory=force_memory,
            )
        return cls._endpoint_budget

    @classmethod
    def request_cache(cls) -> 'RequestCache':
        """Return the shared :class:`RequestCache`, creating on first call.

        Lives at ``<config_dir>/request_cache.db`` (SQLite WAL). Shared
        across every rate-limited HTTP client in this process and with
        sibling ``wb`` processes via the WAL file. The cache is wired
        in regardless of the ``--no-cache`` flag — that flag flips a
        per-client ``no_cache`` switch, not the cache instance itself.
        """
        if cls._request_cache is None:
            from wb.storage.request_cache import RequestCache
            settings = cls.settings()
            cls._request_cache = RequestCache(
                db_path=settings.config_dir / REQUEST_CACHE_DB_FILE,
            )
        return cls._request_cache

    @classmethod
    def response_cache(cls) -> ResponseCache:
        """Return the shared ResponseCache, creating it on first call.

        The cache lives at ``<config_dir>/response_cache.db`` and is
        shared across every service created in this process. SQLite WAL
        mode makes the underlying file safely shared across processes
        too — a second ``wb`` invocation gets the same cache entries.
        """
        if cls._response_cache is None:
            settings = cls.settings()
            cls._response_cache = ResponseCache(
                db_path=settings.config_dir / RESPONSE_CACHE_DB_FILE,
                retention_days=RESPONSE_CACHE_RETENTION_DAYS,
            )
        return cls._response_cache

    @classmethod
    def reset(cls) -> None:
        """Clear all cached state.

        Call this in test teardown to prevent state leaking between tests::

            @pytest.fixture(autouse=True)
            def reset_container():
                yield
                ServiceContainer.reset()
        """
        cls._settings = None
        cls._http_clients.clear()
        cls._response_cache = None
        cls._endpoint_budget = None
        cls._request_cache = None


#: Public alias for ``_Container`` — use in tests and SDK code.
ServiceContainer = _Container


# ── Token resolution ──────────────────────────────────────────────────────────


_NO_PROFILE_HINT = (
    "Run 'wb auth login --profile <name>' to register one. "
    'If WB_API_TOKEN is in env, it will be picked up automatically.'
)


def _bootstrap_required_error(detail: str) -> ConfigError:
    """Build the canonical ConfigError raised when no credential is resolvable.

    Args:
        detail: Short phrase describing what's missing (e.g.
            ``'no active profile and no --token flag'``).

    Returns:
        :class:`ConfigError` suitable for raising — message includes the
        bootstrap migration hint that points users at
        :command:`wb auth login`.
    """
    return ConfigError(f'{detail}. {_NO_PROFILE_HINT}')


def _get_promotion_token(
        profile_name: str | None = None,
        cli_token: str | None = None,
) -> str:
    """Retrieve the promotion token from CLI flag or the active profile.

    Priority chain (post A-2): ``CLI flag → profile → ConfigError``.
    Environment variables / ``.env`` files are no longer consulted at
    runtime — they are bootstrap material for ``wb auth login`` only.

    Args:
        profile_name: Profile name, or None for active profile.
        cli_token: Token passed via CLI flag (highest priority).

    Returns:
        Promotion API token string.

    Raises:
        ConfigError: When neither a CLI flag nor a registered profile
            provides a promotion token.
    """
    if cli_token:
        return cli_token
    settings = _Container.settings()
    try:
        store = ProfileStore(settings.config_dir)
        profile = store.get_profile(profile_name)
    except ConfigError as exc:
        raise _bootstrap_required_error(
            'no active profile and no --token flag',
        ) from exc
    return profile.get_token('promotion')


def _get_token_type(profile_name: str | None = None) -> str:
    """Resolve the token type for rate-limit prior selection.

    Reads :attr:`Profile.token_type` for the named (or active) profile.
    Falls back to :data:`DEFAULT_TOKEN_TYPE` (``'base'``) when no
    profile is registered yet — env-var-only callers default to the
    safer Base assumption rather than the looser Personal one.

    Args:
        profile_name: Profile name, or None for active profile.

    Returns:
        One of :data:`wb.core.constants.TOKEN_TYPES`.
    """
    settings = _Container.settings()
    try:
        store = ProfileStore(settings.config_dir)
        return store.get_profile(profile_name).token_type
    except (ConfigError, OSError):
        return DEFAULT_TOKEN_TYPE


def create_portal_client(
        profile_name: str | None = None,
        cli_authorizev3: str | None = None,
        cli_cookie: str | None = None,
):
    """Create a PortalClient from a CLI flag or the active profile.

    Priority chain (post A-2): ``CLI flags → profile portal session →
    ConfigError``. Environment variables / ``.env`` files are no longer
    consulted at runtime — they are bootstrap material for
    :command:`wb auth login-portal` only.

    Both authorizev3 and cookie are required for portal auth.

    Args:
        profile_name: Profile name, or None for active profile.
        cli_authorizev3: authorizev3 value from CLI flag (highest priority).
        cli_cookie: Cookie from CLI flag (highest priority).

    Returns:
        Configured PortalClient instance.

    Raises:
        ConfigError: If no portal credentials are found in the CLI flags
            or the active profile.
    """
    from wb.client.portal import PortalClient

    if cli_authorizev3 and cli_cookie:
        return PortalClient(authorizev3=cli_authorizev3, cookie=cli_cookie)

    settings = _Container.settings()
    try:
        store = ProfileStore(settings.config_dir)
        profile = store.get_profile(profile_name)
    except ConfigError as exc:
        raise _bootstrap_required_error(
            'no active profile and no --authorizev3/--cookie flags',
        ) from exc
    session = profile.get_portal_session()
    if not session:
        raise ConfigError(
            f'Profile {profile.name!r} has no portal session. '
            "Run 'wb auth login-portal --profile <name>' to register one. "
            'If WB_AUTHORIZEV3 and WB_PORTAL_COOKIE are in env, they will be '
            'picked up automatically.'
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


def create_portal_jam_service(profile_name: str | None = None):
    """Create a :class:`PortalJamService` backed by the active portal session.

    Args:
        profile_name: Profile name, or None for the active profile.

    Returns:
        Configured :class:`PortalJamService`.

    Raises:
        ConfigError: If the resolved profile has no portal session
            (propagated from :func:`create_portal_client`).
    """
    from wb.services.portal_jam import PortalJamService

    client = create_portal_client(profile_name=profile_name)
    return PortalJamService(client)


def create_audit_logger(profile_name: str | None = None) -> AuditLogger:
    """Create an AuditLogger using the current profile's config directory.

    Args:
        profile_name: Profile name, or None for active profile.

    Returns:
        Configured AuditLogger instance.
    """
    settings = _Container.settings()
    return AuditLogger(settings.config_dir)


def create_promotion_client(
        profile_name: str | None = None,
) -> PromotionClient:
    """Create a PromotionClient using the given or active profile's token.

    The returned client shares a cached HTTP connection and per-path rate
    limiters with all other promotion clients created in this process.

    Args:
        profile_name: Profile name, or None for active profile.

    Returns:
        Configured PromotionClient instance.
    """
    token = _get_promotion_token(profile_name)
    token_type = _get_token_type(profile_name)
    http = _Container.http_client(
        PROMOTION_BASE_URL, token,
        with_rate_limits=True, token_type=token_type,
    )
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

    Wires in the shared CacheStore (per-day stats snapshots) and the
    shared ResponseCache (past-day read-through cache for API results).

    Args:
        profile_name: Profile name, or None for active profile.
    """
    from wb.storage.cache import CacheStore
    from wb.services.stats import StatsService

    settings = _Container.settings()
    resolved = _resolve_profile_name(profile_name, settings)
    store = CacheStore(settings.config_dir / CACHE_DB_FILE)
    return StatsService(
        client=create_promotion_client(profile_name),
        cache_store=store,
        profile_name=resolved,
        response_cache=_Container.response_cache(),
        cache_token=_get_promotion_token(profile_name),
    )


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
    """Retrieve the analytics token from a CLI flag or the active profile.

    Priority chain (post A-2): ``CLI flag → profile → ConfigError``.
    Environment variables / ``.env`` files are no longer consulted at
    runtime — they are bootstrap material for ``wb auth login`` only.

    Args:
        profile_name: Profile name, or None for active profile.
        cli_token: Token passed via CLI flag (highest priority).

    Returns:
        Analytics API token string.

    Raises:
        ConfigError: When neither a CLI flag nor a registered profile
            provides an analytics token.
    """
    if cli_token:
        return cli_token
    settings = _Container.settings()
    try:
        store = ProfileStore(settings.config_dir)
        profile = store.get_profile(profile_name)
    except ConfigError as exc:
        raise _bootstrap_required_error(
            'no active profile and no --token flag',
        ) from exc
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
    token_type = _get_token_type(profile_name)
    http = _Container.http_client(
        ANALYTICS_BASE_URL, token,
        with_rate_limits=True, token_type=token_type,
    )
    return AnalyticsClient(http)


def create_analytics_service(profile_name: str | None = None):
    """Create an AnalyticsService from profile credentials.

    Wires in the shared ResponseCache so past-day funnel queries are
    read-through cached across CLI invocations.

    Args:
        profile_name: Profile name, or None for active profile.
    """
    from wb.services.analytics import AnalyticsService
    return AnalyticsService(
        create_analytics_client(profile_name),
        response_cache=_Container.response_cache(),
        cache_token=_get_analytics_token(profile_name),
    )


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
    token_type = _get_token_type(profile_name)
    http = _Container.http_client(
        ANALYTICS_BASE_URL, token,
        with_rate_limits=True, token_type=token_type,
    )
    return ReportsClient(http)


def _resolve_profile_name(
        profile_name: str | None,
        settings: Settings,
) -> str:
    """Resolve a profile name, falling back to the active profile.

    Args:
        profile_name: Explicit profile name, or None.
        settings: Settings instance for active_profile fallback.

    Returns:
        Resolved profile name string.
    """
    return profile_name or settings.active_profile


def create_reports_service(profile_name: str | None = None):
    """Create a ReportsService from profile credentials.

    Wires in the per-profile reports directory and shared CacheStore
    so that warehouse report results are cached on disk.

    Args:
        profile_name: Profile name, or None for active profile.

    Returns:
        Configured ReportsService instance with cache support.
    """
    from wb.storage.cache import CacheStore
    from wb.services.reports import ReportsService

    settings = _Container.settings()
    resolved = _resolve_profile_name(profile_name, settings)
    rdir = settings.reports_dir(resolved)
    store = CacheStore(settings.config_dir / CACHE_DB_FILE)
    return ReportsService(
        create_reports_client(profile_name),
        reports_dir=rdir,
        cache_store=store,
        profile_name=resolved,
    )


def create_statistics_client(profile_name: str | None = None):
    """Create a StatisticsClient using the analytics token.

    Wires the shared :class:`EndpointBudget` so the 1/min limit on
    ``/api/v1/supplier/orders`` and ``/api/v1/supplier/sales`` (swagger
    12) is enforced preemptively. Agents calling these endpoints back to
    back are queued rather than 429'd.

    Args:
        profile_name: Profile name, or None for active profile.

    Returns:
        Configured StatisticsClient instance.
    """
    from wb.client.statistics import StatisticsClient
    token = _get_analytics_token(profile_name)
    token_type = _get_token_type(profile_name)
    http = _Container.http_client(
        STATISTICS_BASE_URL, token,
        with_rate_limits=True, token_type=token_type,
    )
    return StatisticsClient(http)


def create_stock_runway_service(profile_name: str | None = None):
    """Create a ReportsService with StatisticsClient and cache for runway computation.

    Args:
        profile_name: Profile name, or None for active profile.

    Returns:
        Configured ReportsService with statistics_client, reports_dir,
        and cache_store injected.
    """
    from wb.storage.cache import CacheStore
    from wb.services.reports import ReportsService

    settings = _Container.settings()
    resolved = _resolve_profile_name(profile_name, settings)
    rdir = settings.reports_dir(resolved)
    store = CacheStore(settings.config_dir / CACHE_DB_FILE)
    return ReportsService(
        create_reports_client(profile_name),
        statistics_client=create_statistics_client(profile_name),
        reports_dir=rdir,
        cache_store=store,
        profile_name=resolved,
    )


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
    settings = _Container.settings()
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


def create_prices_service(profile_name: str | None = None):
    """Create a PricesService from profile credentials.

    Uses the same promotion token as other seller API calls.
    The Prices & Discounts API uses the identical Authorization header format.

    Args:
        profile_name: Profile name, or None for active profile.

    Returns:
        Configured PricesService instance.
    """
    from wb.client.prices import PricesClient
    from wb.services.prices import PricesService

    token = _get_promotion_token(profile_name)
    http = _Container.http_client(PRICES_BASE_URL, token)
    return PricesService(PricesClient(http))


def create_assess_service(profile_name: str | None = None):
    """Create an AssessService from profile credentials.

    Args:
        profile_name: Profile name, or None for active profile.

    Returns:
        Configured AssessService instance.
    """
    from wb.services.assess import AssessService
    client = create_promotion_client(profile_name)
    return AssessService(
        campaign_service=_lazy_campaign(client),
        budget_service=_lazy_budget(client),
        stats_service=_lazy_stats(client),
    )


def create_pulse_service(profile_name: str | None = None):
    """Create a PulseService from profile credentials.

    Args:
        profile_name: Profile name, or None for active profile.

    Returns:
        Configured PulseService with config_dir for baseline persistence.
    """
    from wb.services.pulse import PulseService
    client = create_promotion_client(profile_name)
    settings = _Container.settings()
    return PulseService(
        campaign_service=_lazy_campaign(client),
        budget_service=_lazy_budget(client),
        bid_service=_lazy_bid(client),
        config_dir=settings.config_dir,
    )


# ── Finance factories ────────────────────────────────────────────────


def _get_finance_token(
        profile_name: str | None = None,
        cli_token: str | None = None,
) -> str:
    """Retrieve the finance token from a CLI flag or the active profile.

    Priority chain (post A-2): ``CLI flag → profile → ConfigError``.
    Mirrors :func:`_get_promotion_token` / :func:`_get_analytics_token`
    but reads the ``finance`` token category.

    Args:
        profile_name: Profile name, or None for active profile.
        cli_token: Token passed via CLI flag (highest priority).

    Returns:
        Finance API JWT.

    Raises:
        ConfigError: When neither a CLI flag nor a registered profile
            provides a finance token.
    """
    if cli_token:
        return cli_token
    settings = _Container.settings()
    try:
        store = ProfileStore(settings.config_dir)
        profile = store.get_profile(profile_name)
    except ConfigError as exc:
        raise _bootstrap_required_error(
            'no active profile and no --token flag',
        ) from exc
    return profile.get_token('finance')


def create_finance_client(profile_name: str | None = None):
    """Create a :class:`FinanceClient` from profile credentials.

    Wires the shared :class:`EndpointBudget` so the 1/min limit on the
    six finance-api endpoints is enforced preemptively.

    Args:
        profile_name: Profile name, or None for active profile.

    Returns:
        Configured :class:`FinanceClient` instance.
    """
    from wb.client.finance import FinanceClient
    token = _get_finance_token(profile_name)
    token_type = _get_token_type(profile_name)
    http = _Container.http_client(
        FINANCE_BASE_URL, token,
        with_rate_limits=True, token_type=token_type,
    )
    return FinanceClient(http)


def create_finance_service(profile_name: str | None = None):
    """Create a :class:`FinanceService` from profile credentials.

    Args:
        profile_name: Profile name, or None for active profile.

    Returns:
        Configured :class:`FinanceService` instance.
    """
    from wb.services.finance import FinanceService
    return FinanceService(create_finance_client(profile_name))


def create_product_service(profile_name: str | None = None):
    """Create a ProductService with all required and optional sub-services.

    Mandatory sub-services use the promotion token.
    Analytics and prices sub-services are best-effort: if no token is
    available for them, those fields of the composite result stay zero.

    Args:
        profile_name: Profile name, or None for active profile.

    Returns:
        Configured ProductService instance.
    """
    from wb.services.product import ProductService

    client = create_promotion_client(profile_name)
    analytics_svc = None
    prices_svc = None

    try:
        analytics_svc = create_analytics_service(profile_name)
    except Exception:  # noqa: BLE001
        pass

    try:
        prices_svc = create_prices_service(profile_name)
    except Exception:  # noqa: BLE001
        pass

    return ProductService(
        campaign_service=_lazy_campaign(client),
        budget_service=_lazy_budget(client),
        stats_service=_lazy_stats(client),
        cluster_service=_lazy_cluster(client),
        analytics_service=analytics_svc,
        prices_service=prices_svc,
    )
