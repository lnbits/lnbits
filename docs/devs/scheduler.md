---
layout: default
parent: For developers
title: Scheduler
nav_order: 8
---

# Core scheduler

LNbits stores core, Python extension, and WASM extension jobs in one core table,
`scheduled_jobs`. The task manager starts the scheduler after database migration
and extension registration. No external cron daemon is required.

## Supported expressions

Expressions have exactly five fields, in this order:

```text
minute hour day-of-month month day-of-week
```

| Field        | Values                                   |
| ------------ | ---------------------------------------- |
| Minute       | 0–59                                     |
| Hour         | 0–23                                     |
| Day of month | 1–31                                     |
| Month        | 1–12 or JAN–DEC                          |
| Day of week  | 0–7 or SUN–SAT; both 0 and 7 mean Sunday |

Supported operators are `*`, comma-separated lists, inclusive ranges (`-`), and
steps (`/`). Month and weekday names are case-insensitive. A whole-field `?` in
day-of-month or day-of-week is accepted and normalized to `*`.

When both day-of-month and day-of-week are restricted, either field matching is
sufficient (standard cron OR semantics). Numeric weekdays follow standard cron,
not Quartz's 1–7 numbering. This is a small cron dialect, not full Quartz.

Seconds, years, `L`, `W`, `#`, `H`, `R`, and aliases such as `@daily` are rejected.
Expressions with no occurrence in the next eight years are rejected when saved.

| Expression        | Meaning                                                 |
| ----------------- | ------------------------------------------------------- |
| `* * * * *`       | Every minute                                            |
| `*/10 * * * *`    | Every ten minutes, at minutes 0, 10, 20, 30, 40, and 50 |
| `0 9 * * MON-FRI` | Weekdays at 09:00                                       |
| `0 0 1 * *`       | Midnight on the first of each month                     |
| `0 9 ? * MON`     | Mondays at 09:00                                        |

Times are interpreted in the job's IANA timezone, defaulting to `UTC`. The database
stores execution and lease times as UTC Unix seconds. Local daylight-saving
behavior follows `croniter`: nonexistent local times can move to the spring
transition, and repeated local times can run twice at distinct UTC instants. For
example, `30 2 * * *` in `Europe/Berlin` runs at 03:00 on March 29, 2026, and can run
at both occurrences of 02:30 on October 25, 2026. Use UTC for schedules that must
avoid daylight-saving shifts.

## Execution and recovery

- After downtime, an overdue job runs once using its saved payload. Missed ticks
  are coalesced into that one execution.
- A job does not overlap itself. Ticks during execution are skipped; completion
  calculates the next occurrence strictly after the finish time.
- Callback failures are logged without including payloads or exception details.
  The next attempt follows the normal schedule, with no immediate retry loop.
- The runner polls once per second and permits four concurrent jobs per process.
  Minute-level expressions describe intended start times, not a hard latency
  guarantee when workers are busy.
- Workers claim jobs atomically with a 60-second lease, renewed every 20 seconds.
  Completion is conditional on the claim token. An interrupted job becomes
  eligible once its lease expires, including after shutdown.
- Revoked permissions, disabled extensions, and disabled/deleted users prevent
  further executions. Running jobs recheck access on lease renewal. Extension
  deactivation also cancels its local scheduled callbacks.
- Pausing sets `enabled` to false. A running callback is cancelled on its next
  lease renewal. Deleting an actively leased job is rejected; pause it and wait
  before deleting. Uninstallation removes that extension's schedules.
- Application shutdown waits up to five seconds for scheduler cleanup, logs
  failures or unfinished jobs, and continues the remaining cleanup. This deadline
  requires a responsive event loop; it cannot forcibly terminate native threads.

Leases coordinate workers but do not make external effects exactly-once. Callbacks
that send messages or make payments must handle duplicate attempts after a crash
or lost lease. Python callbacks must be asynchronous and cooperate with
cancellation. WASM jobs use the existing runtime resource limits and invocation
monitoring (`trigger_type="schedule"`, schedule ID in `context`).

