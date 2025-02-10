from typing import Optional

import shortuuid

from lnbits.core.db import db

from ..models import TinyURL


async def create_tinyurl(domain: str, endless: bool, wallet: str):
    tinyurl_id = shortuuid.uuid()[:8]
    await db.execute(
        """
        INSERT INTO tiny_url (id, url, endless, wallet)
        VALUES (:tinyurl, :domain, :endless, :wallet)
        """,
        {"tinyurl": tinyurl_id, "domain": domain, "endless": endless, "wallet": wallet},
    )
    return await get_tinyurl(tinyurl_id)


async def get_tinyurl(tinyurl_id: str) -> Optional[TinyURL]:
    return await db.fetchone(
        "SELECT * FROM tiny_url WHERE id = :tinyurl",
        {"tinyurl": tinyurl_id},
        TinyURL,
    )


async def get_tinyurl_by_url(url: str) -> list[TinyURL]:
    return await db.fetchall(
        "SELECT * FROM tiny_url WHERE url = :url",
        {"url": url},
        TinyURL,
    )


async def delete_tinyurl(tinyurl_id: str):
    await db.execute(
        "DELETE FROM tiny_url WHERE id = :tinyurl",
        {"tinyurl": tinyurl_id},
    )
