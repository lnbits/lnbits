import asyncio
from time import time
from uuid import uuid4

import pytest

from lnbits.core.crud.users import (
    consume_password_reset,
    create_account,
    get_account,
    get_password_reset_account,
    store_password_reset,
    update_account,
)
from lnbits.core.db import db
from lnbits.core.models.users import Account
from lnbits.db import Connection

pytestmark = pytest.mark.anyio


async def test_password_reset_atomic_across_connections(app):
    account = await create_account(Account(id=uuid4().hex, password_hash="original"))
    now = int(time())
    assert await store_password_reset(account.id, "token-hash", now, now + 120)

    async def attempt(password_hash: str) -> bool:
        changed = account.copy(update={"password_hash": password_hash})
        # Independent connections bypass the Database's process-local lock.
        async with db.engine.connect() as connection:
            assert connection is not None
            conn = Connection(connection, db.type, db.name, db.schema)
            return await consume_password_reset(changed, "token-hash", 120, conn)

    results = await asyncio.gather(attempt("first"), attempt("second"))
    assert sorted(results) == [False, True]
    saved = await get_account(account.id)
    assert saved and saved.password_hash == ("first" if results[0] else "second")
    assert await get_password_reset_account("token-hash") is None


@pytest.mark.parametrize("has_password", [False, True])
@pytest.mark.parametrize("reuse_connection", [False, True])
async def test_reset_survives_profile_update_but_not_password_change(
    app, has_password: bool, reuse_connection: bool
):
    account = await create_account(
        Account(id=uuid4().hex, password_hash="original" if has_password else None)
    )
    now = int(time())
    token_hash = uuid4().hex
    assert await store_password_reset(account.id, token_hash, now, now + 120)
    account.extra.display_name = "<Updated name>'; DROP TABLE accounts; --"
    account.ui_customization = {"text": "':password_hash &amp; <b>bound value</b>"}
    if reuse_connection:
        async with db.connect() as conn:
            await update_account(account, conn)
    else:
        await update_account(account)
    saved = await get_account(account.id)
    assert saved and saved.extra == account.extra
    assert saved.ui_customization == account.ui_customization
    assert saved.created_at == account.created_at
    assert await get_password_reset_account(token_hash)
    stale = account.copy(deep=True)
    account.password_hash = "changed"
    if reuse_connection:
        async with db.connect() as conn:
            await update_account(account, conn)
    else:
        await update_account(account)
    assert await get_password_reset_account(token_hash) is None
    assert not await consume_password_reset(account, token_hash, 120)
    await update_account(stale)
    assert await get_password_reset_account(token_hash) is None


async def test_reset_rechecks_expiry_and_replacement_at_consumption(app):
    account = await create_account(Account(id=uuid4().hex))
    now = int(time())
    token_hash = uuid4().hex
    assert await store_password_reset(account.id, token_hash, now, now + 3600)
    fetched = await get_password_reset_account(token_hash)
    assert fetched
    fetched.password_hash = "changed"
    await db.execute(
        "UPDATE accounts SET password_reset_expires_at = :now WHERE id = :id",
        {"id": account.id, "now": now},
    )
    assert not await consume_password_reset(fetched, token_hash, 3600)

    assert await store_password_reset(account.id, token_hash, now, now + 3600)
    assert await store_password_reset(account.id, "replacement", now, now + 3600)
    assert not await consume_password_reset(fetched, token_hash, 3600)
    assert await get_password_reset_account("replacement")


async def test_admin_reset_age_is_capped_at_consumption(app):
    account = await create_account(Account(id=uuid4().hex))
    now = int(time())
    token_hash = uuid4().hex
    assert await store_password_reset(account.id, token_hash, now - 120, now + 3600)
    account.password_hash = "changed"
    assert not await consume_password_reset(account, token_hash, 120)
    assert await consume_password_reset(account, token_hash, 3600)
