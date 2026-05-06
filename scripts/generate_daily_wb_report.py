import argparse
import csv
import json
import subprocess
import sys
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path


DATE_FMT = '%Y-%m-%d'
ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = ROOT / 'reports' / 'daily'
EXIT_RATE_LIMITED = 5
MAX_RANGE_DAYS = 7

MERGED_FIELDNAMES = [
    'article_number',
    'product_name',
    'opens',
    'cart_adds',
    'orders',
    'order_sum_rub',
    'buyouts',
    'ad_views',
    'ad_clicks',
    'ad_orders',
    'advertising_costs',
    'avg_position',
    'cpo_rub',
    'drr_percent',
    'cpc_rub',
    'ad_attribution_percent',
]


class RateLimitedError(RuntimeError):
    """Raised when `wb` exits with the RATE_LIMITED code (5).

    Attributes:
        retry_after: Cooldown seconds parsed from the CLI's JSON error
            envelope (``error.retry_after``), or ``None`` when the
            envelope was missing or unparseable.
    """

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Generate daily WB report: ad spend + orders per product.',
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        '--date',
        metavar='YYYY-MM-DD',
        help='Single past date (default: yesterday).',
    )
    group.add_argument(
        '--days',
        type=int,
        metavar='N',
        help=f'Relative range ending yesterday, 1–{MAX_RANGE_DAYS}.',
    )
    group.add_argument(
        '--from',
        dest='from_date',
        metavar='YYYY-MM-DD',
        help='Absolute range start (requires --to).',
    )
    parser.add_argument(
        '--to',
        dest='to_date',
        metavar='YYYY-MM-DD',
        help='Absolute range end (requires --from).',
    )
    return parser.parse_args()


def _parse_date(value: str, flag: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError:
        print(f'Error: {flag} must be YYYY-MM-DD, got: {value}', file=sys.stderr)
        raise SystemExit(2)


def _exit_validation(message: str) -> None:
    print(f'Error: {message}', file=sys.stderr)
    raise SystemExit(2)


def resolve_date_range(args: argparse.Namespace) -> tuple[str, str]:
    """Normalise CLI date flags to ``(from_date, to_date)`` strings."""
    today = date.today()
    yesterday = today - timedelta(days=1)

    if args.days is not None:
        if args.to_date is not None:
            _exit_validation('--to cannot be used with --days')
        if args.days < 1 or args.days > MAX_RANGE_DAYS:
            _exit_validation(f'--days must be 1–{MAX_RANGE_DAYS}, got {args.days}')
        to_d = yesterday
        from_d = to_d - timedelta(days=args.days - 1)
    elif args.from_date is not None:
        if args.to_date is None:
            _exit_validation('--from requires --to')
        from_d = _parse_date(args.from_date, '--from')
        to_d = _parse_date(args.to_date, '--to')
        if from_d > to_d:
            _exit_validation('--from must be <= --to')
        if to_d >= today:
            _exit_validation('--to must be at most yesterday')
        if (to_d - from_d).days + 1 > MAX_RANGE_DAYS:
            _exit_validation(f'range must be <= {MAX_RANGE_DAYS} days')
    else:
        if args.to_date is not None:
            _exit_validation('--to requires --from')
        date_str = args.date or yesterday.strftime(DATE_FMT)
        from_d = to_d = _parse_date(date_str, '--date')
        if from_d >= today:
            _exit_validation('--date must be in the past')

    return from_d.strftime(DATE_FMT), to_d.strftime(DATE_FMT)


def run_wb_command(command: list[str]) -> tuple[object, str]:
    """Run a `wb` CLI command that emits JSON on stdout.

    The CLI is the authority on rate-limit waits — it consults
    ``EndpointBudget`` and the request cache and bails fast with
    ``error.retry_after`` when WB-side cooldowns exceed the threshold.
    This helper does NOT retry; it raises :class:`RateLimitedError`
    immediately so the caller can fall back to persisted artifacts.

    Returns ``(parsed_payload, raw_stdout_text)`` on exit 0.
    Raises :class:`RateLimitedError` on exit 5.
    Raises ``RuntimeError`` for any other non-zero exit.
    """
    proc = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding='utf-8',
    )
    stdout = proc.stdout.strip()
    stderr = proc.stderr.strip()

    if proc.returncode == 0:
        if not stdout:
            raise RuntimeError(f'Empty stdout for command: {" ".join(command)}')
        return json.loads(stdout), stdout

    if proc.returncode == EXIT_RATE_LIMITED:
        retry_after = _parse_retry_after_from_envelope(stdout, stderr)
        msg = (
            f'Rate limited for command: {" ".join(command)}\n'
            f'STDOUT:\n{stdout}\nSTDERR:\n{stderr}'
        )
        raise RateLimitedError(msg, retry_after=retry_after)

    raise RuntimeError(
        f'wb CLI failed (exit={proc.returncode}) for command: {" ".join(command)}\n'
        f'STDOUT:\n{stdout}\nSTDERR:\n{stderr}'
    )


