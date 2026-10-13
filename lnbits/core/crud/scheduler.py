from lnbits.core.db import db
from lnbits.core.models.scheduler import (
    ScheduledJob,
    ScheduledJobFilters,
    ScheduledJobRun,
    ScheduledJobRunFilters,
    ScheduledJobRunStatus,
    ScheduledJobSummary,
)
from lnbits.db import Filters, Page


async def save_scheduled_job(job: ScheduledJob) -> ScheduledJob:
    result = await db.execute(
        """
        INSERT INTO scheduled_jobs
            (id, namespace, user_id, handler, cron_expression, timezone,
             payload_json, enabled, next_run_at)
        VALUES
            (:id, :namespace, :user_id, :handler, :cron_expression, :timezone,
             :payload_json, :enabled, :next_run_at)
        ON CONFLICT (id) DO UPDATE SET
            cron_expression = excluded.cron_expression,
            timezone = excluded.timezone,
            payload_json = excluded.payload_json,
            enabled = excluded.enabled,
            next_run_at = excluded.next_run_at
        WHERE scheduled_jobs.namespace = excluded.namespace
          AND scheduled_jobs.handler = excluded.handler
          AND (scheduled_jobs.user_id = excluded.user_id
               OR (scheduled_jobs.user_id IS NULL AND excluded.user_id IS NULL))
        """,
        job.dict(),
    )
    if result.rowcount != 1:
        raise PermissionError(
            "Schedule ID is already in use by another owner or handler."
        )
    stored = await get_scheduled_job(job.id)
    assert stored
    return stored


async def get_scheduled_job(job_id: str) -> ScheduledJob | None:
    return await db.fetchone(
        "SELECT * FROM scheduled_jobs WHERE id = :id",
        {"id": job_id},
        ScheduledJob,
    )


async def get_scheduled_jobs_count(namespace: str, user_id: str, handler: str) -> int:
    row: dict | None = await db.fetchone(
        """
        SELECT COUNT(*) AS count FROM scheduled_jobs
        WHERE namespace = :namespace AND user_id = :user_id AND handler = :handler
        """,
        {"namespace": namespace, "user_id": user_id, "handler": handler},
    )
    return int(row["count"]) if row else 0


async def get_scheduled_jobs_paginated(
    namespace: str, user_id: str | None, *, limit: int = 100, offset: int = 0
) -> Page[ScheduledJob]:
    return await db.fetch_page(
        "SELECT * FROM scheduled_jobs",
        where=[
            "namespace = :namespace",
            "(user_id = :user_id "
            "OR (user_id IS NULL AND CAST(:user_id AS TEXT) IS NULL))",
        ],
        values={"namespace": namespace, "user_id": user_id},
        filters=Filters(limit=limit, offset=offset, sortby="id"),
        model=ScheduledJob,
        table_name="scheduled_jobs",
    )


async def get_scheduled_jobs_overview_paginated(
    filters: Filters[ScheduledJobFilters],
) -> Page[ScheduledJobSummary]:
    if not filters.sortby:
        filters.sortby = "next_run_at"
    return await db.fetch_page(
        """
        SELECT * FROM (
            SELECT job.id, job.namespace, job.handler, job.cron_expression,
                   job.timezone, job.enabled, job.next_run_at,
                   job.user_id, account.username, account.email,
                   last_run.started_at AS last_run_at,
                   last_run.status AS last_result,
                   CASE WHEN job.user_id IS NOT NULL THEN 'user'
                        WHEN job.namespace = 'core' THEN 'core'
                        ELSE 'extension' END AS scope
            FROM scheduled_jobs AS job
            LEFT JOIN accounts AS account ON account.id = job.user_id
            LEFT JOIN scheduled_job_runs AS last_run ON last_run.id = (
                SELECT id FROM scheduled_job_runs
                WHERE job_id = job.id AND namespace = job.namespace
                ORDER BY started_at DESC, id DESC LIMIT 1
            )
        ) AS jobs
        """,
        filters=filters,
        model=ScheduledJobSummary,
    )


async def get_scheduled_job_sources() -> list[str]:
    rows: list[dict] = await db.fetchall(
        "SELECT DISTINCT namespace FROM scheduled_jobs ORDER BY namespace"
    )
    return [row["namespace"] for row in rows]


async def delete_scheduled_job(
    job_id: str, namespace: str, user_id: str | None, now: int
) -> bool:
    # Preserve an active claim: deleting and recreating the ID could overlap it.
    result = await db.execute(
        """
        DELETE FROM scheduled_jobs WHERE id = :id AND namespace = :namespace
          AND (user_id = :user_id
               OR (user_id IS NULL AND CAST(:user_id AS TEXT) IS NULL))
          AND (lease_token IS NULL OR lease_until <= :now)
        """,
        {"id": job_id, "namespace": namespace, "user_id": user_id, "now": now},
    )
    return result.rowcount == 1


async def delete_namespace_schedules(namespace: str) -> None:
    await db.execute(
        "DELETE FROM scheduled_jobs WHERE namespace = :namespace",
        {"namespace": namespace},
    )


async def get_due_scheduled_jobs(now: int, limit: int) -> list[ScheduledJob]:
    return await db.fetchall(
        """
        SELECT * FROM scheduled_jobs
        WHERE enabled = true AND next_run_at <= :now
          AND (lease_token IS NULL OR lease_until <= :now)
        ORDER BY next_run_at, id LIMIT :limit
        """,
        {"now": now, "limit": limit},
        ScheduledJob,
    )


