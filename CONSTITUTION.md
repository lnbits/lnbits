# CONSTITUTION.md

This is the immutable constitution of the LNbits project.
Every feature spec, code change, refactor, extension, or decision by humans or AI agents **must comply** with this document.
Changes to this file require explicit approval from the project owner/maintainers.

## 1. Project Overview

**Project Name:** LNbits
**Core Purpose:** Free and open-source Lightning wallet and accounts system. A lightweight Python server that sits on top of any Lightning funding source, providing safe isolated wallets, a clean REST API, and a powerful extension system for adding features rapidly.
**Target Users:** Individuals, communities, merchants, developers, and enterprises building on Bitcoin/Lightning (self-hosted or as part of larger stacks).
**High-Level Success Criteria:**

- Reliable multi-wallet Lightning accounting with any backend (20+ supported funding sources)
- Secure, extensible via 60+ extensions without bloating core
- High code quality, test coverage, and backward compatibility for extensions
- Production-ready performance and security for real Bitcoin value

**Version:** 1.5.4

## 2. Technology Stack (Strict)

- **Language:** Python >=3.10, <3.13 (strictly enforced via `pyproject.toml`)
- **Framework:** FastAPI + Starlette (backend API)
- **Frontend:** Vue.js + Quasar framework, with bundled static assets
- **Database:** SQLite (aiosqlite) by default, PostgreSQL (asyncpg/psycopg2) supported via `LNBITS_DATABASE_URL`
- **Async Runtime:** uvloop preferred
- **Dependency Management:** uv + pyproject.toml (Hatchling build backend). Use `uv run` for all commands.
- **Wallet Backends:** Abstracted via `lnbits.wallets` – support for LND, Core Lightning, Phoenixd, Boltz, Breez SDK, Liquid, VoidWallet fallback, etc. New backends must follow existing abstraction.
- **Other Key Libs:** SQLAlchemy, Pydantic (v1), Loguru, Jinja2, LNURL, Bolt11, etc. (see `pyproject.toml` for pinned versions)
- **Build/Frontend Tools:** npm for bundling (Quasar/Vue), Prettier for JS/CSS (check Makefile targets)

**Forbidden:**

- Adding new top-level dependencies without updating `pyproject.toml` **and** team approval
- Using synchronous blocking calls in async paths (except where explicitly justified)
- Direct database queries outside of CRUD layers or core services
- Modifying generated files (e.g., gRPC files in wallets/boltz_grpc_files or lnd_grpc_files)

## 3. Architecture & Code Organization (Mandatory Rules)

- **Core Principle:** Modular monolith with heavy emphasis on **extensions**. All non-core features must live in extensions (installed via `lnbits/extensions`). Core stays lean.
- **Backend Structure:**
  - `lnbits/core/` for core models, CRUD, services, routers, tasks
  - `lnbits/wallets/` for funding source abstractions
  - `lnbits/extensions/` for installed/upgradeable extensions (do not commit large extensions to core repo)
  - `lnbits/static/` for bundled frontend assets (managed via npm bundle)
- **Key Rules:**
  - Use dependency injection and FastAPI routers properly
  - Extensions register routes/tasks via `register_ext_routes` / `register_ext_tasks`
  - Database migrations handled centrally (extension-specific migrations)
  - All new endpoints must be under proper versioning/prefixing where applicable
  - Frontend: Vue 2/Quasar components in `wallet.js` style (or updated) – keep reactive, use LNbits.utils helpers
  - No circular imports; respect existing middleware order (e.g., InstalledExtensionMiddleware before ExtensionsRedirectMiddleware)

**Exclusions** (do not lint/format these):

- `lnbits/extensions/`, `lnbits/upgrades/`, generated gRPC files, static/vendor bundles

## 4. Code Quality & Style

- **Formatting & Linting:**
  - Python: Black (line-length 88), Ruff (with selected rules: F, E, W, I, A, C, N, UP, RUF, B, S), MyPy (strict where possible), Pyright
  - JS/Frontend: Prettier
  - Run via Makefile: `make format` and `make check`
- **Type Checking:** MyPy + Pyright enforced on `lnbits/`, `tests/`, `tools/`
- **Testing Requirements:**
  - Unit, API, wallet, and regtest tests via pytest (see Makefile targets)
  - New core code or critical paths: high coverage expected (`--cov=lnbits`)
  - Extensions should include their own tests where possible
- **Error Handling & Logging:** Use Loguru with structured context. Never expose raw stack traces to end users. Graceful fallbacks (e.g., VoidWallet on funding source failure).
- **Pre-commit:** Strongly recommended (`make install-pre-commit-hook`)
- **Bundle Integrity:** Frontend bundles must pass `make checkbundle` before commits affecting static files.

## 5. AI / LLM Usage Standards (if any agents or future AI features are added)

- Any new AI-powered features (e.g., via extensions) must use structured outputs (Pydantic/JSON mode)
- Store prompts/templates versioned in the extension
- Prefer deterministic behavior for financial/security paths (low temperature)
- All AI outputs involving value/money must be validated server-side
- Safety: Never allow untrusted model output to influence payments, wallet balances, or admin actions without guardrails

## 6. Safety, Security & Ethics

- **Critical:** Handle real Bitcoin/Lightning value → security-first mindset
- Per-wallet isolation with separate admin/invoice/read keys
- Rate limiting (SlowAPI) and IP blocking middleware mandatory
- Sanitize all user inputs; validate LNURL, Bolt11, etc.
- PII: Minimal collection; respect privacy (no unnecessary logging of sensitive data)
- Funding source failures: Graceful degradation to VoidWallet + clear logging
- Extensions: Hash-verified installs for vetted extensions; careful with custom extension paths
- Audit logging via AuditMiddleware
- Forbidden: Hard-coded secrets, insecure subprocess calls without review, SQL injection risks (use SQLAlchemy properly)

## 7. Performance & Cost Budgets

- Keep core lightweight – extensions handle heavy features
- Async-first (uvloop, asyncpg/aiosqlite)
- Reasonable retry logic for funding source connections (see `check_funding_source`)
- Frontend: Optimized bundles (checkbundle enforced)
- No unnecessary blocking operations in request paths

## 8. Development Workflow (Spec-Driven where possible)

- **All significant changes** should follow Spec-Driven Development:
  - Create/update Feature Spec in `.specify/` folder (or equivalent)
  - Reference this Constitution in every spec and PR
- Use Makefile targets for format/check/test
- Tests run with `FakeWallet` by default for unit/API; regtest for full flows
- PRs must:
  - Pass `make check` and relevant tests
  - Include Constitution compliance notes (via AGENTS.md/CLAUDE.md)
  - Not break existing extensions or wallet backends
- Branching: Protect main; use feature branches
- Extensions: Develop separately; core repo focuses on framework stability

## 9. Decision Hierarchy (What Takes Precedence)

1. This Constitution
2. Approved Feature Spec / Milestone
3. Existing tests and backward compatibility (especially for extensions and wallet backends)
4. Project maintainers / owner decision
5. Everything else (including helpful AI suggestions)

If conflict: Stop, document the issue, and seek clarification from maintainers.

## 10. Amendment Process

- This Constitution can only be changed with explicit approval from project maintainers.
- All changes must be dated, versioned, and reflected in `AGENTS.md`.
- Minor clarifications can be proposed via PR with justification.

---

**Last Updated:** April 2026 (based on v1.5.4)
**Owner/Maintainers Approval:** LNbits Team
