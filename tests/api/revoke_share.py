#!/usr/bin/env python3
"""
Test: Revoke wallet share via API
This test revokes an existing wallet share using the REST API (soft delete)
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


async def test_revoke_share():  # noqa: C901
    """Test revoking wallet share (soft delete)"""
    config = load_config()

    if not config["admin_key"]:
        logger.error("❌ TEST_ADMIN_API_KEY must be set in .env.local")
        return False

    if not config["wallet_id"]:
        logger.error("❌ TEST_WALLET_ID must be set in .env.local")
        return False

    logger.info("🚀 Starting revoke wallet share API test...")
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

        logger.info(f"📊 Total share count: {initial_count}")

        if initial_count == 0:
            logger.warning("⚠️  No shares found to revoke. Please create a share first.")
            return True  # Not a failure, just nothing to revoke

        # Find a share that can be revoked (pending or accepted)
        share_to_revoke = None
        for share in shares:
            if share.get("status") in ["pending", "accepted"]:
                share_to_revoke = share
                break

        if not share_to_revoke:
            logger.warning("⚠️  No pending/accepted shares found to revoke.")
            return True  # Not a failure, just nothing to revoke

        logger.info(f"📄 Found share to revoke: {share_to_revoke['id']}")
        logger.info(f"   User: {share_to_revoke.get('username', 'Unknown')}")
        logger.info(f"   Current status: {share_to_revoke.get('status', 'unknown')}")

        # Security check: Verify user_id is NOT exposed
        if "user_id" in share_to_revoke:
            logger.error(
                "❌ SECURITY ISSUE: user_id should not be exposed in API response!"
            )
            return False

        # Step 2: Revoke share (using admin key)
        logger.info("📝 Step 2: Revoking share...")
        response = await client.delete(
            f"{config['base_url']}/api/v1/wallet_shares/{share_to_revoke['id']}",
            headers={"X-Api-Key": config["admin_key"]},
        )

        if response.status_code != 200:
            logger.error(f"❌ Failed to revoke share: {response.status_code}")
            logger.error(f"   Response: {response.text}")
            return False

        logger.info("✅ Share revoked successfully!")

        # Step 3: Verify revocation (soft delete - status changed to 'revoked')
        logger.info("📝 Step 3: Verifying revocation...")
        response = await client.get(
            f"{config['base_url']}/api/v1/wallet_shares/{config['wallet_id']}",
            headers={"X-Api-Key": config["admin_key"]},
        )

        if response.status_code != 200:
            logger.error(f"❌ Failed to verify: {response.status_code}")
            return False

        updated_shares = response.json()
        final_count = len(updated_shares) if isinstance(updated_shares, list) else 0

        logger.info(f"📊 Total share count: {final_count} (unchanged - soft delete)")

        # Find the revoked share
        revoked_share = next(
            (s for s in updated_shares if s["id"] == share_to_revoke["id"]), None
        )

        if not revoked_share:
            logger.error("❌ Share not found after revocation")
            return False

        if revoked_share.get("status") == "revoked":
            logger.info("✅ Revocation verified - status changed to 'revoked'!")
            logger.info(f"   Share ID: {revoked_share['id']}")
            logger.info(f"   New status: {revoked_share['status']}")
            logger.info("\n🎉 SUCCESS! Share revoked successfully!")
            return True
        else:
            logger.error("❌ Revocation verification failed")
            logger.error(
                f"   Expected status: 'revoked', Got: '{revoked_share.get('status')}'"
            )
            return False


if __name__ == "__main__":
    success = asyncio.run(test_revoke_share())
    exit(0 if success else 1)
