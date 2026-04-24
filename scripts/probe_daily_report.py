"""Direct probe of the three endpoints used by `wb stats daily-report`.

Bypasses the CLI rate limiter + retry loop: fires one raw httpx request per
endpoint and prints the HTTP status and any Retry-After hint. Shows which
endpoint is currently 429-ing and confirms whether the 429 is coming from
preemptive budget exhaustion (local) or a WB-side global throttle.
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


def load_tokens() -> tuple[str, str, str]:
    data = json.loads(CONFIG.read_text(encoding='utf-8'))
    active = data['active']
    prof = next(p for p in data['profiles'] if p['name'] == active)
    return active, prof['tokens']['promotion'], prof['tokens']['analytics']


def mask(t: str) -> str:
    return f'{t[:4]}...{t[-4:]}'


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
    ra = r.headers.get('Retry-After')
    tail = ''
    if r.status_code >= 400:
        body = r.text[:300].replace('\n', ' ')
        tail = f'   body={body!r}'
    print(f'[{label:20s}] HTTP {r.status_code:3d}   '
          f'Retry-After={ra or "—":<5s}   bytes={len(r.content)}{tail}')


def main() -> int:
    active, promo, analy = load_tokens()
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    print(f'profile={active}   promo={mask(promo)}   analy={mask(analy)}')
    print(f'probe date = {yesterday}')
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
