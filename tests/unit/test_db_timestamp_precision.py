from datetime import datetime, timezone

import pytest

from lnbits.core.models import PaymentFilters
from lnbits.db import SQLITE, Filter, Filters


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("operator", "expected"),
    [("ge", ["boundary", "after"]), ("le", ["before", "boundary"])],
)
async def test_datetime_filter_preserves_fractional_seconds(db, operator, expected):
    if db.type != SQLITE:
        pytest.skip("SQLite stores timestamps as numeric Unix seconds")

    cutoff = datetime(2026, 10, 1, 12, 0, 0, 500000, tzinfo=timezone.utc)
    async with db.connect() as conn:
        await conn.execute("DROP TABLE IF EXISTS test_timestamp_precision")
        await conn.execute("CREATE TABLE test_timestamp_precision (id TEXT, time REAL)")
        try:
            for name, delta in [("before", -0.25), ("boundary", 0), ("after", 0.25)]:
                await conn.execute(
                    "INSERT INTO test_timestamp_precision (id, time) "
                    "VALUES (:id, :time)",
                    {"id": name, "time": cutoff.timestamp() + delta},
                )
            filters = Filters(
                filters=[
                    Filter.parse_query(
                        f"time[{operator}]", [cutoff.isoformat()], PaymentFilters, 0
                    )
                ],
                model=PaymentFilters,
                sortby="time",
            )
            page = await conn.fetch_page(
                "SELECT id, time FROM test_timestamp_precision", filters=filters
            )
            assert [row["id"] for row in page.data] == expected
            assert page.total == len(expected)
        finally:
            await conn.execute("DROP TABLE test_timestamp_precision")
