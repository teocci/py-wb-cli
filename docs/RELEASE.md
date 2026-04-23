# WB CLI — Release Process

`wb` ships as a portable one-directory bundle (PyInstaller) for Windows, Linux, and macOS.

## Version Semantics

`MAJOR.MINOR.PATCH` where:
- `MINOR` bump = new improvement (I-N phase complete)
- `PATCH` bump = bug fix (F-N phase complete)
- `MAJOR` bump = breaking architecture change

## How to Cut a Release

1. Bump version in two places (must match):
   - [src/wb/__init__.py](../src/wb/__init__.py) — `__version__ = 'X.Y.Z'`
   - [pyproject.toml](../pyproject.toml) — `version = 'X.Y.Z'`
2. Append entry to [CHANGELOG.md](../CHANGELOG.md)
3. Commit: `git commit -am 'release: vX.Y.Z — <theme>'`
4. Tag and push:
   ```bash
   git tag vX.Y.Z
   git push origin main
   git push origin vX.Y.Z
   ```
5. The [Release workflow](../.github/workflows/release.yml) triggers on the tag, builds bundles for all three OSes, and publishes a GitHub Release with the zips attached.

> Use the `phase-complete` skill to handle steps 1–3 automatically after a phase ships.

## Release History

| Tag | Version | Date | Notes |
|-----|---------|------|-------|
| v0.23.0 | 0.23.0 | 2026-04-21 | sales-funnel --min-orders + --all |
| v0.22.0 | 0.22.0 | 2026-04-21 | stats daily-report + wb-daily-report skill |
| v0.21.0 | 0.21.0 | 2026-04-21 | stats campaigns --status filter |
| v0.20.6 | 0.20.6 | 2026-04-20 | Empty PaymentType crash fix |
| v0.20.5 | 0.20.5 | 2026-04-19 | campaign list --fields projection fix |
| v0.20.4 | 0.20.4 | 2026-04-19 | TTY-aware ANSI output |
| v0.20.3 | 0.20.3 | 2026-04-19 | Budget unit fix + unified bid_type |
| v0.20.2 | 0.20.2 | 2026-04-17 | UTF-8 pipe fix |
| v0.20.0 | 0.20.0 | 2026-04-17 | Agent skills — wb assess/pulse + 7 skills |
| v0.19.0 | 0.19.0 | 2026-04-08 | Full token category support |
| v0.18.0 | 0.18.0 | 2026-04-08 | First release — polish & agent ergonomics |

> AI Agent instructions: when cutting a release, add a row here and update the Quick Status in [docs/PROGRESS.md](PROGRESS.md).

## Local Build (for testing the spec)

```bash
$VENV/pip install pyinstaller
$VENV/pyinstaller packaging/wb.spec --noconfirm --clean
./dist/wb/wb --version    # Linux/macOS
dist\wb\wb.exe --version  # Windows
```

## Tradeoffs

| Concern | Status |
|---|---|
| Code signing | Unsigned. Windows SmartScreen on first run; macOS needs `xattr -dr com.apple.quarantine`. |
| Bundle size | ~30–50 MB per OS. |
| macOS Intel | `macos-latest` is arm64-only. Add `macos-13` to the matrix if Intel users complain. |
| Auto-update | None — users re-download zips. |
| `keyring` on headless Linux | May fall back to file backend without D-Bus. `WB_API_TOKEN` env-var covers this. |
