from uuid import uuid4

import pytest

from lnbits.core.crud.users import get_user_from_account
from lnbits.core.crud.wallets import delete_wallet, get_wallets
from lnbits.core.models.users import Account
from lnbits.core.services.users import create_user_account


@pytest.mark.anyio
async def test_get_user_from_account_is_wallet_created():

    username = f"user_{uuid4().hex[:8]}"
    account = Account(
        id=uuid4().hex,
        username=username,
        email=f"{username}@lnbits.com",
    )
    account.hash_password("secret1234")
    user = await create_user_account(account)

    assert user is not None
    assert (
        len(user.wallets) == 1
    ), "A wallet should be created for the user if none exist"

    await delete_wallet(user_id=account.id, wallet_id=user.wallets[0].id)

    wallets = await get_wallets(account.id, deleted=False)
    assert len(wallets) == 0, "User should have no wallets after deletion"

    user = await get_user_from_account(account)

    assert user is not None
    assert (
        len(user.wallets) == 1
    ), "A new wallet should be created for the user if none exist after deletion"
