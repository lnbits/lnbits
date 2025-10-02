#!/bin/bash
# Run API tests for wallet sharing (Python)

set +e

echo "🐍 Running Wallet Sharing API Tests (Python)"
echo "============================================="

# Ensure we're in the tests directory
cd "$(dirname "$0")"

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "❌ python3 not found. Please install Python 3."
    exit 1
fi

# Check if dependencies are available
echo "🔍 Checking dependencies..."
if python3 -c "import httpx, loguru" 2>/dev/null; then
    echo "✅ Dependencies available"
else
    echo "❌ Missing dependencies. Please install with:"
    echo "   pip3 install httpx loguru"
    echo "   or: sudo apt install python3-httpx python3-loguru"
    exit 1
fi

# Check for .env.local
if [ ! -f "../.env.local" ]; then
    echo "⚠️  Warning: .env.local not found in project root"
    echo "   Please create it with the following variables:"
    echo "   - TEST_LNBITS_URL=http://localhost:5001"
    echo "   - TEST_ADMIN_API_KEY=your_admin_key"
    echo "   - TEST_WALLET_ID=your_wallet_id"
    echo "   - LNBITS_SECONDARY_USERNAME=test_user"
fi

# Define test files
API_TESTS=(
    "./api/create-share.py:Create Share"
    "./api/read-shares.py:Read Shares"
    "./api/update-share.py:Update Share"
    "./api/delete-share.py:Delete Share"
)

PASSED=0
FAILED=0

echo
echo "Running wallet sharing API tests..."

for test_entry in "${API_TESTS[@]}"; do
    IFS=':' read -r test_file test_name <<< "$test_entry"

    if [ -f "$test_file" ]; then
        echo
        echo "🧪 Testing: $test_name"
        echo "   Running: $test_file"

        # Make executable
        chmod +x "$test_file" 2>/dev/null

        if python3 "$test_file" 2>/dev/null; then
            echo "   ✅ PASSED: $test_name"
            ((PASSED++))
        else
            echo "   ❌ FAILED: $test_name"
            ((FAILED++))
        fi
    else
        echo "⚠️ SKIPPED: $test_name (file not found: $test_file)"
        ((FAILED++))
    fi
done

TOTAL=$((PASSED + FAILED))

echo
echo "============================================="
echo "📊 API Test Results: $PASSED/$TOTAL tests passed"

if [ $PASSED -eq $TOTAL ] && [ $TOTAL -gt 0 ]; then
    echo "🎉 All API tests passed!"
    exit 0
else
    echo "💥 Some API tests failed."
    exit 1
fi
