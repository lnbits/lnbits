from time import time
from typing import Literal, Optional

from lnbits.core.crud.wallets import get_total_balance, get_wallet
from lnbits.core.db import db
from lnbits.core.models import PaymentState
from lnbits.db import DB_TYPE, SQLITE, Connection, Filters, Page

from ..models import (
    CreatePayment,
    Payment,
    PaymentFilters,
    PaymentHistoryPoint,
)

DateTrunc = Literal["hour", "day", "month"]
sqlite_formats = {
    "hour": "%Y-%m-%d %H:00:00",
    "day": "%Y-%m-%d 00:00:00",
    "month": "%Y-%m-01 00:00:00",
}


def update_payment_extra():
    pass


async def get_payment(checking_id: str, conn: Optional[Connection] = None) -> Payment:
    return await (conn or db).fetchone(
        "SELECT * FROM apipayments WHERE checking_id = :checking_id",
        {"checking_id": checking_id},
        Payment,
    )


async def get_standalone_payment(
    checking_id_or_hash: str,
    conn: Optional[Connection] = None,
    incoming: Optional[bool] = False,
    wallet_id: Optional[str] = None,
) -> Optional[Payment]:
    clause: str = "checking_id = :checking_id OR payment_hash = :hash"
    values = {
        "wallet_id": wallet_id,
        "checking_id": checking_id_or_hash,
        "hash": checking_id_or_hash,
    }
    if incoming:
        clause = f"({clause}) AND amount > 0"

    if wallet_id:
        clause = f"({clause}) AND wallet_id = :wallet_id"

    row = await (conn or db).fetchone(
        f"""
        SELECT * FROM apipayments
        WHERE {clause}
        ORDER BY amount LIMIT 1
        """,
        values,
        Payment,
    )
    return row


async def get_wallet_payment(
    wallet_id: str, payment_hash: str, conn: Optional[Connection] = None
) -> Optional[Payment]:
    payment = await (conn or db).fetchone(
        """
        SELECT *
        FROM apipayments
        WHERE wallet_id = :wallet AND payment_hash = :hash
        """,
        {"wallet": wallet_id, "hash": payment_hash},
        Payment,
    )
    return payment


async def get_latest_payments_by_extension(
    ext_name: str, ext_id: str, limit: int = 5
) -> list[Payment]:
    return await db.fetchall(
        f"""
        SELECT * FROM apipayments
        WHERE status = '{PaymentState.SUCCESS}'
        AND extra LIKE :ext_name
        AND extra LIKE :ext_id
        ORDER BY time DESC LIMIT {limit}
        """,
        {"ext_name": f"%{ext_name}%", "ext_id": f"%{ext_id}%"},
        Payment,
    )


async def get_payments_paginated(
    *,
    wallet_id: Optional[str] = None,
    complete: bool = False,
    pending: bool = False,
    outgoing: bool = False,
    incoming: bool = False,
    since: Optional[int] = None,
    exclude_uncheckable: bool = False,
    filters: Optional[Filters[PaymentFilters]] = None,
    conn: Optional[Connection] = None,
) -> Page[Payment]:
    """
    Filters payments to be returned by complete | pending | outgoing | incoming.
    """

    values: dict = {
        "wallet_id": wallet_id,
        "time": since,
    }
    clause: list[str] = []

    if since is not None:
        clause.append(f"time > {db.timestamp_placeholder('time')}")

    if wallet_id:
        clause.append("wallet_id = :wallet_id")

    if complete and pending:
        pass
    elif complete:
        clause.append(
            f"((amount > 0 AND status = '{PaymentState.SUCCESS}') OR amount < 0)"
        )
    elif pending:
        clause.append(f"status = '{PaymentState.PENDING}'")
    else:
        pass

    if outgoing and incoming:
        pass
    elif outgoing:
        clause.append("amount < 0")
    elif incoming:
        clause.append("amount > 0")
    else:
        pass

    if exclude_uncheckable:  # checkable means it has a checking_id that isn't internal
        clause.append("checking_id NOT LIKE 'temp_%'")
        clause.append("checking_id NOT LIKE 'internal_%'")

    return await (conn or db).fetch_page(
        "SELECT * FROM apipayments",
        clause,
        values,
        filters=filters,
        model=Payment,
    )


async def get_payments(
    *,
    wallet_id: Optional[str] = None,
    complete: bool = False,
    pending: bool = False,
    outgoing: bool = False,
    incoming: bool = False,
    since: Optional[int] = None,
    exclude_uncheckable: bool = False,
    filters: Optional[Filters[PaymentFilters]] = None,
    conn: Optional[Connection] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
) -> list[Payment]:
    """
    Filters payments to be returned by complete | pending | outgoing | incoming.
    """

    filters = filters or Filters()

    filters.sortby = filters.sortby or "time"
    filters.direction = filters.direction or "desc"
    filters.limit = limit or filters.limit
    filters.offset = offset or filters.offset

    page = await get_payments_paginated(
        wallet_id=wallet_id,
        complete=complete,
        pending=pending,
        outgoing=outgoing,
        incoming=incoming,
        since=since,
        exclude_uncheckable=exclude_uncheckable,
        filters=filters,
        conn=conn,
    )

    return page.data


