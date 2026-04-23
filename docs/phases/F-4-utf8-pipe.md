# Fix F-4 — UTF-8 Pipe Fix (v0.20.2)

**Date:** 2026-04-17 | **Tests:** 987 passed

## Problem

`wb campaign list | more` crashed with `UnicodeEncodeError: 'charmap' codec can't encode characters`. WB content is in Russian (Cyrillic). Agent shells inheriting the Windows legacy code page (cp437) received no output — the process crashed silently.

## Root Cause

`sys.stdout` encoding was never reconfigured at startup. Python inherited cp437 on piped stdout. Secondary: 10 bare `Console()` calls across CLI modules bypassed the centralized `_stdout_console`.

## Fix

| File | Change |
|------|--------|
| `src/wb/cli/app.py` | `sys.stdout/stderr.reconfigure(encoding='utf-8', errors='replace')` at top of `main()` |
| `src/wb/cli/auth.py` | Replaced 2× `Console()` with `_stdout_console` |
| `src/wb/cli/campaign.py` | `console = Console()` → `_stdout_console` |
| `src/wb/cli/portal.py` | `Console().print(table)` → `_stdout_console.print(table)` |
| `src/wb/cli/prices.py` | Same |
| `src/wb/cli/product.py` | Same |
| `src/wb/cli/pulse.py` | `console = Console()` → `_stdout_console` |
| `src/wb/cli/report.py` | 3× `Console().print(table)` → `_stdout_console.print(table)` |
