import asyncio
import json
from pathlib import Path
from uuid import uuid4

import pytest

from lnbits.core.wasm_ext.api import authoritative_channels, payment_intents
from lnbits.settings import Settings


@pytest.mark.anyio
async def test_payment_intents_and_channels_share_one_extension_engine(
    tmp_path: Path, settings: Settings
):
    settings.lnbits_database_url = None
    settings.lnbits_data_folder = str(tmp_path)
    extension_id = f"shared{uuid4().hex[:8]}"

    intents_database = await payment_intents._database(extension_id)
    channels_database = await authoritative_channels._database(extension_id)

    assert intents_database is channels_database


@pytest.mark.anyio
async def test_reconcile_does_not_release_a_payment_attempt_won_after_stale_read(
    tmp_path: Path, settings: Settings
):
    extension_id, database, intent = await _seed_intent(
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
    groups = payment_intents._table_ref(
        database, payment_intents._PAYMENT_INTENT_GROUPS_TABLE
    )
    async with database.connect() as conn:
        group = await conn.fetchone(f"SELECT * FROM {groups}")  # noqa: S608
    assert group["reserved_msat"] == 1_100


@pytest.mark.anyio
async def test_unattempted_payment_reconciliation_releases_reservation(
    tmp_path: Path, settings: Settings
):
    extension_id, database, intent = await _seed_intent(
        tmp_path,
        settings,
        status="processing",
        attempted=False,
        manual=False,
        payment_request=None,
    )

    current = await payment_intents.reconcile_payment_intent(extension_id, intent)

    assert current["status"] == "failed"
    assert current["reserved_msat"] == 0
    groups = payment_intents._table_ref(
        database, payment_intents._PAYMENT_INTENT_GROUPS_TABLE
    )
    async with database.connect() as conn:
        group = await conn.fetchone(f"SELECT * FROM {groups}")  # noqa: S608
    assert group["reserved_msat"] == 0


@pytest.mark.anyio
async def test_manual_intent_resolution_updates_funding_and_audits_actor(
    tmp_path: Path, settings: Settings
):
    extension_id, database, intent = await _seed_intent(
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
    assert resolved["reserved_msat"] == 0
    assert resolved["fee_msat"] == 50
    groups = payment_intents._table_ref(
        database, payment_intents._PAYMENT_INTENT_GROUPS_TABLE
    )
    async with database.connect() as conn:
        group = await conn.fetchone(f"SELECT * FROM {groups}")  # noqa: S608
    assert group["reserved_msat"] == 0
    assert group["spent_msat"] == 1_050

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
    assert resolved["reserved_msat"] == 0


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
    groups = payment_intents._table_ref(
        _database, payment_intents._PAYMENT_INTENT_GROUPS_TABLE
    )
    async with _database.connect() as conn:
        await conn.execute(
            f"UPDATE {groups} SET funding_msat = 1100 WHERE wallet_id = :wallet_id",  # noqa: S608
            {"wallet_id": intent["wallet_id"]},
        )

    unknown = await payment_intents.set_payment_intent_status(
        extension_id, intent["id"], "paid", fee_msat=150
    )
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
    assert resolved["reserved_msat"] == 0
    async with _database.connect() as conn:
        group = await conn.fetchone(f"SELECT * FROM {groups}")  # noqa: S608
    assert group["spent_msat"] == 1150


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
    assert all(row["status"] == "processing" for row, _acquired in claims)


async def _seed_intent(
    tmp_path: Path,
    settings: Settings,
    *,
    status: str,
    attempted: bool,
    manual: bool,
    payment_request: str | None,
):
    settings.lnbits_data_folder = str(tmp_path)
    extension_id = f"intent{uuid4().hex[:8]}"
    wallet_id = f"wallet-{uuid4().hex[:8]}"
    intent_id = uuid4().hex
    database = await payment_intents._database(extension_id)
    intents = payment_intents._table_ref(
        database, payment_intents._PAYMENT_INTENTS_TABLE
    )
    groups = payment_intents._table_ref(
        database, payment_intents._PAYMENT_INTENT_GROUPS_TABLE
    )
    request_json = json.dumps(
        {
            "scope_id": "scope-1",
            "funding_payment_hashes": ["a" * 64],
        }
    )
    async with database.connect() as conn:
        await conn.execute(
            f"""INSERT INTO {groups}
                (wallet_id, scope_id, funding_hashes_json, funding_msat,
                 reserved_msat, spent_msat)
                VALUES (:wallet_id, 'scope-1', :hashes, 10000, 1100, 0)""",  # noqa: S608
            {"wallet_id": wallet_id, "hashes": json.dumps(["a" * 64])},
        )
        await conn.execute(
            f"""INSERT INTO {intents}
                (id, wallet_id, owner_user_id, idempotency_key, purpose,
                 scope_id, reference_id, destination, payment_request,
                 payment_hash, amount_msat, max_fee_msat, fee_msat,
                 reserved_msat, status, attempted, manual_reconciliation,
                 request_json, error)
                VALUES (:id, :wallet_id, 'owner-hash', 'intent-key', 'refund',
                    'scope-1', 'source-hash', '', :payment_request,
                    NULL, 1000, 100, 0, 1100, :status, :attempted,
                    :manual, :request_json, NULL)""",  # noqa: S608
            {
                "id": intent_id,
                "wallet_id": wallet_id,
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
