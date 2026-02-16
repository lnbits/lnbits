from uuid import uuid4

import pytest

from lnbits.core.crud.users import (
    create_account,
    delete_account,
    get_accounts,
    get_user_from_account,
)
from lnbits.core.crud.wallets import delete_wallet, force_delete_wallet, get_wallets
from lnbits.core.models.users import Account, AccountFilters
from lnbits.core.services.users import create_user_account, create_user_account_no_ckeck
from lnbits.db import Filter, Filters, Operator


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


@pytest.mark.anyio
async def test_get_accounts_success_flow():
    # Create a new account
    username = f"user_{uuid4().hex[:8]}"
    account = Account(
        id=uuid4().hex,
        username=username,
        email=f"{username}@lnbits.com",
    )
    await create_account(account)
    # Should return the created account
    filters = Filters[AccountFilters](filters=[], model=AccountFilters)
    filters.sortby = "created_at"
    filters.direction = "desc"
    page = await get_accounts(filters=filters)
    assert page.total >= 1
    found = any(a.username == username for a in page.data)
    assert found
    await delete_account(account.id)


@pytest.mark.anyio
async def test_get_accounts_with_wallet_id_filter():
    # Create account and wallet
    username = f"user_{uuid4().hex[:8]}"
    account = Account(
        id=uuid4().hex,
        username=username,
        email=f"{username}@lnbits.com",
    )
    await create_user_account_no_ckeck(account)

    wallets = await get_wallets(account.id, deleted=False)
    assert wallets
    wallet = wallets[0]
    # Filter by wallet_id
    filters = Filters[AccountFilters](
        filters=[
            Filter(
                field="wallet_id",
                op=Operator.EQ,
                model=AccountFilters,
                values={"wallet_id__0": wallet.id},
            )
        ],
        model=AccountFilters,
    )
    page = await get_accounts(filters=filters)
    assert page.total == 1
    assert page.data[0].id == account.id
    await delete_account(account.id)


@pytest.mark.anyio
async def test_get_accounts_wallet_id_not_found():

    filters = Filters[AccountFilters](
        filters=[
            Filter(
                field="wallet_id",
                op=Operator.EQ,
                model=AccountFilters,
                values={"wallet_id__0": uuid4().hex},
            )
        ],
        model=AccountFilters,
    )
    page = await get_accounts(filters=filters)
    assert page.total == 0
    assert page.data == []


@pytest.mark.anyio
async def test_get_accounts_empty_filters():
    # Should not raise, should return a Page
    page = await get_accounts()
    assert hasattr(page, "data")
    assert hasattr(page, "total")


@pytest.mark.anyio
async def test_get_accounts_invalid_wallet_id_type():
    # Pass an invalid wallet_id type (int instead of str)

    filters = Filters[AccountFilters](
        filters=[
            Filter(
                field="wallet_id",
                op=Operator.EQ,
                model=AccountFilters,
                values={"wallet_id__0": 12345},
            )
        ],
        model=AccountFilters,
    )
    # Should not raise, just return empty
    page = await get_accounts(filters=filters)
    assert page.total == 0
    assert page.data == []


@pytest.mark.anyio
async def test_get_accounts_with_deleted_wallet():
    # Create account and wallet, then delete wallet
    username = f"user_{uuid4().hex[:8]}"
    account = Account(
        id=uuid4().hex,
        username=username,
        email=f"{username}@lnbits.com",
    )
    await create_user_account_no_ckeck(account)

    wallets = await get_wallets(account.id, deleted=False)
    assert wallets
    wallet = wallets[0]
    await delete_wallet(user_id=account.id, wallet_id=wallet.id)

    filters = Filters[AccountFilters](
        filters=[
            Filter(
                field="wallet_id",
                op=Operator.EQ,
                model=AccountFilters,
                values={"wallet_id__0": wallet.id},
            )
        ],
        model=AccountFilters,
    )
    page = await get_accounts(filters=filters)
    assert page.total == 1
    assert page.data[0].id == account.id

    await force_delete_wallet(wallet_id=wallet.id)

    filters = Filters[AccountFilters](
        filters=[
            Filter(
                field="wallet_id",
                op=Operator.EQ,
                model=AccountFilters,
                values={"wallet_id__0": wallet.id},
            )
        ],
        model=AccountFilters,
    )
    page = await get_accounts(filters=filters)
    assert page.total == 0
    assert page.data == []


@pytest.mark.anyio
async def test_get_accounts_group_by_and_pagination():
    # Create multiple accounts
    accounts = []
    for _ in range(3):
        username = f"user_{uuid4().hex[:8]}"
        account = Account(
            id=uuid4().hex,
            username=username,
            email=f"{username}@lnbits.com",
        )
        await create_user_account_no_ckeck(account)
        accounts.append(account)
    filters = Filters[AccountFilters](model=AccountFilters, limit=2, offset=0)
    page = await get_accounts(filters=filters)
    assert page.total >= 3
    assert len(page.data) <= 2
