---
layout: default
parent: For developers
title: Agent Guide - Python Extensions
nav_order: 4
---

# Agent Guide - Python Extensions

This guide is for AI agents or developers using AI to build **traditional (Python) LNbits extensions**. It defines what to change, what not to change, and the expected structure.

## Hard Rules (Non-Negotiable)

- Do **not** change core LNbits files.
- Only edit files inside your extension folder.
- Do **not** add new Python dependencies unless explicitly approved.

## Extension Folder Layout (Python)

Your extension lives under:

```
lnbits/extensions/<ext_id>/
```

Typical files to edit:

- `views.py` (HTML routes)
- `views_api.py` (API routes)
- `crud.py` / `models.py` (storage logic + models)
- `migrations.py` (DB schema)
- `templates/<ext_id>/` (HTML)
- `static/` (JS/CSS/images)
- `config.json`, `manifest.json`, `README.md`

## What You Can Do

Python extensions can:

- Define their own database schema via `migrations.py`
- Run long-running background tasks via `*_start()` and `*_stop()` hooks
- Access LNbits internal services directly in Python
- Expose custom API routes under `/<ext_id>/api/v1/...`

## What You Must Not Do

- Do not modify core services or routes.
- Do not patch LNbits internals for your extension.
- Avoid direct DB access outside your own schema.

## Background Tasks

Implement background tasks by exposing:

```
def <ext_id>_start():
def <ext_id>_stop():
```

Use `register_invoice_listener` or `wait_for_paid_invoices` if you need to react to payments.

## Testing Checklist

- Extension loads without errors.
- Migrations apply cleanly.
- Routes are registered under `/<ext_id>/...`.
- Background tasks start/stop cleanly.
