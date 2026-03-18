"""Factory functions for creating service instances from CLI context."""

from __future__ import annotations

from wb.auth.profiles import ProfileStore
from wb.client.http import WbHttpClient
from wb.client.promotion import PromotionClient
from wb.core.config import Settings
from wb.core.constants import PROMOTION_BASE_URL

__all__ = [
    'create_promotion_client',
    'create_campaign_service',
    'create_budget_service',
    'create_stats_service',
    'create_cluster_service',
    'create_bid_service',
]


def _get_promotion_token(profile_name: str | None = None) -> str:
    """Retrieve the promotion token for the given or active profile.

    Args:
        profile_name: Profile name, or None for active profile.

    Returns:
        Promotion API token string.
    """
    settings = Settings()
    settings.ensure_config_dir()
    store = ProfileStore(settings.config_dir)
    profile = store.get_profile(profile_name)
    return profile.get_token('promotion')


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
