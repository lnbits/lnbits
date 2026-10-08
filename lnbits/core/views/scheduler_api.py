from fastapi import APIRouter, Depends, Query

from lnbits.core.crud.scheduler import (
    get_scheduled_job_runs,
    get_scheduled_job_sources,
    get_scheduled_jobs_overview,
)
from lnbits.core.models.scheduler import (
    ScheduledJobFilters,
    ScheduledJobRun,
    ScheduledJobRunFilters,
    ScheduledJobSummary,
)
from lnbits.db import Filters, Page
from lnbits.decorators import check_admin, check_admin_ui, parse_filters
from lnbits.helpers import generate_filter_params_openapi

scheduler_router = APIRouter(
    prefix="/scheduler/api/v1",
    dependencies=[Depends(check_admin), Depends(check_admin_ui)],
    tags=["Scheduler"],
)


@scheduler_router.get(
    "",
    summary="List scheduled jobs across core and extensions",
    openapi_extra=generate_filter_params_openapi(ScheduledJobFilters),
)
async def api_get_scheduled_jobs(
    filters: Filters[ScheduledJobFilters] = Depends(parse_filters(ScheduledJobFilters)),
    limit: int = Query(default=10, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> Page[ScheduledJobSummary]:
    filters.limit = limit
    filters.offset = offset
    return await get_scheduled_jobs_overview(filters)


@scheduler_router.get("/sources", summary="List scheduled job sources")
async def api_get_scheduled_job_sources() -> list[str]:
    return await get_scheduled_job_sources()


@scheduler_router.get(
    "/runs",
    summary="List retained scheduler executions, including deleted jobs",
    openapi_extra=generate_filter_params_openapi(ScheduledJobRunFilters),
)
async def api_get_scheduled_job_runs(
    filters: Filters[ScheduledJobRunFilters] = Depends(
        parse_filters(ScheduledJobRunFilters)
    ),
    limit: int = Query(default=10, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> Page[ScheduledJobRun]:
    filters.limit = limit
    filters.offset = offset
    return await get_scheduled_job_runs(filters)
