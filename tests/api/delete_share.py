#!/usr/bin/env python3
"""
Test: Delete wallet share via API
This test deletes/revokes an existing wallet share using the REST API
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
        "wallet_id": config.get("TEST_WALLET_ID", os.getenv("TEST_WALLET_ID")),
        "username": config.get(
            "LNBITS_ADMIN_USERNAME", os.getenv("LNBITS_ADMIN_USERNAME")
        ),
        "password": config.get(
            "LNBITS_ADMIN_PASSWORD", os.getenv("LNBITS_ADMIN_PASSWORD")
        ),
    }


async def test_delete_share():  # noqa: C901
    """Test deleting wallet share"""
    config = load_config()

    if not config["admin_key"]:
        logger.error("❌ TEST_ADMIN_API_KEY must be set in .env.local")
        return False

    if not config["wallet_id"]:
        logger.error("❌ TEST_WALLET_ID must be set in .env.local")
        return False

    logger.info("🚀 Starting delete wallet share API test...")
    logger.info(f"📍 Base URL: {config['base_url']}")
    logger.info(f"📍 Wallet ID: {config['wallet_id']}")

    async with httpx.AsyncClient() as client:
        # Step 1: Get existing shares
        logger.info("📝 Step 1: Getting existing shares...")
        response = await client.get(
            f"{config['base_url']}/api/v1/wallet_shares/{config['wallet_id']}",
            headers={"X-Api-Key": config["admin_key"]},
        )

        if response.status_code != 200:
            logger.error(f"❌ Failed to get shares: {response.status_code}")
            return False

        shares = response.json()
        initial_count = len(shares) if isinstance(shares, list) else 0

        logger.info(f"📊 Initial share count: {initial_count}")

        if initial_count == 0:
            logger.warning("⚠️  No shares found to delete. Please create a share first.")
            return True  # Not a failure, just nothing to delete

        share_to_delete = shares[0]
        logger.info(f"📄 Found share to delete: {share_to_delete['id']}")
        logger.info(f"   User: {share_to_delete.get('username', 'Unknown')}")

        # Security check: Verify user_id is NOT exposed
        if "user_id" in share_to_delete:
            logger.error(
                "❌ SECURITY ISSUE: user_id should not be exposed in API response!"
            )
            return False

        # Step 2: Delete share (using admin key)
        logger.info("📝 Step 2: Deleting share...")
        response = await client.delete(
            f"{config['base_url']}/api/v1/wallet_shares/{share_to_delete['id']}",
            headers={"X-Api-Key": config["admin_key"]},
        )

        if response.status_code != 200:
            logger.error(f"❌ Failed to delete share: {response.status_code}")
            logger.error(f"   Response: {response.text}")
            return False

        logger.info("✅ Share deleted successfully!")

        # Step 3: Verify deletion
        logger.info("📝 Step 3: Verifying deletion...")
        response = await client.get(
            f"{config['base_url']}/api/v1/wallet_shares/{config['wallet_id']}",
            headers={"X-Api-Key": config["admin_key"]},
        )

        if response.status_code != 200:
            logger.error(f"❌ Failed to verify: {response.status_code}")
            return False

        updated_shares = response.json()
        final_count = len(updated_shares) if isinstance(updated_shares, list) else 0

        logger.info(f"📊 Final share count: {final_count}")
        logger.info(f"📉 Count change: {final_count - initial_count}")

        # Verify the specific share is gone
        still_exists = any(s["id"] == share_to_delete["id"] for s in updated_shares)

        if not still_exists and final_count == initial_count - 1:
            logger.info("✅ Deletion verified - share no longer exists!")
            logger.info("\n🎉 SUCCESS! Share deleted successfully!")
            return True
        else:
            logger.error("❌ Deletion verification failed")
            if still_exists:
                logger.error("   Share still exists after deletion")
            if final_count != initial_count - 1:
                logger.error(
                    f"   Expected count: {initial_count - 1}, Got: {final_count}"
                )
            return False


if __name__ == "__main__":
    success = asyncio.run(test_delete_share())
    exit(0 if success else 1)
