#!/usr/bin/env python3
"""
Minimal reproduction of LNbits database connection deadlock issue.

This script demonstrates the deadlock that occurs when calling a CRUD function
that internally opens a database connection while already inside a connection context.

Run with: python3 reproduce_db_deadlock.py

No dependencies required beyond Python 3.10+ stdlib.
"""

import asyncio
from contextlib import asynccontextmanager
from typing import Any


class SimplifiedDatabase:
    """
    Simplified version of LNbits Database class that demonstrates the lock pattern.

    This mimics the pattern in lnbits/db.py:
    - Uses asyncio.Lock() to serialize database connections
    - connect() acquires lock, yields connection, releases lock
    - fetchone() internally calls connect() if no connection provided
    """

    def __init__(self, name: str):
        self.name = name
        self.lock = asyncio.Lock()
        print(f"[DB] Created database '{name}' with lock: {id(self.lock)}")

    @asynccontextmanager
    async def connect(self):
        """
        Simulates opening a database connection.
        IMPORTANT: Acquires a lock to serialize access (SQLite requirement).
        """
        print("[DB] Attempting to acquire lock...")
        await self.lock.acquire()
        print("[DB] ✓ Lock acquired!")

        try:
            # Simulate connection object
            connection = {"db": self.name, "connected": True}
            yield connection
        finally:
            print("[DB] Releasing lock...")
            self.lock.release()
            print("[DB] ✓ Lock released!")

    async def fetchone(self, query: str, conn: dict | None = None) -> dict[str, Any]:
        """
        Fetch a single record.

        If conn is provided, use it.
        If conn is None, open a new connection (acquires lock internally).
        """
        if conn:
            print(f"[QUERY] Using provided connection: {query}")
            await asyncio.sleep(0.1)  # Simulate query time
            return {"result": "data"}
        else:
            print("[QUERY] No connection provided, opening new connection...")
            async with self.connect() as _new_conn:
                print(f"[QUERY] Executing: {query}")
                await asyncio.sleep(0.1)  # Simulate query time
                return {"result": "data"}


async def get_account(user_id: str, conn: dict | None = None, db=None) -> dict:
    """
    Simulates a CRUD function like get_account() in LNbits.

    This is the pattern that causes the issue:
    - conn parameter is optional
    - If not provided, it calls db.fetchone() which tries to open a new connection
    """
    print(
        f"[CRUD] get_account(user_id={user_id}, conn={'provided' if conn else 'None'})"
    )
    return await db.fetchone(
        f"SELECT * FROM accounts WHERE id = '{user_id}'",  # noqa: S608
        conn,
    )


async def broken_pattern():
    """
    ❌ BROKEN: This will DEADLOCK

    Demonstrates calling get_account() inside a connection context
    without passing the connection.
    """
    print("\n" + "=" * 70)
    print("❌ TESTING BROKEN PATTERN (will deadlock)")
    print("=" * 70)

    db = SimplifiedDatabase("lnbits")

    try:
        async with asyncio.timeout(3):  # 3 second timeout to prevent infinite hang
            async with db.connect() as _conn:
                print("\n[MAIN] Inside connection context, lock is held")
                print("[MAIN] Fetching wallet shares...")

                # Simulate getting shares that need related user data
                share_user_ids = ["user1", "user2", "user3"]

                for user_id in share_user_ids:
                    print(f"\n[MAIN] Fetching account for {user_id}...")

                    # ❌ BUG: Not passing conn, so get_account() will try to
                    # open a new connection, which will try to acquire the
                    # lock that we're already holding -> DEADLOCK
                    account = await get_account(user_id, conn=None, db=db)
                    print(f"[MAIN] Got account: {account}")

    except asyncio.TimeoutError:
        print("\n" + "!" * 70)
        print("⏰ DEADLOCK DETECTED: Operation timed out after 3 seconds!")
        print("   The inner get_account() call is waiting for the lock,")
        print("   but the lock won't release until the outer context exits,")
        print("   which won't happen until get_account() returns.")
        print("   Result: Infinite hang / deadlock")
        print("!" * 70)
        return False

    return True


