import asyncio
import json
from pathlib import Path
from uuid import uuid4

import pytest

from lnbits.core.wasm_ext.api import payment_intents
from lnbits.settings import Settings


@pytest.mark.anyio
async def test_payment_intent_tables_initialize_once_for_concurrent_callers(
    tmp_path: Path, settings: Settings, mocker
):
    settings.lnbits_data_folder = str(tmp_path)
    extension_id = f"intent{uuid4().hex[:8]}"
    initialize = mocker.spy(payment_intents, "_create_payment_intent_tables")

    first, second = await asyncio.gather(
        payment_intents._database(extension_id),
        payment_intents._database(extension_id),
    )
    assert first is second
    assert await payment_intents._database(extension_id) is first
    assert initialize.await_count == 1


@pytest.mark.anyio
async def test_reconcile_does_not_undo_attempt_won_after_stale_read(
    tmp_path: Path, settings: Settings
):
    extension_id, _database, intent = await _seed_intent(
        tmp_path,
        settings,
        status="processing",
        attempted=False,
        manual=False,
        payment_request="invoice",
    )
    stale_intent = dict(intent)

    assert await payment_intents.mark_payment_intent_attempted(
        extension_id, intent["id"]
    )
    current = await payment_intents.reconcile_payment_intent(extension_id, stale_intent)

    assert current["status"] == "processing"
    assert bool(current["attempted"]) is True


@pytest.mark.anyio
async def test_unattempted_payment_reconciliation_waits_for_explicit_retry(
    tmp_path: Path, settings: Settings
):
    extension_id, _database, intent = await _seed_intent(
        tmp_path,
        settings,
        status="processing",
        attempted=False,
        manual=False,
        payment_request=None,
    )

    current = await payment_intents.reconcile_payment_intent(extension_id, intent)

    assert current["status"] == "failed"
    assert bool(current["attempted"]) is False
    assert "explicit retry" in current["error"]


@pytest.mark.anyio
async def test_manual_intent_resolution_audits_actor(
    tmp_path: Path, settings: Settings
):
    extension_id, _database, intent = await _seed_intent(
        tmp_path,
        settings,
        status="unknown",
        attempted=False,
        manual=True,
        payment_request=None,
    )

    resolved = await payment_intents.resolve_manual_payment_intent(
        extension_id,
        intent["wallet_id"],
        intent["id"],
        "account-owner",
        "paid",
        50,
        "Verified as settled in the wallet history.",
    )

    assert resolved["status"] == "paid"
    assert resolved["fee_msat"] == 50

    manual_intents = await payment_intents.get_manual_payment_intents(
        extension_id, intent["wallet_id"]
    )
    assert manual_intents[0]["operator_actor_id"] == "account-owner"
    assert manual_intents[0]["operator_action"] == "resolve"
    assert manual_intents[0]["operator_note"] == (
        "Verified as settled in the wallet history."
    )


@pytest.mark.anyio
async def test_legacy_unknown_without_manual_flag_is_discoverable_and_resolvable(
    tmp_path: Path, settings: Settings
):
    extension_id, _database, intent = await _seed_intent(
        tmp_path,
        settings,
        status="unknown",
        attempted=False,
        manual=False,
        payment_request=None,
    )

    listed = await payment_intents.get_manual_payment_intents(
        extension_id, intent["wallet_id"]
    )
    assert [row["id"] for row in listed] == [intent["id"]]

    resolved = await payment_intents.resolve_manual_payment_intent(
        extension_id,
        intent["wallet_id"],
        intent["id"],
        "account-owner",
        "failed",
        0,
        "Checked wallet; no payment was sent.",
    )
    assert resolved["status"] == "failed"


