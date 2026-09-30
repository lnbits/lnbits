import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest

from lnbits.core.models.extensions import ExtensionPermission
from lnbits.core.wasm_ext.api import authoritative_channels as channels
from lnbits.core.wasm_ext.api import ephemeral_broker as transport
from lnbits.core.wasm_ext.storage import crud


@pytest.mark.anyio
async def test_ephemeral_broker_routes_to_one_owner_and_fences_takeover(mocker):
    ext = f"broker{uuid4().hex[:8]}"
    first = transport.EphemeralBroker(poll_interval=0.01)
    peer = transport.EphemeralBroker(poll_interval=0.01)
    counts = {}

    def handler(instance):
        async def dispatch(extension_id, operation, payload):
            assert transport.in_handler()
            if operation == "denied":
                raise PermissionError("permission revoked")
            counts[instance.worker_id] = counts.get(instance.worker_id, 0) + 1
            return {"worker": instance.worker_id, "count": counts[instance.worker_id]}

        return dispatch

    first.configure(handler(first))
    peer.configure(handler(peer))
    try:
        local = await first.call(ext, "event", {})
        original_epoch = first.epoch(ext)
        remote = await peer.call(ext, "event", {})
        assert remote == {"worker": local["worker"], "count": 2}
        with pytest.raises(PermissionError, match="permission revoked"):
            await peer.call(ext, "denied", {})
        # Ordinary local actor execution adds no coordination SQL round trip.
        hot_database = mocker.patch.object(
            first, "_database", side_effect=AssertionError("hot SQL")
        )
        assert (await first.call(ext, "event", {}))["count"] == 3
        mocker.stop(hot_database)
        await first.invalidate(ext)
        replacement = await peer.call(ext, "event", {})
        assert replacement["worker"] == peer.worker_id
        assert peer.epoch(ext) > original_epoch
        assert not first.check_owner(ext)
        # Emulate a paused worker resuming with a still-cached old lease.
        first._owners[ext] = transport._LocalOwner(
            original_epoch, asyncio.get_running_loop().time() + 10
        )
        token = transport._handler_context.set((ext, original_epoch))
        try:
            with pytest.raises(PermissionError, match="ownership expired"):
                await first.assert_owner(ext)
        finally:
            transport._handler_context.reset(token)
    finally:
        await first.close()
        await peer.close()


@pytest.mark.anyio
async def test_ephemeral_broker_remote_revocation_preserves_old_lease():
    ext = f"broker{uuid4().hex[:8]}"

    async def echo(_ext, _op, payload):
        return payload

    first = transport.EphemeralBroker(echo, poll_interval=0.01)
    peer = transport.EphemeralBroker(echo, poll_interval=0.01)
    try:
        await first.call(ext, "event", {})
        before = await first._read_owner(ext)
        await peer.invalidate(ext)
        after = await peer._read_owner(ext)
        assert after["epoch"] > before["epoch"]
        assert after["expires_at_ms"] == before["expires_at_ms"]
        assert after["worker_id"] is None
        assert await peer._try_claim(ext) is None
        await asyncio.sleep(0.1)
        assert not first.check_owner(ext)
    finally:
        await first.close()
        await peer.close()


@pytest.mark.anyio
async def test_ephemeral_cached_grants_are_checked_against_current_installed_state(
    mocker,
):
    mocker.patch.object(channels.settings, "lnbits_extensions_deactivate_all", False)
    grants = [
        ExtensionPermission(id=name)
        for name in (
            "websocket.subscribe",
            "websocket.authoritative",
            "ext.storage.read",
        )
    ]
    installed = SimpleNamespace(active=True, is_wasm=True, permissions=grants)
    mocker.patch(
        "lnbits.core.crud.extensions.get_installed_extension", return_value=installed
    )
    job = SimpleNamespace(extension=SimpleNamespace(id="demo"), permissions=grants)
    await channels._validate_current_channel_permissions(job)
    mocker.patch.object(channels.settings, "lnbits_extensions_deactivate_all", True)
    with pytest.raises(PermissionError, match="not active"):
        await channels._validate_current_channel_permissions(job)
    mocker.patch.object(channels.settings, "lnbits_extensions_deactivate_all", False)
    installed.active = False
    with pytest.raises(PermissionError, match="not active"):
        await channels._validate_current_channel_permissions(job)
    installed.active = True
    installed.permissions = grants[:2]
    with pytest.raises(PermissionError, match="permissions changed"):
        await channels._validate_current_channel_permissions(job)
    installed.permissions = []
    with pytest.raises(PermissionError, match="permission is not granted"):
        await channels._validate_current_channel_permissions(job)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "table",
    [
        "lnbits_payment_intents",
        "lnbits_authoritative_broker_owner",
        "lnbits_authoritative_broker_inbox",
        "lnbits_authoritative_broker_state",
        "lnbits_authoritative_rooms",
    ],
)
async def test_extension_storage_cannot_declare_or_read_host_coordination_tables(
    mocker, table
):
    schema = {"tables": {table: {"fields": [{"name": "id", "type": "string"}]}}}
    mocker.patch.object(crud, "_load_storage_schema", return_value=schema)
    with pytest.raises(ValueError, match="reserved host table"):
        await crud.storage_get_row("demo", table, "1", "owner")
    with pytest.raises(ValueError, match="reserved host table"):
        crud._create_table_sql(
            SimpleNamespace(),
            {"table": table, "fields": schema["tables"][table]["fields"]},
        )
    with pytest.raises(ValueError, match="SQL identifier"):
        await crud.storage_get_row("demo", table + "\n", "1", "owner")


