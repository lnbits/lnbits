# Wallet Sharing UI Tests

Playwright-based UI tests for the wallet sharing feature.

## Prerequisites

1. **Node.js and Playwright**

   ```bash
   cd tests/ui
   npm install playwright
   ```

2. **LNbits Running**

   ```bash
   uv run lnbits --port 5001
   ```

3. **Test Users Created**

   You need two user accounts:
   - Primary admin user (for creating shares)
   - Secondary user (for receiving shares)

   **Option A: Manual Setup (Recommended)**
   1. Open http://localhost:5001
   2. Create account with username `admin` and password `DKTD7Nn6AmMXH1M1rEZ&`
   3. Log out
   4. Create account with username `edit.weeks` and password `Hfd75kEtjp$&PrNAgp%A`

   **Option B: Use Existing Users**
   1. Update `.env.local` with your existing usernames and passwords
   2. Make sure both users have wallets created

## Configuration

Create or update `../../.env.local`:

```bash
# LNbits instance
TEST_LNBITS_URL=http://localhost:5001

# Admin credentials (user who will create shares)
LNBITS_ADMIN_USERNAME=admin
LNBITS_ADMIN_PASSWORD=your_password_here

# Secondary user for sharing tests (user who will receive shares)
LNBITS_SECONDARY_USERNAME=edit.weeks
LNBITS_SECONDARY_PASSWORD=their_password_here
```

## Running Tests

### Run All CRUD Tests

```bash
cd tests
./run_ui_crud_tests.sh
```

### Run Individual Tests

```bash
cd tests/ui

# Create a wallet share
node crud/create-share.js

# Read/list wallet shares
node crud/read-shares.js

# Update share permissions
node crud/update-share.js

# Check shared wallet appears for recipient
node crud/check-share.js

# Delete a share
node crud/delete-share.js
```

## Test Flow

The tests follow this sequence:

1. **create-share.js** - Admin logs in and shares wallet with `edit.weeks`
2. **read-shares.js** - Admin views list of shares
3. **update-share.js** - Admin updates permissions on the share
4. **check-share.js** - `edit.weeks` logs in and verifies shared wallet appears
5. **delete-share.js** - Admin deletes the share

## Debugging

Screenshots are saved to `tests/ui/screenshots/` for debugging test failures:

- `check-share-error.png` - Error state
- `check-share-logged-in.png` - After login
- `check-share-found-wallet.png` - When shared wallet is found
- `check-share-final.png` - Final state

## Common Issues

### "Invalid credentials" Error

- Verify users exist in the database
- Check passwords in `.env.local` match actual user passwords
- Try logging in manually to confirm credentials

### "Could not retrieve wallet ID"

- User needs at least one wallet created
- Log in manually and create a wallet first

### Login Not Working

- Check LNbits is running on the correct port (5001)
- Verify `TEST_LNBITS_URL` in `.env.local`
- Check browser console in screenshots for errors
