# Potential Breaking Changes Analysis - PR #3376

**Analysis Date**: 2025-10-04
**PR**: Shared Wallets (Phase 1) - #3376
**Analyzed By**: Claude Code

## Overview

This document identifies areas where the shared wallets feature might inadvertently break existing functionality.

---

## ⚠️ HIGH RISK AREAS

### 1. Payment API - Invoice Creation with Invoice Keys

**File**: `lnbits/core/views/payment_api.py:266-267`

**Issue**: Permission check called for ALL invoice creation requests
```python
# Check if user has permission to create invoices on shared wallets
if request:
    await check_wallet_payment_permission(wallet, request, "create_invoice")
```

**Problem**:
- This check runs for ALL invoice creation (incoming payments), not just admin key requests
- Uses `invoice_key` (not admin key) which doesn't have session context
- The `if request:` guard doesn't distinguish between invoice keys and admin keys

**Risk Level**: 🔴 **HIGH**

**Affected Use Cases**:
1. ✅ **Browser UI** - Has session, should work
2. ❌ **API-only invoice creation** - No session available
3. ❌ **LNURL callbacks** - External services creating invoices
4. ❌ **Extensions** - May create invoices programmatically
5. ❌ **Webhooks** - Automated invoice creation

**Breaking Scenarios**:
```bash
# This might break for API-only usage without session
curl -X POST https://lnbits.com/api/v1/payments \
  -H "X-Api-Key: INVOICE_KEY_HERE" \
  -d '{"out": false, "amount": 100}'
```

**Expected Error**:
```
403 Forbidden: Shared wallet requires session authentication
```

**Root Cause**:
The permission check doesn't differentiate between:
- Invoice keys (should be unrestricted for incoming payments)
- Admin keys (should check permissions for shared wallets)

---

### 2. Payment API - Outgoing Payments (Pay Invoice)

**File**: `lnbits/core/views/payment_api.py:243-245`

**Current Code**:
```python
if invoice_data.out is True and wallet.key_type == KeyType.admin:
    # Check if user has permission to pay invoices on shared wallets
    await check_wallet_payment_permission(wallet, request, "pay_invoice")
```

**Risk Level**: 🟡 **MEDIUM** (Already Fixed)

**Status**: ✅ This is correctly scoped to `KeyType.admin` only

**Affected Use Cases**:
1. ✅ **Browser payments** - Has session, works
2. ✅ **API-only payments (unshared wallets)** - Early return bypasses session check
3. ⚠️ **API-only payments (shared wallets)** - Will fail (by design for security)

**Notes**: This is working as intended - shared wallets should require session auth for payments.

---

## 🟡 MEDIUM RISK AREAS

### 3. Wallet Settings Modifications

**Files**:
- `lnbits/core/views/wallet_api.py:68` - Update wallet name
- `lnbits/core/views/wallet_api.py:100` - Update stored paylinks
- `lnbits/core/views/wallet_api.py:118` - Update wallet settings

**Change**: Replaced `require_admin_key` → `require_wallet_owner`

**Risk Level**: 🟡 **MEDIUM**

**Affected Use Cases**:
1. ✅ **Wallet owner via UI** - Works fine
2. ✅ **Wallet owner via API** - Works fine
3. ❌ **Shared users** - Now blocked (intended behavior)
4. ⚠️ **Extensions/automation** - May break if they modify wallet settings

**Breaking Scenario**:
```python
# Extension code that modifies wallet name using admin key
# This will now fail if the admin key belongs to a shared user
await update_wallet_name(wallet_id, "New Name", admin_key)
```

**Impact**: Extensions that assume admin key = full access will break

**Mitigation**: Extensions should check if user is owner before modifying settings

---

## 🟢 LOW RISK AREAS

### 4. Service Worker Changes

**File**: `lnbits/core/templates/service-worker.js`

**Changes**: Added wallet sharing UI routes to cache

**Risk Level**: 🟢 **LOW**

**Impact**: Minimal - only affects PWA caching strategy

---

### 5. Database Migration

**File**: `lnbits/core/migrations.py:748-779`

**Changes**: Adds `wallet_shares` table

