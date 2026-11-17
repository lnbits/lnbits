import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from lnbits.middleware import add_ip_block_middleware
from lnbits.settings import Settings


@pytest.mark.anyio
@pytest.mark.parametrize(
    "proxy_ips,peer,forwarded_for,expected_status,expected_client",
    [
        (None, "198.51.100.23", None, 403, None),
        (None, "198.51.100.23", "10.99.0.1", 403, None),
        (None, "127.0.0.1", "10.99.0.1, 198.51.100.23", 403, None),
        (None, "127.0.0.1", "198.51.100.24", 200, "198.51.100.24"),
        (
            "198.51.100.10",
            "198.51.100.10",
            "10.99.0.1, 198.51.100.23",
            403,
            None,
        ),
        (
            "198.51.100.10",
            "198.51.100.10",
            "198.51.100.24",
            200,
            "198.51.100.24",
        ),
    ],
)
async def test_forwarded_client_address(
    monkeypatch,
    settings,
    proxy_ips,
    peer,
    forwarded_for,
    expected_status,
    expected_client,
):
    monkeypatch.delenv("FORWARDED_ALLOW_IPS", raising=False)
    if proxy_ips is not None:
        monkeypatch.setenv("FORWARDED_ALLOW_IPS", proxy_ips)
    loaded = Settings(_env_file=None)  # pyright: ignore[reportCallIssue]
    monkeypatch.setattr(settings, "lnbits_blocked_ips", ["198.51.100.23"])
    monkeypatch.setattr(settings, "lnbits_allowed_ips", [])
    app = FastAPI()
    add_ip_block_middleware(app)

    @app.get("/")
    async def client_address(request: Request):
        return {"client": request.client.host if request.client else None}

    transport = ASGITransport(
        app=ProxyHeadersMiddleware(app, trusted_hosts=loaded.forwarded_allow_ips),
        client=(peer, 12345),
    )
    headers = {"X-Forwarded-For": forwarded_for} if forwarded_for else {}
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/", headers=headers)

    assert response.status_code == expected_status
    if expected_client is not None:
        assert response.json() == {"client": expected_client}
    else:
        assert response.json() == {"detail": "IP is blocked"}
