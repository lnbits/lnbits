from http import HTTPStatus
from uuid import uuid4

from fastapi import (
    APIRouter,
    Body,
    Depends,
    HTTPException,
)

from lnbits.core.crud.wallets import (
    create_wallet,
    get_wallets_paginated,
)
from lnbits.core.models import CreateWallet, KeyType, Wallet, WalletTypeInfo
from lnbits.core.models.lnurl import StoredPayLink, StoredPayLinks
from lnbits.core.models.misc import SimpleStatus
from lnbits.core.models.users import Account, AccountId
from lnbits.core.models.wallets import (
    WalletsFilters,
    WalletSharePermission,
    WalletType,
)
from lnbits.core.services.wallets import (
    create_lightning_shared_wallet,
    delete_wallet_share,
    invite_to_wallet,
    reject_wallet_invitation,
    update_wallet_share_permissions,
)
from lnbits.db import Filters, Page
from lnbits.decorators import (
    check_account_exists,
    check_account_id_exists,
    parse_filters,
    require_admin_key,
    require_invoice_key,
)
from lnbits.helpers import generate_filter_params_openapi
from lnbits.utils.cache import cache

from ..crud import (
    delete_wallet,
    get_wallet,
    update_wallet,
)

wallet_router = APIRouter(prefix="/api/v1/wallet", tags=["Wallet"])


@wallet_router.get("")
async def api_wallet(key_info: WalletTypeInfo = Depends(require_invoice_key)):
    res = {
        "name": key_info.wallet.name,
        "balance": key_info.wallet.balance_msat,
    }
    if key_info.key_type == KeyType.admin:
        res["id"] = key_info.wallet.id
    return res


@wallet_router.get(
    "/paginated",
    name="Wallet List",
    summary="get paginated list of user wallets",
    response_description="list of user wallets",
    response_model=Page[Wallet],
    openapi_extra=generate_filter_params_openapi(WalletsFilters),
)
async def api_wallets_paginated(
    account_id: AccountId = Depends(check_account_id_exists),
    filters: Filters = Depends(parse_filters(WalletsFilters)),
):
    page = await get_wallets_paginated(
        user_id=account_id.id,
        filters=filters,
    )

    return page


@wallet_router.put("/share/invite")
async def api_invite_wallet_share(
    data: WalletSharePermission, key_info: WalletTypeInfo = Depends(require_admin_key)
) -> WalletSharePermission:
    return await invite_to_wallet(key_info.wallet, data)


@wallet_router.delete("/share/invite/{share_request_id}")
async def api_reject_wallet_invitation(
    share_request_id: str, invited_user: Account = Depends(check_account_exists)
) -> SimpleStatus:
    await reject_wallet_invitation(invited_user.id, share_request_id)
    return SimpleStatus(success=True, message="Invitation rejected.")


@wallet_router.put("/share")
async def api_accept_wallet_share_request(
    data: WalletSharePermission, key_info: WalletTypeInfo = Depends(require_admin_key)
) -> WalletSharePermission:
    return await update_wallet_share_permissions(key_info.wallet, data)


@wallet_router.delete("/share/{share_request_id}")
async def api_delete_wallet_share_permissions(
    share_request_id: str, key_info: WalletTypeInfo = Depends(require_admin_key)
) -> SimpleStatus:
    return await delete_wallet_share(key_info.wallet, share_request_id)


@wallet_router.put("/{new_name}")
async def api_update_wallet_name(
    new_name: str, key_info: WalletTypeInfo = Depends(require_admin_key)
):
    wallet = await get_wallet(key_info.wallet.id)
    if not wallet:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Wallet not found")
    wallet.name = new_name

    await update_wallet(wallet)
    return {
        "id": wallet.id,
        "name": wallet.name,
        "balance": wallet.balance_msat,
    }


@wallet_router.put("/reset/{wallet_id}")
async def api_reset_wallet_keys(
    wallet_id: str,
    account_id: AccountId = Depends(check_account_id_exists),
) -> Wallet:
    wallet = await get_wallet(wallet_id)
    if not wallet or wallet.user != account_id.id:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Wallet not found")

    cache.pop(f"auth:wallet:{wallet.id}")
    cache.pop(f"auth:x-api-key:{wallet.adminkey}")
    cache.pop(f"auth:x-api-key:{wallet.inkey}")

    wallet.adminkey = uuid4().hex
    wallet.inkey = uuid4().hex
    await update_wallet(wallet)
    return wallet


@wallet_router.put("/stored_paylinks/{wallet_id}")
async def api_put_stored_paylinks(
    wallet_id: str,
    data: StoredPayLinks,
    key_info: WalletTypeInfo = Depends(require_admin_key),
) -> list[StoredPayLink]:
    if key_info.wallet.id != wallet_id:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN, detail="You cannot modify this wallet"
        )
    key_info.wallet.stored_paylinks.links = data.links
    wallet = await update_wallet(key_info.wallet)
    return wallet.stored_paylinks.links


@wallet_router.patch("")
async def api_update_wallet(
    name: str | None = Body(None),
    icon: str | None = Body(None),
    color: str | None = Body(None),
    currency: str | None = Body(None),
    pinned: bool | None = Body(None),
    key_info: WalletTypeInfo = Depends(require_admin_key),
) -> Wallet:
    wallet = await get_wallet(key_info.wallet.id)
    if not wallet:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Wallet not found")
    wallet.name = name or wallet.name
    wallet.extra.icon = icon or wallet.extra.icon
    wallet.extra.color = color or wallet.extra.color
    wallet.extra.pinned = pinned if pinned is not None else wallet.extra.pinned
    wallet.currency = currency if currency is not None else wallet.currency

    await update_wallet(wallet)
    return wallet


@wallet_router.delete("/{wallet_id}")
async def api_delete_wallet(
    wallet_id: str, account_id: AccountId = Depends(check_account_id_exists)
) -> None:
    wallet = await get_wallet(wallet_id)
    if not wallet or wallet.user != account_id.id:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Wallet not found")

    await delete_wallet(
        user_id=wallet.user,
        wallet_id=wallet.id,
    )


@wallet_router.post("")
async def api_create_wallet(
    data: CreateWallet,
    key_info: WalletTypeInfo = Depends(require_admin_key),
) -> Wallet:
    if data.wallet_type == WalletType.LIGHTNING:
        return await create_wallet(user_id=key_info.wallet.user, wallet_name=data.name)

    if data.wallet_type == WalletType.LIGHTNING_SHARED:
        if not data.shared_wallet_id:
            raise HTTPException(
                HTTPStatus.BAD_REQUEST,
                "Shared wallet ID is required for shared wallets.",
            )
        return await create_lightning_shared_wallet(
            user_id=key_info.wallet.user,
            source_wallet_id=data.shared_wallet_id,
        )

    raise HTTPException(
        HTTPStatus.BAD_REQUEST,
        f"Unknown wallet type: {data.wallet_type}.",
    )
