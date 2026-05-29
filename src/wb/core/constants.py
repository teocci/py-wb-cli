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
    'WB_CMP_BASE_URL',
    'DEFAULT_PROFILE_NAME',
    'CONFIG_DIR_NAME',
    'AUDIT_LOG_FILE',
    'CACHE_DB_FILE',
    'RESPONSE_CACHE_DB_FILE',
    'RESPONSE_CACHE_RETENTION_DAYS',
    'RATE_LIMIT_DB_FILE',
    'RATE_LIMITER_ENV_VAR',
    'RATE_LIMITER_MEMORY_VALUE',
    'REQUEST_CACHE_DB_FILE',
    'REQUEST_CACHE_ENV_VAR',
    'REQUEST_CACHE_DISABLED_VALUE',
    'PROFILES_FILE',
    'DEFAULT_TIMEOUT',
    'DEFAULT_MAX_RETRIES',
    'DEFAULT_RETRY_BASE_DELAY',
    'UPSTREAM_RETRY_BASE_DELAY',
    'UPSTREAM_RETRY_MULTIPLIER',
    'DEFAULT_BATCH_SIZE',
    'BID_BATCH_SIZE',
    'FULLSTATS_BATCH_SIZE',
    'HISTORY_CHUNK_SIZE',
    'PRODUCTS_CHUNK_SIZE',
    'ExitCode',
    'ALL_CATEGORY',
    'TOKEN_CATEGORIES',
    'CATEGORY_DISPLAY_NAMES',
    'TOKEN_TYPES',
    'DEFAULT_TOKEN_TYPE',
    'PROFILE_SLUG_RE',
    'PROFILE_NAME_TEMPLATE',
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
    'EP_PORTAL_BIDS',
    'EP_PORTAL_BIDS_CPC',
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
    'EP_STOCKS_WB_WAREHOUSES',
    'EP_WAREHOUSE_REMAINS_CREATE',
    'EP_WAREHOUSE_REMAINS_STATUS',
    'EP_WAREHOUSE_REMAINS_DOWNLOAD',
    'REPORT_POLL_INTERVAL',
    'REPORT_POLL_TIMEOUT',
    'STATISTICS_BASE_URL',
    'EP_STATISTICS_SALES',
    'EP_STATISTICS_ORDERS',
    'FINANCE_BASE_URL',
    'EP_FINANCE_SALES_REPORT_LIST',
    'EP_FINANCE_SALES_REPORT_DETAILED',
    'EP_FINANCE_SALES_REPORT_DETAILED_BY_ID',
    'EP_FINANCE_ACQUIRING_LIST',
    'EP_FINANCE_ACQUIRING_DETAILED',
    'EP_FINANCE_ACQUIRING_DETAILED_BY_ID',
    'RUNWAY_ALERT_CRITICAL_DAYS',
    'RUNWAY_ALERT_LOW_DAYS',
    'RUNWAY_CONFIDENCE_HIGH_DAYS',
    'RUNWAY_CONFIDENCE_MEDIUM_DAYS',
    'EXCLUDED_WAREHOUSE_PREFIXES',
    'REPORT_CACHE_TTL_HOURS',
    'REPORTS_DIR_NAME',
    'PRICES_BASE_URL',
    'EP_PRICES_GOODS_FILTER',
    'DOWNLOADS_CONTENT_ANALYTICS_BASE_URL',
    'EP_PORTAL_JAM_GENERATE',
    'EP_PORTAL_JAM_DOWNLOADS',
    'EP_PORTAL_JAM_FILE',
    'JAM_REPORT_SEARCH_QUERIES',
]

import re
from enum import IntEnum

# ── API base URLs ──────────────────────────────────────────────────────
PROMOTION_BASE_URL = 'https://advert-api.wildberries.ru'
ANALYTICS_BASE_URL = 'https://seller-analytics-api.wildberries.ru'
STATISTICS_BASE_URL = 'https://statistics-api.wildberries.ru'
FINANCE_BASE_URL = 'https://finance-api.wildberries.ru'
PRICES_BASE_URL = 'https://discounts-prices-api.wildberries.ru'
COMMON_API_BASE_URL = 'https://common-api.wildberries.ru'

# ── Seller portal base URLs ──────────────────────────────────────────
SELLER_PORTAL_BASE_URL = 'https://seller.wildberries.ru'
SELLER_CONTENT_BASE_URL = 'https://seller-content.wildberries.ru'
# Campaign-management portal (undocumented; see docs/portal/README.md).
# Hosts the per-NM bid recommendation endpoints used by `wb portal bids`.
WB_CMP_BASE_URL = 'https://cmp.wildberries.ru'
# WB Джем (Jam) report-download CDN — file payloads land here after WB
# generates them. Auth is cookie-based; no authorizev3 header.
DOWNLOADS_CONTENT_ANALYTICS_BASE_URL = 'https://downloads-content-analytics.wildberries.ru'

