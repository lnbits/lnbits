from starlette.concurrency import run_in_threadpool

from lnbits.core.crud.onchain import create_fresh_addresses, get_addresses
from lnbits.core.crud.users import (
    get_account,
    get_account_by_username_or_email,
    update_account,
)
from lnbits.core.crud.wallets import (
    create_wallet,
    force_delete_wallet,
    get_standalone_wallet,
    get_wallet,
    get_wallets,
    init_onchain_wallet_state,
    update_wallet,
)
from lnbits.core.models.misc import SimpleStatus
from lnbits.core.models.onchain import Address
from lnbits.core.models.users import Account
from lnbits.core.models.wallets import (
    CreateOnchainWallet,
    OnchainMeta,
    OnchainWallet,
    Wallet,
    WalletSharePermission,
    WalletShareStatus,
    WalletType,
)
from lnbits.db import Connection
from lnbits.helpers import sha256s
from lnbits.onchain.helpers import descriptor_fingerprint, descriptor_type, parse_key


async def invite_to_wallet(
    source_wallet: Wallet, data: WalletSharePermission
) -> WalletSharePermission:
    if not source_wallet.is_lightning_wallet:
        raise ValueError("Only lightning wallets can be shared.")
    if not data.username:
        raise ValueError("Username or email missing.")
    invited_user = await get_account_by_username_or_email(data.username)
    if not invited_user:
        raise ValueError("Invited user not found.")

    request_id = sha256s(invited_user.id + source_wallet.id)
    share = source_wallet.extra.find_share_by_id(request_id)
    if share:
        raise ValueError("User already invited to this wallet.")

    invite_request = source_wallet.extra.invite_user_to_shared_wallet(
        request_id=request_id,
        request_type=WalletShareStatus.INVITE_SENT,
        username=data.username,
        permissions=data.permissions,
    )
    await update_wallet(source_wallet)

    wallet_owner = await get_account(source_wallet.user)
    if not wallet_owner:
        raise ValueError("Cannot find wallet owner.")
    invited_user.extra.add_wallet_invite_request(
        request_id=request_id,
        from_user_name=wallet_owner.username or wallet_owner.email,
        to_wallet_id=source_wallet.id,
        to_wallet_name=source_wallet.name,
    )
    await update_account(invited_user)

    return invite_request


async def reject_wallet_invitation(invited_user_id: str, share_request_id: str):
    invited_user = await get_account(invited_user_id)
    if not invited_user:
        raise ValueError("Invited user not found.")

    existing_request = invited_user.extra.find_wallet_invite_request(share_request_id)
    if not existing_request:
        raise ValueError("Invitation not found.")

    invited_user.extra.remove_wallet_invite_request(share_request_id)
    await update_account(invited_user)


async def update_wallet_share_permissions(
    source_wallet: Wallet, data: WalletSharePermission
) -> WalletSharePermission:
    if not source_wallet.is_lightning_wallet:
        raise ValueError("Only lightning wallets can be shared.")
    if not data.shared_with_wallet_id:
        raise ValueError("Wallet ID missing.")

    share = source_wallet.extra.find_share_for_wallet(data.shared_with_wallet_id)
    if not share:
        raise ValueError("Share not found")

    if not share.shared_with_wallet_id:
        raise ValueError("Share does not have a mirror wallet ID.")

    mirror_wallet = await get_wallet(share.shared_with_wallet_id)
    if not mirror_wallet:
        raise ValueError("Target wallet not found")
    if not mirror_wallet.is_lightning_shared_wallet:
        raise ValueError("Target wallet is not a shared wallet.")
    if mirror_wallet.shared_wallet_id != source_wallet.id:
        raise ValueError("Not the owner of the shared wallet.")

    share.approve(permissions=data.permissions)
    await update_wallet(source_wallet)
    return share


async def delete_wallet_share(source_wallet: Wallet, request_id: str) -> SimpleStatus:
    if not source_wallet.is_lightning_wallet:
        raise ValueError("Source wallet is not a lightning wallet.")

    share = source_wallet.extra.find_share_by_id(request_id)
    if not share:
        raise ValueError("Wallet share not found.")
    source_wallet.extra.remove_share_by_id(request_id)

    invited_user = await get_account_by_username_or_email(share.username)
    if not invited_user:
        await update_wallet(source_wallet)
        return SimpleStatus(
            success=True, message="Permission removed. Invited user not found."
        )
    if invited_user.extra.find_wallet_invite_request(request_id):
        invited_user.extra.remove_wallet_invite_request(request_id)
        await update_account(invited_user)

    mirror_wallets = await get_wallets(
        invited_user.id, wallet_type=WalletType.LIGHTNING_SHARED
    )
    mirror_wallet = next(
        (w for w in mirror_wallets if w.shared_wallet_id == source_wallet.id), None
    )

    if not mirror_wallet:
        await update_wallet(source_wallet)
        return SimpleStatus(
            success=True, message="Permission removed. Target wallet not found."
        )

    if not mirror_wallet.is_lightning_shared_wallet:
        raise ValueError("Target wallet is not a shared lightning wallet.")

    if mirror_wallet.shared_wallet_id != source_wallet.id:
        raise ValueError("Not the owner of the shared wallet.")

    await force_delete_wallet(mirror_wallet.id)

    await update_wallet(source_wallet)
    return SimpleStatus(success=True, message="Permission removed.")


