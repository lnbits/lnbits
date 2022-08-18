from http import HTTPStatus

from fastapi.param_functions import Query
from fastapi.params import Depends
from starlette.exceptions import HTTPException

from lnbits.core.crud import get_user
from lnbits.decorators import WalletTypeInfo, get_key_type

from . import strike_ext
from .crud import (
    create_configuration,
    delete_configuration,
    get_configuration,
    get_configurations,
    get_forwards,
)
from .models import CreateConfiguration, StrikeConfiguration, StrikeForward
from .strike_api import StrikeApiClient, StrikeProfile


@strike_ext.post("/api/v1/configurations")
async def api_create_config(data: CreateConfiguration):
    """Create a configuration"""

    client = StrikeApiClient()
    profile = await client.get_profile(data.handle)
    if not profile:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"Strike account with handle {data.handle} doesn't exist",
        )

    if not profile.currencies:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f"Strike account with handle {data.handle} has no currency configured",
        )

    default_currency = filter(
        lambda item: item.isDefaultCurrency == True and item.isAvailable == True,
        profile.currencies,
    )

    if not default_currency:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f"Strike account with handle {data.handle} has no default and available currency",
        )

    try:
        config = await create_configuration(data, list(default_currency)[0].currency)
    except Exception as e:
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=str(e))

    return config.dict()


@strike_ext.get("/api/v1/configurations")
async def api_get_configurations(wallet: WalletTypeInfo = Depends(get_key_type)):
    """Return list of all configurations assigned to wallet with given wallets"""
    wallet_ids = (await get_user(wallet.wallet.user)).wallet_ids
    configurations = []
    for wallet_id in wallet_ids:
        new_configs = await get_configurations(wallet_id)
        configurations += new_configs if new_configs else []
    return [config.dict() for config in configurations] if configurations else []


@strike_ext.get("/api/v1/forwards")
async def api_get_forwards(wallet: WalletTypeInfo = Depends(get_key_type)):
    """Return list of all forwards assigned to wallet with given wallets"""
    wallet_ids = (await get_user(wallet.wallet.user)).wallet_ids
    forwards = []
    for wallet_id in wallet_ids:
        new_forwards = await get_forwards(wallet_id)
        forwards += new_forwards if new_forwards else []
    return [forward.dict() for forward in forwards] if forwards else []


@strike_ext.delete("/api/v1/configurations/{id}")
async def api_delete_configuration(
    wallet: WalletTypeInfo = Depends(get_key_type), id: str = Query(None)
):
    """Delete the configuration with the given id"""
    config = await get_configuration(id)
    if not config:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="No config with this ID!"
        )
    if config.lnbits_wallet != wallet.wallet.id:

        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="Not authorized to delete this config!",
        )
    await delete_configuration(id)

    return "", HTTPStatus.NO_CONTENT
