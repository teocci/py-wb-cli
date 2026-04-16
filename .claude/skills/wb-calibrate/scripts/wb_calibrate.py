"""Strategy calibration script for wb-calibrate skill.

Reads 30-day campaign analytics grouped by [goal] name prefix, computes
observed CTR/spend/order ranges per strategy, and updates rules.json.
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

_RULES_PATH = Path.home() / '.wb-cli' / 'rules.json'
_KEYWORD_RULES_PATH = Path.home() / '.wb-cli' / 'keyword_rules.json'
_RULES_TEMPLATE = Path(__file__).parent.parent / 'rules.json'
_KEYWORD_RULES_TEMPLATE = Path(__file__).parent.parent.parent / 'wb-keywords' / 'keyword_rules.json'

_GOAL_PATTERN = re.compile(r'^\[([^\]]+)\]')
_MIN_VIEWS_TO_VALIDATE = 100
_MIN_DAYS_TO_VALIDATE = 7
_HIGH_CONFIDENCE_VIEWS = 500


def _run_wb(args: list[str]) -> dict | list:
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


def _load_json(path: Path, template: Path | None = None) -> dict:
    if not path.exists():
        if template and template.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(template.read_text(encoding='utf-8'), encoding='utf-8')
            return json.loads(path.read_text(encoding='utf-8'))
        return {}
    return json.loads(path.read_text(encoding='utf-8'))


def _save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def _extract_goal(name: str) -> str | None:
    m = _GOAL_PATTERN.match(name or '')
    return m.group(1) if m else None


def _fetch_campaign_stats(campaign_ids: list[int], date_from: str, date_to: str) -> list[dict]:
    if not campaign_ids:
        return []
    ids_str = ','.join(str(i) for i in campaign_ids)
    raw = _run_wb(['stats', 'campaigns', '--ids', ids_str, '--from', date_from, '--to', date_to, '--compact'])
    return raw if isinstance(raw, list) else (raw.get('campaigns') or [])


def _group_stats_by_goal(campaigns: list[dict], stats: list[dict]) -> dict[str, list]:
    name_by_id = {c['campaign_id']: c.get('name', '') for c in campaigns if 'campaign_id' in c}
    by_goal: dict[str, list] = {}
    for s in stats:
        cid = s.get('campaign_id')
        goal = _extract_goal(name_by_id.get(cid, ''))
        if goal:
            by_goal.setdefault(goal, []).append(s)
    return by_goal


def _compute_strategy_metrics(entries: list[dict]) -> dict:
    total_views = sum(e.get('views', 0) or 0 for e in entries)
    total_clicks = sum(e.get('clicks', 0) or 0 for e in entries)
    total_orders = sum(e.get('orders', 0) or 0 for e in entries)
    total_spend = sum((e.get('spend', 0) or 0) / 100 for e in entries)
    ctr = (total_clicks / total_views * 100) if total_views > 0 else 0.0
    return {
        'total_views': total_views,
        'total_clicks': total_clicks,
        'total_orders': total_orders,
        'total_spend_rub': round(total_spend, 2),
        'ctr': round(ctr, 2),
        'cpc_rub': round(total_spend / total_clicks, 2) if total_clicks > 0 else 0.0,
    }


def _decide_bid_percentile(current: int, ctr: float, goal: str) -> int:
    if goal in ('new_product_visibility', 'volume_sales'):
        if ctr < 1.5:
            return min(current + 5, 95)
        if ctr > 4.0:
            return max(current - 5, 50)
    elif goal in ('steady_low_cost', 'brand_defense'):
        if ctr < 0.8:
            return min(current + 5, 75)
        if ctr > 3.0:
            return max(current - 5, 40)
    return current


def _calibrate_rules(rules: dict, by_goal: dict, days: int) -> tuple[dict, list, dict, dict]:
    strategies = rules.get('strategies', {})
    updated, skipped, changes, skip_reasons = [], [], {}, {}

    for goal, entries in by_goal.items():
        if goal not in strategies:
            skipped.append(goal)
            skip_reasons[goal] = 'unknown_goal'
            continue

        metrics = _compute_strategy_metrics(entries)
        if metrics['total_views'] < _MIN_VIEWS_TO_VALIDATE:
            skipped.append(goal)
            skip_reasons[goal] = f'insufficient_data: only {metrics["total_views"]} views'
            continue

        strat = strategies[goal]
        old_percentile = strat.get('bid_percentile', 50)
        new_percentile = _decide_bid_percentile(old_percentile, metrics['ctr'], goal)
        confidence = 'high' if metrics['total_views'] >= _HIGH_CONFIDENCE_VIEWS else 'medium'

        if new_percentile != old_percentile or not strat.get('validated'):
            changes[goal] = {
                'bid_percentile': {'old': old_percentile, 'new': new_percentile},
                'validated': True,
                'ctr_observed': metrics['ctr'],
            }

        strat['bid_percentile'] = new_percentile
        strat['validated'] = True
        strategies[goal] = strat
        updated.append(goal)

    rules['strategies'] = strategies
    rules['last_calibrated'] = date.today().isoformat()
    rules['confidence'] = 'high' if all(s.get('validated') for s in strategies.values()) else 'medium'
    return rules, skipped, changes, skip_reasons


def main() -> None:
    parser = argparse.ArgumentParser(description='Strategy calibration')
    parser.add_argument('--days', type=int, default=30)
    args = parser.parse_args()

    today = date.today()
    date_to = (today - timedelta(days=1)).isoformat()
    date_from = (today - timedelta(days=args.days)).isoformat()

    rules = _load_json(_RULES_PATH, _RULES_TEMPLATE)
    if not rules:
        print(json.dumps({'error': 'rules.json not found and template missing'}, indent=2))
        sys.exit(1)

    raw_campaigns = _run_wb(['campaign', 'list', '--status', 'running', '--json', '--compact'])
    campaigns = raw_campaigns if isinstance(raw_campaigns, list) else (raw_campaigns.get('campaigns') or [])
    campaign_ids = [c['campaign_id'] for c in campaigns if 'campaign_id' in c]

    stats = _fetch_campaign_stats(campaign_ids, date_from, date_to)
    by_goal = _group_stats_by_goal(campaigns, stats)

    updated_rules, skipped, changes, skip_reasons = _calibrate_rules(rules, by_goal, args.days)
    _save_json(_RULES_PATH, updated_rules)

    output = {
        'calibrated_at': today.isoformat(),
        'strategies_updated': list(changes.keys()),
        'strategies_skipped': skipped,
        'skip_reasons': skip_reasons,
        'changes': changes,
        'note': 'Re-run wb-launch dry-runs for active campaigns using updated strategies.' if changes else 'No changes.',
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