@pytest.mark.anyio
async def test_reconciled_unknown_is_discoverable_and_resolvable(
    tmp_path: Path, settings: Settings
):
    extension_id, _database, intent = await _seed_intent(
        tmp_path,
        settings,
        status="processing",
        attempted=True,
        manual=False,
        payment_request="invoice",
    )

    unknown = await payment_intents.reconcile_payment_intent(extension_id, intent)
    assert unknown["status"] == "unknown"
    assert bool(unknown["manual_reconciliation"]) is True

    listed = await payment_intents.get_manual_payment_intents(
        extension_id, intent["wallet_id"]
    )
    assert [row["id"] for row in listed] == [intent["id"]]

    resolved = await payment_intents.resolve_manual_payment_intent(
        extension_id,
        intent["wallet_id"],
        intent["id"],
        "account-owner",
        "failed",
        0,
        "Confirmed no outgoing payment exists.",
    )
    assert resolved["status"] == "failed"


@pytest.mark.anyio
async def test_over_ceiling_observed_payment_is_manually_resolvable(
    tmp_path: Path, settings: Settings
):
    extension_id, _database, intent = await _seed_intent(
        tmp_path,
        settings,
        status="processing",
        attempted=True,
        manual=False,
        payment_request="invoice",
    )

    unknown = await payment_intents.set_payment_intent_status(
        extension_id, intent["id"], "paid", fee_msat=150
    )
    assert unknown is not None
    assert unknown["status"] == "unknown"
    assert bool(unknown["manual_reconciliation"]) is True
    assert [
        row["id"]
        for row in await payment_intents.get_manual_payment_intents(
            extension_id, intent["wallet_id"]
        )
    ] == [intent["id"]]

    resolved = await payment_intents.resolve_manual_payment_intent(
        extension_id,
        intent["wallet_id"],
        intent["id"],
        "account-owner",
        "paid",
        150,
        "Verified the actual payment and fee in wallet history.",
    )
    assert resolved["status"] == "paid"
    assert resolved["fee_msat"] == 150


@pytest.mark.anyio
async def test_concurrent_claim_allows_only_one_payment_attempt(
    tmp_path: Path, settings: Settings
):
    extension_id, _database, intent = await _seed_intent(
        tmp_path,
        settings,
        status="pending",
        attempted=False,
        manual=False,
        payment_request="invoice",
    )

    claims = await asyncio.gather(
        payment_intents.claim_payment_intent(extension_id, intent["id"]),
        payment_intents.claim_payment_intent(extension_id, intent["id"]),
    )

    assert sum(acquired for _row, acquired in claims) == 1
    assert all(
        row is not None and row["status"] == "processing" for row, _acquired in claims
    )


@pytest.mark.anyio
async def test_failed_bolt11_intent_cannot_be_retried_with_same_invoice(
    tmp_path: Path, settings: Settings
):
    extension_id, _database, intent = await _seed_intent(
        tmp_path,
        settings,
        status="failed",
        attempted=True,
        manual=False,
        payment_request="invoice",
    )
    request_data = json.loads(intent["request_json"])

    with pytest.raises(ValueError, match="cannot be retried"):
        await payment_intents._reserve_payment_intent(
            extension_id=extension_id,
            wallet_id=intent["wallet_id"],
            idempotency_key=intent["idempotency_key"],
            request_data=request_data,
            destination=request_data["destination"],
            payment_request=intent["payment_request"],
            payment_hash=intent["payment_hash"],
            amount_msat=intent["amount_msat"],
            max_fee_msat=intent["max_fee_msat"],
            owner_id="owner-hash",
            retry_failed=True,
        )


