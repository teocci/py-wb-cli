"""Tests for wb.core.endpoint_budget.EndpointBudget (Phase R-1)."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

import pytest

from wb.core.endpoint_budget import (
    BudgetRow,
    EndpointBudget,
    parse_int_header,
    parse_rate_limit_wait,
)
import wb.core.endpoint_budget as endpoint_budget_module


_PRIOR_BURSTY = (5, 1.0)   # 5 calls / 1 s — bootstrap doesn't block in tests
_PRIOR_TIGHT = (1, 60.0)   # 1 call / 60 s — bootstrap would block on second call


@pytest.fixture(autouse=True)
def _reset_fallback_warned():
    """Reset the module-global fallback warning flag between tests."""
    endpoint_budget_module._FALLBACK_WARNED = False
    yield
    endpoint_budget_module._FALLBACK_WARNED = False


def _make_headers(**kwargs) -> dict[str, str]:
    """Convert kwargs like remaining=5 into the header dict observe expects."""
    name_map = {
        'limit': 'x-ratelimit-limit',
        'remaining': 'x-ratelimit-remaining',
        'reset': 'x-ratelimit-reset',
        'retry': 'x-ratelimit-retry',
        'retry_after': 'Retry-After',
    }
    return {name_map[k]: str(v) for k, v in kwargs.items()}


def _seed_row(
        db_path: Path,
        token_fp: str,
        endpoint: str,
        *,
        remaining: int | None,
        reset_at: float,
        seller_id: str | None = None,
        bucket_limit: int | None = None,
        last_seen: float | None = None,
) -> None:
    """Write a row directly to the table, bypassing observe()."""
    last_seen = last_seen if last_seen is not None else time.time()
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            'INSERT OR REPLACE INTO endpoint_budget '
            '(token_fp, endpoint, seller_id, bucket_limit, remaining, reset_at, last_seen) '
            'VALUES (?, ?, ?, ?, ?, ?, ?)',
            (token_fp, endpoint, seller_id, bucket_limit, remaining, reset_at, last_seen),
        )
        conn.commit()
    finally:
        conn.close()


class TestHeaderParsers:
    """Module-level parsers used by observe() and (later) the HTTP client."""

    def test_parse_int_header_returns_int(self):
        assert parse_int_header({'x': '5'}, ('x',)) == 5

    def test_parse_int_header_handles_float_string(self):
        assert parse_int_header({'x': '5.7'}, ('x',)) == 5

    def test_parse_int_header_missing_returns_none(self):
        assert parse_int_header({}, ('x',)) is None

    def test_parse_int_header_invalid_returns_none(self):
        assert parse_int_header({'x': 'abc'}, ('x',)) is None

    def test_parse_int_header_first_match_wins(self):
        assert parse_int_header({'a': '1', 'b': '2'}, ('a', 'b')) == 1

    def test_parse_wait_prefers_x_ratelimit_retry(self):
        """X-Ratelimit-Retry (next-call wait) > Reset (full bucket refill).

        From the official WB doc example:
            X-Ratelimit-Reset: 29   ← burst back to max in 29 s
            X-Ratelimit-Retry: 2    ← can retry next request in 2 s
        Picking Reset would over-wait by ~14×.
        """
        assert parse_rate_limit_wait({
            'x-ratelimit-retry': '2',
            'x-ratelimit-reset': '29',
        }) == 2.0

    def test_parse_wait_retry_after_beats_reset(self):
        assert parse_rate_limit_wait({
            'Retry-After': '5',
            'x-ratelimit-reset': '60',
        }) == 5.0

    def test_parse_wait_falls_back_to_reset_when_only_one_present(self):
        assert parse_rate_limit_wait({'x-ratelimit-reset': '45'}) == 45.0
        assert parse_rate_limit_wait({'x-ratelimit-retry': '30'}) == 30.0
        assert parse_rate_limit_wait({'Retry-After': '15'}) == 15.0

    def test_parse_wait_ignores_non_positive(self):
        assert parse_rate_limit_wait({'Retry-After': '0'}) is None
        assert parse_rate_limit_wait({'x-ratelimit-reset': '-5'}) is None

    def test_parse_wait_empty_returns_none(self):
        assert parse_rate_limit_wait({}) is None


class TestObserveAndReadAll:
    """observe() persists header data; read_all() returns it."""

    def test_observe_no_headers_is_noop(self, tmp_path):
        budget = EndpointBudget(db_path=tmp_path / 'rl.db')
        budget.observe_headers('tk', '/path', {})
        assert budget.read_all() == []

    def test_observe_writes_full_row(self, tmp_path):
        budget = EndpointBudget(db_path=tmp_path / 'rl.db')
        budget.observe_headers(
            'tk', '/adv/v3/fullstats',
            _make_headers(limit=3, remaining=2, reset=60),
            seller_id='sid-12345',
        )
        rows = budget.read_all()
        assert len(rows) == 1
        row = rows[0]
        assert row.token_fp == 'tk'
        assert row.endpoint == '/adv/v3/fullstats'
        assert row.seller_id == 'sid-12345'
        assert row.bucket_limit == 3
        assert row.remaining == 2
        # reset_at is now + 60; allow a couple of seconds of slack
        assert time.time() + 55 < row.reset_at <= time.time() + 61

    def test_observe_partial_headers_only_remaining(self, tmp_path):
        budget = EndpointBudget(db_path=tmp_path / 'rl.db')
        budget.observe_headers('tk', '/p', {'x-ratelimit-remaining': '4'})
        row = budget.read_all()[0]
        assert row.remaining == 4
        assert row.bucket_limit is None
        # reset_in absent → reset_at == now (i.e., already expired, will re-bootstrap on reserve)
        assert row.reset_at <= time.time() + 0.5

    def test_observe_partial_headers_only_reset(self, tmp_path):
        budget = EndpointBudget(db_path=tmp_path / 'rl.db')
        budget.observe_headers('tk', '/p', _make_headers(reset=30))
        row = budget.read_all()[0]
        assert row.remaining is None
        assert time.time() + 25 < row.reset_at <= time.time() + 31

    def test_observe_overwrites_previous(self, tmp_path):
        budget = EndpointBudget(db_path=tmp_path / 'rl.db')
        budget.observe_headers('tk', '/p', _make_headers(limit=3, remaining=3, reset=60))
        budget.observe_headers('tk', '/p', _make_headers(limit=3, remaining=1, reset=20))
        rows = budget.read_all()
        assert len(rows) == 1
        assert rows[0].remaining == 1

    def test_observe_preserves_seller_id_when_later_call_omits_it(self, tmp_path):
        """COALESCE behaviour: don't blank an already-known seller_id."""
        budget = EndpointBudget(db_path=tmp_path / 'rl.db')
        budget.observe_headers(
            'tk', '/p', _make_headers(remaining=5, reset=60), seller_id='sid-1',
        )
        budget.observe_headers(
            'tk', '/p', _make_headers(remaining=4, reset=60), seller_id=None,
        )
        assert budget.read_all()[0].seller_id == 'sid-1'

    def test_per_token_endpoint_isolation(self, tmp_path):
        budget = EndpointBudget(db_path=tmp_path / 'rl.db')
        budget.observe_headers('tk-a', '/p1', _make_headers(remaining=1, reset=60))
        budget.observe_headers('tk-b', '/p1', _make_headers(remaining=2, reset=60))
        budget.observe_headers('tk-a', '/p2', _make_headers(remaining=3, reset=60))
        rows = {(r.token_fp, r.endpoint): r.remaining for r in budget.read_all()}
        assert rows == {('tk-a', '/p1'): 1, ('tk-b', '/p1'): 2, ('tk-a', '/p2'): 3}

    def test_read_all_empty(self, tmp_path):
        budget = EndpointBudget(db_path=tmp_path / 'rl.db')
        assert budget.read_all() == []


