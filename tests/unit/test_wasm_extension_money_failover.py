import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from lnbits.core.wasm_ext.api import authoritative_channels as channels
from lnbits.core.wasm_ext.api import ephemeral_broker as transport
from lnbits.core.wasm_ext.api.host import ExtensionHostAPI
from lnbits.core.wasm_ext.api.models import PaymentIntentCreateRequest
from lnbits.core.wasm_ext.storage import crud as storage_crud
from lnbits.core.wasm_ext.wasm.config import WasmAuthoritativeChannelConfig
from lnbits.helpers import sha256s
from lnbits.settings import Settings


def _drop_extension_database_cache(extension_id: str) -> None:
    loop = asyncio.get_running_loop()
    key = storage_crud._database_key(extension_id)
    storage_crud._databases.get(loop, {}).pop(key, None)
    initialized = storage_crud._initialized_databases.get(loop, set())
    for init_key in list(initialized):
        if init_key[0] == key:
            initialized.discard(init_key)


@pytest.mark.anyio
async def test_result_and_payout_survive_handover_restart_and_revocation(
    tmp_path: Path, settings: Settings, mocker, monkeypatch
):
    """Exercise host money safety; synthetic immutable facts across owner changes."""
    data_path = tmp_path / "data"
    data_path.mkdir()
    settings.lnbits_data_folder = str(data_path)
    settings.lnbits_wasm_extensions_path = str(tmp_path / "wasm_extensions")
    extension_id = f"money{uuid4().hex[:8]}"
    wallet_id = f"wallet-{uuid4().hex[:8]}"
    funding_hash = "a" * 64
    room_id = "room-1"
    owner_user_id = sha256s("operator-1")

    result_fields = [
        {"name": "id", "type": "string"},
        {"name": "scope_id", "type": "string"},
        {"name": "funding_payment_hashes", "type": "string", "list": True},
        {"name": "recipient_payment_hash", "type": "string"},
        {"name": "amount_msat", "type": "integer"},
        {"name": "fact_id", "type": "string"},
    ]
    storage_path = Path(settings.lnbits_wasm_extensions_path) / extension_id / "storage"
    storage_path.mkdir(parents=True)
    (storage_path / "schema.json").write_text(
        json.dumps({"tables": {"results": {"fields": result_fields}}}),
        encoding="utf-8",
    )

    database = await channels._database(extension_id)
    rooms = channels._table_ref(database, channels._ROOMS_TABLE)
    result_table = "results"
    async with database.connect() as conn:
        await conn.execute(
            storage_crud._create_table_sql(
                conn, {"table": result_table, "fields": result_fields}
            )
        )
        await conn.execute(
            f"INSERT INTO {rooms} (room_id, owner_id, lease_owner) "  # noqa: S608
            "VALUES (:room, :owner, :lease)",
            {"room": room_id, "owner": owner_user_id, "lease": "lease-1"},
        )

    result = {
        "scope_id": room_id,
        "funding_payment_hashes": [funding_hash],
        "recipient_payment_hash": funding_hash,
        "amount_msat": 1000,
        "fact_id": "committed-fact",
    }

    first = transport.EphemeralBroker(poll_interval=0.01)
    replacement = transport.EphemeralBroker(poll_interval=0.01)
    restarted = transport.EphemeralBroker(poll_interval=0.01)

    async def dispatch(_extension_id, operation, _payload):
        if operation in {"write_result", "rewrite_result"}:
            row = (
                result
                if operation == "write_result"
                else {**result, "amount_msat": 2000}
            )
            await channels._save_room_state(
                database,
                extension_id,
                room_id,
                owner_user_id,
                "lease-1",
                sequence=1,
                snapshot={"status": "finished", "result": row},
                has_snapshot=True,
                update_sequence=True,
                principal_id=None,
                client_sequence=None,
                result_table=result_table,
            )
            return {"written": True}
        if operation == "read_result":
            row = await storage_crud.storage_get_immutable_row(
                extension_id, result_table, room_id, owner_user_id
            )
            return {"result": row}
        raise ValueError("unexpected broker operation")

    first.configure(dispatch)
    replacement.configure(dispatch)
    restarted.configure(dispatch)
    monkeypatch.setattr(transport._module_config, "broker", first)
    try:
        await first.call(extension_id, "write_result", {})
        old_epoch = first.epoch(extension_id)
        with pytest.raises(
            ValueError, match="conflicts with an existing immutable row"
        ):
            await first.call(extension_id, "rewrite_result", {})
        await first.invalidate(extension_id)

        monkeypatch.setattr(transport._module_config, "broker", replacement)
        recovered = await replacement.call(extension_id, "read_result", {})
        assert recovered["result"]["fact_id"] == result["fact_id"]
        assert replacement.epoch(extension_id) > old_epoch

        # A paused old worker cannot insert another immutable fact: the owner
        # fence runs on the same connection and transaction as this storage write.
        loop = asyncio.get_running_loop()
        first._owners[extension_id] = transport._LocalOwner(old_epoch, loop.time() + 10)
        token = transport._handler_context.set((extension_id, old_epoch))
        try:
            with pytest.raises(PermissionError, match="ownership expired"):
                async with database.connect() as conn:
                    async with channels._transaction(conn):
                        await storage_crud.storage_insert_immutable_row(
                            conn,
                            extension_id,
                            result_table,
                            {**result, "id": "stale-old-owner"},
                            owner_user_id,
                        )
        finally:
            transport._handler_context.reset(token)
            first._owners.pop(extension_id, None)

        wallet = SimpleNamespace(
            id=wallet_id, user="operator-1", can_send_payments=True
        )
        mocker.patch(
            "lnbits.core.crud.wallets.get_wallet",
            mocker.AsyncMock(return_value=wallet),
        )
        funding_payment = SimpleNamespace(
            success=True,
            extension=extension_id,
            amount=1_000_000,
            extra={
                f"extra_{extension_id}": {
                    "scope_id": room_id,
                    "payment_destination": "lnbc-host-attested-destination",
                }
            },
        )
        mocker.patch(
            "lnbits.core.wasm_ext.api.payment_intents.get_standalone_payment",
            mocker.AsyncMock(return_value=funding_payment),
        )
        payout_hash = "b" * 64
        mocker.patch(
            "lnbits.core.wasm_ext.api.payment_intents.bolt11_decode",
            return_value=SimpleNamespace(payment_hash=payout_hash, amount_msat=1000),
        )
        request = PaymentIntentCreateRequest(
            source_payment_hash=None,
            wallet_id=wallet_id,
            idempotency_key=f"payout:{room_id}:{funding_hash}",
            scope_id=room_id,
            purpose="payout",
            funding_payment_hashes=[funding_hash],
            max_fee_msat=100_000,
            record_table=result_table,
            record_id=room_id,
        )
        replacement_api = ExtensionHostAPI(
            extension_id, ["wallet.payment_intents"], user_id="operator-1"
        )

        async def pay_during_handover(**_kwargs):
            await replacement.invalidate(extension_id)
            monkeypatch.setattr(transport._module_config, "broker", restarted)
            await restarted.call(extension_id, "read_result", {})
            restarted_api = ExtensionHostAPI(
                extension_id, ["wallet.payment_intents"], user_id="operator-1"
            )
            retry = await restarted_api.wallet_payment_intent_create_or_get(request)
            assert retry.status == "processing"
            return SimpleNamespace(success=True, failed=False, fee=0)

        pay_mock = mocker.patch(
            "lnbits.core.services.payments.pay_invoice",
            mocker.AsyncMock(side_effect=pay_during_handover),
        )
        first_intent = await replacement_api.wallet_payment_intent_create_or_get(
            request
        )
        assert first_intent.status == "paid"
        pay_mock.assert_awaited_once()

        _drop_extension_database_cache(extension_id)
        after_restart = ExtensionHostAPI(
            extension_id, ["wallet.payment_intents"], user_id="operator-1"
        )
        repeated = await after_restart.wallet_payment_intent_create_or_get(request)
        assert repeated.intent_id == first_intent.intent_id
        assert repeated.status == "paid"
        pay_mock.assert_awaited_once()

        revoked_api = ExtensionHostAPI(extension_id, [], user_id="operator-1")
        with pytest.raises(PermissionError, match="wallet.payment_intents"):
            await revoked_api.wallet_payment_intent_create_or_get(request)
        pay_mock.assert_awaited_once()
    finally:
        await first.close()
        await replacement.close()
        await restarted.close()


