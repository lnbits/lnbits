import pytest

from lnbits.core.crud.users import delete_account, get_account
from lnbits.core.crud.wallets import (
    create_wallet,
    delete_wallet,
    get_wallet,
    get_wallets,
    update_wallet,
)
from lnbits.core.models.users import User
from lnbits.core.models.wallets import (
    Wallet,
    WalletPermission,
    WalletSharePermission,
    WalletShareStatus,
    WalletType,
)
from lnbits.core.services.wallets import (
    create_lightning_shared_wallet,
    delete_wallet_share,
    invite_to_wallet,
    reject_wallet_invitation,
)
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
async def test_two_invites_to_wallet_ok():
    invited_user = await new_user()
    assert invited_user.username is not None
    owner_user_one = await new_user()
    source_wallet_one = await create_wallet(
        user_id=owner_user_one.id, wallet_name="source_wallet_one"
    )

    wallet_share_one = await invite_to_wallet(
        source_wallet=source_wallet_one,
        data=WalletSharePermission(
            username=invited_user.username,
            wallet_id=source_wallet_one.id,
            permissions=[WalletPermission.VIEW_PAYMENTS],
            status=WalletShareStatus.INVITE_SENT,
        ),
    )
    assert wallet_share_one.request_id is not None

    owner_user_two = await new_user()
    source_wallet_two = await create_wallet(
        user_id=owner_user_two.id, wallet_name="source_wallet_two"
    )

    wallet_share_two = await invite_to_wallet(
        source_wallet=source_wallet_two,
        data=WalletSharePermission(
            username=invited_user.username,
            wallet_id=source_wallet_two.id,
            permissions=[
                WalletPermission.VIEW_PAYMENTS,
                WalletPermission.RECEIVE_PAYMENTS,
            ],
            status=WalletShareStatus.INVITE_SENT,
        ),
    )
    assert wallet_share_two.request_id is not None

    invited_user = await get_account(invited_user.id)
    assert invited_user is not None
    assert len(invited_user.extra.wallet_invite_requests) == 2
    invite_request_one = invited_user.extra.find_wallet_invite_request(
        wallet_share_one.request_id
    )
    assert invite_request_one is not None
    assert (
        invite_request_one.from_user_name == owner_user_one.username
        or owner_user_one.email
    )
    assert invite_request_one.to_wallet_id == source_wallet_one.id
    assert invite_request_one.to_wallet_name == source_wallet_one.name
    invite_request_two = invited_user.extra.find_wallet_invite_request(
        wallet_share_two.request_id
    )
    assert invite_request_two is not None
    assert (
        invite_request_two.from_user_name == owner_user_two.username
        or owner_user_two.email
    )
    assert invite_request_two.to_wallet_id == source_wallet_two.id
    assert invite_request_two.to_wallet_name == source_wallet_two.name


@pytest.mark.anyio
async def test_many_invites_and_one_cancel():
    invited_user = await new_user()
    assert invited_user.username is not None
    count = 10
    _, source_wallets = await _create_invitations_for_user(invited_user, count)

    invited_user = await get_account(invited_user.id)
    assert invited_user is not None
    assert len(invited_user.extra.wallet_invite_requests) == count

    mid_index = count // 2
    mid_wallet = source_wallets[mid_index]
    share = mid_wallet.extra.find_share_for_wallet(mid_wallet.id)
    assert share is not None
    assert invited_user.extra.find_wallet_invite_request(share.request_id) is not None
    await delete_wallet_share(mid_wallet, share.request_id)

    invited_user = await get_account(invited_user.id)
    assert invited_user is not None
    assert len(invited_user.extra.wallet_invite_requests) == count - 1
    assert invited_user.extra.find_wallet_invite_request(share.request_id) is None


