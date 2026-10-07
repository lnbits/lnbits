"""Separate-process crash recovery checks for generic wallet execution.

These run without the authoritative channel broker: they cover the durable
payment-intent state on its own, once per configured database backend.
"""

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

from lnbits.core.wasm_ext.api import payment_intents
from lnbits.core.wasm_ext.storage import crud

_TABLE = "settlements"
_IDEMPOTENCY_KEY = "settlement-1"
_INVOICE = "lnbc-crash-fixture-invoice"
_PAYMENT_HASH = "b" * 64
_DESTINATION = "lnbc-crash-fixture-destination"
_SCHEMA = {
    "tables": {
        _TABLE: {
            "table": _TABLE,
            "fields": [
                {"name": "id", "type": "string"},
                {"name": "idempotency_key", "type": "string"},
                {"name": "amount_msat", "type": "integer"},
            ],
        }
    }
}


class _Worker:
    def __init__(self, extension_id: str, env: dict[str, str]):
        self.process = subprocess.Popen(  # noqa: S603
            [sys.executable, str(Path(__file__).resolve()), "--worker"],
            cwd=Path(__file__).resolve().parents[2],
            env={**env, "PAYMENT_TEST_EXTENSION": extension_id},
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self.next_id = 0
        assert self._event(timeout=20)["ready"] > 0

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
            raise AssertionError(f"unexpected worker event: {event}")

    def stop(self) -> None:
        if self.process.poll() is None:
            self.send("stop")
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=3)
        for stream in (self.process.stdout, self.process.stderr, self.process.stdin):
            if stream:
                stream.close()

    def wait_barrier(self, request_id: int, timeout: float = 8) -> None:
        while True:
            event = self._event(timeout)
            if event.get("barrier") == "crash" and event.get("id") == request_id:
                return
            raise AssertionError(f"unexpected worker event: {event}")

    def crash(self) -> None:
        if self.process.poll() is None:
            self.process.send_signal(signal.SIGKILL)
            self.process.wait(timeout=3)
        for stream in (self.process.stdout, self.process.stderr, self.process.stdin):
            if stream:
                stream.close()

    def _event(self, timeout: float = 8) -> dict:
        assert self.process.stdout
        ready, _, _ = select.select([self.process.stdout], [], [], timeout)
        if not ready:
            self.process.kill()
            self.process.wait(timeout=3)
            error = self.process.stderr.read() if self.process.stderr else ""
            raise AssertionError(f"payment worker stalled: {error[-2000:]}")
        line = self.process.stdout.readline()
        if not line:
            error = self.process.stderr.read() if self.process.stderr else ""
            raise AssertionError(f"payment worker exited: {error[-2000:]}")
        return json.loads(line)


@pytest.mark.anyio
async def test_crashed_payment_process_cannot_send_twice(
    tmp_path: Path, settings, mocker
):
    extension_id = f"pay{uuid4().hex[:12]}"
    wasm_path = tmp_path / "wasm_extensions"
    schema_path = wasm_path / extension_id / "storage" / "schema.json"
    schema_path.parent.mkdir(parents=True)
    schema_path.write_text(json.dumps(_SCHEMA), encoding="utf-8")
    data_path = tmp_path / "data"
    data_path.mkdir()
    env = _env(tmp_path, wasm_path, data_path)
    settings.lnbits_data_folder = str(data_path)
    settings.lnbits_wasm_extensions_path = str(wasm_path)
    mocker.patch(
        "lnbits.core.wasm_ext.api.payment_intents.get_standalone_payment",
        mocker.AsyncMock(return_value=None),
    )

    first = _Worker(extension_id, env)
    before_send = after_send = None
    try:
        created = first.result(first.send("create"))["ok"]
        assert created["status"] == "pending"

        # Crash while the attempt is claimed and the invoice is persisted but
        # before the send is marked as attempted.
        before = first.send("kill_before_send")
        first.wait_barrier(before)
        first.crash()

        # A restarted process must see the persisted invoice and no attempt.
        restarted = _Worker(extension_id, env)
        before_send = restarted
        persisted = restarted.result(restarted.send("status"))["ok"]
        assert persisted["status"] == "processing"
        assert bool(persisted["attempted"]) is False
        assert persisted["payment_request"] == _INVOICE
        assert persisted["payment_hash"] == _PAYMENT_HASH
        restarted.stop()
        before_send = None

        reconciled = await payment_intents.reconcile_payment_intent(
            extension_id, persisted
        )
        assert reconciled["status"] == "failed"
        assert bool(reconciled["attempted"]) is False
        assert "explicit retry" in reconciled["error"]
        # A crashed-before-send intent never produces an outgoing payment.
        _, claimed = await payment_intents.claim_payment_intent(
            extension_id, persisted["id"]
        )
        assert claimed is False

        # Crash after the attempt marker: the outcome is unknown, not retryable.
        second = _Worker(extension_id, env)
        after_send = second
        created = second.result(second.send("create", idempotency_key="settlement-2"))[
            "ok"
        ]
        after = second.send("kill_after_send", idempotency_key="settlement-2")
        second.wait_barrier(after)
        second.crash()
        after_send = None

        probe = _Worker(extension_id, env)
        after_send = probe
        attempted = probe.result(probe.send("status", idempotency_key="settlement-2"))[
            "ok"
        ]
        assert bool(attempted["attempted"]) is True
        assert attempted["payment_request"] == _INVOICE
        probe.stop()
        after_send = None

        unknown = await payment_intents.reconcile_payment_intent(
            extension_id, attempted
        )
        assert unknown["status"] == "unknown"
        assert bool(unknown["manual_reconciliation"]) is True
        _, claimed = await payment_intents.claim_payment_intent(
            extension_id, attempted["id"]
        )
        assert claimed is False

        async def retry() -> dict:
            return await payment_intents._reserve_payment_intent(
                extension_id=extension_id,
                wallet_id=attempted["wallet_id"],
                idempotency_key=attempted["idempotency_key"],
                request_data=json.loads(attempted["request_json"]),
                destination=_DESTINATION,
                payment_request=_INVOICE,
                payment_hash=_PAYMENT_HASH,
                amount_msat=attempted["amount_msat"],
                max_fee_msat=attempted["max_fee_msat"],
                owner_id=attempted["owner_user_id"],
                retry_failed=True,
            )

        # An unknown outcome is never retried or re-resolved to a fresh invoice.
        unchanged = await retry()
        assert unchanged["status"] == "unknown"
        assert unchanged["payment_request"] == _INVOICE
        assert unchanged["payment_hash"] == _PAYMENT_HASH

        # Once an operator confirms the failure, a BOLT11 attempt is still
        # single-use: it must not be replayed with the same invoice.
        resolved = await payment_intents.resolve_manual_payment_intent(
            extension_id,
            attempted["wallet_id"],
            attempted["id"],
            "operator-1",
            "failed",
            0,
            "Confirmed no outgoing payment exists.",
        )
        assert resolved["status"] == "failed"
        with pytest.raises(ValueError, match="cannot be retried"):
            await retry()
        manual = await payment_intents.get_manual_payment_intents(
            extension_id, attempted["wallet_id"]
        )
        assert [row["id"] for row in manual] == [attempted["id"]]
        assert manual[0]["operator_actor_id"] == "operator-1"
    finally:
        first.stop()
        if before_send:
            before_send.stop()
        if after_send:
            after_send.stop()


