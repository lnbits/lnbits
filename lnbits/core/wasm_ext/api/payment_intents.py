from __future__ import annotations

import json
import re
from contextlib import asynccontextmanager
from typing import Any
from uuid import uuid4
from weakref import WeakSet

from bolt11 import decode as bolt11_decode
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from lnbits.core.crud.payments import get_standalone_payment
from lnbits.core.models.lnurl import CreateLnurlPayment
from lnbits.core.services.lnurl import fetch_lnurl_pay_request
from lnbits.core.services.payments import (
    check_payment_status,
    fee_reserve_total,
    service_fee,
)
from lnbits.core.wasm_ext.storage import crud as storage_crud
from lnbits.db import SQLITE, Compat, Connection, Database

from .lnurl import lnurl_for_core, lnurl_pay_response_text, lnurl_payment_unit_for_core

_PAYMENT_INTENTS_TABLE = "lnbits_payment_intents"
_PAYMENT_INTENT_MANUAL_AUDIT_TABLE = "lnbits_payment_intent_manual_audit"
_SQL_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_PAYMENT_INTENT_STATES = {"pending", "processing", "paid", "failed", "unknown"}
_MAX_DB_INT = 9_223_372_036_854_775_807
_initialized_databases: WeakSet[Database] = WeakSet()


class PaymentIntentResolutionConflictError(ValueError):
    pass


async def create_or_get_payment_intent(
    extension_id: str,
    wallet_id: str,
    owner_id: str,
    request: Any,
    max_amount_msat: int | float | None = None,
) -> dict[str, Any]:
    """Persist one immutable wallet operation before any external payment work."""

    destination = request.destination.strip()
    if not destination:
        raise ValueError("A payment destination is required.")
    amount_msat = request.amount_msat
    if amount_msat <= 0 or amount_msat > _MAX_DB_INT:
        raise ValueError("Payment amount is out of range.")
    if amount_msat + request.max_fee_msat > _MAX_DB_INT:
        raise ValueError("Payment reservation exceeds the supported amount.")
    if max_amount_msat is not None and amount_msat > max_amount_msat:
        raise PermissionError("Payment exceeds the wallet's background payment grant.")
    if request.max_fee_msat < fee_reserve_total(amount_msat):
        raise PermissionError(
            "Fee ceiling is below the maximum allowed by the wallet configuration."
        )

    payment_request = _bolt11_destination(destination)
    payment_hash: str | None = None
    if payment_request:
        payment_request = payment_request.lower()
        try:
            invoice = bolt11_decode(payment_request)
        except Exception as exc:
            raise ValueError("Payment destination invoice is invalid.") from exc
        payment_hash = str(invoice.payment_hash or "").lower()
        if int(invoice.amount_msat or 0) != amount_msat or not _is_payment_hash(
            payment_hash
        ):
            raise ValueError(
                "Payment destination invoice does not match the requested amount."
            )
    elif not _is_lnurl(destination):
        raise ValueError("Payment destination must be a BOLT11 invoice or an LNURL.")

    request_data = {
        "destination": destination,
        "amount_msat": amount_msat,
        "max_fee_msat": request.max_fee_msat,
        "description": request.description,
    }
    return await _reserve_payment_intent(
        extension_id=extension_id,
        wallet_id=wallet_id,
        idempotency_key=request.idempotency_key,
        request_data=request_data,
        destination=destination,
        payment_request=payment_request,
        payment_hash=payment_hash,
        amount_msat=amount_msat,
        max_fee_msat=request.max_fee_msat,
        owner_id=owner_id,
        retry_failed=request.retry_failed,
    )


async def get_payment_intent(
    extension_id: str, wallet_id: str, idempotency_key: str, owner_id: str
) -> dict[str, Any] | None:
    database = await _database(extension_id)
    table = _table_ref(database, _PAYMENT_INTENTS_TABLE)
    async with database.connect() as conn:
        return await _raw_fetchone(
            conn,
            f"""
            SELECT * FROM {table}
            WHERE wallet_id = :wallet_id AND idempotency_key = :idempotency_key
                AND owner_user_id = :owner_id
            """,  # noqa: S608
            {
                "wallet_id": wallet_id,
                "idempotency_key": idempotency_key,
                "owner_id": owner_id,
            },
        )