async def fixed_pattern():
    """
    ✅ FIXED: This works correctly

    Demonstrates passing the connection to avoid nested lock acquisition.
    """
    print("\n" + "=" * 70)
    print("✅ TESTING FIXED PATTERN (passes connection)")
    print("=" * 70)

    db = SimplifiedDatabase("lnbits")

    async with db.connect() as conn:
        print("\n[MAIN] Inside connection context, lock is held")
        print("[MAIN] Fetching wallet shares...")

        share_user_ids = ["user1", "user2", "user3"]

        for user_id in share_user_ids:
            print(f"\n[MAIN] Fetching account for {user_id}...")

            # ✅ FIXED: Pass the connection so get_account() doesn't try
            # to open a new connection
            account = await get_account(user_id, conn=conn, db=db)
            print(f"[MAIN] Got account: {account}")

    print("\n✓ Success! All queries completed without deadlock")
    return True


async def optimal_batch_pattern():
    """
    🚀 OPTIMAL: Batch query pattern (what we implemented)

    Even better than passing conn: fetch all accounts in one query.
    """
    print("\n" + "=" * 70)
    print("🚀 TESTING OPTIMAL PATTERN (batch query)")
    print("=" * 70)

    db = SimplifiedDatabase("lnbits")

    async with db.connect() as conn:
        print("\n[MAIN] Inside connection context, lock is held")
        print("[MAIN] Fetching wallet shares...")

        share_user_ids = ["user1", "user2", "user3"]

        # 🚀 OPTIMAL: Fetch all accounts in ONE query using IN clause
        print(f"\n[MAIN] Batch fetching all accounts: {share_user_ids}")
        user_ids_str = "', '".join(share_user_ids)
        result = await db.fetchone(
            f"SELECT * FROM accounts WHERE id IN ('{user_ids_str}')", conn  # noqa: S608
        )
        print(f"[MAIN] Got all accounts in single query: {result}")

        # Map results to shares (simulated)
        for user_id in share_user_ids:
            print(f"[MAIN] Mapped account for {user_id}")

    print("\n✓ Success! Batch query is both deadlock-free AND more efficient!")
    print("  (1 query instead of N queries)")
    return True


async def main():
    """Run all test patterns"""
    print("\n" + "=" * 70)
    print("LNbits Database Deadlock Reproduction")
    print("=" * 70)
    print("\nThis script demonstrates the database connection deadlock that")
    print("occurs when CRUD functions with optional 'conn' parameters are")
    print("called from within a connection context without passing the connection.")
    print("\nThe issue:")
    print("- LNbits uses asyncio.Lock() to serialize database connections")
    print("- If you forget to pass 'conn' parameter, the inner function tries")
    print("  to acquire the same lock that's already held -> deadlock")

    # Test 1: Broken pattern (will deadlock)
    await broken_pattern()
    await asyncio.sleep(1)  # Brief pause between tests

    # Test 2: Fixed pattern (passes conn)
    await fixed_pattern()
    await asyncio.sleep(1)

    # Test 3: Optimal pattern (batch query)
    await optimal_batch_pattern()

    print("\n" + "=" * 70)
    print("Summary:")
    print("=" * 70)
    print("❌ Broken: Calling CRUD function without passing conn -> DEADLOCK")
    print("✅ Fixed:  Always pass conn parameter when inside connection context")
    print("🚀 Optimal: Use batch queries to avoid N separate queries entirely")
    print("\nRecommendations for LNbits:")
    print("1. Make 'conn' parameter required in CRUD functions (breaking change)")
    print("2. Add detection for nested connection attempts with clear error")
    print("3. Document this pattern clearly in developer docs")
    print("4. Promote batch query patterns for common operations")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