@pytest.mark.anyio
@pytest.mark.parametrize("checkpoint", [False, True])
@pytest.mark.parametrize("completed", [False, True])
async def test_interrupted_guest_detects_generation_and_voids_or_keeps_result(
    tmp_path: Path, settings: Settings, mocker, monkeypatch, checkpoint, completed
):
    settings.lnbits_data_folder = str(tmp_path)
    settings.lnbits_wasm_extensions_path = str(tmp_path / "extensions")
    ext = f"interrupt{uuid4().hex[:8]}"
    owner = sha256s("owner")
    fields = {
        "starts": [
            {"name": "id", "type": "string"},
            {"name": "generation", "type": "string"},
        ],
        "results": [
            {"name": "id", "type": "string"},
            {"name": "scope_id", "type": "string"},
            {"name": "status", "type": "string"},
        ],
        "decisions": [
            {"name": "id", "type": "string"},
            {"name": "status", "type": "string"},
        ],
    }
    schema = Path(settings.lnbits_wasm_extensions_path) / ext / "storage"
    schema.mkdir(parents=True)
    (schema / "schema.json").write_text(
        json.dumps(
            {"tables": {name: {"fields": values} for name, values in fields.items()}}
        )
    )
    database = await channels._database(ext)
    async with database.connect() as conn:
        for name, values in fields.items():
            await conn.execute(
                storage_crud._create_table_sql(conn, {"table": name, "fields": values})
            )
    extension = SimpleNamespace(
        id=ext,
        config=SimpleNamespace(
            authoritative_channel=WasmAuthoritativeChannelConfig.parse_obj(
                {
                    "authorizeConnection": "authorize",
                    "onEvent": "event",
                    "ownerContext": {"table": "starts", "idParam": "id"},
                    "resultTable": "results",
                    "persistence": "ephemeral",
                    "maxEventsPerSecond": 10,
                    "maxQueueDepth": 4,
                    "maxActiveRooms": 1,
                }
            )
        ),
    )
    limits = {
        "wasm_runtime_max_execution_ms": 1000,
        "wasm_runtime_max_authoritative_rooms": 16,
        "wasm_runtime_max_authoritative_queue_depth": 256,
        "wasm_runtime_max_authoritative_events_per_second": 1000,
        "wasm_runtime_max_authoritative_state_bytes": 4096,
    }
    funding_hash = "a" * 64
    mocker.patch(
        "lnbits.core.crud.wallets.get_wallet",
        mocker.AsyncMock(
            return_value=SimpleNamespace(
                id="wallet", user="owner", can_send_payments=True
            )
        ),
    )
    mocker.patch(
        "lnbits.core.wasm_ext.api.payment_intents.get_standalone_payment",
        mocker.AsyncMock(
            return_value=SimpleNamespace(
                success=True,
                extension=ext,
                amount=1000,
                extra={
                    f"extra_{ext}": {
                        "scope_id": "room",
                        "refund_destination": "lnbc-refund",
                    }
                },
            )
        ),
    )
    mocker.patch(
        "lnbits.core.wasm_ext.api.payment_intents.bolt11_decode",
        return_value=SimpleNamespace(payment_hash="b" * 64, amount_msat=1000),
    )
    pay = mocker.patch(
        "lnbits.core.services.payments.pay_invoice",
        mocker.AsyncMock(
            return_value=SimpleNamespace(success=True, failed=False, fee=0)
        ),
    )
    mocker.patch("lnbits.core.services.payments.fee_reserve_total", return_value=0)
    seen = []

    async def guest(_ext, _export, payload, **_kwargs):
        # Synthetic guest policy: durable start generation + absent result means VOID.
        context = payload["_authoritative"]
        seen.append(context)
        start = await storage_crud.storage_get_row(ext, "starts", "room", owner)
        result = await storage_crud.storage_get_immutable_row(
            ext, "results", "room", owner
        )
        if start is None:
            await storage_crud.storage_insert_if_absent_row(
                ext,
                "starts",
                "room",
                {"id": "room", "generation": context["generation"]},
                owner,
            )
            snapshot = {"progress": 0}
        elif start["generation"] == context["generation"]:
            snapshot = {"progress": 99}
            if completed:
                snapshot["result"] = {"scope_id": "room", "status": "complete"}
        elif result is not None:
            snapshot = {
                "result": {key: value for key, value in result.items() if key != "id"}
            }
        else:
            await storage_crud.storage_insert_if_absent_row(
                ext, "decisions", "room", {"id": "room", "status": "VOID"}, owner
            )
            refund = await ExtensionHostAPI(
                ext, ["wallet.payment_intents"], user_id="owner"
            ).wallet_payment_intent_create_or_get(
                PaymentIntentCreateRequest(
                    wallet_id="wallet",
                    idempotency_key="refund:room",
                    scope_id="room",
                    purpose="refund",
                    source_payment_hash=funding_hash,
                    funding_payment_hashes=[funding_hash],
                    max_fee_msat=0,
                )
            )
            assert refund.status == "paid"
            snapshot = {"status": "VOID"}
        return {"ok": True, "data": {"state": snapshot}}

    mocker.patch(
        "lnbits.core.wasm_ext.wasm.invoke.invoke_wasm_extension_export",
        side_effect=guest,
    )
    first = transport.EphemeralBroker(poll_interval=0.01)
    replacement = transport.EphemeralBroker(poll_interval=0.01)

    # Control the crash boundary rather than racing the background flush timer.
    publish_checkpoint = first._flush_staged_states
    mocker.patch.object(first, "_flush_staged_states", return_value=None)

    async def dispatch(_ext, _op, _payload):
        channels._check_actor_ownership(ext)
        return await channels.run_authoritative_channel_export(
            extension,
            "room",
            owner,
            "api",
            {},
            limits=limits,
            action="api",
            permissions=[],
            policy_generation=channels.get_ephemeral_authoritative_extension_generation(
                ext
            ),
        )

    first.configure(dispatch)
    replacement.configure(dispatch)
    monkeypatch.setattr(transport._module_config, "broker", first)
    try:
        await first.call(ext, "api", {})
        if checkpoint:
            await publish_checkpoint(ext, first.epoch(ext))
        await first.call(ext, "api", {})
        old_generation = seen[-1]["generation"]
        await first.invalidate(ext)
        _drop_extension_database_cache(ext)
        monkeypatch.setattr(transport._module_config, "broker", replacement)
        recovered = await replacement.call(ext, "api", {})
        assert seen[-1]["generation"] != old_generation
        assert seen[-1]["state"] == ({"progress": 0} if checkpoint else None)
        assert recovered["data"]["state"] == (
            {"result": {"scope_id": "room", "status": "complete"}}
            if completed
            else {"status": "VOID"}
        )
        await replacement.call(ext, "api", {})
        assert (
            await storage_crud.storage_count_rows(ext, "starts", {}, owner_id=owner)
            == 1
        )
        assert await storage_crud.storage_count_rows(
            ext, "results", {}, owner_id=owner
        ) == int(completed)
        assert await storage_crud.storage_count_rows(
            ext, "decisions", {}, owner_id=owner
        ) == int(not completed)
        assert pay.await_count == int(not completed)
    finally:
        await first.close()
        await replacement.close()
        channels.invalidate_ephemeral_authoritative_extension(ext)
