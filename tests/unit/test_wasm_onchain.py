import asyncio
import time
from pathlib import Path
from runpy import run_path

import pytest
from pydantic import ValidationError
from wasmtime import Config, Engine, Store, component

from lnbits.core.crud.onchain import (
    get_address_by_id,
    get_wasm_onchain_checkout,
    update_address_snapshot,
)
from lnbits.core.crud.wallets import (
    create_wallet,
    get_onchain_wallet,
    init_onchain_wallet_state,
)
from lnbits.core.db import db
from lnbits.core.models.onchain import Snapshot
from lnbits.core.models.wallets import WalletType
from lnbits.core.services.onchain import OnchainKeyStatus
from lnbits.core.wasm_ext.api.host import ExtensionHostAPI
from lnbits.core.wasm_ext.api.models import EmptyRequest
from lnbits.core.wasm_ext.api.onchain import (
    OnchainPaymentStatusRequest,
    ReserveOnchainAddressRequest,
)
from lnbits.core.wasm_ext.api.registry import extension_api_permission_ids
from lnbits.core.wasm_ext.api.runtime import ExtensionAPIHost
from lnbits.core.wasm_ext.wasm.host import add_extension_host_imports
from lnbits.helpers import sha256s
from lnbits.utils.onchain import new_mnemonic, wallet_descriptor

PERMISSIONS = ["wallet.list", "onchain.receive", "onchain.payments.read"]


@pytest.fixture
async def wallets(app, mocker, settings):
    settings.lnbits_allow_onchain_payments = True
    mocker.patch(
        "lnbits.core.services.onchain.onchain_key_status",
        mocker.AsyncMock(
            return_value=OnchainKeyStatus(configured=True, backup_confirmed=True)
        ),
    )
    result = []
    for owner in ("alice", "bob"):
        base = await create_wallet(
            user_id=owner, wallet_type=WalletType.ONCHAIN, onchain_network="Testnet4"
        )
        wallet = await get_onchain_wallet(base.id)
        assert wallet
        wallet.onchain_wallet_kind = "watch"
        wallet.onchain_meta.masterpub = wallet_descriptor(new_mnemonic(), "Testnet4")[0]
        result.append(await init_onchain_wallet_state(wallet))
    return result


@pytest.fixture
async def checkout(wallets):
    wallet = wallets[0]
    request = ReserveOnchainAddressRequest(
        wallet_id=wallet.id, source_id=wallet.id, checkout_id="sale-1"
    )
    response = await _api().onchain.reserve_address(request)
    return wallet, request, response


@pytest.mark.anyio
async def test_listing_is_owned_safe_and_uses_core_readiness(wallets):
    wallet = wallets[0]
    response = await _api().wallet_list_user_wallets(EmptyRequest())
    summary = next(w for w in response.wallets if w.id == wallet.id)
    assert summary.model_dump() == {
        "id": wallet.id,
        "name": wallet.name,
        "currency": wallet.currency,
        "wallet_type": "onchain",
        "onchain_network": "Testnet4",
        "receiving_ready": True,
    }
    assert wallets[1].id not in [w.id for w in response.wallets]
    await db.execute(
        "UPDATE wallets SET onchain_wallet_kind = 'hot' WHERE id = :id",
        {"id": wallet.id},
    )
    response = await _api().wallet_list_user_wallets(EmptyRequest())
    assert not next(w for w in response.wallets if w.id == wallet.id).receiving_ready


@pytest.mark.anyio
@pytest.mark.parametrize("context", ["user", "event", "schedule"])
async def test_owner_context_is_not_authentication(wallets, context):
    api = _api(None, context=context, owner_id=sha256s("alice"))
    with pytest.raises(PermissionError):
        await api.wallet_list_user_wallets(EmptyRequest())
    with pytest.raises(PermissionError):
        await api.onchain.reserve_address(
            ReserveOnchainAddressRequest(
                wallet_id=wallets[0].id, source_id="terminal", checkout_id="sale"
            )
        )


