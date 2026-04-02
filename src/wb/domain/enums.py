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