@pytest.mark.anyio
async def test_many_invites_and_one_reject():
    invited_user = await new_user()
    assert invited_user.username is not None
    count = 10
    _, source_wallets = await _create_invitations_for_user(invited_user, count)

    invited_user = await get_account(invited_user.id)
    assert invited_user is not None

    mid_wallet = source_wallets[count // 2]
    share = mid_wallet.extra.find_share_for_wallet(mid_wallet.id)
    assert share is not None
    assert invited_user.extra.find_wallet_invite_request(share.request_id) is not None
    await reject_wallet_invitation(invited_user.id, share.request_id)

    invited_user = await get_account(invited_user.id)
    assert invited_user is not None
    assert len(invited_user.extra.wallet_invite_requests) == count - 1
    assert invited_user.extra.find_wallet_invite_request(share.request_id) is None


@pytest.mark.anyio
async def test_many_invites_and_one_accept():
    invited_user = await new_user()
    assert invited_user.username is not None
    count = 10
    _, source_wallets = await _create_invitations_for_user(invited_user, count)

    invited_user = await get_account(invited_user.id)
    assert invited_user is not None

    mid_wallet = source_wallets[count // 2]
    share = mid_wallet.extra.find_share_for_wallet(mid_wallet.id)
    assert share is not None
    await create_lightning_shared_wallet(invited_user.id, mid_wallet.id)

    invited_user = await get_account(invited_user.id)

    assert invited_user is not None
    invited_user_wallets = await get_wallets(invited_user.id)
    assert len(invited_user_wallets) == 2
    shared_wallet = next(
        (w for w in invited_user_wallets if w.shared_wallet_id == mid_wallet.id), None
    )
    assert shared_wallet is not None
    assert shared_wallet.is_lightning_shared_wallet
    assert shared_wallet.shared_wallet_id == mid_wallet.id
    assert len(invited_user.extra.wallet_invite_requests) == count - 1
    assert invited_user.extra.find_wallet_invite_request(share.request_id) is None


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


@pytest.mark.anyio
async def test_invite_to_wallet_no_username():
    owner_user = await new_user()
    source_wallet = await create_wallet(
        user_id=owner_user.id, wallet_name="source_wallet"
    )
    special_username = ""
    with pytest.raises(ValueError, match="Username or email missing."):
        await invite_to_wallet(
            source_wallet=source_wallet,
            data=WalletSharePermission(
                username=special_username,
                wallet_id=source_wallet.id,
                permissions=[WalletPermission.VIEW_PAYMENTS],
                status=WalletShareStatus.INVITE_SENT,
            ),
        )


@pytest.mark.anyio
async def test_reject_wallet_invitation_user_not_found():
    with pytest.raises(ValueError, match="Invited user not found."):
        await reject_wallet_invitation("non_existent_user_id", "some_request_id")


@pytest.mark.anyio
async def test_reject_wallet_invitation_not_found():
    invited_user = await new_user()
    with pytest.raises(ValueError, match="Invitation not found."):
        await reject_wallet_invitation(invited_user.id, "non_existent_request_id")


@pytest.mark.anyio
async def test_delete_wallet_share_bad_wallet_type():
    shared_wallet = await _create_shared_wallet_for_user(await new_user())
    with pytest.raises(ValueError, match="Source wallet is not a lightning wallet."):
        await delete_wallet_share(shared_wallet, "some_request_id")


@pytest.mark.anyio
async def test_delete_wallet_share_not_found(to_wallet: Wallet):
    with pytest.raises(ValueError, match="Wallet share not found."):
        await delete_wallet_share(to_wallet, "non_existent_request_id")


@pytest.mark.anyio
async def test_delete_wallet_share_invited_user_not_found():
    invited_user = await new_user()
    shared_wallet = await _create_shared_wallet_for_user(invited_user)
    assert shared_wallet.shared_wallet_id is not None
    source_wallet = await get_wallet(shared_wallet.shared_wallet_id)
    assert source_wallet is not None
    request_id = source_wallet.extra.shared_with[0].request_id
    assert request_id is not None
    await delete_account(invited_user.id)
    resp = await delete_wallet_share(source_wallet, request_id)

    assert resp.success
    assert resp.message == "Permission removed. Invited user not found."

    source_wallet = await get_wallet(shared_wallet.shared_wallet_id)
    assert source_wallet is not None
    assert source_wallet.extra.find_share_by_id(request_id) is None


@pytest.mark.anyio
async def test_delete_wallet_share_target_wallet_not_found():
    invited_user = await new_user()
    shared_wallet = await _create_shared_wallet_for_user(invited_user)
    assert shared_wallet.shared_wallet_id is not None
    source_wallet = await get_wallet(shared_wallet.shared_wallet_id)
    assert source_wallet is not None
    request_id = source_wallet.extra.shared_with[0].request_id
    assert request_id is not None
    await delete_wallet(user_id=invited_user.id, wallet_id=shared_wallet.id)
    resp = await delete_wallet_share(source_wallet, request_id)

    assert resp.success
    assert resp.message == "Permission removed. Target wallet not found."

    source_wallet = await get_wallet(shared_wallet.shared_wallet_id)
    assert source_wallet is not None
    assert source_wallet.extra.find_share_by_id(request_id) is None


@pytest.mark.anyio
async def test_delete_wallet_share_ok():
    invited_user = await new_user()
    shared_wallet = await _create_shared_wallet_for_user(invited_user)
    assert shared_wallet.shared_wallet_id is not None
    source_wallet = await get_wallet(shared_wallet.shared_wallet_id)
    assert source_wallet is not None
    request_id = source_wallet.extra.shared_with[0].request_id
    assert request_id is not None
    resp = await delete_wallet_share(source_wallet, request_id)

    assert resp.success
    assert resp.message == "Permission removed."

    source_wallet = await get_wallet(shared_wallet.shared_wallet_id)
    assert source_wallet is not None
    assert source_wallet.extra.find_share_by_id(request_id) is None
    assert len(source_wallet.extra.shared_with) == 0

    shared_wallet = await get_wallet(shared_wallet.id)
    assert shared_wallet is None


async def _create_invitations_for_user(invited_user, count):
    owner_users, source_wallets = [], []
    for i in range(count):
        owner_user = await new_user()
        source_wallet = await create_wallet(
            user_id=owner_user.id, wallet_name=f"source_wallet_{i}"
        )

        await invite_to_wallet(
            source_wallet=source_wallet,
            data=WalletSharePermission(
                username=invited_user.username,
                wallet_id=source_wallet.id,
                permissions=[WalletPermission.VIEW_PAYMENTS],
                status=WalletShareStatus.INVITE_SENT,
            ),
        )
        owner_users.append(owner_user)
        source_wallets.append(source_wallet)
    return owner_users, source_wallets


async def _create_shared_wallet_for_user(invited_user: User) -> Wallet:
    assert invited_user.username is not None
    owner_user = await new_user()
    source_wallet = await create_wallet(
        user_id=owner_user.id, wallet_name="source_wallet"
    )

    await invite_to_wallet(
        source_wallet=source_wallet,
        data=WalletSharePermission(
            username=invited_user.username,
            wallet_id=source_wallet.id,
            permissions=[WalletPermission.VIEW_PAYMENTS],
            status=WalletShareStatus.INVITE_SENT,
        ),
    )

    shared_wallet = await create_lightning_shared_wallet(
        user_id=invited_user.id, shared_wallet_id=source_wallet.id
    )
    return shared_wallet