@pytest.mark.anyio
async def test_reservation_uses_core_allocator_and_persists_binding(checkout):
    wallet, request, response = checkout
    stored = await get_wasm_onchain_checkout("pos", **request.model_dump())
    assert stored
    assert stored.owner_id == sha256s("alice")
    assert stored.status_token_hash == sha256s(response.status_token)
    assert response.status_token not in stored.model_dump_json()
    address = await get_address_by_id(stored.address_id)
    assert address and address.address == response.address
    assert address.walet_id == wallet.id and address.branch_index == 0
    assert address.address_index == 0
    second = await _api().onchain.reserve_address(
        request.model_copy(update={"checkout_id": "sale-2"})
    )
    assert second.address != response.address
    with pytest.raises(ValueError, match="unavailable"):
        await _api().onchain.reserve_address(request)
    assert await get_wasm_onchain_checkout("pos", **request.model_dump()) == stored


@pytest.mark.anyio
async def test_concurrent_reservations_never_share_an_address(wallets):
    wallet = wallets[0]
    requests = [
        ReserveOnchainAddressRequest(
            wallet_id=wallet.id, source_id=wallet.id, checkout_id=str(i)
        )
        for i in range(4)
    ]
    responses = await asyncio.gather(
        *[_api().onchain.reserve_address(request) for request in requests]
    )
    assert len({response.address for response in responses}) == 4


@pytest.mark.anyio
async def test_allocator_conflict_is_safe_and_creates_no_binding(wallets, mocker):
    reserve = mocker.patch(
        "lnbits.core.services.onchain.reserve_onchain_address_index",
        mocker.AsyncMock(return_value=False),
    )
    request = ReserveOnchainAddressRequest(
        wallet_id=wallets[0].id, source_id=wallets[0].id, checkout_id="conflict"
    )
    with pytest.raises(ValueError, match="^Onchain wallet or checkout is unavailable"):
        await _api().onchain.reserve_address(request)
    reserve.assert_awaited_once()
    assert await get_wasm_onchain_checkout("pos", **request.model_dump()) is None


@pytest.mark.anyio
async def test_cross_owner_operations_fail_even_with_valid_token(checkout):
    _, request, response = checkout
    with pytest.raises(PermissionError, match="unavailable"):
        await _api("bob").onchain.reserve_address(
            request.model_copy(update={"checkout_id": "bob-sale"})
        )
    with pytest.raises(PermissionError, match="unavailable"):
        await _api("bob").onchain.payment_status(_status(request, response))


@pytest.mark.anyio
async def test_two_owners_can_use_same_source_and_checkout_ids(wallets):
    for wallet in wallets:
        request = ReserveOnchainAddressRequest(
            wallet_id=wallet.id, source_id="same-terminal", checkout_id="same-sale"
        )
        response = await _api(wallet.user).onchain.reserve_address(request)
        await _snapshot(wallet, request, [])
        assert (
            await _api(wallet.user).onchain.payment_status(_status(request, response))
        ).received_sat == 0
        assert (
            await _api(None).onchain.payment_status(_status(request, response))
        ).received_sat == 0


@pytest.mark.anyio
@pytest.mark.parametrize("change", ["address", "network", "descriptor", "source"])
async def test_existing_but_mismatched_binding_is_rejected(checkout, change):
    wallet, request, response = checkout
    second_request = request.model_copy(update={"source_id": wallet.id + "-other"})
    second = await _api().onchain.reserve_address(second_request)
    await _snapshot(wallet, request, [])
    query = _status(request, response)
    if change == "address":
        stored = await get_wasm_onchain_checkout("pos", **request.model_dump())
        assert stored
        await db.execute(
            "UPDATE onchain_addresses SET address = :address WHERE id = :id",
            {"address": second.address, "id": stored.address_id},
        )
    elif change == "network":
        await db.execute(
            "UPDATE wallets SET onchain_network = 'Testnet' WHERE id = :id",
            {"id": wallet.id},
        )
    elif change == "descriptor":
        wallet.onchain_meta.masterpub = wallet_descriptor(new_mnemonic(), "Testnet4")[0]
        await _save_meta(wallet)
    else:
        query = _status(second_request, second).model_copy(
            update={"status_token": response.status_token}
        )
    with pytest.raises(PermissionError, match="unavailable"):
        await _api(None).onchain.payment_status(query)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "field,value",
    [
        ("wallet_id", "forged-wallet"),
        ("source_id", "other-terminal"),
        ("checkout_id", "other-sale"),
        ("address", "forged-address"),
        ("status_token", "forged-token"),
        ("status_token", None),
    ],
)
async def test_public_status_rejects_forged_identifiers(checkout, field, value):
    _, request, response = checkout
    status = _status(request, response).model_copy(update={field: value})
    with pytest.raises(PermissionError, match="unavailable"):
        await _api(
            None, context="event", owner_id=sha256s("alice")
        ).onchain.payment_status(status)


