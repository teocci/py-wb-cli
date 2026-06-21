"""Per-endpoint rate limit definitions for WB APIs.

Maps each API endpoint path to ``(calls, period_seconds)`` for use with
:class:`wb.core.rate_limiter.RateLimiter`. Values are sourced from
``docs/swagger/`` and reflect the **Personal/Service** column where
swagger stratifies by token type. See ``RATE_LIMITS.md`` for the full
reference (Personal vs Base) and CLI command mappings.

Since R-5 the bootstrap prior is chosen by token type via
:func:`select_prior`. Lookup order:

1. ``BASE_OVERRIDES[path]`` when ``token_type == 'base'`` and the
   endpoint is stratified — the dramatically tighter Base bucket
   prevents first-call 429s on Base tokens.
2. ``ENDPOINT_LIMITS[path]`` — Personal/Service prior, also used for
   Test tokens (rare; we keep the safer-than-Personal Base assumption
   only when explicitly typed Base).
3. ``None`` — endpoint not throttled by the CLI; the request goes
   through and ``EndpointBudget`` learns from the response headers.

Sliding-window interpretation of the swagger ``Burst`` column:

- ``burst = 1``   → space calls by ``period / limit``; stored as ``(1, interval)``
- ``burst = limit`` → full burst allowed; stored as ``(limit, period)``
"""

from __future__ import annotations

from wb.core.constants import (
    DEFAULT_TOKEN_TYPE,
    EP_ACCOUNT_BALANCE,
    EP_BID_SET,
    EP_BUDGET_DEPOSIT,
    EP_CAMPAIGN_BUDGET,
    EP_CAMPAIGN_CREATE,
    EP_CAMPAIGN_DELETE,
    EP_CAMPAIGN_FULLSTATS,
    EP_CAMPAIGN_INFO,
    EP_CAMPAIGN_PAUSE,
    EP_CAMPAIGN_RENAME,
    EP_CAMPAIGN_START,
    EP_CAMPAIGN_STOP,
    EP_CONTENT_CARDS_ERROR_LIST,
    EP_CONTENT_CARDS_LIST,
    EP_CONTENT_CARDS_UPDATE,
    EP_CSV_CREATE,
    EP_CSV_LIST,
    EP_CSV_RETRY,
    EP_ELIGIBLE_SUBJECTS,
    EP_FUNNEL_GROUPED,
    EP_FUNNEL_HISTORY,
    EP_FUNNEL_PRODUCTS,
    EP_NQ_DEL_BIDS,
    EP_NQ_GET_BIDS,
    EP_NQ_GET_MINUS,
    EP_NQ_LIST,
    EP_NQ_SET_BIDS,
    EP_NQ_SET_MINUS,
    EP_NQ_STATS,
    EP_NQ_STATS_DAILY,
    EP_RECOMMENDED_BID,
    EP_SEARCH_DETAILS,
    EP_SEARCH_GROUPS,
    EP_SEARCH_ORDERS,
    EP_SEARCH_REPORT,
    EP_SEARCH_TEXTS,
    EP_FINANCE_ACQUIRING_DETAILED,
    EP_FINANCE_ACQUIRING_LIST,
    EP_FINANCE_SALES_REPORT_DETAILED,
    EP_FINANCE_SALES_REPORT_LIST,
    EP_STATISTICS_ORDERS,
    EP_STATISTICS_SALES,
    EP_STOCKS_WB_WAREHOUSES,
    EP_WAREHOUSE_REMAINS_CREATE,
    EP_WAREHOUSE_REMAINS_STATUS,
)

__all__ = ['BASE_OVERRIDES', 'ENDPOINT_LIMITS', 'select_prior']

