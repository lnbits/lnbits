import pytest

from lnbits.core.crud.payments import get_payments
from lnbits.core.crud.users import delete_account, get_account
from lnbits.core.crud.wallets import (
    create_wallet,
    delete_wallet,
    get_wallet,
    get_wallets,
    update_wallet,
)
from lnbits.core.models.payments import PaymentFilters
from lnbits.core.models.users import User
from lnbits.core.models.wallets import (
    Wallet,
    WalletPermission,
    WalletSharePermission,
    WalletShareStatus,
    WalletType,
)
from lnbits.core.services.payments import (
    create_invoice,
    pay_invoice,
    update_wallet_balance,
)
from lnbits.core.services.wallets import (
    create_lightning_shared_wallet,
    delete_wallet_share,
    invite_to_wallet,
    reject_wallet_invitation,
    update_wallet_share_permissions,
)
from lnbits.db import Filters
from lnbits.exceptions import InvoiceError, PaymentError
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
            permissions=[WalletPermission.VIEW_PAYMENTS],
            status=WalletShareStatus.INVITE_SENT,
        ),
    )
    assert wallet_share.status == WalletShareStatus.INVITE_SENT

    source_wallet = await get_wallet(source_wallet.id)
    assert source_wallet is not None
    share = source_wallet.extra.shared_with[0]
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
            permissions=[WalletPermission.VIEW_PAYMENTS],
            status=WalletShareStatus.INVITE_SENT,
        ),
    )

    with pytest.raises(ValueError, match="User already invited to this wallet."):
        await invite_to_wallet(
            source_wallet=source_wallet,
            data=WalletSharePermission(
                username=invited_user.username,
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
    source_wallets = await _create_invitations_for_user(invited_user, count)

    invited_user = await get_account(invited_user.id)
    assert invited_user is not None
    assert len(invited_user.extra.wallet_invite_requests) == count

    mid_index = count // 2
    mid_wallet = source_wallets[mid_index]
    share = mid_wallet.extra.shared_with[0]
    assert share is not None
    assert share.request_id is not None
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
    source_wallets = await _create_invitations_for_user(invited_user, count)

    invited_user = await get_account(invited_user.id)
    assert invited_user is not None

    mid_wallet = source_wallets[count // 2]
    share = mid_wallet.extra.shared_with[0]
    assert share is not None
    assert share.request_id is not None
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
    source_wallets = await _create_invitations_for_user(invited_user, count)

    invited_user = await get_account(invited_user.id)
    assert invited_user is not None

    mid_wallet = source_wallets[count // 2]
    share = mid_wallet.extra.shared_with[0]
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
    assert share.request_id is not None
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


@pytest.mark.anyio
async def test_create_lightning_shared_wallet_ok():
    invited_user = await new_user()
    assert invited_user.username is not None
    owner_user = await new_user()
    source_wallet = await create_wallet(
        user_id=owner_user.id, wallet_name="source_wallet"
    )

    await invite_to_wallet(
        source_wallet=source_wallet,
        data=WalletSharePermission(
            username=invited_user.username,
            permissions=[WalletPermission.RECEIVE_PAYMENTS],
            status=WalletShareStatus.INVITE_SENT,
        ),
    )

    invited_user = await get_account(invited_user.id)
    assert invited_user is not None
    assert len(invited_user.extra.wallet_invite_requests) == 1

    mirror_wallet = await create_lightning_shared_wallet(
        user_id=invited_user.id, source_wallet_id=source_wallet.id
    )

    assert mirror_wallet is not None
    assert mirror_wallet.is_lightning_shared_wallet
    assert mirror_wallet.shared_wallet_id == source_wallet.id
    assert mirror_wallet.can_receive_payments is True
    assert mirror_wallet.can_view_payments is False
    assert mirror_wallet.can_send_payments is False

    source_wallet = await get_wallet(source_wallet.id)
    assert source_wallet is not None
    share = source_wallet.extra.find_share_for_wallet(mirror_wallet.id)
    assert share is not None
    assert share.status == WalletShareStatus.APPROVED
    assert share.permissions == [WalletPermission.RECEIVE_PAYMENTS]

    invited_user = await get_account(invited_user.id)
    assert invited_user is not None
    assert len(invited_user.extra.wallet_invite_requests) == 0

    with pytest.raises(ValueError, match="This wallet is already shared with you."):
        mirror_wallet = await create_lightning_shared_wallet(
            user_id=invited_user.id, source_wallet_id=source_wallet.id
        )


@pytest.mark.anyio
async def test_shared_wallet_view_permissions(from_wallet: Wallet):
    invited_user = await new_user()
    mirror_wallet: Wallet | None = await _create_shared_wallet_for_user(invited_user)
    assert mirror_wallet is not None
    assert mirror_wallet.shared_wallet_id is not None

    assert mirror_wallet.can_view_payments is True
    assert mirror_wallet.can_send_payments is False
    assert mirror_wallet.can_receive_payments is False

    shared_wallet_payments = await get_payments(wallet_id=mirror_wallet.id)
    assert len(shared_wallet_payments) == 0

    payment_count = 11
    wallet_balance = 0

    for i in range(payment_count):
        payment = await create_invoice(
            wallet_id=mirror_wallet.shared_wallet_id,
            amount=1000 + i * 100,
            memo=f"Test invoice {i}",
        )
        await pay_invoice(wallet_id=from_wallet.id, payment_request=payment.bolt11)
        wallet_balance += payment.sat

    filters = Filters(limit=100, model=PaymentFilters)
    shared_wallet_payments = await get_payments(
        wallet_id=mirror_wallet.id, filters=filters
    )
    assert len(shared_wallet_payments) == payment_count
    mirror_wallet = await get_wallet(mirror_wallet.id)
    assert mirror_wallet is not None
    assert mirror_wallet.shared_wallet_id is not None
    assert mirror_wallet.balance == wallet_balance

    source_wallet = await get_wallet(mirror_wallet.shared_wallet_id)
    assert source_wallet is not None
    assert source_wallet.balance == wallet_balance

    with pytest.raises(
        InvoiceError, match="Wallet does not have permission to create invoices."
    ):
        await create_invoice(
            wallet_id=mirror_wallet.id,
            amount=1000,
            memo="Test invoice with no permissions",
        )

    payment = await create_invoice(
        wallet_id=from_wallet.id,
        amount=1000,
        memo="Test invoice for payment",
    )
    with pytest.raises(
        PaymentError, match="Wallet does not have permission to pay invoices."
    ):
        await pay_invoice(wallet_id=mirror_wallet.id, payment_request=payment.bolt11)


@pytest.mark.anyio
async def test_shared_wallet_no_permissions(from_wallet: Wallet):
    invited_user = await new_user()
    mirror_wallet: Wallet | None = await _create_shared_wallet_for_user(invited_user)
    assert mirror_wallet is not None
    assert mirror_wallet.shared_wallet_id is not None
    source_wallet = await get_wallet(mirror_wallet.shared_wallet_id)
    assert source_wallet is not None

    share = source_wallet.extra.find_share_for_wallet(mirror_wallet.id)
    assert share is not None
    share.permissions = []
    await update_wallet_share_permissions(source_wallet, share)

    shared_wallet_payments = await get_payments(wallet_id=mirror_wallet.id)
    assert len(shared_wallet_payments) == 0
    mirror_wallet = await get_wallet(mirror_wallet.id)
    assert mirror_wallet is not None
    assert mirror_wallet.balance == 0

    payment = await create_invoice(
        wallet_id=from_wallet.id,
        amount=1000,
        memo="Test invoice",
    )

    with pytest.raises(
        InvoiceError, match="Wallet does not have permission to create invoices."
    ):
        await create_invoice(
            wallet_id=mirror_wallet.id,
            amount=1000,
            memo="Test invoice with no permissions",
        )

    with pytest.raises(
        PaymentError, match="Wallet does not have permission to pay invoices."
    ):
        await pay_invoice(wallet_id=mirror_wallet.id, payment_request=payment.bolt11)


@pytest.mark.anyio
async def test_shared_wallet_receive_permission(from_wallet: Wallet):
    invited_user = await new_user()
    mirror_wallet: Wallet | None = await _create_shared_wallet_for_user(invited_user)
    assert mirror_wallet is not None
    assert mirror_wallet.shared_wallet_id is not None
    source_wallet = await get_wallet(mirror_wallet.shared_wallet_id)
    assert source_wallet is not None

    share = source_wallet.extra.find_share_for_wallet(mirror_wallet.id)
    assert share is not None
    share.permissions = [WalletPermission.RECEIVE_PAYMENTS]
    await update_wallet_share_permissions(source_wallet, share)
    shared_wallet_payments = await get_payments(wallet_id=mirror_wallet.id)
    # cannot view payments
    assert len(shared_wallet_payments) == 0
    mirror_wallet = await get_wallet(mirror_wallet.id)
    assert mirror_wallet is not None
    assert mirror_wallet.balance == 0
    # ok to create invoice
    await create_invoice(
        wallet_id=mirror_wallet.id,
        amount=1000,
        memo="Test invoice with no permissions",
    )

    payment = await create_invoice(
        wallet_id=from_wallet.id,
        amount=1000,
        memo="Test invoice",
    )
    # but not to pay
    await update_wallet_balance(mirror_wallet, 100000)
    with pytest.raises(
        PaymentError, match="Wallet does not have permission to pay invoices."
    ):
        await pay_invoice(wallet_id=mirror_wallet.id, payment_request=payment.bolt11)

    shared_wallet_payments = await get_payments(wallet_id=mirror_wallet.id)
    assert len(shared_wallet_payments) == 0
    mirror_wallet = await get_wallet(mirror_wallet.id)
    assert mirror_wallet is not None
    assert mirror_wallet.balance == 100000

    share = source_wallet.extra.find_share_for_wallet(mirror_wallet.id)
    assert share is not None
    share.permissions.append(WalletPermission.VIEW_PAYMENTS)
    await update_wallet_share_permissions(source_wallet, share)
    shared_wallet_payments = await get_payments(wallet_id=mirror_wallet.id)
    assert len(shared_wallet_payments) == 2

    # check that paying is still not allowed after adding view permission
    with pytest.raises(
        PaymentError, match="Wallet does not have permission to pay invoices."
    ):
        await pay_invoice(wallet_id=mirror_wallet.id, payment_request=payment.bolt11)


@pytest.mark.anyio
async def test_shared_wallet_send_permission(from_wallet: Wallet):
    invited_user = await new_user()
    mirror_wallet: Wallet | None = await _create_shared_wallet_for_user(invited_user)
    assert mirror_wallet is not None
    assert mirror_wallet.shared_wallet_id is not None
    source_wallet = await get_wallet(mirror_wallet.shared_wallet_id)
    assert source_wallet is not None

    share = source_wallet.extra.find_share_for_wallet(mirror_wallet.id)
    assert share is not None
    share.permissions = [WalletPermission.SEND_PAYMENTS]
    await update_wallet_share_permissions(source_wallet, share)
    shared_wallet_payments = await get_payments(wallet_id=mirror_wallet.id)
    assert len(shared_wallet_payments) == 0
    mirror_wallet = await get_wallet(mirror_wallet.id)
    assert mirror_wallet is not None
    assert mirror_wallet.balance == 0
    # cannot create invoice
    with pytest.raises(
        InvoiceError, match="Wallet does not have permission to create invoices."
    ):
        await create_invoice(
            wallet_id=mirror_wallet.id,
            amount=1000,
            memo="Test invoice with no permissions",
        )

    # but can pay invoice
    payment = await create_invoice(
        wallet_id=from_wallet.id,
        amount=1000,
        memo="Test invoice",
    )
    await update_wallet_balance(mirror_wallet, 100000)
    await pay_invoice(wallet_id=mirror_wallet.id, payment_request=payment.bolt11)

    share = source_wallet.extra.find_share_for_wallet(mirror_wallet.id)
    assert share is not None
    share.permissions.append(WalletPermission.VIEW_PAYMENTS)
    await update_wallet_share_permissions(source_wallet, share)
    shared_wallet_payments = await get_payments(wallet_id=mirror_wallet.id)
    assert len(shared_wallet_payments) == 2

    # check that creating invoice is still not allowed after adding view permission
    with pytest.raises(
        InvoiceError, match="Wallet does not have permission to create invoices."
    ):
        await create_invoice(
            wallet_id=mirror_wallet.id,
            amount=1000,
            memo="Test invoice with no permissions",
        )


@pytest.mark.anyio
async def test_create_lightning_shared_wallet_missing_source():
    invited_user = await new_user()
    with pytest.raises(ValueError, match="Shared wallet does not exist."):
        await create_lightning_shared_wallet(
            invited_user.id, "non_existent_source_wallet_id"
        )


@pytest.mark.anyio
async def test_create_lightning_shared_wallet_bad_type():
    invited_user = await new_user()
    shared_wallet = await _create_shared_wallet_for_user(invited_user)
    with pytest.raises(ValueError, match="Shared wallet is not a lightning wallet."):
        await create_lightning_shared_wallet(invited_user.id, shared_wallet.id)


@pytest.mark.anyio
async def test_create_lightning_shared_wallet_self_mirror(to_wallet: Wallet):
    with pytest.raises(ValueError, match="Cannot mirror your own wallet."):
        await create_lightning_shared_wallet(to_wallet.user, to_wallet.id)


@pytest.mark.anyio
async def test_create_lightning_shared_wallet_missing_invitation(to_wallet: Wallet):
    with pytest.raises(ValueError, match="Cannot find invited user."):
        await create_lightning_shared_wallet("non_existing_user", to_wallet.id)


@pytest.mark.anyio
async def test_create_lightning_shared_wallet_missing_user(to_wallet: Wallet):
    invited_user = await new_user()
    with pytest.raises(ValueError, match="No invitation found for this invited user."):
        await create_lightning_shared_wallet(invited_user.id, to_wallet.id)


async def _create_invitations_for_user(invited_user, count) -> list[Wallet]:
    source_wallets = []
    for i in range(count):
        owner_user = await new_user()
        source_wallet = await create_wallet(
            user_id=owner_user.id, wallet_name=f"source_wallet_{i}"
        )

        await invite_to_wallet(
            source_wallet=source_wallet,
            data=WalletSharePermission(
                username=invited_user.username,
                permissions=[WalletPermission.VIEW_PAYMENTS],
                status=WalletShareStatus.INVITE_SENT,
            ),
        )
        source_wallets.append(source_wallet)
    return source_wallets


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
            permissions=[WalletPermission.VIEW_PAYMENTS],
            status=WalletShareStatus.INVITE_SENT,
        ),
    )

    shared_wallet = await create_lightning_shared_wallet(
        user_id=invited_user.id, source_wallet_id=source_wallet.id
    )
    return shared_wallet
