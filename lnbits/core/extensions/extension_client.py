from __future__ import annotations

import posixpath
import re
from typing import Any
from urllib.parse import unquote, urlsplit, urlunsplit

import httpx

from lnbits.core.crud.extensions import (
    get_installed_extension,
    get_user_active_extensions_ids,
)
from lnbits.settings import settings

from .models import ExtensionApiRequest, HttpResponse

EXTENSION_API_TIMEOUT_SECONDS = 10.0
EXTENSION_API_MAX_RESPONSE_BYTES = 262_144

_READ_METHODS = {"GET", "HEAD"}
_WRITE_METHODS = {"DELETE", "PATCH", "POST", "PUT"}
_EXTENSION_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")
_FORBIDDEN_RESPONSE_HEADERS = {
    "connection",
    "content-length",
    "set-cookie",
    "transfer-encoding",
}


async def send_extension_api_request(
    caller_extension_id: str,
    policy: dict[str, Any],
    user_id: str | None,
    access_token: str | None,
    request: ExtensionApiRequest,
) -> HttpResponse:
    if not user_id:
        raise PermissionError("Extension API requests require authentication.")
    if not access_token:
        raise PermissionError("Extension API requests require an account access token.")

    target_extension_id = _target_extension_id(request.extension_id)
    access = _target_extension_access(policy, target_extension_id)
    _require_method_access(caller_extension_id, target_extension_id, access, request)
    await _require_enabled_extension(target_extension_id, user_id)

    path = _extension_api_path(request.path)
    body = request.body.encode() if request.body is not None else b""
    if len(body) > 65_536:
        raise ValueError("Extension API request body is too large.")

    url = f"http://{settings.host}:{settings.port}/{target_extension_id}{path}"
    try:
        async with httpx.AsyncClient(
            follow_redirects=False,
            timeout=EXTENSION_API_TIMEOUT_SECONDS,
            trust_env=False,
        ) as client:
            async with client.stream(
                request.method,
                url,
                headers={"Authorization": f"Bearer {access_token}"},
                content=body,
            ) as response:
                response_body = await _read_limited_response(response)
                return HttpResponse(
                    status_code=response.status_code,
                    headers=_response_headers(dict(response.headers)),
                    body=response_body.decode(response.encoding or "utf-8", "replace"),
                )
    except httpx.RequestError as exc:
        raise ValueError("Extension API request failed.") from exc


def _target_extension_id(extension_id: str) -> str:
    target = extension_id.strip()
    if not target or not _EXTENSION_ID_RE.match(target):
        raise PermissionError("Extension API request has an invalid target extension.")
    return target


def _target_extension_access(
    policy: dict[str, Any], target_extension_id: str
) -> set[str]:
    extensions = policy.get("extensions")
    if not isinstance(extensions, list) or not extensions:
        raise PermissionError(
            "Extension API requests require a non-empty extensions policy."
        )

    for extension in extensions:
        if isinstance(extension, str):
            extension_id = extension
            access = ["read"]
        elif isinstance(extension, dict):
            raw_extension_id = extension.get("id")
            raw_access = extension.get("access")
            if not isinstance(raw_extension_id, str):
                continue
            if not isinstance(raw_access, list):
                raise PermissionError(
                    f"Extension API target '{target_extension_id}' "
                    "has no access policy."
                )
            extension_id = raw_extension_id
            access = raw_access
        else:
            continue

        if extension_id != target_extension_id:
            continue
        clean_access = {
            item
            for item in access
            if isinstance(item, str) and item in {"read", "write"}
        }
        if clean_access:
            return clean_access
        break

    raise PermissionError(
        f"Extension API target '{target_extension_id}' is not allowed."
    )


def _require_method_access(
    caller_extension_id: str,
    target_extension_id: str,
    access: set[str],
    request: ExtensionApiRequest,
) -> None:
    if request.method in _READ_METHODS:
        required_access = "read"
    elif request.method in _WRITE_METHODS:
        required_access = "write"
    else:
        raise PermissionError("Extension API request method is not allowed.")

    if required_access not in access:
        raise PermissionError(
            f"Extension '{caller_extension_id}' cannot {required_access} "
            f"extension '{target_extension_id}'."
        )


async def _require_enabled_extension(target_extension_id: str, user_id: str) -> None:
    extension = await get_installed_extension(target_extension_id)
    if not extension or not extension.active:
        raise PermissionError(
            f"Target extension '{target_extension_id}' is not installed or enabled."
        )

    active_extensions = await get_user_active_extensions_ids(user_id)
    if target_extension_id not in active_extensions:
        raise PermissionError(
            f"Target extension '{target_extension_id}' is not active for this user."
        )


def _extension_api_path(path: str) -> str:
    parts = urlsplit(path)
    if parts.scheme or parts.netloc:
        raise PermissionError("Extension API request path must be relative.")
    if parts.fragment:
        raise PermissionError("Extension API request path cannot include a fragment.")
    if not parts.path.startswith("/api/"):
        raise PermissionError("Extension API request path must start with '/api/'.")

    decoded_path = unquote(parts.path)
    path_parts = decoded_path.split("/")
    if any(part == ".." for part in path_parts):
        raise PermissionError("Extension API request path cannot traverse directories.")

    normalized = posixpath.normpath(decoded_path)
    if normalized != decoded_path.rstrip("/") or not normalized.startswith("/api/"):
        raise PermissionError("Extension API request path is invalid.")

    return urlunsplit(("", "", parts.path, parts.query, ""))


async def _read_limited_response(response: httpx.Response) -> bytes:
    chunks: list[bytes] = []
    size = 0
    async for chunk in response.aiter_bytes():
        size += len(chunk)
        if size > EXTENSION_API_MAX_RESPONSE_BYTES:
            raise ValueError("Extension API response is too large.")
        chunks.append(chunk)
    return b"".join(chunks)


def _response_headers(headers: dict[str, str]) -> dict[str, str]:
    return {
        key: value
        for key, value in headers.items()
        if key.lower() not in _FORBIDDEN_RESPONSE_HEADERS
    }
