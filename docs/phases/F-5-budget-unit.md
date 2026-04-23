# Fix F-5 — Budget Unit + Unified Bid Type (v0.20.3)

**Date:** 2026-04-19 | **Tests:** 990 passed

## Bug A — Budget Deposit Unit

WB `/adv/v1/budget/deposit` `sum` field expects **rubles**, not kopecks. The wb-launch and wb-manage skills were multiplying `budget_rub * 100`, causing 100× over-deposit (1000 RUB → 100,000 RUB deposited). WB minimum is 1000 RUB, multiple of 50 RUB.

**Fix:** Updated `services/budgets.py` docstrings, `cli/budget.py` `--sum` help, skill SKILL.md files. Removed `* 100` conversion.

## Bug B — Unified Bid Type Must Omit placement_types

WB API: `placement_types` is "Specify for campaign with custom bid only". For `bid_type: unified`, sending `placement_types` confuses the API.

**Fix:** `CampaignCreate.to_api()` in `domain/models.py` — skip `placement_types` for unified `bid_type`.
