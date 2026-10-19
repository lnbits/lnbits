---
layout: default
parent: For developers
title: WASM extensions from the CLI
nav_order: 11
---

# Developing WASM extensions from the CLI

This guide is for developers and coding agents working from a terminal or local
checkout. Read the [shared WASM rules](wasm-extensions.md) before applying this
workflow. Follow the repository's `AGENTS.md` and the user's authorized scope.

The [Studio agent](wasm-extensions-studio.md) uses its own draft-only workflow.
This CLI guide is not part of the Studio agent's mandatory instructions.

## Work directly in the extension directory

**Make extension changes directly in `data/wasm_extensions/<id>`**, or the
corresponding directory under the configured `LNBITS_WASM_EXTENSIONS_PATH`.
For Pricebot in this checkout, work in `data/wasm_extensions/pricebot`.
If that directory is a symlink, edit its existing target and preserve the link.

Keep the source, configuration, UI/assets, schema, migrations, tests, and rebuilt
WASM component in that extension directory. Run the extension's checks there.
Do not use a temporary copy or separate checkout as the primary working directory
unless the user explicitly requests it. Temporary test databases and fixtures
are fine, but completed extension changes must be present in the actual directory.

If filesystem permissions block an edit, request access to the actual target;
do not silently redirect the work elsewhere. If changes were already staged in
a temporary copy, reconcile them into the extension directory, preserve any
concurrent user edits, and verify the destination before reporting completion.
State separately whether the running instance has loaded the changes and whether
installation or permission approval is still required.

This working-directory rule does not authorize core edits. Core changes still
require the explicit approval described below and belong in their core files.

## Core changes require explicit user approval

**Never change LNbits core while creating, fixing, or updating a WASM extension
without first asking the user and receiving explicit approval for those core
changes.** Approval to work on an extension, including a general "go ahead", does
not authorize core changes. A missing host capability or a failing extension test
does not create an exception.

This applies to host APIs, the WASM runtime, scheduling and activation, permissions,
authentication, storage and migrations, core frontend code, core tests, and core
dependencies or build configuration. Do not change core indirectly through build
scripts, generated files, or patches in another checkout.

Read-only inspection of core is allowed. If the existing APIs cannot meet an
extension requirement, explain the limitation, any extension-only alternatives,
and the specific core changes and files proposed. Ask whether the user authorizes
that scope, then wait for their answer before editing core. Continue only the
extension work that does not depend on that approval.

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

Use the shared [release format and installation rules](wasm-extensions.md#build-release-and-verification)
when packaging an extension. The [Python component notes](wasm-extensions.md#python-components)
cover `componentize-py`, runtime requirements, and compiler flag limitations.

Verification references: [host tests](../tests/unit/test_wasm_extension_host_api.py),
[component tests](../tests/unit/test_wasm_extension_component.py),
[frontend contract tests](../tests/unit/test_wasm_extension_frontend.py).
