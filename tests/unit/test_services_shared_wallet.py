import pytest

from lnbits.core.crud.users import get_account
from lnbits.core.crud.wallets import create_wallet, get_wallet
from lnbits.core.models.wallets import (
    WalletPermission,
    WalletSharePermission,
    WalletShareStatus,
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
