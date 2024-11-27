from fastapi import APIRouter, Depends

from lnbits.core.crud.audit import (
    get_audit_entries,
    get_count_stats,
    get_long_duration_stats,
)
from lnbits.core.models import AuditEntry, AuditFilters
from lnbits.core.models.audit import AuditStats
from lnbits.db import Filters, Page
from lnbits.decorators import check_admin, parse_filters
from lnbits.helpers import generate_filter_params_openapi

audit_router = APIRouter(
    prefix="/audit/api/v1", dependencies=[Depends(check_admin)], tags=["Audit"]
)


@audit_router.get(
    "",
    name="Get audit entries",
    summary="Get paginated list audit entries",
    openapi_extra=generate_filter_params_openapi(AuditFilters),
)
async def api_get_audit(
    filters: Filters = Depends(parse_filters(AuditFilters)),
) -> Page[AuditEntry]:
    return await get_audit_entries(filters)


@audit_router.get(
    "/stats",
    name="Get audit entries",
    summary="Get paginated list audit entries",
    openapi_extra=generate_filter_params_openapi(AuditFilters),
)
async def api_get_audit_stats(
    filters: Filters = Depends(parse_filters(AuditFilters)),
) -> AuditStats:
    request_mothod_stats = await get_count_stats("request_method", filters)
    response_code_stats = await get_count_stats("response_code", filters)
    components_stats = await get_count_stats("component", filters)
    long_duration_stats = await get_long_duration_stats(filters)
    return AuditStats(
        request_method=request_mothod_stats,
        response_code=response_code_stats,
        component=components_stats,
        long_duration=long_duration_stats,
    )