class TestReserve:
    """reserve() blocks (or returns immediately) according to bucket state."""

    def test_no_state_uses_bootstrap_and_returns(self, tmp_path):
        budget = EndpointBudget(db_path=tmp_path / 'rl.db')
        start = time.monotonic()
        budget.reserve('tk', '/p', prior=_PRIOR_BURSTY)
        # Bootstrap = SharedRateLimiter (5/1s); a single call returns instantly.
        assert time.monotonic() - start < 0.1

    def test_remaining_above_zero_decrements_and_returns(self, tmp_path):
        db = tmp_path / 'rl.db'
        budget = EndpointBudget(db_path=db)
        _seed_row(db, 'tk', '/p', remaining=5, reset_at=time.time() + 60, bucket_limit=5)

        start = time.monotonic()
        budget.reserve('tk', '/p', prior=_PRIOR_TIGHT)
        assert time.monotonic() - start < 0.05

        rows = budget.read_all()
        assert len(rows) == 1
        assert rows[0].remaining == 4

    def test_remaining_one_decrements_to_zero(self, tmp_path):
        db = tmp_path / 'rl.db'
        budget = EndpointBudget(db_path=db)
        _seed_row(db, 'tk', '/p', remaining=1, reset_at=time.time() + 60)

        budget.reserve('tk', '/p', prior=_PRIOR_TIGHT)
        assert budget.read_all()[0].remaining == 0

    def test_remaining_zero_sleeps_until_reset(self, tmp_path):
        db = tmp_path / 'rl.db'
        budget = EndpointBudget(db_path=db)
        # Lock for ~0.4 s, then bootstrap allows the call.
        _seed_row(db, 'tk', '/p', remaining=0, reset_at=time.time() + 0.4)

        start = time.monotonic()
        budget.reserve('tk', '/p', prior=_PRIOR_BURSTY)
        elapsed = time.monotonic() - start
        # Should sleep at least ~0.3 s (the wait) but well under a second.
        assert 0.3 < elapsed < 1.5

    def test_expired_reset_re_bootstraps(self, tmp_path):
        db = tmp_path / 'rl.db'
        budget = EndpointBudget(db_path=db)
        # remaining=0 but reset_at AND last_seen already in the past → bucket has refilled.
        # Use last_seen far enough back that last_seen + prior_period also passed.
        old = time.time() - 100.0
        _seed_row(db, 'tk', '/p', remaining=0, reset_at=old, last_seen=old)

        start = time.monotonic()
        budget.reserve('tk', '/p', prior=_PRIOR_BURSTY)
        # Should NOT sleep (both authoritative reset and prior-fallback already passed).
        assert time.monotonic() - start < 0.1

    def test_remaining_zero_no_wait_header_uses_interval_fallback(self, tmp_path):
        """Regression for the live test on 2026-04-26.

        WB sends ``X-Ratelimit-Remaining: 0`` on 200 responses but no
        wait header (Retry / Reset / Retry-After). Without a fallback,
        :meth:`reserve` would treat the row as "expired" and fire the
        next request immediately, getting a 429 with a multi-minute
        penalty.

        Per the WB doc, the fallback is ``interval = period / calls``.
        """
        budget = EndpointBudget(db_path=tmp_path / 'rl.db')
        budget.observe_headers('tk', '/p', {'x-ratelimit-remaining': '0'})

        start = time.monotonic()
        # prior = (1, 0.4) → interval = 0.4 / 1 = 0.4 s
        budget.reserve('tk', '/p', prior=(1, 0.4))
        elapsed = time.monotonic() - start
        # Must wait ~0.4 s, not return immediately.
        assert 0.3 < elapsed < 1.5

    def test_interval_fallback_is_period_over_calls(self, tmp_path):
        """For burst-style endpoints, fallback = period/calls, not period.

        Per the WB doc, "interval = period / limit". For 300/min the
        interval is 200 ms, NOT 60 s. Using ``period`` directly would
        over-wait by a factor of ``calls`` for any burst endpoint.
        """
        budget = EndpointBudget(db_path=tmp_path / 'rl.db')
        budget.observe_headers('tk', '/p', {'x-ratelimit-remaining': '0'})

        start = time.monotonic()
        # prior = (5, 1.0) → interval = 1.0 / 5 = 0.2 s
        budget.reserve('tk', '/p', prior=(5, 1.0))
        elapsed = time.monotonic() - start
        # Must wait ~0.2 s, well below the 1.0 s `period`.
        assert 0.15 < elapsed < 0.6

    def test_wb_429_retry_2_reset_29_uses_retry_value(self, tmp_path):
        """Doc example: Retry=2 s, Reset=29 s. We must sleep ~2 s, not 29 s."""
        budget = EndpointBudget(db_path=tmp_path / 'rl.db')
        budget.observe_headers(
            'tk', '/p',
            {
                'x-ratelimit-remaining': '0',
                'x-ratelimit-retry': '0.4',
                'x-ratelimit-reset': '5.0',
            },
        )

        start = time.monotonic()
        # Use a tighter prior than retry so the retry value dominates.
        budget.reserve('tk', '/p', prior=(1, 0.1))
        elapsed = time.monotonic() - start
        # Must wait ~0.4 s (the retry), not ~5 s (the reset).
        assert 0.3 < elapsed < 1.5

    def test_max_wait_seconds_raises_for_long_lockouts(self, tmp_path):
        """Long cooldowns should fail fast, not block the CLI for minutes.

        Mirrors the F-12 60 s bail-out behaviour the HTTP client (R-2)
        will need: when the bucket says we'd have to wait 30 minutes,
        raise RateLimitError immediately instead of sleeping.
        """
        from wb.core.exceptions import RateLimitError

        db = tmp_path / 'rl.db'
        budget = EndpointBudget(db_path=db)
        # Lock the bucket for 1800 s (the real Base-token /adv/v1/balance penalty).
        _seed_row(db, 'tk', '/p', remaining=0, reset_at=time.time() + 1800.0)

        with pytest.raises(RateLimitError) as exc_info:
            budget.reserve(
                'tk', '/p', prior=(1, 1.0), max_wait_seconds=60.0,
            )
        assert exc_info.value.retry_after is not None
        assert 1700 < exc_info.value.retry_after <= 1800

    def test_max_wait_seconds_does_not_raise_for_short_waits(self, tmp_path):
        """Short waits should still sleep transparently within the ceiling."""
        db = tmp_path / 'rl.db'
        budget = EndpointBudget(db_path=db)
        _seed_row(db, 'tk', '/p', remaining=0, reset_at=time.time() + 0.3)

        start = time.monotonic()
        budget.reserve('tk', '/p', prior=_PRIOR_BURSTY, max_wait_seconds=60.0)
        elapsed = time.monotonic() - start
        assert elapsed < 1.5  # well under the ceiling

    def test_max_wait_seconds_none_keeps_blocking_semantics(self, tmp_path):
        """Without a ceiling, reserve always blocks regardless of duration."""
        db = tmp_path / 'rl.db'
        budget = EndpointBudget(db_path=db)
        _seed_row(db, 'tk', '/p', remaining=0, reset_at=time.time() + 0.3)

        # max_wait_seconds=None — must NOT raise even though we're locked.
        start = time.monotonic()
        budget.reserve('tk', '/p', prior=_PRIOR_BURSTY, max_wait_seconds=None)
        elapsed = time.monotonic() - start
        assert 0.2 < elapsed < 1.5


