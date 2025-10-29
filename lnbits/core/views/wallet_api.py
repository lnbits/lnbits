from http import HTTPStatus
from uuid import uuid4

from fastapi import (
    APIRouter,
    Body,
    Depends,
    HTTPException,
)

from lnbits.core.crud.users import (
    get_account,
    get_account_by_username_or_email,
    update_account,
)
from lnbits.core.crud.wallets import (
    create_wallet,
    force_delete_wallet,
    get_wallets_paginated,
)
from lnbits.core.models import CreateWallet, KeyType, User, Wallet, WalletTypeInfo
from lnbits.core.models.lnurl import StoredPayLink, StoredPayLinks
from lnbits.core.models.misc import SimpleStatus
from lnbits.core.models.wallets import (
    WalletsFilters,
    WalletSharePermission,
    WalletShareStatus,
    WalletType,
)
from lnbits.core.services.wallets import (
    create_lightning_shared_wallet,
)
from lnbits.db import Filters, Page
from lnbits.decorators import (
    check_user_exists,
    parse_filters,
    require_admin_key,
    require_invoice_key,
)
from lnbits.helpers import generate_filter_params_openapi

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
    user: User = Depends(check_user_exists),
    filters: Filters = Depends(parse_filters(WalletsFilters)),
):
    page = await get_wallets_paginated(
        user_id=user.id,
        filters=filters,
    )

    return page


@wallet_router.put("/share/invite")
async def api_invite_wallet_share(
    data: WalletSharePermission, key_info: WalletTypeInfo = Depends(require_admin_key)
) -> WalletSharePermission:
    source_wallet = key_info.wallet
    if not source_wallet.is_lightning_wallet:
        raise HTTPException(
            HTTPStatus.BAD_REQUEST, "Only lightning wallets can be shared."
        )
    if not data.username:
        raise HTTPException(HTTPStatus.BAD_REQUEST, "Username or email missing.")
    invited_user = await get_account_by_username_or_email(data.username)
    if not invited_user:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Invited user not found.")

    share = source_wallet.extra.find_share_for_user(invited_user.id)
    if share:
        raise HTTPException(
            HTTPStatus.BAD_REQUEST, "User already invited to this wallet."
        )

    invite_request = source_wallet.extra.add_share_request(
        user_id=invited_user.id,
        username=invited_user.username or invited_user.email,
        permissions=data.permissions,
        request_type=WalletShareStatus.INVITE_SENT,
    )
    await update_wallet(source_wallet)

    wallet_owner = await get_account(source_wallet.user)
    if not wallet_owner:
        raise HTTPException(
            HTTPStatus.INTERNAL_SERVER_ERROR, "Cannot find wallet owner."
        )
    invited_user.extra.add_wallet_invite_request(
        from_user_id=wallet_owner.id,
        from_user_name=wallet_owner.username or wallet_owner.email,
        to_wallet_id=source_wallet.id,
        to_wallet_name=source_wallet.name,
    )
    await update_account(invited_user)

    return invite_request


@wallet_router.put("/share/accept")
async def api_accept_wallet_share_request(
    data: WalletSharePermission, key_info: WalletTypeInfo = Depends(require_admin_key)
) -> WalletSharePermission:
    source_wallet = key_info.wallet
    if not source_wallet.is_lightning_wallet:
        raise HTTPException(
            HTTPStatus.BAD_REQUEST, "Only lightning wallets can be shared."
        )
    if not data.wallet_id:
        raise HTTPException(HTTPStatus.BAD_REQUEST, "Wallet ID missing.")

    share = source_wallet.extra.find_share_for_wallet(data.wallet_id)
    if not share:
        raise HTTPException(HTTPStatus.BAD_REQUEST, "Share not found")
    if not share.wallet_id:
        raise HTTPException(HTTPStatus.BAD_REQUEST, "Wallet ID missing in share.")

    mirror_wallet = await get_wallet(share.wallet_id)
    if not mirror_wallet:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Target wallet not found")
    if not mirror_wallet.is_lightning_shared_wallet:
        raise HTTPException(
            HTTPStatus.BAD_REQUEST, "Target wallet is not a shared wallet."
        )

    share.approve(permissions=data.permissions)
    await update_wallet(source_wallet)
    return share


@wallet_router.delete("/share/{user_id_hash}")
async def api_delete_wallet_share_permissions(
    user_id_hash: str, key_info: WalletTypeInfo = Depends(require_admin_key)
) -> SimpleStatus:
    source_wallet = key_info.wallet
    if not source_wallet.is_lightning_wallet:
        raise HTTPException(
            HTTPStatus.BAD_REQUEST, "Source wallet is not a lightning wallet."
        )

    share = source_wallet.extra.find_share_for_user_id_hash(user_id_hash)
    if not share:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Wallet share not found.")
    source_wallet.extra.remove_share_for_user(user_id_hash)
    mirror_wallet = await get_wallet(share.wallet_id) if share.wallet_id else None
    if not mirror_wallet:
        await update_wallet(source_wallet)
        return SimpleStatus(
            success=True, message="Permission removed. Target wallet not found."
        )

    if not mirror_wallet.is_lightning_shared_wallet:
        raise HTTPException(
            HTTPStatus.BAD_REQUEST, "Target wallet is not a shared lightning wallet."
        )

    if mirror_wallet.shared_wallet_id != source_wallet.id:
        raise HTTPException(
            HTTPStatus.BAD_REQUEST, "Not the owner of the shared wallet."
        )

    await force_delete_wallet(mirror_wallet.id)

    await update_wallet(source_wallet)
    return SimpleStatus(success=True, message="Permission removed.")


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
    wallet_id: str, user: User = Depends(check_user_exists)
) -> Wallet:
    wallet = await get_wallet(wallet_id)
    if not wallet or wallet.user != user.id:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Wallet not found")

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
    wallet_id: str, user: User = Depends(check_user_exists)
) -> None:
    wallet = await get_wallet(wallet_id)
    if not wallet or wallet.user != user.id:
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
        return await create_lightning_shared_wallet(
            user_id=key_info.wallet.user,
            shared_wallet_id=data.shared_wallet_id,
        )

    raise HTTPException(
        HTTPStatus.BAD_REQUEST,
        f"Unknown wallet type: {data.wallet_type}.",
    )