# Mapping of endpoint path → (calls, period_seconds) for sliding-window throttling.
#
# Format: EP_CONSTANT: (calls, period_seconds)
#   calls  — max requests allowed within the period
#   period — window size in seconds
#
# Entries are ordered by API group, then by severity (strictest first).
ENDPOINT_LIMITS: dict[str, tuple[int, float]] = {

    # ── Promotion API — per-minute limits (most likely to cause 429) ──────
    #   fullstats: 3/min, burst=1 → enforce 1 every 20 s (no burst)
    EP_CAMPAIGN_FULLSTATS:   (1, 20.0),   # swagger 08: 3/min, burst 1
    #   campaign create: 5/min, burst 5
    EP_CAMPAIGN_CREATE:      (5, 60.0),   # swagger 08: 5/min, burst 5
    #   bid recommendations: 5/min, burst 5
    EP_RECOMMENDED_BID:      (5, 60.0),   # swagger 08: 5/min, burst 5
    #   eligible subjects: 1/12s
    EP_ELIGIBLE_SUBJECTS:    (1, 12.0),   # swagger 08: 1/12 s, burst 5

    # ── Promotion API — per-second limits ─────────────────────────────────
    EP_CAMPAIGN_INFO:        (5, 1.0),    # swagger 08: 5/s, burst 5
    EP_CAMPAIGN_START:       (5, 1.0),    # swagger 08: 5/s, burst 5
    EP_CAMPAIGN_PAUSE:       (5, 1.0),    # swagger 08: 5/s, burst 5
    EP_CAMPAIGN_STOP:        (5, 1.0),    # swagger 08: 5/s, burst 5
    EP_CAMPAIGN_DELETE:      (5, 1.0),    # swagger 08: 5/s, burst 5
    EP_CAMPAIGN_RENAME:      (5, 1.0),    # swagger 08: 5/s, burst 5
    EP_CAMPAIGN_BUDGET:      (4, 1.0),    # swagger 08: 4/s, burst 4
    EP_BUDGET_DEPOSIT:       (1, 1.0),    # swagger 08: 1/s, burst 5
    EP_ACCOUNT_BALANCE:      (1, 1.0),    # swagger 08: 1/s, burst 5
    EP_BID_SET:              (5, 1.0),    # swagger 08: 5/s, burst 5

    # ── Normquery (clusters) API ──────────────────────────────────────────
    #   stats endpoints: 10/min, burst 20
    EP_NQ_STATS:             (10, 60.0),  # swagger 08: 10/min, burst 20
    EP_NQ_STATS_DAILY:       (10, 60.0),  # swagger 08: 10/min, burst 20
    #   bids write: 2/s, burst 4
    EP_NQ_SET_BIDS:          (2, 1.0),    # swagger 08: 2/s, burst 4
    EP_NQ_DEL_BIDS:          (2, 1.0),    # swagger 08: 2/s, burst 4 (same path)
    #   read endpoints: 5/s, burst 10
    EP_NQ_LIST:              (5, 1.0),    # swagger 08: 5/s, burst 10
    EP_NQ_GET_BIDS:          (5, 1.0),    # swagger 08: 5/s, burst 10
    EP_NQ_GET_MINUS:         (5, 1.0),    # swagger 08: 5/s, burst 10
    EP_NQ_SET_MINUS:         (5, 1.0),    # swagger 08: 5/s, burst 10

    # ── Analytics API — sales funnel ──────────────────────────────────────
    #   all funnel endpoints share 3/min, burst 3
    EP_FUNNEL_PRODUCTS:      (3, 60.0),   # swagger 11: 3/min, burst 3
    EP_FUNNEL_HISTORY:       (3, 60.0),   # swagger 11: 3/min, burst 3
    EP_FUNNEL_GROUPED:       (3, 60.0),   # assumed same group (not in swagger 11)

    # ── Analytics API — search-report ────────────────────────────────────
    #   all search-report endpoints: 3/min, burst 3
    EP_SEARCH_REPORT:        (3, 60.0),   # swagger 11: 3/min, burst 3
    EP_SEARCH_GROUPS:        (3, 60.0),   # swagger 11: 3/min, burst 3
    EP_SEARCH_DETAILS:       (3, 60.0),   # swagger 11: 3/min, burst 3
    EP_SEARCH_TEXTS:         (3, 60.0),   # swagger 11: 3/min, burst 3
    EP_SEARCH_ORDERS:        (3, 60.0),   # swagger 11: 3/min, burst 3

    # ── Analytics API — CSV / nm-report ──────────────────────────────────
    EP_CSV_CREATE:           (3, 60.0),   # swagger 11: 3/min, burst 3
    EP_CSV_LIST:             (3, 60.0),   # swagger 11: 3/min, burst 3
    EP_CSV_RETRY:            (3, 60.0),   # swagger 11: 3/min, burst 3

    # ── Analytics API — stocks report ─────────────────────────────────────
    #   stocks: 3/min, burst=1 → enforce 1 every 20 s (no burst)
    EP_STOCKS_WB_WAREHOUSES: (1, 20.0),  # swagger 11: 3/min, burst 1

    # ── Reports API — warehouse remains ──────────────────────────────────
    #   create: 1/min (strict)
    EP_WAREHOUSE_REMAINS_CREATE: (1, 60.0),  # swagger 12: 1/min, burst 5
    #   status poll and download share the same path; use stricter (1/5s)
    EP_WAREHOUSE_REMAINS_STATUS: (1, 5.0),   # swagger 12: poll 1/5s, download 1/min

    # ── Statistics API — supplier orders / sales ─────────────────────────
    #   both endpoints: 1/min, burst 1 (strict; preemptive throttle protects agents)
    EP_STATISTICS_ORDERS: (1, 60.0),         # swagger 12: 1/min, burst 1
    EP_STATISTICS_SALES:  (1, 60.0),         # swagger 12: 1/min, burst 1

    # ── Finance API — sales-reports + acquiring ──────────────────────────
    # All six endpoints documented at 1/min, burst 1. Only the four
    # non-templated paths are entered here; the two ``/detailed/{report_id}``
    # variants are not — their URL carries a per-report ID so each
    # reportId would be its own ``EndpointBudget`` bucket and a static
    # prior wouldn't help. EndpointBudget self-corrects from response
    # headers if WB throttles us. The by-period endpoints (the typical
    # agent path) ARE rate-limited preemptively here.
    EP_FINANCE_SALES_REPORT_LIST:     (1, 60.0),   # swagger 13: 1/min, burst 1
    EP_FINANCE_SALES_REPORT_DETAILED: (1, 60.0),   # swagger 13: 1/min, burst 1
    EP_FINANCE_ACQUIRING_LIST:        (1, 60.0),   # swagger 13: 1/min, burst 1
    EP_FINANCE_ACQUIRING_DETAILED:    (1, 60.0),   # swagger 13: 1/min, burst 1

    # ── Content API — product cards (I-27) ───────────────────────────────
    #   reads are generous; writes and the error-list share a 10/min bucket.
    EP_CONTENT_CARDS_LIST:       (100, 60.0),  # swagger 02: 100/min, burst 5
    EP_CONTENT_CARDS_UPDATE:     (10, 60.0),   # swagger 02: 10/min, 6 s, burst 5
    EP_CONTENT_CARDS_ERROR_LIST: (10, 60.0),   # swagger 02: 10/min, burst 5
}

