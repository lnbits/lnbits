---
layout: default
parent: For developers
title: WASM extensions
nav_order: 9
---

# Developing WASM extensions

**Read this guide before creating a WASM extension or choosing its architecture.**
Check the host APIs, execution context, browser restrictions, and release format
before copying an existing extension. The [extension setup guide](devs/extensions.md)
describes the separate Python workflow.

This guide combines source and documentation review of all **16 extensions and
21 releases** in the [WASM registry snapshot](https://github.com/lnbits/lnbits-extensions-wasm/blob/2ee1c7b4adedeb49bb23fc2ac66af7564adc9527/extensions.json).
Reviewed on **2026-10-08**, against LNbits commit
`e6301243e82790ecd50550eb9ee6f1d20a1db799`. Core behavior below comes from this
checkout; extension examples are pinned to their registry-listed releases.
This was a static review of manifests, WIT, application source, frontend code,
build scripts, migrations, tests, and available documentation. It does not certify
the security or runtime compatibility of the released binaries. See the
[review inventory](#review-inventory) for every repository and version.

## Start with these decisions

1. Choose a component toolchain: existing extensions demonstrate JavaScript, Rust,
   and C. Browser JavaScript and server-side WASM are separate programs.
2. Map each operation to an existing host method and the permission it requires.
   Identify whether it runs for a logged-in user, a public visitor, a payment
   event, or a scheduled job. These contexts have different capabilities.
3. Design ownership and public responses before defining tables. Shared jobs do
   not provide shared storage. Public owner-context routes need their own action
   authorization.
4. Choose explicit Vue render functions or templates compiled during the build.
   Runtime template compilation violates the iframe's CSP.
5. Budget storage calls, HTTP calls, response sizes, and execution time. Work that
   requires SQL transactions, an arbitrary server process, or a missing host API
   needs a different design or an explicit core change.

## Runtime and languages

LNbits runs a **WebAssembly component** in Wasmtime on the server. A bare WASM
module, Python extension directory, or browser WASM bundle is not interchangeable
with that component. Imports must match the host's WIT interfaces and records;
exports accept a JSON string and return a JSON string.

| Guest language | Observed build approach                                                  | Examples                                          |
| -------------- | ------------------------------------------------------------------------ | ------------------------------------------------- |
| JavaScript     | Bundle guest source, then use `@bytecodealliance/jco` to componentize it | Tips, games, SupportChat, InventoryStats, PopMenu |
| Rust           | `cargo-component`, WIT bindings, compiled component                      | BigPayment, Forms, GiftCards, ZapGoals            |
| C              | WASI SDK, `wit-bindgen` C bindings, then `jco embed` / `jco new`         | PaySplit                                          |

Other languages are possible if they produce a compatible component. The table
records build approaches present in the reviewed source, not a required language.
JavaScript guests do not receive Node.js or browser APIs such as `process`, DOM,
or unrestricted `fetch` merely because the source language is JavaScript.

Each invocation gets a fresh instance and store. Compiled components are cached;
guest globals are not persistent application state or reliable locks. The host
links WASI, but supplies no preopened application directories or inherited
environment through its empty WASI configuration. Use host storage, HTTP, wallet,
event, and scheduler APIs instead of assuming filesystem, socket, or background
process access. Rebuild the component after changing guest source.

Sources: [component lifecycle](../lnbits/core/wasm_ext/wasm/component.py),
[invocation](../lnbits/core/wasm_ext/wasm/invoke.py),
[host imports](../lnbits/core/wasm_ext/wasm/host.py).

## Files and interface contracts

A typical package contains:

```text
config.json                    Identity, module, exports, routes, permissions
wasm/<extension>.wasm          Built component referenced by config.json
wasm/lnbits-extension.wit      WIT contract, if configured
storage/schema.json           Table and field definitions, if storage is used
storage/migrations/0001_*.json Declarative schema operations
ui/*.html                     Configured iframe entrypoints
static/*.js, static/*.css      Browser application and other allowed assets
dev/ or wasm/src/             Source/build tooling; layout varies by toolchain
```

`config.json` needs a matching `id`, name, description, version,
`extension_type: "wasm"`, and `wasm.module`. Declare exports with visibility
`authenticated`, `public`, or `event`. HTTP routes cannot expose event exports.
The currently supported payment event configuration is `events.onInvoicePaid`.
Scheduler handlers also use event exports, with separate scheduler policies.

When first creating a WASM extension, set `config.json`'s `min_lnbits_version`
to the current LNbits version from `[project].version` in
[`pyproject.toml`](../pyproject.toml). Read that value at creation time and preserve
any prerelease suffix. Do not copy an older minimum version from a template or
another extension.

Host method IDs such as `utils.currencies.rate` are different from their WIT
import names. Imports live in interfaces such as `lnbits:extension/host`,
`lnbits:extension/utils-currencies`, and `lnbits:extension/scheduler`. Match names,
record fields, optional values, and numeric types exactly. JavaScript bindings
for WIT 64-bit integers use `BigInt`; normalize values before JSON serialization
and only convert to `Number` when precision is safe.

The authoritative method list and request/response schemas come from
[`list_extension_api_methods()` / `extension_api_contract()`](../lnbits/core/wasm_ext/api/registry.py)
and the [host models](../lnbits/core/wasm_ext/api/models.py). The
[TypeScript SDK generator](../tools/codegen/extension_sdk_typescript.py) derives
types and wrappers from those methods. It does not replace building a matching
WIT component. Repository-specific `lnbits-sdk.js` wrappers can differ; verify
their behavior rather than treating one copied SDK as the host specification.

Unknown config fields are currently ignored. In particular, copying a
`wasm.resource_limits` or `wasm.host_api` field does not configure the runtime.
Unknown requested permission IDs are rejected. See the
[config models](../lnbits/core/wasm_ext/wasm/config.py) and
[permission registry](../lnbits/core/wasm_ext/api/registry.py).

### Routes and JSON

API routes are mounted at `/api/v1/ext/<id><configured-path>`. UI routes are
mounted under `/ext`, and assets under `/ext-assets/<id>/`. UI entrypoints are
served through the core wrapper with a short-lived frame token; static HTML is
not an alternate entrypoint.

API payloads merge mapped path parameters, then query parameters, then JSON body
fields; later values override earlier ones. Query values are strings. POST, PUT,
and PATCH accept a JSON object. Configure `path_params` explicitly when names
matter, and validate the merged payload inside the guest. Do not assume that an
identifier came exclusively from the path.

Guests receive structured JSON, not a FastAPI request with arbitrary headers,
raw body, uploaded files, or control over response headers and status. A webhook
scheme that needs signatures over raw bytes or a special header may need a host
change. Returning `{ "ok": false, "error": "..." }` is an extension convention
and can still produce HTTP 200; handle business errors and transport errors.

Sources: [API routing](../lnbits/core/wasm_ext/routes/api.py),
[UI routing](../lnbits/core/wasm_ext/routes/ui.py),
[OpenAPI metadata](../lnbits/core/wasm_ext/routes/open_api.py).

## Browser UI: build for the actual sandbox

The iframe has `sandbox allow-scripts allow-pointer-lock`, without
`allow-same-origin`, `allow-forms`, or `allow-popups`. Its CSP permits scripts and
styles only from the extension asset prefix, forbids inline scripts and
`unsafe-eval`, and sets `connect-src 'none'` and `form-action 'none'`.

Consequences for implementation:

- **Vue templates must not compile in the browser.** Use `render()` / `Vue.h()`,
  as the JavaScript examples do, or compile templates into JavaScript at build
  time, as Forms, GiftCards, and ZapGoals do. Mounting Vue over template markup,
  using a `template` string, or calling `new Function` can cause `EvalError`.
- Load JavaScript and CSS as external extension assets. Inline handlers, inline
  style attributes, runtime-injected style blocks, and CDN dependencies are not
  supported by this policy. Test libraries that manipulate styles under the real
  CSP; a permissive development page is insufficient.
- Use explicit button click handlers and bridge API calls for save actions.
  Use `type="button"` where appropriate. Do not depend on native form submission,
  including a submit button inside a Quasar form.
- Direct `fetch`, XHR, browser WebSockets, workers, nested frames, and popup flows
  are unavailable. Use the parent bridge for its supported operations.
- The opaque iframe does not share the parent's DOM, cookies, or normal origin
  storage. Use the session-storage bridge for transient UI state and host storage
  for durable state. Do not assume browser wallet or Nostr providers are injected.

Allowed static file suffixes are `.css`, `.gif`, `.ico`, `.jpeg`, `.jpg`, `.js`,
`.ogg`, `.png`, `.webp`, `.woff`, and `.woff2`. **SVG files, JSON files, HTML files,
and WASM binaries are not served by the static asset route.** Use supported image
formats, canvas, or bundled JavaScript data as appropriate. This restriction on
SVG files is separate from generating DOM elements in JavaScript.

Core exposes a small asset proxy at `/ext-assets/<id>/_lnbits/`: Vue, Quasar,
QR-code JavaScript, bundled/Quasar CSS, and Material Icons CSS/font. Use its
allowlist rather than referencing arbitrary `/static/` paths.

### Parent bridge

The bridge uses a message channel to the LNbits wrapper. Account credentials
remain in the parent. Supported actions include:

| Action family                                                    | Purpose and boundary                                                                               |
| ---------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| `context`, `api`                                                 | Obtain UI context and call this extension's registered API routes                                  |
| `ui.notify`                                                      | Display a browser notification/toast; separate from delivery to a user's notification channels     |
| `navigation.replace`, `navigation.open_new_tab`                  | Parent-mediated navigation; opening an external tab requires confirmation                          |
| `storage.session.get`, `storage.session.set`                     | Transient session state                                                                            |
| `ui.scan_qr`                                                     | Parent camera UI, with `ui.camera.scan_qr` and user approval                                       |
| `permissions.request*`                                           | User permission dialogs, including background-payment and wallet-watch grants                      |
| `payment.subscribe`, `payment.unsubscribe`                       | Payment updates for hashes accepted by the parent, including hashes returned by approved API calls |
| `websocket.subscribe`, `websocket.unsubscribe`, `websocket.send` | Parent-managed extension channels                                                                  |

The bridge is not a generic browser-to-core RPC or an arbitrary URL proxy.
External widgets in some repositories execute on another site's page and have
their own CSP/CORS constraints. They do not relax the LNbits iframe policy;
`frame-ancestors 'self'` also prevents simply embedding the LNbits UI cross-site.

Sources: [CSP and frame tokens](../lnbits/core/wasm_ext/routes/security.py),
[asset allowlist](../lnbits/core/wasm_ext/routes/assets.py),
[parent bridge implementation](../lnbits/static/js/wasm-extension-component.js).

## Permissions and execution context

Permissions are declared in the extension configuration and reviewed by the
administrator during installation. Policies narrow access to tables, fields,
external origins, target extensions, websocket rates, or scheduled handlers.
Installation approval does not replace per-user wallet grants.

| Capability                                     | Permission / restriction                                                                     |
| ---------------------------------------------- | -------------------------------------------------------------------------------------------- |
| Private storage reads and writes               | `ext.storage.read`, `ext.storage.write`; requires an owner                                   |
| Public reads and public append                 | `ext.storage.read_public`, `ext.storage.append_public`; explicit table/field/source policies |
| List wallets / read balance                    | `wallet.list`, `wallet.balance.read`; accessible user wallets                                |
| Create invoices                                | `wallet.create_invoice`; user's wallet                                                       |
| Public invoice creation                        | `wallet.create_invoice_public`; wallet selected through an approved stored source            |
| Interactive outgoing payments                  | `wallet.pay_invoice`; user's wallet                                                          |
| Background outgoing payments                   | `wallet.pay_invoice_background` plus an enabled per-wallet user grant                        |
| Observe additional wallet payments             | `wallet.payments.watch` plus a per-wallet watch grant                                        |
| Currency rates, conversions, invoice utilities | `utils.basic`                                                                                |
| Outbound HTTPS                                 | `http.request`; approved origins and host network restrictions                               |
| Another extension's API                        | `extension.api.request`; approved target/read-write policy and interactive account token     |
| Core user notifications                        | `notifications.send_user_notification`; resolved user's saved channel settings               |
| Server-published channel messages              | `websocket.publish`; approved rate policy                                                    |
| Browser channel access                         | `websocket.subscribe`; parent-managed connection                                             |
| User / shared schedules                        | `scheduler.user` / `scheduler.extension`; approved handler, cron, timezone                   |

Host ID generation, current time, and logging do not require a separate
permission. LNURL helpers have their own wallet requirements; inspect the
method contract rather than assuming every utility belongs to `utils.basic`.

| Invocation                       | Identity available                                                           | Practical effect                                                                                          |
| -------------------------------- | ---------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| Authenticated HTTP request       | Logged-in account, owner, account access token                               | User storage and approved interactive wallet/API operations                                               |
| Ordinary public HTTP request     | No account or owner                                                          | Explicit public capabilities only                                                                         |
| Public route with `ownerContext` | Owner resolved from a source row; event context, no logged-in account token  | Owner-scoped operations become possible; the guest must authorize the public action                       |
| Invoice-paid event               | Event wallet; owner may be resolved from the approved source or wallet watch | Approved event work; no browser account token                                                             |
| User schedule                    | Job's user and storage owner; no browser account token                       | Owner storage, notifications, separately authorized background payments                                   |
| Extension-wide schedule          | No user or storage owner                                                     | Shared work using capabilities that do not need a user; no private user storage or selectable user wallet |

### Public owner context is not caller authentication

`ownerContext: { "table": "...", "idParam": "..." }` resolves the owner of a
stored source and invokes the guest in event context. A public visitor who knows
the source ID does not thereby become that owner. Validate bearer/action tokens,
game membership, permitted transitions, amounts, and related row IDs in the
extension before performing an operation.

Return an explicit public projection. A `public_fields` policy filters the public
storage API; it does not sanitize JSON assembled from private storage inside an
owner-context route. Secrets such as player tokens, unrevealed cards, claim
credentials, and private configuration must remain out of those responses.

Sources: [host methods and authorization](../lnbits/core/wasm_ext/api/host.py),
[method permissions](../lnbits/core/wasm_ext/api/registry.py),
[route owner resolution](../lnbits/core/wasm_ext/routes/api.py).

## Storage and concurrency

Tables are described in `storage/schema.json`. Numbered JSON migration files
support `create_table`, `add_field`, and `create_index`. Field types include
strings, integers, numbers, booleans, datetimes, and lists. Complex objects can
be serialized into declared string fields. There is no guest SQL interface,
join API, multi-call transaction, or compare-and-set operation.

Core adds the reserved `__lnbits_owner_id__` column and scopes private operations
to the invocation owner. Do not declare or supply that field. Each table's `id`
is nevertheless a **table-wide primary key**, not a key unique only within one
user's partition. Reusing `id: "settings"` for every user can collide and fail to
save the second user's settings. Generate distinct IDs and locate configuration
through an owner-scoped query.

Private storage supports get, upsert, delete, and pagination. Pages are limited
to 1,000 rows, with equality filters, search, and one sort key. Pagination is not
a transactionally consistent snapshot. Large scans must fit the invocation's
storage-call and response budgets.

Public reads require explicit `public_fields`. Public pagination additionally
requires a configured `source_id_field` and a `sourceId` in the request. Public
append policies restrict the destination table, source table/link, allowed
fields, and rows per source; the host derives ownership and generates the row
ID. Public append is not permission for arbitrary updates or deletions.
Policy keys differ: public-read policies use `table_name`, while public append
and public-invoice policies use `table`. Copy the schema for the actual method.

**There is no shared-storage host API in this checkout.** An extension-wide
schedule does not get access to all users' rows. Do not invent `storage.shared`
or `ext.storage.read_shared` / `ext.storage.write_shared` permissions. A shared
collector and user evaluators need an explicitly supported shared-data design.

Multiple invocations can run concurrently. Reading a version or processing flag
and then writing a row is not an atomic lock. Separate writes can partially
complete, and an HTTP timeout does not undo a payment or a stored row. Use
durable operation IDs, immutable receipts where suitable, bounded retries, and
reconciliation. If correctness requires an atomic primitive the host lacks,
resolve that requirement before shipping; guest globals cannot supply it.

Sources: [storage implementation and migrations](../lnbits/core/wasm_ext/storage/crud.py),
[storage policies](../lnbits/core/wasm_ext/api/host.py).

## Payments, events, and notifications

Public invoice creation uses a configured source row and wallet-field policy;
the caller does not choose an arbitrary wallet. Guest metadata is nested under
`extra_<extension-id>`. Check the actual event fields and units: settled payment
amounts are in millisatoshis, whereas invoice APIs also accept currency-specific
amounts. Do not assume all numeric amounts represent sats.

For settlement-driven state changes, verify status/pending state, payment hash,
amount, wallet, source, and the extension's stored invoice binding. Store enough
information before invoice creation to cope with settlement arriving before
that call returns. Treat browser payment/channel messages as UI updates, not
proof that funds were received.

The event dispatcher does not provide a durable application retry queue. Handle
duplicate attempts and recovery explicitly. A processed-hash row helps with
replays, but a separate check and write does not make concurrent side effects
exactly-once. Check `success` / pending status on payment responses rather than
equating `ok` with confirmed settlement.

Background payments, including payments from scheduled callbacks and public
owner-context actions, need the extension permission plus the user's wallet
grant. Grants restrict amount and destination policy; a per-payment cap is not
a daily spending budget. Wallet-watch permission only enables additional incoming
events and does not authorize spending. A shared schedule has no wallet owner.

`notifications.send_user_notification` queues a message through core using the
resolved user's saved email, Nostr, or Telegram preferences. It is not an
arbitrary-recipient messaging API. An owner hash alone is not always enough to
resolve a notification recipient; ordinary public owner-context requests lack
the event wallet and logged-in user. A queued response is not a delivery receipt.

Sources: [wallet and notification methods](../lnbits/core/wasm_ext/api/host.py),
[payment events](../lnbits/core/wasm_ext/wasm/events.py).

## Scheduled work

Use the [core scheduler guide](devs/scheduler.md) for the exact API and supported
cron syntax. The relevant WASM rules are:

- Declare handler, cron expression, and timezone policies at installation for
  administrator approval. Installing the extension does not create the jobs.
- `scheduler.user` manages the authenticated user's jobs.
  `scheduler.extension` manages shared jobs and requires an administrator.
  Management happens through interactive authenticated requests, not callbacks.
- Multiple jobs are supported, with one durable job per handler and owner/scope;
  use distinct handlers for distinct activities. Saving the same combination
  updates that job. Core assigns ownership and namespace. Users cannot replace
  the approved cron with a different expression. A callback may inspect internal conditions and
  return without doing its application work.
- Expressions have five fields and minute-or-longer granularity. Lists, ranges,
  steps, month/weekday names, and whole-field `?` in a day field are supported.
  This is not full Quartz: no seconds, years, `L`, `W`, `#`, `H`, `R`, or aliases.
  Weekday numbering and day-field OR semantics follow standard cron.
- Missed ticks are coalesced into one execution. A job does not overlap itself;
  the next occurrence is calculated after completion. Failures wait for the
  normal next occurrence. Different jobs can run concurrently.
- Leases enable recovery, not exactly-once external effects. Disabled extensions,
  disabled owners, and revoked permissions prevent further authorized execution;
  cancellation cannot reverse an already completed side effect.

For a price alert extension, core already exposes `utils.currencies.rate` with
`utils.basic`, including the BTC price for the requested fiat currency. It uses
core's rate provider/cache; it is not a guarantee of a new market quote for each
call. A user job can fetch that rate, maintain owner-scoped history, evaluate an
alert threshold, and request a notification. A shared price collector would also
need the shared-data capability discussed above.

Sources: [WASM scheduler API](../lnbits/core/wasm_ext/api/scheduler.py),
[scheduled invocation](../lnbits/core/wasm_ext/wasm/scheduler.py),
[currency helpers](../lnbits/core/wasm_ext/api/utils.py).

## Networking and live updates

`http.request` is server-side, requires an authenticated/event/schedule context,
and accepts only approved HTTPS origins. Origin matching includes the host and
port. URL credentials, localhost, and non-public resolved IP addresses are
rejected; redirects are not followed and proxy environment variables are not
inherited. The body is text, limited to 65,536 UTF-8 bytes. Cookie and transport
headers are filtered. There is no arbitrary guest socket or browser fetch access.

`extension.api.request` can call approved target-extension APIs using the logged-in
account's token. The target must be installed, active, and enabled for that user.
Its URL construction targets the extension's `/api/` routes; it is not a generic
core API proxy or the WASM route dispatcher. This capability is unavailable to
scheduled callbacks and payment events because they lack the interactive token.
InventoryStats demonstrates the interactive use case.

Websockets **are supported through core**. Guests can publish with the relevant
permission/rate policy, and the UI can subscribe/send through the parent bridge.
Channels are extension-scoped; item IDs use a restricted character set and
length. Browser relay messages have an 8 KiB limit and a 60 messages/second
per-connection limit. Server publication has a separate approved rate policy.

Channel messages are untrusted input. Browser relay does not invoke guest
validation automatically. Do not send secrets on public channels or authorize
payments from peer messages. The current hub is in-memory and process-local,
not durable storage or a cross-worker message bus. Use authoritative API reads
and polling/reconnection recovery where needed.

Sources: [HTTP client](../lnbits/core/wasm_ext/client/http.py),
[extension API client](../lnbits/core/wasm_ext/client/extensions.py),
[websocket channels and limits](../lnbits/core/wasm_ext/api/websockets.py),
[parent bridge](../lnbits/static/js/wasm-extension-component.js).

## Resource limits

These are current **default settings**, not values an extension can promise or
override in `config.json`. Administrators can change defaults and installed
extension overrides. Design bounded work even when a deployment relaxes limits.

| Limit                               | Default                                                 |
| ----------------------------------- | ------------------------------------------------------- |
| Guest memory                        | 64 MiB                                                  |
| Execution budget                    | 5,000 ms and 100,000,000 fuel                           |
| Invocation request / response       | 1 MiB each                                              |
| WASM stack                          | 1 MiB                                                   |
| Component resources                 | 10,000 table elements, 8 instances, 10 tables, 1 memory |
| Concurrent invocations, per process | 16 globally; 4 per extension; 4 per user                |
| Host calls per invocation           | 1,000 total; 100 storage; 20 HTTP; 20 wallet            |
| Outbound HTTP                       | 5,000 ms timeout; 1 MiB response                        |

The HTTP helper's fallback constants differ from the runtime's effective
defaults; the host passes the runtime values. A guest execution deadline is not
a universal wall-clock guarantee for stopping native threads or already-started
host I/O. Timeouts and cancellation do not provide transaction rollback.

Sources: [default settings](../lnbits/settings.py),
[limit resolution and monitoring](../lnbits/core/services/extensions.py),
[component execution](../lnbits/core/wasm_ext/wasm/component.py).

## Build, release, and verification

Use the chosen extension's build instructions and pinned dependencies, then
verify against the intended core version. Existing repositories demonstrate
component smoke tests, domain tests, host mocks, frontend bridge tests, and
release-package checks. Mock success alone does not verify WIT imports, host
authorization, browser CSP, or release installation.

For a new extension:

1. Check configuration, WIT, exports, routes, and permission policies against the
   current core contract. Test actual component instantiation and a host call.
2. Check owner isolation with two users, public projections, forged identifiers,
   denied permissions, and unavailable invocation contexts.
3. For payments or stateful events, check duplicates, pending/failed results,
   concurrent attempts, partial completion, and recovery. For schedules, check
   approved expressions, user/shared scope, deactivation, and missed runs.
4. Exercise the UI through the actual LNbits wrapper, including save buttons,
   asset loading, navigation, bridge errors, and CSP console messages.
5. Build and inspect the installable ZIP. Include one top-level extension
   directory containing config, the compiled module, required WIT, UI/assets,
   schema, and migrations. Exclude files the WASM installer rejects.
6. Check installation, approval, migration, activation, and update with the
   target LNbits version. Copying a folder alone does not complete this flow.

WASM extensions live under `LNBITS_WASM_EXTENSIONS_PATH`, defaulting to
`<LNBITS_DATA_FOLDER>/wasm_extensions`. They must remain outside Python-importable
extension and upgrade directories. Old examples using
`lnbits/extensions/<id>` should not be followed for this checkout.

The installer rejects `.py`, `.pyc`, `.pyo`, `.so`, and `.pyd` files anywhere in a
WASM package, including development/test helpers. A repository may contain such
tools, but its automatic GitHub source ZIP can consequently be unsuitable.
For example, the reviewed PaySplit v0.2.2 source tree includes
[`dev/test_notifications.py`](https://github.com/lnbits/paysplit/blob/ae9f3e9c9c33d0f4ab9f2fd595ce22a873498af4/dev/test_notifications.py);
packaging that file would fail this checkout's installer. Inspect the selected
release artifact rather than assuming the source archive is installable.

Registry manifests can describe repository discovery or explicit release
entries. Keep extension identity, release version, package contents, and minimum
core version consistent. A minimum-version string does not prove that an older
WIT contract or copied SDK matches a locally modified host.

Sources: [installer and archive validation](../lnbits/core/models/extensions.py),
[WASM loader](../lnbits/core/wasm_ext/wasm/loader.py),
[host tests](../tests/unit/test_wasm_extension_host_api.py),
[component tests](../tests/unit/test_wasm_extension_component.py),
[frontend contract tests](../tests/unit/test_wasm_extension_frontend.py).

## Differences from older extension documentation

| Statement or copied pattern                                         | Guidance for this checkout                                                          |
| ------------------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| Websockets are unavailable, or a game is only a polling placeholder | Inspect its actual code; core supports mediated channels and several games use them |
| Mount Vue over HTML templates                                       | Use render functions or compile templates during the build                          |
| A normal submit button is sufficient                                | Validate and save through an explicit handler in the sandbox                        |
| Copy SVGs or fetch JSON from `static/`                              | The static suffix allowlist excludes both                                           |
| Install under `lnbits/extensions`                                   | Use the separate WASM directory and normal approval/registration flow               |
| Put runtime limits in extension config                              | Limits come from core settings and installed-extension overrides                    |
| Every user can save the same settings row ID                        | IDs are table-wide; generate distinct IDs                                           |
| A version field or `redeeming` flag provides a lock                 | Storage has no compare-and-set or multi-call transaction                            |
| A shared scheduled job can store/read shared rows                   | No shared-storage host API is present                                               |
| HTTP always has a 10-second / 256 KiB limit                         | Runtime defaults passed by core are 5 seconds / 1 MiB                               |

Recheck the linked core code when it changes. Update this guide when a host
capability, permission contract, sandbox policy, scheduler rule, or package
format changes; treat example READMEs as supporting material.

## Review inventory

The table records every registry entry. Where a repository has multiple entries,
the older tagged source was compared with the newest listed release. Code links
point to immutable commits. Documentation was read where present, including
Tips' `agent.md`, Forms' `AGENTS.md` and design notes, and ZapGoals' policy and test
notes. Repositories without a README were reviewed through code and configuration.

| Extension         | All listed releases                                                                                                                                                                                      | Guest      | Reviewed code / documentation                                                                                                                                                                                                                                                                                                                                                                                                         | Useful example                                                                                      |
| ----------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| battleshipswasm   | [v0.1.2](https://github.com/lnbits/battleshipswasm/tree/ac62fa9b843f4f3e5af8fffc3c3a9801c36ab1b9), [v0.1.6](https://github.com/lnbits/battleshipswasm/tree/b3eec844791624b77388c1da1d623575c4a3d819)     | JavaScript | [code](https://github.com/lnbits/battleshipswasm/blob/b3eec844791624b77388c1da1d623575c4a3d819/dev/src/index.js) · [config](https://github.com/lnbits/battleshipswasm/blob/b3eec844791624b77388c1da1d623575c4a3d819/config.json) · [README.md](https://github.com/lnbits/battleshipswasm/blob/b3eec844791624b77388c1da1d623575c4a3d819/README.md)                                                                                     | Private fleets, paid player access, action IDs, and state-version checks.                           |
| bigpayment        | [v0.1.1](https://github.com/lnbits/bigpayment/tree/d68736e60a1a122af2bea6e3eb03dd39342f4420)                                                                                                             | Rust       | [code](https://github.com/lnbits/bigpayment/blob/d68736e60a1a122af2bea6e3eb03dd39342f4420/dev/src/lib.rs) · [config](https://github.com/lnbits/bigpayment/blob/d68736e60a1a122af2bea6e3eb03dd39342f4420/config.json)                                                                                                                                                                                                                  | Authenticated wallet aggregation and outgoing payment results; partial transfers need handling.     |
| chesswasm         | [v0.1.4](https://github.com/lnbits/chesswasm/tree/f2a6c94477bc0205ff610c46c7a4ee1cc160f34c), [v0.1.7](https://github.com/lnbits/chesswasm/tree/6f0bd55f559daa1a5950a45e39aa0ca8a69c7bb1)                 | JavaScript | [code](https://github.com/lnbits/chesswasm/blob/6f0bd55f559daa1a5950a45e39aa0ca8a69c7bb1/dev/src/index.js) · [config](https://github.com/lnbits/chesswasm/blob/6f0bd55f559daa1a5950a45e39aa0ca8a69c7bb1/config.json) · [README.md](https://github.com/lnbits/chesswasm/blob/6f0bd55f559daa1a5950a45e39aa0ca8a69c7bb1/README.md)                                                                                                       | Guest-side move validation, player authorization, and duplicate-action handling.                    |
| forms             | [v0.2.5](https://github.com/bitkarrot/forms/tree/7930173bb5d3475660af502bdb936ebbd9aa4a14)                                                                                                               | Rust       | [code](https://github.com/bitkarrot/forms/blob/7930173bb5d3475660af502bdb936ebbd9aa4a14/wasm/src/lib.rs) · [config](https://github.com/bitkarrot/forms/blob/7930173bb5d3475660af502bdb936ebbd9aa4a14/config.json) · [README.md](https://github.com/bitkarrot/forms/blob/7930173bb5d3475660af502bdb936ebbd9aa4a14/README.md) · [AGENTS.md](https://github.com/bitkarrot/forms/blob/7930173bb5d3475660af502bdb936ebbd9aa4a14/AGENTS.md) | Validated free/paid submissions, invoice bindings, notifications, and precompiled Vue templates.    |
| giftcardswasm     | [v0.3.0](https://github.com/bitkarrot/giftcardswasm/tree/1fa537459e10966f1542365c49b8dfd1705cb6b4)                                                                                                       | Rust       | [code](https://github.com/bitkarrot/giftcardswasm/blob/1fa537459e10966f1542365c49b8dfd1705cb6b4/wasm/src/lib.rs) · [config](https://github.com/bitkarrot/giftcardswasm/blob/1fa537459e10966f1542365c49b8dfd1705cb6b4/config.json) · [README.md](https://github.com/bitkarrot/giftcardswasm/blob/1fa537459e10966f1542365c49b8dfd1705cb6b4/README.md)                                                                                   | Hashed claim tokens, public owner context, LNURL redemption, and explicit storage-race limitations. |
| inventorystats    | [v0.1.1](https://github.com/lnbits/inventorystats/tree/19050c29b681e051ae38224168e57242768627c8)                                                                                                         | JavaScript | [code](https://github.com/lnbits/inventorystats/blob/19050c29b681e051ae38224168e57242768627c8/dev/src/index.js) · [config](https://github.com/lnbits/inventorystats/blob/19050c29b681e051ae38224168e57242768627c8/config.json) · [README.md](https://github.com/lnbits/inventorystats/blob/19050c29b681e051ae38224168e57242768627c8/README.md)                                                                                        | Interactive calls to the Inventory Python extension, pagination, and dashboard calculations.        |
| lnq1              | [v0.1.4](https://github.com/lnbits/lnq1/tree/f6a4a46204aa639a345b60f029ba5ce01d8150be), [v0.1.5](https://github.com/lnbits/lnq1/tree/22775d1fcbd8d00cda8a5bd6473b2ab14e4cba11)                           | JavaScript | [code](https://github.com/lnbits/lnq1/blob/22775d1fcbd8d00cda8a5bd6473b2ab14e4cba11/dev/src/index.js) · [config](https://github.com/lnbits/lnq1/blob/22775d1fcbd8d00cda8a5bd6473b2ab14e4cba11/config.json) · [README.md](https://github.com/lnbits/lnq1/blob/22775d1fcbd8d00cda8a5bd6473b2ab14e4cba11/README.md)                                                                                                                      | Browser game integration, player presence, paid gameplay, and parent-bridge channels.               |
| paysplit          | [v0.1.1](https://github.com/lnbits/paysplit/tree/092e8995a2c552612c764e2219f39340e927e648), [v0.2.2](https://github.com/lnbits/paysplit/tree/ae9f3e9c9c33d0f4ab9f2fd595ce22a873498af4)                   | C          | [code](https://github.com/lnbits/paysplit/blob/ae9f3e9c9c33d0f4ab9f2fd595ce22a873498af4/dev/src/paysplit.c) · [config](https://github.com/lnbits/paysplit/blob/ae9f3e9c9c33d0f4ab9f2fd595ce22a873498af4/config.json)                                                                                                                                                                                                                  | Watched wallet events, background LNURL splits, and user notifications.                             |
| pingpong          | [v0.1.1](https://github.com/lnbits/pingpong/tree/6f1f013c62214823e90f870ab6a221348b06d403)                                                                                                               | JavaScript | [code](https://github.com/lnbits/pingpong/blob/6f1f013c62214823e90f870ab6a221348b06d403/dev/src/index.js) · [config](https://github.com/lnbits/pingpong/blob/6f1f013c62214823e90f870ab6a221348b06d403/config.json)                                                                                                                                                                                                                    | Token-authorized public games, invoices, and winner payouts.                                        |
| poker             | [v0.1.2](https://github.com/lnbits/poker/tree/8bbaf5f035268339ff9ac12a8f4cffebf5ba0f7d)                                                                                                                  | JavaScript | [code](https://github.com/lnbits/poker/blob/8bbaf5f035268339ff9ac12a8f4cffebf5ba0f7d/dev/src/index.js) · [config](https://github.com/lnbits/poker/blob/8bbaf5f035268339ff9ac12a8f4cffebf5ba0f7d/config.json) · [README.md](https://github.com/lnbits/poker/blob/8bbaf5f035268339ff9ac12a8f4cffebf5ba0f7d/README.md)                                                                                                                   | Persistent rounds, private hand projections, and payout tracking.                                   |
| popmenu           | [v0.1.0](https://github.com/lnbits/popmenu/tree/42638e8df2efbe3ed4ae17d9030c97b455691c3b)                                                                                                                | JavaScript | [code](https://github.com/lnbits/popmenu/blob/42638e8df2efbe3ed4ae17d9030c97b455691c3b/dev/src/domain.js) · [config](https://github.com/lnbits/popmenu/blob/42638e8df2efbe3ed4ae17d9030c97b455691c3b/config.json) · [README.md](https://github.com/lnbits/popmenu/blob/42638e8df2efbe3ed4ae17d9030c97b455691c3b/README.md)                                                                                                            | Menus, order/payment state, decimal calculations, and separate domain/host/component tests.         |
| satoshisplacewasm | [v0.1.4](https://github.com/lnbits/satoshisplacewasm/tree/971ab69589372d8d47de9a6399c07a7096bdf4e3)                                                                                                      | JavaScript | [code](https://github.com/lnbits/satoshisplacewasm/blob/971ab69589372d8d47de9a6399c07a7096bdf4e3/dev/src/index.js) · [config](https://github.com/lnbits/satoshisplacewasm/blob/971ab69589372d8d47de9a6399c07a7096bdf4e3/config.json) · [README.md](https://github.com/lnbits/satoshisplacewasm/blob/971ab69589372d8d47de9a6399c07a7096bdf4e3/README.md)                                                                               | Paid pixel updates, compact invoice metadata, and public canvas data.                               |
| streetfighterwasm | [v0.1.5](https://github.com/lnbits/streetfighterwasm/tree/62eede95d2287d4aa16eb7580c8d69c7cf5f8e89), [v0.1.6](https://github.com/lnbits/streetfighterwasm/tree/2355a203013ba6b6d25ec7b97e5555a0a9f3c277) | JavaScript | [code](https://github.com/lnbits/streetfighterwasm/blob/2355a203013ba6b6d25ec7b97e5555a0a9f3c277/dev/src/index.js) · [config](https://github.com/lnbits/streetfighterwasm/blob/2355a203013ba6b6d25ec7b97e5555a0a9f3c277/config.json) · [README.md](https://github.com/lnbits/streetfighterwasm/blob/2355a203013ba6b6d25ec7b97e5555a0a9f3c277/README.md)                                                                               | Canvas game, player-token checks, live input/state messaging, and paid matches.                     |
| supportchat       | [v0.2.2](https://github.com/lnbits/supportchat/tree/b0abb1986117ada2a6c31e64627de6a67c7e2b32)                                                                                                            | JavaScript | [code](https://github.com/lnbits/supportchat/blob/b0abb1986117ada2a6c31e64627de6a67c7e2b32/dev/src/index.js) · [config](https://github.com/lnbits/supportchat/blob/b0abb1986117ada2a6c31e64627de6a67c7e2b32/config.json)                                                                                                                                                                                                              | Public append policies, source-scoped conversations, widgets, and live messages.                    |
| tips              | [v0.1.4](https://github.com/lnbits/tips/tree/c7195fbd203c1eb207dd974087b53b20c4596317)                                                                                                                   | JavaScript | [code](https://github.com/lnbits/tips/blob/c7195fbd203c1eb207dd974087b53b20c4596317/dev/src/index.js) · [config](https://github.com/lnbits/tips/blob/c7195fbd203c1eb207dd974087b53b20c4596317/config.json) · [README.md](https://github.com/lnbits/tips/blob/c7195fbd203c1eb207dd974087b53b20c4596317/README.md) · [agent.md](https://github.com/lnbits/tips/blob/c7195fbd203c1eb207dd974087b53b20c4596317/agent.md)                  | Public tip jars, source-bound invoices, declarative migrations, and detailed authoring notes.       |
| zapgoalswasm      | [v0.5.2](https://github.com/bitkarrot/zapgoalswasm/tree/052a7299b5693a7e60afb39043caff0e01d146ba)                                                                                                        | Rust       | [code](https://github.com/bitkarrot/zapgoalswasm/blob/052a7299b5693a7e60afb39043caff0e01d146ba/wasm/src/lib.rs) · [config](https://github.com/bitkarrot/zapgoalswasm/blob/052a7299b5693a7e60afb39043caff0e01d146ba/config.json) · [README.md](https://github.com/bitkarrot/zapgoalswasm/blob/052a7299b5693a7e60afb39043caff0e01d146ba/README.md)                                                                                      | Verified immutable payment receipts, recurring-goal projections, sweeps, and precompiled UI.        |

The older Chess, Battleships, StreetFighter, and LNQ1 entries illustrate the
fixed-settings-ID problem; their newer listed releases generate distinct IDs.
Chess and Battleships also add action IDs/state versions, and PaySplit adds
notification support. Those changes do not supply an atomic storage primitive.

These examples demonstrate possibilities, not guarantees of production safety.
For example, GiftCards explicitly discusses the lack of compare-and-set around
redemption, and multi-wallet or multi-recipient payments can partially complete.
None of the registry examples is the specification for the scheduler or a missing
host capability; use this checkout's core implementation and tests for those.
