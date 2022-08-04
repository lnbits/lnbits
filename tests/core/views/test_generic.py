import pytest
import pytest_asyncio

from tests.conftest import client


@pytest.mark.asyncio
async def test_core_views_generic(client):
    response = await client.get("/")
    assert response.status_code == 200, (
        str(response.url) + " " + str(response.status_code)
    )


# check GET /wallet: wallet info
@pytest.mark.asyncio
async def test_get_wallet(client):
    response = await client.get("wallet")
    assert response.status_code == 307, (  # redirect not modified
        str(response.url) + " " + str(response.status_code)
    )


# check GET /wallet: do not allow redirects, expect code 307
@pytest.mark.asyncio
async def test_get_wallet_no_redirect(client):
    response = await client.get("wallet", follow_redirects=False)
    assert response.status_code == 307, (
        str(response.url) + " " + str(response.status_code)
    )

    # determine the next redirect location
    request = client.build_request("GET", "wallet")
    i = 0
    while request is not None:
        response = await client.send(request)
        request = response.next_request
        if i == 0:
            assert response.status_code == 307, (  # first redirect
                str(response.url) + " " + str(response.status_code)
            )
        elif i == 1:
            assert response.status_code == 200, (  # then get the actual page
                str(response.url) + " " + str(response.status_code)
            )
        i += 1


# check GET /wallet: wrong user, expect 204
@pytest.mark.asyncio
async def test_get_wallet_with_nonexistent_user(client):
    response = await client.get("wallet", params={"usr": "1"})
    assert response.status_code == 204, (
        str(response.url) + " " + str(response.status_code)
    )


# check GET /wallet: with user
@pytest.mark.asyncio
async def test_get_wallet_with_user(client, to_user):
    response = await client.get("wallet", params={"usr": to_user.id})
    assert response.status_code == 307, (
        str(response.url) + " " + str(response.status_code)
    )

    # determine the next redirect location
    request = client.build_request("GET", "wallet", params={"usr": to_user.id})
    i = 0
    while request is not None:
        response = await client.send(request)
        request = response.next_request
        if i == 0:
            assert response.status_code == 307, (  # first redirect
                str(response.url) + " " + str(response.status_code)
            )
        elif i == 1:
            assert response.status_code == 200, (  # then get the actual page
                str(response.url) + " " + str(response.status_code)
            )
        i += 1


# check GET /wallet: wallet and user
@pytest.mark.asyncio
async def test_get_wallet_with_user_and_wallet(client, to_user, to_wallet):
    response = await client.get(
        "wallet", params={"usr": to_user.id, "wal": to_wallet.id}
    )
    assert response.status_code == 200, (
        str(response.url) + " " + str(response.status_code)
    )


# check GET /wallet: wrong wallet and user, expect 204
@pytest.mark.asyncio
async def test_get_wallet_with_user_and_wrong_wallet(client, to_user):
    response = await client.get("wallet", params={"usr": to_user.id, "wal": "1"})
    assert response.status_code == 204, (
        str(response.url) + " " + str(response.status_code)
    )


# check GET /extensions: extensions list
@pytest.mark.asyncio
async def test_get_extensions(client, to_user):
    response = await client.get("extensions", params={"usr": to_user.id})
    assert response.status_code == 200, (
        str(response.url) + " " + str(response.status_code)
    )


# check GET /extensions: extensions list wrong user, expect 204
@pytest.mark.asyncio
async def test_get_extensions_wrong_user(client, to_user):
    response = await client.get("extensions", params={"usr": "1"})
    assert response.status_code == 204, (
        str(response.url) + " " + str(response.status_code)
    )


# check GET /extensions: no user given, expect code 204 no content
@pytest.mark.asyncio
async def test_get_extensions_no_user(client):
    response = await client.get("extensions")
    assert response.status_code == 204, (  # no content
        str(response.url) + " " + str(response.status_code)
    )


# check GET /extensions: enable extension
@pytest.mark.asyncio
async def test_get_extensions_enable(client, to_user):
    response = await client.get(
        "extensions", params={"usr": to_user.id, "enable": "lnurlp"}
    )
    assert response.status_code == 200, (
        str(response.url) + " " + str(response.status_code)
    )


# check GET /extensions: enable nonexistent extension, expect code 400 bad request
@pytest.mark.asyncio
async def test_get_extensions_enable_nonexistent_extension(client, to_user):
    response = await client.get(
        "extensions", params={"usr": to_user.id, "enable": "12341234"}
    )
    assert response.status_code == 400, (
        str(response.url) + " " + str(response.status_code)
    )


# check GET /extensions: enable and disable extensions, expect code 400 bad request
@pytest.mark.asyncio
async def test_get_extensions_enable_and_disable(client, to_user):
    response = await client.get(
        "extensions",
        params={"usr": to_user.id, "enable": "lnurlp", "disable": "lnurlp"},
    )
    assert response.status_code == 400, (
        str(response.url) + " " + str(response.status_code)
    )
