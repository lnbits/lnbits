from http import HTTPStatus

from fastapi import APIRouter, Depends

from lnbits.core.models.misc import SimpleStatus
from lnbits.core.services.fiat_providers import test_connection
from lnbits.decorators import check_admin

fiat_router = APIRouter(tags=["Fiat API"], prefix="/api/v1/fiat")


@fiat_router.put(
    "/check/{provider}",
    status_code=HTTPStatus.OK,
    dependencies=[Depends(check_admin)],
)
async def api_test_fiat_provider(provider: str) -> SimpleStatus:
    return await test_connection(provider)
