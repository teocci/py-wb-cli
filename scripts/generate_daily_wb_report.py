import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path


DATE_FMT = "%Y-%m-%d"
ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = ROOT / "reports" / "daily"
WB_HOME_DIR = ROOT / ".home"
WB_CONFIG_DIR = WB_HOME_DIR / ".wb-cli"
SPEND_CHUNK_SIZE = 80

EXIT_RATE_LIMITED = 5

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
    """Raised when `wb` exits with the RATE_LIMITED code (5) after retries."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--date",
        default=(date.today() - timedelta(days=1)).strftime(DATE_FMT),
        help="Report date in YYYY-MM-DD format. Defaults to yesterday.",
    )
    return parser.parse_args()


def build_wb_env() -> dict[str, str]:
    env = os.environ.copy()
    WB_CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    source_config_dir = Path.home() / ".wb-cli"
    for filename in ("profiles.json", "audit.jsonl"):
        source = source_config_dir / filename
        target = WB_CONFIG_DIR / filename
        if source.exists() and not target.exists():
            shutil.copy2(source, target)

    env["HOME"] = str(WB_HOME_DIR)
    env["USERPROFILE"] = str(WB_HOME_DIR)
    return env


def run_wb_command(command: list[str], *, retry_waits: list[int]) -> tuple[object, str]:
    """Run a `wb` CLI command that emits JSON on stdout.

    Returns ``(parsed_payload, raw_stdout_text)`` when wb exits 0.
    Raises :class:`RateLimitedError` after retries exhaust on exit 5.
    Raises ``RuntimeError`` for any other non-zero exit.
    """
    env = build_wb_env()
    last_error = ""
    for attempt in range(len(retry_waits) + 1):
        proc = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
        )
        stdout = proc.stdout.strip()
        stderr = proc.stderr.strip()

        if proc.returncode == 0:
            if not stdout:
                raise RuntimeError(f"Empty stdout for command: {' '.join(command)}")
            return json.loads(stdout), stdout

        if proc.returncode == EXIT_RATE_LIMITED:
            last_error = (
                f"Rate limited for command: {' '.join(command)}\n"
                f"STDOUT:\n{stdout}\nSTDERR:\n{stderr}"
            )
            if attempt < len(retry_waits):
                time.sleep(retry_waits[attempt])
                continue
            raise RateLimitedError(last_error)

        raise RuntimeError(
            f"wb CLI failed (exit={proc.returncode}) for command: {' '.join(command)}\n"
            f"STDOUT:\n{stdout}\nSTDERR:\n{stderr}"
        )
    raise RateLimitedError(last_error)


def read_rate_status() -> dict:
    """Run ``wb rate status`` and return the parsed payload.

    ``wb rate status`` reads ``~/.wb-cli/rate_limits.db`` only — it does not
    make any HTTP call, so it does not consume seller-budget calls. Use this
    as a pre-flight "is any endpoint already locked?" check.

    Since R-3 the payload is ``{now_epoch, profile, sellers: [...]}``. Walk
    ``find_active_lock`` to flatten it down to a single "longest active
    cooldown" reading. If our local DB has not yet seen a WB-side 429, no
    endpoint will be marked locked even when WB is in fact about to trip
    us — the first real fetch will refresh state once WB reports the
    cooldown via the response headers.

    Returns an empty dict when the command output cannot be parsed.
    """
    env = build_wb_env()
    proc = subprocess.run(
        ["wb", "--json", "rate", "status"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
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
    longest = 0.0
    locked_endpoint: str | None = None
    for seller in status.get("sellers", []) or []:
        for token in seller.get("tokens", []) or []:
            for endpoint in token.get("endpoints", []) or []:
                if not endpoint.get("locked"):
                    continue
                reset_in = float(endpoint.get("reset_in_s") or 0.0)
                if reset_in > longest:
                    longest = reset_in
                    locked_endpoint = endpoint.get("endpoint")
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

    Relies on the CLI's ``--all`` flag (I-10) for auto-pagination and on the
    shared rate limiter (I-12) for throttling — no script-level sleeps needed.
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
        retry_waits=[60, 120, 180],
    )
    if not isinstance(payload, list):
        raise RuntimeError("Orders payload is not a list")
    return payload


def fetch_spend_payload(report_date: str, nm_ids: list[str]) -> dict:
    """Fetch product-spend in chunks of ``SPEND_CHUNK_SIZE`` NM IDs.

    The shared rate limiter preempts per-endpoint limits across chunks; no
    manual sleeps between chunks.
    """
    chunk_payloads: list[dict] = []
    aggregated_results: dict[str, dict] = {}
    for start in range(0, len(nm_ids), SPEND_CHUNK_SIZE):
        chunk_nm_ids = nm_ids[start : start + SPEND_CHUNK_SIZE]
        chunk_payload, _ = run_wb_command(
            [
                "wb",
                "--json",
                "--compact",
                "stats",
                "product-spend",
                "--nms",
                ",".join(chunk_nm_ids),
                "--from",
                report_date,
                "--to",
                report_date,
            ],
            retry_waits=[20, 60],
        )
        if not isinstance(chunk_payload, list):
            raise RuntimeError("Spend payload chunk is not a list")
        chunk_results = {str(item["nm_id"]): item for item in chunk_payload}
        normalized_payload = {"results": chunk_results, "errors": []}
        chunk_payloads.append(
            {
                "requested_nm_ids": chunk_nm_ids,
                "payload": normalized_payload,
            }
        )
        aggregated_results.update(chunk_results)
    return {
        "source": "wb stats product-spend",
        "date": report_date,
        "chunk_size": SPEND_CHUNK_SIZE,
        "chunks": chunk_payloads,
        "results": aggregated_results,
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

    Reads ``wb rate status`` (no HTTP) first. When any endpoint is already
    locked, falls back to the persisted raw artifacts if they exist; otherwise
    exits with the rate-limit code. On the normal path, each fetch catches
    its own :class:`RateLimitedError` and falls back to persisted artifacts
    if available.
    """
    status = read_rate_status()
    is_locked, cooldown, locked_endpoint = find_active_lock(status)

    if is_locked:
        if orders_raw_path.exists() and spend_raw_path.exists():
            print(
                f"wb rate status: {locked_endpoint} locked ({cooldown:.0f}s). "
                "Rebuilding CSVs from persisted artifacts.",
                file=sys.stderr,
            )
            return (
                load_orders_payload(orders_raw_path),
                load_spend_payload(spend_raw_path),
            )
        print(
            f"wb rate status: {locked_endpoint} locked ({cooldown:.0f}s) and no "
            f"persisted artifacts exist for {report_date}.",
            file=sys.stderr,
        )
        raise SystemExit(EXIT_RATE_LIMITED)

    try:
        orders_payload = fetch_orders_payload(report_date)
        write_json(orders_raw_path, orders_payload)
    except RateLimitedError as exc:
        if not orders_raw_path.exists():
            raise
        print(f"Orders fetch rate-limited: {exc}. Using persisted artifact.", file=sys.stderr)
        orders_payload = load_orders_payload(orders_raw_path)

    nm_ids = [str(item["nm_id"]) for item in orders_payload]
    try:
        spend_payload = fetch_spend_payload(report_date, nm_ids)
        write_json(spend_raw_path, spend_payload)
    except RateLimitedError as exc:
        if not spend_raw_path.exists():
            raise
        print(f"Spend fetch rate-limited: {exc}. Using persisted artifact.", file=sys.stderr)
        spend_payload = load_spend_payload(spend_raw_path)

    return orders_payload, spend_payload


def main() -> int:
    args = parse_args()
    report_date = args.date
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    orders_raw_path = REPORTS_DIR / f"orders_{report_date}_raw.json"
    spend_raw_path = REPORTS_DIR / f"product_spend_{report_date}_raw.json"
    bundle_raw_path = REPORTS_DIR / f"daily_report_{report_date}_raw.json"
    orders_csv_path = REPORTS_DIR / f"orders_{report_date}_by_nm.csv"
    merged_csv_path = REPORTS_DIR / f"ad_costs_{report_date}_merged.csv"

    orders_payload, spend_payload = acquire_payloads(
        report_date, orders_raw_path, spend_raw_path,
    )

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
