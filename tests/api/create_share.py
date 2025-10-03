#!/usr/bin/env python3
"""
Test: Create wallet share via API
This test creates a new wallet share with another user using the REST API
"""

import asyncio
import os
import secrets
import string

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
        "secondary_username": config.get(
            "LNBITS_SECONDARY_USERNAME", os.getenv("LNBITS_SECONDARY_USERNAME")
        ),
    }


async def test_create_share():
    """Test creating a wallet share"""
    config = load_config()

    if not config["admin_key"]:
        logger.error("❌ TEST_ADMIN_API_KEY must be set in .env.local")
        return False

    if not config["secondary_username"]:
        logger.error("❌ LNBITS_SECONDARY_USERNAME must be set in .env.local")
        return False

    logger.info("🚀 Starting create wallet share API test...")
    logger.info(f"📍 Base URL: {config['base_url']}")
    logger.info(f"👤 Sharing with: {config['secondary_username']}")

    async with httpx.AsyncClient() as client:
        # Step 0: Always create a fresh test wallet for this test
        random_name = "".join(
            secrets.choice(string.ascii_letters + string.digits) for _ in range(10)
        )
        logger.info("📝 Step 0: Creating fresh test wallet...")
        response = await client.post(
            f"{config['base_url']}/api/v1/wallet",
            headers={"X-Api-Key": config["admin_key"]},
            json={"name": f"test_{random_name}"},
        )

        if response.status_code not in [200, 201]:
            logger.error(f"❌ Failed to create test wallet: {response.status_code}")
            logger.error(f"   Response: {response.text}")
            return False

        wallet_data = response.json()
        wallet_id = wallet_data["id"]
        admin_key = wallet_data["adminkey"]
        logger.info(f"✅ Created fresh test wallet: {wallet_id}")

        config["wallet_id"] = wallet_id
        config["admin_key"] = admin_key
        # Step 1: Get initial share count
        logger.info("📝 Step 1: Getting initial share count...")
        response = await client.get(
            f"{config['base_url']}/api/v1/wallet_shares/{config['wallet_id']}",
            headers={"X-Api-Key": config["admin_key"]},
        )

        if response.status_code != 200:
            logger.error(f"❌ Failed to get initial shares: {response.status_code}")
            return False

        initial_shares = response.json()
        initial_count = len(initial_shares) if isinstance(initial_shares, list) else 0
        logger.info(f"📊 Initial share count: {initial_count}")

        # Step 2: Create new share
        logger.info("📝 Step 2: Creating new share...")
        create_data = {
            "user_id": config["secondary_username"],
            "permissions": 1,  # VIEW only
        }

        response = await client.post(
            f"{config['base_url']}/api/v1/wallet_shares/{config['wallet_id']}",
            headers={
                "X-Api-Key": config["admin_key"],
                "Content-Type": "application/json",
            },
            json=create_data,
        )

        if response.status_code not in [200, 201]:
            logger.error(f"❌ Failed to create share: {response.status_code}")
            logger.error(f"   Response: {response.text}")
            return False

        response_data = response.json()
        created_share = response_data.get("share", response_data)
        logger.info("✅ Share created successfully!")
        logger.info(f"   ID: {created_share['id']}")
        logger.info(
            f"   User: {created_share.get('username', created_share['user_id'])}"
        )
        logger.info(f"   Permissions: {created_share['permissions']}")

        # Step 3: Verify share was created
        logger.info("📝 Step 3: Verifying share creation...")
        response = await client.get(
            f"{config['base_url']}/api/v1/wallet_shares/{config['wallet_id']}",
            headers={"X-Api-Key": config["admin_key"]},
        )

        if response.status_code != 200:
            logger.error(f"❌ Failed to verify shares: {response.status_code}")
            return False

        final_shares = response.json()
        final_count = len(final_shares) if isinstance(final_shares, list) else 0
        logger.info(f"📊 Final share count: {final_count}")
        logger.info(f"📈 Count change: +{final_count - initial_count}")

        # Verify the specific share exists
        share_found = any(s["id"] == created_share["id"] for s in final_shares)

        if share_found and final_count >= initial_count:
            logger.info("🎉 SUCCESS! Wallet share created and verified!")
            return True
        else:
            logger.error("❌ FAILED: Share not found in verification")
            return False


if __name__ == "__main__":
    success = asyncio.run(test_create_share())
    exit(0 if success else 1)