@pytest.mark.anyio
async def test_status_token_cannot_cross_checkout_extension_or_route_owner(checkout):
    _, request, response = checkout
    second_request = request.model_copy(update={"checkout_id": "sale-2"})
    second = await _api().onchain.reserve_address(second_request)
    status = _status(second_request, second).model_copy(
        update={"status_token": response.status_token}
    )
    for api, query in [
        (_api(None), status),
        (_api(None, extension_id="other"), _status(request, response)),
        (
            _api(None, owner_id=sha256s("bob"), context="event"),
            _status(request, response),
        ),
    ]:
        with pytest.raises(PermissionError, match="unavailable"):
            await api.onchain.payment_status(query)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "change",
    [
        "deleted",
        "unconfigured",
        "hot-unbacked",
        "network",
        "descriptor",
        "owner",
        "type",
    ],
)
async def test_unavailable_or_reconfigured_wallets_reject_status_and_receive(
    checkout, change
):
    wallet, request, response = checkout
    if change == "deleted":
        await db.execute(
            "UPDATE wallets SET deleted = true WHERE id = :id", {"id": wallet.id}
        )
    elif change in {"unconfigured", "hot-unbacked"}:
        await db.execute(
            "UPDATE wallets SET onchain_wallet_kind = :kind WHERE id = :id",
            {"id": wallet.id, "kind": None if change == "unconfigured" else "hot"},
        )
    elif change == "network":
        await db.execute(
            "UPDATE wallets SET onchain_network = NULL WHERE id = :id",
            {"id": wallet.id},
        )
    elif change == "descriptor":
        wallet.onchain_meta.masterpub = ""
        await _save_meta(wallet)
    elif change == "owner":
        await db.execute(
            'UPDATE wallets SET "user" = :owner WHERE id = :id',
            {"id": wallet.id, "owner": "bob"},
        )
    else:
        await db.execute(
            "UPDATE wallets SET wallet_type = 'lightning' WHERE id = :id",
            {"id": wallet.id},
        )
    with pytest.raises(PermissionError, match="unavailable"):
        await _api().onchain.reserve_address(
            request.model_copy(update={"checkout_id": "new"})
        )
    with pytest.raises(PermissionError, match="unavailable"):
        await _api(None).onchain.payment_status(_status(request, response))


@pytest.mark.anyio
@pytest.mark.parametrize("failure", ["disabled", "key", "backup"])
async def test_server_setup_checks_apply_to_listing_and_both_operations(
    checkout, settings, mocker, failure
):
    wallet, request, response = checkout
    settings.lnbits_allow_onchain_payments = failure != "disabled"
    mocker.patch(
        "lnbits.core.services.onchain.onchain_key_status",
        mocker.AsyncMock(
            return_value=OnchainKeyStatus(
                configured=failure != "key", backup_confirmed=failure != "backup"
            )
        ),
    )
    summaries = await _api().wallet_list_user_wallets(EmptyRequest())
    assert not next(w for w in summaries.wallets if w.id == wallet.id).receiving_ready
    with pytest.raises(ValueError, match="unavailable"):
        await _api().onchain.reserve_address(request)
    with pytest.raises(ValueError, match="unavailable"):
        await _api(None).onchain.payment_status(_status(request, response))


@pytest.mark.anyio
async def test_checkout_totals_include_spent_outputs_and_only_this_address(checkout):
    wallet, request, response = checkout
    transactions = [
        _tx("a", response.address, [1000, 2000], confirmed=True),
        _tx("b", response.address, [4000], confirmed=False),
        _tx("c", "another-checkout-address", [999999], confirmed=True),
    ]
    # The core explorer represents OP_RETURN outputs with a null address.
    transactions[0]["vout"].append(
        {"value": 0, "scriptpubkey": "6a00", "scriptpubkey_address": None}
    )
    # A spending transaction cannot subtract previously received funds.
    transactions[2]["vin"] = [
        {"prevout": {"scriptpubkey_address": response.address, "value": 3000}}
    ]
    transactions.append(transactions[0].copy())
    await _snapshot(wallet, request, transactions)
    for api in [
        _api(),
        _api(None),
        _api(None, context="event", owner_id=sha256s("alice")),
    ]:
        result = await api.onchain.payment_status(_status(request, response))
        assert result.model_dump() == {
            "received_sat": 7000,
            "confirmed_sat": 3000,
            "unconfirmed_sat": 4000,
            "checked_at": wallet.onchain_meta.sync_checked_at,
        }
    owner_query = _status(request, response).model_copy(update={"status_token": None})
    assert (await _api().onchain.payment_status(owner_query)).received_sat == 7000
    # Replacement/reorg snapshots replace earlier totals instead of accumulating them.
    await _snapshot(
        wallet, request, [_tx("b", response.address, [4000], confirmed=True)]
    )
    result = await _api().onchain.payment_status(owner_query)
    assert result.received_sat == result.confirmed_sat == 4000
    assert result.unconfirmed_sat == 0


