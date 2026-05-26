"""Cache policy for the I-15 HTTP-layer request cache.

This module is the single source of truth for *which* endpoints may be
cached, *how long* their entries live, and *which mutations* invalidate
which cached reads. It pairs with :mod:`wb.storage.request_cache`
(storage) and :mod:`wb.client.http` (integration).

Design
------

- Every entry in :data:`wb.core.rate_limits.ENDPOINT_LIMITS` must appear
  in exactly one of :data:`CACHEABLE_ENDPOINTS` or :data:`NEVER_CACHE`.
  A unit test enforces this — future endpoints can't sneak in
  uncategorised. ``select_prior`` returning ``None`` means the endpoint
  has no rate-limit prior; in that case the cache is also bypassed
  (no TTL to derive).

- :func:`cache_ttl_seconds` computes the TTL as ``period / calls`` from
  the token-type's prior. This is the *interval* between legal calls —
  a Base ``(1, 3600)`` endpoint gets a 1-hour TTL because that is
  exactly the window WB will refuse a refresh in. Personal endpoints
  with sub-second intervals end up with effectively-zero TTLs and the
  cache becomes a no-op for them.

- :func:`canonical_hash` produces a stable hash of the request's query
  params + body. Dict ordering, list ordering for primitive lists, and
  the body's bytes are normalised so semantically-equal calls collide
  on the same cache row.

- :data:`MUTATION_INVALIDATES` maps each mutation endpoint to the list
  of cacheable read endpoints whose entries it should drop on success.
  A successful ``wb campaign start`` invalidates the cached campaign
  list so the next ``wb campaign list`` sees the new state.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

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
    EP_CAMPAIGN_ITEMS,
    EP_CAMPAIGN_PAUSE,
    EP_CAMPAIGN_PLACEMENTS,
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

__all__ = [
    'CACHEABLE_ENDPOINTS',
    'NEVER_CACHE',
    'MUTATION_INVALIDATES',
    'cache_ttl_seconds',
    'canonical_hash',
    'is_cacheable',
]


# Read-only, idempotent endpoints whose responses are safe to cache. Each
# is keyed by (token_fp, endpoint, params_hash); TTL comes from
# :func:`cache_ttl_seconds`. Mutations on the related campaign / cluster
# / budget surface drop these entries via :data:`MUTATION_INVALIDATES`.
CACHEABLE_ENDPOINTS: frozenset[str] = frozenset({
    EP_CAMPAIGN_INFO,
    EP_CAMPAIGN_BUDGET,
    EP_CAMPAIGN_FULLSTATS,
    EP_RECOMMENDED_BID,
    EP_ACCOUNT_BALANCE,
    EP_ELIGIBLE_SUBJECTS,
    EP_FUNNEL_PRODUCTS,
    EP_FUNNEL_HISTORY,
    EP_FUNNEL_GROUPED,
    EP_NQ_LIST,
    EP_NQ_GET_BIDS,
    EP_NQ_GET_MINUS,
    EP_NQ_STATS,
    EP_NQ_STATS_DAILY,
    EP_SEARCH_REPORT,
    EP_SEARCH_GROUPS,
    EP_SEARCH_DETAILS,
    EP_SEARCH_TEXTS,
    EP_SEARCH_ORDERS,
    # Statistics API — past-day queries are idempotent; 60 s TTL matches
    # the 1/min rate limit (caching the only legal call window).
    EP_STATISTICS_ORDERS,
    EP_STATISTICS_SALES,
    # Finance API — settlement reports are write-once by WB on a fixed
    # schedule; once published, the rows never change. 60 s TTL (Personal)
    # / 1 h TTL (Base) lets back-to-back agent calls share the response
    # instead of fighting the 1/min throttle. The two ``/detailed/{id}``
    # endpoints aren't listed here for the same reason they aren't in
    # ENDPOINT_LIMITS — see the comment in :mod:`wb.core.rate_limits`.
    EP_FINANCE_SALES_REPORT_LIST,
    EP_FINANCE_SALES_REPORT_DETAILED,
    EP_FINANCE_ACQUIRING_LIST,
    EP_FINANCE_ACQUIRING_DETAILED,
})


# Endpoints that must never be cached. Two reasons split this list:
#
#   1. Mutations — caching a mutation's response would short-circuit the
#      side effect on a re-run.
#   2. Workflow / async endpoints — CSV download lifecycles, warehouse
#      report polls, stocks reports — these return different state on
#      each call by design, even when params are identical.
NEVER_CACHE: frozenset[str] = frozenset({
    # ── Promotion mutations ─────────────────────────────────
    EP_CAMPAIGN_CREATE,
    EP_CAMPAIGN_START,
    EP_CAMPAIGN_PAUSE,
    EP_CAMPAIGN_STOP,
    EP_CAMPAIGN_DELETE,
    EP_CAMPAIGN_RENAME,
    EP_CAMPAIGN_ITEMS,
    EP_CAMPAIGN_PLACEMENTS,
    EP_BUDGET_DEPOSIT,
    EP_BID_SET,
    # ── Normquery mutations ─────────────────────────────────
    EP_NQ_SET_BIDS,
    EP_NQ_DEL_BIDS,
    EP_NQ_SET_MINUS,
    # ── Async / workflow endpoints ──────────────────────────
    EP_CSV_CREATE,
    EP_CSV_LIST,
    EP_CSV_RETRY,
    EP_STOCKS_WB_WAREHOUSES,
    EP_WAREHOUSE_REMAINS_CREATE,
    EP_WAREHOUSE_REMAINS_STATUS,
})


# Mutation → invalidation map. After a successful (2xx) call to a key
# endpoint, the HTTP client drops cached entries for every value
# endpoint scoped to the acting token. The mapping is hand-curated and
# enforced by a unit test (every mutation key is in NEVER_CACHE; every
# invalidation target is in CACHEABLE_ENDPOINTS).
MUTATION_INVALIDATES: dict[str, tuple[str, ...]] = {
    EP_CAMPAIGN_CREATE: (EP_CAMPAIGN_INFO,),
    EP_CAMPAIGN_START:  (EP_CAMPAIGN_INFO,),
    EP_CAMPAIGN_PAUSE:  (EP_CAMPAIGN_INFO,),
    EP_CAMPAIGN_STOP:   (EP_CAMPAIGN_INFO,),
    EP_CAMPAIGN_DELETE: (EP_CAMPAIGN_INFO,),
    EP_CAMPAIGN_RENAME: (EP_CAMPAIGN_INFO,),
    EP_BUDGET_DEPOSIT:  (EP_CAMPAIGN_BUDGET, EP_ACCOUNT_BALANCE),
    EP_BID_SET:         (EP_CAMPAIGN_INFO, EP_RECOMMENDED_BID),
    EP_NQ_SET_BIDS:     (EP_NQ_GET_BIDS, EP_NQ_LIST),
    EP_NQ_DEL_BIDS:     (EP_NQ_GET_BIDS, EP_NQ_LIST),
    EP_NQ_SET_MINUS:    (EP_NQ_GET_MINUS,),
}


def is_cacheable(endpoint: str) -> bool:
    """Return True when ``endpoint`` is in the cacheable allowlist.

    Args:
        endpoint: API path constant from :mod:`wb.core.constants`.

    Returns:
        True for read-only endpoints whose responses may be cached.
    """
    return endpoint in CACHEABLE_ENDPOINTS


def cache_ttl_seconds(
        endpoint: str,
        token_type: str = DEFAULT_TOKEN_TYPE,
) -> float:
    """Return the cache TTL for ``endpoint`` under the given token type.

    TTL = ``period / calls`` from :func:`wb.core.rate_limits.select_prior`.
    This is the interval between legal calls — Base ``(1, 3600)`` →
    3600 s; Personal ``(5, 1.0)`` → 0.2 s. When the endpoint has no
    prior or is not in the allowlist, returns ``0.0`` (no cache).

    Args:
        endpoint: API path constant.
        token_type: One of :data:`wb.core.constants.TOKEN_TYPES`.
            Unknown values are treated as :data:`DEFAULT_TOKEN_TYPE`.

    Returns:
        TTL in seconds; ``0.0`` when caching is not applicable.
    """
    if endpoint not in CACHEABLE_ENDPOINTS:
        return 0.0
    from wb.core.rate_limits import select_prior
    prior = select_prior(endpoint, token_type)
    if prior is None:
        return 0.0
    calls, period = prior
    if calls <= 0:
        return 0.0
    return period / calls


def canonical_hash(
        params: dict[str, Any] | None,
        body: Any | None = None,
) -> str:
    """Return a stable SHA-256 hex digest of the request's params + body.

    Dict keys are sorted recursively. Lists of primitives are sorted so
    that ``{'ids': [3, 1, 2]}`` and ``{'ids': [1, 2, 3]}`` collide on
    the same cache row. The body is included under a sentinel key so
    that GETs (body=None) and POSTs with the same params don't collide.

    Args:
        params: Query params dict (or ``None``).
        body: JSON-serialisable body (or ``None``). For raw bytes the
            caller may pass a hex digest directly.

    Returns:
        SHA-256 hex digest as a string.
    """
    payload = {
        'params': _canonicalise(params or {}),
        'body': _canonicalise(body),
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(encoded.encode('utf-8')).hexdigest()


def _canonicalise(value: Any) -> Any:
    """Recursively normalise a value for stable JSON serialisation."""
    if value is None:
        return None
    if isinstance(value, dict):
        return {k: _canonicalise(v) for k, v in sorted(value.items())}
    if isinstance(value, (list, tuple, set)):
        items = [_canonicalise(v) for v in value]
        if all(isinstance(v, (str, int, float, bool)) for v in items):
            return sorted(items, key=_sort_key)
        return items
    if isinstance(value, bytes):
        return hashlib.sha256(value).hexdigest()
    return value


def _sort_key(value: Any) -> tuple[int, Any]:
    """Stable ordering across heterogeneous primitives."""
    if isinstance(value, bool):
        return (0, value)
    if isinstance(value, (int, float)):
        return (1, value)
    return (2, str(value))