async def claim_scheduled_job(
    job_id: str, token: str, now: int, lease_until: int
) -> ScheduledJob | None:
    result = await db.execute(
        """
        UPDATE scheduled_jobs SET lease_token = :token, lease_until = :lease_until
        WHERE id = :id AND enabled = true AND next_run_at <= :now
          AND (lease_token IS NULL OR lease_until <= :now)
        """,
        {"id": job_id, "token": token, "now": now, "lease_until": lease_until},
    )
    if result.rowcount != 1:
        return None
    job = await get_scheduled_job(job_id)
    return job if job and job.lease_token == token else None


async def renew_scheduled_job(job_id: str, token: str, now: int, until: int) -> bool:
    result = await db.execute(
        """
        UPDATE scheduled_jobs SET lease_until = :until
        WHERE id = :id AND lease_token = :token AND lease_until > :now
          AND enabled = true
        """,
        {"id": job_id, "token": token, "now": now, "until": until},
    )
    return result.rowcount == 1


async def finish_scheduled_job(job: ScheduledJob, next_run: int | None) -> None:
    await db.execute(
        """
        UPDATE scheduled_jobs
        SET next_run_at = CASE
                WHEN cron_expression = :cron_expression AND timezone = :timezone
                THEN :next_run ELSE next_run_at END,
            lease_token = NULL, lease_until = 0
        WHERE id = :id AND lease_token = :lease_token
        """,
        {**job.dict(), "next_run": next_run},
    )


async def create_scheduled_job_run(job: ScheduledJob, now: float) -> ScheduledJobRun:
    assert job.lease_token
    run = ScheduledJobRun(
        job_id=job.id,
        namespace=job.namespace,
        handler=job.handler,
        scope=(
            "user"
            if job.user_id
            else "core" if job.namespace == "core" else "extension"
        ),
        timezone=job.timezone,
        scheduled_at=job.next_run_at,
        started_at=now,
    )
    await db.execute(
        """
        INSERT INTO scheduled_job_runs
            (id, job_id, namespace, handler, scope, timezone, scheduled_at,
             started_at, status, lease_token, user_id)
        VALUES (:id, :job_id, :namespace, :handler, :scope, :timezone,
                :scheduled_at, :started_at, :status, :lease_token, :user_id)
        """,
        {**run.dict(), "lease_token": job.lease_token, "user_id": job.user_id},
    )
    return run


async def finish_scheduled_job_run(
    run_id: str,
    status: ScheduledJobRunStatus,
    now: float,
    error_summary: str | None = None,
) -> None:
    await db.execute(
        """
        UPDATE scheduled_job_runs
        SET status = :status, finished_at = :now, error_summary = :error_summary
        WHERE id = :id AND status = 'running'
        """,
        {"id": run_id, "status": status, "now": now, "error_summary": error_summary},
    )


async def get_scheduled_job_runs_paginated(
    filters: Filters[ScheduledJobRunFilters],
) -> Page[ScheduledJobRun]:
    if not filters.sortby:
        filters.sortby = "started_at"
        filters.direction = "desc"
    return await db.fetch_page(
        """
        SELECT id, job_id, namespace, handler, scope, timezone, scheduled_at,
               started_at, finished_at, status, error_summary
        FROM scheduled_job_runs
        """,
        filters=filters,
        model=ScheduledJobRun,
        table_name="scheduled_job_runs",
    )


async def interrupt_expired_scheduled_job_runs(now: float) -> None:
    # Check the durable claim, not local tasks: another process may own this run.
    # The actual finish time is unknown after a crash, so leave it unset.
    await db.execute(
        """
        UPDATE scheduled_job_runs
        SET status = 'interrupted', error_summary = :error_summary
        WHERE status = 'running' AND NOT EXISTS (
            SELECT 1 FROM scheduled_jobs
            WHERE scheduled_jobs.id = scheduled_job_runs.job_id
              AND scheduled_jobs.lease_token = scheduled_job_runs.lease_token
              AND scheduled_jobs.lease_until > :now
        )
        """,
        {
            "now": now,
            "error_summary": "Execution ended without a recorded result; "
            "its lease is no longer active.",
        },
    )


async def delete_expired_scheduled_job_runs(
    cutoff: float, failed_cutoff: float
) -> None:
    await db.execute(
        """
        DELETE FROM scheduled_job_runs
        WHERE (status NOT IN ('running', 'failed')
               AND COALESCE(finished_at, started_at) < :cutoff)
           OR (status = 'failed'
               AND COALESCE(finished_at, started_at) < :failed_cutoff)
        """,
        {"cutoff": cutoff, "failed_cutoff": failed_cutoff},
    )


async def delete_excess_scheduled_job_runs(
    max_runs_per_user: int,
    max_runs_per_extension: int,
    preferred_status: ScheduledJobRunStatus,
) -> None:
    await db.execute(
        """
        DELETE FROM scheduled_job_runs WHERE id IN (
            SELECT id FROM (
                SELECT id, scope, ROW_NUMBER() OVER (
                    PARTITION BY scope,
                        CASE WHEN scope = 'user' THEN user_id ELSE namespace END
                    ORDER BY CASE WHEN status = :preferred_status THEN 0 ELSE 1 END,
                             COALESCE(finished_at, started_at) DESC, id DESC
                ) AS position
                FROM scheduled_job_runs
                WHERE status != 'running'
                  AND scope IN ('user', 'extension')
            ) AS ranked_runs
            WHERE (scope = 'user' AND position > :max_runs_per_user)
               OR (scope = 'extension' AND position > :max_runs_per_extension)
        )
        """,
        {
            "max_runs_per_user": max_runs_per_user,
            "max_runs_per_extension": max_runs_per_extension,
            "preferred_status": preferred_status,
        },
    )