async def claim_payment_intent(
    extension_id: str, intent_id: str
) -> tuple[dict[str, Any] | None, bool]:
    database = await _database(extension_id)
    table = _table_ref(database, _PAYMENT_INTENTS_TABLE)
    async with database.connect() as conn:
        result = await conn.execute(
            f"""
            UPDATE {table}
            SET status = 'processing', updated_at = {database.timestamp_now}
            WHERE id = :id AND status = 'pending' AND attempted = false
            """,  # noqa: S608
            {"id": intent_id},
        )
        row = await conn.fetchone(
            f"SELECT * FROM {table} WHERE id = :id",  # noqa: S608
            {"id": intent_id},
        )
    return row, bool(result.rowcount)


async def save_payment_intent_invoice(
    extension_id: str,
    intent_id: str,
    payment_request: str,
    payment_hash: str,
) -> bool:
    database = await _database(extension_id)
    table = _table_ref(database, _PAYMENT_INTENTS_TABLE)
    async with database.connect() as conn:
        result = await conn.execute(
            f"""
            UPDATE {table}
            SET payment_request = :payment_request,
                payment_hash = :payment_hash,
                checking_id = :checking_id,
                updated_at = {database.timestamp_now}
            WHERE id = :id AND status = 'processing' AND attempted = false
            """,  # noqa: S608
            {
                "id": intent_id,
                "payment_request": payment_request,
                "payment_hash": payment_hash,
                "checking_id": payment_hash,
            },
        )
    return bool(result.rowcount)


async def mark_payment_intent_attempted(extension_id: str, intent_id: str) -> bool:
    database = await _database(extension_id)
    table = _table_ref(database, _PAYMENT_INTENTS_TABLE)
    async with database.connect() as conn:
        result = await conn.execute(
            f"""
            UPDATE {table}
            SET attempted = true, updated_at = {database.timestamp_now}
            WHERE id = :id AND status = 'processing'
                AND attempted = false AND payment_request IS NOT NULL
            """,  # noqa: S608
            {"id": intent_id},
        )
    return bool(result.rowcount)


async def set_payment_intent_status(
    extension_id: str,
    intent_id: str,
    status: str,
    *,
    fee_msat: int = 0,
    error: str | None = None,
    attempted: bool | None = None,
    expected_status: str | None = None,
    expected_attempted: bool | None = None,
) -> dict[str, Any] | None:
    if status not in _PAYMENT_INTENT_STATES:
        raise ValueError("Invalid payment intent status.")
    database = await _database(extension_id)
    intents = _table_ref(database, _PAYMENT_INTENTS_TABLE)
    async with database.connect() as conn:
        async with _intent_transaction(conn):
            row = await _raw_fetchone(
                conn,
                f"SELECT * FROM {intents} WHERE id = :id{_for_update(conn.type)}",  # noqa: S608
                {"id": intent_id},
            )
            if not row:
                return None
            if expected_status is not None and row["status"] != expected_status:
                return row
            if (
                expected_attempted is not None
                and bool(row["attempted"]) != expected_attempted
            ):
                return row
            if row["status"] in {"paid", "failed"}:
                return row
            if row["status"] == "unknown" and status == "pending":
                return row
            if status == "paid" and fee_msat > row["max_fee_msat"]:
                status = "unknown"
                error = (
                    "Observed fee exceeded the reserved ceiling; "
                    "operator review required."
                )
            await conn.conn.execute(
                text(f"""
                    UPDATE {intents}
                    SET status = :status, fee_msat = :fee_msat,
                        error = :error,
                        manual_reconciliation = CASE
                            WHEN :status = 'unknown' THEN true
                            ELSE manual_reconciliation
                        END,
                        attempted = COALESCE(:attempted, attempted),
                        updated_at = {database.timestamp_now}
                    WHERE id = :id
                """),  # noqa: S608
                {
                    "status": status,
                    "fee_msat": fee_msat if status in {"paid", "unknown"} else 0,
                    "error": error,
                    "attempted": attempted,
                    "id": intent_id,
                },
            )
            return await _raw_fetchone(
                conn,
                f"SELECT * FROM {intents} WHERE id = :id",  # noqa: S608
                {"id": intent_id},
            )


