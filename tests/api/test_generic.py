import pytest


@pytest.mark.asyncio
async def test_core_views_generic(client):
    response = await client.get("/")
    assert response.status_code == 200, f"{response.url} {response.status_code}"


# check GET /wallet: wrong user, expect 400
@pytest.mark.asyncio
async def test_get_wallet_with_nonexistent_user(client):
    response = await client.get("wallet", params={"usr": "1"})
    assert response.status_code == 400, f"{response.url} {response.status_code}"


# check GET /wallet: wallet and user
@pytest.mark.asyncio
async def test_get_wallet_with_user_and_wallet(client, to_user, to_wallet):
    response = await client.get(
        "wallet", params={"usr": to_user.id, "wal": to_wallet.id}
    )
    assert response.status_code == 200, f"{response.url} {response.status_code}"


# check GET /wallet: wrong wallet and user, expect 400
@pytest.mark.asyncio
async def test_get_wallet_with_user_and_wrong_wallet(client, to_user):
    response = await client.get("wallet", params={"usr": to_user.id, "wal": "1"})
    assert response.status_code == 400, f"{response.url} {response.status_code}"


# check GET /extensions: extensions list
@pytest.mark.asyncio
async def test_get_extensions(client, to_user):
    response = await client.get("extensions", params={"usr": to_user.id})
    assert response.status_code == 200, f"{response.url} {response.status_code}"


# check GET /extensions: extensions list wrong user, expect 400
@pytest.mark.asyncio
async def test_get_extensions_wrong_user(client):
    response = await client.get("extensions", params={"usr": "1"})
    assert response.status_code == 400, f"{response.url} {response.status_code}"


# check GET /extensions: no user given, expect code 400 bad request
@pytest.mark.asyncio
async def test_get_extensions_no_user(client):
    response = await client.get("extensions")
    # bad request
    assert response.status_code == 401, f"{response.url} {response.status_code}"


# check GET /extensions: enable extension
# TODO: test fails because of removing lnurlp extension
# @pytest.mark.asyncio
# async def test_get_extensions_enable(client, to_user):
#     response = await client.get(
#         "extensions", params={"usr": to_user.id, "enable": "lnurlp"}
#     )
#     assert response.status_code == 200, f"{response.url} {response.status_code}"


# check GET /extensions: enable and disable extensions, expect code 400 bad request
# @pytest.mark.asyncio
# async def test_get_extensions_enable_and_disable(client, to_user):
#     response = await client.get(
#         "extensions",
#         params={"usr": to_user.id, "enable": "lnurlp", "disable": "lnurlp"},
#     )
#     assert response.status_code == 400, f"{response.url} {response.status_code}"


# check GET /extensions: enable nonexistent extension, expect code 400 bad request
@pytest.mark.asyncio
async def test_get_extensions_enable_nonexistent_extension(client, to_user):
    response = await client.get(
        "extensions", params={"usr": to_user.id, "enable": "12341234"}
    )
    assert response.status_code == 400, f"{response.url} {response.status_code}"