class TestObserveThenReserveRoundTrip:
    """End-to-end behaviour matching the production HTTP client lifecycle."""

    def test_observe_then_reserve_decrements_persisted_state(self, tmp_path):
        budget = EndpointBudget(db_path=tmp_path / 'rl.db')
        budget.observe_headers(
            'tk', '/p', _make_headers(limit=3, remaining=3, reset=60),
        )
        budget.reserve('tk', '/p', prior=_PRIOR_BURSTY)
        budget.reserve('tk', '/p', prior=_PRIOR_BURSTY)
        rows = budget.read_all()
        assert rows[0].remaining == 1

    def test_observe_overrides_previous_decrements(self, tmp_path):
        """Real WB headers always win over our provisional decrements."""
        budget = EndpointBudget(db_path=tmp_path / 'rl.db')
        budget.observe_headers('tk', '/p', _make_headers(remaining=3, reset=60))
        budget.reserve('tk', '/p', prior=_PRIOR_BURSTY)  # decrements to 2
        budget.observe_headers('tk', '/p', _make_headers(remaining=10, reset=60))
        assert budget.read_all()[0].remaining == 10


class TestFallback:
    """When SQLite is unavailable, the in-memory dict takes over silently."""

    def test_corrupt_db_falls_back_at_init(self, tmp_path, caplog):
        db = tmp_path / 'rl.db'
        db.write_bytes(b'not a sqlite db')
        with caplog.at_level('WARNING', logger='wb.core.endpoint_budget'):
            budget = EndpointBudget(db_path=db)
        assert budget._fallback is not None
        # Operations still work through the fallback dict.
        budget.observe_headers('tk', '/p', _make_headers(remaining=5, reset=60))
        rows = budget.read_all()
        assert len(rows) == 1 and rows[0].remaining == 5

    def test_fallback_decrement_on_reserve(self, tmp_path):
        db = tmp_path / 'rl.db'
        db.write_bytes(b'not a sqlite db')
        budget = EndpointBudget(db_path=db)
        budget.observe_headers('tk', '/p', _make_headers(remaining=2, reset=60))
        budget.reserve('tk', '/p', prior=_PRIOR_BURSTY)
        assert budget.read_all()[0].remaining == 1

    def test_fallback_warning_emitted_once(self, tmp_path, caplog):
        db1 = tmp_path / 'a.db'
        db2 = tmp_path / 'b.db'
        db1.write_bytes(b'corrupt')
        db2.write_bytes(b'corrupt')
        with caplog.at_level('WARNING', logger='wb.core.endpoint_budget'):
            EndpointBudget(db_path=db1)
            EndpointBudget(db_path=db2)
        warnings = [
            r for r in caplog.records
            if 'Endpoint budget DB unavailable' in r.message
        ]
        assert len(warnings) == 1