async def reconcile_payment_intent(
    extension_id: str, intent: dict[str, Any]
) -> dict[str, Any]:
    if intent["status"] in {"paid", "failed"}:
        return intent
    if intent["manual_reconciliation"]:
        return intent
    if not intent["attempted"]:
        return (
            await set_payment_intent_status(
                extension_id,
                intent["id"],
                "failed",
                error=(
                    "Interrupted before payment started; an explicit retry "
                    "is available."
                ),
                expected_status="processing",
                expected_attempted=False,
            )
            or intent
        )
    payment = (
        await get_standalone_payment(
            intent["payment_hash"], wallet_id=intent["wallet_id"]
        )
        if intent["payment_hash"]
        else None
    )
    if not payment:
        return (
            await set_payment_intent_status(
                extension_id,
                intent["id"],
                "unknown",
                error=(
                    "Payment record is unavailable; operator reconciliation "
                    "is required."
                ),
            )
            or intent
        )
    if payment.success:
        return (
            await set_payment_intent_status(
                extension_id,
                intent["id"],
                "paid",
                fee_msat=abs(payment.fee),
            )
            or intent
        )
    if payment.failed:
        return (
            await set_payment_intent_status(
                extension_id, intent["id"], "failed", error="Payment failed."
            )
            or intent
        )
    try:
        status = await check_payment_status(payment)
    except Exception:
        return (
            await set_payment_intent_status(
                extension_id,
                intent["id"],
                "unknown",
                error=(
                    "Payment status could not be confirmed; reconcile before retrying."
                ),
            )
            or intent
        )
    if status.success:
        actual_fee_msat = abs(status.fee_msat or 0) + service_fee(
            abs(payment.amount), internal=payment.is_internal
        )
        return (
            await set_payment_intent_status(
                extension_id,
                intent["id"],
                "paid",
                fee_msat=actual_fee_msat,
            )
            or intent
        )
    if status.failed:
        return (
            await set_payment_intent_status(
                extension_id, intent["id"], "failed", error="Payment failed."
            )
            or intent
        )
    return (
        await set_payment_intent_status(extension_id, intent["id"], "pending") or intent
    )


async def resolve_payment_intent_invoice(
    intent: dict[str, Any],
) -> tuple[str, str, str]:
    if intent["payment_request"]:
        return intent["payment_request"], intent["payment_hash"], ""

    response, action = await fetch_lnurl_pay_request(
        data=CreateLnurlPayment(
            lnurl=lnurl_for_core(intent["destination"]),
            amount=int(intent["amount_msat"]),
            unit=lnurl_payment_unit_for_core("sat"),
            comment=None,
            internal_memo=intent.get("description") or "WASM wallet payment",
        ),
        wallet=None,
    )
    payment_request = str(action.pr)
    try:
        invoice = bolt11_decode(payment_request)
    except Exception as exc:
        raise ValueError("LNURL returned an invalid invoice.") from exc
    payment_hash = str(invoice.payment_hash or "").lower()
    if int(invoice.amount_msat or 0) != intent["amount_msat"] or not _is_payment_hash(
        payment_hash
    ):
        raise ValueError("Resolved invoice amount does not match the intent.")
    return payment_request, payment_hash, lnurl_pay_response_text(response)


async def get_manual_payment_intents(
    extension_id: str, wallet_id: str, *, limit: int = 100
) -> list[dict[str, Any]]:
    database = await _database(extension_id)
    intents = _table_ref(database, _PAYMENT_INTENTS_TABLE)
    audit = _table_ref(database, _PAYMENT_INTENT_MANUAL_AUDIT_TABLE)
    async with database.connect() as conn:
        rows = await conn.fetchall(
            f"""SELECT i.id, i.wallet_id, i.idempotency_key, i.destination,
                    i.payment_hash, i.payment_request, i.amount_msat,
                    i.max_fee_msat, i.fee_msat, i.status, i.attempted, i.error,
                    a.actor_id AS operator_actor_id,
                    a.action AS operator_action,
                    a.note AS operator_note,
                    a.created_at AS operator_action_at
                FROM {intents} i
                LEFT JOIN {audit} a ON a.id = (
                    SELECT id FROM {audit} WHERE intent_id = i.id
                    ORDER BY created_at DESC LIMIT 1
                )
                WHERE i.wallet_id = :wallet_id
                    AND (i.status = 'unknown'
                        OR i.manual_reconciliation = true OR a.id IS NOT NULL)
                ORDER BY i.updated_at DESC LIMIT :limit""",  # noqa: S608
            {"wallet_id": wallet_id, "limit": limit},
        )
    return list(rows)


