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
- Admins can enable or disable the scheduler in Settings > Scheduler. The
  `lnbits_scheduler_enabled` setting defaults to true and takes effect on save
  without restarting the server. While disabled, the scheduler stays alive but
  does not poll for jobs or maintain run history. Jobs already running finish
  normally. Re-enabling runs each overdue job once, then resumes its cron schedule
  without replaying every missed occurrence.
- Application shutdown and extension job shutdown wait up to five seconds for
  scheduler cleanup, log failures or unfinished jobs, and continue the remaining
  cleanup. This deadline requires a responsive event loop; it cannot forcibly
  terminate native threads or bound an extension's separate Python stop hook.

Leases coordinate workers but do not make external effects exactly-once. Callbacks
that send messages or make payments must handle duplicate attempts after a crash
or lost lease. Python callbacks must be asynchronous and cooperate with
cancellation. WASM jobs use the existing runtime resource limits and invocation
monitoring (`trigger_type="schedule"`, schedule ID in `context`).

## Execution history

The admin-only Scheduler page shows each job's latest attempt and result. Select
a job to open its execution history, or use **Run history** to browse all retained
attempts, including deleted jobs. History opens on `/scheduler/runs` with
clearable job ID, namespace, user ID, and status filters, search, and pagination.
Opening a job prefills its job ID, namespace, and user ID. Filters are stored in
the URL so refreshes and shared links preserve them. Its API is
`GET /scheduler/api/v1/runs`, with optional `job_id`, `namespace`, `user_id`,
`status`, `search`, `limit`, and `offset` parameters.

Each attempt is stored in the core database's `scheduled_job_runs` table. Records
snapshot the job ID, source, handler, scope, timezone, scheduled time, actual
start and finish times, and result. Durations are calculated from start and finish
times. User ownership is stored internally so history limits still apply after a
job is deleted. User IDs and lease tokens are never returned by the API. Failed
attempts include the exception type and a redacted error message, limited to 500
characters, in the run details and server log. Common credential fields, bearer
tokens, and 64-character hex values are redacted. WASM backtraces are omitted in
favor of the cause. Job payloads and Python tracebacks are not attached to errors.

Results are `running`, `succeeded`, `failed`, `cancelled`, `interrupted`, or
`skipped`. Missing or paused jobs and unregistered handlers are skipped. An
unfinished attempt whose lease is no longer active becomes interrupted; its
finish time and duration remain unknown. A recorded result describes the
callback's completion, not a guarantee about its external effects.

History limits are configurable under **Settings → Scheduler** and apply without
a restart:

- `lnbits_scheduler_history_retention_days`: seven days for successful, cancelled,
  interrupted, and skipped attempts.
- `lnbits_scheduler_history_failed_retention_days`: thirty days for failed attempts.
- `lnbits_scheduler_history_max_runs_per_user`: 1,000 completed attempts per user,
  across all extensions and handlers.
- `lnbits_scheduler_history_max_runs_per_extension`: 1,000 completed shared attempts
  per extension, across all handlers. User attempts do not consume this limit.

All settings have a minimum of one. While the scheduler is enabled, abandoned
runs are marked interrupted once per minute and history cleanup runs every
15 minutes. History can temporarily exceed its limits between cleanups.
Completed attempts expire relative to their finish time; interrupted attempts
use their start time. After expired attempts are removed, count limits remove
oldest non-failed attempts first, then oldest failures.
Active runs are preserved and do not count toward these limits. Shared core jobs
use age retention only.

Deleting a job does not immediately delete its history.
History writes are best-effort: recording failures do not prevent execution or
change the scheduler's retry and lease behavior.

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

Use `scheduler.list_paginated(namespace, user_id=..., limit=100, offset=0)` and
`scheduler.delete(namespace, job_id, user_id=...)` to manage the corresponding
scope. Listing returns a `Page` with `data` and the total number of matching jobs
in `total`. Save the same ID with `enabled=False` to pause, or `enabled=True` to resume.
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

Each scheduling permission must declare a nonempty `policies` list containing
one cron expression and timezone per handler. The administrator reviews and
approves these schedules at installation; policies alone do not create jobs.
For example, a pricebot can declare:

```json
{
  "permissions": [
    {
      "id": "scheduler.extension",
      "policies": [
        {
          "handler": "collect_prices",
          "cron_expression": "* * * * *",
          "timezone": "UTC"
        }
      ]
    },
    {
      "id": "scheduler.user",
      "policies": [
        {
          "handler": "check_alerts",
          "cron_expression": "*/10 * * * *",
          "timezone": "UTC",
          "max_jobs_per_user": 10
        }
      ]
    }
  ]
}
```

Both handlers must be declared in `wasm.exports` with `visibility: "event"`.
Timezone defaults to `UTC`. Handlers must be unique within each permission;
the same handler can have different schedules in the two scopes. Administrators
may grant a subset of the declared handlers, or omit a permission entirely.
Cron and timezone must match the declared policy; schedule changes require an
updated manifest and administrator approval.

Each `scheduler.user` handler policy has a positive integer `max_jobs_per_user`,
defaulting to 10 when omitted, including in existing grants. The quota is separate
for each extension, user, and handler, and counts enabled and paused jobs. Admins
can raise or lower it in the extension permission editor, effective immediately.
Lowering it preserves existing jobs and permits updates and deletion; new jobs
are rejected until the count is below the limit. Deleting a job frees a slot.

WASM extensions can also declare a top-level `schedules` array containing the
shared policies to start automatically. These entries must match granted
`scheduler.extension` policies and cannot be omitted from the grants. Core creates
the jobs on activation and restores missing jobs on startup, preserving existing
jobs' next runs, leases, and administrator pauses. See
[automatic WASM schedules](../wasm-extensions.md#scheduled-work).

The host methods are `scheduler.set`, `scheduler.list`, and `scheduler.delete`,
exposed through WIT instance `lnbits:extension/scheduler` as `set-schedule`,
`list-schedules`, and `delete-schedule`. The TypeScript SDK generator discovers
these methods automatically.

`scheduler.set` accepts `id` (optional on first creation), `handler`,
`cronExpression`, `timezone` (default `UTC`), `payloadJson` (a JSON object, up to
8192 bytes), `enabled` (default true), and `scope` (`user` by default, or
`extension`). It returns `scheduleJson`; retain its `id` and send it on updates.
For user jobs, omitting `id` creates a new job, even for the same handler. Supplying
the same ID updates that job; its handler, owner, and namespace cannot change.
Shared extension jobs retain one stable job ID per handler.
The handler, normalized cron expression, and timezone must match the approved
policy for that scope on both creation and updates. Core checks approval again
before executing a job and during its heartbeat. Revoking the policy blocks
future callbacks and cancels running callbacks at the next heartbeat. The
extension may check its own conditions and return without doing work; it cannot
override the approved schedule. Core and trusted Python schedules do not require
these WASM policies.
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
storage and notification context. Shared callbacks use the storage owner
`extension:<id>`, without a user identity. They can access that extension-owned
partition, but cannot access users' private rows or choose a user's wallet. Scheduled
payments require the existing background-payment permission and per-wallet grant.

Shared data APIs are separate from scheduling. An extension-wide price collector
and per-user alert evaluators can use different schedules and permissions; this
scheduler does not create the pricebot, its tables, or a shared storage API.
