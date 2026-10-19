from datetime import date, datetime, timezone

import pytest
from pydantic import BaseModel, Field

from lnbits.core.crud import (
    create_wallet,
    delete_wallet,
    get_wallet,
    get_wallet_for_key,
)
from lnbits.core.crud.payments import get_payment
from lnbits.core.models import CreateInvoice, PaymentFilters
from lnbits.core.services.payments import create_wallet_invoice
from lnbits.db import POSTGRES, SQLITE, Filter, Filters, dict_to_model, model_to_dict


@pytest.mark.parametrize("db_type", [SQLITE, POSTGRES])
def test_model_database_roundtrip_preserves_nested_and_optional_fields(
    monkeypatch, db_type
):
    class Details(BaseModel):
        description: str
        note: str | None = None
        attributes: dict[str, int] = {}

    class Record(BaseModel):
        details: Details | None = None
        history: list[Details] = []
        optional_history: list[Details] | None = None
        metadata: dict[str, int] = {}
        created_at: datetime
        enabled: bool = False
        derived: int = Field(default=0, json_schema_extra={"no_database": True})

    monkeypatch.setattr("lnbits.db.DB_TYPE", db_type)
    record = Record(
        details=Details(description="invoice", attributes={"attempts": 1}),
        history=[Details(description="created")],
        metadata={"attempts": 1},
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        enabled=True,
        derived=10,
    )
    row = model_to_dict(record)
    assert "derived" not in row
    assert isinstance(row["details"], str)
    assert isinstance(row["history"], str)
    assert isinstance(row["metadata"], str)
    row["enabled"] = 1
    row["joined_column"] = "ignored"
    restored = dict_to_model(row, Record)
    assert restored.model_dump(exclude={"derived"}) == record.model_dump(
        exclude={"derived"}
    )
    assert restored.derived == 0

    row["details"] = "null"
    assert dict_to_model(row, Record).details is None


@pytest.mark.parametrize(
    ("db_type", "lower_statement", "upper_statement"),
    [
        (
            POSTGRES,
            "(time >= to_timestamp(:time__0_0))",
            "(time <= to_timestamp(:time__1_0))",
        ),
        (SQLITE, "(time >= :time__0_0)", "(time <= :time__1_0)"),
    ],
)
def test_datetime_filter_uses_database_timestamp_placeholder(
    monkeypatch, db_type, lower_statement, upper_statement
):
    monkeypatch.setattr("lnbits.db.DB_TYPE", db_type)
    lower_bound = Filter.parse_query(
        "time[ge]", ["2026-06-16T00:00:00"], PaymentFilters, 0
    )
    upper_bound = Filter.parse_query(
        "time[le]", ["2026-06-23T23:59:59"], PaymentFilters, 1
    )
    filters = Filters(filters=[lower_bound, upper_bound], model=PaymentFilters)
    values = filters.values()

    assert isinstance(values["time__0_0"], datetime)
    assert values["time__0_0"] == datetime(2026, 6, 16)
    assert values["time__1_0"] == datetime(2026, 6, 23, 23, 59, 59)
    assert filters.where() == f"WHERE {lower_statement} AND {upper_statement}"
    assert lower_bound.statement == lower_statement
    assert upper_bound.statement == upper_statement


@pytest.mark.anyio
async def test_date_conversion(db):
    if db.type == POSTGRES:
        row = await db.fetchone("SELECT now()::date as now")
        assert row and isinstance(row.get("now"), date)


@pytest.mark.anyio
async def test_payment_datetime_fields_have_timezone(app, to_user):
    """Test that Payment datetime fields always have UTC timezone info."""
    wallet = await create_wallet(user_id=to_user.id, wallet_name="test_tz_wallet")
    invoice_data = CreateInvoice(amount=10, memo="timezone_test", out=False)
    invoice = await create_wallet_invoice(wallet.id, invoice_data)

    payment = await get_payment(invoice.checking_id)
    assert payment is not None

    # All datetime fields should have UTC timezone info
    assert payment.time.tzinfo == timezone.utc
    assert payment.created_at.tzinfo == timezone.utc
    assert payment.updated_at.tzinfo == timezone.utc
    if payment.expiry:
        assert payment.expiry.tzinfo == timezone.utc


# make test to create wallet and delete wallet
@pytest.mark.anyio
async def test_create_wallet_and_delete_wallet(app, to_user):
    # create wallet
    wallet = await create_wallet(user_id=to_user.id, wallet_name="test_wallet_delete")
    assert wallet

    # delete wallet
    await delete_wallet(user_id=to_user.id, wallet_id=wallet.id)

    # check if wallet is deleted
    del_wallet = await get_wallet(wallet.id)
    assert del_wallet is None

    # check if wallet is deleted
    del_wallet = await get_wallet(wallet.id, False)
    assert del_wallet is None

    del_wallet = await get_wallet(wallet.id, None)
    assert del_wallet is not None
    assert del_wallet.deleted is True

    del_wallet = await get_wallet(wallet.id, True)
    assert del_wallet is not None
    assert del_wallet.deleted is True

    del_wallet = await get_wallet_for_key(wallet.inkey)
    assert del_wallet is None


class _Nested(BaseModel):
    cap: int | None = Field(default=0)  # nullable, non-None default
    note: str | None = None


class _Row(BaseModel):
    id: str
    added_later: int = 7  # not nullable; NULL means "column predates field"
    cap: int | None = Field(default=0)  # nullable; NULL means None
    nested: _Nested | None = None


def test_null_column_fills_the_default_for_a_non_nullable_field():
    """`ALTER TABLE ADD COLUMN` leaves existing rows NULL. A field that
    cannot hold None must fall back to its default rather than raise."""
    row = dict_to_model({"id": "x", "added_later": None}, _Row)
    assert row.added_later == 7


def test_null_column_stays_none_for_a_nullable_field():
    """Regression: a nullable field whose default is not None could never
    read back as None — the key was dropped and the default substituted, so
    `Optional[int] = 0` always returned 0 however the row was stored."""
    row = dict_to_model({"id": "x", "cap": None}, _Row)
    assert row.cap is None


def test_absent_column_still_fills_the_default():
    """Absence is not NULL, and must keep behaving as before."""
    assert dict_to_model({"id": "x"}, _Row).cap == 0


def test_nullable_roundtrip_through_both_serializers():
    """The path crud uses: model -> row -> model."""
    stored = _Row(id="x", cap=None, nested=_Nested(cap=None, note="n"))
    back = dict_to_model(model_to_dict(stored), _Row)
    assert back.cap is None
    assert back.added_later == 7
    assert back.nested is not None
    assert back.nested.cap is None
    assert back.nested.note == "n"


def test_join_column_absent_from_the_model_is_still_ignored():
    row = dict_to_model({"id": "x", "joined_extra": None, "other": 1}, _Row)
    assert row.id == "x"
