# AGENTS.md - AI Coding Agent Guide for LNbits

This file guides AI coding agents working on LNbits. Keep changes small, verified, and aligned with existing project patterns.

## Core Behavior

- Think before coding. State material assumptions. Ask when ambiguity affects correctness, security, payments, wallets, or data migrations.
- Prefer the simplest implementation that solves the request.
- Make surgical changes. Every changed line should trace back to the task.
- Do not refactor, reformat, rename, or clean adjacent code unless required.
- Remove only dead code or imports created by your own changes.
- Define success criteria for non-trivial work and verify them before reporting done.

## LNbits Architecture

- Keep core lean. Prefer/assess extensions for non-core features.
- Preserve compatibility with existing extensions and wallet backends.
- Follow existing patterns in `lnbits/core`, `lnbits/wallets`, `lnbits/extensions`, and frontend code.
- Use existing CRUD, services, settings, and migration patterns.
- Do not edit generated files, bundled vendor files, or unrelated extension code.

## Security-Sensitive Areas

Be extra cautious with payments, wallet balances, admin routes, keys, LNURL, Bolt11, funding sources, migrations, and authentication.

Do not expose raw stack traces or sensitive values. Do not add synchronous blocking work in hot async paths without justification.

## Commands and Verification

Read `Makefile` before running project commands.

Use Makefile targets instead of hand-written commands when available:

- `make check` for full checks.
- `make test-unit` for unit tests.
- `make test-api` for API tests.
- `make test-wallets` for wallet tests.
- `make checkbundle` when bundled frontend assets may be affected.
- `make format` only when formatting is intended.

Do not run `make test` by default. Use the targeted tests available in the Makefile that are related to the work done, unless the user explicitly asks for broader test coverage.

## Dependencies

Do not add dependencies without approval. If approved, update the correct project files and explain why the dependency is necessary.

## Maintenance

LNbits maintainers own this file. They should update it when the development workflow, architecture, or verification commands materially change.

Do not edit, commit, push, or include changes to this file in a PR as part of normal feature work unless the user explicitly asks for `AGENTS.md` changes.

## Reporting

When finished, report:

- Summary of what changed.
- Files touched.
- Makefile targets or checks run.
- Anything not verified and why.