async def get_payment_intent_by_id(
    extension_id: str, wallet_id: str, intent_id: str
) -> dict[str, Any] | None:
    database = await _database(extension_id)
    intents = _table_ref(database, _PAYMENT_INTENTS_TABLE)
    async with database.connect() as conn:
        return await _raw_fetchone(
            conn,
            f"SELECT * FROM {intents} WHERE wallet_id = :wallet_id AND id = :id",  # noqa: S608
            {"wallet_id": wallet_id, "id": intent_id},
        )


async def resolve_manual_payment_intent(
    extension_id: str,
    wallet_id: str,
    intent_id: str,
    actor_id: str,
    status: str,
    fee_msat: int,
    note: str,
) -> dict[str, Any]:
    if status not in {"paid", "failed"}:
        raise ValueError("Manual resolution must be paid or failed.")
    if fee_msat < 0:
        raise ValueError("Observed fee cannot be negative.")
    note = note.strip()
    if not note or len(note) > 512:
        raise ValueError("A manual reconciliation note is required.")
    if status == "failed" and fee_msat:
        raise ValueError("A failed payment cannot have a fee.")

    database = await _database(extension_id)
    intents = _table_ref(database, _PAYMENT_INTENTS_TABLE)
    audit = _table_ref(database, _PAYMENT_INTENT_MANUAL_AUDIT_TABLE)
    async with database.connect() as conn:
        async with _intent_transaction(conn):
            intent = await _raw_fetchone(
                conn,
                f"SELECT * FROM {intents} WHERE id = :id AND wallet_id = :wallet_id"  # noqa: S608
                f"{_for_update(conn.type)}",
                {"id": intent_id, "wallet_id": wallet_id},
            )
            if not intent or intent["status"] != "unknown":
                raise PaymentIntentResolutionConflictError(
                    "Only an unresolved manual payment intent can be resolved."
                )
            await conn.conn.execute(
                text(f"""UPDATE {intents}
                    SET status = :status, fee_msat = :fee_msat,
                        error = NULL, updated_at = {database.timestamp_now}
                    WHERE id = :id"""),  # noqa: S608
                {
                    "status": status,
                    "fee_msat": fee_msat if status == "paid" else 0,
                    "id": intent_id,
                },
            )
            await conn.conn.execute(
                text(f"""INSERT INTO {audit}
                    (id, intent_id, wallet_id, actor_id, action, resolved_status,
                     fee_msat, note)
                    VALUES (:id, :intent_id, :wallet_id, :actor_id, 'resolve',
                        :status, :fee_msat, :note)"""),  # noqa: S608
                {
                    "id": uuid4().hex,
                    "intent_id": intent_id,
                    "wallet_id": wallet_id,
                    "actor_id": actor_id,
                    "status": status,
                    "fee_msat": fee_msat if status == "paid" else 0,
                    "note": note,
                },
            )
            return await _raw_fetchone(
                conn,
                f"SELECT * FROM {intents} WHERE id = :id",  # noqa: S608
                {"id": intent_id},
            )


async def record_payment_intent_operator_action(
    extension_id: str,
    intent_id: str,
    wallet_id: str,
    actor_id: str,
    action: str,
    status: str,
    note: str,
) -> None:
    if action not in {"retry_requested", "retry_result"}:
        raise ValueError("Invalid payment intent operator action.")
    database = await _database(extension_id)
    audit = _table_ref(database, _PAYMENT_INTENT_MANUAL_AUDIT_TABLE)
    async with database.connect() as conn:
        await conn.execute(
            f"""INSERT INTO {audit}
                (id, intent_id, wallet_id, actor_id, action, resolved_status,
                 fee_msat, note)
                VALUES (:id, :intent_id, :wallet_id, :actor_id, :action,
                    :status, 0, :note)""",  # noqa: S608
            {
                "id": uuid4().hex,
                "intent_id": intent_id,
                "wallet_id": wallet_id,
                "actor_id": actor_id,
                "action": action,
                "status": status,
                "note": note,
            },
        )


