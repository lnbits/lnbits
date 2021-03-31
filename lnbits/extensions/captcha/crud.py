from typing import List, Optional, Union

from lnbits.helpers import urlsafe_short_hash

from . import db
from .models import Captcha


async def create_captcha(
    *,
    wallet_id: str,
    url: str,
    memo: str,
    description: Optional[str] = None,
    amount: int = 0,
    remembers: bool = True,
) -> Captcha:
    captcha_id = urlsafe_short_hash()
    await db.execute(
        """
        INSERT INTO captchas (id, wallet, url, memo, description, amount, remembers)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (captcha_id, wallet_id, url, memo, description, amount, int(remembers)),
    )

    captcha = await get_captcha(captcha_id)
    assert captcha, "Newly created captcha couldn't be retrieved"
    return captcha


async def get_captcha(captcha_id: str) -> Optional[Captcha]:
    row = await db.fetchone("SELECT * FROM captchas WHERE id = ?", (captcha_id,))

    return Captcha.from_row(row) if row else None


async def get_captchas(wallet_ids: Union[str, List[str]]) -> List[Captcha]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    q = ",".join(["?"] * len(wallet_ids))
    rows = await db.fetchall(
        f"SELECT * FROM captchas WHERE wallet IN ({q})", (*wallet_ids,)
    )

    return [Captcha.from_row(row) for row in rows]


async def delete_captcha(captcha_id: str) -> None:
    await db.execute("DELETE FROM captchas WHERE id = ?", (captcha_id,))