@pytest.mark.anyio
async def test_failed_lnurl_intent_can_resolve_a_fresh_invoice(
    tmp_path: Path, settings: Settings
):
    extension_id, _database, intent = await _seed_intent(
        tmp_path,
        settings,
        status="failed",
        attempted=True,
        manual=False,
        payment_request="invoice",
        destination="user@example.com",
    )
    request_data = json.loads(intent["request_json"])

    retried = await payment_intents._reserve_payment_intent(
        extension_id=extension_id,
        wallet_id=intent["wallet_id"],
        idempotency_key=intent["idempotency_key"],
        request_data=request_data,
        destination=request_data["destination"],
        payment_request=None,
        payment_hash=None,
        amount_msat=intent["amount_msat"],
        max_fee_msat=intent["max_fee_msat"],
        owner_id="owner-hash",
        retry_failed=True,
    )

    assert retried["status"] == "pending"
    assert bool(retried["attempted"]) is False
    assert retried["payment_request"] is None
    assert retried["payment_hash"] is None


@pytest.mark.anyio
async def test_manual_intents_include_latest_audit_for_otherwise_unlisted_intent(
    tmp_path: Path, settings: Settings
):
    extension_id, database, intent = await _seed_intent(
        tmp_path,
        settings,
        status="failed",
        attempted=True,
        manual=False,
        payment_request="invoice",
    )
    assert not await payment_intents.get_manual_payment_intents(
        extension_id, intent["wallet_id"]
    )
    await payment_intents.record_payment_intent_operator_action(
        extension_id,
        intent["id"],
        intent["wallet_id"],
        "first-actor",
        "retry_requested",
        "failed",
        "First note",
    )
    audit = payment_intents._table_ref(
        database, payment_intents._PAYMENT_INTENT_MANUAL_AUDIT_TABLE
    )
    async with database.connect() as conn:
        await conn.execute(
            f"UPDATE {audit} "  # noqa: S608
            f"SET created_at = created_at - {database.interval_seconds(1)}"
        )
    await payment_intents.record_payment_intent_operator_action(
        extension_id,
        intent["id"],
        intent["wallet_id"],
        "second-actor",
        "retry_result",
        "failed",
        "Second note",
    )

    listed = await payment_intents.get_manual_payment_intents(
        extension_id, intent["wallet_id"]
    )
    assert len(listed) == 1
    assert listed[0]["operator_actor_id"] == "second-actor"
    assert listed[0]["operator_action"] == "retry_result"
    assert listed[0]["operator_note"] == "Second note"
    assert listed[0]["operator_action_at"] is not None
    assert not await payment_intents.get_manual_payment_intents(
        extension_id, "other-wallet"
    )


async def _seed_intent(
    tmp_path: Path,
    settings: Settings,
    *,
    status: str,
    attempted: bool,
    manual: bool,
    payment_request: str | None,
    destination: str = "invoice",
):
    settings.lnbits_data_folder = str(tmp_path)
    extension_id = f"intent{uuid4().hex[:8]}"
    wallet_id = f"wallet-{uuid4().hex[:8]}"
    intent_id = uuid4().hex
    database = await payment_intents._database(extension_id)
    intents = payment_intents._table_ref(
        database, payment_intents._PAYMENT_INTENTS_TABLE
    )
    request_json = json.dumps(
        {
            "destination": destination,
            "amount_msat": 1000,
            "max_fee_msat": 100,
            "description": None,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    async with database.connect() as conn:
        await conn.execute(
            f"""INSERT INTO {intents}
                (id, wallet_id, owner_user_id, idempotency_key, destination,
                 payment_request, payment_hash, amount_msat, max_fee_msat,
                 fee_msat, status, attempted, manual_reconciliation,
                 request_json, error)
                VALUES (:id, :wallet_id, 'owner-hash', 'intent-key', :destination,
                    :payment_request, NULL, 1000, 100, 0, :status, :attempted,
                    :manual, :request_json, NULL)""",  # noqa: S608
            {
                "id": intent_id,
                "wallet_id": wallet_id,
                "destination": destination,
                "payment_request": payment_request,
                "status": status,
                "attempted": attempted,
                "manual": manual,
                "request_json": request_json,
            },
        )
        intent = await conn.fetchone(
            f"SELECT * FROM {intents} WHERE id = :id",  # noqa: S608
            {"id": intent_id},
        )
    return extension_id, database, intent
