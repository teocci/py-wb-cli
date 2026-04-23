# Fix F-6 — TTY-Aware ANSI Output (v0.20.4)

**Date:** 2026-04-19 | **Tests:** 988 passed

## Problem

Commands piped to files, `2>&1` captures, or agent shells received raw ANSI escape codes (e.g. `[3m ... [0m`), making output unparseable.

## Root Cause

`_stdout_console` in `core/output.py` was created with `force_terminal=True`, which forced ANSI output regardless of TTY state. `cli/assess.py` had its own `Console(force_terminal=True)`.

## Fix

| File | Change |
|------|--------|
| `src/wb/core/output.py` | `force_terminal=True` → `force_terminal=sys.stdout.isatty()` on both consoles; added `import sys` |
| `src/wb/cli/assess.py` | Removed local `Console(force_terminal=True)`; use shared `_stdout_console` |

`legacy_windows=False` retained on both consoles for UTF-8 correctness regardless of TTY state.
