import argparse
import csv
import json
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path


DATE_FMT = "%Y-%m-%d"
ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = ROOT / "reports" / "daily"

EXIT_RATE_LIMITED = 5

# F-16: spend-relevant endpoints. The script's mid-run rate-status check
# scopes its lock detection to these — locks on unrelated endpoints
# (like sales-funnel) shouldn't abort the spend phase.
SPEND_RELEVANT_ENDPOINTS = frozenset({
    '/api/advert/v2/adverts',
    '/adv/v3/fullstats',
})

MERGED_FIELDNAMES = [
    "article_number",
    "product_name",
    "opens",
    "cart_adds",
    "orders",
    "order_sum_rub",
    "buyouts",
    "ad_views",
    "ad_clicks",
    "ad_orders",
    "advertising_costs",
    "avg_position",
    "cpo_rub",
    "drr_percent",
    "cpc_rub",
    "ad_attribution_percent",
]


class RateLimitedError(RuntimeError):
    """Raised when `wb` exits with the RATE_LIMITED code (5).

    Attributes:
        retry_after: Cooldown seconds parsed from the CLI's JSON error
            envelope (``error.retry_after``), or ``None`` when the
            envelope was missing or unparseable. Surfaces the WB-supplied
            cooldown so logs and operators see how long to wait without
            having to re-run.
    """

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--date",
        default=(date.today() - timedelta(days=1)).strftime(DATE_FMT),
        help="Report date in YYYY-MM-DD format. Defaults to yesterday.",
    )
    return parser.parse_args()


def run_wb_command(command: list[str]) -> tuple[object, str]:
    """Run a `wb` CLI command that emits JSON on stdout.

    The CLI is the authority on rate-limit waits — it consults
    ``EndpointBudget`` and the I-15 ``RequestCache`` and bails fast with
    ``error.retry_after`` when WB-side cooldowns exceed the in-process
    threshold. Re-running with hardcoded waits on top would only fight
    that authority, so this helper does NOT retry rate-limited calls;
    it parses ``retry_after`` from the JSON envelope and raises
    immediately.

    Returns ``(parsed_payload, raw_stdout_text)`` when wb exits 0.
    Raises :class:`RateLimitedError` on exit code 5, with ``retry_after``
    populated when available.
    Raises ``RuntimeError`` for any other non-zero exit.
    """
    proc = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    stdout = proc.stdout.strip()
    stderr = proc.stderr.strip()

    if proc.returncode == 0:
        if not stdout:
            raise RuntimeError(f"Empty stdout for command: {' '.join(command)}")
        return json.loads(stdout), stdout

    if proc.returncode == EXIT_RATE_LIMITED:
        retry_after = _parse_retry_after_from_envelope(stdout, stderr)
        msg = (
            f"Rate limited for command: {' '.join(command)}\n"
            f"STDOUT:\n{stdout}\nSTDERR:\n{stderr}"
        )
        raise RateLimitedError(msg, retry_after=retry_after)

    raise RuntimeError(
        f"wb CLI failed (exit={proc.returncode}) for command: {' '.join(command)}\n"
        f"STDOUT:\n{stdout}\nSTDERR:\n{stderr}"
    )


