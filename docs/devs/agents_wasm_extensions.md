---
layout: default
parent: For developers
title: Agent Guide - WASM Extensions
nav_order: 3
---

# Agent Guide - WASM Extensions

This guide is written for AI agents or developers using AI to build LNbits WASM extensions. It describes what to change, what not to change, and the available capabilities/limits.

## Hard Rules (Non-Negotiable)

- Do **not** change core LNbits files. Only edit files inside your extension folder.
- Do **not** add new Python dependencies.
- Do **not** rely on long-running WASM processes. WASM runs per-call with timeouts.

## Extension Folder Layout (WASM)

Your extension lives under:

```
lnbits/extensions/<ext_id>/
```

You should only edit files under this folder, typically:

- `config.json` (metadata, permissions, tags, public handlers)
- `wasm/` (your `module.wasm` or `module.wat`)
- `static/` (frontend assets)
- `templates/` (HTML pages)
- `manifest.json`, `README.md`, `description.md` (docs and metadata)

## Required Config Fields

In `config.json`:

- `id` / `name`
- `extension_type: "wasm"`
- `permissions` (required API permissions)
- `public_wasm_functions` (handlers callable from public routes)
- `public_kv_keys` (publicly readable KV keys)
- `payment_tags` (list of tags the user may grant for watcher access)

Example:

```json
{
  "id": "myext",
  "name": "MyExt",
  "extension_type": "wasm",
  "permissions": [
    {"id": "ext.db.read_write", "label": "DB access", "description": "..."},
    {
      "id": "api.POST:/api/v1/payments",
      "label": "Create invoices",
      "description": "..."
    },
    {
      "id": "ext.payments.watch",
      "label": "Watch payments",
      "description": "..."
    },
    {
      "id": "ext.tasks.schedule",
      "label": "Schedule tasks",
      "description": "..."
    },
    {"id": "ext.db.sql", "label": "SQL access", "description": "..."}
  ],
  "public_wasm_functions": [
    "public_create_invoice",
    "on_tag_payment",
    "on_schedule"
  ],
  "public_kv_keys": ["public_lists", "public_tasks"],
  "payment_tags": ["coinflip", "myext"]
}
```

## What the WASM Host Can Do

WASM runs in a short-lived subprocess. It can:

- Read/write extension KV (`/api/v1/kv/*`)
- Read/write secret KV (`/api/v1/secret/*`)
- Call internal LNbits endpoints (only if declared + granted)
- Publish websockets (`ws_publish`)
- Run backend tag watchers and scheduled handlers (server-side triggers)

## Permissions Model

Your extension can only call or access what is declared and granted:

- `api.METHOD:/path` for internal endpoints (core or other extensions)
- `ext.db.read_write` for KV access
- `ext.payments.watch` for payment watchers
- `ext.tasks.schedule` for scheduled jobs
- `ext.db.sql` for SQL interface

If the endpoint doesn’t exist, permissions won’t save.

## Tag Watchers (Backend)

You can register tag watchers:

```
POST /<ext_id>/api/v1/watch_tag
{
  "tag": "coinflip",
  "wallet_id": "<wallet-id>",
  "handler": "on_tag_payment",
  "store_key": "tag:coinflip:last_payment"
}
```

Constraints:

- Tag must be in `payment_tags` and granted by the user.
- Watchers are persisted and restored on restart.

## Scheduled Tasks (Backend)

You can schedule periodic handlers:

```
POST /<ext_id>/api/v1/schedule
{
  "interval_seconds": 30,
  "handler": "on_schedule",
  "store_key": "schedule:last_run"
}
```

Constraints:

- Requires `ext.tasks.schedule` permission.
- Minimum interval is 5 seconds.
- Stored in extension KV and restored on restart.

## SQL Interface (Limited)

You can run SQL within your extension schema:

- `/api/v1/sql/query` (SELECT only)
- `/api/v1/sql/exec` (limited DDL/DML)

Rules:

- Single statement only
- No `PRAGMA`, no `sqlite_master`
- No cross-schema access

## Public Pages (No Keys)

Public pages must not depend on `window.g` or wallet keys.
They can call:

- `/{ext_id}/api/v1/public/kv/{key}`
- `/{ext_id}/api/v1/public/call/{handler}`

## What Not To Do

- Do not write to core routes or override existing LNbits paths.
- Do not add background threads; use watchers or scheduler instead.
- Do not assume the WASM process persists.

## Testing Checklist

- Permissions show correctly in the extensions UI.
- Public handlers are in `public_wasm_functions`.
- Public KV keys are explicitly listed.
- Tag watchers only use allowed tags.
- Scheduled handlers run and update KV as expected.
