from datetime import date

import pytest

from lnbits.db import POSTGRES


@pytest.mark.asyncio
async def test_date_conversion(db):
    if db.type == POSTGRES:
        row = await db.fetchone("SELECT now()::date")
        assert row and isinstance(row[0], date)
