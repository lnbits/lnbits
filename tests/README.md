# Wallet Sharing Tests

Comprehensive test suite for the LNbits wallet sharing/joint accounts feature.

## Structure

```
tests/
├── ui/                           # UI tests using Playwright
│   ├── screenshots/              # Test screenshots
│   ├── crud/                     # CRUD operation tests
│   │   ├── create-share.js       # Create wallet share
│   │   ├── read-shares.js        # Read wallet shares
│   │   ├── update-share.js       # Update share permissions
│   │   └── delete-share.js       # Delete/revoke share
│   ├── auth-helper.js            # Authentication helper
│   └── package.json              # Node.js dependencies
├── api/                          # API tests using Python
│   ├── create-share.py           # Create share via API
│   ├── read-shares.py            # Read shares via API
│   ├── update-share.py           # Update share via API
│   └── delete-share.py           # Delete share via API
├── run_ui_crud_tests.sh          # Run UI tests
└── run_api_tests.sh              # Run API tests
```

## Setup

### 1. Create `.env.local` in project root

```bash
# LNbits instance
TEST_LNBITS_URL=http://localhost:5001

# Admin credentials
LNBITS_ADMIN_USERNAME=your_username
LNBITS_ADMIN_PASSWORD=your_password

# For API tests
TEST_ADMIN_API_KEY=your_admin_api_key
TEST_WALLET_ID=your_wallet_id

# Secondary user for sharing tests
LNBITS_SECONDARY_USERNAME=test_user
LNBITS_SECONDARY_PASSWORD=test_password
```

### 2. Install Dependencies

**For UI tests (Node.js/Playwright):**
```bash
cd tests/ui
npm install
```

**For API tests (Python):**
```bash
pip3 install httpx loguru
# or
sudo apt install python3-httpx python3-loguru
```

## Running Tests

### Run All UI Tests
```bash
cd tests
./run_ui_crud_tests.sh
```

### Run All API Tests
```bash
cd tests
./run_api_tests.sh
```

### Run Individual Tests

**UI Test:**
```bash
cd tests/ui
node crud/create-share.js
```

**API Test:**
```bash
cd tests
python3 api/create-share.py
```

## Test Flow

Tests should be run in this order for a complete CRUD cycle:

1. **Create** - Create a new wallet share with a secondary user
2. **Read** - Verify the share exists and has correct properties
3. **Update** - Modify permissions on the share
4. **Delete** - Remove the share (revoke access)

## Screenshots

UI test screenshots are saved to `tests/ui/screenshots/` for debugging:
- `create-share-dialog.png` - Share creation dialog
- `create-share-filled.png` - Filled form before submission
- `create-share-result.png` - Result after creation
- `read-shares-dialog.png` - Share list view
- `update-share-result.png` - After permission update
- `delete-share-before.png` - Before deletion
- `delete-share-after.png` - After deletion
- `*-error.png` - Error states for debugging

## Troubleshooting

### UI Tests Fail with Login Errors
- Verify `LNBITS_ADMIN_USERNAME` and `LNBITS_ADMIN_PASSWORD` in `.env.local`
- Check that LNbits is running at `TEST_LNBITS_URL`
- Look at error screenshots in `ui/screenshots/`

### API Tests Fail with 401/403
- Verify `TEST_ADMIN_API_KEY` is correct
- Ensure the API key has admin permissions
- Check `TEST_WALLET_ID` matches the wallet owned by the admin key

### Share Creation Fails with "User not found"
- Ensure `LNBITS_SECONDARY_USERNAME` exists in your LNbits instance
- Create a test user account if needed
- Verify the username spelling is exact

### Tests Timeout
- Increase timeout in test files (default 60s for UI, none for API)
- Check server performance and network connectivity
- Use `--verbose` or check logs for details

## Contributing

When adding new tests:
1. Follow the existing naming convention (`verb-noun.js/py`)
2. Include descriptive console output
3. Take screenshots at key points (UI tests)
4. Verify cleanup (tests should not leave residual data)
5. Update this README with new test descriptions

## CI/CD Integration

These tests can be integrated into CI/CD pipelines:

```yaml
# Example GitHub Actions workflow
- name: Run API Tests
  run: ./tests/run_api_tests.sh

- name: Run UI Tests
  run: ./tests/run_ui_crud_tests.sh
```

Exit codes:
- `0` = All tests passed
- `1` = One or more tests failed