def _parse_retry_after_from_envelope(stdout: str, stderr: str) -> float | None:
    """Extract ``error.retry_after`` from the CLI's JSON error envelope.

    The CLI emits the envelope to stdout in ``--json`` mode; in human
    mode it goes to stderr. Try both, fall back to ``None`` when the
    payload doesn't parse or doesn't carry ``retry_after``.
    """
    for raw in (stdout, stderr):
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError):
            continue
        if not isinstance(payload, dict):
            continue
        error = payload.get("error")
        if not isinstance(error, dict):
            continue
        value = error.get("retry_after")
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def read_rate_status() -> dict:
    """Run ``wb rate status`` and return the parsed payload.

    Reads ``~/.wb-cli/rate_limits.db`` only — no HTTP, no rate-limit
    consumption. With HOME isolation dropped (F-16), the script and
    the operator's interactive shell now share one DB, so any
    observation visible here is also visible to ``wb rate status`` from
    a separate terminal.

    Returns an empty dict when the command output cannot be parsed.
    """
    proc = subprocess.run(
        ["wb", "--json", "rate", "status"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    text = (proc.stdout or proc.stderr).strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def find_active_lock(status: dict) -> tuple[bool, float, str | None]:
    """Walk the sellers→tokens→endpoints tree and find the longest lock.

    Returns ``(is_locked, cooldown_seconds, endpoint_path)``. A lock is
    counted only when the endpoint row has ``locked: true``; the
    ``cooldown_seconds`` is the largest ``reset_in_s`` among locked rows.
    """
    return find_active_lock_for(status, endpoints=None)


def find_active_lock_for(
        status: dict,
        endpoints: frozenset[str] | None,
) -> tuple[bool, float, str | None]:
    """Filtered variant of :func:`find_active_lock`.

    When ``endpoints`` is provided, only locks on those paths are
    counted. Used by :func:`acquire_payloads` to scope the mid-run
    re-check to the spend phase's endpoint family
    (:data:`SPEND_RELEVANT_ENDPOINTS`) — a lock on, say, sales-funnel
    after orders fetch shouldn't abort spend.

    Args:
        status: Parsed payload from :func:`read_rate_status`.
        endpoints: Set of endpoint paths to consider, or ``None`` for
            all endpoints (matches :func:`find_active_lock`).

    Returns:
        ``(is_locked, cooldown_seconds, endpoint_path)``.
    """
    longest = 0.0
    locked_endpoint: str | None = None
    for seller in status.get("sellers", []) or []:
        for token in seller.get("tokens", []) or []:
            for endpoint in token.get("endpoints", []) or []:
                if not endpoint.get("locked"):
                    continue
                path = endpoint.get("endpoint")
                if endpoints is not None and path not in endpoints:
                    continue
                reset_in = float(endpoint.get("reset_in_s") or 0.0)
                if reset_in > longest:
                    longest = reset_in
                    locked_endpoint = path
    return locked_endpoint is not None, longest, locked_endpoint


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    tmp_path.replace(path)


def load_orders_payload(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, list):
        raise RuntimeError(f"Orders raw artifact is not a list: {path}")
    required_keys = {"nm_id", "title", "order_count"}
    for item in payload:
        if not isinstance(item, dict) or not required_keys.issubset(item):
            raise RuntimeError(f"Orders raw artifact has an unexpected shape: {path}")
    return payload


def load_spend_payload(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise RuntimeError(f"Spend raw artifact is not an object: {path}")
    if not isinstance(payload.get("results"), dict):
        raise RuntimeError(f"Spend raw artifact has no results map: {path}")
    return payload


def money(value: object) -> str:
    decimal_value = Decimal(str(value))
    return str(decimal_value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _decimal_or_none(value: object) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


def _ratio_2dp(numerator: object, denominator: object) -> str:
    num = _decimal_or_none(numerator)
    den = _decimal_or_none(denominator)
    if num is None or den is None or den == 0:
        return ""
    return str((num / den).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _percent_2dp(numerator: object, denominator: object) -> str:
    num = _decimal_or_none(numerator)
    den = _decimal_or_none(denominator)
    if num is None or den is None or den == 0:
        return ""
    return str(
        (num * Decimal("100") / den).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    )


def _percent_1dp(numerator: object, denominator: object) -> str:
    num = _decimal_or_none(numerator)
    den = _decimal_or_none(denominator)
    if num is None or den is None or den == 0:
        return ""
    return str(
        (num * Decimal("100") / den).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    )


def _format_position(value: object) -> str:
    decimal_value = _decimal_or_none(value)
    if decimal_value is None or decimal_value == 0:
        return ""
    return str(decimal_value.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def build_orders_rows(orders_payload: list[dict]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for item in orders_payload:
        rows.append(
            {
                "article_number": str(item["nm_id"]),
                "product_name": item["title"],
                "sales-funnel order_count": str(item["order_count"]),
            }
        )
    return rows


def collect_spend_results(spend_payload: dict) -> dict[int, dict]:
    results = spend_payload.get("results", {})
    spend_by_nm: dict[int, dict] = {}
    for spend_item in results.values():
        spend_by_nm[int(spend_item["nm_id"])] = spend_item
    return spend_by_nm


def build_spend_rows(
    orders_payload: list[dict],
    spend_by_nm: dict[int, dict],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for order_item in orders_payload:
        nm_id = int(order_item["nm_id"])
        spend_item = spend_by_nm.get(nm_id, {})

        order_count = int(order_item.get("order_count", 0))
        order_sum = int(order_item.get("order_sum", 0))
        ad_clicks = int(spend_item.get("clicks", 0))
        ad_orders = int(spend_item.get("orders", 0))
        spend_value = spend_item.get("spend", 0)

        rows.append(
            {
                "article_number": str(nm_id),
                "product_name": order_item.get("title", ""),
                "opens": str(int(order_item.get("open_count", 0))),
                "cart_adds": str(int(order_item.get("cart_count", 0))),
                "orders": str(order_count),
                "order_sum_rub": money(order_sum),
                "buyouts": str(int(order_item.get("buyout_count", 0))),
                "ad_views": str(int(spend_item.get("views", 0))),
                "ad_clicks": str(ad_clicks),
                "ad_orders": str(ad_orders),
                "advertising_costs": money(spend_value),
                "avg_position": _format_position(spend_item.get("avg_position")),
                "cpo_rub": _ratio_2dp(spend_value, order_count),
                "drr_percent": _percent_2dp(spend_value, order_sum),
                "cpc_rub": _ratio_2dp(spend_value, ad_clicks),
                "ad_attribution_percent": _percent_1dp(ad_orders, order_count),
            }
        )
    rows.sort(
        key=lambda row: (
            Decimal(row["advertising_costs"]),
            Decimal(row["article_number"]),
        ),
        reverse=True,
    )
    return rows


def fetch_orders_payload(report_date: str) -> list[dict]:
    """Fetch the full sales-funnel payload for the date.

    Relies on the CLI's ``--all`` flag (I-10) for auto-pagination and on
    the shared rate limiter (I-12) + I-15 request cache for throttling
    and cross-process reuse — no script-level retries needed.
    """
    payload, _ = run_wb_command(
        [
            "wb",
            "--json",
            "--compact",
            "analytics",
            "sales-funnel",
            "products",
            "--from",
            report_date,
            "--to",
            report_date,
            "--all",
        ],
    )
    if not isinstance(payload, list):
        raise RuntimeError("Orders payload is not a list")
    return payload


def fetch_spend_payload(report_date: str, nm_ids: list[str]) -> dict:
    """Fetch product-spend in a single ``wb`` invocation.

    The CLI internally chunks campaign-stats batches at ``FULLSTATS_BATCH_SIZE``
    and (since I-15) caches ``list_campaigns`` so repeated invocations
    share the campaign list. Splitting NMs into outer chunks added no
    value and turned every chunk into its own subprocess + rate-limit
    bucket consumer. One invocation passes them all and lets the CLI
    aggregate.
    """
    if not nm_ids:
        return {
            "source": "wb stats product-spend",
            "date": report_date,
            "results": {},
            "errors": [],
        }
    chunk_payload, _ = run_wb_command(
        [
            "wb",
            "--json",
            "--compact",
            "stats",
            "product-spend",
            "--nms",
            ",".join(nm_ids),
            "--from",
            report_date,
            "--to",
            report_date,
        ],
    )
    if not isinstance(chunk_payload, list):
        raise RuntimeError("Spend payload is not a list")
    results = {str(item["nm_id"]): item for item in chunk_payload}
    return {
        "source": "wb stats product-spend",
        "date": report_date,
        "requested_nm_ids": list(nm_ids),
        "results": results,
        "errors": [],
    }


def verify_spend_rows_against_payloads(
    rows: list[dict[str, str]],
    orders_by_nm: dict[int, dict],
) -> list[dict[str, str]]:
    expected_article_numbers = {str(nm_id) for nm_id in orders_by_nm}
    actual_article_numbers = {row["article_number"] for row in rows}
    if actual_article_numbers != expected_article_numbers:
        raise RuntimeError("Merged rows do not cover the same NM IDs as the orders payload")
    return rows


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        writer.writerows(rows)


def verify_orders_csv(csv_path: Path, orders_payload: list[dict]) -> None:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    expected_rows = build_orders_rows(orders_payload)
    if rows != expected_rows:
        raise RuntimeError(f"Orders CSV verification failed for {csv_path}")


def verify_merged_csv(csv_path: Path, orders_payload: list[dict], spend_payload: dict) -> None:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    spend_by_nm = collect_spend_results(spend_payload)
    orders_by_nm = {int(item["nm_id"]): item for item in orders_payload}
    expected_rows = verify_spend_rows_against_payloads(
        build_spend_rows(orders_payload, spend_by_nm),
        orders_by_nm,
    )
    if rows != expected_rows:
        raise RuntimeError(f"Merged CSV verification failed for {csv_path}")


def acquire_payloads(
    report_date: str,
    orders_raw_path: Path,
    spend_raw_path: Path,
) -> tuple[list[dict], dict]:
    """Acquire orders + spend payloads for ``report_date``.

    Reads ``wb rate status`` (no HTTP) before each phase and walks
    :func:`find_active_lock_for` scoped to the relevant endpoint family.
    When a phase's endpoints are locked, falls back to the persisted
    raw artifact if it exists; otherwise exits with the rate-limit
    code. On the normal path, each fetch catches its own
    :class:`RateLimitedError` and falls back to persisted artifacts
    if available.
    """
    # Phase 1: orders.
    try:
        orders_payload = fetch_orders_payload(report_date)
        write_json(orders_raw_path, orders_payload)
    except RateLimitedError as exc:
        if not orders_raw_path.exists():
            raise
        _log_rate_limited('Orders fetch', exc)
        orders_payload = load_orders_payload(orders_raw_path)

    # Phase 2: product-spend. Re-check rate status between phases —
    # orders touched the analytics endpoint family, but a spend-phase
    # lock could have been observed by a parallel `wb` invocation in
    # the gap. Skip re-check if a persisted artifact would let us
    # rebuild without firing more HTTP anyway.
    spend_status = read_rate_status()
    is_locked, cooldown, locked_endpoint = find_active_lock_for(
        spend_status, endpoints=SPEND_RELEVANT_ENDPOINTS,
    )
    if is_locked:
        if spend_raw_path.exists():
            print(
                f"wb rate status: {locked_endpoint} locked ({cooldown:.0f}s). "
                "Rebuilding spend CSV from persisted artifact.",
                file=sys.stderr,
            )
            return orders_payload, load_spend_payload(spend_raw_path)
        print(
            f"wb rate status: {locked_endpoint} locked ({cooldown:.0f}s) and no "
            f"persisted spend artifact exists for {report_date}.",
            file=sys.stderr,
        )
        raise SystemExit(EXIT_RATE_LIMITED)

    nm_ids = [str(item["nm_id"]) for item in orders_payload]
    try:
        spend_payload = fetch_spend_payload(report_date, nm_ids)
        write_json(spend_raw_path, spend_payload)
    except RateLimitedError as exc:
        if not spend_raw_path.exists():
            raise
        _log_rate_limited('Spend fetch', exc)
        spend_payload = load_spend_payload(spend_raw_path)

    return orders_payload, spend_payload


def _log_rate_limited(phase: str, exc: RateLimitedError) -> None:
    """Surface the WB-supplied cooldown when falling back to an artifact."""
    if exc.retry_after is not None:
        print(
            f"{phase} rate-limited (~{exc.retry_after:.0f}s cooldown). "
            f"Using persisted artifact.",
            file=sys.stderr,
        )
    else:
        print(
            f"{phase} rate-limited: {exc}. Using persisted artifact.",
            file=sys.stderr,
        )


def main() -> int:
    args = parse_args()
    report_date = args.date
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    orders_raw_path = REPORTS_DIR / f"orders_{report_date}_raw.json"
    spend_raw_path = REPORTS_DIR / f"product_spend_{report_date}_raw.json"
    bundle_raw_path = REPORTS_DIR / f"daily_report_{report_date}_raw.json"
    orders_csv_path = REPORTS_DIR / f"orders_{report_date}_by_nm.csv"
    merged_csv_path = REPORTS_DIR / f"ad_costs_{report_date}_merged.csv"

    try:
        orders_payload, spend_payload = acquire_payloads(
            report_date, orders_raw_path, spend_raw_path,
        )
    except RateLimitedError as exc:
        # Bubbled past acquire_payloads' fallback (no persisted artifact
        # to use). Convert to a clean exit-5 with the WB-supplied
        # cooldown so the operator / cron logs see a single line, not
        # a Python traceback.
        cooldown = (
            f' (~{exc.retry_after:.0f}s cooldown)'
            if exc.retry_after is not None else ''
        )
        print(
            f'wb stats product-spend rate-limited{cooldown}; '
            f'no persisted artifact for {report_date} to fall back to.',
            file=sys.stderr,
        )
        return EXIT_RATE_LIMITED

    orders_rows = build_orders_rows(orders_payload)
    write_csv(
        orders_csv_path,
        ["article_number", "product_name", "sales-funnel order_count"],
        orders_rows,
    )

    orders_by_nm = {int(item["nm_id"]): item for item in orders_payload}
    spend_by_nm = collect_spend_results(spend_payload)
    merged_rows = verify_spend_rows_against_payloads(
        build_spend_rows(orders_payload, spend_by_nm),
        orders_by_nm,
    )
    write_csv(merged_csv_path, MERGED_FIELDNAMES, merged_rows)

    verify_orders_csv(orders_csv_path, orders_payload)
    verify_merged_csv(merged_csv_path, orders_payload, spend_payload)

    bundle_payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": report_date,
        "sources": {
            "orders": "wb --json --compact analytics sales-funnel products --all",
            "spend": "wb --json --compact stats product-spend",
        },
        "artifacts": {
            "orders_raw_path": str(orders_raw_path),
            "spend_raw_path": str(spend_raw_path),
            "orders_csv_path": str(orders_csv_path),
            "merged_csv_path": str(merged_csv_path),
        },
        "orders": orders_payload,
        "product_spend": spend_payload,
    }
    write_json(bundle_raw_path, bundle_payload)

    summary = {
        "date": report_date,
        "orders_raw_path": str(orders_raw_path),
        "spend_raw_path": str(spend_raw_path),
        "bundle_raw_path": str(bundle_raw_path),
        "orders_csv_path": str(orders_csv_path),
        "merged_csv_path": str(merged_csv_path),
        "orders_rows": len(orders_rows),
        "merged_rows": len(merged_rows),
    }
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