# ── Base-token overrides (R-5) ─────────────────────────────────────────
#
# Endpoints where the swagger ``| Type |`` table documents a Base limit
# tighter than Personal/Service. Format identical to ``ENDPOINT_LIMITS``:
# ``(calls, period_seconds)`` with the same burst-1-collapses-to-interval
# convention.
#
# Endpoints not in this map use the Personal/Service prior even for Base
# tokens — either swagger documents a uniform rate (campaign mutations,
# normquery list/get, stocks-warehouses) or the endpoint isn't stratified
# at all. ``EndpointBudget`` self-corrects from response headers if the
# real Base limit is tighter than the prior.
BASE_OVERRIDES: dict[str, tuple[int, float]] = {
    # Promotion API
    EP_CAMPAIGN_FULLSTATS: (1, 3600.0),   # 1/h, burst 1
    EP_CAMPAIGN_INFO:      (1, 3600.0),   # 1/h, burst 1
    EP_CAMPAIGN_RENAME:    (1, 1800.0),   # 2/h, 30 min interval, burst 1
    EP_RECOMMENDED_BID:    (1,  180.0),   # 20/h, 3 min interval, burst 1
    EP_ELIGIBLE_SUBJECTS:  (1, 1800.0),   # 2/h, 30 min interval, burst 1
    EP_BUDGET_DEPOSIT:     (1,  720.0),   # 5/h, 12 min interval, burst 1
    EP_ACCOUNT_BALANCE:    (1, 1800.0),   # 2/h, 30 min interval, burst 1
    EP_BID_SET:            (1, 1800.0),   # 2/h, 30 min interval, burst 1

    # Normquery (cluster) API
    EP_NQ_STATS:           (1,  720.0),   # 5/h, 12 min interval, burst 1
    EP_NQ_STATS_DAILY:     (1, 1800.0),   # 2/h, 30 min interval, burst 1
    EP_NQ_SET_BIDS:        (1,  720.0),   # 5/h, 12 min interval, burst 1
    EP_NQ_DEL_BIDS:        (1,  720.0),   # 5/h, 12 min interval, burst 1

    # Analytics — sales funnel
    EP_FUNNEL_PRODUCTS:    (1, 1800.0),   # 2/h, 30 min interval, burst 1
    EP_FUNNEL_HISTORY:     (1, 1800.0),   # 2/h, 30 min interval, burst 1
    EP_FUNNEL_GROUPED:     (1, 1800.0),   # 2/h, 30 min interval, burst 1

    # Analytics — search-report (1/h each, burst 1)
    EP_SEARCH_REPORT:      (1, 3600.0),
    EP_SEARCH_GROUPS:      (1, 3600.0),
    EP_SEARCH_DETAILS:     (1, 3600.0),
    EP_SEARCH_TEXTS:       (1, 3600.0),
    EP_SEARCH_ORDERS:      (1, 3600.0),

    # Analytics — CSV (1/h each, burst 1)
    EP_CSV_CREATE:         (1, 3600.0),
    EP_CSV_LIST:           (1, 3600.0),
    EP_CSV_RETRY:          (1, 3600.0),

    # Reports — warehouse remains (4/h, 15 min interval, burst 1)
    EP_WAREHOUSE_REMAINS_CREATE: (1, 900.0),
    EP_WAREHOUSE_REMAINS_STATUS: (1, 900.0),

    # Finance — sales-reports + acquiring. Swagger doesn't stratify by
    # token type; the 1/min Personal limit becomes 1/hour for Base tokens
    # by the same convention applied to other un-stratified endpoints in
    # this file (RATE_LIMITS.md "When swagger silent, default Base = 1/h").
    EP_FINANCE_SALES_REPORT_LIST:     (1, 3600.0),
    EP_FINANCE_SALES_REPORT_DETAILED: (1, 3600.0),
    EP_FINANCE_ACQUIRING_LIST:        (1, 3600.0),
    EP_FINANCE_ACQUIRING_DETAILED:    (1, 3600.0),
}


def select_prior(
        path: str,
        token_type: str = DEFAULT_TOKEN_TYPE,
) -> tuple[int, float] | None:
    """Return the bootstrap rate-limit prior for an endpoint + token type.

    Used by :class:`wb.client.http.WbHttpClient` to seed
    :meth:`wb.core.endpoint_budget.EndpointBudget.reserve` on first call
    to a fresh ``(token, endpoint)`` bucket. Once WB responds, the budget
    switches to header-driven authority and the prior is no longer
    consulted for that bucket.

    Args:
        path: API endpoint path (an ``EP_*`` constant value).
        token_type: One of :data:`wb.core.constants.TOKEN_TYPES`.
            Unknown values are treated as :data:`DEFAULT_TOKEN_TYPE`.

    Returns:
        ``(calls, period_seconds)`` to pass to ``EndpointBudget.reserve``,
        or ``None`` when the path has no documented prior (the request
        proceeds without preemptive throttling).
    """
    if token_type == 'base' and path in BASE_OVERRIDES:
        return BASE_OVERRIDES[path]
    return ENDPOINT_LIMITS.get(path)
