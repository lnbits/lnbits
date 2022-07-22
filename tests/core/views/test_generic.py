import pytest
import pytest_asyncio
from tests.conftest import client


@pytest.mark.asyncio
async def test_core_views_generic(client):
    response = await client.get("/")
    assert response.status_code == 200


# check GET /wallet: wallet info
@pytest.mark.asyncio
async def test_get_wallet(client):
    response = await client.get("wallet")
    assert response.status_code == 200


# check GET /wallet: do not allow redirects, expect code 307
@pytest.mark.asyncio
async def test_get_wallet_no_redirect(client):
    response = await client.get("wallet", allow_redirects=False)
    assert response.status_code == 307


# check GET /wallet: wrong user, expect 204
@pytest.mark.asyncio
async def test_get_wallet_with_nonexistent_user(client):
    response = await client.get("wallet", params={"usr": "1"})
    print(response.url)
    assert response.status_code == 204


# check GET /wallet: with user
@pytest.mark.asyncio
async def test_get_wallet_with_user(client, to_user):
    response = await client.get("wallet", params={"usr": to_user.id})
    print(response.url)
    assert response.status_code == 200


# check GET /wallet: wallet and user
@pytest.mark.asyncio
async def test_get_wallet_with_user_and_wallet(client, to_user, to_wallet):
    response = await client.get(
        "wallet", params={"usr": to_user.id, "wal": to_wallet.id}
    )
    print(response.url)
    assert response.status_code == 200

    # check GET /wallet: wrong wallet and user, expect 204


@pytest.mark.asyncio
async def test_get_wallet_with_user_and_wrong_wallet(client, to_user, to_wallet):
    response = await client.get("wallet", params={"usr": to_user.id, "wal": "1"})
    print(response.url)
    assert response.status_code == 204
