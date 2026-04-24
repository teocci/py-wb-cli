"""Direct probe of the three endpoints used by `wb stats daily-report`.

Bypasses the CLI rate limiter + retry loop: fires one raw httpx request per
endpoint and prints the HTTP status together with every rate-limit header
WB's gateway returns. Shows which endpoint is currently 429-ing, how close
we are to the next throttle (via `x-ratelimit-remaining` on 200s), and the
authoritative cooldown in seconds (via `x-ratelimit-reset` on 429s).

WB's undocumented headers read here:

- ``x-ratelimit-remaining`` — calls left before the next reset (on 2xx)
- ``x-ratelimit-reset``     — seconds until the window clears (on 429)
- ``x-ratelimit-retry``     — alias of reset (on 429)
- ``x-ratelimit-limit``     — the limit that was hit (on 429)

These headers are absent from the swagger 429 schema
(``docs/swagger/01-general.yaml``) but are sent on every response.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

import httpx

CONFIG = Path(os.path.expanduser('~/.wb-cli/profiles.json'))

PROMO = 'https://advert-api.wildberries.ru'
ANALY = 'https://seller-analytics-api.wildberries.ru'

# Headers to surface in the probe output. Ordered so the most useful values
# (remaining budget, cooldown seconds) appear first.
_RATE_LIMIT_HEADERS: tuple[str, ...] = (
    'x-ratelimit-remaining',
    'x-ratelimit-reset',
    'x-ratelimit-retry',
    'x-ratelimit-limit',
    'Retry-After',
)


def load_tokens() -> tuple[str, str, str]:
    data = json.loads(CONFIG.read_text(encoding='utf-8'))
    active = data['active']
    prof = next(p for p in data['profiles'] if p['name'] == active)
    return active, prof['tokens']['promotion'], prof['tokens']['analytics']


def mask(t: str) -> str:
    return f'{t[:4]}...{t[-4:]}'


def format_rate_headers(headers: httpx.Headers) -> str:
    """Build a compact ``key=value`` summary of every rate-limit header present."""
    parts = []
    for name in _RATE_LIMIT_HEADERS:
        value = headers.get(name)
        if value is not None:
            # Short alias for readability: x-ratelimit-remaining → rem, etc.
            short = {
                'x-ratelimit-remaining': 'rem',
                'x-ratelimit-reset': 'reset',
                'x-ratelimit-retry': 'retry',
                'x-ratelimit-limit': 'lim',
                'Retry-After': 'retry-after',
            }[name]
            parts.append(f'{short}={value}')
    return '  '.join(parts) if parts else '(no rate-limit headers)'


def probe(label: str, method: str, base: str, path: str, *,
          token: str, params=None, json_body=None) -> None:
    url = f'{base}{path}'
    headers = {
        'Authorization': token,
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }
    with httpx.Client(timeout=15.0) as c:
        try:
            r = c.request(method, url, params=params, json=json_body,
                          headers=headers)
        except httpx.TimeoutException as e:
            print(f'[{label}] TIMEOUT: {e}')
            return

    rl_summary = format_rate_headers(r.headers)
    tail = ''
    if r.status_code >= 400:
        body = r.text[:200].replace('\n', ' ')
        tail = f'   body={body!r}'
    print(
        f'[{label:20s}] HTTP {r.status_code:3d}   '
        f'bytes={len(r.content):>6d}   {rl_summary}{tail}'
    )


def main() -> int:
    active, promo, analy = load_tokens()
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    print(f'profile={active}   promo={mask(promo)}   analy={mask(analy)}')
    print(f'probe date = {yesterday}')
    print(
        'rate-limit header legend: rem=x-ratelimit-remaining (calls left), '
        'reset=x-ratelimit-reset (sec until cooldown clears), '
        'retry=x-ratelimit-retry (alias), lim=x-ratelimit-limit'
    )
    print('-' * 70)

    # 1. EP_CAMPAIGN_INFO — GET with status filter in query
    probe('campaign-info', 'GET', PROMO, '/api/advert/v2/adverts',
          token=promo, params={'status': 9})

    # 2. EP_CAMPAIGN_FULLSTATS — GET with ids/beginDate/endDate
    probe('campaign-fullstats', 'GET', PROMO, '/adv/v3/fullstats',
          token=promo, params={
              'ids': '0', 'beginDate': yesterday, 'endDate': yesterday,
          })

    # 3. EP_FUNNEL_PRODUCTS — POST with selectedPeriod (CLAUDE.md quirk)
    probe('funnel-products', 'POST', ANALY,
          '/api/analytics/v3/sales-funnel/products',
          token=analy,
          json_body={
              'timezone': 'Europe/Moscow',
              'selectedPeriod': {'start': yesterday, 'end': yesterday},
              'page': 1, 'limit': 10, 'orderBy': 'orders',
          })
    return 0


if __name__ == '__main__':
    sys.exit(main())
