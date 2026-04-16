"""Keyword lifecycle analysis for wb-keywords skill.

Calls wb cluster commands sequentially, joins keyword_rules.json lifecycle state,
and outputs a ranked report of hot/underperforming/blocked/ready-to-restore keywords.
"""

import argparse
import json
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

_KEYWORD_RULES_PATH = Path.home() / '.wb-cli' / 'keyword_rules.json'
_TEMPLATE_PATH = Path(__file__).parent.parent / 'keyword_rules.json'

_CTR_BLOCK_THRESHOLD = 1.0
_CTR_HOT_THRESHOLD = 3.0
_SPEND_BLOCK_THRESHOLD_RUB = 50.0
_RESTORE_AFTER_DAYS = 14


def _run_wb(args: list[str]) -> dict:
    result = subprocess.run(
        [sys.executable, '-m', 'wb', '--json'] + args,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return {}
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {}


def _load_rules() -> dict:
    if not _KEYWORD_RULES_PATH.exists():
        if _TEMPLATE_PATH.exists():
            _KEYWORD_RULES_PATH.parent.mkdir(parents=True, exist_ok=True)
            _KEYWORD_RULES_PATH.write_text(_TEMPLATE_PATH.read_text(encoding='utf-8'), encoding='utf-8')
        return {'version': 1, 'keywords': {}}
    return json.loads(_KEYWORD_RULES_PATH.read_text(encoding='utf-8'))


def _save_rules(rules: dict) -> None:
    _KEYWORD_RULES_PATH.parent.mkdir(parents=True, exist_ok=True)
    _KEYWORD_RULES_PATH.write_text(json.dumps(rules, ensure_ascii=False, indent=2), encoding='utf-8')


def _days_since(date_str: str) -> int:
    try:
        blocked = date.fromisoformat(date_str)
        return (date.today() - blocked).days
    except (ValueError, TypeError):
        return 0


def _collect_cluster_data(campaign_id: int, nm_id: int, days: int) -> tuple[list, list, list]:
    today = date.today().isoformat()
    from_date = (date.today() - timedelta(days=days)).isoformat()

    raw_list = _run_wb(['cluster', 'list', '--campaign', str(campaign_id), '--nm', str(nm_id), '--compact'])
    raw_stats = _run_wb([
        'cluster', 'stats',
        '--campaign', str(campaign_id),
        '--nm', str(nm_id),
        '--from', from_date,
        '--to', today,
        '--compact',
    ])
    raw_minus = _run_wb(['cluster', 'minus', 'list', '--campaign', str(campaign_id), '--nm', str(nm_id), '--compact'])

    clusters = raw_list.get('clusters') or []
    stats = raw_stats.get('stats') or []
    minus_phrases = {p.lower() for p in (raw_minus.get('phrases') or [])}

    return clusters, stats, minus_phrases


def _build_keyword_report(
    clusters: list,
    stats: list,
    minus_phrases: set,
    rules: dict,
    campaign_id: int,
    nm_id: int,
) -> dict:
    stats_by_query = {s['query'].lower(): s for s in stats if 'query' in s}
    keywords_state = rules.get('keywords', {})

    hot, underperforming, blocked_list, ready_to_restore = [], [], [], []

    for cluster in clusters:
        query = cluster.get('name', '').lower()
        if not query:
            continue

        kw_stat = stats_by_query.get(query, {})
        views = kw_stat.get('views', 0) or 0
        clicks = kw_stat.get('clicks', 0) or 0
        orders = kw_stat.get('orders', 0) or 0
        spend_rub = (kw_stat.get('spend', 0) or 0) / 100
        ctr = (clicks / views * 100) if views > 0 else 0.0

        state = keywords_state.get(query, {})
        status = state.get('status', 'active')

        if query in minus_phrases or status == 'blocked':
            days_blocked = _days_since(state.get('blocked_since', ''))
            restore_after = state.get('restore_after_days', _RESTORE_AFTER_DAYS)
            entry = {'query': query, 'blocked_since': state.get('blocked_since'), 'blocked_days': days_blocked}
            blocked_list.append(entry)
            if days_blocked >= restore_after:
                ready_to_restore.append(entry)
            continue

        if ctr >= _CTR_HOT_THRESHOLD or orders >= 3:
            hot.append({'query': query, 'ctr': round(ctr, 2), 'orders': orders})
        elif views >= 50 and (ctr < _CTR_BLOCK_THRESHOLD or spend_rub > _SPEND_BLOCK_THRESHOLD_RUB):
            underperforming.append({
                'query': query,
                'ctr': round(ctr, 2),
                'spend_rub': round(spend_rub, 2),
                'suggestion': 'block',
            })

    return {
        'hot': sorted(hot, key=lambda x: -x['ctr']),
        'underperforming': sorted(underperforming, key=lambda x: x['ctr']),
        'blocked': blocked_list,
        'ready_to_restore': ready_to_restore,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description='Keyword lifecycle analysis')
    parser.add_argument('--campaign', type=int, required=True)
    parser.add_argument('--nm', type=int, required=True)
    parser.add_argument('--days', type=int, default=14)
    args = parser.parse_args()

    rules = _load_rules()
    clusters, stats, minus_phrases = _collect_cluster_data(args.campaign, args.nm, args.days)
    report = _build_keyword_report(clusters, stats, minus_phrases, rules, args.campaign, args.nm)

    output = {
        'data_as_of': date.today().isoformat(),
        'campaign_id': args.campaign,
        'nm_id': args.nm,
        **report,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
