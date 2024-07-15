---
layout: default
title: For developers
nav_order: 4
has_children: true
---

# For developers

Thanks for contributing :)

# Run

This starts the lnbits uvicorn server

```bash
poetry run lnbits
```

This starts the lnbits uvicorn with hot reloading.

```bash
make dev
# or
poetry run lnbits --reload
```

# Precommit hooks

This ensures that all commits adhere to the formatting and linting rules.

```bash
make install-pre-commit-hook
```

# Tests

This project has unit tests that help prevent regressions. Before you can run the tests, you must install a few dependencies:

```bash
poetry install
npm i
```

Then to run the tests:

```bash
make test
```

Run formatting:

```bash
make format
```

Run mypy checks:

```bash
poetry run mypy
```

Run everything:

```bash
make all
```
