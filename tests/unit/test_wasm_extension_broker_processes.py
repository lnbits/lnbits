"""Separate-process broker recovery checks; run once per configured backend."""

from __future__ import annotations

import asyncio
import json
import os
import select
import signal
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest

_TABLE = "broker_money_facts"
_ROOM = "process-room"
_OWNER = "process-owner"
_SCHEMA = {
    "tables": {
        _TABLE: {
            "table": _TABLE,
            "fields": [
                {"name": "id", "type": "string"},
                {"name": "idempotency_key", "type": "string"},
                {"name": "amount_msat", "type": "integer"},
                {"name": "generation", "type": "string"},
            ],
        }
    }
}


class _Worker:
    def __init__(self, extension_id: str, env: dict[str, str]):
        self.process = subprocess.Popen(  # noqa: S603
            [sys.executable, str(Path(__file__).resolve()), "--worker"],
            cwd=Path(__file__).resolve().parents[2],
            env={**env, "BROKER_TEST_EXTENSION": extension_id},
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self.next_id = 0
        assert self._event(timeout=20)["ready"] > 0

    def _event(self, timeout: float = 8) -> dict:
        assert self.process.stdout
        ready, _, _ = select.select([self.process.stdout], [], [], timeout)
        if not ready:
            self.process.kill()
            self.process.wait(timeout=3)
            error = self.process.stderr.read() if self.process.stderr else ""
            raise AssertionError(
                f"broker worker did not reach its barrier: {error[-2000:]}"
            )
        line = self.process.stdout.readline()
        if not line:
            error = self.process.stderr.read() if self.process.stderr else ""
            raise AssertionError(f"broker worker exited: {error[-2000:]}")
        return json.loads(line)

    def send(self, command: str, **payload) -> int:
        self.next_id += 1
        request_id = self.next_id
        assert self.process.stdin
        self.process.stdin.write(
            json.dumps({"id": request_id, "command": command, **payload}) + "\n"
        )
        self.process.stdin.flush()
        return request_id

    def result(self, request_id: int, timeout: float = 12) -> dict:
        while True:
            event = self._event(timeout)
            if event.get("id") == request_id:
                return event
            if event.get("barrier") == "paused":
                continue
            raise AssertionError(f"unexpected worker event: {event}")

    def stop(self) -> None:
        if self.process.poll() is None:
            self.send("stop")
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=3)
        if self.process.stdout:
            self.process.stdout.close()
        if self.process.stderr:
            self.process.stderr.close()
        if self.process.stdin:
            self.process.stdin.close()

    def crash(self) -> None:
        if self.process.poll() is None:
            self.process.send_signal(signal.SIGKILL)
            self.process.wait(timeout=3)
        if self.process.stdout:
            self.process.stdout.close()
        if self.process.stderr:
            self.process.stderr.close()
        if self.process.stdin:
            self.process.stdin.close()


def _fact(fact_id: str, key: str, amount: int, generation: str) -> dict:
    return {
        "id": fact_id,
        "idempotency_key": key,
        "amount_msat": amount,
        "generation": generation,
    }