@pytest.mark.anyio
@pytest.mark.parametrize(
    "failure", ["missing", "stale", "future", "error", "incomplete", "lease"]
)
async def test_payment_data_must_be_recent_and_complete(checkout, failure):
    wallet, request, response = checkout
    if failure != "missing":
        checked_at = int(time.time()) + {"stale": -121, "future": 30}.get(failure, 0)
        await _snapshot(wallet, request, [], checked_at=checked_at)
        if failure == "error":
            wallet.onchain_meta.sync_error = "private explorer URL"
        elif failure == "incomplete":
            wallet.onchain_meta.sync_checked_at = checked_at - 1
        await _save_meta(wallet)
        if failure == "lease":
            await db.execute(
                "UPDATE wallets SET onchain_sync_lease_until = :lease WHERE id = :id",
                {"id": wallet.id, "lease": int(time.time()) + 60},
            )
    with pytest.raises(
        ValueError, match="^Onchain checkout payment data is unavailable"
    ):
        await _api(None).onchain.payment_status(_status(request, response))


@pytest.mark.anyio
@pytest.mark.parametrize(
    "failure",
    [
        "value",
        "bool",
        "negative",
        "status",
        "txid",
        "outputs",
        "duplicate",
        "address",
        "script",
    ],
)
async def test_malformed_payment_data_fails_closed(checkout, failure):
    wallet, request, response = checkout
    tx = _tx("a", response.address, [100], confirmed=True)
    txs = [tx]
    if failure in {"value", "bool", "negative"}:
        tx["vout"][0]["value"] = {"value": 1.5, "bool": True, "negative": -1}[failure]
    elif failure == "status":
        tx["status"]["confirmed"] = "true"
    elif failure == "txid":
        tx["txid"] = "invalid"
    elif failure == "outputs":
        tx.pop("vout")
    elif failure == "address":
        tx["vout"][0].pop("scriptpubkey_address")
    elif failure == "script":
        tx["vout"][0]["scriptpubkey"] = "6a00"
    else:
        txs.append(_tx("a", response.address, [200], confirmed=True))
    await _snapshot(wallet, request, txs)
    with pytest.raises(ValueError, match="unavailable"):
        await _api().onchain.payment_status(_status(request, response))


@pytest.mark.anyio
async def test_permissions_are_required_for_every_operation(checkout):
    _, request, response = checkout
    api = ExtensionHostAPI("pos", [], user_id="alice")
    with pytest.raises(PermissionError, match="wallet.list"):
        await api.wallet_list_user_wallets(EmptyRequest())
    with pytest.raises(PermissionError, match="onchain.receive"):
        await api.onchain.reserve_address(request)
    with pytest.raises(PermissionError, match="onchain.payments.read"):
        await api.onchain.payment_status(_status(request, response))


@pytest.mark.parametrize(
    "field", ["user_id", "owner_id", "address", "explorer_url", "credentials"]
)
def test_reservation_rejects_caller_authority_and_configuration(field):
    with pytest.raises(ValidationError):
        ReserveOnchainAddressRequest.model_validate(
            {
                "wallet_id": "wallet",
                "source_id": "source",
                "checkout_id": "checkout",
                field: "forged",
            }
        )


