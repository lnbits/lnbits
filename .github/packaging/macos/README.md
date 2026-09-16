# macOS release packaging

The Python/PyInstaller and Tkinter app supports macOS 15 or later, with separate
native Apple Silicon (`arm64`) and Intel (`x86_64`) builds. Its bundle identifier
is `com.lnbits.desktop`. Each image contains `LNbits.app`, an Applications
shortcut, and instructions appropriate to its signing status. User data lives
outside the app in `~/Library/Application Support/LNbits` by default.

The macOS packaging and bundled funding implementation was selectively ported
from [arcbtc/lnbits at f664f0d](https://github.com/arcbtc/lnbits/tree/f664f0db96bd469405126852a7cd7a3ee42399fd).
The original checkout already had the shared desktop entry point, but no macOS
workflow, DMG builder, or sidecars. The port includes the required packaging
helpers and tests; it does not import wallet changes, package version changes,
or Python dependency/lockfile updates. Bundled funding is enabled only for
macOS in this checkout. See [funding documentation](../README.md) for the pinned
Node, Phoenixd and Spark versions, persistence, licensing, and offline checks.

## Prerequisites

Build on the target Mac architecture, without Rosetta. Install Python 3.12 with
Tk (`python3 -c 'import tkinter'` must work), Node/npm 24, uv, Rust/Cargo,
Homebrew `openssl@3`, and current Xcode command-line tools. Accept Xcode's license
and check `xcrun notarytool --version`. Signing requires an Apple Developer
Program membership, a valid Developer ID Application certificate **with its
private key**, and access to Apple's authentication, timestamp, and notarization
services. Native dependency downloads and npm audit also require network access.

The command prepares locked dependencies and frontend assets, preserving the
fork's static OpenSSL check. Intel's locked cryptography release is built from
source. We clear its uv cache and reinstall with `OPENSSL_STATIC=1` and Homebrew's
`OPENSSL_DIR`, then reject native bindings that still link shared `libssl` or
`libcrypto`. This prevents PyInstaller from substituting an incompatible Python
OpenSSL library. See [cryptography's build instructions](https://cryptography.io/en/latest/installation/#building-cryptography-on-macos).
No project dependency or version update is needed.

## Certificate and credentials

In Keychain Access, find your **Developer ID Application: Name (TEAMID)** entry
under My Certificates. Expand it and confirm that its private key is present.
Export the certificate **and private key** as a password-protected `.p12`. A
Developer ID Installer or Apple Development certificate will not work. Export
only one current matching Developer ID Application identity; expired, untrusted,
wrong-team, missing-private-key, or ambiguous matching identities fail the build.

Base64-encode that export into a private file, without displaying it:

```sh
umask 077
base64 -i /private/path/DeveloperID.p12 -o /private/path/certificate.base64
```

Keep both files private. Use these exact six names locally and as GitHub Actions
repository/environment secrets:

| Name                          | Value                                                                                                    |
| ----------------------------- | -------------------------------------------------------------------------------------------------------- |
| `BUILD_CERTIFICATE_BASE64`    | Base64-encoded P12 containing the certificate and private key; use a single line in the local file.      |
| `P12_PASSWORD`                | The password chosen when exporting the P12.                                                              |
| `KEYCHAIN_PASSWORD`           | A separate strong password for the disposable build keychain; this is not your login password.           |
| `APPLE_ID`                    | The Apple account email associated with the developer team.                                              |
| `APPLE_TEAM_ID`               | The ten-character Team ID from the Apple Developer account, matching the certificate.                    |
| `APPLE_APP_SPECIFIC_PASSWORD` | An app-specific password generated at account.apple.com for this Apple account, not its normal password. |

`.env.macos-release` is explicitly ignored by Git and is separate from LNbits'
runtime `.env`. A tracked [example](.env.macos-release.example) contains mock
values. A private mock local file was created during implementation only if it
did not already exist. To initialize a fresh checkout without overwriting a file:

```sh
python3 - <<'PY'
import os
from pathlib import Path
try:
    fd = os.open('.env.macos-release', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
except FileExistsError:
    pass
else:
    with os.fdopen(fd, 'w') as stream:
        stream.write(Path('.github/packaging/macos/.env.macos-release.example').read_text())
PY
```

Edit the local file privately and replace all six mock values. It must have mode
`0600` (`chmod 600 .env.macos-release`). Use `NAME=value` or `NAME="value"`, one per
line. There is no shell evaluation, variable expansion, multiline value syntax,
or inline comment syntax. Do not `source` it or put these values in LNbits'
runtime configuration. The release process reads it explicitly and removes all
six variables from frontend, dependency, PyInstaller, and smoke-test subprocess
environments. It never includes the file in the application.

## Exact local commands

From the repository root, build an ad-hoc development DMG without Apple credentials:

```sh
make build-macos
```

After configuring `.env.macos-release`, build a signed release artifact:

```sh
make build-macos-release
```

Both commands build the current Mac's native architecture and produce
`dist/LNbits-v<VERSION>-macOS-<ARCH>.dmg` and `.dmg.sha256`. Version normalization
is unchanged: for example, `1.6.2-rc1` becomes `1.6.2rc1` in the filename and
`1.6.2` in the app metadata. Neither command publishes or creates a release.
Build on each architecture; this is not a universal binary or a cross compiler.

The original development entry points remain available after dependency setup:

```sh
uv run --no-sync python .github/packaging/build.py
uv run --no-sync python .github/packaging/macos/dmg.py
```

The latter finalizes, ad-hoc signs and checks the existing app, then verifies the
final mounted image. It does not submit anything to Apple. Merely setting
`MACOS_CODESIGN_IDENTITY` on `build.py` does not notarize a release.

## Shared release sequence and cleanup

`macos/release.py` implements both local and CI release operations:

1. Build the app, preserving dependency checks, then finalize all metadata.
2. Decode the P12 inside a unique mode-0700 temporary directory, create/unlock a
   temporary keychain, import the identity, remove the P12, and set the
   `apple-tool:,apple:,codesign:` key partition list for unattended signing.
   Save the original keychain search list, and store validated notarytool
   credentials in this temporary keychain.
3. Select exactly one valid Developer ID Application identity for the team.
   Recursively detect Mach-O code by file magic, including files collected as
   data inside Spark. Sign native files and nested bundles from the inside out,
   then sign `LNbits.app`. All final signatures explicitly specify that identity
   and temporary keychain, hardened runtime where applicable, and Apple's default
   `--timestamp`. PyInstaller's preliminary ad-hoc signatures and signing
   warnings are superseded only by successful explicit signing and verification.
4. Verify every nested signature's Developer ID requirement, team, hardened
   runtime, secure timestamp and exact entitlement policy. Create a temporary ZIP
   with `ditto`, submit it once to `notarytool`, retain the submission ID, and wait
   at most 30 minutes for JSON status exactly `Accepted`. Staple and validate the
   app ticket. The ZIP is removed; the app is never modified or re-signed again.
5. Copy that stapled app with `ditto` (preserving tickets, xattrs and symlinks) into
   the final DMG, sign the DMG, submit it once separately, require `Accepted`, then
   staple and validate the DMG. There are **two submissions**, one for the app ZIP
   and one for the final image. The DMG is not rebuilt after notarization.
6. Verify final image integrity, signature, ticket and Gatekeeper assessment.
   Mount that exact image read-only and verify the contained app with
   `codesign --verify --deep --strict`, Developer ID/team requirements, Gatekeeper,
   stapler, native architecture and required bundled data checks. Run the existing
   sidecar authentication/shutdown and packaged server smoke checks, plus packaged
   Tk launcher/quit and Wasmtime execution checks, with disposable external data.
7. Detach the image, restore and verify the original keychain search list, delete
   the keychain and temporary directory, then generate and recheck the SHA-256
   checksum against the final stapled DMG bytes. Any failure, including cleanup,
   fails the release and removes the attempted DMG/checksum.

A private recovery journal under `build/` contains paths and the original search
list, never credentials. Normal exceptions and SIGINT/SIGTERM trigger cleanup.
After an uncatchable termination or machine restart, recover before building:

```sh
python3 .github/packaging/macos/release.py --cleanup
```

Do not run concurrent local builds using the same checkout. CI uses a journal in
`RUNNER_TEMP` and an `always()` cleanup step **before** artifact upload. The journal
is retained if cleanup fails, so recovery can be retried. For a custom journal,
pass `--state /path/to/state.json` to both the build and cleanup commands.

## Entitlements

The policy is deliberately smaller than upstream general-purpose runtimes'
entitlement lists:

- **LNbits/Python executable and enclosing app:**
  `com.apple.security.cs.allow-unsigned-executable-memory`. The locked Wasmtime
  runtime publishes compiled WebAssembly code using ordinary `mmap` and
  `mprotect(PROT_EXEC)`, without `MAP_JIT`; `allow-jit` alone does not cover that
  path. See the [Wasmtime v45 implementation](https://github.com/bytecodealliance/wasmtime/blob/v45.0.0/crates/wasmtime/src/runtime/vm/sys/unix/mmap.rs).
- **Node executable:** `com.apple.security.cs.allow-jit`. The pinned Node/V8
  allocator uses `MAP_JIT` for executable allocations on Darwin, including Intel.
  See the [pinned V8 allocator](https://github.com/nodejs/node/blob/v24.21.0/deps/v8/src/base/platform/platform-posix.cc).
  All shipped native add-ons are re-signed by the same team, so loading them does
  not require disabling library validation.
- **Phoenixd, Python/Tk libraries, extensions and other native libraries:** no
  executable-memory exceptions. The [Phoenixd distribution](https://github.com/ACINQ/phoenixd)
  uses Kotlin/Native on macOS rather than a JVM JIT. Entitlements belong on the
  host executable, not each loaded library.

No debug entitlement, disabled library validation, disabled executable-page
protection, DYLD environment exception, or Electron entitlements are enabled.
`MACOS_ENTITLEMENTS_FILE` can select a Python plist only if its contents equal
this policy; an override cannot silently broaden a release. If set on the shared
release script, `MACOS_CODESIGN_IDENTITY` must equal the selected certificate's
fingerprint. Credential-based selection remains authoritative.

These choices must still be confirmed in real Developer ID builds on **both**
architectures. The mounted smoke checks execute Wasmtime-generated code and Node
and exercise the native Phoenixd executable; failures stop publication.

## GitHub Actions

`macos.yml` retains `macos-15` (arm64) and `macos-15-intel` (x86_64). Ordinary branch
pushes build ad-hoc artifacts without secrets. Manual `workflow_dispatch` accepts
`signed: true` with an empty tag for signed, notarized **artifact-only** builds.
A nonempty release tag always forces the signed path regardless of the checkbox.
The stable and RC callers explicitly pass all six secrets and `signed: true`.
Missing credentials never fall back to ad-hoc signing. Other platform jobs and
release triggers are unchanged.

Credentials are scoped to the signed build step. Dependency preparation and
launcher/packaging tests run separately without them. Both modes call the same
implementation as the local commands. Upload requires successful signing,
notarization, final-image smoke checks, checksum generation, and cleanup.

## Troubleshooting and release validation

- **Identity/import failure:** export the certificate with its private key, check
  P12 password, certificate expiry, trust chain and team, and remove ambiguous
  matching certificates from the exported P12. The login keychain is not used to
  silently fill in missing credentials.
- **Authentication failure (401/403):** verify Apple ID, Team ID, app-specific
  password, developer membership and any pending Apple agreements. Store-credentials
  validates the account before submission. Do not paste secrets into build logs.
- **Timestamp failure:** allow Apple's timestamp service through the network or
  proxy and check the system clock. The command uses `--timestamp` without a
  custom URL; never work around a release failure by omitting timestamps.
- **Notarization rejection or timeout:** logs show a sanitized operation name,
  submission ID and status, and rejection diagnostics where available. `Accepted`
  is the only passing status. A timeout fails the build even if Apple's service
  later completes. Investigate that ID in Apple's tools before retrying; the
  pipeline never automatically submits the same artifact again.
- **Gatekeeper or smoke failure:** check the exact image on the matching native
  architecture; do not disable Gatekeeper or broaden entitlements without finding
  the failing executable/runtime requirement.

Run `make test-desktop` for mocked Apple-tool tests, identity validation,
notarization/signing order, failure and cleanup gates, checksum generation,
launcher controls, and bundled funding lifecycle tests. No test uses real Apple
credentials or submits real notarization. CI additionally tests the final mounted
contents. Before distribution, test an actually downloaded/quarantined signed DMG
on macOS 15 on each architecture: drag to Applications, open normally, configure,
start, install an extension, stop, restart and quit. Hosted CI and mocks cannot
establish real Apple acceptance, quarantine behavior or every runtime on both Macs.

See [Apple's notarization workflow](https://developer.apple.com/documentation/security/customizing-the-notarization-workflow)
and [code-signing guidance](https://developer.apple.com/documentation/technotes/tn3161-inside-code-signing-certificates).
