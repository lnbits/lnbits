import pytest

from lnbits.core.crud.users import get_account
from lnbits.core.crud.wallets import create_wallet, get_wallet, update_wallet
from lnbits.core.models.wallets import (
    WalletPermission,
    WalletSharePermission,
    WalletShareStatus,
    WalletType,
)
from lnbits.core.services.wallets import invite_to_wallet
from tests.conftest import new_user


@pytest.mark.anyio
async def test_invite_to_wallet_ok():
    owner_user = await new_user()
    source_wallet = await create_wallet(
        user_id=owner_user.id, wallet_name="source_wallet"
    )
    invited_user = await new_user()
    assert invited_user.username is not None
    wallet_share = await invite_to_wallet(
        source_wallet=source_wallet,
        data=WalletSharePermission(
            username=invited_user.username,
            wallet_id=source_wallet.id,
            permissions=[WalletPermission.VIEW_PAYMENTS],
            status=WalletShareStatus.INVITE_SENT,
        ),
    )
    assert wallet_share.status == WalletShareStatus.INVITE_SENT

    source_wallet = await get_wallet(source_wallet.id)
    assert source_wallet is not None
    share = source_wallet.extra.find_share_for_wallet(source_wallet.id)
    assert share is not None
    assert share.request_id is not None
    assert share.username == invited_user.username
    assert share.permissions == [WalletPermission.VIEW_PAYMENTS]
    assert share.status == WalletShareStatus.INVITE_SENT

    invited_user = await get_account(invited_user.id)
    assert invited_user is not None
    invite_request = invited_user.extra.find_wallet_invite_request(share.request_id)
    assert invite_request is not None
    assert invite_request.request_id == share.request_id
    assert invite_request.from_user_name == owner_user.username or owner_user.email
    assert invite_request.to_wallet_id == source_wallet.id
    assert invite_request.to_wallet_name == source_wallet.name


@pytest.mark.anyio
async def test_invite_to_wallet_twice():
    owner_user = await new_user()
    source_wallet = await create_wallet(
        user_id=owner_user.id, wallet_name="source_wallet"
    )
    invited_user = await new_user()
    assert invited_user.username is not None
    await invite_to_wallet(
        source_wallet=source_wallet,
        data=WalletSharePermission(
            username=invited_user.username,
            wallet_id=source_wallet.id,
            permissions=[WalletPermission.VIEW_PAYMENTS],
            status=WalletShareStatus.INVITE_SENT,
        ),
    )

    with pytest.raises(ValueError, match="User already invited to this wallet."):
        await invite_to_wallet(
            source_wallet=source_wallet,
            data=WalletSharePermission(
                username=invited_user.username,
                wallet_id=source_wallet.id,
                permissions=[WalletPermission.VIEW_PAYMENTS],
                status=WalletShareStatus.INVITE_SENT,
            ),
        )


@pytest.mark.anyio
async def test_invite_to_wallet_non_lightning_wallet():
    owner_user = await new_user()
    source_wallet = await create_wallet(
        user_id=owner_user.id,
        wallet_name="source_wallet",
        wallet_type=WalletType.LIGHTNING_SHARED,
        shared_wallet_id="some_shared_wallet_id",
    )

    invited_user = await new_user()
    assert invited_user.username is not None
    source_wallet.shared_wallet_id = "some_shared_wallet_id"
    await update_wallet(source_wallet)
    with pytest.raises(ValueError, match="Only lightning wallets can be shared."):
        await invite_to_wallet(
            source_wallet=source_wallet,
            data=WalletSharePermission(
                username=invited_user.username,
                wallet_id=source_wallet.id,
                permissions=[WalletPermission.VIEW_PAYMENTS],
                status=WalletShareStatus.INVITE_SENT,
            ),
        )