def test_registry_sdk_and_permissions_expose_only_receive_and_status():
    assert {
        "onchain.receive",
        "onchain.payments.read",
    } <= extension_api_permission_ids()
    generate = run_path(
        str(Path(__file__).parents[2] / "tools/codegen/extension_sdk_typescript.py")
    )["generate_typescript_sdk"]
    sdk = generate(
        method_ids=[
            "wallet.list_user_wallets",
            "onchain.reserve_address",
            "onchain.payment_status",
        ]
    )
    assert "walletType" in sdk and "receivingReady" in sdk
    assert "host.onchain.reserveAddress(input)" in sdk
    assert "host.onchain.paymentStatus(input)" in sdk
    assert "receivedSat: number" in sdk


@pytest.mark.anyio
@pytest.mark.parametrize("extended", [False, True])
async def test_old_and_extended_wallet_list_wit_imports(wallets, extended):
    loop = asyncio.get_running_loop()
    extra = (
        """(field "wallet-type" string) (field "onchain-network" (option string))
        (field "receiving-ready" bool)"""
        if extended
        else ""
    )

    def call_import():
        config = Config()
        config.wasm_component_model = True
        engine = Engine(config)
        store = Store(engine)
        linker = component.Linker(engine)
        add_extension_host_imports(linker, ExtensionAPIHost(_api()), loop)
        compiled = component.Component(
            engine,
            f"""(component
            (import "lnbits:extension/host" (instance $host
                (type $wallet-def (record (field "id" string) (field "name" string)
                    (field "currency" (option string)) {extra}))
                (export "wallet" (type $wallet (eq $wallet-def)))
                (type $response-def (record (field "wallets" (list $wallet))))
                (export "response" (type $response (eq $response-def)))
                (export "list-user-wallets" (func (result $response)))))
            (alias export $host "wallet" (type $wallet))
            (alias export $host "response" (type $response))
            (export "wallet" (type $wallet))
            (export "response" (type $response))
            (alias export $host "list-user-wallets" (func $list))
            (core module $memory
                (memory (export "memory") 10)
                (global $heap (mut i32) (i32.const 0))
                (func (export "realloc") (param i32 i32 i32 i32) (result i32)
                    global.get $heap
                    global.get $heap local.get 3 i32.add
                    i32.const 7 i32.add i32.const -8 i32.and global.set $heap))
            (core instance $memory (instantiate $memory))
            (core func $list (canon lower (func $list)
                (memory $memory "memory") (realloc (func $memory "realloc"))))
            (core module $adapter
                (import "host" "list" (func $list (param i32)))
                (import "host" "realloc" (func $realloc
                    (param i32 i32 i32 i32) (result i32)))
                (func (export "list") (result i32) (local $result i32)
                    i32.const 0 i32.const 0 i32.const 4 i32.const 8
                    call $realloc local.set $result
                    local.get $result call $list local.get $result))
            (core instance $adapter (instantiate $adapter
                (with "host" (instance (export "list" (func $list))
                    (export "realloc" (func $memory "realloc"))))))
            (func (export "list") (result $response)
                (canon lift (core func $adapter "list")
                    (memory $memory "memory") (realloc (func $memory "realloc")))))""",
        )
        instance = linker.instantiate(store, compiled)
        function = instance.get_func(store, "list")
        assert function
        response = function(store)
        function.post_return(store)
        wallet = next(w for w in response.wallets if w.id == wallets[0].id)
        assert wallet.name == wallets[0].name
        if extended:
            assert getattr(wallet, "wallet-type") == "onchain"
            assert getattr(wallet, "receiving-ready") is True
        else:
            assert set(wallet.__dict__) == {"id", "name", "currency"}

    await asyncio.wait_for(asyncio.to_thread(call_import), 10)


