from http import HTTPStatus

import pytest


@pytest.mark.anyio
async def test_create___bad_body(client, user_headers_from):
    response = await client.post(
        "/api/v1/webpush",
        headers=user_headers_from,
        json={"subscription": "bad_json"},
    )
    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR


@pytest.mark.anyio
async def test_create___missing_fields(client, user_headers_from):
    response = await client.post(
        "/api/v1/webpush",
        headers=user_headers_from,
        json={"subscription": """{"a": "x"}"""},
    )
    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR


@pytest.mark.anyio
async def test_create___bad_access_key(client, inkey_headers_from):
    response = await client.post(
        "/api/v1/webpush",
        headers=inkey_headers_from,
        json={"subscription": """{"a": "x"}"""},
    )
    assert response.status_code == HTTPStatus.UNAUTHORIZED


@pytest.mark.anyio
async def test_delete__bad_endpoint_format(client, user_headers_from):
    response = await client.delete(
        "/api/v1/webpush",
        params={"endpoint": "https://this.should.be.base64.com"},
        headers=user_headers_from,
    )
    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR


@pytest.mark.anyio
async def test_delete__no_endpoint_param(client, user_headers_from):
    response = await client.delete(
        "/api/v1/webpush",
        headers=user_headers_from,
    )
    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR


@pytest.mark.anyio
async def test_delete__no_endpoint_found(client, user_headers_from):
    response = await client.delete(
        "/api/v1/webpush",
        params={"endpoint": "aHR0cHM6Ly9kZW1vLmxuYml0cy5jb20="},
        headers=user_headers_from,
    )
    assert response.status_code == HTTPStatus.OK
    assert response.json()["count"] == 0


@pytest.mark.anyio
async def test_delete__bad_access_key(client, inkey_headers_from):
    response = await client.delete(
        "/api/v1/webpush",
        headers=inkey_headers_from,
    )
    assert response.status_code == HTTPStatus.UNAUTHORIZED


@pytest.mark.anyio
async def test_create_and_delete(client, user_headers_from):
    response = await client.post(
        "/api/v1/webpush",
        headers=user_headers_from,
        json={"subscription": """{"endpoint": "https://demo.lnbits.com"}"""},
    )
    assert response.status_code == HTTPStatus.CREATED
    response = await client.delete(
        "/api/v1/webpush",
        params={"endpoint": "aHR0cHM6Ly9kZW1vLmxuYml0cy5jb20="},
        headers=user_headers_from,
    )
    assert response.status_code == HTTPStatus.OK
    assert response.json()["count"] == 1
