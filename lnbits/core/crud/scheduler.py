from lnbits.core.db import db
from lnbits.core.models.scheduler import (
    ScheduledJob,
    ScheduledJobFilters,
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
            handler = excluded.handler,
            cron_expression = excluded.cron_expression,
            timezone = excluded.timezone,
            payload_json = excluded.payload_json,
            enabled = excluded.enabled,
            next_run_at = excluded.next_run_at
        WHERE scheduled_jobs.namespace = excluded.namespace
          AND (scheduled_jobs.user_id = excluded.user_id
               OR (scheduled_jobs.user_id IS NULL AND excluded.user_id IS NULL))
        """,
        job.dict(),
    )
    if result.rowcount != 1:
        raise PermissionError("Schedule ID is already in use by another owner.")
    stored = await get_scheduled_job(job.id)
    assert stored
    return stored


async def get_scheduled_job(job_id: str) -> ScheduledJob | None:
    return await db.fetchone(
        "SELECT * FROM scheduled_jobs WHERE id = :id",
        {"id": job_id},
        ScheduledJob,
    )


async def list_scheduled_jobs(
    namespace: str, user_id: str | None, *, limit: int = 100, offset: int = 0
) -> list[ScheduledJob]:
    return await db.fetchall(
        """
        SELECT * FROM scheduled_jobs WHERE namespace = :namespace
          AND (user_id = :user_id OR (user_id IS NULL AND :user_id IS NULL))
        ORDER BY id LIMIT :limit OFFSET :offset
        """,
        {"namespace": namespace, "user_id": user_id, "limit": limit, "offset": offset},
        ScheduledJob,
    )


async def get_scheduled_jobs_overview(
    filters: Filters[ScheduledJobFilters],
) -> Page[ScheduledJobSummary]:
    if not filters.sortby:
        filters.sortby = "next_run_at"
    return await db.fetch_page(
        """
        SELECT * FROM (
            SELECT id, namespace, handler, cron_expression, timezone, enabled,
                   next_run_at,
                   CASE WHEN user_id IS NOT NULL THEN 'user'
                        WHEN namespace = 'core' THEN 'core'
                        ELSE 'extension' END AS scope
            FROM scheduled_jobs
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
          AND (user_id = :user_id OR (user_id IS NULL AND :user_id IS NULL))
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
