"""PoC-1: Measure the recovery window of WB's seller-global throttle.

Polls a lightweight endpoint (``GET /api/advert/v2/adverts?status=9``) until
it returns a non-429 status, printing WB's authoritative rate-limit headers
on each response. When the endpoint is throttled, sleeps for
``x-ratelimit-reset`` seconds (plus a small margin) instead of a fixed
interval — this both gives a faster recovery detection and avoids
extending the cooldown with unnecessary polls.

WB's undocumented headers used here:

- ``x-ratelimit-reset``     — seconds until the window clears (on 429)
- ``x-ratelimit-remaining`` — calls left before the next reset (on 2xx)

These headers are absent from the swagger 429 schema
(``docs/swagger/01-general.yaml``) but are sent on every response.
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx

CONFIG = Path(os.path.expanduser('~/.wb-cli/profiles.json'))
PROMO = 'https://advert-api.wildberries.ru'
PATH = '/api/advert/v2/adverts'

# Fallback poll interval when WB sends no `x-ratelimit-reset` header
# (shouldn't happen on a real 429 but keeps the script honest).
FALLBACK_POLL_INTERVAL = 15.0

# Cap per-iteration sleep so a runaway reset value (observed up to ~30 min)
# doesn't freeze the script for too long. If the reset is larger, we poll
# in chunks and re-read the header each time.
MAX_SLEEP_PER_POLL = 60.0

# Small buffer added to reset-based sleeps so we land just past the server's
# clock rather than hitting the boundary exactly.
RESET_MARGIN_SECONDS = 2.0

MAX_MINUTES = 10


def load_promo_token() -> tuple[str, str]:
    data = json.loads(CONFIG.read_text(encoding='utf-8'))
    active = data['active']
    prof = next(p for p in data['profiles'] if p['name'] == active)
    return active, prof['tokens']['promotion']


def ts() -> str:
    return datetime.now().strftime('%H:%M:%S')


def parse_float_header(headers: httpx.Headers, *names: str) -> float | None:
    for name in names:
        raw = headers.get(name)
        if raw is None:
            continue
        try:
            value = float(raw)
        except ValueError:
            continue
        if value >= 0:
            return value
    return None


def main() -> int:
    profile, token = load_promo_token()
    headers = {
        'Authorization': token,
        'Accept': 'application/json',
    }
    print(f'[{ts()}] profile={profile}   endpoint={PATH}')
    print(
        f'[{ts()}] smart poll: uses x-ratelimit-reset when 429, '
        f'{FALLBACK_POLL_INTERVAL:.0f}s fallback otherwise; '
        f'cap {MAX_SLEEP_PER_POLL:.0f}s per sleep; abort after {MAX_MINUTES} min'
    )
    print('-' * 70)

    start = time.time()
    deadline = start + MAX_MINUTES * 60
    attempt = 0

    with httpx.Client(timeout=10.0) as c:
        while time.time() < deadline:
            attempt += 1
            try:
                r = c.get(f'{PROMO}{PATH}', params={'status': 9}, headers=headers)
            except httpx.RequestError as e:
                print(f'[{ts()}] attempt={attempt}  NET ERROR: {e}')
                time.sleep(FALLBACK_POLL_INTERVAL)
                continue

            elapsed = time.time() - start
            reset = parse_float_header(
                r.headers, 'x-ratelimit-reset', 'x-ratelimit-retry', 'Retry-After',
            )
            remaining = parse_float_header(r.headers, 'x-ratelimit-remaining')
            detail = _format_rate_detail(reset, remaining)
            print(
                f'[{ts()}] attempt={attempt:3d}  t+{elapsed:5.1f}s   '
                f'HTTP {r.status_code}   {detail}'
            )

            if r.status_code != 429:
                print()
                remaining_str = (
                    f'{remaining:.0f}' if remaining is not None else 'unknown'
                )
                print(
                    f'RECOVERED at t+{elapsed:.1f}s on attempt {attempt}   '
                    f'status={r.status_code}   calls_remaining={remaining_str}'
                )
                return 0

            # Still 429 — sleep for the server-reported reset, capped so we
            # re-read the header periodically on very long cooldowns.
            wait = min(
                (reset or FALLBACK_POLL_INTERVAL) + RESET_MARGIN_SECONDS,
                MAX_SLEEP_PER_POLL,
            )
            print(f'[{ts()}]   sleeping {wait:.1f}s before next poll')
            # Ensure we don't overshoot the overall deadline
            time.sleep(max(0.0, min(wait, deadline - time.time())))

    print()
    print(f'TIMEOUT after {MAX_MINUTES}min; still 429')
    return 1


def _format_rate_detail(reset: float | None, remaining: float | None) -> str:
    parts = []
    if reset is not None:
        parts.append(f'reset={reset:.0f}s')
    if remaining is not None:
        parts.append(f'rem={remaining:.0f}')
    return '  '.join(parts) if parts else '(no rate-limit headers)'


if __name__ == '__main__':
    sys.exit(main())
