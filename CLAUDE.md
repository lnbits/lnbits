# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Quick Start

### Installing and running LNbits (Poetry - recommended for development)

```bash
# Install dependencies
poetry install --only main

# Run the development server
poetry run lnbits --reload

# Run with specific port/host
poetry run lnbits --port 9000 --host 0.0.0.0
```

### Essential Commands

```bash
# Format code (run all formatters)
make format

# Check code quality (run all checks)
make check

# Run all tests
make test

# Run specific test suites
make test-unit        # Unit tests only
make test-api         # API tests only
make test-wallets     # Wallet tests only
make test-regtest     # Regtest tests only

# Run a single test
poetry run pytest tests/unit/test_helpers.py::test_encode_strict_zbase32 -v

# Build frontend bundle
npm install
npm run bundle

# Database migration (SQLite to PostgreSQL)
poetry run python tools/conv.py

# Access LNbits CLI
poetry run lnbits-cli --help
```

## Architecture Overview

LNbits is a Lightning Network wallet and accounts system built with FastAPI (Python) and Vue.js/Quasar (frontend).

### Core Components

1. **Backend Structure** (`lnbits/`)
   - `app.py`: FastAPI application setup and initialization
   - `server.py`: Main entry point, Uvicorn server configuration
   - `settings.py`: Pydantic settings management (reads from .env)
   - `decorators.py`: Authentication and permission decorators
   - `exceptions.py`: Custom exception handlers

2. **Core Module** (`lnbits/core/`)
   - `models/`: Pydantic models for payments, wallets, users, extensions
   - `views/`: API endpoints organized by domain (payment_api.py, wallet_api.py, etc.)
   - `services/`: Business logic layer (payments.py, users.py, websockets.py)
   - `crud/`: Database operations layer
   - `migrations.py`: Database schema migrations

3. **Wallet Backends** (`lnbits/wallets/`)
   - Base class: `base.py` defines the interface all wallets must implement
   - Each wallet implements: `create_invoice()`, `pay_invoice()`, `get_invoice_status()`, `get_payment_status()`
   - Common wallets: `fake.py` (for testing), `lndrest.py`, `clnrest.py`, `lnbits.py`

4. **Extensions System** (`lnbits/extensions/`)
   - Extensions are mini-apps that extend LNbits functionality
   - Each extension has its own models, views, static files, and migrations
   - Extensions are installed/managed via the admin UI or lnbits-cli

5. **Frontend** (`lnbits/static/`)
   - Vue 3 + Quasar framework
   - Components in `js/components/`
   - Bundle built from `package.json` dependencies

### Key Patterns

1. **Authentication**: Uses API keys stored in wallets. Decorators like `@require_invoice_key` and `@require_admin_key` handle auth.

2. **Database**: Supports SQLite (default) and PostgreSQL. Uses raw SQL with query builders, not an ORM.

3. **Async Everywhere**: All database operations and HTTP calls are async. Use `await` for all I/O operations.

4. **Payment Flow**:
   - Invoice creation: `create_invoice()` → stores in DB → returns payment_request
   - Payment tracking: Background task polls wallet backend → updates DB → sends websocket notifications
   - Payment verification: Check payment_hash in DB for status

5. **WebSocket Updates**: Real-time updates via `/api/v1/ws/{id}` endpoint for payment notifications.

### Testing Approach

- Use `FakeWallet` backend for tests (set in environment)
- Tests organized by type: unit, api, wallets, regtest
- Fixtures in `conftest.py` provide test wallets, users, payments
- Always clean up test data in teardown

### Important Files to Understand

- `lnbits/core/services/payments.py`: Core payment logic
- `lnbits/core/views/payment_api.py`: Payment API endpoints
- `lnbits/wallets/base.py`: Wallet interface definition
- `lnbits/core/models/payments.py`: Payment data models
- `lnbits/settings.py`: All configuration options
