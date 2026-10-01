from __future__ import annotations

import json
import re
from contextlib import asynccontextmanager
from typing import Any
from uuid import uuid4

from bolt11 import decode as bolt11_decode
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from lnbits.core.crud.payments import get_standalone_payment
from lnbits.core.models.payments import Payment
from lnbits.core.wasm_ext.storage import crud as storage_crud
from lnbits.core.wasm_ext.storage.crud import (
    _fence_authoritative_write,
    _initialize_database_once,
    storage_get_immutable_row,
)
from lnbits.db import SQLITE, Database

_PAYMENT_INTENTS_TABLE = "lnbits_payment_intents"
_PAYMENT_INTENT_GROUPS_TABLE = "lnbits_payment_intent_groups"
_PAYMENT_INTENT_MANUAL_AUDIT_TABLE = "lnbits_payment_intent_manual_audit"
_SQL_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_PAYMENT_INTENT_STATES = {"pending", "processing", "paid", "failed", "unknown"}
_MAX_DB_INT = 9_223_372_036_854_775_807


class PaymentIntentResolutionConflictError(ValueError):
    pass


async def create_or_get_payment_intent(  # noqa: C901
    extension_id: str,
    wallet_id: str,
    owner_id: str,
    request: Any,
    max_amount_msat: int | float | None = None,
) -> dict[str, Any]:
    """Persist and reserve a verified intent before resolving its destination."""
    funding_payments: dict[str, Payment] = {}
    funding_msat = 0
    for funding_hash in sorted(request.funding_payment_hashes):
        payment = await get_standalone_payment(
            funding_hash, incoming=True, wallet_id=wallet_id
        )
        if (
            not payment
            or not payment.success
            or payment.extension != extension_id
            or payment.amount <= 0
            or _payment_scope_id(payment, extension_id) != request.scope_id
        ):
            raise PermissionError("Scoped funding contains an unverified payment.")
        funding_payments[funding_hash] = payment
        funding_msat += payment.amount
        if funding_msat > _MAX_DB_INT:
            raise PermissionError("Scoped funding exceeds the supported amount.")

    manual_error: str | None = None
    if request.purpose == "payout":
        record = await storage_get_immutable_row(
            extension_id,
            request.record_table,
            request.record_id,
            owner_id,
        )
        if (
            not record
            or record.get("scope_id") != request.scope_id
            or _normalized_hashes(record.get("funding_payment_hashes"))
            != sorted(request.funding_payment_hashes)
        ):
            raise PermissionError("Payout requires a matching immutable record.")
        recipient_hash = record.get("recipient_payment_hash")
        amount_msat = record.get("amount_msat")
        recipient_payment = (
            funding_payments.get(recipient_hash.lower())
            if isinstance(recipient_hash, str)
            else None
        )
        if (
            not isinstance(recipient_hash, str)
            or not isinstance(amount_msat, int)
            or isinstance(amount_msat, bool)
            or amount_msat <= 0
            or not recipient_payment
        ):
            raise PermissionError("Immutable record has no valid payment recipient.")
        destination = _payment_extra_value(
            recipient_payment, extension_id, "payment_destination"
        )
        record_table = request.record_table
        record_id = request.record_id
        source_payment_hash = None
        reference_id = f"{record_table}/{record_id}"
    else:
        source_payment_hash = request.source_payment_hash
        source_payment = funding_payments.get(source_payment_hash)
        if not source_payment:
            raise PermissionError("Refund source is not in verified scoped funding.")
        amount_msat = source_payment.amount
        destination = _payment_extra_value(
            source_payment, extension_id, "refund_destination"
        )
        record_table = None
        record_id = None
        reference_id = source_payment_hash

    if not isinstance(destination, str) or not destination.strip():
        if request.purpose != "refund":
            raise PermissionError(
                "A destination bound to the incoming payment is required."
            )
        destination = ""
        manual_error = (
            "Refund destination is missing; manual reconciliation is required."
        )
    else:
        destination = destination.strip()
    if amount_msat > funding_msat:
        raise PermissionError("Intent amount exceeds verified scoped funding.")
    if amount_msat > _MAX_DB_INT:
        raise PermissionError("Intent amount exceeds the supported amount.")
    if max_amount_msat is not None and amount_msat > max_amount_msat:
        raise PermissionError("Payment exceeds the wallet's background payment grant.")

    if amount_msat + request.max_fee_msat > _MAX_DB_INT:
        raise PermissionError("Intent reservation exceeds the supported amount.")

    payment_request = _bolt11_destination(destination) if destination else None
    if payment_request:
        payment_request = payment_request.lower()
    payment_hash: str | None = None
    if payment_request:
        try:
            invoice = bolt11_decode(payment_request)
        except Exception:
            manual_error = (
                "Bound invoice is invalid; manual reconciliation is required."
            )
            payment_request = None
        else:
            payment_hash = str(invoice.payment_hash or "").lower()
            if int(invoice.amount_msat or 0) != amount_msat or not _is_payment_hash(
                payment_hash
            ):
                manual_error = (
                    "Bound invoice amount or payment hash is invalid; "
                    "manual reconciliation is required."
                )
                payment_request = None
                payment_hash = None
    elif destination and not _is_lnurl(destination):
        manual_error = (
            "Intent destination is invalid; manual reconciliation is required."
        )

    funding_hashes = sorted(request.funding_payment_hashes)
    request_data = {
        "purpose": request.purpose,
        "scope_id": request.scope_id,
        "funding_payment_hashes": funding_hashes,
        "max_fee_msat": request.max_fee_msat,
        "record_table": record_table,
        "record_id": record_id,
        "source_payment_hash": source_payment_hash,
        "destination": destination,
        "amount_msat": amount_msat,
        "manual_error": manual_error,
    }
    return await _reserve_payment_intent(
        extension_id=extension_id,
        wallet_id=wallet_id,
        idempotency_key=request.idempotency_key,
        request_data=request_data,
        funding_hashes=funding_hashes,
        funding_msat=funding_msat,
        destination=destination,
        payment_request=payment_request,
        payment_hash=payment_hash,
        amount_msat=amount_msat,
        max_fee_msat=request.max_fee_msat,
        purpose=request.purpose,
        scope_id=request.scope_id,
        reference_id=reference_id,
        record_table=record_table,
        record_id=record_id,
        source_payment_hash=source_payment_hash,
        owner_id=owner_id,
        retry_failed=request.retry_failed,
        manual_error=manual_error,
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
        await _fence_authoritative_write(extension_id, conn)
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
        await _fence_authoritative_write(extension_id, conn)
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
        await _fence_authoritative_write(extension_id, conn)
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
    groups = _table_ref(database, _PAYMENT_INTENT_GROUPS_TABLE)
    async with database.connect() as conn:
        async with _intent_transaction(conn):
            # Guest transitions are fenced; host reconciliation without a room
            # context can still settle an already-issued payment after failover.
            await _fence_authoritative_write(extension_id, conn)
            row = await _raw_fetchone(
                conn,
                f"SELECT * FROM {intents} WHERE id = :id{_for_update(conn.type)}",  # noqa: S608
                {"id": intent_id},
            )
            if not row:
                return None
            if not _matches_expected_intent_state(
                row, expected_status, expected_attempted
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
            if status in {"paid", "failed"} and row["reserved_msat"]:
                group = await _raw_fetchone(
                    conn,
                    f"""
                    SELECT * FROM {groups}
                    WHERE wallet_id = :wallet_id AND scope_id = :scope_id
                    {_for_update(conn.type)}
                    """,  # noqa: S608
                    {"wallet_id": row["wallet_id"], "scope_id": row["scope_id"]},
                )
                if not group:
                    raise RuntimeError("Payment intent funding reservation is missing.")
                reserved = max(0, group["reserved_msat"] - row["reserved_msat"])
                spent = group["spent_msat"]
                if status == "paid":
                    spent += row["amount_msat"] + fee_msat
                await conn.conn.execute(
                    text(f"""
                        UPDATE {groups}
                        SET reserved_msat = :reserved_msat,
                            spent_msat = :spent_msat,
                            updated_at = {database.timestamp_now}
                        WHERE wallet_id = :wallet_id AND scope_id = :scope_id
                    """),  # noqa: S608
                    {
                        "reserved_msat": reserved,
                        "spent_msat": spent,
                        "wallet_id": row["wallet_id"],
                        "scope_id": row["scope_id"],
                    },
                )
                await conn.conn.execute(
                    text(f"""
                        UPDATE {intents}
                        SET status = :status, fee_msat = :fee_msat,
                            reserved_msat = 0, error = :error,
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
            else:
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
    from lnbits.core.services.payments import check_payment_status, service_fee

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


async def _reserve_payment_intent(  # noqa: C901
    *,
    extension_id: str,
    wallet_id: str,
    idempotency_key: str,
    request_data: dict[str, Any],
    funding_hashes: list[str],
    funding_msat: int,
    destination: str,
    payment_request: str | None,
    payment_hash: str | None,
    amount_msat: int,
    max_fee_msat: int,
    purpose: str,
    scope_id: str,
    reference_id: str,
    record_table: str | None,
    record_id: str | None,
    source_payment_hash: str | None,
    owner_id: str,
    retry_failed: bool,
    manual_error: str | None,
) -> dict[str, Any]:
    from lnbits.core.services.payments import fee_reserve_total

    database = await _database(extension_id)
    intents = _table_ref(database, _PAYMENT_INTENTS_TABLE)
    groups = _table_ref(database, _PAYMENT_INTENT_GROUPS_TABLE)
    request_json = json.dumps(request_data, sort_keys=True, separators=(",", ":"))
    hashes_json = json.dumps(funding_hashes, separators=(",", ":"))
    reserve_msat = amount_msat + max_fee_msat

    try:
        async with database.connect() as conn:
            async with _intent_transaction(conn):
                await _fence_authoritative_write(extension_id, conn)
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
                        conn,
                        database,
                        existing,
                        request_json,
                        retry_failed,
                        reserve_msat,
                    )

                await conn.conn.execute(
                    text(f"""
                        INSERT INTO {groups}
                            (wallet_id, scope_id, funding_hashes_json,
                             funding_msat, reserved_msat, spent_msat)
                        VALUES (:wallet_id, :scope_id, :hashes, :funding_msat, 0, 0)
                        ON CONFLICT (wallet_id, scope_id) DO NOTHING
                    """),  # noqa: S608
                    {
                        "wallet_id": wallet_id,
                        "scope_id": scope_id,
                        "hashes": hashes_json,
                        "funding_msat": funding_msat,
                    },
                )
                group = await _raw_fetchone(
                    conn,
                    f"""
                    SELECT * FROM {groups}
                    WHERE wallet_id = :wallet_id AND scope_id = :scope_id
                    {_for_update(conn.type)}
                    """,  # noqa: S608
                    {"wallet_id": wallet_id, "scope_id": scope_id},
                )
                if not group:
                    raise RuntimeError("Could not reserve scoped funds.")
                old_hashes = json.loads(group["funding_hashes_json"])
                if not set(old_hashes).issubset(funding_hashes):
                    raise PermissionError(
                        "Scoped funding cannot remove verified payments."
                    )
                if old_hashes != funding_hashes:
                    if group["funding_msat"] > funding_msat:
                        raise PermissionError("Scoped funding total cannot decrease.")
                    await conn.conn.execute(
                        text(f"""
                            UPDATE {groups}
                            SET funding_hashes_json = :hashes,
                                funding_msat = :funding_msat,
                                updated_at = {database.timestamp_now}
                            WHERE wallet_id = :wallet_id AND scope_id = :scope_id
                        """),  # noqa: S608
                        {
                            "hashes": hashes_json,
                            "funding_msat": funding_msat,
                            "wallet_id": wallet_id,
                            "scope_id": scope_id,
                        },
                    )
                    group["funding_msat"] = funding_msat
                    group["funding_hashes_json"] = hashes_json

                reference = await _find_reference_intent(
                    conn,
                    intents,
                    wallet_id,
                    purpose,
                    record_table,
                    record_id,
                    source_payment_hash,
                )
                if reference:
                    if reference["request_json"] != request_json:
                        raise ValueError("An intent already exists for this reference.")
                    return reference
                if max_fee_msat < fee_reserve_total(amount_msat):
                    raise PermissionError(
                        "Fee ceiling is below the maximum allowed by the "
                        "wallet configuration."
                    )
                if (
                    group["spent_msat"] + group["reserved_msat"] + reserve_msat
                    > group["funding_msat"]
                ):
                    raise PermissionError("Scoped funds are already fully reserved.")

                intent_id = uuid4().hex
                await conn.conn.execute(
                    text(f"""
                        UPDATE {groups}
                        SET reserved_msat = reserved_msat + :reserve_msat,
                        updated_at = {database.timestamp_now}
                        WHERE wallet_id = :wallet_id AND scope_id = :scope_id
                    """),  # noqa: S608
                    {
                        "reserve_msat": reserve_msat,
                        "wallet_id": wallet_id,
                        "scope_id": scope_id,
                    },
                )
                await conn.conn.execute(
                    text(f"""
                        INSERT INTO {intents}
                            (id, wallet_id, owner_user_id, idempotency_key, purpose,
                             scope_id, reference_id, record_table, record_id,
                             source_payment_hash, destination, payment_request,
                             payment_hash, checking_id, amount_msat, max_fee_msat,
                             fee_msat, reserved_msat, status, attempted,
                             manual_reconciliation, request_json, error)
                        VALUES
                            (:id, :wallet_id, :owner_user_id, :idempotency_key,
                             :purpose, :scope_id, :reference_id, :record_table,
                             :record_id, :source_payment_hash, :destination,
                             :payment_request, :payment_hash, :checking_id,
                             :amount_msat, :max_fee_msat, 0, :reserved_msat,
                             :status, false, :manual_reconciliation,
                             :request_json, :error)
                    """),  # noqa: S608
                    {
                        "id": intent_id,
                        "wallet_id": wallet_id,
                        "owner_user_id": owner_id,
                        "idempotency_key": idempotency_key,
                        "purpose": purpose,
                        "scope_id": scope_id,
                        "reference_id": reference_id,
                        "record_table": record_table,
                        "record_id": record_id,
                        "source_payment_hash": source_payment_hash,
                        "destination": destination,
                        "payment_request": payment_request,
                        "payment_hash": payment_hash,
                        "checking_id": payment_hash,
                        "amount_msat": amount_msat,
                        "max_fee_msat": max_fee_msat,
                        "reserved_msat": reserve_msat,
                        "status": "unknown" if manual_error else "pending",
                        "manual_reconciliation": bool(manual_error),
                        "request_json": request_json,
                        "error": manual_error,
                    },
                )
                row = await _raw_fetchone(
                    conn,
                    f"SELECT * FROM {intents} WHERE id = :id",  # noqa: S608
                    {"id": intent_id},
                )
                return row
    except IntegrityError as exc:
        row = await get_payment_intent(
            extension_id, wallet_id, idempotency_key, owner_id
        )
        if row and row["request_json"] == request_json:
            return row
        raise ValueError(
            "An intent already exists for this idempotency key or reference."
        ) from exc


async def _existing_intent(
    conn: Any,
    database: Database,
    row: dict[str, Any],
    request_json: str,
    retry_failed: bool,
    reserve_msat: int,
) -> dict[str, Any]:
    if row["request_json"] != request_json:
        raise ValueError("Idempotency key was already used for different intent data.")
    if not retry_failed or row["status"] != "failed":
        return row
    if row["attempted"] and not _is_lnurl(row["destination"]):
        raise ValueError(
            "A failed BOLT11 intent cannot be retried with the same invoice."
        )
    groups = _table_ref(database, _PAYMENT_INTENT_GROUPS_TABLE)
    intents = _table_ref(database, _PAYMENT_INTENTS_TABLE)
    group = await _raw_fetchone(
        conn,
        f"""
        SELECT * FROM {groups}
        WHERE wallet_id = :wallet_id AND scope_id = :scope_id{_for_update(conn.type)}
        """,  # noqa: S608
        {"wallet_id": row["wallet_id"], "scope_id": row["scope_id"]},
    )
    if (
        not group
        or group["spent_msat"] + group["reserved_msat"] + reserve_msat
        > group["funding_msat"]
    ):
        raise PermissionError("Scoped funds are already fully reserved.")
    await conn.conn.execute(
        text(f"""
            UPDATE {groups}
            SET reserved_msat = reserved_msat + :reserve_msat,
                updated_at = {database.timestamp_now}
            WHERE wallet_id = :wallet_id AND scope_id = :scope_id
        """),  # noqa: S608
        {
            "reserve_msat": reserve_msat,
            "wallet_id": row["wallet_id"],
            "scope_id": row["scope_id"],
        },
    )
    await conn.conn.execute(
        text(f"""
            UPDATE {intents}
            SET status = 'pending', payment_request = :payment_request,
                payment_hash = :payment_hash, checking_id = :checking_id,
                fee_msat = 0, reserved_msat = :reserved_msat,
                attempted = false, manual_reconciliation = false, error = NULL,
                updated_at = {database.timestamp_now}
            WHERE id = :id AND status = 'failed'
        """),  # noqa: S608
        {
            "payment_request": (
                None if _is_lnurl(row["destination"]) else row["payment_request"]
            ),
            "payment_hash": (
                None if _is_lnurl(row["destination"]) else row["payment_hash"]
            ),
            "checking_id": (
                None if _is_lnurl(row["destination"]) else row["checking_id"]
            ),
            "reserved_msat": reserve_msat,
            "id": row["id"],
        },
    )
    return await _raw_fetchone(
        conn,
        f"SELECT * FROM {intents} WHERE id = :id",  # noqa: S608
        {"id": row["id"]},
    )


async def _find_reference_intent(
    conn: Any,
    table: str,
    wallet_id: str,
    purpose: str,
    record_table: str | None,
    record_id: str | None,
    source_payment_hash: str | None,
) -> dict[str, Any] | None:
    if purpose == "payout":
        return await _raw_fetchone(
            conn,
            f"""
            SELECT * FROM {table}
            WHERE wallet_id = :wallet_id AND purpose = 'payout'
                AND record_table = :record_table AND record_id = :record_id
            """,  # noqa: S608
            {
                "wallet_id": wallet_id,
                "record_table": record_table,
                "record_id": record_id,
            },
        )
    return await _raw_fetchone(
        conn,
        f"""
        SELECT * FROM {table}
        WHERE wallet_id = :wallet_id AND purpose = 'refund'
            AND source_payment_hash = :source_payment_hash
        """,  # noqa: S608
        {"wallet_id": wallet_id, "source_payment_hash": source_payment_hash},
    )


async def resolve_payment_intent_invoice(
    intent: dict[str, Any],
) -> tuple[str, str, str]:
    if intent["payment_request"]:
        return intent["payment_request"], intent["payment_hash"], ""
    from lnbits.core.models.lnurl import CreateLnurlPayment
    from lnbits.core.services.lnurl import fetch_lnurl_pay_request

    from .lnurl import (
        lnurl_for_core,
        lnurl_pay_response_text,
        lnurl_payment_unit_for_core,
    )

    response, action = await fetch_lnurl_pay_request(
        data=CreateLnurlPayment(
            lnurl=lnurl_for_core(intent["destination"]),
            amount=int(intent["amount_msat"]),
            unit=lnurl_payment_unit_for_core("sat"),
            comment=None,
            internal_memo=f"WASM {intent['purpose']} payment intent",
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


def _payment_scope_id(payment: Payment, extension_id: str) -> str | None:
    return _payment_extra_value(payment, extension_id, "scope_id")


def _payment_extra_value(payment: Payment, extension_id: str, key: str) -> str | None:
    extra = payment.extra if isinstance(payment.extra, dict) else {}
    extension_extra = extra.get(f"extra_{extension_id}")
    value = extension_extra.get(key) if isinstance(extension_extra, dict) else None
    if value is None:
        value = extra.get(key)
    return value if isinstance(value, str) else None


def _normalized_hashes(values: Any) -> list[str] | None:
    if not isinstance(values, list) or any(
        not isinstance(value, str) or not _is_payment_hash(value) for value in values
    ):
        return None
    return sorted(value.lower() for value in values)


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
        from .lnurl import lnurl_for_core

        lnurl_for_core(value)
    except Exception:
        return False
    return True


async def _database(extension_id: str) -> Database:
    if not _SQL_IDENTIFIER_RE.fullmatch(extension_id):
        raise ValueError("Invalid WASM extension ID.")
    await _initialize_database_once(
        extension_id, "payment_intents", _create_payment_intent_tables
    )
    return storage_crud._database(extension_id)


async def _create_payment_intent_tables(database: Database) -> None:
    intents = _table_ref(database, _PAYMENT_INTENTS_TABLE)
    groups = _table_ref(database, _PAYMENT_INTENT_GROUPS_TABLE)
    audit = _table_ref(database, _PAYMENT_INTENT_MANUAL_AUDIT_TABLE)
    async with database.connect() as conn:
        await conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {intents} (
                id TEXT PRIMARY KEY,
                wallet_id TEXT NOT NULL,
                owner_user_id TEXT NOT NULL,
                idempotency_key TEXT NOT NULL,
                purpose TEXT NOT NULL,
                scope_id TEXT NOT NULL,
                reference_id TEXT NOT NULL,
                record_table TEXT,
                record_id TEXT,
                source_payment_hash TEXT,
                destination TEXT NOT NULL,
                payment_request TEXT,
                payment_hash TEXT,
                checking_id TEXT,
                amount_msat {database.big_int} NOT NULL,
                max_fee_msat {database.big_int} NOT NULL,
                fee_msat {database.big_int} NOT NULL DEFAULT 0,
                reserved_msat {database.big_int} NOT NULL,
                status TEXT NOT NULL,
                attempted BOOLEAN NOT NULL DEFAULT false,
                manual_reconciliation BOOLEAN NOT NULL DEFAULT false,
                request_json TEXT NOT NULL,
                error TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT {database.timestamp_now},
                updated_at TIMESTAMP NOT NULL DEFAULT {database.timestamp_now},
                UNIQUE (wallet_id, idempotency_key)
            )
        """)
        await conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {groups} (
                wallet_id TEXT NOT NULL,
                scope_id TEXT NOT NULL,
                funding_hashes_json TEXT NOT NULL,
                funding_msat {database.big_int} NOT NULL,
                reserved_msat {database.big_int} NOT NULL DEFAULT 0,
                spent_msat {database.big_int} NOT NULL DEFAULT 0,
                created_at TIMESTAMP NOT NULL DEFAULT {database.timestamp_now},
                updated_at TIMESTAMP NOT NULL DEFAULT {database.timestamp_now},
                PRIMARY KEY (wallet_id, scope_id)
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
                fee_msat {database.big_int} NOT NULL DEFAULT 0,
                note TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT {database.timestamp_now}
            )
        """)
        index_schema = f"{database.schema}." if database.type == SQLITE else ""
        index_table = _PAYMENT_INTENTS_TABLE if database.type == SQLITE else intents
        payout_index = f"{index_schema}lnbits_payment_intent_payout_reference"
        refund_index = f"{index_schema}lnbits_payment_intent_refund_source"
        await conn.execute(f"""
            CREATE UNIQUE INDEX IF NOT EXISTS {payout_index}
            ON {index_table} (wallet_id, record_table, record_id)
            WHERE purpose = 'payout'
        """)
        await conn.execute(f"""
            CREATE UNIQUE INDEX IF NOT EXISTS {refund_index}
            ON {index_table} (wallet_id, source_payment_hash)
            WHERE purpose = 'refund'
        """)


def _table_ref(database: Database, name: str) -> str:
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


async def get_manual_payment_intents(
    extension_id: str, wallet_id: str, *, limit: int = 100
) -> list[dict[str, Any]]:
    database = await _database(extension_id)
    intents = _table_ref(database, _PAYMENT_INTENTS_TABLE)
    audit = _table_ref(database, _PAYMENT_INTENT_MANUAL_AUDIT_TABLE)
    async with database.connect() as conn:
        rows = await conn.fetchall(
            f"""SELECT i.id, i.wallet_id, i.idempotency_key, i.purpose,
                    i.reference_id, i.source_payment_hash, i.payment_hash,
                    i.payment_request, i.amount_msat, i.max_fee_msat, i.fee_msat,
                    i.reserved_msat, i.status, i.attempted, i.error,
                    (SELECT a.actor_id FROM {audit} a WHERE a.intent_id = i.id
                        ORDER BY a.created_at DESC LIMIT 1) AS operator_actor_id,
                    (SELECT a.action FROM {audit} a WHERE a.intent_id = i.id
                        ORDER BY a.created_at DESC LIMIT 1) AS operator_action,
                    (SELECT a.note FROM {audit} a WHERE a.intent_id = i.id
                        ORDER BY a.created_at DESC LIMIT 1) AS operator_note,
                    (SELECT a.created_at FROM {audit} a WHERE a.intent_id = i.id
                        ORDER BY a.created_at DESC LIMIT 1) AS operator_action_at
                FROM {intents} i
                WHERE i.wallet_id = :wallet_id
                    AND (i.status = 'unknown'
                        OR i.manual_reconciliation = true OR EXISTS (
                        SELECT 1 FROM {audit} a WHERE a.intent_id = i.id
                    ))
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
    groups = _table_ref(database, _PAYMENT_INTENT_GROUPS_TABLE)
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
            group = await _raw_fetchone(
                conn,
                f"""SELECT * FROM {groups}
                    WHERE wallet_id = :wallet_id AND scope_id = :scope_id
                    {_for_update(conn.type)}""",  # noqa: S608
                {"wallet_id": wallet_id, "scope_id": intent["scope_id"]},
            )
            if not group or group["reserved_msat"] < intent["reserved_msat"]:
                raise RuntimeError(
                    "Payment intent funding reservation is inconsistent."
                )
            spent = group["spent_msat"]
            if status == "paid":
                spent += intent["amount_msat"] + fee_msat
            release_query = f"""
                UPDATE {groups}
                SET reserved_msat = reserved_msat - :reserved_msat,
                    spent_msat = :spent_msat,
                    updated_at = {database.timestamp_now}
                WHERE wallet_id = :wallet_id AND scope_id = :scope_id
            """  # noqa: S608
            await conn.conn.execute(
                text(release_query),
                {
                    "reserved_msat": intent["reserved_msat"],
                    "spent_msat": spent,
                    "wallet_id": wallet_id,
                    "scope_id": intent["scope_id"],
                },
            )
            await conn.conn.execute(
                text(f"""UPDATE {intents}
                    SET status = :status, fee_msat = :fee_msat,
                        reserved_msat = 0, error = NULL,
                        updated_at = {database.timestamp_now}
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
                    VALUES (:id, :intent_id, :wallet_id, :actor_id, 'resolve', :status,
                        :fee_msat, :note)"""),  # noqa: S608
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


def _matches_expected_intent_state(
    row: dict[str, Any],
    expected_status: str | None,
    expected_attempted: bool | None,
) -> bool:
    return (expected_status is None or row["status"] == expected_status) and (
        expected_attempted is None or bool(row["attempted"]) == expected_attempted
    )


def _for_update(db_type: str | None) -> str:
    return "" if db_type == SQLITE else " FOR UPDATE"
