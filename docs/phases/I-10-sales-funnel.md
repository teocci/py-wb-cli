# Phase I-10 — Sales-Funnel --min-orders + --all (v0.23.0)

**Date:** 2026-04-21

## What Was Built

- `--min-orders N` option on `wb analytics sales-funnel products`: client-side post-filter dropping rows where `order_count < N`
- `--all` flag: auto-paginate with `page_size=1000` using existing `paginate_all`; ignores `--limit`/`--offset`
- 7 new tests in `tests/unit/test_analytics_sorting.py`: filter correctness, pagination loop, edge cases

## Agent Usage

```bash
wb --json analytics sales-funnel products \
  --from 2026-04-20 --to 2026-04-20 \
  --sort-by orders --min-orders 1 --all
```

Rate limit: `EP_FUNNEL_PRODUCTS` = 3/min; `--all` at 1000 rows/page completes in 1 call for most sellers.
