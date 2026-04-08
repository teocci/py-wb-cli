# Release Process

`wb` is shipped as a **portable one-directory bundle** built by GitHub Actions for Windows, Linux, and macOS. End users download a zip, extract it, and run the binary — no Python installation required.

## Quick Status Dashboard (for AI Agents)

| Metric | Value | Status |
|--------|-------|--------|
| **Latest Release Tag** | v0.19.0 | ✅ Tagged |
| **Latest Bundle Version** | 0.18.0 | ✅ Matches source |
| **Pipeline** | `.github/workflows/release.yml` | ✅ Ready |
| **Targets** | windows-x64, linux-x64, macos-arm64 | ✅ 3 platforms |
| **Signing** | Unsigned | ⚠️ SmartScreen / Gatekeeper warning |
| **Spec** | `packaging/wb.spec` | ✅ Ready |

### Release History

| Tag | Version | Date | Notes |
|-----|---------|------|-------|
| v0.19.0 | 0.19.0 | 2026-04-08 | Full token category support |
| v0.18.0 | 0.18.0 | 2026-04-08 | First release — polish & agent ergonomics |

> **AI Agent instructions:** When cutting a release, update the table above with the new tag, version, and date. The tag must match `git tag --list 'v*'`. Update **Latest Release Tag** and add a row to Release History.

## How to cut a release

1. Bump the version in two places (must match):
   - [src/wb/__init__.py](src/wb/__init__.py) — `__version__ = 'X.Y.Z'`
   - [pyproject.toml](pyproject.toml) — `version = 'X.Y.Z'`
2. Commit the bump: `git commit -am 'release: vX.Y.Z'`
3. Tag and push:
   ```bash
   git tag vX.Y.Z
   git push origin main
   git push origin vX.Y.Z
   ```
4. The [Release workflow](.github/workflows/release.yml) triggers on the tag, builds bundles for all three OSes, and publishes a GitHub Release with the zips attached.

You can also dispatch the workflow manually from the Actions tab without creating a release (build-only, useful for CI verification).

## Local build (for testing the spec)

From the repo root, with the venv active:

```bash
$VENV/pip install pyinstaller
$VENV/pyinstaller packaging/wb.spec --noconfirm --clean
./dist/wb/wb --version    # Linux/macOS
dist\wb\wb.exe --version  # Windows
```

The output is in `dist/wb/`. Both `dist/` and `build/` should be in `.gitignore`.

## End-user install instructions

### Windows
1. Download `wb-X.Y.Z-windows-x64.zip` from the [Releases page](https://github.com/teocci/py-wb-cli/releases).
2. Extract anywhere (e.g. `C:\Tools\wb\`).
3. Run `wb.exe` from the extracted folder, or add the folder to `PATH`.
4. **First run:** Windows SmartScreen may show "Windows protected your PC" — click **More info → Run anyway**. The binary is unsigned (see Tradeoffs below).

### Linux
```bash
unzip wb-X.Y.Z-linux-x64.zip
sudo mv wb /opt/wb
sudo ln -s /opt/wb/wb /usr/local/bin/wb
wb --version
```

### macOS (Apple Silicon)
```bash
unzip wb-X.Y.Z-macos-arm64.zip
xattr -dr com.apple.quarantine wb        # remove Gatekeeper quarantine flag
mv wb /usr/local/wb
ln -s /usr/local/wb/wb /usr/local/bin/wb
wb --version
```

## Architecture

The release pipeline consists of three pieces:

| File | Purpose |
|---|---|
| [packaging/wb.spec](packaging/wb.spec) | PyInstaller build spec — hidden imports, data files, output layout |
| [.github/workflows/release.yml](.github/workflows/release.yml) | Tag-triggered matrix build (windows/linux/macos) + GitHub Release publish |
| RELEASE.md | This file |

The spec explicitly collects:
- `keyring.backends.*` — backend selection is dynamic; PyInstaller can't see it statically
- `pydantic` + `pydantic_core` — pulls in the C extension
- `wb.*` — every CLI submodule (some are imported via Typer's lazy command registration)
- `certifi` data files — `httpx` needs the CA bundle on Windows

## Tradeoffs

| Concern | Status |
|---|---|
| **Code signing** | Bundles are unsigned. Windows shows SmartScreen on first run; macOS requires `xattr -dr com.apple.quarantine`. Acceptable for current scale; revisit if adoption grows. |
| **Bundle size** | ~30–50 MB per OS. Cost of bundling the interpreter. |
| **macOS Intel** | `macos-latest` is arm64-only. Add `macos-13` to the matrix in [release.yml](.github/workflows/release.yml) if Intel users complain. |
| **Auto-update** | None — users re-download zips. Fine for the current audience. |
| **`keyring` on headless Linux** | May fall back to file backend without D-Bus / `secretstorage`. The `WB_API_TOKEN` env-var fallback (see [CLAUDE.md](CLAUDE.md)) covers this case. |

## Verifying a build

After downloading a release zip:

```bash
./wb version
./wb --help
./wb auth --help
./wb portal --help
```

If `--version` prints but `auth --help` crashes with `ModuleNotFoundError`, a hidden import is missing — add it to `hidden_imports` in [packaging/wb.spec](packaging/wb.spec) and rebuild.
