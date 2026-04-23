# Phase I-6 — Full Token Category Support (v0.19.0)

**Date:** 2026-04-08 | **Tests:** +34 tests

## What Was Built

- 11 category slugs + `ALL_CATEGORY` sentinel + `CATEGORY_DISPLAY_NAMES` dict in `core/constants.py`
- `ProfileStore.save_token` loops over `TOKEN_CATEGORIES` when `category == 'all'`
- `wb auth categories` subcommand: table/JSON listing of all valid slugs + the `all` meta-shortcut
- Token validation fires when `--category all` (promotion is included)

## Usage

```bash
wb auth login --token "<jwt>" --category all   # saves under all 11 categories
wb auth categories                              # list valid --category values
wb auth categories --json
```