def _parse_retry_after_from_envelope(stdout: str, stderr: str) -> float | None:
    for raw in (stdout, stderr):
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError):
            continue
        if not isinstance(payload, dict):
            continue
        error = payload.get('error')
        if not isinstance(error, dict):
            continue
        value = error.get('retry_after')
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def fetch_daily_report(from_date: str, to_date: str) -> list[dict]:
    """Fetch the rich daily-report payload in a single wb subprocess."""
    payload, _ = run_wb_command([
        'wb', '--json', '--compact', 'stats', 'daily-report',
        '--from', from_date,
        '--to', to_date,
    ])
    if not isinstance(payload, list):
        raise RuntimeError('daily-report payload is not a list')
    return payload


def load_daily_report_payload(path: Path) -> list[dict]:
    with path.open('r', encoding='utf-8') as handle:
        payload = json.load(handle)
    if not isinstance(payload, list):
        raise RuntimeError(f'Daily report artifact is not a list: {path}')
    required_keys = {'nm_id', 'name', 'orders'}
    for item in payload:
        if not isinstance(item, dict) or not required_keys.issubset(item):
            raise RuntimeError(f'Daily report artifact has unexpected shape: {path}')
    return payload


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8',
    )
    tmp.replace(path)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        writer.writerows(rows)