## Core and Python API

Register handlers whenever the application or extension starts. Store a stable
job ID in your configuration and reuse it for edits. Registration alone does not
change a persisted job's next execution time.

```python
import json

from lnbits.core.models.scheduler import ScheduleConfig, ScheduledJob
from lnbits.core.services.scheduler import scheduler
from lnbits.helpers import sha256s


async def refresh(job: ScheduledJob) -> None:
    options = json.loads(job.payload_json)
    # Perform the extension's work using options and job.user_id.


def myextension_start() -> None:
    scheduler.register("extension:myextension", "refresh", refresh)


async def enable_refresh(user_id: str) -> dict:
    # Call this from your authenticated user configuration endpoint.
    job = await scheduler.save(
        "extension:myextension",
        ScheduleConfig(
            id="myextension:" + sha256s(user_id) + ":refresh",
            handler="refresh",
            cron_expression="*/10 * * * *",
            payload_json='{"configuration_id":"example"}',
        ),
        user_id=user_id,
    )
    return job.public_data()
```

Job IDs must be globally unique. A UUID saved with the configuration or a
namespaced ID using a hashed user ID is suitable. Return `public_data()` to
clients so account IDs and lease tokens remain private.

Core uses the same API with namespace `core`. An extension-wide job omits
`user_id`. Python extensions must enforce authentication/admin checks in their
own configuration endpoints: Python is trusted application code, not sandboxed.
The service checks that the extension and any user owner remain active.

Use `scheduler.list(namespace, user_id=..., limit=100, offset=0)` and
`scheduler.delete(namespace, job_id, user_id=...)` to manage the corresponding
scope. Save the same ID with `enabled=False` to pause, or `enabled=True` to resume.
Saving recalculates the next occurrence from the current time. IDs cannot be
reassigned across namespaces or owners.

## WASM host API and permissions

Declare scheduling permissions in the extension manifest for administrator
approval:

| Permission            | Scope                                                                         |
| --------------------- | ----------------------------------------------------------------------------- |
| `scheduler.user`      | Manage jobs belonging to the authenticated user                               |
| `scheduler.extension` | Manage shared jobs for the extension; requires an authenticated administrator |

An extension may request either or both. Scheduling permission does not grant
notification, HTTP, storage, or payment access. Each still needs its own grants.

The host methods are `scheduler.set`, `scheduler.list`, and `scheduler.delete`,
exposed through WIT instance `lnbits:extension/scheduler` as `set-schedule`,
`list-schedules`, and `delete-schedule`. The TypeScript SDK generator discovers
these methods automatically.

`scheduler.set` accepts `id` (optional on first creation), `handler`,
`cronExpression`, `timezone` (default `UTC`), `payloadJson` (a JSON object, up to
8192 bytes), `enabled` (default true), and `scope` (`user` by default, or
`extension`). It returns `scheduleJson`; retain its `id` and send it on updates.
Listing returns `schedulesJson` and accepts `scope`, `limit`, and `offset`.
Deletion accepts `id` and `scope` and returns `deleted`.

The host assigns the extension namespace and user identity; callers cannot
supply either. Only interactive authenticated requests may manage schedules.
Scheduled callbacks cannot create additional jobs. Owners may still list/delete
their jobs after the scheduling grant is revoked; shared jobs remain admin-only.

The handler must be a registered WASM export with `visibility: "event"`. Its
JSON payload contains `scheduleId`, `scheduledAt` (the saved due time), and `data`
(the decoded `payloadJson`). The callback runs with `context="schedule"` and
without a browser access token. User-scoped callbacks receive their owner's
storage and notification context. Shared callbacks have no user owner and cannot
access private owner-scoped storage or choose another user's wallet. Scheduled
payments require the existing background-payment permission and per-wallet grant.

Shared data APIs are separate from scheduling. An extension-wide price collector
and per-user alert evaluators can use different schedules and permissions; this
scheduler does not create the pricebot, its tables, or a shared storage API.