# ── Configuration defaults ─────────────────────────────────────────────
DEFAULT_PROFILE_NAME = 'default'
CONFIG_DIR_NAME = '.wb-cli'
AUDIT_LOG_FILE = 'audit.jsonl'
CACHE_DB_FILE = 'cache.db'
RESPONSE_CACHE_DB_FILE = 'response_cache.db'
RESPONSE_CACHE_RETENTION_DAYS = 90
RATE_LIMIT_DB_FILE = 'rate_limits.db'
RATE_LIMITER_ENV_VAR = 'WB_RATE_LIMITER'
RATE_LIMITER_MEMORY_VALUE = 'memory'

# I-15 — request cache filename and bypass env var.
# The cache lives at <config_dir>/request_cache.db (SQLite WAL). TTL is
# tied to each endpoint's `period / calls` rate-limit interval, so the
# cache horizon never exceeds what WB lets us refresh.
REQUEST_CACHE_DB_FILE = 'request_cache.db'
REQUEST_CACHE_ENV_VAR = 'WB_REQUEST_CACHE'
REQUEST_CACHE_DISABLED_VALUE = 'disabled'

PROFILES_FILE = 'profiles.json'

# ── HTTP / retry defaults ─────────────────────────────────────────────
DEFAULT_TIMEOUT = 30.0
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_BASE_DELAY = 1.0

# Upstream (5xx) retries use longer, more patient backoff than 429.
# Rationale: 5xx signals WB infra stress — burning attempts in ~12 s
# rarely clears the wave. 5 s → 15 s → 45 s with jitter rides it out.
UPSTREAM_RETRY_BASE_DELAY = 5.0
UPSTREAM_RETRY_MULTIPLIER = 3.0

# ── Batch processing ──────────────────────────────────────────────────
DEFAULT_BATCH_SIZE = 1000
BID_BATCH_SIZE = 1000           # max items per PATCH /api/advert/v1/bids
FULLSTATS_BATCH_SIZE = 50       # max campaign IDs per GET /adv/v3/fullstats
HISTORY_CHUNK_SIZE = 20         # max nm_ids per analytics history call
PRODUCTS_CHUNK_SIZE = 1000      # max nm_ids per analytics products call


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
ALL_CATEGORY: str = 'all'

TOKEN_CATEGORIES: list[str] = [
    'promotion',
    'analytics',
    'statistics',
    'content',
    'marketplace',
    'buyers-returns',
    'documents',
    'finance',
    'supplies',
    'feedbacks-questions',
    'prices-discounts',
]

CATEGORY_DISPLAY_NAMES: dict[str, str] = {
    'promotion':           'Promotion',
    'analytics':           'Analytics',
    'statistics':          'Statistics',
    'content':             'Content',
    'marketplace':         'Marketplace',
    'buyers-returns':      'Buyers Returns',
    'documents':           'Documents',
    'finance':             'Finance',
    'supplies':            'Supplies',
    'feedbacks-questions': 'Feedbacks and Questions',
    'prices-discounts':    'Prices and Discounts',
}

# ── Token types (R-5) ────────────────────────────────────────────────
# WB issues four token types. Personal/Service share the standard advert
# rate budget; Base is 30–60× tighter on most advert + analytics endpoints
# (e.g. /adv/v1/balance: 1/s for Personal vs 2/h for Base). Test tokens are
# rare and treated like Base for safety. See RATE_LIMITS.md and the
# BASE_OVERRIDES map in wb.core.rate_limits.
TOKEN_TYPES: tuple[str, ...] = ('personal', 'service', 'base', 'test')

# Default when a profile carries no explicit token_type. Base is the safer
# assumption: over-throttling Personal is harmless; under-throttling Base
# trips a 30-minute lockout on the first call.
DEFAULT_TOKEN_TYPE: str = 'base'

# ── Profile naming (A-1) ─────────────────────────────────────────────
# Slug: lowercase letters/digits/underscore, starts with letter or digit.
# Leading digit OK because seller_id (oid) is numeric (e.g. '668554_base').
PROFILE_SLUG_RE = re.compile(r'^[a-z0-9][a-z0-9_]*$')

