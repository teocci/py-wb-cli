# Fix F-8 — Empty PaymentType Crash (v0.20.6)

**Date:** 2026-04-20 | **Tests:** 990 passed (+2)

## Problem

`wb campaign list` crashes with `ValueError: '' is not a valid PaymentType` when WB API returns `{"payment_type": ""}`.

## Root Cause

`Campaign.from_api()` in `domain/models.py`:
```python
payment_type=PaymentType(settings.get('payment_type', 'cpm')),
```
`.get(key, default)` only uses the default when the key is **absent**. An empty string is returned and passed to `PaymentType('')`.

## Fix

```python
payment_type=PaymentType(settings.get('payment_type') or 'cpm'),
```
Both `''` and `None` are falsy; `'cpm'` is used as fallback in both cases.

**Files:** `src/wb/domain/models.py` (line 85), `tests/unit/test_campaign_service.py` (+2 parametrized regression tests)