@pytest.mark.anyio
async def test_broker_published_state_is_read_only_and_epoch_generation_fenced(mocker):
    ext = f"state{uuid4().hex[:8]}"
    calls = []
    first = transport.EphemeralBroker(poll_interval=0.01)
    peer = transport.EphemeralBroker(poll_interval=0.01)

    async def handler(extension_id, operation, payload):
        calls.append(operation)
        return {"state": {"snapshot": {"x": 2}, "version": 2}, "generation": "new"}

    first.configure(handler)
    peer.configure(handler)
    try:
        await first.call(ext, "start", {})
        epoch = first.epoch(ext)
        first.publish_state(
            ext,
            "room",
            "owner",
            {"snapshot": {"x": 1}, "version": 1, "has_snapshot": True},
            "old",
            max_rooms=1,
        )
        await first._flush_staged_states(ext, epoch)
        result = await peer.call(
            ext,
            "state",
            {
                "room_id": "room",
                "owner_id": "owner",
                "expected_generation": "old",
                "max_bytes": 100,
            },
        )
        assert result["state"]["version"] == 1
        assert calls == ["start"]  # cached reads never enter the mutation mailbox
        with pytest.raises(ValueError, match="host limit"):
            await peer.call(
                ext, "state", {"room_id": "room", "owner_id": "owner", "max_bytes": 1}
            )
        request = asyncio.create_task(
            peer.call(
                ext,
                "state",
                {
                    "room_id": "room",
                    "owner_id": "owner",
                    "expected_generation": "new",
                },
                timeout_seconds=0.5,
            )
        )
        await asyncio.sleep(0.02)
        first.publish_state(
            ext,
            "room",
            "owner",
            {
                "snapshot": {"x": 2},
                "version": 2,
                "has_snapshot": True,
            },
            "new",
            max_rooms=1,
        )
        await first._flush_staged_states(ext, epoch)
        result = await request
        assert result["generation"] == "new"
        assert calls == ["start"]  # cache misses also never invoke the owner
        await first._drop_owner(ext)
        assert (
            await peer._read_published_state(
                ext, {"room_id": "room", "owner_id": "owner"}
            )
            is None
        )
    finally:
        await first.close()
        await peer.close()


@pytest.mark.anyio
async def test_state_reads_preserve_published_room_capacity():
    ext = f"statecap{uuid4().hex[:8]}"
    broker = transport.EphemeralBroker(poll_interval=0.01)

    async def handler(extension_id, operation, payload):
        return {
            "state": {"snapshot": {"x": 1}, "version": 1, "has_snapshot": True},
            "generation": "generation",
        }

    broker.configure(handler)
    try:
        await broker.call(ext, "start", {})
        broker.publish_state(
            ext,
            "room",
            "owner",
            {"snapshot": {"x": 1}, "version": 1, "has_snapshot": True},
            "generation",
            max_rooms=48,
        )
        assert broker._state_room_limits[ext] == 48
        # A cached "state" dispatch must not reset the channel's capacity.
        await broker.call(
            ext,
            "state",
            {"room_id": "room", "owner_id": "owner", "generation": "generation"},
        )
        assert broker._state_room_limits[ext] == 48
    finally:
        await broker.close()


