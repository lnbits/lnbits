from __future__ import annotations

from collections.abc import AsyncIterator
from typing import cast

import pytest
from fastapi import Request

from lnbits.core.wasm_ext.routes.api import (
    WasmRequestBodyTooLargeError,
    _read_api_payload,
    _read_json_object_with_size,
)


@pytest.mark.anyio
async def test_wasm_json_reader_rejects_large_content_length_without_reading():
    request = _FakeRequest([b"{}"], content_length="11")

    with pytest.raises(WasmRequestBodyTooLargeError, match="11 bytes"):
        await _read_json_object_with_size(cast(Request, request), max_body_bytes=10)

    assert request.stream_started is False


@pytest.mark.anyio
async def test_wasm_json_reader_rejects_large_stream_without_content_length():
    request = _FakeRequest([b'{"value":"', b"x" * 20, b'"}'])

    with pytest.raises(WasmRequestBodyTooLargeError):
        await _read_json_object_with_size(cast(Request, request), max_body_bytes=16)

    assert request.stream_started is True


@pytest.mark.anyio
async def test_wasm_api_payload_records_actual_body_bytes():
    body = b'{"amount":21}'
    request = _FakeRequest(
        [body],
        path_params={"invoice_id": "abc"},
        query_params={"include_paid": "true"},
    )

    payload = await _read_api_payload(
        cast(Request, request),
        {"invoice_id": "invoiceId"},
        max_body_bytes=100,
    )

    assert payload.data == {
        "invoiceId": "abc",
        "includePaid": "true",
        "amount": 21,
    }
    assert payload.request_bytes == len(body)


class _FakeRequest:
    method = "POST"

    def __init__(
        self,
        chunks: list[bytes],
        *,
        content_length: str | None = None,
        path_params: dict[str, str] | None = None,
        query_params: dict[str, str] | None = None,
    ) -> None:
        self._chunks = chunks
        self.headers: dict[str, str] = {}
        if content_length is not None:
            self.headers["content-length"] = content_length
        self.path_params = path_params or {}
        self.query_params = query_params or {}
        self.stream_started = False

    async def stream(self) -> AsyncIterator[bytes]:
        self.stream_started = True
        for chunk in self._chunks:
            yield chunk