@pytest.mark.anyio
async def test_invite_to_wallet_wallet_owner_not_found():
    owner_user = await new_user()
    source_wallet = await create_wallet(
        user_id=owner_user.id, wallet_name="source_wallet"
    )
    invited_user = await new_user()
    assert invited_user.username is not None
    # Remove wallet owner by setting an invalid user id
    source_wallet.user = "invalid_user_id"

    with pytest.raises(ValueError, match="Cannot find wallet owner."):
        await invite_to_wallet(
            source_wallet=source_wallet,
            data=WalletSharePermission(
                username=invited_user.username,
                wallet_id=source_wallet.id,
                permissions=[WalletPermission.VIEW_PAYMENTS],
                status=WalletShareStatus.INVITE_SENT,
            ),
        )


@pytest.mark.anyio
async def test_invite_to_wallet_empty_permissions_ok():
    owner_user = await new_user()
    source_wallet = await create_wallet(
        user_id=owner_user.id, wallet_name="source_wallet"
    )
    invited_user = await new_user()
    assert invited_user.username is not None
    # Test with empty permissions list
    wallet_share = await invite_to_wallet(
        source_wallet=source_wallet,
        data=WalletSharePermission(
            username=invited_user.username,
            wallet_id=source_wallet.id,
            permissions=[],
            status=WalletShareStatus.INVITE_SENT,
        ),
    )
    assert wallet_share.permissions == []


@pytest.mark.anyio
async def test_invite_to_wallet_username_is_email():
    owner_user = await new_user()
    source_wallet = await create_wallet(
        user_id=owner_user.id, wallet_name="source_wallet"
    )
    invited_user = await new_user()
    assert invited_user.email is not None
    # Use email instead of username
    wallet_share = await invite_to_wallet(
        source_wallet=source_wallet,
        data=WalletSharePermission(
            username=invited_user.email,
            wallet_id=source_wallet.id,
            permissions=[WalletPermission.VIEW_PAYMENTS],
            status=WalletShareStatus.INVITE_SENT,
        ),
    )
    assert wallet_share.username == invited_user.email


@pytest.mark.anyio
async def test_invite_to_wallet_sql_injection_username():
    owner_user = await new_user()
    source_wallet = await create_wallet(
        user_id=owner_user.id, wallet_name="source_wallet"
    )
    # Try a SQL injection-like username
    with pytest.raises(ValueError, match="Invited user not found."):
        await invite_to_wallet(
            source_wallet=source_wallet,
            data=WalletSharePermission(
                username="' OR 1=1; --",
                wallet_id=source_wallet.id,
                permissions=[WalletPermission.VIEW_PAYMENTS],
                status=WalletShareStatus.INVITE_SENT,
            ),
        )


@pytest.mark.anyio
async def test_invite_to_wallet_long_username():
    owner_user = await new_user()
    source_wallet = await create_wallet(
        user_id=owner_user.id, wallet_name="source_wallet"
    )
    long_username = "a" * 256
    with pytest.raises(ValueError, match="Invited user not found."):
        await invite_to_wallet(
            source_wallet=source_wallet,
            data=WalletSharePermission(
                username=long_username,
                wallet_id=source_wallet.id,
                permissions=[WalletPermission.VIEW_PAYMENTS],
                status=WalletShareStatus.INVITE_SENT,
            ),
        )


@pytest.mark.anyio
async def test_invite_to_wallet_special_characters_username():
    owner_user = await new_user()
    source_wallet = await create_wallet(
        user_id=owner_user.id, wallet_name="source_wallet"
    )
    special_username = "!@#$%^&*()_+-=[]{}|;':,.<>/?"
    with pytest.raises(ValueError, match="Invited user not found."):
        await invite_to_wallet(
            source_wallet=source_wallet,
            data=WalletSharePermission(
                username=special_username,
                wallet_id=source_wallet.id,
                permissions=[WalletPermission.VIEW_PAYMENTS],
                status=WalletShareStatus.INVITE_SENT,
            ),
        )