async def _reserve_payment_intent(
    *,
    extension_id: str,
    wallet_id: str,
    idempotency_key: str,
    request_data: dict[str, Any],
    destination: str,
    payment_request: str | None,
    payment_hash: str | None,
    amount_msat: int,
    max_fee_msat: int,
    owner_id: str,
    retry_failed: bool,
) -> dict[str, Any]:
    database = await _database(extension_id)
    intents = _table_ref(database, _PAYMENT_INTENTS_TABLE)
    request_json = json.dumps(request_data, sort_keys=True, separators=(",", ":"))

    try:
        async with database.connect() as conn:
            async with _intent_transaction(conn):
                existing = await _raw_fetchone(
                    conn,
                    f"""
                    SELECT * FROM {intents}
                    WHERE wallet_id = :wallet_id AND idempotency_key = :key
                        AND owner_user_id = :owner_id
                    {_for_update(conn.type)}
                    """,  # noqa: S608
                    {
                        "wallet_id": wallet_id,
                        "key": idempotency_key,
                        "owner_id": owner_id,
                    },
                )
                if existing:
                    return await _existing_intent(
                        conn, database, existing, request_json, retry_failed
                    )
                intent_id = uuid4().hex
                await conn.conn.execute(
                    text(f"""
                        INSERT INTO {intents}
                            (id, wallet_id, owner_user_id, idempotency_key,
                             destination, description, payment_request,
                             payment_hash, checking_id, amount_msat,
                             max_fee_msat, fee_msat, status, attempted,
                             manual_reconciliation, request_json, error)
                        VALUES
                            (:id, :wallet_id, :owner_user_id, :idempotency_key,
                             :destination, :description, :payment_request,
                             :payment_hash, :checking_id, :amount_msat,
                             :max_fee_msat, 0, 'pending', false, false,
                             :request_json, NULL)
                    """),  # noqa: S608
                    {
                        "id": intent_id,
                        "wallet_id": wallet_id,
                        "owner_user_id": owner_id,
                        "idempotency_key": idempotency_key,
                        "destination": destination,
                        "description": request_data.get("description"),
                        "payment_request": payment_request,
                        "payment_hash": payment_hash,
                        "checking_id": payment_hash,
                        "amount_msat": amount_msat,
                        "max_fee_msat": max_fee_msat,
                        "request_json": request_json,
                    },
                )
                return await _raw_fetchone(
                    conn,
                    f"SELECT * FROM {intents} WHERE id = :id",  # noqa: S608
                    {"id": intent_id},
                )
    except IntegrityError as exc:
        row = await get_payment_intent(
            extension_id, wallet_id, idempotency_key, owner_id
        )
        if row and row["request_json"] == request_json:
            return row
        raise ValueError("An intent already exists for this idempotency key.") from exc


async def _existing_intent(
    conn: Any,
    database: Database,
    row: dict[str, Any],
    request_json: str,
    retry_failed: bool,
) -> dict[str, Any]:
    if row["request_json"] != request_json:
        raise ValueError("Idempotency key was already used for different payment data.")
    if not retry_failed or row["status"] != "failed":
        return row
    is_lnurl = _is_lnurl(row["destination"])
    if row["attempted"] and not is_lnurl:
        raise ValueError(
            "A failed BOLT11 intent cannot be retried with the same invoice."
        )
    intents = _table_ref(database, _PAYMENT_INTENTS_TABLE)
    await conn.conn.execute(
        text(f"""
            UPDATE {intents}
            SET status = 'pending', payment_request = :payment_request,
                payment_hash = :payment_hash, checking_id = :checking_id,
                fee_msat = 0, attempted = false, manual_reconciliation = false,
                error = NULL, updated_at = {database.timestamp_now}
            WHERE id = :id AND status = 'failed'
        """),  # noqa: S608
        {
            "payment_request": (None if is_lnurl else row["payment_request"]),
            "payment_hash": (None if is_lnurl else row["payment_hash"]),
            "checking_id": (None if is_lnurl else row["checking_id"]),
            "id": row["id"],
        },
    )
    return await _raw_fetchone(
        conn,
        f"SELECT * FROM {intents} WHERE id = :id",  # noqa: S608
        {"id": row["id"]},
    )