def _env(tmp_path: Path, wasm_path: Path, data_path: Path) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "PYTHONPATH": str(Path(__file__).resolve().parents[2]),
            "LNBITS_DATA_FOLDER": str(data_path),
            "LNBITS_WASM_EXTENSIONS_PATH": str(wasm_path),
        }
    )
    if env.get("LNBITS_DATABASE_URL", "") == "":
        env["LNBITS_DATABASE_URL"] = ""
    return env


async def _worker_main() -> None:
    extension_id = os.environ["PAYMENT_TEST_EXTENSION"]
    database = crud._database(extension_id)
    async with database.connect() as conn:
        await conn.execute(crud._create_table_sql(conn, _SCHEMA["tables"][_TABLE]))

    async def create(idempotency_key: str) -> dict:
        return await payment_intents._reserve_payment_intent(
            extension_id=extension_id,
            wallet_id="wallet",
            idempotency_key=idempotency_key,
            request_data={
                "destination": _DESTINATION,
                "amount_msat": 1000,
                "max_fee_msat": 100,
                "description": None,
            },
            destination=_DESTINATION,
            payment_request=_INVOICE,
            payment_hash=_PAYMENT_HASH,
            amount_msat=1000,
            max_fee_msat=100,
            owner_id="owner-hash",
            retry_failed=False,
        )

    async def begin_attempt(idempotency_key: str) -> dict:
        intent = await create(idempotency_key)
        current, claimed = await payment_intents.claim_payment_intent(
            extension_id, intent["id"]
        )
        assert claimed, f"intent {idempotency_key} was not claimable"
        assert current is not None
        assert await payment_intents.save_payment_intent_invoice(
            extension_id, intent["id"], _INVOICE, _PAYMENT_HASH
        )
        return current

    print(json.dumps({"ready": os.getpid()}), flush=True)
    while line := await _readline():
        message = json.loads(line)
        command = message["command"]
        request_id = message["id"]
        idempotency_key = message.get("idempotency_key", _IDEMPOTENCY_KEY)
        if command == "stop":
            break
        if command == "create":
            intent = await create(idempotency_key)
            print(
                json.dumps({"id": request_id, "ok": {"status": intent["status"]}}),
                flush=True,
            )
            continue
        if command == "status":
            row = await payment_intents.get_payment_intent(
                extension_id, "wallet", idempotency_key, "owner-hash"
            )
            print(
                json.dumps({"id": request_id, "ok": _jsonable(row)}),
                flush=True,
            )
            continue
        if command in {"kill_before_send", "kill_after_send"}:
            await begin_attempt(idempotency_key)
            if command == "kill_after_send":
                attempt = await payment_intents.get_payment_intent(
                    extension_id, "wallet", idempotency_key, "owner-hash"
                )
                assert attempt is not None
                assert await payment_intents.mark_payment_intent_attempted(
                    extension_id, attempt["id"]
                )
            print(json.dumps({"barrier": "crash", "id": request_id}), flush=True)
            os.kill(os.getpid(), signal.SIGKILL)
            return
        raise ValueError(f"unexpected payment worker command: {command}")


def _jsonable(row: dict | None) -> dict:
    """Rows carry driver-specific types (e.g. PostgreSQL datetimes)."""
    return {
        key: (
            value
            if isinstance(value, (str, int, float, bool, type(None)))
            else str(value)
        )
        for key, value in (row or {}).items()
    }


async def _readline() -> str:
    return await asyncio.to_thread(sys.stdin.readline)


if __name__ == "__main__" and sys.argv[1:] == ["--worker"]:
    asyncio.run(_worker_main())