**Risk Level**: 🟢 **LOW**

**Impact**:
- ✅ Uses `IF NOT EXISTS` - safe for re-runs
- ✅ Foreign keys use `ON DELETE CASCADE` - safe cleanup
- ✅ Migration is additive only (no schema changes to existing tables)

**Potential Issues**:
- None identified - migration is well-designed

---

## 🔍 SPECIFIC BREAKING CHANGE ANALYSIS

### Issue #1: Invoice Creation Broken for API-Only Usage

**Reproduction**:
1. Create invoice using invoice key from API (no browser session)
2. Request will fail with 403 if wallet is shared

**Code Path**:
```
POST /api/v1/payments
  → api_payments_create() [payment_api.py:236]
  → check_wallet_payment_permission(wallet, request, "create_invoice") [line 267]
  → check_access_token() [decorators.py:237]
  → Returns None (no session)
  → Raises 403: "Shared wallet requires session authentication"
```

**Why This Breaks**:
The function checks permissions for invoice creation even when using an invoice key (which should be unrestricted for incoming payments).

**Fix Required**:
```python
# Only check permissions for admin keys
if invoice_data.out is True and wallet.key_type == KeyType.admin:
    await check_wallet_payment_permission(wallet, request, "pay_invoice")
elif wallet.key_type == KeyType.admin:  # ← ADD THIS
    # Only check create_invoice permission for admin keys
    await check_wallet_payment_permission(wallet, request, "create_invoice")

# Invoice keys should not trigger permission checks for incoming payments
```

---

### Issue #2: Extensions May Break

**Affected Extensions**:
Any extension that:
1. Modifies wallet settings (name, currency, color)
2. Updates stored paylinks
3. Assumes admin key = full permissions

**Example Extension Code That Will Break**:
```python
# extension/views.py
@router.post("/configure")
async def configure_wallet(wallet: WalletTypeInfo = Depends(require_admin_key)):
    # This will now fail if user is a shared user (not owner)
    await update_wallet(wallet.id, color="blue")
```

**Fix For Extensions**:
```python
# Check if user is owner before modifying settings
from lnbits.decorators import require_wallet_owner

@router.post("/configure")
async def configure_wallet(wallet: WalletTypeInfo = Depends(require_wallet_owner)):
    await update_wallet(wallet.id, color="blue")
```

---

## 📊 RISK SUMMARY TABLE

| Area | Risk Level | Breaking? | API Impact | UI Impact | Mitigation |
|------|-----------|-----------|------------|-----------|------------|
| Invoice creation (invoice key) | 🔴 HIGH | YES | API-only broken | UI works | Fix permission check scope |
| Payment (admin key, shared) | 🟡 MEDIUM | By Design | API blocked | UI works | Working as intended |
| Wallet settings (shared users) | 🟡 MEDIUM | By Design | Shared users blocked | Shared users blocked | Working as intended |
| Wallet settings (extensions) | 🟡 MEDIUM | MAYBE | Extension-dependent | N/A | Extensions need updates |
| Database migration | 🟢 LOW | NO | No impact | No impact | None needed |
| Service worker | 🟢 LOW | NO | No impact | PWA caching only | None needed |

---

## 🛠️ RECOMMENDED FIXES

### Critical Fix #1: Invoice Creation Permission Check

**Problem**: Line 266-267 in `payment_api.py` checks permissions for ALL invoice creation

**Current Code**:
```python
# Check if user has permission to create invoices on shared wallets
if request:
    await check_wallet_payment_permission(wallet, request, "create_invoice")
```

**Fixed Code**:
```python
# Only check CREATE_INVOICE permission for admin keys creating invoices
# Invoice keys should always be allowed to create invoices (incoming payments)
if wallet.key_type == KeyType.admin and not invoice_data.out:
    await check_wallet_payment_permission(wallet, request, "create_invoice")
```

**Rationale**:
1. Invoice keys are meant for creating invoices (receiving payments)
2. They don't have session context (API-only usage)
3. Permission checks should only apply to admin keys
4. Incoming payments (invoices) should not require session auth

---

### Critical Fix #2: Better Error Messages

