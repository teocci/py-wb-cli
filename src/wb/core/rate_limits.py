"""Per-endpoint rate limit definitions for WB APIs.

Maps each API endpoint path to ``(calls, period_seconds)`` for use with
:class:`wb.core.rate_limiter.RateLimiter`.

Values are sourced from ``docs/swagger/`` where available, otherwise from
empirical observation (noted inline). See ``RATE_LIMITS.md`` for the full
reference table including CLI command mappings and agent guidance.

Sliding-window interpretation of the swagger ``Burst`` column:
- ``burst = 1``   → space calls by ``period / limit``; stored as ``(1, interval)``
- ``burst = limit`` → full burst allowed; stored as ``(limit, period)``
"""

from __future__ import annotations

from wb.core.constants import (
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
    EP_STOCKS_WB_WAREHOUSES,
    EP_WAREHOUSE_REMAINS_CREATE,
    EP_WAREHOUSE_REMAINS_STATUS,
)

__all__ = ['ENDPOINT_LIMITS']

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
}
