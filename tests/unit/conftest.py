import asyncio
import socket
from unittest.mock import AsyncMock, Mock

import httpx
import pytest

from lnbits.utils.safe_http import SafeHttpClient


@pytest.fixture
async def safe_http_mock(monkeypatch):
    """Exercise destination validation and pinning without making network requests."""
    resolver = AsyncMock(
        return_value=[
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))
        ]
    )
    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", resolver)
    handler = Mock(side_effect=lambda request: httpx.Response(200, json={}))
    original_init = SafeHttpClient.__init__

    def init(client, **kwargs):
        original_init(client, **kwargs)
        client.client._transport = httpx.MockTransport(handler)

    monkeypatch.setattr(SafeHttpClient, "__init__", init)
    return resolver, handler