class TestCrossProcess:
    """Two EndpointBudget instances on the same DB see each other's writes."""

    def test_observe_in_one_visible_in_other(self, tmp_path):
        db = tmp_path / 'rl.db'
        writer = EndpointBudget(db_path=db)
        reader = EndpointBudget(db_path=db)
        writer.observe_headers(
            'tk', '/p', _make_headers(limit=3, remaining=2, reset=120),
            seller_id='sid-x',
        )
        rows = reader.read_all()
        assert len(rows) == 1
        assert rows[0].remaining == 2
        assert rows[0].seller_id == 'sid-x'

    def test_decrement_in_one_visible_in_other(self, tmp_path):
        db = tmp_path / 'rl.db'
        a = EndpointBudget(db_path=db)
        b = EndpointBudget(db_path=db)
        a.observe_headers('tk', '/p', _make_headers(remaining=5, reset=120))
        a.reserve('tk', '/p', prior=_PRIOR_BURSTY)
        a.reserve('tk', '/p', prior=_PRIOR_BURSTY)
        assert b.read_all()[0].remaining == 3

    def test_lock_set_by_one_blocks_other(self, tmp_path):
        db = tmp_path / 'rl.db'
        a = EndpointBudget(db_path=db)
        b = EndpointBudget(db_path=db)
        a.observe_headers('tk', '/p', _make_headers(remaining=0, reset=0.4))

        start = time.monotonic()
        b.reserve('tk', '/p', prior=_PRIOR_BURSTY)
        elapsed = time.monotonic() - start
        assert 0.3 < elapsed < 1.5


class TestBudgetRow:
    """Minor: BudgetRow is a frozen dataclass and serialises predictably."""

    def test_rows_are_frozen(self):
        row = BudgetRow(
            token_fp='tk', endpoint='/p', seller_id=None, bucket_limit=None,
            remaining=None, reset_at=0.0, last_seen=0.0,
        )
        with pytest.raises((AttributeError, Exception)):
            row.token_fp = 'mutated'  # type: ignore[misc]