# Auto-generated profile name format: '{seller_id}_{token_type}'.
# Example: '668554_base', '25169_personal'.
PROFILE_NAME_TEMPLATE = '{seller_id}_{token_type}'

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

# ── Stocks Report API endpoint paths ────────────────────────────────
# Source: docs/swagger/11-analytics.yaml
EP_STOCKS_WB_WAREHOUSES = '/api/analytics/v1/stocks-report/wb-warehouses'

# ── Warehouse Remains Report endpoint paths ─────────────────────────
# Source: docs/swagger/12-reports.yaml (async 3-step: create → poll → download)
EP_WAREHOUSE_REMAINS_CREATE = '/api/v1/warehouse_remains'
EP_WAREHOUSE_REMAINS_STATUS = '/api/v1/warehouse_remains/tasks'
EP_WAREHOUSE_REMAINS_DOWNLOAD = '/api/v1/warehouse_remains/tasks'

# ── Report polling defaults ─────────────────────────────────────────
REPORT_POLL_INTERVAL = 5.0
REPORT_POLL_TIMEOUT = 120.0

# ── Statistics API endpoint paths ────────────────────────────────────
# Source: statistics-api.wildberries.ru
EP_STATISTICS_SALES = '/api/v1/supplier/sales'
EP_STATISTICS_ORDERS = '/api/v1/supplier/orders'

# ── Finance API endpoint paths ───────────────────────────────────────
# Source: docs/swagger/13-finances.yaml (verified 2026-05-27).
# WB pre-generates these reports on a weekly schedule (daily if the
# seller has opted in). All six endpoints are read-only; the
# ``detailed*`` variants paginate via the ``rrdId`` cursor (204 = end).
EP_FINANCE_SALES_REPORT_LIST = '/api/finance/v1/sales-reports/list'
EP_FINANCE_SALES_REPORT_DETAILED = '/api/finance/v1/sales-reports/detailed'
EP_FINANCE_SALES_REPORT_DETAILED_BY_ID = '/api/finance/v1/sales-reports/detailed/{report_id}'
EP_FINANCE_ACQUIRING_LIST = '/api/finance/v1/acquiring/list'
EP_FINANCE_ACQUIRING_DETAILED = '/api/finance/v1/acquiring/detailed'
EP_FINANCE_ACQUIRING_DETAILED_BY_ID = '/api/finance/v1/acquiring/detailed/{report_id}'

# ── Stock runway thresholds ──────────────────────────────────────────
RUNWAY_ALERT_CRITICAL_DAYS = 7
RUNWAY_ALERT_LOW_DAYS = 14
RUNWAY_CONFIDENCE_HIGH_DAYS = 20
RUNWAY_CONFIDENCE_MEDIUM_DAYS = 10
EXCLUDED_WAREHOUSE_PREFIXES = ('В пути', 'Всего')

# ── Report cache settings ─────────────────────────────────────────────
REPORT_CACHE_TTL_HOURS = 6
REPORTS_DIR_NAME = 'reports'

# ── Prices & Discounts API endpoint paths ───────────────────────────
# Source: discounts-prices-api.wildberries.ru (verified live 2026-04-05)
EP_PRICES_GOODS_FILTER = '/api/v2/list/goods/filter'

# ── Seller portal endpoint paths ─────────────────────────────────────
EP_PORTAL_AUTH_TOKEN = '/ns/suppliers-auth/suppliers-portal-core/auth/token'
EP_PORTAL_TOKENS_JRPC = '/ns/suppliers-auth-tokens/suppliers-portal-core/api/v1/tokensjrpc'
EP_PORTAL_TABLE_LIST = '/ns/viewer/content-card/viewer/tableListv6'
# F-21 — bid-recommendation endpoints on the campaign-management portal.
# Documented empirically in docs/portal/endpoints/bids.md and bids-cpc.md.
EP_PORTAL_BIDS = '/api/v1/advert/bids'
EP_PORTAL_BIDS_CPC = '/api/v1/advert/bids-cpc'
# I-23 — WB Джем (Jam) report endpoints. Async file-manager workflow:
# POST generate → GET poll list → GET file. See docs/phases/I-23-portal-jam-reports.md.
EP_PORTAL_JAM_GENERATE = '/ns/analytics-api/content-analytics/api/v1/file-manager/download'
EP_PORTAL_JAM_DOWNLOADS = '/ns/analytics-api/content-analytics/api/v1/file-manager/downloads'
EP_PORTAL_JAM_FILE = '/api/v1/file-manager/download'  # download host; '/{id}' appended
JAM_REPORT_SEARCH_QUERIES = 'SEARCH_QUERIES_REPORT'