@pytest.mark.anyio
async def test_process_revocation_crash_restart_preserves_fenced_money_facts(
    tmp_path: Path,
):
    extension_id = f"proc{uuid4().hex[:12]}"
    wasm_path = tmp_path / "wasm_extensions"
    schema_path = wasm_path / extension_id / "storage" / "schema.json"
    schema_path.parent.mkdir(parents=True)
    schema_path.write_text(json.dumps(_SCHEMA), encoding="utf-8")
    data_path = tmp_path / "data"
    data_path.mkdir()
    env = os.environ.copy()
    env.update(
        {
            "PYTHONPATH": str(Path(__file__).resolve().parents[2]),
            "LNBITS_DATA_FOLDER": str(data_path),
            "LNBITS_WASM_EXTENSIONS_PATH": str(wasm_path),
        }
    )
    # Keep the harness inside a disposable directory even when PG is selected.
    if env.get("LNBITS_DATABASE_URL", "") == "":
        env["LNBITS_DATABASE_URL"] = ""

    first = _Worker(extension_id, env)
    replacement = restarted = None
    try:
        initial = first.result(first.send("call", operation="claim"))
        assert initial["ok"]["epoch"] > 0
        first_fact = _fact("fact-1", "settlement-1", 1000, "generation-1")
        first_commit = first.result(
            first.send("call", operation="commit", payload={"fact": first_fact})
        )
        assert first_commit.get("ok", {}).get("count") == 1, first_commit
        initial_response = first.result(first.send("call", operation="intent"))
        assert "ok" in initial_response, initial_response
        initial_intent = initial_response["ok"]
        assert initial_intent["new_attempt"] is True
        assert initial_intent["attempted"] is True
        assert (
            first.result(
                first.send(
                    "call",
                    operation="publish",
                    payload={"generation": "generation-1", "fact_ids": ["fact-1"]},
                )
            )["ok"]["published"]
            is True
        )

        # Hold an old-epoch host storage write in-flight while another process
        # revokes and replaces the owner.
        stale_fact = _fact("fact-stale", "settlement-stale", 9000, "generation-1")
        pending = first.send(
            "call", operation="pause_commit", payload={"fact": stale_fact}
        )
        barrier = first._event(timeout=5)
        assert barrier == {"barrier": "paused", "id": pending}

        replacement = _Worker(extension_id, env)
        assert replacement.result(replacement.send("invalidate"))["ok"] is True
        recover_result = replacement.result(
            replacement.send(
                "call",
                operation="recover",
                payload={"generation": "generation-2"},
            ),
            timeout=10,
        )
        assert "ok" in recover_result, recover_result
        recovered = recover_result["ok"]
        assert recovered["epoch"] > initial["ok"]["epoch"]
        assert recovered["checkpoint"] == {"fact_ids": ["fact-1"]}
        assert recovered["publication"]["generation"] == "generation-2"
        assert recovered["fact"]["id"] == "fact-1"
        handed_over_intent = replacement.result(
            replacement.send("call", operation="intent")
        )["ok"]
        assert handed_over_intent["id"] == initial_intent["id"]
        assert handed_over_intent["attempted"] is True
        assert handed_over_intent["new_attempt"] is False

        assert first.result(first.send("resume", target=pending))["ok"] is True
        stale_result = first.result(pending)
        assert stale_result["error"] == "PermissionError"
        assert (
            replacement.result(
                replacement.send(
                    "call",
                    operation="commit",
                    payload={
                        "fact": _fact("fact-2", "settlement-2", 2000, "generation-2")
                    },
                )
            )["ok"]["count"]
            == 2
        )
        assert (
            replacement.result(
                replacement.send(
                    "call",
                    operation="publish",
                    payload={
                        "generation": "generation-2",
                        "fact_ids": ["fact-1", "fact-2"],
                    },
                )
            )["ok"]["published"]
            is True
        )

        # Exact retry is idempotent; a changed retry is rejected.
        exact = _fact("fact-2", "settlement-2", 2000, "generation-2")
        assert (
            replacement.result(
                replacement.send("call", operation="commit", payload={"fact": exact})
            )["ok"]["count"]
            == 2
        )
        changed = _fact("fact-2", "settlement-2", 3000, "generation-2")
        conflict = replacement.result(
            replacement.send("call", operation="commit", payload={"fact": changed})
        )
        assert conflict["error"] == "ValueError"
        replacement.crash()

        restarted = _Worker(extension_id, env)
        assert restarted.result(restarted.send("wait_expiry"))["ok"] is True
        final_result = restarted.result(
            restarted.send(
                "call",
                operation="recover_all",
                payload={"generation": "generation-3"},
            ),
            timeout=12,
        )
        assert "ok" in final_result, final_result
        final = final_result["ok"]
        assert final["epoch"] > recovered["epoch"]
        assert final["checkpoint"] == {"fact_ids": ["fact-1", "fact-2"]}
        assert final["publication"]["generation"] == "generation-3"
        assert final["facts"] == [first_fact, exact]
        assert final["count"] == 2
        assert final["new_generation"] == "generation-3"
        restarted_intent = restarted.result(restarted.send("call", operation="intent"))[
            "ok"
        ]
        assert restarted_intent["id"] == initial_intent["id"]
        assert restarted_intent["attempted"] is True
        assert restarted_intent["new_attempt"] is False
    finally:
        first.stop()
        if replacement:
            replacement.stop()
        if restarted:
            restarted.stop()


