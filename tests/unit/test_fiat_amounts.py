import json
import sqlite3
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from lnbits.core.migrations import m053_integer_fiat_amounts
from lnbits.core.models.payments import fiat_amount_fields
from lnbits.db import SQLITE, Connection


@pytest.mark.parametrize(
    ("value", "units", "precision"),
    [
        ("12.3400", 1234, 2),
        ("1000", 1000, 0),
        ("1.234", 1234, 3),
        ("1E-8", 1, 8),
        ("1E3", 1000, 0),
        ("0.000", 0, 0),
        ("-12.34", -1234, 2),
        ("9999999999.99999999", 999999999999999999, 8),
        ("9223372036854775807", 9223372036854775807, 0),
        ("-9223372036854775808", -9223372036854775808, 0),
    ],
)
def test_fiat_integer_amounts_preserve_precision(value, units, precision):
    assert fiat_amount_fields(
        {"wallet_fiat_currency": "usd", "wallet_fiat_amount": value}
    ) == ("USD", units, precision)


@pytest.mark.parametrize("value", [None, "NaN", "Infinity", "invalid", True, {}])
def test_invalid_fiat_amounts_are_not_accounted(value):
    assert fiat_amount_fields({"fiat_currency": "USD", "fiat_amount": value}) == (
        None,
        None,
        None,
    )


@pytest.mark.parametrize("value", ["9223372036854775808", "1E1000000000"])
def test_unrepresentable_fiat_amounts_are_rejected_without_rounding(value):
    with pytest.raises(ValueError, match="database integer"):
        fiat_amount_fields({"fiat_currency": "USD", "fiat_amount": value})


@pytest.mark.anyio
async def test_fiat_migration_replaces_custom_view_with_native_sql(tmp_path: Path):
    path = tmp_path / "fiat.sqlite3"
    engine = create_async_engine(f"sqlite+aiosqlite:///{path}")
    async with engine.connect() as raw:
        assert raw is not None
        conn = Connection(raw, SQLITE, "database", None)
        await conn.execute("""CREATE TABLE wallets (
            id TEXT PRIMARY KEY, wallet_type TEXT, deleted BOOLEAN)""")
        await conn.execute("""CREATE TABLE apipayments (
            wallet_id TEXT, checking_id TEXT, status TEXT, tag TEXT,
            amount INTEGER, extra TEXT, fiat_currency TEXT)""")
        await conn.execute("""INSERT INTO wallets VALUES
            ('wallet', 'fiat', false), ('alias', 'receive-only', false),
            ('lightning', 'lightning', false), ('deleted', 'fiat', true)""")
        for wallet, checking_id, status, extra in [
            (
                "wallet",
                "same",
                "success",
                {"fiat_currency": "USD", "fiat_amount": "0.1"},
            ),
            (
                "wallet",
                "cash",
                "success",
                {"wallet_fiat_currency": "USD", "wallet_fiat_amount": "0.20"},
            ),
            (
                "wallet",
                "pending",
                "pending",
                {"fiat_currency": "USD", "fiat_amount": "5"},
            ),
            (
                "wallet",
                "failed",
                "failed",
                {"fiat_currency": "USD", "fiat_amount": "9"},
            ),
            (
                "wallet",
                "deleted",
                "deleted",
                {"fiat_currency": "USD", "fiat_amount": "9"},
            ),
            (
                "wallet",
                "provider",
                "success",
                {
                    "fiat_currency": "KWD",
                    "fiat_amount": "1.234",
                    "wallet_fiat_currency": "USD",
                    "wallet_fiat_amount": "4.56",
                },
            ),
            (
                "alias",
                "same",
                "success",
                {"fiat_currency": "EUR", "fiat_amount": "7.80"},
            ),
            (
                "lightning",
                "same",
                "success",
                {"fiat_currency": "USD", "fiat_amount": "99"},
            ),
            (
                "deleted",
                "same",
                "success",
                {"fiat_currency": "USD", "fiat_amount": "99"},
            ),
        ]:
            await conn.execute(
                """INSERT INTO apipayments
                (wallet_id, checking_id, status, tag, amount, extra)
                VALUES (:wallet, :checking_id, :status, NULL, 1000, :extra)""",
                {
                    "wallet": wallet,
                    "checking_id": checking_id,
                    "status": status,
                    "extra": json.dumps(extra),
                },
            )
        # Reproduce an applied m052 without registering its old SQLite aggregate.
        await conn.execute("""CREATE VIEW fiat_balances AS
            SELECT decimal_sum(amount) AS fiat_total FROM apipayments""")
        original: list[dict] = await conn.fetchall(
            "SELECT wallet_id, checking_id, status, amount, extra FROM apipayments"
        )
        await m053_integer_fiat_amounts(conn)
        await m053_integer_fiat_amounts(conn)  # An interrupted upgrade can be retried.
        assert (
            await conn.fetchall(
                "SELECT wallet_id, checking_id, status, amount, extra FROM apipayments"
            )
            == original
        )
    await engine.dispose()

    # A plain SQLite client can query the view, without any LNbits connection hooks.
    with sqlite3.connect(path) as native:
        assert (
            native.execute("""SELECT wallet_id, currency, fiat_precision, fiat_total
            FROM fiat_balances ORDER BY wallet_id, currency""").fetchall()
            == [
                ("alias", "EUR", 1, 78),
                ("wallet", "KWD", 3, 1234),
                ("wallet", "USD", 1, 3),
            ]
        )
        native.execute(
            "UPDATE apipayments SET status = 'success' WHERE checking_id = 'pending'"
        )
        assert native.execute("""SELECT fiat_total FROM fiat_balances
            WHERE wallet_id = 'wallet' AND currency = 'USD'
            AND fiat_precision = 0""").fetchone() == (5,)
