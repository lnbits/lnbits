# Desktop funding sources

The shared launcher offers **Neither**, **Spark L2**, and, on Linux/macOS,
**Phoenixd**. Choose an unused daemon port, then launch LNbits. Neither starts
LNbits using its normal funding settings. Spark/Phoenixd start locally, wait for
an authenticated wallet API response, and configure the existing LNbits backend.
Python, Node.js and the daemons do not need to be installed by the user.
An internet connection is needed for either funding service.

Managed funding requires a new local SQLite data folder on first setup. An
existing LNbits database cannot be attached to a newly generated backing wallet,
and changing between Spark and Phoenixd requires a separate data folder. These
guards prevent existing user balances being backed by a different wallet.
External database URLs are not supported in managed mode. Neither retains the
normal LNbits database and funding configuration options.

## Persistence and backup

The selected provider and port are remembered in `funding/profile.json` within
the chosen LNbits data folder. Selecting Neither explicitly skips daemon startup
for that launch. Each provider's identity is generated once:

- Spark: 24 words in `funding/spark/seed.dat`.
- Phoenixd: 12 words in `funding/phoenixd/seed.dat`, alongside its database and
  `phoenix.conf`.

Restarting, updating the app, or changing the daemon port reuses the same seed.
A missing or invalid seed in an existing profile stops startup; the launcher
never silently generates a replacement. Back up the **whole data folder** with
the app stopped, and keep an offline copy of the seed. The files contain secrets;
store backups privately. Never run two Phoenix instances with the same seed.
The launcher prevents concurrent managed launches using the same data folder.

The daemon binds to `127.0.0.1` and requires a random API password/key generated
for each launch. Connection settings are authoritative for the managed LNbits
worker, so stale saved backend settings cannot override the selected daemon.
Change the managed port/provider in the launcher, rather than LNbits admin.

Closing the launcher stops LNbits first, then the daemon. LNbits' own restart
keeps the daemon running. A daemon failure stops LNbits and reports an error;
there is no automatic switch to another funding source. The daemon supervisor
also shuts down when its launcher pipe closes unexpectedly.

Phoenixd first setup asks users to acknowledge seed backup and automatic
liquidity fees/fee credit. See [ACINQ's liquidity documentation](https://phoenix.acinq.co/server/auto-liquidity).
Logs are under `logs/desktop.log`, `logs/spark.log` or `logs/phoenixd.log`.

Headless examples (using the same persistent `LNBITS_DATA_FOLDER` each time):

```sh
LNbits --headless --funding-source spark --funding-port 8765 --port 5000
LNbits --headless --funding-source phoenixd --funding-port 9740 --accept-phoenixd-terms
```

The terms flag is needed only for Phoenixd's first headless setup. Omit
`--funding-source` on later launches to reuse the saved provider and port.

## Build and verification

`build.py` prepares runtimes before invoking PyInstaller. `sidecars/pins.json`
pins Node 24.21.0 and Phoenixd 0.9.0 with SHA-256 checksums. Each build resolves
Spark's latest published stable GitHub release to a commit and downloads that
revision. Its release tag and revision appear in the build log; the tag, revision
and downloaded archive's SHA-256 are recorded in the bundled `sidecars/pins.json`.
Downloads occur at build time only. Drafts and prereleases are excluded; a
missing release or failed download fails the build without falling back to a branch.
Builds require npm; Linux builds also require `libcrypt.so.1`, zlib and the C++
runtime, which are bundled separately for the daemons. Build on the target OS
and architecture using the release workflows.

Spark uses the selected release's own manifest and lockfile with `npm ci`.
An npm audit fails the build on high or critical production dependency advisories;
dependency fixes should be published in a new Spark release. Mobile-only SDK
libraries are excluded; runtime JS/WASM and dependency licenses are retained.
Phoenixd's Apache license is included separately. CI supplies `GITHUB_TOKEN`
for release metadata requests; local builds can use the public API without it.

`make test-desktop` covers launcher controls, persistence, ownership, readiness,
settings precedence, restart and shutdown. `smoke_sidecars.py` tests native
versions, Spark authentication and shutdown without initializing a real wallet
or sending payments. CI runs it against the runtimes extracted from the shipped
EXE/Linux binary or from the final read-only DMG. `smoke.py` tests the packaged
LNbits server separately. Live network readiness and actual payments should
also be checked on each target platform before releasing to users.
