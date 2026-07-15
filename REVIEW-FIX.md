# Review Fixes — LNbits PR #3954 — 2026-07-14

This fix pass covers the Critical payment-correlation failure and the coupled
High/Medium REST, status, WebSocket, and test-isolation findings from the
exact-head review. The contributor's original commit is preserved, current
`dev` is integrated as a merge commit, and the adapter repair plus its
regression tests are one atomic follow-up commit.

## Environment

- Original PR head: `bbc30217103ea303d81bac48ebca1668dcf254d8`
- Live LNbits `dev`: `61ed636df066ced4c600a5eb55af147e6d13d130`
- Clean integration commit: `4e851bcf3e9c75f73e1c4e3b651f99a4d038732c`
- Gateway contract source: `clavestra-gateway`
  `a9ffff253cfb6848e08a180dbebb31bd6ca11574`
- Python 3.12.13, dependencies installed and commands run through
  `uv run --frozen`

## Result: adapter blockers fixed; complete wallet suite passing

```text
black --check clavestra source/tests       -> pass
ruff check clavestra source/tests          -> pass
mypy clavestra source/tests                -> success, no issues
pytest tests/wallets/test_clavestra.py -q  -> 40 passed
pytest tests/wallets -q                    -> 306 passed, 20 skipped
gateway fixture byte comparison            -> all 10 fixtures identical
git diff --check                           -> pass
```

| Commit | Finding | Files | Regression test | Verified |
|--------|---------|-------|-----------------|----------|
| this fix commit | **C-1** dispatched payment misclassified as failed | `lnbits/wallets/clavestra.py`, `tests/wallets/test_clavestra.py` | timeout, malformed, mismatch, in-flight, dispatched, hard-fail, settled cases | ✅ |
| this fix commit | **H-1** REST/status schema mismatch | same plus `tests/wallets/fixtures/clavestra-v15/` | byte-identical gateway v15 golden fixtures and outbound-body assertions | ✅ |
| this fix commit | **M-1** incompatible at-most-once WebSocket | same | plain-hash frame and polling-recovery tests | ✅ |
| this fix commit | **M-2** session-wide HTTP fixture collision | `tests/wallets/test_clavestra.py` | full wallet suite | ✅ |

## [C-1] Preserve funds after an ambiguous or dispatched payment

**Change.** `pay_invoice` decodes the submitted BOLT11 before POST and uses its
signed payment hash as the durable `checking_id`. A successful gateway response
must return the same identifier, and terminal proof must satisfy
`SHA256(preimage) == payment_hash`; a merely well-formed 32-byte value is not
accepted. Timeouts, transport errors, malformed bodies, hash/preimage
mismatches, `ok:null`, and `ok:true` without valid settlement proof return
pending under that known hash. Only the gateway's explicit `ok:false` response
or an HTTP rejection known to occur before dispatch returns failed.

**Behavior preserved.** Gateway business failures remain visible to LNbits.
Ambiguous outcomes deliberately reserve the LNbits balance until
`GET /v1/ln/payment/{hash}` reports a terminal result. An invalid preimage is
not propagated upward while the payment remains pending.

**Regression tests** in `tests/wallets/test_clavestra.py` cover dispatched,
settled, in-flight, hard-fail, response-loss timeout, malformed response,
correlation mismatch, cryptographically mismatched preimage, pre-dispatch
rejection, and ambiguous 5xx behavior.

## [H-1] Match gateway v15 REST and RFC 9457 contracts

**Change.** Invoice amounts are sent as sats in `amount`; all required nullable
response keys are validated; invoice `checking_id` must match the returned
BOLT11; HTTP 200 business failures are respected; balance `error_message` is
propagated; and non-2xx errors use RFC 9457 Problem Details. Description-hash
options are rejected because gateway v15 accepts but does not pass them to the
Lightning node.

**Regression tests.** Ten response fixtures are copied byte-for-byte from the
pinned gateway commit. Tests assert exact key sets, sats request units, bearer
scope, body-level errors, node-unreachable status, RFC 9457 parsing, unsupported
description options, and invoice correlation.

## [M-1] Treat WebSocket delivery as a hint and reconcile by polling

**Change.** The client no longer sends a JSON subscription or expects replay
frames. It accepts only lowercase 64-hex text frames with header bearer auth.
Created invoices are tracked and polled every five seconds, so an at-most-once
frame lost during disconnect does not strand settlement processing.

**Regression tests.** A no-`send` fake socket proves the plain-frame contract;
separate tests prove both low-latency WS delivery and recovery when the event is
missed.

## [M-2] Keep the complete wallet suite isolated

**Change.** Clavestra REST tests use `httpx.MockTransport` and no longer replace
pytest-httpserver's session-scoped listen address. This removes the 8555/8556
collection-order collision.

**Regression test.** The complete `tests/wallets` suite passes with the new
tests collected.

## Residual gateway-side hardening

- Gateway commit `a9ffff2` parses but does not enforce `fee_limit_msat` at the
  Lightning-node boundary. The adapter cannot retroactively enforce a routing
  fee ceiling after dispatch. Resolve this in the gateway before enabling this
  backend for real funds.
- The same gateway commit parses invoice expiry but does not pass it to the
  Lightning node. The default LNbits and gateway value is 3600 seconds, but a
  custom LNbits expiry is not currently guaranteed end-to-end.
- Verification used the gateway's authoritative golden fixtures and executable
  failure-mode mocks; no live federation payment was dispatched in this pass.