async def create_lightning_shared_wallet(
    user_id: str,
    source_wallet_id: str,
    conn: Connection | None = None,
) -> Wallet:
    source_wallet = await get_standalone_wallet(source_wallet_id, conn=conn)
    if not source_wallet:
        raise ValueError("Shared wallet does not exist.")

    if not source_wallet.is_lightning_wallet:
        raise ValueError("Shared wallet is not a lightning wallet.")

    if source_wallet.user == user_id:
        raise ValueError("Cannot mirror your own wallet.")

    invited_user = await get_account(user_id, conn=conn)
    if not invited_user:
        raise ValueError("Cannot find invited user.")

    return await _accept_invitation_to_shared_wallet(
        invited_user, source_wallet, conn=conn
    )


async def init_onchain_wallet(
    data: CreateOnchainWallet, wallet: OnchainWallet
) -> OnchainWallet | None:
    descriptor, network = await run_in_threadpool(parse_key, data.masterpub)
    assert network
    signing_network = "Testnet" if data.network == "Testnet4" else data.network
    if signing_network != network["name"]:
        raise ValueError(
            "Account network error.  This account is for '{}'".format(network["name"])
        )

    wallet.name = data.title
    wallet.onchain_network = data.network
    wallet.onchain_wallet_kind = "watch"
    wallet.onchain_meta = OnchainMeta(
        accountPath=data.meta.accountPath,
        xpub=data.meta.xpub,
        masterpub=data.masterpub,
        fingerprint=descriptor_fingerprint(descriptor),
        script_type=descriptor_type(descriptor),
    )

    return await init_onchain_wallet_state(wallet)


async def get_wallet_addresses(wallet: OnchainWallet) -> list[Address]:
    addresses = await get_addresses(wallet.id)
    config = wallet.onchain_config

    if not addresses:
        await create_fresh_addresses(wallet.id, 0, config.receive_gap_limit)
        await create_fresh_addresses(wallet.id, 0, config.change_gap_limit, True)
        addresses = await get_addresses(wallet.id)

    receive_addresses = list(filter(lambda addr: addr.branch_index == 0, addresses))
    change_addresses = list(filter(lambda addr: addr.branch_index == 1, addresses))

    last_receive_address = list(
        filter(lambda addr: addr.has_activity, receive_addresses)
    )[-1:]
    last_change_address = list(
        filter(lambda addr: addr.has_activity, change_addresses)
    )[-1:]

    if last_receive_address:
        current_index = receive_addresses[-1].address_index
        address_index = last_receive_address[0].address_index
        await create_fresh_addresses(
            wallet.id, current_index + 1, address_index + config.receive_gap_limit + 1
        )

    if last_change_address:
        current_index = change_addresses[-1].address_index
        address_index = last_change_address[0].address_index
        await create_fresh_addresses(
            wallet.id,
            current_index + 1,
            address_index + config.change_gap_limit + 1,
            True,
        )

    return await get_addresses(wallet.id)


async def _accept_invitation_to_shared_wallet(
    invited_user: Account,
    source_wallet: Wallet,
    conn: Connection | None = None,
) -> Wallet:
    request_id = sha256s(invited_user.id + source_wallet.id)
    existing_request = source_wallet.extra.find_share_by_id(request_id)
    if not existing_request:
        raise ValueError("No invitation found for this invited user.")
    if existing_request.status == WalletShareStatus.APPROVED:
        raise ValueError("This wallet is already shared with you.")
    if existing_request.status != WalletShareStatus.INVITE_SENT:
        raise ValueError("Unknown request type.")

    invited_user.extra.remove_wallet_invite_request(request_id)
    await update_account(invited_user)

    # todo: double check if user already has a mirror wallet for this source wallet

    mirror_wallet = await create_wallet(
        user_id=invited_user.id,
        wallet_name=source_wallet.name,
        wallet_type=WalletType.LIGHTNING_SHARED,
        shared_wallet_id=source_wallet.id,
        conn=conn,
    )
    existing_request.approve(shared_with_wallet_id=mirror_wallet.id)
    await update_wallet(source_wallet, conn=conn)
    mirror_wallet.mirror_shared_wallet(source_wallet)
    return mirror_wallet
