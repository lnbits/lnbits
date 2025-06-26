from time import time
from typing import Any, Optional

from lnbits.core.crud.wallets import get_total_balance, get_wallet, get_wallets_ids
from lnbits.core.db import db
from lnbits.core.models import PaymentState
from lnbits.db import Connection, DateTrunc, Filters, Page

from ..models import (
    CreatePayment,
    Payment,
    PaymentCountField,
    PaymentCountStat,
    PaymentDailyStats,
    PaymentFilters,
    PaymentHistoryPoint,
    PaymentsStatusCount,
    PaymentWalletStats,
)


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
        ORDER BY time DESC LIMIT {int(limit)}
        """,
        {"ext_name": f"%{ext_name}%", "ext_id": f"%{ext_id}%"},
        Payment,
    )


async def get_payments_paginated(
    *,
    wallet_id: Optional[str] = None,
    user_id: Optional[str] = None,
    complete: bool = False,
    pending: bool = False,
    failed: bool = False,
    outgoing: bool = False,
    incoming: bool = False,
    since: Optional[int] = None,
    exclude_uncheckable: bool = False,
    filters: Optional[Filters[PaymentFilters]] = None,
    conn: Optional[Connection] = None,
) -> Page[Payment]:
    """
    Filters payments to be returned by:
      - complete | pending | failed | outgoing | incoming.
    """

    values: dict[str, Any] = {
        "time": since,
    }
    clause: list[str] = []

    if since is not None:
        clause.append(f"time > {db.timestamp_placeholder('time')}")

    if wallet_id:
        values["wallet_id"] = wallet_id
        clause.append("wallet_id = :wallet_id")
    elif user_id:
        only_user_wallets = await _only_user_wallets_statement(user_id, conn=conn)
        clause.append(only_user_wallets)

    if complete and pending:
        clause.append(
            f"(status = '{PaymentState.SUCCESS}' OR status = '{PaymentState.PENDING}')"
        )
    elif complete:
        clause.append(
            f"""
            (
                status = '{PaymentState.SUCCESS}'
                OR (amount < 0 AND status = '{PaymentState.PENDING}')
            )
            """
        )
    elif pending:
        clause.append(f"status = '{PaymentState.PENDING}'")
    elif failed:
        clause.append(f"status = '{PaymentState.FAILED}'")

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


async def get_payments_status_count() -> PaymentsStatusCount:
    empty_page: Filters = Filters(limit=0)
    in_payments = await get_payments_paginated(incoming=True, filters=empty_page)
    out_payments = await get_payments_paginated(outgoing=True, filters=empty_page)
    pending_payments = await get_payments_paginated(pending=True, filters=empty_page)
    failed_payments = await get_payments_paginated(failed=True, filters=empty_page)

    return PaymentsStatusCount(
        incoming=in_payments.total,
        outgoing=out_payments.total,
        pending=pending_payments.total,
        failed=failed_payments.total,
    )


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
    extra = data.extra or {}

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
        tag=extra.get("tag", None),
        extra=extra,
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

    date_trunc = db.datetime_grouping(group)

    values = {
        "wallet_id": wallet_id,
    }
    # count outgoing payments if they are still pending
    where = [
        f"""
        wallet_id = :wallet_id AND (
            status = '{PaymentState.SUCCESS}'
            OR (amount < 0 AND status = '{PaymentState.PENDING}')
        )
        """
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


async def get_payment_count_stats(
    field: PaymentCountField,
    filters: Optional[Filters[PaymentFilters]] = None,
    user_id: Optional[str] = None,
    conn: Optional[Connection] = None,
) -> list[PaymentCountStat]:

    if not filters:
        filters = Filters()
    extra_stmts = []

    if user_id:
        only_user_wallets = await _only_user_wallets_statement(user_id, conn=conn)
        extra_stmts.append(only_user_wallets)

    clause = filters.where(extra_stmts)
    data = await (conn or db).fetchall(
        query=f"""
            SELECT {field} as field, count(*) as total
            FROM apipayments
            {clause}
            GROUP BY {field}
            ORDER BY {field}
        """,
        values=filters.values(),
        model=PaymentCountStat,
    )

    return data


async def get_daily_stats(
    filters: Optional[Filters[PaymentFilters]] = None,
    user_id: Optional[str] = None,
    conn: Optional[Connection] = None,
) -> tuple[list[PaymentDailyStats], list[PaymentDailyStats]]:

    if not filters:
        filters = Filters()

    in_where_stmts = ["(apipayments.status = 'success' AND apipayments.amount > 0)"]
    out_where_stmts = [
        "(apipayments.status IN ('success', 'pending') AND apipayments.amount < 0)"
    ]

    if user_id:
        only_user_wallets = await _only_user_wallets_statement(user_id, conn=conn)
        in_where_stmts.append(only_user_wallets)
        out_where_stmts.append(only_user_wallets)

    in_clause = filters.where(in_where_stmts)
    out_clause = filters.where(out_where_stmts)

    date_trunc = db.datetime_grouping("day")
    query = """
        SELECT {date_trunc} date,
            SUM(apipayments.amount - ABS(apipayments.fee)) AS balance,
            ABS(SUM(apipayments.fee)) as fee,
            COUNT(*) as payments_count
        FROM wallets
        LEFT JOIN apipayments ON apipayments.wallet_id = wallets.id
        {clause}
        AND (wallets.deleted = false OR wallets.deleted is NULL)
        GROUP BY date
        ORDER BY date ASC
    """

    data_in = await (conn or db).fetchall(
        query=query.format(date_trunc=date_trunc, clause=in_clause),
        values=filters.values(),
        model=PaymentDailyStats,
    )
    data_out = await (conn or db).fetchall(
        query=query.format(date_trunc=date_trunc, clause=out_clause),
        values=filters.values(),
        model=PaymentDailyStats,
    )

    return data_in, data_out


async def get_wallets_stats(
    filters: Optional[Filters[PaymentFilters]] = None,
    user_id: Optional[str] = None,
    conn: Optional[Connection] = None,
) -> list[PaymentWalletStats]:

    if not filters:
        filters = Filters()

    where_stmts = [
        "(wallets.deleted = false OR wallets.deleted is NULL)",
        """
        (
            (apipayments.status = 'success' AND apipayments.amount > 0)
            OR (
                apipayments.status IN ('success', 'pending')
                AND apipayments.amount < 0
                )
        )
        """,
    ]
    if user_id:
        only_user_wallets = await _only_user_wallets_statement(user_id, conn=conn)
        where_stmts.append(only_user_wallets)

    clauses = filters.where(where_stmts)

    data = await (conn or db).fetchall(
        query=f"""
            SELECT apipayments.wallet_id,
                    MAX(wallets.name) AS wallet_name,
                    MAX(wallets.user) AS user_id,
                    COUNT(*) as payments_count,
                    SUM(apipayments.amount - ABS(apipayments.fee)) AS balance
            FROM wallets
            LEFT JOIN apipayments ON apipayments.wallet_id = wallets.id
            {clauses}
            GROUP BY apipayments.wallet_id
            ORDER BY payments_count
        """,
        values=filters.values(),
        model=PaymentWalletStats,
    )

    return data


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


async def mark_webhook_sent(payment_hash: str, status: str) -> None:
    await db.execute(
        """
        UPDATE apipayments SET webhook_status = :status
        WHERE payment_hash = :hash
        """,
        {"status": status, "hash": payment_hash},
    )


async def _only_user_wallets_statement(
    user_id: str, conn: Optional[Connection] = None
) -> str:
    wallet_ids = await get_wallets_ids(user_id=user_id, conn=conn) or [
        "no-wallets-for-user"
    ]
    # wallet ids are safe to use in sql queries
    wallet_ids_str = [f"'{w}'" for w in wallet_ids]
    return f""" wallet_id IN ({", ".join(wallet_ids_str)}) """
