"""Project-wide constants for the WB CLI.

Defines API base URLs, configuration defaults, exit codes, and
token categories used throughout the application.
"""

__all__ = [
    'PROMOTION_BASE_URL',
    'ANALYTICS_BASE_URL',
    'DEFAULT_PROFILE_NAME',
    'CONFIG_DIR_NAME',
    'AUDIT_LOG_FILE',
    'PROFILES_FILE',
    'DEFAULT_TIMEOUT',
    'DEFAULT_MAX_RETRIES',
    'DEFAULT_RETRY_BASE_DELAY',
    'DEFAULT_BATCH_SIZE',
    'ExitCode',
    'TOKEN_CATEGORIES',
    'EP_CAMPAIGN_LIST',
    'EP_CAMPAIGN_FULLSTATS',
    'EP_ELIGIBLE_SUBJECTS',
    'EP_ELIGIBLE_ITEMS',
    'EP_RECOMMENDED_BID',
    'EP_ACCOUNT_BALANCE',
    'EP_CAMPAIGN_BUDGET',
    'EP_CLUSTER_ACTIVE',
    'EP_CLUSTER_ALL',
    'EP_CLUSTER_STATS',
    'EP_CAMPAIGN_START',
    'EP_CAMPAIGN_PAUSE',
    'EP_CAMPAIGN_STOP',
    'EP_CAMPAIGN_RENAME',
    'EP_CAMPAIGN_CREATE',
    'EP_CAMPAIGN_ITEMS',
    'EP_CAMPAIGN_PLACEMENTS',
    'EP_BUDGET_DEPOSIT',
    'EP_BID_SET',
]

from enum import IntEnum

# ── API base URLs ──────────────────────────────────────────────────────
PROMOTION_BASE_URL = 'https://advert-api.wildberries.ru'
ANALYTICS_BASE_URL = 'https://seller-analytics-api.wildberries.ru'

# ── Configuration defaults ─────────────────────────────────────────────
DEFAULT_PROFILE_NAME = 'default'
CONFIG_DIR_NAME = '.wb-cli'
AUDIT_LOG_FILE = 'audit.jsonl'
PROFILES_FILE = 'profiles.json'

# ── HTTP / retry defaults ─────────────────────────────────────────────
DEFAULT_TIMEOUT = 30.0
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_BASE_DELAY = 1.0

# ── Batch processing ──────────────────────────────────────────────────
DEFAULT_BATCH_SIZE = 1000


# ── Exit codes ─────────────────────────────────────────────────────────
class ExitCode(IntEnum):
    """Process exit codes returned by CLI commands.

    Attributes:
        SUCCESS: Command completed successfully.
        VALIDATION_ERROR: Input validation failed.
        AUTH_FAILURE: Authentication credentials invalid or expired.
        AUTH_MISSING_SCOPE: Token lacks required permission scope.
        RATE_LIMITED: API rate limit exceeded.
        API_ERROR: General API error.
        CONFIG_ERROR: Configuration file or value error.
    """

    SUCCESS = 0
    VALIDATION_ERROR = 2
    AUTH_FAILURE = 3
    AUTH_MISSING_SCOPE = 4
    RATE_LIMITED = 5
    API_ERROR = 6
    CONFIG_ERROR = 7


# ── Token categories ──────────────────────────────────────────────────
TOKEN_CATEGORIES: list[str] = ['promotion', 'analytics']

# ── Promotion API endpoint paths (read) ──────────────────────────────
EP_CAMPAIGN_LIST = '/adv/v1/promotion/adverts'
EP_CAMPAIGN_FULLSTATS = '/adv/v2/fullstats'
EP_ELIGIBLE_SUBJECTS = '/adv/v1/promotion/subjects'
EP_ELIGIBLE_ITEMS = '/adv/v1/promotion/nms'
EP_RECOMMENDED_BID = '/adv/v2/promotion/recommended_cpm'
EP_ACCOUNT_BALANCE = '/adv/v1/account/balance'
EP_CAMPAIGN_BUDGET = '/adv/v1/budget'
EP_CLUSTER_ACTIVE = '/adv/v1/auto/active-words'
EP_CLUSTER_ALL = '/adv/v1/auto/words'
EP_CLUSTER_STATS = '/adv/v2/auto/stat-words'

# ── Promotion API endpoint paths (write) ─────────────────────────────
EP_CAMPAIGN_START = '/adv/v0/start'
EP_CAMPAIGN_PAUSE = '/adv/v0/pause'
EP_CAMPAIGN_STOP = '/adv/v0/stop'
EP_CAMPAIGN_RENAME = '/adv/v1/rename'
EP_CAMPAIGN_CREATE = '/adv/v1/promotion/adverts'
EP_CAMPAIGN_ITEMS = '/adv/v1/promotion/nms'
EP_CAMPAIGN_PLACEMENTS = '/adv/v1/auto/update-params'
EP_BUDGET_DEPOSIT = '/adv/v1/budget/deposit'
EP_BID_SET = '/adv/v1/cpm'