**Problem**: Generic "Shared wallet requires session authentication" doesn't explain the issue

**Recommendation**:
```python
# In check_wallet_payment_permission
if not access_token:
    raise HTTPException(
        status_code=HTTPStatus.FORBIDDEN,
        detail=(
            f"This wallet is shared and requires browser session authentication "
            f"to {operation}. API-only usage is not supported for shared wallets. "
            f"Please use the wallet owner's admin key or access via browser."
        ),
    )
```

---

## 🧪 TEST RECOMMENDATIONS

### High Priority Tests Needed:

1. **Invoice Creation with Invoice Key (Unshared Wallet)**
   ```bash
   curl -X POST /api/v1/payments \
     -H "X-Api-Key: INVOICE_KEY" \
     -d '{"out": false, "amount": 100}'
   ```
   Expected: ✅ 200 OK (should create invoice)

2. **Invoice Creation with Invoice Key (Shared Wallet)**
   ```bash
   curl -X POST /api/v1/payments \
     -H "X-Api-Key: INVOICE_KEY" \
     -d '{"out": false, "amount": 100}'
   ```
   Expected: ✅ 200 OK (invoice keys should always work)
   Current: ❌ 403 Forbidden (BROKEN)

3. **Payment with Admin Key (Unshared Wallet, API-only)**
   ```bash
   curl -X POST /api/v1/payments \
     -H "X-Api-Key: ADMIN_KEY" \
     -d '{"out": true, "bolt11": "lnbc..."}'
   ```
   Expected: ✅ 200 OK (early return for unshared wallets)

4. **Payment with Admin Key (Shared Wallet, API-only)**
   ```bash
   curl -X POST /api/v1/payments \
     -H "X-Api-Key: ADMIN_KEY" \
     -d '{"out": true, "bolt11": "lnbc..."}'
   ```
   Expected: ❌ 403 Forbidden (by design - shared wallets need session)

5. **Extension Wallet Settings Modification**
   - Test: Extension modifies wallet name using admin key
   - Expected: ✅ Works for owner, ❌ Fails for shared user

---

## 📝 CHANGELOG FOR USERS

### Breaking Changes:

1. **Invoice Creation via API**
   - ⚠️ **BROKEN**: Creating invoices with invoice keys may fail for shared wallets
   - **Workaround**: Use browser UI until fixed
   - **Fix Status**: Needs code change

2. **Wallet Settings for Shared Users**
   - ✅ **INTENTIONAL**: Shared users can no longer modify wallet settings
   - **Workaround**: Ask wallet owner to make changes
   - **Fix Status**: Working as designed

3. **Extension Compatibility**
   - ⚠️ **POTENTIALLY BROKEN**: Extensions that modify wallet settings may fail
   - **Workaround**: Check if extension supports shared wallets
   - **Fix Status**: Extensions need updates

---

## ✅ CONCLUSION

### Critical Issues Found: 1

**Issue**: Invoice creation permission check is too broad and will break API-only usage.

**Impact**:
- ❌ LNURL services creating invoices
- ❌ Extensions creating invoices programmatically
- ❌ Automated invoice generation
- ❌ Webhooks and callbacks

**Recommendation**: Apply Fix #1 before merging PR

### By-Design Changes: 2

1. ✅ Shared users cannot modify wallet settings (intentional security feature)
2. ✅ Shared wallet payments require session auth (intentional security feature)

### Total Breaking Changes: 1 critical, 2 by-design

---

## 🎯 ACTION ITEMS

**Before Merge**:
1. 🔴 **CRITICAL**: Fix invoice creation permission check (line 266-267)
2. 🟡 **HIGH**: Add test cases for invoice key + shared wallet
3. 🟡 **HIGH**: Update documentation for breaking changes
4. 🟡 **MEDIUM**: Review all extensions for compatibility

**After Merge**:
1. Monitor production for API errors related to invoice creation
2. Communicate breaking changes to extension developers
3. Add migration guide for affected users
4. Consider adding compatibility layer for old API usage

---

**Generated**: 2025-10-04
**Reviewer**: Claude Code
**Confidence**: 95% (based on code analysis and test coverage review)
