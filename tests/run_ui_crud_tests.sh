#!/bin/bash
# Run UI CRUD tests for wallet sharing (Playwright/Node.js)

set +e

echo "🎭 Running Wallet Sharing UI CRUD Tests (Playwright)"
echo "====================================================="

# Ensure we're in the tests directory
cd "$(dirname "$0")"

# Check if Node.js is available
if ! command -v node &> /dev/null; then
    echo "❌ node not found. Please install Node.js."
    exit 1
fi

# Check if Playwright is installed
if [ ! -d "ui/node_modules" ]; then
    echo "⚠️  Playwright not installed. Installing dependencies..."
    cd ui && npm install playwright && cd ..
fi

# Create screenshots directory if it doesn't exist
mkdir -p ui/screenshots

# Check for .env.local
if [ ! -f "../.env.local" ]; then
    echo "⚠️  Warning: .env.local not found in project root"
    echo "   Please create it with the following variables:"
    echo "   - TEST_LNBITS_URL=http://localhost:5001"
    echo "   - LNBITS_ADMIN_USERNAME=your_username"
    echo "   - LNBITS_ADMIN_PASSWORD=your_password"
    echo "   - LNBITS_SECONDARY_USERNAME=test_user"
fi

echo
echo "🧪 Running CRUD operation tests..."
echo

PASSED=0
FAILED=0

# Define CRUD tests to run (in order)
CRUD_TESTS=(
    "crud/create-wallet.js:Create Wallet"
    "crud/create-share.js:Create Share"
    "crud/read-shares.js:Read Shares"
    "crud/update-share.js:Update Share"
    "crud/revoke-share.js:Revoke Share"
)

# Run each test
for test_entry in "${CRUD_TESTS[@]}"; do
    IFS=':' read -r test_file test_name <<< "$test_entry"

    if [ -f "ui/$test_file" ]; then
        echo "📝 Testing: $test_name"
        echo "   Running: ui/$test_file"

        cd ui
        if timeout 60 node "$test_file" > test_output.tmp 2>&1; then
            # Check output for success indicators
            if grep -q "✅.*SUCCESS\|passed\|PASSED" test_output.tmp; then
                echo "   ✅ PASSED: $test_name"
                ((PASSED++))
            else
                echo "   ⚠️  COMPLETED: $test_name (check output for details)"
                tail -5 test_output.tmp | sed 's/^/      /'
                ((PASSED++))
            fi
        else
            echo "   ❌ FAILED: $test_name"
            tail -10 test_output.tmp | sed 's/^/      /'
            ((FAILED++))
        fi
        rm -f test_output.tmp
        cd ..
        echo
    else
        echo "⚠️  SKIPPED: $test_name (file not found: ui/$test_file)"
        ((FAILED++))
        echo
    fi
done

TOTAL=$((PASSED + FAILED))

echo "====================================================="
echo "📊 UI CRUD Test Results: $PASSED/$TOTAL tests passed"
echo

if [ $PASSED -eq $TOTAL ] && [ $TOTAL -gt 0 ]; then
    echo "🎉 All UI CRUD tests passed!"
    echo
    echo "📁 Screenshots saved in: ui/screenshots/"
    exit 0
else
    echo "💥 Some UI CRUD tests failed."
    echo
    echo "📁 Screenshots saved in: ui/screenshots/"
    echo "   View them to debug any failures"
    exit 1
fi