@pytest.mark.anyio
async def test_owner_handover_recovers_checkpoint_but_never_serves_old_publication():
    ext = f"broker{uuid4().hex[:8]}"
    first = transport.EphemeralBroker()
    replacement = transport.EphemeralBroker()

    def handler(instance):
        async def dispatch(extension_id, operation, payload):
            if operation == "recover":
                return {
                    "state": await instance.recover_state(extension_id, "room", "owner")
                }
            return {}

        return dispatch

    first.configure(handler(first))
    replacement.configure(handler(replacement))
    state = {
        "sequence": 7,
        "version": 4,
        "last_schedule_ms": 123,
        "snapshot": {"kills": ["kill-1"]},
        "has_snapshot": True,
        "event_timestamps": [],
    }
    try:
        await first.call(ext, "start", {})
        epoch = first.epoch(ext)
        first.publish_state(ext, "room", "owner", state, "old-generation")
        await first._flush_staged_states(ext, epoch)
        await first.invalidate(ext)
        assert (
            await replacement._read_published_state(
                ext, {"room_id": "room", "owner_id": "owner"}
            )
            is None
        )
        assert (await replacement.call(ext, "recover", {}))["state"] == state
        assert replacement.epoch(ext) > epoch
        assert (
            await replacement._read_published_state(
                ext, {"room_id": "room", "owner_id": "owner"}
            )
            is None
        )
        replacement.publish_state(ext, "room", "owner", state, "new-generation")
        await replacement._flush_staged_states(ext, replacement.epoch(ext))
        assert (
            await replacement._read_published_state(
                ext,
                {
                    "room_id": "room",
                    "owner_id": "owner",
                    "expected_generation": "old-generation",
                },
            )
            is None
        )
        published = await replacement._read_published_state(
            ext,
            {
                "room_id": "room",
                "owner_id": "owner",
                "expected_generation": "new-generation",
            },
        )
        assert published is not None and published["state"] == state
    finally:
        await first.close()
        await replacement.close()


@pytest.mark.anyio
async def test_ephemeral_broker_idle_backoff_batches_and_wakes_for_publication(mocker):
    ext = f"idle{uuid4().hex[:8]}"
    started = asyncio.Event()
    finish = asyncio.Event()
    seen = []

    async def dispatch(_ext, operation, payload):
        if operation == "hold":
            seen.append(payload["index"])
            if len(seen) == 4:
                started.set()
            await finish.wait()
        return {}

    owner = transport.EphemeralBroker(dispatch)
    peers = [transport.EphemeralBroker(dispatch) for _ in range(4)]
    calls = []
    try:
        await owner.call(ext, "start", {})
        # After the idle ramp, the owner must not return to a 50 Hz polling loop.
        await asyncio.sleep(0.5)
        reads = mocker.spy(owner, "_read_owner")
        await asyncio.sleep(0.6)
        assert reads.await_count <= 5
        calls = [
            asyncio.create_task(peer.call(ext, "hold", {"index": index}))
            for index, peer in enumerate(peers)
        ]
        await asyncio.wait_for(started.wait(), timeout=1)
        assert sorted(seen) == [0, 1, 2, 3]
        assert len(owner._owners[ext].handler_tasks) == 4
        owner.publish_state(ext, "room", "owner", {"published": True}, "generation")
        publication = await peers[0].call(
            ext, "state", {"room_id": "room", "owner_id": "owner"}, timeout_seconds=0.15
        )
        assert publication["state"] == {"published": True}
        # Cleanup has its own task; it is stopped alongside the lease and inbox.
        cleanup = owner._owners[ext].cleanup_task
        assert cleanup is not None and not cleanup.done()
        finish.set()
        await asyncio.gather(*calls)
        await owner.invalidate(ext)
        assert cleanup.done()
    finally:
        finish.set()
        await asyncio.gather(*calls, return_exceptions=True)
        await owner.close()
        for peer in peers:
            await peer.close()


@pytest.mark.anyio
async def test_ephemeral_broker_uncertain_response_commit_drops_owner(mocker):
    ext = f"uncertain{uuid4().hex[:8]}"
    started = asyncio.Event()
    finish = asyncio.Event()

    async def dispatch(_ext, operation, _payload):
        if operation == "hold":
            started.set()
            await finish.wait()
        return {}

    owner = transport.EphemeralBroker(dispatch)
    peer = transport.EphemeralBroker(dispatch)
    pending = None
    try:
        await owner.call(ext, "start", {})
        pending = asyncio.create_task(peer.call(ext, "hold", {}))
        await asyncio.wait_for(started.wait(), timeout=1)
        mocker.patch.object(
            owner,
            "_assert_owner_on_connection",
            side_effect=RuntimeError("private database failure"),
        )
        finish.set()
        with pytest.raises(PermissionError, match="owner changed"):
            await pending
        assert not owner.check_owner(ext)
    finally:
        finish.set()
        if pending:
            await asyncio.gather(pending, return_exceptions=True)
        await owner.close()
        await peer.close()
