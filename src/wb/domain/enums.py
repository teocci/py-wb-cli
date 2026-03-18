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
        READY: Campaign created but not yet launched.
        RUNNING: Campaign is actively serving ads.
        PAUSED: Campaign is temporarily paused.
        ARCHIVED: Campaign has been archived.
    """

    READY = 4
    RUNNING = 9
    PAUSED = 11
    ARCHIVED = 7


class CampaignType(IntEnum):
    """Wildberries campaign type identifier.

    Attributes:
        AUTO: Automatic campaign managed by WB algorithms.
        SEARCH_PLUS_CATALOG: Combined search and catalog placement.
    """

    AUTO = 8
    SEARCH_PLUS_CATALOG = 6


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
        AUTO: Bid is managed automatically by the platform.
        MANUAL: Bid is set and adjusted manually.
    """

    AUTO = 'auto'
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
