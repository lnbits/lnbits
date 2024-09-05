import hashlib
from typing import Any, Optional
from urllib import request

import httpx
from loguru import logger
from packaging import version

from lnbits.settings import settings


def version_parse(v: str):
    """
    Wrapper for version.parse() that does not throw if the version is invalid.
    Instead it return the lowest possible version ("0.0.0")
    """
    try:
        return version.parse(v)
    except Exception:
        return version.parse("0.0.0")


async def github_api_get(url: str, error_msg: Optional[str]) -> Any:
    headers = {"User-Agent": settings.user_agent}
    if settings.lnbits_ext_github_token:
        headers["Authorization"] = f"Bearer {settings.lnbits_ext_github_token}"
    async with httpx.AsyncClient(headers=headers) as client:
        resp = await client.get(url)
        if resp.status_code != 200:
            logger.warning(f"{error_msg} ({url}): {resp.text}")
        resp.raise_for_status()
        return resp.json()


def download_url(url, save_path):
    with request.urlopen(url, timeout=60) as dl_file:
        with open(save_path, "wb") as out_file:
            out_file.write(dl_file.read())


def file_hash(filename):
    h = hashlib.sha256()
    b = bytearray(128 * 1024)
    mv = memoryview(b)
    with open(filename, "rb", buffering=0) as f:
        while n := f.readinto(mv):
            h.update(mv[:n])
    return h.hexdigest()


def icon_to_github_url(source_repo: str, path: Optional[str]) -> str:
    if not path:
        return ""
    _, _, *rest = path.split("/")
    tail = "/".join(rest)
    return f"https://github.com/{source_repo}/raw/main/{tail}"
