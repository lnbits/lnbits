from http import HTTPStatus
from typing import List

from . import db
from .models import (
    Token,
)

"""
Get Deezy Token
"""


async def get_token() -> Token:

    row = await db.fetchone(
        f"SELECT * FROM deezy.token ORDER BY created_at DESC",
    )

    return Token(**row) if row else None


async def save_token(
    data: Token,
) -> Token:

    await db.execute(
        """
        INSERT INTO deezy.token (
            deezy_token
        )
        VALUES (?)
        """,
        (
            data.deezy_token,
        ),
    )
    return data