async def _worker_main() -> None:  # noqa: C901
    from lnbits.core.wasm_ext.api import authoritative_channels as channels
    from lnbits.core.wasm_ext.api import ephemeral_broker as transport
    from lnbits.core.wasm_ext.api import payment_intents
    from lnbits.core.wasm_ext.storage import crud

    extension_id = os.environ["BROKER_TEST_EXTENSION"]
    generation = "generation-1"
    pending_commit = asyncio.Event()
    database = crud._database(extension_id)
    async with database.connect() as conn:
        await conn.execute(crud._create_table_sql(conn, _SCHEMA["tables"][_TABLE]))

    async def dispatch(_ext: str, operation: str, payload: dict) -> dict:
        if operation == "claim":
            return {"epoch": await broker.assert_owner(extension_id)}
        if operation == "intent":
            # Synthetic verified funding exercises real intent transactions;
            # the durable attempt marker must prevent resends in new processes.
            intent = await payment_intents._reserve_payment_intent(
                extension_id=extension_id,
                wallet_id="wallet",
                idempotency_key="refund",
                request_data={"scope_id": _ROOM},
                funding_hashes=["a" * 64],
                funding_msat=1000000,
                destination="fixture-invoice",
                payment_request="fixture-invoice",
                payment_hash="b" * 64,
                amount_msat=1000,
                max_fee_msat=100000,
                purpose="refund",
                scope_id=_ROOM,
                reference_id="a" * 64,
                record_table=None,
                record_id=None,
                source_payment_hash="a" * 64,
                owner_id=_OWNER,
                retry_failed=False,
                manual_error=None,
            )
            current, claimed = await payment_intents.claim_payment_intent(
                extension_id, intent["id"]
            )
            attempted = claimed and await payment_intents.mark_payment_intent_attempted(
                extension_id, intent["id"]
            )
            persisted = await payment_intents.get_payment_intent(
                extension_id, "wallet", "refund", _OWNER
            )
            assert current is not None
            assert persisted is not None
            return {
                "id": current["id"],
                "attempted": bool(persisted["attempted"]),
                "new_attempt": attempted,
            }
        if operation in {"commit", "pause_commit"}:
            if operation == "pause_commit":
                print(
                    json.dumps({"barrier": "paused", "id": payload["request_id"]}),
                    flush=True,
                )
                await pending_commit.wait()
            async with database.connect() as conn:
                async with channels._transaction(conn):
                    await crud.storage_insert_immutable_row(
                        conn, extension_id, _TABLE, payload["fact"], _OWNER
                    )
            return {"count": await _fact_count(database, extension_id)}
        if operation == "publish":
            nonlocal generation
            generation = payload["generation"]
            broker.publish_state(
                extension_id,
                _ROOM,
                _OWNER,
                {"fact_ids": payload["fact_ids"]},
                generation,
            )
            await broker._flush_staged_states(extension_id, broker.epoch(extension_id))
            return {"published": True}
        if operation in {"recover", "recover_all"}:
            checkpoint = await broker.recover_state(extension_id, _ROOM, _OWNER)
            generation = payload["generation"]
            broker.publish_state(
                extension_id,
                _ROOM,
                _OWNER,
                checkpoint or {},
                generation,
            )
            await broker._flush_staged_states(extension_id, broker.epoch(extension_id))
            publication = await broker._read_published_state(
                extension_id,
                {
                    "room_id": _ROOM,
                    "owner_id": _OWNER,
                    "expected_generation": generation,
                },
            )
            assert publication is not None
            if operation == "recover":
                fact = await crud.storage_get_immutable_row(
                    extension_id, _TABLE, "fact-1", _OWNER
                )
                return {
                    "epoch": broker.epoch(extension_id),
                    "checkpoint": checkpoint,
                    "publication": publication,
                    "fact": fact,
                }
            facts = [
                await crud.storage_get_immutable_row(
                    extension_id, _TABLE, fact_id, _OWNER
                )
                for fact_id in ("fact-1", "fact-2")
            ]
            return {
                "epoch": broker.epoch(extension_id),
                "checkpoint": checkpoint,
                "publication": publication,
                "facts": facts,
                "count": await _fact_count(database, extension_id),
                "new_generation": generation,
            }
        raise ValueError("unexpected broker operation")

    broker = transport.EphemeralBroker(dispatch, lease_seconds=3, poll_interval=0.01)
    transport._module_config.broker = broker
    try:
        print(json.dumps({"ready": os.getpid()}), flush=True)
        tasks: set[asyncio.Task] = set()
        while line := await asyncio.to_thread(sys.stdin.readline):
            message = json.loads(line)
            command = message["command"]
            request_id = message["id"]
            if command == "stop":
                break
            if command == "wait_expiry":
                async with asyncio.timeout(8):
                    while True:
                        owner = await broker._read_owner(extension_id)
                        if not owner or owner["expires_at_ms"] <= owner["now_ms"]:
                            break
                        await asyncio.sleep(0.05)
                print(json.dumps({"id": request_id, "ok": True}), flush=True)
                continue
            if command == "resume":
                pending_commit.set()
                print(json.dumps({"id": request_id, "ok": True}), flush=True)
                continue
            if command == "invalidate":
                try:
                    await broker.invalidate(extension_id)
                    response = {"id": request_id, "ok": True}
                except Exception as exc:
                    response = {"id": request_id, "error": type(exc).__name__}
                print(json.dumps(response), flush=True)
                continue
            operation = message["operation"]
            payload = message.get("payload", {})
            if operation == "pause_commit":
                payload["request_id"] = request_id

            async def run(command_id: int, op: str, request: dict) -> None:
                try:
                    response = await broker.call(
                        extension_id, op, request, timeout_seconds=10
                    )
                    result = {"id": command_id, "ok": response}
                except Exception as exc:
                    result = {"id": command_id, "error": type(exc).__name__}
                print(json.dumps(result), flush=True)

            task = asyncio.create_task(run(request_id, operation, payload))
            tasks.add(task)
            task.add_done_callback(tasks.discard)
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    finally:
        await broker.close()


async def _fact_count(database, extension_id: str) -> int:
    from lnbits.core.wasm_ext.storage import crud

    async with database.connect() as conn:
        row = await conn.fetchone(
            "SELECT COUNT(*) AS count FROM "  # noqa: S608
            f"{crud._table_ref_for_schema(extension_id, _TABLE)}"
        )
    return int(row["count"])


if __name__ == "__main__" and sys.argv[1:] == ["--worker"]:
    import uvloop

    uvloop.run(_worker_main())