@pytest.mark.anyio
@pytest.mark.parametrize("method", ["reserve-address", "payment-status"])
async def test_onchain_component_imports(checkout, method):
    wallet, request, response = checkout
    request_fields = """
        (field "wallet-id" string) (field "source-id" string)
        (field "checkout-id" string)
    """
    if method == "reserve-address":
        payload = request.model_copy(
            update={"checkout_id": "component-sale"}
        ).model_dump()
        response_fields = """(field "address" string) (field "network" string)
            (field "status-token" string)"""
        params, result_size = 6, 24
    else:
        await _snapshot(
            wallet, request, [_tx("a", response.address, [5000000000], confirmed=True)]
        )
        payload = _status(request, response).model_dump()
        request_fields += (
            '(field "address" string) (field "status-token" (option string))'
        )
        response_fields = """(field "received-sat" u64) (field "confirmed-sat" u64)
            (field "unconfirmed-sat" u64) (field "checked-at" u64)"""
        params, result_size = 11, 32
    loop = asyncio.get_running_loop()

    def call_import():
        config = Config()
        config.wasm_component_model = True
        engine = Engine(config)
        store = Store(engine)
        linker = component.Linker(engine)
        add_extension_host_imports(linker, ExtensionAPIHost(_api()), loop)
        compiled = component.Component(
            engine,
            f"""(component
            (import "lnbits:extension/onchain" (instance $host
                (type $request-def (record {request_fields}))
                (export "request" (type $request (eq $request-def)))
                (type $response-def (record {response_fields}))
                (export "response" (type $response (eq $response-def)))
                (export "{method}" (func (param "request" $request)
                    (result $response)))))
            (alias export $host "request" (type $request))
            (alias export $host "response" (type $response))
            (export "request" (type $request))
            (export "response" (type $response))
            (alias export $host "{method}" (func $call))
            (core module $memory
                (memory (export "memory") 1)
                (global $heap (mut i32) (i32.const 0))
                (func (export "realloc") (param i32 i32 i32 i32) (result i32)
                    global.get $heap
                    global.get $heap local.get 3 i32.add
                    i32.const 7 i32.add i32.const -8 i32.and global.set $heap))
            (core instance $memory (instantiate $memory))
            (core func $call (canon lower (func $call)
                (memory $memory "memory") (realloc (func $memory "realloc"))))
            (core module $adapter
                (import "host" "call" (func $call (param {"i32 " * (params + 1)})))
                (import "host" "realloc" (func $realloc
                    (param i32 i32 i32 i32) (result i32)))
                (func (export "call") (param {"i32 " * params}) (result i32)
                    (local $result i32)
                    i32.const 0 i32.const 0 i32.const 8 i32.const {result_size}
                    call $realloc local.set $result
                    {" ".join(f"local.get {i}" for i in range(params))}
                    local.get $result call $call local.get $result))
            (core instance $adapter (instantiate $adapter
                (with "host" (instance (export "call" (func $call))
                    (export "realloc" (func $memory "realloc"))))))
            (func (export "call") (param "request" $request) (result $response)
                (canon lift (core func $adapter "call")
                    (memory $memory "memory") (realloc (func $memory "realloc")))))""",
        )
        instance = linker.instantiate(store, compiled)
        function = instance.get_func(store, "call")
        assert function
        record = component.Record()
        for key, value in payload.items():
            setattr(record, key.replace("_", "-"), value)
        result = function(store, record)
        function.post_return(store)
        if method == "reserve-address":
            assert result.address != response.address
            assert result.network == "Testnet4"
            assert len(getattr(result, "status-token")) >= 32
        else:
            assert getattr(result, "received-sat") == 5000000000
            assert getattr(result, "confirmed-sat") == 5000000000
            assert getattr(result, "unconfirmed-sat") == 0

    await asyncio.wait_for(asyncio.to_thread(call_import), 10)


def _api(user: str | None = "alice", *, extension_id="pos", **kwargs):
    return ExtensionHostAPI(extension_id, PERMISSIONS, user_id=user, **kwargs)


def _status(request, response):
    return OnchainPaymentStatusRequest(
        **request.model_dump(),
        address=response.address,
        status_token=response.status_token,
    )


def _tx(txid, address, amounts, *, confirmed):
    return {
        "txid": txid * 64,
        "status": {"confirmed": confirmed, "block_height": 100 if confirmed else None},
        "vout": [
            {"scriptpubkey_address": address, "value": value} for value in amounts
        ],
    }


async def _save_meta(wallet):
    await db.execute(
        "UPDATE wallets SET onchain_meta = :meta WHERE id = :id",
        {"id": wallet.id, "meta": wallet.onchain_meta.model_dump_json()},
    )


async def _snapshot(wallet, request, transactions, *, checked_at=None):
    stored = await get_wasm_onchain_checkout("pos", **request.model_dump())
    assert stored
    checked_at = int(time.time()) if checked_at is None else checked_at
    # Empty UTXOs deliberately model payments that have already been spent.
    await update_address_snapshot(
        Snapshot(
            address_id=stored.address_id,
            transactions=transactions,
            utxos=[],
            checked_at=checked_at,
        ),
        amount=0,
    )
    wallet.onchain_meta.sync_checked_at = checked_at
    await _save_meta(wallet)
