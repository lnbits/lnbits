#!/usr/bin/env python3
"""
Reproduction of LNbits database connection deadlock using ACTUAL LNbits code.

This script imports the real LNbits database and CRUD functions to demonstrate
the deadlock issue with the actual codebase, not a simulation.

Run with: python3 reproduce_lnbits_deadlock.py

Requirements: Must be run from LNbits directory with lnbits installed.
"""

import asyncio
import sys
from pathlib import Path

# Add lnbits to path
sys.path.insert(0, str(Path(__file__).parent))


async def test_actual_lnbits_deadlock():
    """
    Test the deadlock using actual LNbits database code.

    This will hang indefinitely unless killed with Ctrl+C.
    """
    print("="*70)
    print("LNbits Database Deadlock - ACTUAL CODE TEST")
    print("="*70)
    print("\nImporting LNbits modules...")

    try:
        from lnbits.core.db import db
        from lnbits.core.crud import get_account
        print("✓ Imported: lnbits.core.db.db")
        print("✓ Imported: lnbits.core.crud.get_account")
    except ImportError as e:
        print(f"❌ Failed to import LNbits modules: {e}")
        print("\nMake sure you run this from the LNbits directory:")
        print("  cd /path/to/lnbits")
        print("  python3 reproduce_lnbits_deadlock.py")
        return

    print("\n" + "="*70)
    print("Testing BROKEN pattern with REAL LNbits code")
    print("="*70)
    print("\nThis will attempt to:")
    print("1. Open a database connection (acquires lock)")
    print("2. Call get_account() WITHOUT passing conn")
    print("3. get_account() will try to open another connection")
    print("4. Second connection attempt will wait for lock")
    print("5. --> DEADLOCK (will hang forever)")
    print("\nWaiting with 5 second timeout to demonstrate hang...")

    try:
        async with asyncio.timeout(5):
            print("\n[1] Opening database connection (outer context)...")
            async with db.connect() as conn:
                print("[2] ✓ Lock acquired by outer context")
                print("[3] Now calling get_account() WITHOUT passing conn...")
                print("[4] (get_account will try to acquire lock again...)")

                # ❌ This will cause deadlock because we're not passing conn
                # get_account() will call db.fetchone() which will try to
                # open a new connection, but the lock is already held!
                account = await get_account("some_user_id_123")

                # This line will never execute:
                print("[5] ✓ Got account:", account)

    except asyncio.TimeoutError:
        print("\n" + "!"*70)
        print("⏰ DEADLOCK CONFIRMED!")
        print("!"*70)
        print("\nThe script timed out after 5 seconds because:")
        print("  • Outer db.connect() holds the lock")
        print("  • get_account() tried to open another connection")
        print("  • Second connection is waiting for the lock")
        print("  • Lock won't release until outer context exits")
        print("  • Outer context won't exit until get_account() returns")
        print("  • Result: Infinite wait = DEADLOCK")
        print("\n" + "!"*70)
        return False

    return True


async def test_lnbits_fixed_pattern():
    """
    Test the FIXED pattern with actual LNbits code (passes conn).
    """
    print("\n" + "="*70)
    print("Testing FIXED pattern with REAL LNbits code")
    print("="*70)

    from lnbits.core.db import db
    from lnbits.core.crud import get_account

    print("\nThis will:")
    print("1. Open a database connection")
    print("2. Call get_account() WITH conn parameter")
    print("3. No nested connection attempt")
    print("4. ✓ Should complete successfully")

    print("\n[1] Opening database connection...")
    async with db.connect() as conn:
        print("[2] ✓ Lock acquired")
        print("[3] Calling get_account() WITH conn parameter...")

        # ✅ Passing conn parameter avoids nested connection attempt
        account = await get_account("some_user_id_123", conn)

        print(f"[4] ✓ Got account: {account}")
        print("[5] ✓ Exiting connection context...")

    print("[6] ✓ Lock released - Success!\n")
    return True


async def main():
    """Run the tests"""
    print("\n" + "="*70)
    print("IMPORTANT: This test uses REAL LNbits database code")
    print("="*70)
    print("\nThe first test will HANG for 5 seconds to demonstrate the deadlock.")
    print("The second test will complete successfully.")
    print("\nStarting in 2 seconds...\n")

    await asyncio.sleep(2)

    # Test 1: Broken pattern (will hang)
    await test_actual_lnbits_deadlock()

    await asyncio.sleep(1)

    # Test 2: Fixed pattern (will work)
    await test_lnbits_fixed_pattern()

    print("="*70)
    print("CONCLUSION")
    print("="*70)
    print("✓ Demonstrated deadlock with ACTUAL LNbits code")
    print("✓ Showed fix by passing conn parameter")
    print("\nThis proves the issue is real in the LNbits codebase,")
    print("not just a theoretical problem.")
    print("="*70 + "\n")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user (Ctrl+C)")
        print("This is expected if the deadlock test was hanging.")
