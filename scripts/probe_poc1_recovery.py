"""PoC-1: Measure the recovery window of WB's seller-global throttle.

Polls a lightweight endpoint (`GET /api/advert/v2/adverts?status=9`) every
15 s until it returns a non-429 status, printing a timestamped status line
for each probe. Confirms whether the F-9 patient backoff schedule
(5 / 15 / 45 s) covers the actual clear time.
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
POLL_INTERVAL = 15.0
MAX_MINUTES = 10


def load_promo_token() -> tuple[str, str]:
    data = json.loads(CONFIG.read_text(encoding='utf-8'))
    active = data['active']
    prof = next(p for p in data['profiles'] if p['name'] == active)
    return active, prof['tokens']['promotion']


def ts() -> str:
    return datetime.now().strftime('%H:%M:%S')


def main() -> int:
    profile, token = load_promo_token()
    headers = {
        'Authorization': token,
        'Accept': 'application/json',
    }
    print(f'[{ts()}] profile={profile}   endpoint={PATH}   poll={POLL_INTERVAL:.0f}s')
    print(f'[{ts()}] will abort after {MAX_MINUTES} minutes')
    print('-' * 70)

    start = time.time()
    deadline = start + MAX_MINUTES * 60
    attempt = 0
    first_ok_at: float | None = None

    with httpx.Client(timeout=10.0) as c:
        while time.time() < deadline:
            attempt += 1
            try:
                r = c.get(f'{PROMO}{PATH}', params={'status': 9}, headers=headers)
                elapsed = time.time() - start
                print(f'[{ts()}] attempt={attempt:3d}  t+{elapsed:5.1f}s   HTTP {r.status_code}')
                if r.status_code != 429:
                    first_ok_at = elapsed
                    print()
                    print(f'RECOVERED at t+{elapsed:.1f}s on attempt {attempt}   status={r.status_code}')
                    return 0
            except httpx.RequestError as e:
                print(f'[{ts()}] attempt={attempt}  NET ERROR: {e}')
            time.sleep(POLL_INTERVAL)

    print()
    print(f'TIMEOUT after {MAX_MINUTES}min; still 429')
    return 1


if __name__ == '__main__':
    sys.exit(main())