def money(value: object) -> str:
    return str(Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


def _decimal_or_none(value: object) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


def _ratio_2dp(numerator: object, denominator: object) -> str:
    num = _decimal_or_none(numerator)
    den = _decimal_or_none(denominator)
    if num is None or den is None or den == 0:
        return ''
    return str((num / den).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


def _percent_2dp(numerator: object, denominator: object) -> str:
    num = _decimal_or_none(numerator)
    den = _decimal_or_none(denominator)
    if num is None or den is None or den == 0:
        return ''
    return str(
        (num * Decimal('100') / den).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    )


def _percent_1dp(numerator: object, denominator: object) -> str:
    num = _decimal_or_none(numerator)
    den = _decimal_or_none(denominator)
    if num is None or den is None or den == 0:
        return ''
    return str(
        (num * Decimal('100') / den).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)
    )


def _format_position(value: object) -> str:
    d = _decimal_or_none(value)
    if d is None or d == 0:
        return ''
    return str(d.quantize(Decimal('0.1'), rounding=ROUND_HALF_UP))


def build_orders_rows(payload: list[dict]) -> list[dict[str, str]]:
    return [
        {
            'article_number': str(item['nm_id']),
            'product_name': item.get('name', ''),
            'sales-funnel order_count': str(int(item.get('orders', 0))),
        }
        for item in payload
    ]


def build_report_rows(payload: list[dict]) -> list[dict[str, str]]:
    rows = []
    for item in payload:
        order_count = int(item.get('orders', 0))
        order_sum = int(item.get('order_sum', 0))
        ad_clicks = int(item.get('clicks', 0))
        ad_orders = int(item.get('ad_orders', 0))
        spend = item.get('spend', 0)
        rows.append({
            'article_number': str(item['nm_id']),
            'product_name': item.get('name', ''),
            'opens': str(int(item.get('opens', 0))),
            'cart_adds': str(int(item.get('cart_adds', 0))),
            'orders': str(order_count),
            'order_sum_rub': money(order_sum),
            'buyouts': str(int(item.get('buyouts', 0))),
            'ad_views': str(int(item.get('views', 0))),
            'ad_clicks': str(ad_clicks),
            'ad_orders': str(ad_orders),
            'advertising_costs': money(spend),
            'avg_position': _format_position(item.get('avg_position')),
            'cpo_rub': _ratio_2dp(spend, order_count),
            'drr_percent': _percent_2dp(spend, order_sum),
            'cpc_rub': _ratio_2dp(spend, ad_clicks),
            'ad_attribution_percent': _percent_1dp(ad_orders, order_count),
        })
    rows.sort(
        key=lambda row: (
            Decimal(row['advertising_costs']),
            Decimal(row['article_number']),
        ),
        reverse=True,
    )
    return rows


def _log_rate_limited(phase: str, exc: RateLimitedError) -> None:
    if exc.retry_after is not None:
        print(
            f'{phase} rate-limited (~{exc.retry_after:.0f}s cooldown). '
            f'Using persisted artifact.',
            file=sys.stderr,
        )
    else:
        print(f'{phase} rate-limited: {exc}. Using persisted artifact.', file=sys.stderr)


def _artifact_paths(from_date: str, to_date: str) -> tuple[Path, Path, Path]:
    """Return ``(artifact, orders_csv, merged_csv)`` paths for the date range."""
    if from_date == to_date:
        artifact = REPORTS_DIR / f'daily_report_{from_date}_full.json'
        orders_csv = REPORTS_DIR / f'orders_{from_date}_by_nm.csv'
        merged_csv = REPORTS_DIR / f'ad_costs_{from_date}_merged.csv'
    else:
        artifact = REPORTS_DIR / f'daily_report_{from_date}_to_{to_date}_full.json'
        orders_csv = REPORTS_DIR / f'orders_{from_date}_to_{to_date}_by_nm.csv'
        merged_csv = REPORTS_DIR / f'ad_costs_{from_date}_to_{to_date}_merged.csv'
    return artifact, orders_csv, merged_csv


def main() -> int:
    args = parse_args()
    from_date, to_date = resolve_date_range(args)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    artifact_path, orders_csv_path, merged_csv_path = _artifact_paths(from_date, to_date)

    try:
        payload = fetch_daily_report(from_date, to_date)
        write_json(artifact_path, payload)
    except RateLimitedError as exc:
        if not artifact_path.exists():
            cooldown = (
                f' (~{exc.retry_after:.0f}s cooldown)'
                if exc.retry_after is not None else ''
            )
            print(
                f'wb stats daily-report rate-limited{cooldown}; '
                f'no persisted artifact for {from_date}–{to_date} to fall back to.',
                file=sys.stderr,
            )
            return EXIT_RATE_LIMITED
        _log_rate_limited('Daily report fetch', exc)
        payload = load_daily_report_payload(artifact_path)

    orders_rows = build_orders_rows(payload)
    merged_rows = build_report_rows(payload)

    write_csv(
        orders_csv_path,
        ['article_number', 'product_name', 'sales-funnel order_count'],
        orders_rows,
    )
    write_csv(merged_csv_path, MERGED_FIELDNAMES, merged_rows)

    summary = {
        'from_date': from_date,
        'to_date': to_date,
        'artifact_path': str(artifact_path),
        'orders_csv_path': str(orders_csv_path),
        'merged_csv_path': str(merged_csv_path),
        'orders_rows': len(orders_rows),
        'merged_rows': len(merged_rows),
    }
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
