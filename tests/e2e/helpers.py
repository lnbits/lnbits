from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class LNbitsE2EServer:
    base_url: str
    password: str
    username: str


def api_json(
    base_url: str,
    method: str,
    path: str,
    data: dict[str, Any] | None = None,
    api_key: str | None = None,
    timeout: float = 30,
) -> dict[str, Any]:
    status, body = request_json(
        f"{base_url}{path}",
        method=method,
        data=data,
        api_key=api_key,
        timeout=timeout,
    )
    if not 200 <= status < 300:
        raise AssertionError(f"{method} {path} failed with {status}: {body!r}")
    return body


def request_json(
    url: str,
    *,
    method: str,
    data: dict[str, Any] | None = None,
    api_key: str | None = None,
    timeout: float = 30,
) -> tuple[int, dict[str, Any]]:
    body = json.dumps(data or {}).encode("utf-8") if data is not None else None
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-Api-Key"] = api_key
    request = Request(url, data=body, headers=headers, method=method)  # noqa: S310
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310
            response_body = response.read().decode("utf-8")
            return response.status, json.loads(response_body or "{}")
    except HTTPError as exc:
        response_body = exc.read().decode("utf-8")
        try:
            parsed = json.loads(response_body or "{}")
        except json.JSONDecodeError:
            parsed = {"detail": response_body}
        return exc.code, parsed