async def delete_expired_invoices(
    conn: Optional[Connection] = None,
) -> None:
    # first we delete all invoices older than one month

    await (conn or db).execute(
        f"""
        DELETE FROM apipayments
        WHERE status = '{PaymentState.PENDING}' AND amount > 0
        AND time < {db.timestamp_placeholder("delta")}
        """,
        {"delta": int(time() - 2592000)},
    )
    # then we delete all invoices whose expiry date is in the past
    await (conn or db).execute(
        f"""
        DELETE FROM apipayments
        WHERE status = '{PaymentState.PENDING}' AND amount > 0
        AND expiry < {db.timestamp_placeholder("now")}
        """,
        {"now": int(time())},
    )


async def create_payment(
    checking_id: str,
    data: CreatePayment,
    status: PaymentState = PaymentState.PENDING,
    conn: Optional[Connection] = None,
) -> Payment:
    # we don't allow the creation of the same invoice twice
    # note: this can be removed if the db uniqueness constraints are set appropriately
    previous_payment = await get_standalone_payment(checking_id, conn=conn)
    assert previous_payment is None, "Payment already exists"

    payment = Payment(
        checking_id=checking_id,
        status=status,
        wallet_id=data.wallet_id,
        payment_hash=data.payment_hash,
        bolt11=data.bolt11,
        amount=data.amount_msat,
        memo=data.memo,
        preimage=data.preimage,
        expiry=data.expiry,
        webhook=data.webhook,
        fee=data.fee,
        extra=data.extra or {},
    )

    await (conn or db).insert("apipayments", payment)

    return payment


async def update_payment_checking_id(
    checking_id: str, new_checking_id: str, conn: Optional[Connection] = None
) -> None:
    await (conn or db).execute(
        "UPDATE apipayments SET checking_id = :new_id WHERE checking_id = :old_id",
        {"new_id": new_checking_id, "old_id": checking_id},
    )


async def update_payment(
    payment: Payment,
    new_checking_id: Optional[str] = None,
    conn: Optional[Connection] = None,
) -> None:
    await (conn or db).update(
        "apipayments", payment, "WHERE checking_id = :checking_id"
    )
    if new_checking_id and new_checking_id != payment.checking_id:
        await update_payment_checking_id(payment.checking_id, new_checking_id, conn)


async def get_payments_history(
    wallet_id: Optional[str] = None,
    group: DateTrunc = "day",
    filters: Optional[Filters] = None,
) -> list[PaymentHistoryPoint]:
    if not filters:
        filters = Filters()

    if DB_TYPE == SQLITE and group in sqlite_formats:
        date_trunc = f"strftime('{sqlite_formats[group]}', time, 'unixepoch')"
    elif group in ("day", "hour", "month"):
        date_trunc = f"date_trunc('{group}', time)"
    else:
        raise ValueError(f"Invalid group value: {group}")

    values = {
        "wallet_id": wallet_id,
    }
    where = [
        f"wallet_id = :wallet_id AND (status = '{PaymentState.SUCCESS}' OR amount < 0)"
    ]
    transactions: list[dict] = await db.fetchall(
        f"""
        SELECT {date_trunc} date,
               SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END) income,
               SUM(CASE WHEN amount < 0 THEN abs(amount) + abs(fee) ELSE 0 END) spending
        FROM apipayments
        {filters.where(where)}
        GROUP BY date
        ORDER BY date DESC
        """,
        filters.values(values),
    )
    if wallet_id:
        wallet = await get_wallet(wallet_id)
        if wallet:
            balance = wallet.balance_msat
        else:
            raise ValueError("Unknown wallet")
    else:
        balance = await get_total_balance()

    # since we dont know the balance at the starting point,
    # we take the current balance and walk backwards
    results: list[PaymentHistoryPoint] = []
    for row in transactions:
        results.insert(
            0,
            PaymentHistoryPoint(
                balance=balance,
                date=row.get("date", 0),
                income=row.get("income", 0),
                spending=row.get("spending", 0),
            ),
        )
        balance -= row.get("income", 0) - row.get("spending", 0)
    return results


async def delete_wallet_payment(
    checking_id: str, wallet_id: str, conn: Optional[Connection] = None
) -> None:
    await (conn or db).execute(
        "DELETE FROM apipayments WHERE checking_id = :checking_id AND wallet = :wallet",
        {"checking_id": checking_id, "wallet": wallet_id},
    )


async def check_internal(
    payment_hash: str, conn: Optional[Connection] = None
) -> Optional[Payment]:
    """
    Returns the checking_id of the internal payment if it exists,
    otherwise None
    """
    return await (conn or db).fetchone(
        f"""
        SELECT * FROM apipayments
        WHERE payment_hash = :hash AND status = '{PaymentState.PENDING}' AND amount > 0
        """,
        {"hash": payment_hash},
        Payment,
    )


async def is_internal_status_success(
    payment_hash: str, conn: Optional[Connection] = None
) -> bool:
    """
    Returns True if the internal payment was found and is successful,
    """
    payment = await (conn or db).fetchone(
        """
        SELECT * FROM apipayments
        WHERE payment_hash = :payment_hash AND amount > 0
        """,
        {"payment_hash": payment_hash},
        Payment,
    )
    if not payment:
        return False
    return payment.status == PaymentState.SUCCESS.value


async def mark_webhook_sent(payment_hash: str, status: int) -> None:
    await db.execute(
        """
        UPDATE apipayments SET webhook_status = :status
        WHERE payment_hash = :hash
        """,
        {"status": status, "hash": payment_hash},
    )
