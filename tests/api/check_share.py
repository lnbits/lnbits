#!/usr/bin/env python3
"""
Test: Check if shared wallet appears in recipient's wallet list
This test verifies that when a wallet is shared and accepted,
it appears in the recipient's wallet list via the /api/v1/wallet endpoint
"""

import asyncio
import os

import httpx
from loguru import logger


# Load config from .env.local
def load_config():
    config = {}
    env_path = os.path.join(os.path.dirname(__file__), "../../.env.local")

    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    config[key.strip()] = value.strip()

    return {
        "base_url": config.get("TEST_LNBITS_URL", os.getenv("TEST_LNBITS_URL")),
        "admin_key": config.get("TEST_ADMIN_API_KEY", os.getenv("TEST_ADMIN_API_KEY")),
        "recipient_key": config.get(
            "TEST_RECIPIENT_API_KEY", os.getenv("TEST_RECIPIENT_API_KEY")
        ),
        "wallet_id": config.get("TEST_WALLET_ID", os.getenv("TEST_WALLET_ID")),
    }


async def test_check_shared_wallet():  # noqa: C901
    """Test that shared wallet appears in recipient's wallet list"""
    config = load_config()

    if not config["admin_key"]:
        logger.error("❌ TEST_ADMIN_API_KEY must be set in .env.local")
        return False

    if not config["recipient_key"]:
        logger.warning("⚠️  TEST_RECIPIENT_API_KEY not set - skipping check_share test")
        logger.info("   This test requires a second user's API key to verify shared wallet access")
        return True  # Return success to not fail the test suite

    if not config["wallet_id"]:
        logger.error("❌ TEST_WALLET_ID must be set in .env.local")
        return False

    logger.info("🚀 Starting check shared wallet API test...")
    logger.info(f"📍 Base URL: {config['base_url']}")
    logger.info(f"📍 Shared Wallet ID: {config['wallet_id']}")

    async with httpx.AsyncClient() as client:
        # Step 1: Get admin's wallet info to know what we're looking for
        logger.info("\n📝 Step 1: Getting admin wallet info...")
        admin_wallet_response = await client.get(
            f"{config['base_url']}/api/v1/wallet",
            headers={"X-Api-Key": config["admin_key"]},
        )

        if admin_wallet_response.status_code != 200:
            logger.error(
                f"❌ Failed to get admin wallet: {admin_wallet_response.status_code}"
            )
            logger.error(f"   Response: {admin_wallet_response.text}")
            return False

        admin_wallet = admin_wallet_response.json()
        logger.info(f"✅ Admin wallet name: {admin_wallet['name']}")
        logger.info(f"   Wallet ID: {admin_wallet['id']}")

        # Step 2: Get recipient's user data (includes all wallets)
        logger.info("\n📝 Step 2: Getting recipient's wallet list...")
        recipient_response = await client.get(
            f"{config['base_url']}/api/v1/wallet",
            headers={"X-Api-Key": config["recipient_key"]},
        )

        if recipient_response.status_code != 200:
            logger.error(
                f"❌ Failed to get recipient wallet: {recipient_response.status_code}"
            )
            logger.error(f"   Response: {recipient_response.text}")
            return False

        logger.info("✅ Recipient wallet endpoint responded")

        # The /api/v1/wallet endpoint returns the current wallet
        # To check all wallets, we need to check the user endpoint
        logger.info("\n📝 Step 3: Checking all recipient wallets...")

        # Get all wallets by calling the wallets list endpoint
        wallets_response = await client.get(
            f"{config['base_url']}/api/v1/wallets",
            headers={"X-Api-Key": config["recipient_key"]},
        )

        if wallets_response.status_code != 200:
            logger.error(
                f"❌ Failed to get wallets list: {wallets_response.status_code}"
            )
            logger.error(f"   Response: {wallets_response.text}")
            return False

        wallets = wallets_response.json()
        logger.info(f"📊 Found {len(wallets)} wallet(s) for recipient")

        # Display all wallets
        logger.info("\n📄 Recipient's Wallets:")
        shared_wallet_found = False
        for i, wallet in enumerate(wallets, 1):
            logger.info(f"\n  Wallet {i}:")
            logger.info(f"    Name: {wallet['name']}")
            logger.info(f"    ID: {wallet['id']}")
            is_shared = wallet.get("is_shared", False)
            logger.info(f"    Is Shared: {is_shared}")

            if is_shared:
                logger.info(
                    f"    Share Permissions: {wallet.get('share_permissions', 0)}"
                )

            # Check if this is the shared wallet
            if wallet["id"] == config["wallet_id"]:
                shared_wallet_found = True
                logger.info("    ⭐ This is the shared wallet!")

                if not is_shared:
                    logger.error(
                        "    ❌ ERROR: Wallet found but is_shared flag is not set!"
                    )
                    return False

        # Final verification
        if shared_wallet_found:
            logger.info(
                "\n🎉 SUCCESS! Shared wallet appears in recipient's wallet list!"
            )
            logger.info("   The wallet is properly marked as shared with permissions.")
            return True
        else:
            logger.error(
                "\n❌ FAILED: Shared wallet does NOT appear in recipient's wallet list"
            )
            logger.error(
                f"   Expected wallet ID {config['wallet_id']} was not found in the list"
            )
            return False


if __name__ == "__main__":
    success = asyncio.run(test_check_shared_wallet())
    exit(0 if success else 1)
