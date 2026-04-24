# AGENTS.md - Instructions for All AI Coding Agents

This file is the **master instruction manual** for any AI agent (Grok, Claude, Cursor, Aider, etc.) working on LNbits.

## 1. Core Rule (Never Break This)

**You MUST read and strictly follow `CONSTITUTION.md` before doing any planning, coding, refactoring, or suggesting changes.**

- Every single change, feature, extension, or fix **must comply** with the Constitution.
- If you detect a violation (in new code or existing code), you **must** flag it immediately and propose a fix or ask for clarification.
- Constitution > any other instruction (including this file, user prompts, or previous conversations).

## 2. Mandatory Development Workflow

For **any non-trivial task** (new feature, bug fix, refactor, extension change):

1. **Constitution Check** – Re-read relevant sections of `CONSTITUTION.md`
2. **Feature Spec Check** – If a spec exists in `.specify/`, follow it exactly. If none exists, ask the user for clarification or propose a minimal spec.
3. **Think Step-by-Step** – Follow the "Think Before Coding" and "Simplicity First" guidelines below.
4. **Surgical Changes** – Only touch what is necessary.
5. **Implement**
6. **Verify** – Run relevant tests (`make test-unit`, `make test-api`, etc.), `make check`, and confirm compliance.
7. **Report** – Always include a clear summary.

Use the following response format:

```markdown
## Constitution & Spec Compliance

- Relevant Constitution sections checked: [list or quote key rules]
- Feature Spec followed: [yes / no / proposed]

## Assumptions & Plan

- Assumptions: ...
- Plan:
  1. ...
  2. ...
- Tradeoffs considered: ...

## Changes Made

- Files changed: ...
- Summary of modifications:

## Verification

- [ ] Passes `make check`
- [ ] Relevant tests pass (`make test-xxx`)
- [ ] Complies with Constitution
- [ ] Surgical & minimal (no unrelated changes)
```

## 3. Behavioral Guidelines (Merged & Project-Specific)

**Think Before Coding**

- Don't assume. Don't hide confusion. Surface tradeoffs.
- State assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them — don't pick silently.
- If something is unclear (especially regarding wallets, extensions, or funding sources), stop and ask.

**Simplicity First**

- Minimum code that solves the problem. Nothing speculative.
- No features beyond what was asked.
- No abstractions for single-use code.
- Respect LNbits' lean core philosophy: new functionality should preferably go into an **extension** unless it truly belongs in core.

**Surgical Changes**

- Touch only what you must. Clean up only your own mess.
- Match existing style (Python: Black + Ruff rules; JS: Prettier).
- Do not "improve" or refactor adjacent code unless explicitly asked.
- When editing, remove only imports/variables/functions made unused **by your changes**.
- Never delete pre-existing dead code unless instructed.

**Goal-Driven Execution**

- Transform tasks into verifiable goals.
- For tests: Write or update tests first when fixing bugs or adding behavior.
- Always consider impact on existing extensions and multiple wallet backends (LND, CLN, Boltz, VoidWallet, etc.).

## 4. LNbits-Specific Rules

- **Extensions First**: Core should remain lean. Prefer implementing new features as extensions unless they are fundamental to wallets, security, or the API.
- **Testing**: Use `FakeWallet` for unit/API tests. Regtest tests for full Lightning flows. Never break existing test targets in the Makefile.
- **Dependencies**: Never add new dependencies without updating `pyproject.toml` and getting approval.
- **Frontend**: JS/Vue code (e.g. `wallet.js`) must follow existing patterns and pass `make checkbundle` when static files are affected.
- **Database / Migrations**: Do not make raw SQL changes. Use existing CRUD/services and migration tooling.
- **Security**: Be extremely cautious with anything touching payments, keys, LNURL, Bolt11, or admin routes.
- **Tools**: Use `uv run` for all commands. Prefer Makefile targets (`make format`, `make check`, `make test-xxx`).
- **Generated Files**: Never modify gRPC files or other generated code.

## 5. Forbidden Behaviors

- Ignoring Constitution rules to "be helpful"
- Large refactors without a spec or explicit request
- Adding features "for future use"
- Breaking backward compatibility for extensions or existing wallet backends
- Committing code that fails `make check` or relevant tests
- Exposing raw errors/stack traces to users
- Using synchronous code in hot async paths without justification

## 6. How to Handle This File + Constitution

When the user gives you a task, start your response with:

> Following LNbits CONSTITUTION.md and AGENTS.md...

Then proceed with the structured format above.

---

**These guidelines are working if:**

- Fewer unnecessary changes appear in diffs
- Clarifying questions come **before** implementation
- All changes respect the lean, extension-first, security-first nature of LNbits
- Tests and `make check` continue to pass

Last Updated: April 2026
