"""Project-wide constants for the WB CLI.

Defines API base URLs, configuration defaults, exit codes, and
token categories used throughout the application.
"""

__all__ = [
    'PROMOTION_BASE_URL',
    'ANALYTICS_BASE_URL',
    'COMMON_API_BASE_URL',
    'SELLER_PORTAL_BASE_URL',
    'SELLER_CONTENT_BASE_URL',
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
    'PING_PATH',
    'PORTAL_AUTH_HEADER',
    'PORTAL_SESSION_HEADER',
    'EP_CAMPAIGN_COUNT',
    'EP_CAMPAIGN_INFO',
    'EP_CAMPAIGN_FULLSTATS',
    'EP_ELIGIBLE_SUBJECTS',
    'EP_ELIGIBLE_ITEMS',
    'EP_RECOMMENDED_BID',
    'EP_ACCOUNT_BALANCE',
    'EP_CAMPAIGN_BUDGET',
    'EP_CAMPAIGN_START',
    'EP_CAMPAIGN_PAUSE',
    'EP_CAMPAIGN_STOP',
    'EP_CAMPAIGN_RENAME',
    'EP_CAMPAIGN_DELETE',
    'EP_CAMPAIGN_CREATE',
    'EP_CAMPAIGN_ITEMS',
    'EP_CAMPAIGN_PLACEMENTS',
    'EP_BUDGET_DEPOSIT',
    'EP_BID_SET',
    'EP_BID_MIN',
    'EP_NQ_LIST',
    'EP_NQ_GET_BIDS',
    'EP_NQ_SET_BIDS',
    'EP_NQ_DEL_BIDS',
    'EP_NQ_GET_MINUS',
    'EP_NQ_SET_MINUS',
    'EP_NQ_STATS',
    'EP_NQ_STATS_DAILY',
    'EP_PORTAL_AUTH_TOKEN',
    'EP_PORTAL_TOKENS_JRPC',
    'EP_PORTAL_TABLE_LIST',
    'EP_FUNNEL_PRODUCTS',
    'EP_FUNNEL_HISTORY',
    'EP_FUNNEL_GROUPED',
    'EP_SEARCH_REPORT',
    'EP_SEARCH_GROUPS',
    'EP_SEARCH_DETAILS',
    'EP_SEARCH_TEXTS',
    'EP_SEARCH_ORDERS',
    'EP_CSV_CREATE',
    'EP_CSV_LIST',
    'EP_CSV_RETRY',
    'EP_CSV_DOWNLOAD',
]

from enum import IntEnum

# ── API base URLs ──────────────────────────────────────────────────────
PROMOTION_BASE_URL = 'https://advert-api.wildberries.ru'
ANALYTICS_BASE_URL = 'https://seller-analytics-api.wildberries.ru'
COMMON_API_BASE_URL = 'https://common-api.wildberries.ru'

# ── Seller portal base URLs ──────────────────────────────────────────
SELLER_PORTAL_BASE_URL = 'https://seller.wildberries.ru'
SELLER_CONTENT_BASE_URL = 'https://seller-content.wildberries.ru'

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

# ── Connection check ─────────────────────────────────────────────────
PING_PATH = '/ping'

# ── Seller portal auth headers ───────────────────────────────────────
PORTAL_AUTH_HEADER = 'authorizev3'
PORTAL_SESSION_HEADER = 'wb-seller-lk'

# ── Promotion API endpoint paths (read) ──────────────────────────────
# Source: dev-wb-adv.md (verified live 2026-04-02)
EP_CAMPAIGN_COUNT = '/adv/v1/promotion/count'
EP_CAMPAIGN_INFO = '/api/advert/v2/adverts'
EP_CAMPAIGN_FULLSTATS = '/adv/v3/fullstats'
EP_ELIGIBLE_SUBJECTS = '/adv/v1/supplier/subjects'
EP_ELIGIBLE_ITEMS = '/adv/v2/supplier/nms'
EP_RECOMMENDED_BID = '/api/advert/v0/bids/recommendations'
EP_ACCOUNT_BALANCE = '/adv/v1/balance'
EP_CAMPAIGN_BUDGET = '/adv/v1/budget'

# ── Promotion API endpoint paths (write) ─────────────────────────────
EP_CAMPAIGN_CREATE = '/adv/v2/seacat/save-ad'
EP_CAMPAIGN_START = '/adv/v0/start'
EP_CAMPAIGN_PAUSE = '/adv/v0/pause'
EP_CAMPAIGN_STOP = '/adv/v0/stop'
EP_CAMPAIGN_RENAME = '/adv/v0/rename'
EP_CAMPAIGN_DELETE = '/adv/v0/delete'
EP_CAMPAIGN_ITEMS = '/adv/v0/auction/nms'
EP_CAMPAIGN_PLACEMENTS = '/adv/v0/auction/placements'
EP_BUDGET_DEPOSIT = '/adv/v1/budget/deposit'
EP_BID_SET = '/api/advert/v1/bids'
EP_BID_MIN = '/api/advert/v1/bids/min'

# ── Normquery API endpoint paths (search clusters) ──────────────────
EP_NQ_LIST = '/adv/v0/normquery/list'
EP_NQ_GET_BIDS = '/adv/v0/normquery/get-bids'
EP_NQ_SET_BIDS = '/adv/v0/normquery/bids'
EP_NQ_DEL_BIDS = '/adv/v0/normquery/bids'
EP_NQ_GET_MINUS = '/adv/v0/normquery/get-minus'
EP_NQ_SET_MINUS = '/adv/v0/normquery/set-minus'
EP_NQ_STATS = '/adv/v0/normquery/stats'
EP_NQ_STATS_DAILY = '/adv/v1/normquery/stats'

# ── Analytics API endpoint paths ─────────────────────────────────────
# Source: docs/swagger/11-analytics.yaml
EP_FUNNEL_PRODUCTS = '/api/analytics/v3/sales-funnel/products'
EP_FUNNEL_HISTORY = '/api/analytics/v3/sales-funnel/products/history'
EP_FUNNEL_GROUPED = '/api/analytics/v3/sales-funnel/grouped/history'
EP_SEARCH_REPORT = '/api/v2/search-report/report'
EP_SEARCH_GROUPS = '/api/v2/search-report/table/groups'
EP_SEARCH_DETAILS = '/api/v2/search-report/table/details'
EP_SEARCH_TEXTS = '/api/v2/search-report/product/search-texts'
EP_SEARCH_ORDERS = '/api/v2/search-report/product/orders'
EP_CSV_CREATE = '/api/v2/nm-report/downloads'
EP_CSV_LIST = '/api/v2/nm-report/downloads'
EP_CSV_RETRY = '/api/v2/nm-report/downloads/retry'
EP_CSV_DOWNLOAD = '/api/v2/nm-report/downloads/file'

# ── Seller portal endpoint paths ─────────────────────────────────────
EP_PORTAL_AUTH_TOKEN = '/ns/suppliers-auth/suppliers-portal-core/auth/token'
EP_PORTAL_TOKENS_JRPC = '/ns/suppliers-auth-tokens/suppliers-portal-core/api/v1/tokensjrpc'
EP_PORTAL_TABLE_LIST = '/ns/viewer/content-card/viewer/tableListv6'
