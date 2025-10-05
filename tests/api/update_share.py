#!/usr/bin/env python3
"""
Test: Update wallet share permissions via API
This test updates permissions on an existing wallet share using the REST API
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


async def test_update_share():
    """Test updating wallet share permissions"""
    config = load_config()

    if not config["admin_key"]:
        logger.error("❌ TEST_ADMIN_API_KEY must be set in .env.local")
        return False

    if not config["wallet_id"]:
        logger.error("❌ TEST_WALLET_ID must be set in .env.local")
        return False

    logger.info("🚀 Starting update wallet share API test...")
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

        if not isinstance(shares, list) or len(shares) == 0:
            logger.warning("⚠️  No shares found to update. Please create a share first.")
            return True  # Not a failure, just nothing to update

        share_to_update = shares[0]
        logger.info(f"📄 Found share to update: {share_to_update['id']}")
        logger.info(f"   Current permissions: {share_to_update['permissions']}")

        # Step 2: Update permissions (using admin key)
        logger.info("📝 Step 2: Updating share permissions...")

        # Toggle between VIEW (1) and VIEW+CREATE_INVOICE (3)
        new_permissions = 3 if share_to_update["permissions"] == 1 else 1

        response = await client.put(
            f"{config['base_url']}/api/v1/wallet_shares/{share_to_update['id']}",
            headers={
                "X-Api-Key": config["admin_key"],
                "Content-Type": "application/json",
            },
            json={"permissions": new_permissions},
        )

        if response.status_code != 200:
            logger.error(f"❌ Failed to update share: {response.status_code}")
            logger.error(f"   Response: {response.text}")
            return False

        updated_share = response.json()
        logger.info("✅ Share updated successfully!")
        logger.info(f"   New permissions: {updated_share['permissions']}")

        # Step 3: Verify update
        logger.info("📝 Step 3: Verifying update...")
        response = await client.get(
            f"{config['base_url']}/api/v1/wallet_shares/{config['wallet_id']}",
            headers={"X-Api-Key": config["admin_key"]},
        )

        if response.status_code != 200:
            logger.error(f"❌ Failed to verify: {response.status_code}")
            return False

        updated_shares = response.json()
        verified_share = next(
            (s for s in updated_shares if s["id"] == share_to_update["id"]), None
        )

        if verified_share and verified_share["permissions"] == new_permissions:
            logger.info("✅ Update verified - permissions match!")
            logger.info("\n🎉 SUCCESS! Share updated successfully!")
            return True
        else:
            logger.error("❌ Update verification failed - permissions do not match")
            return False


if __name__ == "__main__":
    success = asyncio.run(test_update_share())
    exit(0 if success else 1)
