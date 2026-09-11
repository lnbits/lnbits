# macOS release packaging

The `Build LNbits macOS DMG` workflow builds native Apple Silicon (`arm64`)
and Intel (`x86_64`) apps on macOS 15 runners. macOS 15 is the supported minimum.
Each DMG contains `LNbits.app`, an Applications shortcut and first-launch
instructions. Python, Tk, frontend assets and required native dependencies
are included in the app.

Branch builds upload DMGs and SHA-256 checksums as Actions artifacts. The
stable and release-candidate workflows also attach them to the GitHub release.
Manual runs accept an optional release tag; leave it empty for an artifact-only
build. Version information comes from `pyproject.toml`.

CI checks the app architecture, bundled certificate/data files, code signatures,
disk-image integrity, launcher controls and server shutdown. The packaged server
is tested from the final read-only DMG, with its data outside the app bundle.
Before publishing, also check a downloaded DMG on a Mac: drag to Applications,
approve its first launch, open the configuration window, start LNbits, install an
extension, stop, restart and quit. Hosted CI does not reproduce Gatekeeper's
download quarantine or every user's macOS configuration.

## Build locally

On a Mac with Python 3.12 (including Tk), Node/npm, uv and the Xcode command-line tools,
from the repository root:

```sh
uv sync --locked --no-dev --no-editable
uv pip install pyinstaller==6.22.2
uv run --no-sync python .github/packaging/build.py
uv run --no-sync python -m unittest discover -s .github/packaging -v
uv run --no-sync python .github/packaging/macos/dmg.py
```

Build on each target architecture. A universal app would additionally require
universal builds of every native dependency. Linux cannot build this macOS app.

The app includes Spark L2 and Phoenixd. See the shared
[funding documentation](../README.md) for pins, persistence and verification.

## Signing status

Current CI artifacts use ad-hoc signatures, which provide no verified developer
identity. They are **not Developer ID signed or notarized**. Their first launch
may require approval in System Settings > Privacy & Security > Open Anyway.
Do not disable Gatekeeper or System Integrity Protection.

When a Developer ID becomes available, the build and DMG scripts accept
`MACOS_CODESIGN_IDENTITY` and `MACOS_ENTITLEMENTS_FILE`. Supply the same values to
both scripts; PyInstaller signs nested binaries and the DMG script re-signs the
app after setting its metadata. Developer ID builds enable hardened runtime.
Validate any required native/JIT entitlements on macOS before distributing them.
Certificate import, Apple notarization, ticket stapling and verification must
then be added to CI with protected credentials. Setting an identity alone does
not notarize an app. Recompute the DMG checksum after signing or stapling it.

See [Apple's distribution guidance](https://developer.apple.com/developer-id/)
and [PyInstaller's macOS signing documentation](https://pyinstaller.org/en/stable/feature-notes.html#macos-binary-code-signing).