def _is_payment_hash(value: str) -> bool:
    return len(value) == 64 and all(c in "0123456789abcdefABCDEF" for c in value)


def _bolt11_destination(destination: str) -> str | None:
    payment_request = destination.strip()
    if payment_request.lower().startswith("lightning:"):
        payment_request = payment_request.split(":", 1)[1].strip()
    if payment_request.lower().startswith(("lnbc", "lntb", "lnbcrt")):
        return payment_request
    return None


def _is_lnurl(destination: str) -> bool:
    value = destination.strip().lower()
    if value.startswith("lightning:"):
        value = value.split(":", 1)[1].strip()
    if not value:
        return False
    try:
        lnurl_for_core(value)
    except Exception:
        return False
    return True


async def _database(extension_id: str) -> Database:
    if not _SQL_IDENTIFIER_RE.fullmatch(extension_id):
        raise ValueError("Invalid WASM extension ID.")
    database = storage_crud._database(extension_id)
    if database not in _initialized_databases:
        async with database.connect() as conn:
            if database not in _initialized_databases:
                await _create_payment_intent_tables(conn)
                _initialized_databases.add(database)
    return database


async def _create_payment_intent_tables(conn: Connection) -> None:
    intents = _table_ref(conn, _PAYMENT_INTENTS_TABLE)
    audit = _table_ref(conn, _PAYMENT_INTENT_MANUAL_AUDIT_TABLE)
    await conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {intents} (
            id TEXT PRIMARY KEY,
            wallet_id TEXT NOT NULL,
            owner_user_id TEXT NOT NULL,
            idempotency_key TEXT NOT NULL,
            destination TEXT NOT NULL,
            description TEXT,
            payment_request TEXT,
            payment_hash TEXT,
            checking_id TEXT,
            amount_msat {conn.big_int} NOT NULL,
            max_fee_msat {conn.big_int} NOT NULL,
            fee_msat {conn.big_int} NOT NULL DEFAULT 0,
            status TEXT NOT NULL,
            attempted BOOLEAN NOT NULL DEFAULT false,
            manual_reconciliation BOOLEAN NOT NULL DEFAULT false,
            request_json TEXT NOT NULL,
            error TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT {conn.timestamp_now},
            updated_at TIMESTAMP NOT NULL DEFAULT {conn.timestamp_now},
            UNIQUE (wallet_id, idempotency_key)
        )
    """)
    await conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {audit} (
            id TEXT PRIMARY KEY,
            intent_id TEXT NOT NULL,
            wallet_id TEXT NOT NULL,
            actor_id TEXT NOT NULL,
            action TEXT NOT NULL,
            resolved_status TEXT NOT NULL,
            fee_msat {conn.big_int} NOT NULL DEFAULT 0,
            note TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT {conn.timestamp_now}
        )
    """)


def _table_ref(database: Compat, name: str) -> str:
    if not _SQL_IDENTIFIER_RE.fullmatch(name):
        raise ValueError("Invalid WASM payment intent table name.")
    schema = database.schema
    if schema:
        if not _SQL_IDENTIFIER_RE.fullmatch(schema):
            raise ValueError("Invalid WASM payment intent schema.")
        return f"{schema}.{name}"
    return name


async def _raw_fetchone(conn: Any, query: str, values: dict[str, Any]) -> Any:
    result = await conn.conn.execute(text(query), values)
    row = result.mappings().first()
    result.close()
    return row


@asynccontextmanager
async def _intent_transaction(conn: Any):
    if conn.type != SQLITE:
        async with conn.conn.begin():
            yield
        return
    # Extension SQLite files are attached under a schema alias; an immediate
    # transaction attempts to lock the same file twice.
    await conn.conn.exec_driver_sql("BEGIN")
    try:
        yield
    except BaseException:
        await conn.conn.rollback()
        raise
    else:
        await conn.conn.commit()


def _for_update(db_type: str | None) -> str:
    return "" if db_type == SQLITE else " FOR UPDATE"
