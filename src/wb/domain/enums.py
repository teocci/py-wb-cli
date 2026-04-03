"""Domain enums for the WB CLI.

Defines enumerations that model Wildberries advertising concepts
such as campaign status, campaign type, payment model, placement,
bid strategy, and CLI output preferences.
"""

__all__ = [
    'CampaignStatus',
    'CampaignType',
    'PaymentType',
    'PlacementType',
    'BidType',
    'OutputFormat',
    'VerbosityLevel',
    'OptimizationAction',
    'TargetType',
    'ClusterClass',
    'ProductRole',
]

from enum import Enum, IntEnum


class CampaignStatus(IntEnum):
    """Wildberries campaign lifecycle status.

    Attributes:
        DELETED: Campaign has been deleted.
        READY: Campaign created but not yet launched.
        ARCHIVED: Campaign has been archived.
        DECLINED: Campaign was declined by moderation.
        RUNNING: Campaign is actively serving ads.
        PAUSED: Campaign is temporarily paused.
    """

    DELETED = -1
    READY = 4
    ARCHIVED = 7
    DECLINED = 8
    RUNNING = 9
    PAUSED = 11


class CampaignType(IntEnum):
    """Wildberries campaign type identifier.

    Attributes:
        SEARCH_PLUS_CATALOG: Combined search and catalog placement (type 6).
        AUTO: Deprecated automatic campaign type.
        STANDARD: Standard or custom bid campaigns (new default).
    """

    SEARCH_PLUS_CATALOG = 6
    AUTO = 8
    STANDARD = 9


class PaymentType(str, Enum):
    """Billing model for ad campaigns.

    Attributes:
        CPM: Cost per mille (thousand impressions).
        CPC: Cost per click.
    """

    CPM = 'cpm'
    CPC = 'cpc'


class PlacementType(str, Enum):
    """Ad placement location within Wildberries.

    Attributes:
        SEARCH: Search results page only.
        RECOMMENDATIONS: Recommendation blocks only.
        SEARCH_AND_RECO: Both search and recommendation placements.
    """

    SEARCH = 'search'
    RECOMMENDATIONS = 'recom'
    SEARCH_AND_RECO = 'search_recom'


class BidType(str, Enum):
    """Bid management strategy.

    Attributes:
        UNIFIED: Standard bid managed uniformly across placements.
        MANUAL: Bid is set and adjusted manually per placement.
    """

    UNIFIED = 'unified'
    MANUAL = 'manual'


class OutputFormat(str, Enum):
    """CLI output format.

    Attributes:
        TABLE: Rich formatted table output.
        JSON: Machine-readable JSON output.
        QUIET: Minimal output (exit code only).
    """

    TABLE = 'table'
    JSON = 'json'
    QUIET = 'quiet'


class VerbosityLevel(str, Enum):
    """CLI verbosity level.

    Attributes:
        NORMAL: Standard output.
        VERBOSE: Additional diagnostic information.
        QUIET: Suppress non-essential output.
    """

    NORMAL = 'normal'
    VERBOSE = 'verbose'
    QUIET = 'quiet'


class OptimizationAction(str, Enum):
    """Optimizer-recommended action type.

    Attributes:
        RAISE_ITEM_BID: Increase bid for a product item.
        LOWER_ITEM_BID: Decrease bid for a product item.
        RAISE_CLUSTER_BID: Increase bid for a search cluster.
        LOWER_CLUSTER_BID: Decrease bid for a search cluster.
        DELETE_CLUSTER_BID: Remove bid from a search cluster.
        ADD_MINUS_PHRASE: Add a cluster to minus phrases.
        TOPUP_BUDGET: Deposit additional budget.
        PAUSE_CAMPAIGN: Pause a running campaign.
        REMOVE_PRODUCT: Remove a product from a campaign.
        ADD_PRODUCT: Add a product to a campaign.
    """

    RAISE_ITEM_BID = 'raise_item_bid'
    LOWER_ITEM_BID = 'lower_item_bid'
    RAISE_CLUSTER_BID = 'raise_cluster_bid'
    LOWER_CLUSTER_BID = 'lower_cluster_bid'
    DELETE_CLUSTER_BID = 'delete_cluster_bid'
    ADD_MINUS_PHRASE = 'add_minus_phrase'
    TOPUP_BUDGET = 'topup_budget'
    PAUSE_CAMPAIGN = 'pause_campaign'
    REMOVE_PRODUCT = 'remove_product'
    ADD_PRODUCT = 'add_product'


class TargetType(str, Enum):
    """Type of entity targeted by an optimization decision.

    Attributes:
        CAMPAIGN: A campaign-level action.
        ITEM: A product item-level action.
        CLUSTER: A search cluster-level action.
    """

    CAMPAIGN = 'campaign'
    ITEM = 'item'
    CLUSTER = 'cluster'


class ClusterClass(str, Enum):
    """Search cluster classification for optimization.

    Attributes:
        EFFICIENT: Converting well, candidate for bid increase.
        VISIBLE_WEAK: High impressions but weak conversion.
        EXPENSIVE_NON_CONVERTING: Spending without orders.
        INACTIVE_PROMISING: Not active but has potential.
        NOISY_EXCLUSION: Irrelevant, candidate for minus phrase.
    """

    EFFICIENT = 'efficient'
    VISIBLE_WEAK = 'visible_weak'
    EXPENSIVE_NON_CONVERTING = 'expensive_non_converting'
    INACTIVE_PROMISING = 'inactive_promising'
    NOISY_EXCLUSION = 'noisy_exclusion'


class ProductRole(str, Enum):
    """Product role within a campaign portfolio.

    Attributes:
        HERO: Primary product, highest confidence.
        SUPPORT: Proven secondary product.
        EXPERIMENTAL: New or uncertain product.
    """

    HERO = 'hero'
    SUPPORT = 'support'
    EXPERIMENTAL = 'experimental'
