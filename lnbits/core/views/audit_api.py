from fastapi import APIRouter, Depends

from lnbits.core.crud.audit import get_audit_entries
from lnbits.core.models import AuditEntry, AuditFilters
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
async def api_get_users(
    filters: Filters = Depends(parse_filters(AuditFilters)),
) -> Page[AuditEntry]:
    return await get_audit_entries(filters)
