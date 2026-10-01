"""Measure idle SQL traffic from the ephemeral WASM broker."""

from __future__ import annotations

import argparse
import asyncio
import os
import statistics
import tempfile
import time
from typing import Any
from uuid import uuid4

import uvloop


class SQLStats:
    def __init__(self) -> None:
        self.durations: list[float] = []

    @property
    def count(self) -> int:
        return len(self.durations)

    def before(
        self,
        _conn: Any,
        _cursor: Any,
        _statement: str,
        _params: Any,
        ctx: Any,
        _many: bool,
    ) -> None:
        ctx.benchmark_started = time.perf_counter()

    def after(
        self,
        _conn: Any,
        _cursor: Any,
        _statement: str,
        _params: Any,
        ctx: Any,
        _many: bool,
    ) -> None:
        started = getattr(ctx, "benchmark_started", None)
        if started is not None:
            self.durations.append(time.perf_counter() - started)

    def reset(self) -> None:
        self.durations.clear()


async def run(args: argparse.Namespace) -> None:  # noqa: C901
    with tempfile.TemporaryDirectory(prefix="wasm-broker-bench-") as data_dir:
        os.environ["LNBITS_DATA_FOLDER"] = data_dir
        os.environ["LNBITS_DATABASE_URL"] = args.database_url or ""

        from lnbits.core.wasm_ext.api.ephemeral_broker import EphemeralBroker
        from lnbits.core.wasm_ext.storage import crud

        databases = []

        async def handler(
            _extension: str, operation: str, _payload: dict[str, Any]
        ) -> dict[str, Any]:
            if operation == "wait":
                started[0] += 1
                if started[0] == callers:
                    all_started.set()
                await gate.wait()
            return {"ok": True}

        for rooms, callers in ((1, 0), (8, 0), (1, 1), (1, 4), (8, 1), (8, 4)):
            ext_id = f"bench_{uuid4().hex[:12]}"
            broker = EphemeralBroker(handler, lease_seconds=6, poll_interval=0.02)
            await broker.call(ext_id, "start", {}, timeout_seconds=2)
            db = crud._database(ext_id)
            databases.append(db)
            from sqlalchemy import event

            stats = SQLStats()
            event.listen(db.engine.sync_engine, "before_cursor_execute", stats.before)
            event.listen(db.engine.sync_engine, "after_cursor_execute", stats.after)

            for room in range(rooms):
                broker.publish_state(
                    ext_id, f"room_{room}", "owner", {"n": room}, f"g{room}"
                )
            await asyncio.sleep(1.5)
            # Keep state-cache misses distinct from the published room keys.
            callers_brokers = [
                EphemeralBroker(handler, lease_seconds=6) for _ in range(callers)
            ]
            gate = asyncio.Event()
            all_started = asyncio.Event()
            started = [0]
            mailbox_tasks: list[asyncio.Task[Any]] = []
            miss_tasks: list[asyncio.Task[Any]] = []
            for index, remote in enumerate(callers_brokers):
                if args.waiter_mode in {"mailbox", "both"}:
                    mailbox_tasks.append(
                        asyncio.create_task(
                            remote.call(
                                ext_id, "wait", {"index": index}, timeout_seconds=20
                            )
                        )
                    )
                if args.waiter_mode in {"snapshot", "both"}:
                    miss_tasks.append(
                        asyncio.create_task(
                            remote.call(
                                ext_id,
                                "state",
                                {"room_id": f"missing_{index}", "owner_id": "missing"},
                                timeout_seconds=20,
                            )
                        )
                    )
            if mailbox_tasks:
                await asyncio.wait_for(all_started.wait(), timeout=3)
            await asyncio.sleep(1.5 if callers else 0)

            stats.reset()
            began = time.perf_counter()
            await asyncio.sleep(args.window)
            elapsed = time.perf_counter() - began
            sql_count = stats.count
            durations = stats.durations[:]
            sql_ms = statistics.fmean(durations) * 1000 if durations else 0
            total_waiters = len(mailbox_tasks) + len(miss_tasks)
            print(
                f"backend={args.backend} rooms={rooms} "
                f"mailbox_waiters={len(mailbox_tasks)} "
                f"snapshot_miss_waiters={len(miss_tasks)} "
                f"total_remote_waiters={total_waiters} window_s={elapsed:.3f} "
                f"sql={sql_count} sql_per_s={sql_count / elapsed:.1f} "
                f"sql_exec_ms_avg={sql_ms:.3f}",
                flush=True,
            )
            if callers:
                gate.set()
                await asyncio.gather(*mailbox_tasks, return_exceptions=True)
                for task in miss_tasks:
                    task.cancel()
                await asyncio.gather(*miss_tasks, return_exceptions=True)
            await broker.invalidate(ext_id)

        for db in databases:
            await db.engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=("sqlite", "postgres"), required=True)
    parser.add_argument(
        "--database-url", help="LNbits postgres:// URL; omit for SQLite"
    )
    parser.add_argument("--window", type=float, default=2.0)
    parser.add_argument(
        "--waiter-mode", choices=("mailbox", "snapshot", "both"), default="both"
    )
    args = parser.parse_args()
    if (args.backend == "postgres") != bool(args.database_url):
        parser.error("--database-url is required for postgres and omitted for sqlite")
    if args.window < 2:
        parser.error("--window must be at least 2 seconds")
    uvloop.run(run(args))


if __name__ == "__main__":
    main()
