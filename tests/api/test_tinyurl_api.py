from http import HTTPStatus

import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_tinyurl_api_create_get_redirect_and_delete(
    client: AsyncClient,
    adminkey_headers_from: dict[str, str],
    inkey_headers_from: dict[str, str],
    inkey_headers_to: dict[str, str],
):
    created = await client.post(
        "/api/v1/tinyurl",
        params={"url": "https://example.com/landing", "endless": "true"},
        headers=adminkey_headers_from,
    )
    assert created.status_code == HTTPStatus.OK
    tinyurl = created.json()
    assert tinyurl["url"] == "https://example.com/landing"
    assert tinyurl["endless"] is True

    fetched = await client.get(
        f"/api/v1/tinyurl/{tinyurl['id']}",
        headers=inkey_headers_from,
    )
    assert fetched.status_code == HTTPStatus.OK
    assert fetched.json()["id"] == tinyurl["id"]

    wrong_wallet = await client.get(
        f"/api/v1/tinyurl/{tinyurl['id']}",
        headers=inkey_headers_to,
    )
    assert wrong_wallet.status_code == HTTPStatus.NOT_FOUND
    assert wrong_wallet.json()["detail"] == "Unable to fetch tinyurl"

    redirect = await client.get(f"/t/{tinyurl['id']}")
    assert redirect.status_code == HTTPStatus.TEMPORARY_REDIRECT
    assert redirect.headers["location"] == "https://example.com/landing"

    deleted = await client.delete(
        f"/api/v1/tinyurl/{tinyurl['id']}",
        headers=adminkey_headers_from,
    )
    assert deleted.status_code == HTTPStatus.OK
    assert deleted.json()["deleted"] is True

    missing_redirect = await client.get(f"/t/{tinyurl['id']}")
    assert missing_redirect.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.anyio
async def test_tinyurl_api_reuses_existing_entries_for_same_wallet(
    client: AsyncClient,
    adminkey_headers_from: dict[str, str],
):
    first = await client.post(
        "/api/v1/tinyurl",
        params={"url": "https://example.com/reused"},
        headers=adminkey_headers_from,
    )
    second = await client.post(
        "/api/v1/tinyurl",
        params={"url": "https://example.com/reused"},
        headers=adminkey_headers_from,
    )

    assert first.status_code == HTTPStatus.OK
    assert second.status_code == HTTPStatus.OK
    assert first.json()["id"] == second.json()["id"]
