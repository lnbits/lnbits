# Core onchain wallets

## Integration plan

1. Introduce an `onchain` wallet type with accounts owned by a core wallet ID.
   Keep blockchain balances and transactions outside the Lightning payment ledger.
2. Port the descriptor, hardware PSBT, server signing and seed recovery flows into
   `lnbits/onchain`. Preserve the Watchonly extension and its database.
3. Persist complete address snapshots. Background scans replace a snapshot only
   after successful retrieval, retain history on errors, and discover both receive
   and change branches. The browser cannot submit authoritative balances.
4. Render the onchain account cards above core wallet configuration, fiat display,
   charts and API tools. Preserve activity/address/coin tabs, relative timestamps,
   recipient addresses, nonblocking scans and stable payment drafts.
5. Verify core wallet isolation, seed recovery, signing validation, migration,
   background hydration and UI behavior, alongside existing wallet regressions.

## Boundaries

- A core wallet uses one Bitcoin network. Test coins are never Lightning funds.
- Invoice keys can read history and derive receive addresses; administrator keys
  are required for configuration, signing and recovery.
- Blockchain balances cannot be credited/debited through the Lightning ledger.
- Server-held seeds use the existing superuser-managed encryption key and backup
  controls. Seed export remains available when server signing is disabled.
- Explorer requests originate from the server. The built-in explorer reuses the
  shared service behind its API; user-selected Mempool URLs can address public or
  local instances. Redirects and environment proxies are disabled.
- Watchonly data is not deleted or automatically adopted by core.

## Audit findings and implementation

- Core wallet balances were read directly from the Lightning `balances` view.
  Onchain wallets now read their own persisted address balances. Duplicate addresses
  from single-path descriptors are counted once, including in the UI's coin list.
- Core invoice permissions and payment insertion are separate boundaries. Onchain
  wallets reject both invoice creation and Lightning ledger entries, including
  virtual admin credits/debits. Server Lightning totals include only Lightning.
- Watchonly authorization was user-scoped. Core routes require an onchain wallet's
  read/admin key and bind each Bitcoin account to that core wallet ID.
- Watchonly's browser submitted balances. Core derives them from complete provider
  snapshots; clients can change address notes but cannot submit amounts.
- Scans use database leases and bounded worker concurrency. Address reservation is
  atomic, failed scans retain snapshots, and expensive signing/finalization runs
  outside the async request loop.
- Seed and public account insertion is atomic. AES-GCM binds ciphertext to its core
  wallet, account, network and descriptor. Existing superuser key lifecycle and
  seed-backup verification are reused. Permanent cleanup preserves onchain accounts.
- The wallet page lazily loads namespaced ES modules. Onchain tools precede the
  existing wallet configuration, mobile browser access, fiat tracking and charts.
  Lightning-only sharing and invoice tools remain unavailable for this wallet type.
- Wally is a standard runtime dependency for Bitcoin descriptors, PSBTs and signing.
  The existing version constraint is retained; the `liquid` extra continues to add
  Boltz support.

## Verification record

- 160 ported Bitcoin descriptor, PSBT and server signing unit cases passed; the
  six existing core encryption-key tests also passed.
- Full unit run: 817 passed. A copied-workspace fixture omitted `package.json`;
  that one test passed on rerun. The remaining webhook test requires an external
  HTTP response and failed because sandbox DNS is unavailable (818/819 verified).
- 52 targeted core API tests passed: onchain account ownership, key/seed recovery,
  concurrent receive addresses, scanning, single-path descriptor accounting,
  immutable networks, stale input rejection, cleanup protection, fiat wallet and
  Lightning wallet regressions.
- Hardware wire-protocol, payment-finalization and seed-backup JavaScript suites
  passed via `make test-onchain-ui`.
- `make test-onchain-browser` passed with core wallet tools/charts, backup verification,
  receive links, send review, wallet creation during scanning, relative timestamps,
  recipient addresses, fiat display and desktop/mobile light/dark layouts.
- Mypy, Pyright (using the project interpreter), Ruff, Black, Prettier,
  `git diff --check`, and `make checkbundle` passed.
- Two additional live fiat exchange-rate API tests could not pass without external
  network access. Physical hardware, live Bitcoin broadcasts and PostgreSQL were
  not exercised in this environment.
