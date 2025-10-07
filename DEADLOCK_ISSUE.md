# Database connection deadlock with optional `conn` parameter pattern

## Summary

LNbits' database API uses optional `conn` parameters in CRUD functions (e.g., `get_account(user_id, conn=None)`). When these functions are called from within an existing `db.connect()` context **without passing the connection**, it causes a deadlock due to the non-reentrant `asyncio.Lock()` used to serialize database connections.

## Impact

- **Server hangs/crashes** with no error message
- **Silent failure** - no exception raised, just infinite hang
- **Common mistake** - easy to forget passing `conn` when fetching related data in loops
- **Difficult to debug** - the hang occurs deep in the database layer with no stack trace

## Root Cause

The `Database` class in `lnbits/db.py` uses `asyncio.Lock()` to serialize connections:

```python
# lnbits/db.py line 328
self.lock = asyncio.Lock()

@asynccontextmanager
async def connect(self):
    await self.lock.acquire()  # Acquires lock
    try:
        # ... yield connection ...
    finally:
        self.lock.release()  # Releases lock

async def fetchone(self, query, values, model):
    async with self.connect() as conn:  # Tries to acquire lock again
        return await conn.fetchone(query, values, model)
```

**The deadlock sequence:**

1. Outer code: `async with db.connect()` → **lock acquired** ✓
2. Outer code calls CRUD function without passing `conn`
3. CRUD function calls `db.fetchone()` internally
4. `db.fetchone()` tries to call `db.connect()` → **waits for lock** ⏰
5. Lock won't release until outer context exits
6. Outer context won't exit until CRUD function returns
7. **Deadlock!** ∞

## Reproduction

I've created a standalone Python script that demonstrates the issue without requiring a full LNbits installation:

**[reproduce_db_deadlock.py](https://github.com/BenGWeeks/lnbits/blob/feat/shared-wallets-phase1-issue-3297/reproduce_db_deadlock.py)**

Run it with:
```bash
python3 reproduce_db_deadlock.py
```

Output shows:
- ❌ **Broken pattern**: Deadlocks after 3 seconds
- ✅ **Fixed pattern**: Works by passing `conn`
- 🚀 **Optimal pattern**: Batch query avoids N queries

## Real-World Example

This issue was discovered while implementing wallet sharing feature. Initial code:

```python
async with db.connect() as conn:
    shares = await get_wallet_shares(conn, wallet_id)

    # ❌ BUG: This causes deadlock
    for share in shares:
        account = await get_account(share.user_id)  # Forgot to pass conn!
        share.username = account.username
```

**Server hung indefinitely** with no error message. The fix:

```python
# ✅ Fixed: Pass connection
for share in shares:
    account = await get_account(share.user_id, conn)

# 🚀 Even better: Batch query
user_ids = [share.user_id for share in shares]
accounts = await get_accounts_by_ids(user_ids, conn)  # Single query
```

See full implementation: [PR #3297](https://github.com/BenGWeeks/lnbits/pull/XX) - commits [8118a606](https://github.com/BenGWeeks/lnbits/commit/8118a606)

## Proposed Solutions

### Short-term (non-breaking):

1. **Document the pattern clearly**
   - Add warnings to CRUD function docstrings
   - Add section to developer documentation
   - Include example in contribution guidelines

2. **Add deadlock detection**
   - Track which async task holds the lock
   - Raise clear error if same task tries to acquire again
   - Example: "Deadlock detected: Cannot acquire database lock from task X which already holds it. Did you forget to pass 'conn' parameter?"

3. **Promote batch query patterns**
   - Add helper functions like `get_accounts_by_ids()` for common operations
   - Show examples in docs of efficient batch fetching

### Long-term (breaking changes):

4. **Make `conn` parameter required** in CRUD functions
   - Forces explicit connection management
   - Makes API harder to misuse
   - Breaking change requiring major version bump

5. **Consider reentrant lock** or task-local connection tracking
   - Allow same task to acquire lock multiple times
   - More complex but prevents this entire class of bugs

## Recommendations

I recommend implementing solutions **#1, #2, and #3** first (non-breaking):
- Document the pattern clearly (low effort, high value)
- Add detection with helpful error message (prevents silent hangs)
- Provide batch query helpers (better performance anyway)

Then consider **#4** (required `conn`) for next major version.

## Testing

The reproduction script can be added to the test suite to ensure this pattern is detected. Example test:

```python
async def test_nested_connection_attempt_raises_error():
    """Verify that nested connection attempts raise clear error"""
    async with db.connect() as conn:
        with pytest.raises(DeadlockError, match="forgot to pass 'conn'"):
            await db.fetchone("SELECT 1")  # Should detect and raise
```

## References

- Reproduction script: [reproduce_db_deadlock.py](https://github.com/BenGWeeks/lnbits/blob/feat/shared-wallets-phase1-issue-3297/reproduce_db_deadlock.py)
- Real-world fix: [commit 8118a606](https://github.com/BenGWeeks/lnbits/commit/8118a606)
- Python asyncio.Lock docs: https://docs.python.org/3/library/asyncio-sync.html#asyncio.Lock

---

**Environment:**
- LNbits version: 1.3.0rc8
- Database: SQLite (issue applies to all database types)
- Python: 3.12

CC: @arcbtc
